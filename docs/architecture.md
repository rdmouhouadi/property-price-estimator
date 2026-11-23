# Architecture

## Goal

Estimate a home's sale price from what an owner knows, plus the history of past sales nearby. Optionally include the energy rating (DPE), and measure what it adds. Keep the system able to retrain when the DPE calculation rules change.

## Part 1: batch ML pipeline (done, 21 Nov 2026)

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

## Part 2: MLOps (built 22 Nov 2026)

```sh
                       params.yaml  (every setting, incl. dpe_rules.elec_coefficient)
                            │
   DVC pipeline (dvc.yaml)  ▼
   download_dvf ─► clean_dvf ─┐
   extract_dpe ───────────────┴► join ─► features ─► train ─► test ─► reports/test_metrics.json
                                    │      ▲           │        │
                                    │      │ dpe_rules │        └─► promote_if_better (gate)
                                    │      │ .py       ▼                     │
                                    │      │     MLflow run + registry ◄──────┘
                                    ▼      │     (v1, v2…, alias "champion")
                          market_snapshot  │                │
                                    │      │                ▼
                                    └──────┼────► FastAPI /estimate ◄── Streamlit app
                                           │        ▲  IGN geocoding + cadastre
                                           │
   monitoring/drift.py ── reports/drift.json ──► retrain_on_drift.py
   (implied coefficient,                        writes new coefficient → dvc repro test
    label PSI all / electric)

   GitHub Actions CI on every push: uv sync --locked · ruff · pytest · dvc dag
```

### Components added in part 2

| Module | Role |
|---|---|
| `params.py` + `params.yaml` | one cached loader; every setting in one file |
| `dvc.yaml` / `dvc.lock` | stages, dependencies, parameters per stage; `dvc repro` reruns what changed ([ADR-0007](adr/0007-pipeline-and-tracking.md)) |
| `tracking.py` | MLflow setup, registry, `promote_if_better` gate |
| `dpe_rules.py` | label thresholds, `harmonised_sql(coef, elec_ids)`; shared by features and drift |
| `features/market_snapshot.py` | latest local market prices for serving |
| `serving/geo.py` | address → commune, coordinates, cadastral section (IGN) |
| `serving/predictor.py` | rebuilds the 21 features, estimate + range + price by label |
| `serving/api.py` | FastAPI `/health`, `/estimate` ([ADR-0009](adr/0009-serving.md)) |
| `app/streamlit_app.py` | user interface, calls the API |
| `monitoring/drift.py` | implied coefficient + PSI checks, real and simulated → `reports/drift.json`, `drift.html` ([ADR-0008](adr/0008-drift-detector-design.md)) |
| `monitoring/retrain_on_drift.py` | drift → edit `params.yaml` → `dvc repro test` → gate; `--simulate` for the demo |
| `tests/`, `.github/workflows/ci.yml` | DPE rules unit tests, API test (mocked geocoding), CI |

### Design principles added

7. **One source of truth per rule.** The DPE coefficient lives in `params.yaml`; the label thresholds live in `dpe_rules.py`. Training, serving and monitoring all read the same ones.
8. **Monitor the cause.** The drift detector measures the rule itself (implied coefficient), not only its diluted effect on labels.
9. **Automation decides, people commit.** The retrain trigger leaves a diff (`params.yaml`, `dvc.lock`) and a registry decision; a person reviews and commits.
10. **The API owns the model.** The UI is a client and can be replaced.

### Not built yet

- Docker Compose for API + app; Terraform for an AWS target, validated with an AWS emulator.

## Part 3: deploy and monitor (in progress)

```sh
 Hugging Face Hub (model.txt, metadata.json, market_snapshot.parquet, card)
        │ downloaded on first start, cached
        ▼
 Streamlit Community Cloud ── app, in-process Predictor ── IGN geocoding + cadastre
        ▲ uptime ping (layer 3)

 GitHub Actions, weekly (layer 2):
   ADEME remote DuckDB (recent ratings) ─► drift vs frozen reports/drift_reference.json
        └─ drift? ─► open a GitHub issue ─► human runs retrain_on_drift locally

 Laptop (layer 1): dvc repro → logs/pipeline.jsonl (run_id) + MLflow UI
 Twice a year (layer 4): new DVF release → score the champion on fresh sales
```

Details and alternatives: [ADR-0010](adr/0010-deployment-and-monitoring.md).

## V2: scale-out (planned)

Move from one laptop to a cloud cluster only when the data justifies it. See [ADR-0002](adr/0002-scale-out-trigger.md).
