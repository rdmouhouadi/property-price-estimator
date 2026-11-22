"""Latest 12-month market prices per section / commune / département x type, for serving."""
from pathlib import Path

import duckdb

from property_price.logging_config import get_logger, log_metric
from property_price.params import params

log = get_logger(__name__)
SRC = "data/processed/sales_enriched.parquet"
OUT = Path("data/processed/market_snapshot.parquet")
W = params("features")["window_days"]


def main() -> None:
    """
    Build market_snapshot.parquet from sales_enriched.parquet.
    This function computes the latest 12-month market prices for each section, commune, and département,
    grouped by property type. The results are saved to a Parquet file.
    """
    OUT.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"""
    COPY (
      WITH s AS (SELECT *, ln(prix_m2) AS y, left(id_parcelle, 10) AS section FROM '{SRC}'),
      ref AS (SELECT max(date) AS d FROM s),
      recent AS (SELECT s.* FROM s, ref WHERE s.date > ref.d - INTERVAL {W} DAYS)
      SELECT 'dept' AS level, code_departement AS key, type_bien, avg(y) AS m, count(*) AS n
        FROM recent GROUP BY ALL
      UNION ALL
      SELECT 'commune', code_commune, type_bien, avg(y), count(*) FROM recent GROUP BY ALL
      UNION ALL
      SELECT 'section', section, type_bien, avg(y), count(*) FROM recent
        WHERE section IS NOT NULL GROUP BY ALL
    ) TO '{OUT.as_posix()}' (FORMAT parquet)
    """)
    row = con.execute(f"SELECT count(*), max(n) FROM '{OUT.as_posix()}'").fetchone()
    assert row is not None
    log_metric(log, "market_snapshot", rows=row[0])


if __name__ == "__main__":
    main()