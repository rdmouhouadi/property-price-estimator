# ADR-0009: Serving, FastAPI for the model, Streamlit for people

- **Status:** accepted
- **Date:** 2026-11-22

## Context

A user knows an address, a type, a surface, rooms, maybe a DPE label. The model needs 21 features, including the cadastral section and the latest local market prices. Something must turn the first into the second, the same way training did.

## Decision

- **FastAPI** (`serving/api.py`) owns the model: Pydantic-validated `POST /estimate`, `GET /health` (serving model version), model and market snapshot loaded once at startup (lifespan), clear 404 (address not found) and 503 (geocoding service down), `X-Robots-Tag: noindex` (DVF terms forbid indexing transactions).
- **Streamlit** (`app/streamlit_app.py`) is only a client of the API: form, estimate, range, map, "what is my energy rating worth?" chart. The UI can be replaced without touching the model.
- **Geocoding through IGN:** Géoplateforme geocoding (`data.geopf.fr/geocodage/search`, the successor of `api-adresse.data.gouv.fr`) gives the commune code and coordinates; API Carto cadastre gives the parcel, whose first 10 characters are the cadastral section.
- **Market snapshot** (DVC stage `market_snapshot`): the latest 12-month prices per section, commune and département × type, rebuilt with every pipeline run, so serving uses the same shrinkage as training.
- **Range shown = ± test median error for the property type.** Honest and simple; calibrated intervals are V1.1.
- **Model source:** `artifacts/model.txt` by default, or the MLflow `champion` (`MODEL_SOURCE=mlflow`).

## Alternatives considered

- **Streamlit alone (model inside the app):** fastest to build, but no API for other clients, and model and UI ship together.
- **Flask:** no built-in validation or OpenAPI docs.
- **BentoML / MLflow serve:** serve the model, not the feature rebuilding (geocoding, cadastre, market lookup), which is most of the work here.
- **Vercel front end:** better for a polished product, more work than a weekend beta needs.

## Consequences

- Two processes to run (uvicorn + streamlit). Docker Compose is the next step.
- Serving depends on two IGN services. If they're down, the API returns 503 instead of a wrong estimate.
- Tests mock the geocoder, so they run offline and in CI.

## References

- FastAPI docs (tutorial, lifespan events, testing): https://fastapi.tiangolo.com/
- Streamlit docs: https://docs.streamlit.io/
- IGN Géoplateforme, geocoding service: https://geoservices.ign.fr/documentation/services/services-geoplateforme/geocodage
- IGN API Carto, cadastre module: https://apicarto.ign.fr/api/doc/cadastre
