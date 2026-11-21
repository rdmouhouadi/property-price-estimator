import time
import duckdb

con = duckdb.connect("data/raw/dpe/opendata.duckdb", read_only=True)

TABLES = [
    "dpe", "dpe_administratif", "dpe_caracteristique_generale",
    "dpe_ep_conso", "dpe_emission_ges", "dpe_ef_conso",
    "dpe_geolocalisation", "dpe_installation_chauffage", "dpe_generateur_chauffage",
    "dpe_enum_periode_construction", "dpe_enum_type_energie",
    "dpe_enum_classe_etiquette", "dpe_enum_methode_application_dpe_log",
    "dpe_enum_version",
]

for t in TABLES:
    print(f"\n== {t} ==")
    for c in con.execute(f"DESCRIBE {t}").fetchall():
        print(f"  {c[0]:45} {c[1]}")

# The enum tables are small: print their contents too
for t in ["dpe_enum_classe_etiquette", "dpe_enum_methode_application_dpe_log",
          "dpe_enum_periode_construction", "dpe_enum_version"]:
    print(f"\n-- {t} values --")
    for row in con.execute(f"SELECT * FROM {t} LIMIT 40").fetchall():
        print("  ", row[:3])

# Size check (also tells us how fast remote queries are)
for t in ["dpe", "dpe_t_adresse"]:
    t0 = time.time()
    row_count = con.execute(f"SELECT count(*) FROM {t}").fetchone()
    assert row_count is not None # count(*) always returns a row, even if the table is empty
    row = row_count[0]
    print(f"\n{t}: {row:,} rows in {time.time() - t0:.1f}s")