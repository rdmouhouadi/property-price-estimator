"""Energy-label drift checks for the DPE rule changes.

Reference : harmonised labels (coefficient from params.yaml, 1.9) of DPEs dated in the
            12 months before the test period.
Checks    :
  - all_*                 PSI on all DPEs            (shows the dilution: population-level is blind)
  - electric_*            PSI on electric-heated DPEs (the segment the coefficient affects)
  - implied_coefficient_* median(primary / final energy) for electric-heated DPEs
                          (the coefficient itself: jumps on day one of a rule change)
  Each is computed on real recent DPEs (should be stable) and on the same DPEs simulated
  under --coefficient (default 1.7, the 2027 rule; drift expected).

Simulation (approximate, stated in the docs): for electric-heated homes, harmonised primary
energy is scaled by new/current coefficient, then the 2021 thresholds are re-applied
(worst of energy and CO2). Small-surface rules are ignored.

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
from property_price.dpe_rules import CLASSES, class_index, EP_LIMITS, GES_LIMITS

log = get_logger(__name__)
DPE = "data/interim/dpe_flat/*.parquet"
DB = "data/raw/dpe/opendata.duckdb"
REPORT = Path("reports/drift.json")
FIGURE = Path("reports/drift.html")
#CLASSES = list("ABCDEFG")
#EP_LIMITS = [70, 110, 180, 250, 330, 420]   # primary energy, kWh/m²/yr: upper bound of A..F
#GES_LIMITS = [6, 11, 30, 50, 70, 100]       # CO2, kg/m²/yr: upper bound of A..F
RECENT_DAYS = 180
PSI_WARN, PSI_ALERT = 0.1, 0.2
COEF_ALERT = 0.03                           # >3% relative change in the implied coefficient


def psi(ref: dict[int, float], cur: dict[int, float], eps: float = 1e-4) -> float:
    """Population Stability Index (PSI) = sum((cur - ref) * log(cur / ref)).
    Args:
        ref: Reference label distribution.
        cur: Current label distribution.
        eps: Small value to avoid division by zero.
    Returns:
        The PSI value.
    """
    return sum((cur.get(k, eps) - ref.get(k, eps)) * math.log(cur.get(k, eps) / ref.get(k, eps))
               for k in range(1, 8))


def status(score: float) -> str:
    """
    Determine the status based on the PSI value.
    PSI = Σ (current% - reference%) x ln(current% / reference%)
    PSI < 0.1 stable, 0.1-0.2 warning, > 0.2 drift.
    """
    return "drift" if score > PSI_ALERT else "warning" if score > PSI_WARN else "stable"


def main() -> None:
    """Run all drift checks, write reports/drift.json and reports/drift.html."""
    new_coef = float(sys.argv[sys.argv.index("--coefficient") + 1]) if "--coefficient" in sys.argv else 1.7
    cur_coef = params("dpe_rules")["elec_coefficient"]
    test_start = date.fromisoformat(params("split")["test_start"])

    con = duckdb.connect()
    con.execute(f"ATTACH '{DB}' AS src (READ_ONLY)")
    elec = [r[0] for r in con.execute(
        "SELECT id FROM src.dpe_enum_type_energie "
        "WHERE strip_accents(lower(lib)) LIKE 'electricite%'").fetchall()]
    elec_ids = ",".join(map(str, elec)) or "-1"
    log.info("electricity energy ids: %s", elec_ids)

    ep_h = "coalesce(ep_m2_pef19, ep_m2)"                 # harmonised primary energy
    ep_sim = f"{ep_h} * {new_coef} / {cur_coef}"          # same home under the new rule
    con.execute(f"""
        CREATE TEMP TABLE d AS
        SELECT date_dpe,
               energie_id IN ({elec_ids})                                        AS elec,
               ef_m2, ep_m2, {ep_h} AS ep_h,
               list_position({CLASSES}, coalesce(classe_dpe_pef19, classe_dpe))  AS cls_h,
               list_position({CLASSES}, classe_dpe)                              AS cls,
               CASE WHEN energie_id IN ({elec_ids}) AND {ep_h} IS NOT NULL
                    THEN {class_index(ep_sim, 'ges_m2')}
                    ELSE list_position({CLASSES}, classe_dpe) END                AS cls_sim,
               CASE WHEN energie_id IN ({elec_ids}) THEN {ep_sim} ELSE ep_m2 END AS ep_sim
        FROM '{DPE}' WHERE classe_dpe IS NOT NULL
    """)

    # periods: reference = 12 months before the test period; recent = last RECENT_DAYS of data
    row = con.execute("SELECT max(date_dpe) FROM d").fetchone()
    assert row is not None
    recent_from = row[0] - timedelta(days=RECENT_DAYS)
    ref_from = test_start - timedelta(days=365)
    ref_where = f"date_dpe >= DATE '{ref_from}' AND date_dpe < DATE '{test_start}'"
    recent = f"date_dpe > DATE '{recent_from}'"

    def dist(col: str, where: str) -> dict[int, float]:
        """
        Calculate the distribution of labels in a column for rows matching a condition.
        Args:
            col: The column name to calculate the distribution for.
            where: The condition to filter rows.
        Returns:
            A dictionary mapping label values to their proportions.
        """
        rows = con.execute(f"SELECT {col}, count(*) FROM d WHERE {where} GROUP BY 1").fetchall()
        total = sum(n for _, n in rows)
        return {int(k): n / total for k, n in rows if k is not None}

    def implied(ep_col: str, where: str) -> float:
        """
        Calculate the implied coefficient based on the median primary/final energy ratio
        for electric-heated DPEs in a given period."""
    
        r = con.execute(f"SELECT median({ep_col} / ef_m2) FROM d "
                        f"WHERE elec AND ef_m2 > 0 AND {where}").fetchone()
        assert r is not None
        return float(r[0])

    # --- PSI checks ---
    ref = dist("cls_h", ref_where)
    ref_elec = dist("cls_h", f"{ref_where} AND elec")
    checks = {   # name: (reference, current)
        "all_real": (ref, dist("cls", recent)),
        f"all_simulated_{new_coef}": (ref, dist("cls_sim", recent)),
        "electric_real": (ref_elec, dist("cls", f"{recent} AND elec")),
        f"electric_simulated_{new_coef}": (ref_elec, dist("cls_sim", f"{recent} AND elec")),
    }

    report: dict = {
        "reference_period": [str(ref_from), str(test_start)],
        "recent_period_from": str(recent_from),
        "current_coefficient": cur_coef,
        "simulated_coefficient": new_coef,
        "reference": {CLASSES[k - 1]: round(v, 4) for k, v in sorted(ref.items())},
        "reference_electric": {CLASSES[k - 1]: round(v, 4) for k, v in sorted(ref_elec.items())},
        "checks": [],
    }
    for name, (base, cur) in checks.items():
        score = psi(base, cur)
        report["checks"].append({"name": name, "psi": round(score, 4), "status": status(score),
                                 "distribution": {CLASSES[k - 1]: round(v, 4)
                                                  for k, v in sorted(cur.items())}})
        log_metric(log, "drift_check", check=name, psi=round(score, 4), status=status(score))

    # --- implied-coefficient checks ---
    coef_ref = implied("ep_h", ref_where)
    report["implied_coefficient"] = {
        "reference": round(coef_ref, 3),
        "recent_real": round(implied("ep_m2", recent), 3),
        f"recent_simulated_{new_coef}": round(implied("ep_sim", recent), 3),
    }
    for name, value in list(report["implied_coefficient"].items())[1:]:
        change = abs(value / coef_ref - 1)
        st = "drift" if change > COEF_ALERT else "stable"
        report["checks"].append({"name": f"implied_coefficient_{name}", "value": value,
                                 "relative_change": round(change, 4), "status": st})
        log_metric(log, "drift_check", check=f"implied_coefficient_{name}",
                   value=value, relative_change=round(change, 4), status=st)

    report["drift_detected"] = any(c["status"] == "drift" for c in report["checks"])

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # --- figure: electric-heated segment ---
    elec_checks = [c for c in report["checks"] if c["name"].startswith("electric")]
    fig = go.Figure([go.Bar(name="Reference, electric-heated (harmonised)", x=CLASSES,
                            y=[ref_elec.get(i + 1, 0) for i in range(7)], marker_color="#a1a99d")])
    for c, color in zip(elec_checks, ["#586259", "#2438d8"]):
        fig.add_bar(name=f"{c['name']} · PSI {c['psi']} ({c['status']})", x=CLASSES,
                    y=[c["distribution"].get(k, 0) for k in CLASSES], marker_color=color)
    ic = report["implied_coefficient"]
    fig.update_layout(
        barmode="group",
        title=(f"Electric-heated homes: label shift under coefficient {new_coef}<br>"
               f"<sub>Implied coefficient: reference {ic['reference']} · recent {ic['recent_real']}"
               f" · simulated {ic[f'recent_simulated_{new_coef}']}</sub>"),
        yaxis_tickformat=".0%", xaxis_title="Energy label", yaxis_title="Share of DPEs",
    )
    fig.write_html(FIGURE)
    log.info("drift detected: %s · saved %s and %s", report["drift_detected"], REPORT, FIGURE)


if __name__ == "__main__":
    main()