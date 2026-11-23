# Deployment and configuration

How to run the estimator locally and in the cloud, and every setting it reads. Design decisions: [ADR-0010](adr/0010-deployment-and-monitoring.md) (deployment, monitoring) and [ADR-0011](adr/0011-app-serving-modes.md) (in-process vs remote API).

## Environment variables

Settings that change between machines live in environment variables, never in code ([Twelve-Factor, Config](https://12factor.net/config)). Locally they go in `.env` (git-ignored); `.env.example` lists them, empty, and is committed. Run commands with `uv run --env-file .env ...`.

| Variable | Used by | Meaning | Example |
|---|---|---|---|
| `HF_REPO_ID` | `serving/hub.py`, `scripts/push_to_hub.py` | Hugging Face model repo holding the serving files | `rdmouhouadi/property-price-estimator` |
| `HF_REVISION` | `serving/hub.py` | optional: pin a commit or tag of the model repo | `v1` |
| `HF_TOKEN` | `huggingface_hub` | token; needed to **push**, or to download from a private repo (else use `hf auth login`) | `hf_…` (never committed) |
| `GITHUB_REPO` | `scripts/push_to_hub.py` | repo linked from the model card | `rdmouhouadi/property-price-estimator` |
| `API_URL` | Streamlit app | set → remote API mode; unset → in-process mode | `http://127.0.0.1:8000` |
| `MODEL_SOURCE` | predictor | `mlflow` → load the MLflow champion; otherwise `artifacts/model.txt` | `mlflow` |
| `MLFLOW_TRACKING_URI` | training, tracking | MLflow backend | `sqlite:///mlflow.db` |
| `RUN_ID`, `LOG_TO_FILE` | logging | run identifier; `0` = stdout only (containers) | |

## Publish the model to Hugging Face Hub

```sh
uv run hf auth login                                   # once, with a Write token
uv run --env-file .env python scripts/push_to_hub.py   # model.txt, metadata.json, market_snapshot.parquet, card
```
The repo is created on first run (`exist_ok=True`). Push again after each promotion of a new champion.

## Run the app

| Mode | Command | When |
|---|---|---|
| In-process | `uv run --env-file .env streamlit run src/property_price/app/streamlit_app.py` | Streamlit Cloud, quick local demo |
| Remote API | terminal 1: `uv run uvicorn property_price.serving.api:app --reload` · terminal 2: `$env:API_URL = "http://127.0.0.1:8000"; uv run streamlit run src/property_price/app/streamlit_app.py` | development of the API, Render (part 3) |

To test the Hub download locally, rename `artifacts/` temporarily and start in-process: the files are fetched from the Hub.

## Streamlit Community Cloud

Live: **https://property-price-estimator.streamlit.app**

1. App-only, **pinned** requirements, generated from the lock file (never by hand):
   ```sh
   # pyproject.toml: [dependency-groups] app = ["streamlit", "fastapi", "httpx", ...]
   uv lock
   uv export --only-group app --no-hashes --no-emit-project -o src/property_price/app/requirements.txt
   ```
   The file sits **next to the entrypoint**: Community Cloud uses the first dependency file it finds, searching the entrypoint's folder before the repo root, and prefers `uv.lock` over `requirements.txt`. At the root, it would install the full `uv.lock` (MLflow, DVC…). CI regenerates it and fails if it differs (`git diff --exit-code`).
   Smoke test before deploying: a throwaway venv with only this file (`uv venv .venv-app` → `uv pip install -r … --python .venv-app` → run the app).
2. share.streamlit.io → New app → this repo, branch `main`, entrypoint `src/property_price/app/streamlit_app.py`, Python 3.11 (Advanced settings).
   The app adds `src/` to `sys.path` at the top of `streamlit_app.py` (the package isn't installed on the cloud).
3. **Secrets:** `HF_REPO_ID = "rdmouhouadi/property-price-estimator"`. Leave `API_URL` unset.
4. First visit: model download + load (cold start). The app sleeps after inactivity.

## Next (part 3)

Docker images (API, app) → Terraform → Prometheus + Grafana → (Ansible) → Render, with `API_URL` pointing the app at the hosted API.
