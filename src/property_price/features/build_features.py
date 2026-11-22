"""sales_enriched -> features.parquet (leak-free local market features, time split)."""
from pathlib import Path

import duckdb

from property_price.dpe_rules import harmonised_sql
from property_price.params import params

SRC = "data/processed/sales_enriched.parquet"
OUT = Path("data/processed/features.parquet")
K_SHRINK = params("features")["k_shrink"]  # pseudo-count for shrinkage of local market features
WINDOW_DAYS = params("features")["window_days"]  # number of days for the moving average window
_s = params("split") # number of months for the time-based split
_r = params("dpe_rules") # DPE harmonisation parameters
DPE_CLASS_SQL, DPE_EP_SQL = harmonised_sql(_r["elec_coefficient"], _r["electric_energy_ids"])


def window(part: str) -> str:
    """
    Previous 365 days (excluding the sale day) within a partition, same property type.
    """
    return (f"OVER (PARTITION BY {part}, type_bien ORDER BY date "
            "RANGE BETWEEN INTERVAL 365 DAYS PRECEDING AND INTERVAL 1 DAY PRECEDING)")


def shrink(child: str, n: str, parent: str) -> str:
    """
    Shrink a child-level average toward the parent-level average, using a pseudo-count.
    """
    return f"coalesce(({n} * {child} + {K_SHRINK} * {parent}) / ({n} + {K_SHRINK}), {parent})"


def main() -> None:
    """
    Build features.parquet from sales_enriched.parquet.
    """
    OUT.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit = '5GB'")
    con.execute("SET threads = 4")
    con.execute("SET temp_directory = 'data/tmp'")

    con.execute(f"""
    COPY (
      WITH s AS (
        SELECT *, ln(prix_m2) AS y, left(id_parcelle, 10) AS section
        FROM '{SRC}'
      ),
      w AS (
        SELECT *,
          avg(y)   {window('code_departement')} AS dept_m,
          count(*) {window('code_departement')} AS dept_n,
          avg(y)   {window('code_commune')}     AS com_m,
          count(*) {window('code_commune')}     AS com_n,
          avg(y)   {window('section')}          AS sec_m,
          count(*) {window('section')}          AS sec_n
        FROM s
      ),
      sm AS (
        SELECT *,
          {shrink('com_m', 'com_n', 'dept_m')} AS com_sm
        FROM w
      )
      SELECT
        id_mutation, date, y, valeur, prix_m2,
        -- property
        type_bien, surface_bati, pieces, surface_terrain, n_dependances,
        -- location
        code_departement, code_commune, lat, lon,
        -- local market (leak-free, shrunk)
        dept_m AS mkt_dept_12m, com_sm AS mkt_commune_12m,
        {shrink('sec_m', 'sec_n', 'com_sm')} AS mkt_section_12m,
        com_n AS mkt_commune_n, sec_n AS mkt_section_n,
        -- time
        date_diff('month', DATE '2021-01-01', date) AS t_months,
        month(date) AS month,
        -- DPE (null when no match)
        has_dpe,
        {DPE_CLASS_SQL} AS dpe_class, 
        list_position(['A','B','C','D','E','F','G'], classe_ges) AS ges_class,
        {DPE_EP_SQL} AS dpe_ep_m2,
        periode_id AS dpe_periode, annee_construction, energie_id AS dpe_energie,
        etage, nb_niveaux, dpe_genere_immeuble, dpe_version,
        -- split
        CASE WHEN date < DATE '2024-07-01' THEN 'train'
             WHEN date < DATE '2025-01-01' THEN 'valid'
             ELSE 'test' END AS split
      FROM sm
    ) TO '{OUT.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
    """)
    print(f"written {OUT}")

    def show(sql: str) -> None:
        """
        Show a SQL query result.
        """
        rel = con.sql(sql)
        assert rel is not None
        rel.show(max_rows=40)

    f = f"'{OUT.as_posix()}'"
    show(f"""SELECT split, count(*) AS n, round(100*avg(has_dpe::INT),1) AS pct_dpe,
                    min(date) AS from_, max(date) AS to_
             FROM {f} GROUP BY split ORDER BY from_""")
    show(f"""SELECT round(100*avg((mkt_section_12m IS NULL)::INT),1) AS pct_null_mkt,
                    round(corr(y, mkt_section_12m), 3) AS r_section,
                    round(corr(y, mkt_commune_12m), 3) AS r_commune,
                    round(corr(y, mkt_dept_12m), 3)    AS r_dept
             FROM {f} WHERE split = 'train'""")


if __name__ == "__main__":
    main()