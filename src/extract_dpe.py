"""Flatten the ADEME DPE base into Parquet.
Stage A: pull needed columns of each remote table to local Parquet (streaming, low RAM).
Stage B: join locally in N hash buckets of dpe_id (bounded RAM)."""

import sys
import time
from pathlib import Path
import duckdb

DB = "data/raw/dpe/opendata.duckdb"
PARTS = Path("data/interim/dpe_parts")
OUT = Path("data/interim/dpe_flat")
N_BUCKETS = 8

MAISON = (1,)
APPART = (2, 3, 4, 5, 31, 32, 35, 36, 37)
APPART_GENERE = (10, 11, 12, 13, 33, 34, 38, 39, 40)
KEEP = MAISON + APPART + APPART_GENERE

# table -> SELECT body (columns + optional filter)
EXTRACTS = {
    "dpe": """SELECT id AS dpe_id, identifiant_dpe,
                     enum_type_energie_chauffage_principal_id AS energie_id
              FROM dpe
              WHERE coalesce(is_dpe_2012, false) = false
                AND coalesce(desactive, false) = false
                AND dpe_remplacant_id IS NULL""",
    "administratif": """SELECT dpe_id, date_etablissement_dpe::DATE AS date_dpe,
                               enum_version_id AS dpe_version
                        FROM dpe_administratif
                        WHERE date_etablissement_dpe >= DATE '2021-07-01'""",
    "carac": f"""SELECT dpe_id, enum_methode_application_dpe_log_id AS methode_id,
                        surface_habitable_logement AS surface_hab, annee_construction,
                        enum_periode_construction_id AS periode_id,
                        nombre_niveau_logement AS nb_niveaux
                 FROM dpe_caracteristique_generale
                 WHERE enum_methode_application_dpe_log_id IN {KEEP}""",
    "ep": """SELECT dpe_id, classe_bilan_dpe AS classe_dpe, ep_conso_5_usages_m2 AS ep_m2,
                    nouvelle_classe_bilan_dpe_pef AS classe_dpe_pef19,
                    nouvelle_ep_conso_5_usages_m2_pef AS ep_m2_pef19
             FROM dpe_ep_conso""",
    "ges": """SELECT dpe_id, classe_emission_ges AS classe_ges,
                     emission_ges_5_usages_m2 AS ges_m2
              FROM dpe_emission_ges""",
    "ef": "SELECT dpe_id, conso_5_usages_m2 AS ef_m2 FROM dpe_ef_conso",
    "geoloc": """SELECT administratif_id, adresse_bien_id, id_batiment_rnb
                 FROM dpe_geolocalisation""",
    "adresse": """SELECT id AS adresse_id, compl_etage_appartement AS etage,
                         ban_id, ban_housenumber, ban_street, ban_citycode, ban_postcode,
                         ban_departement, ban_score, ban_x, ban_y
                  FROM dpe_t_adresse""",
}


def connect(db: str | None = None) -> duckdb.DuckDBPyConnection:
    """
    Connect to the given DuckDB database (or in-memory if None).
    Sets some pragmas for performance and resource limits.
    """
    con = duckdb.connect(db or ":memory:", read_only=db is not None)
    con.execute("SET memory_limit = '5GB'")
    con.execute("SET threads = 4")
    con.execute("SET preserve_insertion_order = false")
    con.execute("SET temp_directory = 'data/tmp'")
    return con


def show(con: duckdb.DuckDBPyConnection, sql: str, max_rows: int = 40) -> None:
    """
    Execute the given SQL query and print the results in a tabular format.
    The number of rows displayed can be limited with the max_rows parameter.
    """
    rel = con.sql(sql)
    assert rel is not None
    rel.show(max_rows=max_rows)


