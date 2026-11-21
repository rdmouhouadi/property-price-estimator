# Architecture

## Goal

Estimate a home's sale price from what an owner knows, plus the history of past sales nearby. Optionally include the energy rating (DPE), and measure what it adds. Keep the system able to retrain when the DPE calculation rules change.

## V1: batch ML pipeline (done)

```sh
                 SOURCES                         STORAGE (local, Parquet)                 COMPUTE
┌──────────────────────────────┐
│ files.data.gouv.fr           │  download_dvf   data/raw/dvf/dvf_YYYY.csv.gz
│ geo-DVF full.csv.gz per year │ ─────────────►  (5 files)
└──────────────────────────────┘                        │ clean_dvf (DuckDB csv→Parquet, Polars)
                                                         ▼
                                                 data/interim/dvf_sales.parquet ──────┐
┌──────────────────────────────┐                                                      │
│ ADEME remote DuckDB (S3)     │  dpe_setup      data/raw/dpe/opendata.duckdb (views) │
│ ~20M DPEs, 170+ views        │ ─────────────►         │ extract_dpe A: columns → Parquet per table
└──────────────────────────────┘                        │ extract_dpe B: bucketed local join
                                                         ▼                             │
                                                 data/interim/dpe_flat/part_k.parquet ┤
                                                                                       │ join_dvf_dpe (DuckDB)
                                                                                       ▼
                                          data/processed/sales_enriched.parquet (all sales + DPE + has_dpe)
                                                                                       │ build_features (DuckDB windows)
                                                                                       ▼
                                          data/processed/features.parquet (target y, features, split)
                                                                                       │
                     models_comparison → importance → train_valid_model → test_model (once)
                                                                                       │
                                          artifacts/model.txt + metadata.json, reports/*.csv|json
```

### Components

| Module | Engine | Input → output | Notes |
|---|---|---|---|
| `data/download_dvf` | requests | data.gouv → `data/raw/dvf/` | resumable (`.part` files) |
| `data/dpe_setup` | DuckDB | remote `dpe.duckdb` → local view catalogue | queries stream from ADEME's storage |
| `data/extract_dpe` | DuckDB | remote views → `dpe_parts/` → `dpe_flat/` | stage A streams, stage B joins in 8 hash buckets |
| `data/clean_dvf` | DuckDB + Polars | csv.gz → `dvf_raw/` → `dvf_sales.parquet` | one row per sale, lineage counts |
| `data/join_dvf_dpe` | DuckDB | sales × DPE → `sales_enriched.parquet` | candidates saved, rules as parameters |
| `features/build_features` | DuckDB | → `features.parquet` | leak-free rolling market prices, time split |
| `models/*` | LightGBM, XGBoost, scikit-learn | features → reports, artifacts | see [build journal](build-journal.md) |
| `logging_config` | stdlib logging | all modules → console + `logs/pipeline.jsonl` | one `run_id` per execution |

### Design principles

1. **Resumable steps.** Each step writes files and skips outputs that already exist. A crash costs one step, not the pipeline.
2. **Bounded memory.** DuckDB runs with `memory_limit` set and spills to disk. Large joins are bucketed by hash, so RAM use stays flat as data grows ([ADR-0001](adr/0001-data-processing-stack.md)).
3. **Columns, not rows.** Everything between steps is Parquet, typed and compressed.
4. **Identifiers are strings.** Commune, département, postcode, parcel and lot codes are labels, never numbers.
5. **No leakage.** Market features use only sales before the one being estimated. Splits are by time. Test is scored once.
6. **Observable.** Every step logs its row counts with a `run_id` ([ADR-0006](adr/0006-logging.md)).

## Part 2: MLOps (planned, Sunday)

```sh
 GitHub Actions (weekly cron)                         DVC pipeline (params.yaml)
 ┌────────────────────────────┐      drift?           ┌───────────────────────────────────────┐
 │ pull new DPEs since last   │ ───── yes ──────────► │ harmonise → features → train → eval    │
 │ run → Evidently drift check│                       └───────────────┬───────────────────────┘
 └──────────┬─────────────────┘                                       │ challenger vs champion
            │ no: log report                                           ▼ on newest sales
            ▼                                          MLflow registry ("champion" alias)
       logs / GitHub issue                                             │
                                                                       ▼
                                   Hugging Face Hub (model + card) ─► FastAPI /predict ─► Streamlit app
```

- **Trigger 1, weekly:** input drift on new DPEs (class distribution, energy use per m², share of electric heating). This catches the coefficient change of 1 January 2027 ([ADR-0005](adr/0005-dpe-coefficient-drift.md)).
- **Trigger 2, twice a year:** new DVF release (April / October) → accuracy check on fresh sales and retrain.
- **Human gate:** a retrained model is promoted only if it beats the current one on the newest sales.
- **Packaging:** Docker images for the pipeline and the app. IaC (Terraform) for an AWS target, validated locally with AWS Emulator.

## V2: scale-out (planned)

Move from one laptop to a cloud cluster only when the data justifies it. See [ADR-0002](adr/0002-scale-out-trigger.md).
