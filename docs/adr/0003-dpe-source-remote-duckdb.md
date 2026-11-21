# ADR-0003: DPE source, ADEME's remote DuckDB instead of a CSV export or the SQL dump

- **Status:** accepted
- **Date:** 2026-11-21

## Context

The DPE dataset page offers several access methods, and none is a simple full CSV:

- the data.ademe.fr table viewer: filter and export, meant for small extracts;
- an API: paginated, slow for about 20M rows;
- a full PostgreSQL dump of about 70 GB, updated weekly;
- **SQL access via DuckDB**: a `dpe.duckdb` file on ADEME's object storage, which can be attached and queried directly.

## Decision

Use the **remote DuckDB** access:

```sql
ATTACH 'https://s3.fr-par.scw.cloud/prod-dpe-opendata/dpe/dpe.duckdb' AS src_dpe (READ_ONLY);
COPY FROM DATABASE src_dpe TO opendata;   -- local catalogue of views over the remote data
DETACH DATABASE src_dpe;
```

Then pull only the needed columns of each table into local Parquet (stage A), and join locally (stage B).

## Why

- **Column pruning at the source:** we read about 25 columns out of hundreds, instead of downloading everything.
- **Same stack as the rest of the project** (DuckDB SQL), with no PostgreSQL server to run.
- **Fast:** counting 20M rows took under a second, and the full stage A took about 1m45.
- **Fresh:** ADEME updates it weekly. That is the hook for part 2's drift monitoring.

## Consequences

- The model is **relational**: `dpe` → `dpe_administratif`, `dpe_caracteristique_generale`, `dpe_ep_conso`, `dpe_emission_ges`, `dpe_ef_conso`, `dpe_geolocalisation` → `dpe_t_adresse`. The links were confirmed by inspection; the schema dump is in `reports/dpe_schema.txt`. `dpe_geolocalisation.administratif_id = dpe.id` was checked on a 100k sample (88% linked; the rest are DPEs filtered out).
- Remote queries need internet access. That's why stage A materializes locally.
- A single 8-table remote join ran out of memory, so the extraction is split into two stages ([troubleshooting #10](../troubleshooting.md)).
- **Property type** comes from `enum_methode_application_dpe_log_id`:
  - `1`: house;
  - `2–5, 31, 32, 35–37`: apartment;
  - `10–13, 33, 34, 38–40`: apartment generated from a building DPE (flagged);
  - whole buildings (`6–9, 26–30`) and new builds (`14–25`) are excluded.
- **Bonus:** ADEME publishes old and new electricity-coefficient values (`ancienne_*_pef`, `nouvelle_*_pef`), which is used for harmonisation ([ADR-0005](0005-dpe-coefficient-drift.md)).

## References

- ADEME, *DPE Logements existants (depuis juillet 2021)*: https://www.data.gouv.fr/datasets/dpe-logements-existants-depuis-juillet-2021/
- DuckDB, `ATTACH` and remote databases: https://duckdb.org/docs/sql/statements/attach