def stage_a() -> None:
    """
    Stage A: extract needed columns from each remote table and save to local Parquet files.
    Creates the PARTS directory if it does not exist. 
    For each table in EXTRACTS, it checks if the corresponding Parquet file already exists;
    if not, it executes the SELECT query and saves the result to a temporary Parquet file, which is then renamed to the final target file. 
    The function also prints the time taken for each extraction.
    """
    PARTS.mkdir(parents=True, exist_ok=True)
    con = connect(DB)
    for name, select in EXTRACTS.items():
        target = PARTS / f"{name}.parquet"
        if target.exists():
            print(f"skip {target}")
            continue
        t0 = time.time()
        tmp = target.with_suffix(".parquet.part")
        con.execute(f"COPY ({select}) TO '{tmp.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
        tmp.rename(target)
        print(f"{name:14} {time.time() - t0:6.0f}s")


def stage_b() -> None:
    """
    Stage B: join the extracted Parquet files into N_BUCKETS of flattened Parquet files.
    Creates the OUT directory if it does not exist.
    For each bucket, it checks if the corresponding Parquet file already exists; 
    if not, it performs a series of joins on the extracted Parquet files based on dpe_id and other relevant keys, 
    filtering rows into the current bucket using a hash function.
    The resulting joined data is saved to a temporary Parquet file, which is then renamed to the final target file.
    After processing all buckets, it performs a summary query to count the total rows, distinct dpe_ids, 
    and the percentage of rows without address or class information, and prints the results.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    con = connect()
    p = {n: f"'{(PARTS / f'{n}.parquet').as_posix()}'" for n in EXTRACTS}

    # sanity check of the one assumed link: geoloc.administratif_id -> dpe.id
    show(con, f"""
        SELECT count(*) AS geoloc_rows,
               count(*) FILTER (WHERE administratif_id IN (SELECT dpe_id FROM {p['dpe']})) AS linked_to_dpe
        FROM (SELECT administratif_id FROM {p['geoloc']} LIMIT 100000)
    """)

    for k in range(N_BUCKETS):
        target = OUT / f"part_{k}.parquet"
        if target.exists():
            print(f"skip {target}")
            continue
        t0 = time.time()
        b = f"hash({{col}}) % {N_BUCKETS} = {k}"
        con.execute(f"""
        COPY (
            SELECT d.dpe_id, d.identifiant_dpe, a.date_dpe, a.dpe_version,
                   CASE WHEN c.methode_id IN {MAISON} THEN 'Maison' ELSE 'Appartement' END AS type_bien,
                   c.methode_id IN {APPART_GENERE} AS dpe_genere_immeuble,
                   c.surface_hab, c.annee_construction, c.nb_niveaux, c.periode_id,
                   ep.classe_dpe, ep.ep_m2, ep.classe_dpe_pef19, ep.ep_m2_pef19,
                   ges.classe_ges, ges.ges_m2, ef.ef_m2, d.energie_id,
                   g.id_batiment_rnb,
                   ad.etage, ad.ban_id, ad.ban_housenumber, ad.ban_street, ad.ban_citycode,
                   ad.ban_postcode, ad.ban_departement, ad.ban_score, ad.ban_x, ad.ban_y
            FROM (SELECT * FROM {p['dpe']} WHERE {b.format(col='dpe_id')}) d
            JOIN (SELECT * FROM {p['administratif']} WHERE {b.format(col='dpe_id')}) a USING (dpe_id)
            JOIN (SELECT * FROM {p['carac']} WHERE {b.format(col='dpe_id')}) c USING (dpe_id)
            LEFT JOIN (SELECT * FROM {p['ep']}  WHERE {b.format(col='dpe_id')}) ep USING (dpe_id)
            LEFT JOIN (SELECT * FROM {p['ges']} WHERE {b.format(col='dpe_id')}) ges USING (dpe_id)
            LEFT JOIN (SELECT * FROM {p['ef']}  WHERE {b.format(col='dpe_id')}) ef USING (dpe_id)
            LEFT JOIN (SELECT * FROM {p['geoloc']} WHERE {b.format(col='administratif_id')}) g
                   ON g.administratif_id = d.dpe_id
            LEFT JOIN {p['adresse']} ad ON ad.adresse_id = g.adresse_bien_id
        ) TO '{target.as_posix()}' (FORMAT parquet, COMPRESSION zstd)
        """)
        print(f"bucket {k}  {time.time() - t0:6.0f}s")

    show(con, f"""
        SELECT count(*) AS rows, count(DISTINCT dpe_id) AS distinct_dpe,
               round(100 * avg((ban_citycode IS NULL)::INT), 1) AS pct_no_address,
               round(100 * avg((classe_dpe IS NULL)::INT), 1)   AS pct_no_class
        FROM '{OUT.as_posix()}/*.parquet'
    """)
    show(con, f"SELECT type_bien, classe_dpe, count(*) n FROM '{OUT.as_posix()}/*.parquet' "
              "GROUP BY ALL ORDER BY ALL")


if __name__ == "__main__":
    Path("data/tmp").mkdir(parents=True, exist_ok=True)
    if "a" in sys.argv[1:]:
        stage_a()
    if "b" in sys.argv[1:]:
        stage_b()