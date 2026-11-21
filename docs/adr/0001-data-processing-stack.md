# ADR-0001: Data processing stack (Polars + DuckDB + Parquet, pandas only at the model boundary)

- **Status:** accepted
- **Date:** 2026-11-21

## Context

- DPE base: about 20M rows across 170+ relational tables, read remotely. We need about 25 columns.
- DVF: about 3.5M rows per year, several rows per sale, five years.
- The core operation is a large relational join (DVF × DPE on address, with surface and date windows).
- Hardware: one Windows laptop, no cluster, memory capped at about 5 GB for processing.

## Decision

| Layer | Tool | Role |
|---|---|---|
| Large joins, windows, CSV ingestion | **DuckDB** | in-process analytical SQL, spills to disk |
| Cleaning and transformation code | **Polars** | lazy, multi-threaded DataFrames |
| Storage between steps | **Parquet** (via pyarrow) | typed, columnar, compressed |
| Model input | **pandas** | only after aggregation, where scikit-learn / LightGBM expect it |
| Environment | **uv** | fast installs, lockfile for reproducible CI and Docker |

Rule of thumb: **joins in SQL (DuckDB), transformations in Python (Polars)**. Both share the Arrow memory format, so passing data between them costs nothing.

## Alternatives considered

- **pandas everywhere.** It loads whole files eagerly, uses one core, and stores strings inefficiently. Memory ends up several times the file size, and some operations make extra copies. The DPE extraction would not fit.
- **PostgreSQL.** Built for transactional workloads (many small reads and writes), stores data by row, and needs a running server plus a loading step. Overkill for batch analytics on files.
- **SQLite.** In-process like DuckDB, but row-oriented and slow on large joins and aggregations.
- **Spark.** Designed to spread work across a cluster. On one machine with a few GB, its JVM and setup add overhead and bring nothing. Kept for V2 ([ADR-0002](0002-scale-out-trigger.md)).
- **CSV between steps.** Loses types (commune `01001` becomes `1001`), and is larger and slower to read.

## Consequences

- The DPE extraction ran in about 2m45 within 5 GB of RAM (stage A about 1m45, stage B about 1 min). The DVF × DPE join and window features also stayed within that limit.
- Two engines to know instead of one. This is mitigated by the clear rule above.
- Polars streaming does not yet support every operation. Unsupported steps fall back to in-memory execution.
- Big joins must be written to bound memory: materialize the needed columns locally first, then join in hash buckets ([troubleshooting #10](../troubleshooting.md)).
- To do: measure pandas vs Polars peak RAM and time on one DVF year, and add the numbers here.

## Related decisions

- **No `shap` package.** Explanations use the native TreeSHAP in LightGBM/XGBoost (`pred_contrib=True`). This avoids the numba/llvmlite dependency chain ([troubleshooting #2](../troubleshooting.md)).
- **Bounded `requires-python = ">=3.11,<3.13"`.** It keeps the lockfile resolvable and matches what CI tests.

## References

- pandas, *Scaling to large datasets*: https://pandas.pydata.org/docs/user_guide/scale.html
- Polars, *Lazy API*: https://docs.pola.rs/user-guide/concepts/lazy-api/ · *Optimizations*: https://docs.pola.rs/user-guide/lazy/optimizations/ · *Streaming*: https://docs.pola.rs/user-guide/concepts/streaming
- DuckDB, *Why DuckDB*: https://duckdb.org/why_duckdb · *Memory Management in DuckDB* (2024): https://duckdb.org/2024/07/09/memory-management.html · *How to Tune Workloads*: https://duckdb.org/docs/current/guides/performance/how_to_tune_workloads
- Kuiper, Groß, Boncz, Mühleisen (2025). *Saving Private Hash Join*. VLDB. https://duckdb.org/library/saving-private-hash-join-vldb/
- Apache Parquet docs: https://parquet.apache.org/docs/ · Apache Arrow columnar format: https://arrow.apache.org/docs/format/Columnar.html · DuckDB × Polars: https://duckdb.org/docs/guides/python/polars
- J. Tigani (2023). *Big Data is Dead*: https://motherduck.com/blog/big-data-is-dead/ (vendor opinion). Counterpoint debate *Big Data: Funeral or Renaissance?*: https://motherduck.com/videos/big-data-funeral-or-renaissance/
- uv: https://docs.astral.sh/uv/
