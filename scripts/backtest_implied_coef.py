"""Backtest the implied-coefficient detector on the real 2.3 -> 1.9 change (1 Jan 2026).

ADEME restated older ratings at 1.9 in the main columns; the values as issued
are kept in ancienne_* columns. One-off analysis: not part of the DVC pipeline.
"""
from pathlib import Path

import duckdb

from property_price.params import params

DB = "data/raw/dpe/opendata.duckdb"            # same file drift.py attaches
SIDE = Path("data/interim/dpe_pef23.parquet")
ids = ", ".join(str(i) for i in params("dpe_rules")["electric_energy_ids"])

con = duckdb.connect()

if not SIDE.exists():
    con.execute(f"ATTACH '{DB}' AS src (READ_ONLY)")
    con.execute(f"""COPY (
        SELECT dpe_id,
               ancienne_ep_conso_5_usages_m2_pef AS ep_m2_pef23,
               ancienne_classe_bilan_dpe_pef     AS classe_dpe_pef23
        FROM src.dpe_ep_conso
    ) TO '{SIDE.as_posix()}' (FORMAT parquet)""")

query = f"""
    SELECT date_trunc('month', f.date_dpe)::DATE                   AS month,
           round(median(coalesce(s.ep_m2_pef23, f.ep_m2) / f.ef_m2), 3) AS coef_as_issued,
           round(median(f.ep_m2 / f.ef_m2), 3)                      AS coef_published,
           round(avg((s.ep_m2_pef23 IS NOT NULL)::INT), 3)          AS share_with_old,
           round(avg((coalesce(s.classe_dpe_pef23, f.classe_dpe) = f.classe_dpe)::INT), 3) AS share_same_label,
           count(*)                                                  AS n
    FROM 'data/interim/dpe_flat/*.parquet' f
    LEFT JOIN '{SIDE.as_posix()}' s USING (dpe_id)
    WHERE f.energie_id IN ({ids}) AND f.ef_m2 > 0
      AND f.date_dpe BETWEEN DATE '2025-07-01' AND DATE '2026-06-30'
    GROUP BY 1 ORDER BY 1
"""
print(f"{'month':<12}{'as_issued':>10}{'published':>10}{'with_old':>10}{'same_lbl':>10}{'n':>9}")
for m, a, p, w, sl, n in con.execute(query).fetchall():
    print(f"{m!s:<12}{a!s:>10}{p!s:>10}{w!s:>10}{sl!s:>10}{n:>9}")

con.execute(f"COPY ({query}) TO 'reports/backtest_implied_coef.csv' (HEADER)")