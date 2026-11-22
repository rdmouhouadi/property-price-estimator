# Build journal

What was done, in order, and why. Links point to the decisions (ADRs) and the problems hit ([troubleshooting](troubleshooting.md)).

## Saturday 21 Nov 2026: the ML part

**1. Choose the problem.** The brief: tabular, big or semi-big, simple, and **useful to real people**, with a model people can download. A first idea, energy-consumption forecasting from smart meters, was dropped, because users don't have the input data. A property price estimator works: anyone knows their commune, surface and rooms. Prior art checked: Valia (DVF estimator), the *Valeur verte* dataset (DVF × DPE), VendreBien, Copilot Immo. The estimator itself exists. The angle no one covers: **detecting DPE rule changes and retraining automatically** ([ADR-0005](adr/0005-dpe-coefficient-drift.md)).

**2. Set up.**
- Repo scaffold, uv environment with a bounded Python range, data stack Polars/DuckDB/pyarrow, ML stack scikit-learn/LightGBM/XGBoost/Optuna/Plotly ([ADR-0001](adr/0001-data-processing-stack.md)).
- `data/` git-ignored. Conventional Commits.
- Issues: #1–#5.

**3. Download DVF.** `download_dvf.py` gets geo-DVF `full.csv.gz` per year, 2021–2025, resumable (#6).

**4. Find the DPE data.** No full CSV (#7). Found ADEME's remote DuckDB: `dpe_setup.py` attaches it, and `scripts/dpe_inspect.py` dumped schema, enums and row counts to `reports/dpe_schema.txt`. That mapped the table links and property-type codes ([ADR-0003](adr/0003-dpe-source-remote-duckdb.md)).
- **Discovery:** ADEME already publishes labels recalculated under the new electricity coefficient, which gives the harmonisation step for free.

**5. Extract DPE.** The first single-query attempt ran out of memory (#9, #10). The rewrite:
- stage A pulls the needed columns per table to local Parquet;
- stage B joins locally in 8 hash buckets;
- result: 15,672,018 DPEs in under 3 minutes within 5 GB.

**6. Explore DVF.** Type inference broke on `14A` (#11), so DVF is read all-as-strings. Cleaning rules set: ordinary sales only, one row per sale, exactly one dwelling, outbuildings counted, price never summed. First commit.

**7. Clean DVF.** `clean_dvf.py`:
- DuckDB converts csv.gz → Parquet, with explicit quoting (#13);
- Polars rebuilds one row per sale, applies the filters and prints lineage counts;
- result: 4,245,617 sales. Medians match the known market levels.

**8. Join DVF × DPE.** `join_dvf_dpe.py`:
- normalized addresses, candidates saved with surface and date gaps, rules as parameters;
- result: **604,773** unique matches, vs 610,000 in the independent Valeur verte dataset ([ADR-0004](adr/0004-dvf-dpe-matching-rules.md)).

**9. Restructure.** The data stage is done, so the scripts moved into the `src/property_price/{data,features,models,monitoring}` package (hatchling build, run with `python -m`), and exploration scripts moved to `scripts/`.

**10. Build features.** `build_features.py`:
- target ln(price/m²);
- leak-free 12-month rolling market prices by cadastral section, commune and département, with shrinkage;
- harmonised DPE class as an ordinal;
- time split: train < Jul 2024, valid H2 2024, test 2025.
- Check: section correlation 0.839 > commune 0.824 > département 0.739.

**11. Logging.** A shared `logging_config.py`: console + JSON lines, `run_id`, `log_metric` ([ADR-0006](adr/0006-logging.md)).

**12. Compare models.** The single script was refactored into `dataset.py`, `metrics.py`, `models_zoo.py` (every model is `fn(train, valid, feats) -> predictions`), `models_comparison.py` and `importance.py`.
- **Experiment A:** LightGBM best (17.5%), tied with XGBoost, faster.
- **Experiment B:** the DPE cuts the median error by 13% on identical rows.
- Issues: #14–#17.

**13. Select features.** Permutation importance: the neighbourhood market price dominates, and the construction period is the top DPE feature. Dropped `t_months` (trees can't extrapolate time), `month` and `dpe_genere_immeuble`.

**14. Train the final model.** `train_valid_model.py`:
- fit on train with early stopping on validation → 2,646 trees, validation 16.3%;
- refit on train + validation (the refit / final fit);
- saved to `artifacts/`.
- Issues: #18–#20.

**15. Test once.** `test_model.py` on 2025: **median error 16.0%, 59.5% within 20%**, apartments 13.6%, houses 18.2%. Test ≈ validation, so no overfitting.

**16. Write-up.** Portfolio case study, part 1: *What is a home's energy rating worth?*

**17. Docs and GitHub repo.** README, architecture, 6 ADRs, data dictionary, lineage, model card, models, troubleshooting, this journal, roadmap, PLAYBOOK.

## Sunday 22 Nov 2026: the MLOps part

Started around 17:00. Order agreed up front: pipeline → parameters → tracking → serving → drift → retraining → CI. Docker and AWS were left for later.

**18. Vision first: V3 "value over time".** Before starting, the long-term goal was added to the roadmap: a 10-year value curve under 4 explicit scenarios (baseline, local development, downturn, renovation), driven by PLU zoning, Sitadel building permits, DPE rental bans and the owner's renovation choice. It's a scenario projection, not a forecast ([roadmap](roadmap.md)).

**19. DVC pipeline.** `uv add dvc`, `dvc init`, cache type `hardlink,copy`. `dvc.yaml` declares the stages over the existing modules: `download_dvf` (output `persist`, so raw data is never deleted) → `extract_dpe` → `clean_dvf` → `join` → `features` → `train` → `test`.
- `reports/test_metrics.json` is a DVC metric, not cached.
- `models_comparison` and `importance` stay out of the pipeline: they're exploration, not production.
- `dvc commit -f` recorded the existing outputs without recomputing hours of work ([ADR-0007](adr/0007-pipeline-and-tracking.md)).

**20. Parameters.** `params.yaml` holds every knob: DVF years, DPE start date, match rules, feature window and shrinkage, split dates, model settings, and `dpe_rules.elec_coefficient: 1.9`. A small loader (`params.py`, cached) replaced the constants in every script, and each `dvc.yaml` stage declares the parameter sections it reads. Values were unchanged, so `dvc commit -f` again.

**21. MLflow.** SQLite backend (`mlflow.db`) plus `mlruns/`, both git-ignored. `tracking.py`:
- experiment `property-price`, registered model `property-price-estimator`, alias `champion`;
- `train_valid_model` logs parameters, validation metrics and the model, and registers a new version;
- `test_model` logs test metrics into the same run, then calls `promote_if_better`: the new version becomes champion only if its test median error beats the champion's.
- v1 promoted to champion (median error 15.96%). Issues: #21–#22.

**22. Serving core.**
- `market_snapshot` stage: the latest 12-month market prices per section, commune and département × type, so the API can rebuild the same features the model was trained on.
- `serving/geo.py`: address → IGN Géoplateforme geocoding (`data.geopf.fr/geocodage`, which replaces the old `api-adresse.data.gouv.fr`) → API Carto cadastre (parcel → cadastral section).
- `serving/predictor.py`: rebuilds the 21 features, returns the estimate, a typical range (± test median error for that property type) and a "what if the label were A…G" table. Loads the model from `artifacts/` or the MLflow champion. Issue: #23.

**23. FastAPI.** `serving/api.py`: Pydantic-validated request, model loaded once at startup (lifespan), `GET /health`, `POST /estimate`, clean 404/503 errors, `X-Robots-Tag: noindex` (DVF terms). `tests/test_api.py` mocks geocoding, so it needs no network. First real call: 10 rue de Rivoli, Paris, 50 m² apartment, label D → **€587,000** (€11,750/m²).

**24. Streamlit.** `app/streamlit_app.py` calls the API: form, estimate with range and €/m², map, and a bar chart *"What is my energy rating worth?"*. Second test, Le Pecq (78), same flat → €206,000.
- Finding: G → A is worth **+4% in central Paris but +13% in Le Pecq**. The green value is bigger where location matters less ([model card](model-card.md)).

**25. Drift detection, v1.** `monitoring/drift.py`: hand-written PSI (Population Stability Index) on the label distribution. Reference = harmonised labels of the 12 months before the test period. Two checks: recent real DPEs (expected stable, which proves harmonisation works) and the same DPEs relabelled at the 2027 coefficient, 1.7 (drift expected).
- **Result:** real 0.017 stable, as expected. **Simulated 0.028, also "stable".** The monitor was blind to the very change it was built for: only electric-heated homes are affected, their energy figure drops ~10%, and labels only move near the thresholds, so the change is diluted in the whole population.

**26. Drift detection, v2.** Three changes:
- PSI on the **electric-heated segment** only: 0.033, still "stable", even though A went 4.1% → 6.3% and B 8.8% → 12.8%.
- A detector on the **cause**: the *implied coefficient*, the median of primary ÷ final energy for electric-heated homes. Reference 1.905, recent real 1.900 (stable), simulated **1.70 (−10.75%, drift)**. It fires on the first new ratings, before any label distribution moves.
- Bug fixed: `drift_detected` must count only real checks, not simulated ones.
- Caveat: on simulated data, the implied coefficient is partly drift by construction. The real test is the 2.3 → 1.9 change of January 2026 (backtest pending, see [roadmap](roadmap.md)). Design: [ADR-0008](adr/0008-drift-detector-design.md).

**27. Drift → retrain loop.**
- `dpe_rules.py`: label thresholds and `harmonised_sql(coef, elec_ids)`, shared by features and drift, so both apply the same rule. At 1.9 it returns the original SQL, so nothing changes today.
- `monitoring/retrain_on_drift.py [--simulate]`: reads `reports/drift.json`; if the implied coefficient drifted, it writes the new coefficient into `params.yaml` and runs `dvc repro test`.
- First run failed on a missing parameter (#24).
- **Demo at 1.7:** trigger → features rebuilt → retrained (2,966 trees) → v2 registered → test 15.94% → gate promoted v2 (15.94% < 15.96%).
- **Finding:** the gate is too weak. 0.02 points is noise, and the two scores come from different test features (v2 at 1.7, v1 at 1.9). A fair gate scores the champion on the same features and requires a margin (roadmap V1.1).
- Revert: champion alias back to v1, v2 tagged `simulated`, coefficient back to 1.9 in `params.yaml`, `dvc repro test`.

**28. CI.** `ruff` (lint, imports) and `pytest` as dev tools. `tests/test_dpe_rules.py` tests the drift logic on an in-memory DuckDB table, no data needed: worst of energy and emissions, unchanged at 1.9, an electric home at 190 kWh/m² becomes 170 → D to C at 1.7. The API test is skipped when the model isn't there. `.github/workflows/ci.yml`: `uv sync --locked`, ruff, pytest, `dvc dag` (checks the pipeline definition without running it). **CI green.** Issue: #25.

**29. Docs and write-up part 2.** This journal, PLAYBOOK part 2, troubleshooting #21–25, ADRs 0007–0009, [learning references](learning-references.md), model card, architecture, roadmap, README. Portfolio case study, part 2.
