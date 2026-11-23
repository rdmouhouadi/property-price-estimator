# ADR-0011: App serving modes, in-process vs remote API

- **Status:** accepted
- **Date:** 2026-11-23

## Context

The Streamlit app needs estimates. Until now it called the FastAPI service over HTTP, so two processes had to run. Streamlit Community Cloud hosts **only the Streamlit process**: there is no FastAPI there. The model files (`model.txt`, `market_snapshot.parquet`) are git-ignored, so they aren't in the deployed repo either.

## Vocabulary

- **Remote API mode** (also *out-of-process*, *client–server*, *model as a service*): the model runs in **another process**, often on another machine. The app sends an HTTP request (`POST /estimate`) and reads the JSON answer. Here: FastAPI + uvicorn.
- **In-process mode** (also *embedded model*): the model runs **inside the same Python process** as the app. A function call, no network between UI and model.
- **Hugging Face Hub here is storage, not compute.** The app doesn't "call the model on Hugging Face". It **downloads the files** from the Hub once, then runs the model itself. (Running the model on Hugging Face's servers would be a different product: Inference Endpoints or a Space.)

## Decision

One app, **two modes, chosen by one environment variable:**

| `API_URL` | Mode | What happens |
|---|---|---|
| set (e.g. `http://127.0.0.1:8000`) | remote API | `requests` → FastAPI → predictor |
| not set | in-process | the FastAPI app itself runs inside Streamlit, through FastAPI's `TestClient`; no server, no network |

**The trick: reuse the API in-process instead of rewriting it.** FastAPI's `TestClient` sends requests straight to the app's code in memory (an ASGI call), without a server or a socket. So in-process mode runs exactly the same validation, geocoding, predictor and error codes as the real API, and returns responses of the same shape. The app only has one function, `call_api(method, path, ...)`:

```python
API_URL = os.environ.get("API_URL")

@st.cache_resource          # one client per app server, shared by all users
def _local_client():
    from fastapi.testclient import TestClient
    from property_price.serving.api import app
    client = TestClient(app)
    client.__enter__()      # runs the lifespan: the model is loaded once
    return client

def call_api(method, path, **kwargs):
    if API_URL:
        return requests.request(method, f"{API_URL}{path}", timeout=30, **kwargs)
    return _local_client().request(method, path, **kwargs)
```

**Model files come from the Hub only when missing** (`serving/hub.py`, `ensure_serving_files()`, called first in `Predictor.__init__`):
- locally, DVC's files exist → nothing is downloaded;
- on Streamlit Cloud (or in a fresh container) → `model.txt`, `metadata.json`, `market_snapshot.parquet` are downloaded from `HF_REPO_ID` (optionally pinned with `HF_REVISION`) on first start, then reused.

### How to run each mode

```sh
# in-process (as on Streamlit Cloud)
uv run --env-file .env streamlit run src/property_price/app/streamlit_app.py

# remote API (two terminals, PowerShell)
uv run uvicorn property_price.serving.api:app --reload
$env:API_URL = "http://127.0.0.1:8000"; uv run streamlit run src/property_price/app/streamlit_app.py
Remove-Item Env:API_URL    # back to in-process
```

On Streamlit Cloud: leave `API_URL` unset, set `HF_REPO_ID` in the app's **Secrets**. On Render (part 3): set `API_URL` to the API service's URL.

## Pros and cons

| | In-process | Remote API |
|---|---|---|
| Services to run and host | **one** | two |
| Free hosting | **yes** (Streamlit Cloud) | needs a host for the API (Render, a Space…) |
| Latency UI → model | **none** (function call) | one HTTP round trip |
| Other clients (scripts, other apps) | no API exposed | **yes**, documented at `/docs` |
| Scaling | UI and model scale together; each app replica loads the model (~70 MB on disk, more in RAM) | **independently** |
| Memory in the UI process | model + snapshot + Streamlit | **UI only** |
| Cold start | model download + load on first visit | the API stays warm separately |
| HTTP headers (`noindex`), auth, rate limits, Prometheus metrics | not available (no HTTP server of ours) | **available** |
| Failure isolation | a model crash takes the UI down | **UI can show "service unavailable"** |
| Same code path as production API | yes, through `TestClient` | yes |

**When to use which:** in-process for a free public demo and a single user-facing app; remote API as soon as there is more than one client, real traffic, or monitoring of the model service (part 3: Docker, Prometheus, Render).

## Caveats

- `TestClient` is designed for tests. Using it to embed an app is a pragmatic shortcut, fine for a demo. A production in-process app would call the `Predictor` directly, or the API would be hosted.
- `st.cache_resource` shares one predictor across all sessions of an app server. LightGBM prediction is read-only, so sharing is safe here.
- Heavy imports (e.g. MLflow) must stay inside the branches that need them, or the cloud app has to install them.

## Alternatives considered

- **Duplicate the API logic in the app:** two code paths to keep in sync; results could diverge.
- **Model files in git (Git LFS):** works, but no model card, no download page, LFS quotas.
- **Hugging Face Space or Inference Endpoint:** runs the model on Hugging Face's side; useful later, more setup than a beta needs.

## References

- FastAPI, *Testing* (`TestClient`): https://fastapi.tiangolo.com/tutorial/testing/ · *Lifespan events*: https://fastapi.tiangolo.com/advanced/events/
- Starlette, *TestClient*: https://www.starlette.io/testclient/
- Streamlit, *Caching* (`st.cache_resource`): https://docs.streamlit.io/develop/concepts/architecture/caching · *Secrets management*: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- Hugging Face Hub, *Download files* (`hf_hub_download`): https://huggingface.co/docs/huggingface_hub/guides/download
- The Twelve-Factor App, *Config* (settings in environment variables): https://12factor.net/config
- Chip Huyen (2022), *Designing Machine Learning Systems*, ch. 7 (model deployment: online vs batch prediction, model as a service, edge/embedded)
- Lakshmanan, Robinson, Munn (2020), *Machine Learning Design Patterns*, *Stateless Serving Function* pattern
