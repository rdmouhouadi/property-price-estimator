# Roadmap

## V1: ML (done, 21 Nov 2026)

Data prep for 4.2M sales and 15.7M DPEs, the DVF × DPE join, leak-free features, five models compared, LightGBM chosen, tested once on 2025 (median error 16.0%).

## Part 2: MLOps (done, 22 Nov 2026)

- [x] DVC pipeline (`dvc.yaml` stages, parameters in `params.yaml`)
- [x] MLflow tracking and model registry (champion alias, promotion gate)
- [x] Harmonise step (DPE labels under the current coefficient, from `params.yaml`, shared `dpe_rules.py`)
- [x] Drift detection: implied coefficient (primary) + label PSI overall and for electric homes (secondary)
- [x] Retrain trigger: drift → new coefficient → `dvc repro` → gate; demo at 1.7, then reverted
- [x] FastAPI `/estimate` and Streamlit app (estimate + range + "what is my DPE worth?"), `noindex`
- [x] Tests (pytest: DPE rules, API with mocked geocoding), ruff
- [x] GitHub Actions: lock check, lint, tests, `dvc dag`
- [x] Write-up part 2
- [x] **Backtest the drift detector on the real 2.3 → 1.9 change:** 2.30 → 1.90 (−17%) in the first month (23 Nov)
- [ ] **Freeze the drift reference** (`reports/drift_reference.json`), since ADEME restates history
- [ ] App: ask for the rating date; re-label pre-2026 electric-heated ratings at the current coefficient
- [ ] Full `dvc repro --force` from raw data (should reproduce 15.96%)
- [ ] DVC remote for prepared Parquet
- [ ] Schedule the drift check (weekly, GitHub Actions cron or local scheduler) and open an issue on drift
- [ ] Convert `print` to the logger in `data/` scripts
- [ ] Model and card on Hugging Face Hub
- [ ] Docker images (API, app, pipeline) + Compose; Terraform for AWS, validated with an AWS emulator

## Part 3: deploy and monitor (in progress, from 23 Nov 2026)

Plan: [ADR-0010](adr/0010-deployment-and-monitoring.md).

**Deploy**
- [ ] Push model, metadata, market snapshot and model card to Hugging Face Hub
- [ ] App in-process mode (no `API_URL` → `Predictor` in the app, files from the Hub, cached)
- [ ] Slim `requirements.txt` for the app
- [ ] Deploy on Streamlit Community Cloud (Python 3.11)

**Monitor (four layers)**
- [ ] 1. Pipeline runs: JSON-lines logs per `run_id` + MLflow UI (in place; document how to follow live)
- [ ] 2. Data: freeze the drift reference (`reports/drift_reference.json`); weekly GitHub Actions drift job on recent ADEME ratings → GitHub issue on drift
- [ ] 3. Service: uptime ping on the app and `/health`; later Prometheus + Grafana with Docker
- [ ] 4. Model quality: log estimates (inputs, model version); score the champion on each DVF release (April / October)

## V1.1: model improvements

- [ ] Relax match uniqueness: keep a clearly best candidate (closest surface, then date)
- [ ] Ablation: DPE strictly before the sale vs the +30-day tolerance
- [ ] Prediction ranges: LightGBM quantile objective, with coverage measured (conformal calibration)
- [ ] Tuning: more trees or a higher learning rate (early stopping hit 2,646 of 3,000), Optuna search
- [ ] Walk-forward validation as a robustness check
- [ ] Benchmark pandas vs Polars (RAM, time) for ADR-0001
- [ ] Update LightGBM `eval_set` → `eval_X` / `eval_y`
- [ ] **Fairer promotion gate:** re-score the champion on the same current test features, require a margin (e.g. 0.1 point); after a rule change, promote when not worse within a tolerance
- [ ] Third drift signal: share of new DPEs per `dpe_version`

## V1.5: app features

- [ ] 3D view beside the price monitor: pydeck/deck.gl, DPE coordinates (`ban_x/ban_y`, Lambert-93 → WGS-84), buildings via the RNB ID
- [ ] "Why this price": native TreeSHAP contributions as a waterfall

## V3: value over time ("what will my home be worth in 10 years?")

A **scenario projection**, not a forecast: a value curve for each of 4 explicit scenarios, shown as a fan chart, with the assumptions stated next to it.

**Model:** value(t) = today's estimate (V1 model) × local price index path(t) under the scenario, plus a label adjustment (green-value gap from V1, Exp B).

**Scenario drivers**
- **Market:** historical local trend, or a stress path (e.g. a repeat of the 2023–2024 slowdown).
- **Local development:** what is planned nearby. Dwellings authorised within 500 m (Sitadel building permits, dated, since 2013) and the PLU zone of the parcel, plus the share of to-be-urbanised land nearby (Géoportail de l'Urbanisme).
- **Energy regulation:** rental bans by DPE label (G since 2025, F in 2028, E in 2034 as currently scheduled; the calendar is still debated, which is why it's a scenario variable).
- **Owner choice:** keep the current label vs renovate (e.g. to C), using the energy-audit base for cost.

**Default scenarios:** baseline (trend continues) · development (planned construction happens) · downturn (stress market) · renovation (label upgraded before the next ban).

**Validation:** backtest what can be checked. Train on DVF+ up to year T, project 1–3 years, compare with real local price changes. The 10-year curves stay labelled as scenarios.

**Data needed:** DVF+ since 2014 (longer history, which triggers [ADR-0002](adr/0002-scale-out-trigger.md)), Sitadel permits, PLU zones, the rental-ban calendar.

## V2: scale and scope

- [ ] Cloud cluster when data justifies it ([ADR-0002](adr/0002-scale-out-trigger.md)): DVF+ since 2014, pre-2021 DPE, BDNB; minikube Spark first, then EMR Serverless
- [ ] Energy-audit base: renovation cost vs value gain ("is renovating worth it?")
