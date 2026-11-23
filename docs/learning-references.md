# Learning references

Where to go deeper on every stage of this project. For each one: the **official docs** (start here), a **book or course** (the why), and a **video** (the quick tour). The *why we chose it* is in the [ADRs](adr/).

## Cross-cutting

| | |
|---|---|
| Book | Chip Huyen (2022), *Designing Machine Learning Systems*, O'Reilly. The one book for this project: data (ch. 3–5), evaluation (6), deployment (7), drift and monitoring (8), continual learning (9). |
| Book | Lakshmanan, Robinson, Munn (2020), *Machine Learning Design Patterns*, O'Reilly. Patterns used here: *Continued Model Evaluation*, *Workflow Pipeline*, *Feature Store* (our market snapshot is a tiny one). |
| Course | DataTalks.Club **MLOps Zoomcamp** (free): https://github.com/DataTalksClub/mlops-zoomcamp. Tracking (module 2), orchestration (3), deployment (4), monitoring (5), best practices and CI (6). Each module links its lecture videos. |
| Video | Same Zoomcamp lectures, module by module. |

## Part 1: the model

### Setup: uv, project layout
- Docs: uv https://docs.astral.sh/uv/ (projects, lockfile, `requires-python`)
- Read: Python Packaging User Guide, *src layout*: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/

### Data processing: DuckDB, Polars, Parquet ([ADR-0001](adr/0001-data-processing-stack.md))
- Docs: DuckDB *Why DuckDB* https://duckdb.org/why_duckdb · *How to Tune Workloads* https://duckdb.org/docs/current/guides/performance/how_to_tune_workloads · *Memory Management in DuckDB* (2024) https://duckdb.org/2024/07/09/memory-management.html
- Docs: Polars user guide, lazy API and streaming: https://docs.pola.rs/user-guide/concepts/lazy-api/
- Docs: Parquet https://parquet.apache.org/docs/ · Arrow columnar format https://arrow.apache.org/docs/format/Columnar.html
- Paper: Kuiper et al. (2025), *Saving Private Hash Join*, VLDB: https://duckdb.org/library/saving-private-hash-join-vldb/
- Read: pandas, *Scaling to large datasets*: https://pandas.pydata.org/docs/user_guide/scale.html
- Opinion and counterpoint: J. Tigani, *Big Data is Dead* https://motherduck.com/blog/big-data-is-dead/ · debate *Big Data: Funeral or Renaissance?* https://motherduck.com/videos/big-data-funeral-or-renaissance/

### Data sources
- DVF (geo-DVF): https://www.data.gouv.fr/ (search "Demandes de valeurs foncières géolocalisées")
- ADEME DPE since July 2021: https://www.data.gouv.fr/datasets/dpe-logements-existants-depuis-juillet-2021/ ([ADR-0003](adr/0003-dpe-source-remote-duckdb.md))
- Valeur verte dataset (external check of the join): https://www.data.gouv.fr/datasets/valeur-verte-des-logements-ecarts-de-prix-par-etiquette-dpe-610-000-ventes-dvf-x-ademe
- DPE coefficient changes: [ADR-0005](adr/0005-dpe-coefficient-drift.md) references (ministry pages)

### Record linkage (joining without a key, [ADR-0004](adr/0004-dvf-dpe-matching-rules.md))
- Book: Christen (2012), *Data Matching*, Springer (normalisation, blocking, evaluation)
- Docs: Base Adresse Nationale https://adresse.data.gouv.fr/

### Features, validation, models
- Book: James, Witten, Hastie, Tibshirani, *An Introduction to Statistical Learning* (free, Python labs): https://www.statlearning.com (§6.2 Ridge, ch. 8 trees and boosting, ch. 5 resampling)
- Book: Géron, *Hands-On Machine Learning*, O'Reilly (ch. 2 end-to-end project, ch. 6–7 trees and ensembles)
- Paper: Grinsztajn, Oyallon, Varoquaux (2022), *Why do tree-based models still outperform deep learning on tabular data?* https://arxiv.org/abs/2207.08815
- Docs: LightGBM https://lightgbm.readthedocs.io/ · XGBoost paper https://arxiv.org/abs/1603.02754
- Docs: scikit-learn, *Time series split* and *refit* (GridSearchCV): https://scikit-learn.org/stable/modules/cross_validation.html
- Book: Molnar, *Interpretable Machine Learning* (permutation importance, SHAP): https://christophm.github.io/interpretable-ml-book/
- Video: StatQuest (Josh Starmer) series *Ridge Regression*, *Random Forests*, *Gradient Boost*, *XGBoost*. More in [models.md](models.md).

### Logging ([ADR-0006](adr/0006-logging.md))
- Docs: Python logging HOWTO https://docs.python.org/3/howto/logging.html · logging cookbook https://docs.python.org/3/howto/logging-cookbook.html
- Read: The Twelve-Factor App, *Logs*: https://12factor.net/logs

