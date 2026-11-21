<div align="center">
# 🏠 Property Price Estimator
### What is a French home worth, and what is its energy rating worth?
 
*From 20 million rows of public data to a price estimate anyone can use, on one laptop.*
 
![Version](https://img.shields.io/badge/version-v0.1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Status](https://img.shields.io/badge/status-Part%201%20Complete-brightgreen)
 
**Author:** Richie Mouhouadi
 
</div>
---
 
## 🧭 What is it?
 
An estimator of the **sale price of a French house or apartment**, built entirely on public open data:
 
- **4.2M residential sales** (DVF, 2021–2025), joined with
- **15.7M energy performance ratings** (ADEME DPE, the A-to-G label every seller must show).
You enter what you know about a home: commune, surface, rooms, land, and optionally its energy rating. You get an estimated price. The model also measures **what a better energy rating is worth**, a question buyers and sellers keep asking.
 
It is built in two parts:
 
- **Part 1, the model** ✅: data engineering at the 20M-row scale, a validated join between two datasets that share no key, leak-free features, five models compared, and one tested once on a year it never saw.
- **Part 2, the MLOps** 🔄: an automated pipeline that **detects when France changes the energy-rating rules and retrains the model**, served through FastAPI and a Streamlit app.
---
 
## 🎯 Why this project
 
France publishes every property sale and every energy rating, but **the two datasets were never designed to work together**. Sales have no rating, ratings have no price, and nothing links them.
 
The rating itself is a **moving target**. On 1 Jan 2026, the electricity conversion coefficient in the DPE calculation dropped from 2.3 to 1.9. On 1 Jan 2027 it drops again, to 1.7. The same home can get a better label with no work done. A model trained on yesterday's labels quietly becomes wrong.
 
This project:
 
1. **Rebuilds the missing link** between sales and ratings, and validates it against an independent count.
2. **Measures the rating's real effect** on prices, on identical sales, with selection effects stated.
3. **Plans for the rules changing**: harmonised training labels today, drift detection and retraining in part 2.
4. **Stays useful to real people**: every input is something an owner knows. Users who don't know their rating still get an estimate.
---
 
## ✨ What's different
 
DVF price estimators and DVF × DPE analyses already exist (see [Prior art](#-prior-art--acknowledgements)). This project adds four things:
 
| | |
|---|---|
| 🔁 **Rule-change aware** | Training labels are harmonised under one coefficient, and part 2 monitors incoming ratings, detects the 2027 shift, and retrains with a human gate. None of the estimators reviewed model the label itself changing. |
| 📏 **Measured, not assumed** | Same model, same 73k sales, with vs without the rating: **−13% median error**. Selection effects stated, not hidden. |
| ✅ **Validated join** | **604,773** sales matched to their rating, within 1% of an independent dataset built with similar rules (610k). |
| 🧩 **One model, optional rating** | Uses the rating when given, still estimates without it. |
 
All of it runs on **one laptop**: about 20M source rows within 5 GB of RAM, with every decision recorded in an [ADR](docs/adr/).
 
---
 
## 📊 Results (Part 1)
 
**Final test on 2025:** 790,767 sales the model never saw, scored once.
 
| Segment | Median error | Within 10% | Within 20% | Mean error |
|---|---:|---:|---:|---:|
| **All sales** | **16.0%** | **33.2%** | **59.5%** | **€48,945** |
| Apartments | 13.6% | 38.1% | 66.9% | €38,973 |
| Houses | 18.2% | 29.4% | 53.8% | €56,675 |
| With a matched rating | 11.9% | 43.1% | 72.6% | €39,805 |
| Without a matched rating | 17.2% | 30.9% | 56.4% | €51,129 |
 
*Median error = median of |estimate − price| / price.* Test (16.0%) ≈ validation (16.3%): no overfitting.
Limits, risks and intended use: [model card](docs/model-card.md).
 
**Model comparison** (validation, H2 2024, no rating features):
 
| Model | Median error | Within 20% | Training time |
|---|---:|---:|---:|
| Neighbourhood average (baseline) | 19.9% | 50.2% | – |
| Ridge | 19.6% | 50.9% | 2 s |
| Random forest (300k rows) | 18.3% | 53.8% | 12 min |
| **LightGBM (1M rows)** ✅ | **17.5%** | **55.9%** | **28 s** |
| XGBoost (1M rows) | 17.6% | 55.7% | 75 s |
 
📝 Write-up: [What is a home's energy rating worth?](https://rdmouhouadi.github.io/) *(case study, part 1)*
 
---
 
## 🏗️ Architecture Overview
 
```
┌──────────────────────────────────────────────────────────────────────┐
│                       Property Price Estimator                        │
├──────────────────┬───────────────────────────────────────────────────┤
│   Data Sources   │  DVF (data.gouv.fr) · ADEME DPE (remote DuckDB)   │
├──────────────────┴───────────────────────────────────────────────────┤
│                                                                      │
│   ┌──────────────────────┐          ┌──────────────────────────┐     │
│   │ DVF: csv.gz → Parquet │          │ DPE: 8 tables → Parquet  │     │
│   │ one row per sale      │          │ bucketed join, 15.7M     │     │
│   │ 4.25M sales           │          │ ratings                  │     │
│   └──────────┬───────────┘          └────────────┬─────────────┘     │
│              └─────────────┬──────────────────────┘                  │
│                            ▼                                         │
│              ┌───────────────────────────┐                           │
│              │  Address join (DuckDB)    │  604,773 matches          │
│              └─────────────┬─────────────┘                           │
│                            ▼                                         │
│              ┌───────────────────────────┐                           │
│              │  Leak-free features       │  12-month local prices    │
│              │  + time split             │  section → commune → dept │
│              └─────────────┬─────────────┘                           │
│                            ▼                                         │
│   compare 5 models → feature selection → train / refit → test once   │
│                            │                                         │
│                            ▼                                         │
│              artifacts/model.txt + metadata.json                     │
│                            │                                         │
│   ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│─ Part 2 (in progress) ─ ─ ─ ─ ─ ─ ─ ─   │
│                            ▼                                         │
│   drift check (weekly) → retrain → challenger vs champion → promote  │
│                            │                                         │
│                 FastAPI /predict  →  Streamlit app                    │
└──────────────────────────────────────────────────────────────────────┘
```
 
### Pipeline: scripts and files
 
```sh
DVF csv.gz (5 yrs) ─► clean_dvf ─► dvf_sales.parquet (4.25M sales) ─┐
                                                                     ├─► join_dvf_dpe ─► sales_enriched.parquet
ADEME remote DuckDB ─► extract_dpe ─► dpe_flat/*.parquet (15.7M) ────┘          │
                                                                                 ▼
                                                     build_features ─► features.parquet (time split)
                                                                                 │
                     models_comparison ─► importance ─► train_valid_model ─► artifacts/model.txt
                                                                                 │
                                                                        test_model (once) ─► reports/test_metrics.json
```
 
**Key design decisions:**
- **DuckDB for joins, Polars for transformations, Parquet between steps,** pandas only at the model boundary. No Spark: it isn't needed at this size ([ADR-0001](docs/adr/0001-data-processing-stack.md)).
- **Every step is resumable** and logs its row counts with a `run_id`. A crash costs one step, not the pipeline.
- **No leakage:** market features use only earlier sales, splits are by time, and the test set is scored once.
- **Identifiers stay strings:** commune `01001` never becomes `1001`.
Full design: [`docs/architecture.md`](docs/architecture.md).
 
---
 
## ✅ Current Status: v0.1.0 (Part 1 Complete)
 
| Component | Status | Description |
|-----------|--------|-------------|
| DVF download | ✅ | 5 years of geo-DVF, resumable |
| DPE extraction | ✅ | ADEME remote DuckDB → local Parquet, 15.7M ratings in < 3 min within 5 GB |
| DVF cleaning | ✅ | One row per sale, 4.25M residential sales, lineage counts |
| DVF × DPE join | ✅ | Normalised addresses, surface and date windows, unique matches, rules as parameters |
| Features | ✅ | Leak-free rolling market prices with shrinkage, harmonised rating label |
| Model comparison | ✅ | Baseline, Ridge, random forest, LightGBM, XGBoost |
| Feature selection | ✅ | Permutation importance on validation |
| Final model | ✅ | LightGBM, refit on train + validation, tested once on 2025 |
| Logging | ✅ | Console + JSON lines, one `run_id` per execution |
| Documentation | ✅ | Architecture, 6 ADRs, data dictionary, lineage, model card, troubleshooting |
 
### 🔄 In progress: Part 2 (MLOps)
 
| Component | Status | Description |
|-----------|--------|-------------|
| DVC pipeline + `params.yaml` | ⬜ | Reproducible stages, versioned data |
| MLflow tracking + registry | ⬜ | Experiments, champion model |
| Tests + CI (GitHub Actions) | ⬜ | pytest, schema checks, ruff, pipeline on a sample |
| Drift detection | ⬜ | Weekly check on new ratings (Evidently) → retrain trigger |
| Serving | ⬜ | FastAPI `/predict` + Streamlit app |
| Model on Hugging Face Hub | ⬜ | Downloadable model + card |
| Docker + Terraform (AWS) | ⬜ | Validated locally with AWS Emulator |
 
---
 
## 📚 A Documented Learning Journey
 
This project is built to be reproducible and to teach, not just to work.
 
| Part | Concepts Introduced |
|------|-------------------|
| Part 1 | Out-of-core processing (DuckDB, Polars, Parquet), bucketed joins, record linkage without a shared key, data lineage, leak-free features, shrinkage, time-based validation, refit, gradient boosting, permutation importance |
| Part 2 | Pipelines (DVC), experiment tracking (MLflow), data drift, retraining with a human gate, model serving (FastAPI), CI/CD, containers, infrastructure as code |
 
| Doc | What it answers |
|---|---|
| [`docs/adr/`](docs/adr/) | Why each design decision was made, with references |
| [`docs/models.md`](docs/models.md) | How each model works, pros and cons, books and videos to learn more |
| [`docs/data-lineage.md`](docs/data-lineage.md) | Row counts at every step, raw → test |
| [`docs/data-dictionary.md`](docs/data-dictionary.md) | Every column kept, its source and meaning |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | Every error hit (20 so far): symptom → cause → fix |
| [`docs/build-journal.md`](docs/build-journal.md) | What was done, in order, and why |
| [`PLAYBOOK.md`](PLAYBOOK.md) | The reusable recipe: tabular big-data ML on one laptop |
 
This is not a tutorial. It is my record of how the project was built, including the wrong turns.
 
---
 
## 🗺️ Roadmap
 
### Part 1: The Model ✅ · `v0.1.0`
DVF + DPE extraction → validated join → leak-free features → model comparison → LightGBM tested on 2025
 
### Part 2: MLOps 🔄 · `v0.2.0`
DVC + MLflow → CI → drift detection on rating rule changes → automatic retraining → FastAPI + Streamlit → Docker + AWS IaC
 
### V1.1: Model Improvements ⬜
Relaxed match uniqueness → calibrated price ranges (quantile + conformal) → tuning → walk-forward validation
 
### V1.5: App Features ⬜
3D map view beside the price monitor → "why this price" explanations
 
### V2: Scale & Scope ⬜
Cloud cluster when the data justifies it (DVF since 2014, pre-2021 ratings) → renovation cost vs value gain
 
> See [`docs/roadmap.md`](docs/roadmap.md) for the full task-level breakdown.
 
---
 
## 🚀 Quick Start
 
### Prerequisites
 
- Python 3.11 and [uv](https://docs.astral.sh/uv/)
- About 15 GB of free disk space and an internet connection (the DPE base is queried remotely)
### 1. Clone and install
 
```bash
git clone https://github.com/rdmouhouadi/property-price-estimator.git
cd property-price-estimator
uv sync
```
 
### 2. Get and prepare the data
 
```bash
uv run python -m property_price.data.download_dvf
uv run python -m property_price.data.dpe_setup
uv run python -m property_price.data.extract_dpe a b
uv run python -m property_price.data.clean_dvf
uv run python -m property_price.data.join_dvf_dpe
```
 
### 3. Build features and train
 
```bash
uv run python -m property_price.features.build_features
uv run python -m property_price.models.models_comparison      # which model
uv run python -m property_price.models.importance             # which features
uv run python -m property_price.models.train_valid_model --features dpe
```
 
### 4. Final test (run once)
 
```bash
uv run python -m property_price.models.test_model
```
 
Every step is resumable: finished outputs are skipped on rerun. Logs go to the console and to `logs/pipeline.jsonl`.
 
---
 
## 🗂️ Project Structure
 
```
property-price-estimator/
├── src/property_price/
│   ├── data/                     # 🧱 Data engineering
│   │   ├── download_dvf.py       # geo-DVF per year, resumable
│   │   ├── dpe_setup.py          # attach ADEME's remote DuckDB
│   │   ├── extract_dpe.py        # stage A: columns → Parquet · stage B: bucketed join
│   │   ├── clean_dvf.py          # one row per sale + lineage
│   │   └── join_dvf_dpe.py       # address matching, rules as parameters
│   ├── features/
│   │   └── build_features.py     # leak-free market prices, time split
│   ├── models/
│   │   ├── dataset.py            # feature lists, loading
│   │   ├── metrics.py            # errors in € and %
│   │   ├── models_zoo.py         # every model: fn(train, valid, feats) → predictions
│   │   ├── models_comparison.py  # experiments A and B
│   │   ├── importance.py         # permutation importance
│   │   ├── train_valid_model.py  # early stopping → refit → artifacts
│   │   └── test_model.py         # final test, once
│   ├── monitoring/               # 🔄 drift detection (Part 2)
│   └── logging_config.py         # console + JSON lines, run_id
│
├── scripts/
│   └── dpe_inspect.py            # one-off schema exploration
│
├── reports/                      # schema dump, comparison, importance, test metrics
│
├── docs/
│   ├── adr/                      # 6 architecture decision records
│   ├── architecture.md
│   ├── data-dictionary.md
│   ├── data-lineage.md
│   ├── model-card.md
│   ├── models.md
│   ├── troubleshooting.md
│   ├── build-journal.md
│   └── roadmap.md
│
├── PLAYBOOK.md
├── pyproject.toml
└── uv.lock
```
 
`data/`, `artifacts/` and `logs/` are generated locally and git-ignored.
 
---
 
## 🙏 Prior Art & Acknowledgements
 
This project builds on public work that showed what is possible with these datasets:
 
- **[Valia](https://github.com/LucNIK/valia)**: a France-wide DVF estimator with calibrated ranges, rebuilt after each DVF release.
- **[Valeur verte des logements](https://www.data.gouv.fr/datasets/valeur-verte-des-logements-ecarts-de-prix-par-etiquette-dpe-610-000-ventes-dvf-x-ademe)** (France DPE): 610,000 DVF × DPE matched sales and price gaps by label. Its count is the independent check for this project's join.
- **VendreBien** and **Copilot Immo**: DVF × DPE analyses and estimators.
**Where this project diverges:**
- It treats the **energy-rating rule changes as a first-class problem**: harmonisation now, drift detection and retraining in part 2.
- The rating's effect is **measured on identical sales**, with selection effects stated.
- It is **fully documented and reproducible**, from raw files to the test score, with every decision and error recorded.
Data: **DVF géolocalisées** (DGFiP / Etalab) and **DPE Logements existants** (ADEME), both under Licence Ouverte. Per DVF's terms, no individual transaction is published or indexed.
 
---
 
## 📄 License
 
This project is licensed under the **MIT License**.
 
You are free to use, copy, modify and distribute this software, provided the copyright notice is kept.
 
See the [LICENSE](LICENSE) file for details.
 
---
 
## 🤝 Contributing
 
Contributions are welcome. Please open an issue before submitting a pull request so we can discuss the proposed change.
 
---
 
<div align="center">
<sub>Built with Python · DuckDB · Polars · LightGBM · scikit-learn · uv</sub>
</div>
 