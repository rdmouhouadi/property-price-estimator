"""DVF sales x DPE matching (address + type + surface + date, unique both ways).
Step 1: candidate pairs per commune-hash bucket -> data/interim/match_candidates/
Step 2: apply rules, keep unique matches, write enriched sales + lineage."""

from pathlib import Path
import duckdb
from property_price.params import params

DVF = "data/interim/dvf_sales.parquet"
DPE = "data/interim/dpe_flat/*.parquet"
CAND = Path("data/interim/match_candidates")
OUT = Path("data/processed/sales_enriched.parquet")
N_BUCKETS = 8

# matching rules (keep as params: we'll test variants)
_m = params("match")
SURF_TOL = _m["surf_tol"]
DAYS_BEFORE = _m["days_before"]
DAYS_AFTER = _m["days_after"]
MIN_BAN_SCORE = _m["min_ban_score"]

ABBR = [("AV", "AVENUE"), ("BD", "BOULEVARD"), ("BLD", "BOULEVARD"), ("CHE", "CHEMIN"),
        ("CHEM", "CHEMIN"), ("IMP", "IMPASSE"), ("ALL", "ALLEE"), ("PL", "PLACE"),
        ("RTE", "ROUTE"), ("CRS", "COURS"), ("SQ", "SQUARE"), ("QUA", "QUAI"),
        ("PAS", "PASSAGE"), ("LOT", "LOTISSEMENT"), ("RES", "RESIDENCE"), ("FG", "FAUBOURG"),
        ("ST", "SAINT"), ("STE", "SAINTE"), ("PRO", "PROMENADE"), ("HAM", "HAMEAU")]


def street(col: str) -> str:
    """
    Normalize street names for matching by:
    - stripping accents and converting to uppercase
    - replacing non-alphanumeric characters with spaces
    - expanding common abbreviations (e.g., "AV" to "AVENUE")
    This function returns a SQL expression that can be used in a DuckDB query to normalize street names in the specified column.
    """
    e = f"upper(strip_accents(coalesce({col}, '')))"
    e = f"trim(regexp_replace({e}, '[^A-Z0-9]+', ' ', 'g'))"
    for a, full in ABBR:
        e = f"regexp_replace({e}, '\\b{a}\\b', '{full}', 'g')"
    return e


def number(col: str) -> str:
    """
    Extract the numeric part of an address number for matching.
    This function returns a SQL expression that can be used in a DuckDB query to extract the leading numeric part of an address number from the specified column. 
    It uses a regular expression to find the first sequence of digits, ignoring any leading whitespace.
    """
    return f"TRY_CAST(regexp_extract({col}, '^\\s*(\\d+)', 1) AS INTEGER)"


def connect() -> duckdb.DuckDBPyConnection:
    """
    Establish a DuckDB connection with specific settings for memory limit, number of threads, insertion order, and temporary directory.
    This function creates and returns a DuckDB connection object configured with the following settings:
    - Memory limit: 5GB
    - Number of threads: 4
    - Preserve insertion order: false
    - Temporary directory: 'data/tmp'
    These settings are intended to optimize performance for the matching process between DVF sales and DPE data.
    """
    con = duckdb.connect()
    con.execute("SET memory_limit = '5GB'")
    con.execute("SET threads = 4")
    con.execute("SET preserve_insertion_order = false")
    con.execute("SET temp_directory = 'data/tmp'")
    return con


def show(con: duckdb.DuckDBPyConnection, sql: str) -> None:
    """
    Execute a SQL query using the provided DuckDB connection and display the results.
    This function takes a DuckDB connection and a SQL query string as input, executes the query, and prints the results to the console.
    It is useful for debugging and inspecting the output of SQL queries during the matching process between DVF sales and DPE data.
    """
    rel = con.sql(sql)
    assert rel is not None
    rel.show(max_rows=60)


