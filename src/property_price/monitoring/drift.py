"""Energy-label drift check with the Population Stability Index (PSI).
Reference : harmonised labels (coef 1.9) of DPEs in the 12 months before the test period.
Check 1   : real recent DPEs                  -> should be stable (harmonisation works)
Check 2   : same DPEs re-labelled at --coefficient (default 1.7, the 2027 rule) -> drift expected
Usage: python -m property_price.monitoring.drift [--coefficient 1.7]"""

import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import plotly.graph_objects as go

from property_price.logging_config import get_logger, log_metric
from property_price.params import params

log = get_logger(__name__)
DPE = "data/interim/dpe_flat/*.parquet"
DB = "data/raw/dpe/opendata.duckdb"
REPORT = Path("reports/drift.json")
FIGURE = Path("reports/drift.html")
CLASSES = list("ABCDEFG")
EP_LIMITS = [70, 110, 180, 250, 330, 420]   # primary energy, kWh/m²/yr: upper bound of A..F
GES_LIMITS = [6, 11, 30, 50, 70, 100]       # CO2, kg/m²/yr: upper bound of A..F
RECENT_DAYS = 180
PSI_WARN, PSI_ALERT = 0.1, 0.2


def class_index(ep: str, ges: str) -> str:
    """
    SQL expression to compute the energy label index (1..7) from primary energy and CO2.
    label index 1 (A) .. 7 (G) = worst of energy and CO2 thresholds (2021 method)
    Args:
        ep (str): SQL expression for primary energy.
        ges (str): SQL expression for CO2 emissions.
    Returns:
        str: SQL expression for the energy label index."""
   
    e = " + ".join(f"({ep} > {t})::INT" for t in EP_LIMITS)
    g = " + ".join(f"(coalesce({ges}, 0) > {t})::INT" for t in GES_LIMITS)
    return f"(1 + greatest({e}, {g}))"


def psi(ref: dict[int, float], cur: dict[int, float], eps: float = 1e-4) -> float:
    """Population Stability Index (PSI) between two distributions.
    Args:
        ref (dict[int, float]): Reference distribution.
        cur (dict[int, float]): Current distribution.
        eps (float): Small value to avoid division by zero.
    Returns:
        float: The PSI value."""
    return sum((cur.get(k, eps) - ref.get(k, eps)) * math.log(cur.get(k, eps) / ref.get(k, eps))
               for k in range(1, 8))


def status(score: float) -> str:
    """Determine the status based on the PSI score.
    Args:
        score (float): The PSI score.
    Returns:
        str: The status ("drift", "warning", or "stable")."""
    return "drift" if score > PSI_ALERT else "warning" if score > PSI_WARN else "stable"


def main() -> None:
    """Run the energy-label drift check and generate a report and figure."""
    new_coef = float(sys.argv[sys.argv.index("--coefficient") + 1]) if "--coefficient" in sys.argv else 1.7
    test_start = date.fromisoformat(params("split")["test_start"])

    con = duckdb.connect()
    con.execute(f"ATTACH '{DB}' AS src (READ_ONLY)")
    elec = [r[0] for r in con.execute(
        "SELECT id FROM src.dpe_enum_type_energie "
        "WHERE strip_accents(lower(lib)) LIKE 'electricite%'").fetchall()]
    elec_ids = ",".join(map(str, elec)) or "-1"
    log.info("electricity energy ids: %s", elec_ids)

    con.execute(f"""
        CREATE TEMP TABLE d AS
        SELECT date_dpe,
               energie_id IN ({elec_ids})                              AS elec,
               list_position({CLASSES}, coalesce(classe_dpe_pef19, classe_dpe)) AS cls_h,
               list_position({CLASSES}, classe_dpe)                    AS cls,
               CASE WHEN energie_id IN ({elec_ids}) AND ef_m2 IS NOT NULL
                    THEN {class_index(f'ef_m2 * {new_coef}', 'ges_m2')}
                    ELSE list_position({CLASSES}, classe_dpe) END      AS cls_sim
        FROM '{DPE}' WHERE classe_dpe IS NOT NULL
    """)
    row = con.execute("SELECT max(date_dpe) FROM d").fetchone()
    assert row is not None
    recent_from = row[0] - timedelta(days=RECENT_DAYS)
    ref_from = test_start - timedelta(days=365)

    def dist(col: str, where: str) -> dict[int, float]:
        """Compute the distribution of energy labels for a given column and condition.
        Args:
            col (str): The column name.
            where (str): The WHERE clause for the SQL query.
        Returns:
            dict[int, float]: The distribution of energy labels.
        """
        rows = con.execute(f"SELECT {col}, count(*) FROM d WHERE {where} GROUP BY 1").fetchall()
        total = sum(n for _, n in rows)
        return {int(k): n / total for k, n in rows if k is not None}

    ref = dist("cls_h", f"date_dpe >= DATE '{ref_from}' AND date_dpe < DATE '{test_start}'")
    recent = f"date_dpe > DATE '{recent_from}'"
    checks = {
        "recent_real": dist("cls", recent),
        f"recent_simulated_coef_{new_coef}": dist("cls_sim", recent),
    }

    report = {"reference_period": [str(ref_from), str(test_start)],
              "recent_period_from": str(recent_from), "simulated_coefficient": new_coef,
              "reference": {CLASSES[k - 1]: round(v, 4) for k, v in sorted(ref.items())},
              "checks": []}
    for name, cur in checks.items():
        score = psi(ref, cur)
        report["checks"].append({"name": name, "psi": round(score, 4), "status": status(score),
                                 "distribution": {CLASSES[k - 1]: round(v, 4)
                                                  for k, v in sorted(cur.items())}})
        log_metric(log, "drift_check", check=name, psi=round(score, 4), status=status(score))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    fig = go.Figure([go.Bar(name="Reference (training period, harmonised)", x=CLASSES,
                            y=[ref.get(i + 1, 0) for i in range(7)], marker_color="#a1a99d")])
    for c, color in zip(report["checks"], ["#586259", "#2438d8"]):
        fig.add_bar(name=f"{c['name']} · PSI {c['psi']} ({c['status']})", x=CLASSES,
                    y=[c["distribution"].get(k, 0) for k in CLASSES], marker_color=color)
    fig.update_layout(barmode="group", title="Energy-label distribution: reference vs recent DPEs",
                      yaxis_tickformat=".0%", xaxis_title="Energy label", yaxis_title="Share of DPEs")
    fig.write_html(FIGURE)
    log.info("saved %s and %s", REPORT, FIGURE)


if __name__ == "__main__":
    main()