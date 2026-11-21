from pathlib import Path
import duckdb

DB = Path("data/raw/dpe/opendata.duckdb")
DB.parent.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(DB))
# "audit" is the energy-audit base: we only need "dpe"
con.execute(
    "ATTACH 'https://s3.fr-par.scw.cloud/prod-dpe-opendata/dpe/dpe.duckdb' "
    "AS src_dpe (READ_ONLY)"
)
con.execute("COPY FROM DATABASE src_dpe TO opendata")
con.execute("DETACH DATABASE IF EXISTS src_dpe")

# What did we get? Every table/view, plus its row count
objects = con.execute("""
    SELECT table_name, table_type
    FROM information_schema.tables
    WHERE table_schema = 'main'
    ORDER BY table_name
""").fetchall()
for name, kind in objects:
    print(f"{kind:10} {name}")

# Columns of the tables we will need for the join
for t in [n for n, _ in objects if "adresse" in n or n.endswith("_dpe") or "logement" in n]:
    cols = con.execute(f"DESCRIBE {t}").fetchall()
    print(f"\n== {t} ==")
    for c in cols:
        print(f"  {c[0]:45} {c[1]}")