def candidates(con: duckdb.DuckDBPyConnection) -> None:
    """
    Generate candidate pairs of DVF sales and DPE records based on commune-hash buckets.
    This function creates candidate pairs of DVF sales and DPE records by partitioning the data into buckets based on a hash of the commune code.
    For each bucket, it selects relevant columns from both DVF and DPE datasets, applies filtering criteria, 
    and saves the resulting candidate pairs as Parquet files in the CAND directory.
    The candidate pairs are generated to facilitate the matching process between DVF sales and DPE records, 
    ensuring that only relevant pairs are considered for further analysis.
    """

    CAND.mkdir(parents=True, exist_ok=True)
    for k in range(N_BUCKETS):
        target = CAND / f"part_{k}.parquet"
        if target.exists():
            print(f"skip {target}")
            continue
        con.execute(f"""
        COPY (
            WITH s AS (
                SELECT id_mutation, date, type_bien, surface_bati, code_commune,
                       {number('adresse_numero')} AS num, {street('adresse_nom_voie')} AS street
                FROM '{DVF}' WHERE hash(code_commune) % {N_BUCKETS} = {k}
            ),
            d AS (
                SELECT dpe_id, date_dpe, type_bien, surface_hab, ban_citycode AS code_commune,
                       {number('ban_housenumber')} AS num, {street('ban_street')} AS street
                FROM '{DPE}'
                WHERE hash(ban_citycode) % {N_BUCKETS} = {k}
                  AND ban_score >= {MIN_BAN_SCORE} AND surface_hab > 0
            )
            SELECT s.id_mutation, d.dpe_id,
                   abs(d.surface_hab - s.surface_bati) / s.surface_bati AS dsurf,
                   date_diff('day', d.date_dpe, s.date) AS ddays   -- >0: DPE before sale
            FROM s JOIN d
              ON s.code_commune = d.code_commune AND s.num = d.num
             AND s.street = d.street AND s.type_bien = d.type_bien
            WHERE s.num IS NOT NULL AND s.street <> ''
        ) TO '{target.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
        """)
        print(f"bucket {k} done")


def match(con: duckdb.DuckDBPyConnection) -> None:
    """
    Match DVF sales with DPE records based on candidate pairs, applying filtering rules to ensure unique matches.
    This function processes the candidate pairs generated by the candidates function, 
    applying filtering rules to identify unique matches between DVF sales and DPE records.
    It creates a temporary table of filtered matches, ensuring that each DVF sale and DPE record is matched uniquely. 
    The resulting enriched sales data, including DPE information, is saved as a Parquet file in the OUT directory.
    The function also prints lineage counts for each filtering step, providing insight into how many rows remain after each filter is applied, 
    and displays summary statistics of the enriched sales data.
    """

    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = f"'{CAND.as_posix()}/*.parquet'"
    con.execute(f"""
        CREATE TEMP TABLE m AS
        WITH f AS (
            SELECT * FROM {c}
            WHERE dsurf <= {SURF_TOL} AND ddays BETWEEN -{DAYS_AFTER} AND {DAYS_BEFORE}
        )
        SELECT * FROM f
        QUALIFY count(*) OVER (PARTITION BY id_mutation) = 1
            AND count(*) OVER (PARTITION BY dpe_id) = 1
    """)

    print("Match lineage")
    show(con, f"""
        SELECT 'DVF sales' AS step, count(*) AS n FROM '{DVF}'
        UNION ALL SELECT '+ address & type candidate', count(DISTINCT id_mutation) FROM {c}
        UNION ALL SELECT '+ surface within tol', count(DISTINCT id_mutation) FROM {c}
              WHERE dsurf <= {SURF_TOL}
        UNION ALL SELECT '+ date window', count(DISTINCT id_mutation) FROM {c}
              WHERE dsurf <= {SURF_TOL} AND ddays BETWEEN -{DAYS_AFTER} AND {DAYS_BEFORE}
        UNION ALL SELECT '= unique both ways', count(*) FROM m
    """)

    con.execute(f"""
        COPY (
            SELECT s.*, m.dpe_id IS NOT NULL AS has_dpe, m.ddays AS dpe_age_days,
                   d.date_dpe, d.dpe_version, d.classe_dpe, d.classe_ges, d.ep_m2, d.ef_m2,
                   d.ges_m2, d.classe_dpe_pef19, d.ep_m2_pef19, d.energie_id,
                   d.annee_construction, d.periode_id, d.nb_niveaux, d.etage,
                   d.dpe_genere_immeuble, d.surface_hab AS surface_dpe
            FROM '{DVF}' s
            LEFT JOIN m USING (id_mutation)
            LEFT JOIN '{DPE}' d USING (dpe_id)
        ) TO '{OUT.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
    """)
    print(f"written {OUT}")
    show(con, f"""
        SELECT type_bien, year(date) AS year, count(*) AS sales,
               round(100 * avg(has_dpe::INT), 1) AS pct_with_dpe
        FROM '{OUT.as_posix()}' GROUP BY ALL ORDER BY ALL
    """)


if __name__ == "__main__":
    Path("data/tmp").mkdir(parents=True, exist_ok=True)
    con = connect()
    candidates(con)
    match(con)