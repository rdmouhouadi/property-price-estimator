# ADR-0010: Deployment and live monitoring

- **Status:** accepted (plan) · in progress
- **Date:** 2026-11-23

## Context

The estimator runs on one laptop: FastAPI + Streamlit, model and market snapshot in git-ignored folders. To make it usable by anyone, and to keep watching for the 2027 rule change, it needs a public home and monitoring that runs without the laptop.

## Decision

### Deployment (V1 beta)

1. **Model on Hugging Face Hub** (`model.txt`, `metadata.json`, `market_snapshot.parquet`, model card). It's the "downloadable model", and the place the app fetches its files from.
2. **App with two modes.** `API_URL` set → the app calls FastAPI (local, or a future hosted API). Not set → the app runs the `Predictor` in-process and downloads the files from the Hub on first start (cached).
3. **Slim `requirements.txt`** for the app only (no MLflow, DVC, XGBoost): faster builds, within the free tier's memory.
4. **Streamlit Community Cloud**, entrypoint `src/property_price/app/streamlit_app.py`, Python 3.11.

FastAPI goes online later, with Docker (Render or a Hugging Face Space).

### Monitoring: four layers

| Layer | What | How | Cadence |
|---|---|---|---|
| 1. Pipeline runs | did each step run, how many rows, how long | `logs/pipeline.jsonl` with `run_id` (follow live: `Get-Content logs\pipeline.jsonl -Wait -Tail 20`), MLflow UI | every `dvc repro` |
| 2. Data | has the DPE rule changed? | weekly GitHub Actions job: recent ratings from ADEME's remote DuckDB vs a **frozen reference** (`reports/drift_reference.json`) → implied coefficient + PSI → opens a GitHub issue on drift | weekly |
| 3. Service | is the app / API up and fast? | uptime ping on the app URL and `/health` (e.g. StakPuls); later Prometheus metrics + Grafana with Docker | every few minutes |
| 4. Model quality | is it still accurate? | log each estimate (inputs, model version, no personal data); score the champion on each new DVF release | April / October |

Layer 2 is the one that raises alerts. The others are for diagnosis.

## Alternatives considered

- **Deploy FastAPI + Streamlit together now** (Render, Fly.io): two services to host and keep awake; more than a beta needs.
- **Model in git (Git LFS):** works, but the Hub gives versioning, a model card and a download page for free.
- **Evidently / Grafana stack now:** useful once there's traffic and Docker; overkill for a beta.

## Consequences

- Streamlit Cloud can't set HTTP headers, so the `noindex` header only applies to the API. The app shows estimates, not individual sales, which keeps within the DVF terms.
- The free tier sleeps when unused: the first visit after a pause is slow.
- The weekly drift job depends on ADEME's remote database staying available, and on the frozen reference being committed.

## References

- Hugging Face Hub, uploading files and model cards: https://huggingface.co/docs/hub/models-uploading · https://huggingface.co/docs/hub/model-cards
- Streamlit Community Cloud, deploy an app: https://docs.streamlit.io/deploy/streamlit-community-cloud
- GitHub Actions, scheduled workflows (`on: schedule`): https://docs.github.com/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule
- Chip Huyen (2022), *Designing ML Systems*, ch. 8 (monitoring and observability)