## Part 2: MLOps

### Pipeline and parameters: DVC ([ADR-0007](adr/0007-pipeline-and-tracking.md))
- Docs: *Get started: data pipelines* https://dvc.org/doc/start/data-pipelines · *dvc.yaml* https://dvc.org/doc/user-guide/project-structure/dvcyaml-files · command reference (`repro`, `commit`, `dag`, `params diff`, `metrics diff`) https://dvc.org/doc/command-reference
- Course: MLOps Zoomcamp (best-practices module)
- Video: the official DVC YouTube channel (DVCorg), *Data pipelines* episodes

### Tracking and registry: MLflow ([ADR-0007](adr/0007-pipeline-and-tracking.md))
- Docs: https://mlflow.org/docs/latest/ (Tracking, *Model Registry* with aliases, `mlflow.lightgbm` flavour)
- Course: MLOps Zoomcamp, module 2 (experiment tracking and model management)
- Video: Zoomcamp module 2 lectures

### Serving: FastAPI and Streamlit ([ADR-0009](adr/0009-serving.md))
- Docs: FastAPI tutorial https://fastapi.tiangolo.com/tutorial/ · *Lifespan events* https://fastapi.tiangolo.com/advanced/events/ · *Testing* https://fastapi.tiangolo.com/tutorial/testing/
- Docs: Pydantic https://docs.pydantic.dev/
- Docs: Streamlit https://docs.streamlit.io/ (forms, `st.metric`, `st.map`, `st.plotly_chart`)
- Docs: IGN geocoding https://geoservices.ign.fr/documentation/services/services-geoplateforme/geocodage · API Carto cadastre https://apicarto.ign.fr/api/doc/cadastre
- Course: MLOps Zoomcamp, module 4 (deployment)

### Drift and monitoring ([ADR-0008](adr/0008-drift-detector-design.md))
- Book: Huyen, *Designing ML Systems*, ch. 8 (covariate, label and concept shift; detection; monitoring)
- Book: Siddiqi (2006), *Credit Risk Scorecards*, Wiley (PSI and its thresholds)
- Paper: Rabanser, Günnemann, Lipton (2019), *Failing Loudly*, NeurIPS: https://arxiv.org/abs/1810.11953 (which shift tests actually detect shift)
- Docs: Evidently AI https://docs.evidentlyai.com/ (presets, metrics explained, even if not used here)
- Course: MLOps Zoomcamp, module 5 (monitoring)

### Testing and CI
- Docs: pytest https://docs.pytest.org/ · Book: Okken, *Python Testing with pytest* (2nd ed., 2022)
- Docs: ruff https://docs.astral.sh/ruff/
- Docs: uv in GitHub Actions https://docs.astral.sh/uv/guides/integration/github/ · GitHub Actions https://docs.github.com/actions
- Course: MLOps Zoomcamp, module 6 (best practices: tests, linting, CI/CD)

### Deployment: model hub, serving modes, configuration ([ADR-0010](adr/0010-deployment-and-monitoring.md), [ADR-0011](adr/0011-app-serving-modes.md))
- Docs: Hugging Face Hub, upload and download (`hf_hub_download`), model cards: https://huggingface.co/docs/huggingface_hub/guides/download · https://huggingface.co/docs/hub/model-cards
- Docs: FastAPI *Testing* (`TestClient`, the in-process trick) https://fastapi.tiangolo.com/tutorial/testing/ · Starlette TestClient https://www.starlette.io/testclient/
- Docs: Streamlit caching (`st.cache_resource`) https://docs.streamlit.io/develop/concepts/architecture/caching · Community Cloud and secrets https://docs.streamlit.io/deploy/streamlit-community-cloud
- Read: The Twelve-Factor App, *Config*: https://12factor.net/config
- Book: Huyen, *Designing ML Systems*, ch. 7 (deployment: model as a service vs embedded, online vs batch) · Lakshmanan et al., *ML Design Patterns*, *Stateless Serving Function*
- Course: MLOps Zoomcamp, module 4 (deployment: web service vs batch)

## Next steps (not built yet)

- Docker: https://docs.docker.com/get-started/ · Compose https://docs.docker.com/compose/
- Terraform, AWS provider: https://developer.hashicorp.com/terraform/tutorials/aws-get-started
- Hugging Face Hub, model cards: https://huggingface.co/docs/hub/model-cards
- Spark on Kubernetes and EMR Serverless (V2): see [ADR-0002](adr/0002-scale-out-trigger.md)
- Conformal prediction for calibrated ranges (V1.1): Angelopoulos & Bates, *A Gentle Introduction to Conformal Prediction*: https://arxiv.org/abs/2107.07511
