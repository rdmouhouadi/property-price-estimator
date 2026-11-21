# Property price estimator (France): DVF × DPE

Estimate the sale price of a French house or apartment from public data, and measure what its energy rating (DPE) is worth.

- **4.2M** residential sales (DVF, 2021–2025) joined with **15.7M** energy ratings (ADEME DPE), on one laptop.
- **604,773** sales matched to their rating, within 1% of an independent count (610k).
- **LightGBM** on 21 features. **Final test on 2025** (never seen in training): median error **16.0%**, **59.5%** of estimates within 20% of the real price.
- On identical sales, adding the energy rating cuts the median error by **13%**.

> Status: **V1, ML part done** (Saturday). MLOps (pipeline automation, drift detection, retraining, API, app) comes in part 2. See [roadmap](docs/roadmap.md).

Write-up: [What is a home's energy rating worth?](https://rdmouhouadi.github.io/) *(link to the case-study page)*

---

## Results

| Test set: 2025, 790,767 sales | Median error | Within 10% | Within 20% | Mean error |
|---|---:|---:|---:|---:|
| All sales | 16.0% | 33.2% | 59.5% | €48,945 |
| Apartments | 13.6% | 38.1% | 66.9% | €38,973 |
| Houses | 18.2% | 29.4% | 53.8% | €56,675 |
| With a matched DPE | 11.9% | 43.1% | 72.6% | €39,805 |
| Without a matched DPE | 17.2% | 30.9% | 56.4% | €51,129 |

Median error = median of |estimate − price| / price. Details and limits: [model card](docs/model-card.md).

## Pipeline

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

Full design: [architecture](docs/architecture.md).

## Quick start

Requires Python 3.11 and [uv](https://docs.astral.sh/uv/). About 15 GB of free disk space.

```sh
git clone https://github.com/rdmouhouadi/property-price-estimator.git
cd property-price-estimator
uv sync

# data
uv run python -m property_price.data.download_dvf
uv run python -m property_price.data.dpe_setup
uv run python -m property_price.data.extract_dpe a b
uv run python -m property_price.data.clean_dvf
uv run python -m property_price.data.join_dvf_dpe

# features and models
uv run python -m property_price.features.build_features
uv run python -m property_price.models.models_comparison
uv run python -m property_price.models.importance
uv run python -m property_price.models.train_valid_model --features dpe
uv run python -m property_price.models.test_model   # run once
```

Every step is resumable: finished outputs are skipped on rerun.

## Repository layout

```sh
src/property_price/
├── data/          # download, extract, clean, join
├── features/      # leak-free market features + time split
├── models/        # dataset, metrics, models_zoo, comparison, importance, train, test
├── monitoring/    # (part 2) drift detection
└── logging_config.py
scripts/           # one-off exploration (dpe_inspect.py)
reports/           # schema dump, comparison, importance, test metrics
docs/              # architecture, ADRs, data docs, model card, journal
```

`data/`, `artifacts/` and `logs/` are git-ignored.

## Documentation

| Doc | What it answers |
|---|---|
| [Architecture](docs/architecture.md) | How the pieces fit, V1 and planned MLOps |
| [ADRs](docs/adr/) | Why each design decision was made, with references |
| [Data dictionary](docs/data-dictionary.md) | Every column kept, its source and meaning |
| [Data lineage](docs/data-lineage.md) | Row counts at every step, raw → test |
| [Model card](docs/model-card.md) | Intended use, metrics, limits, risks |
| [Models](docs/models.md) | How each model works, pros/cons, where to learn more |
| [Troubleshooting](docs/troubleshooting.md) | Every error hit during the build: symptom → cause → fix |
| [Build journal](docs/build-journal.md) | What was done, in order, and why |
| [Roadmap](docs/roadmap.md) | V1.1, part 2 (MLOps), V2 |
| [PLAYBOOK](PLAYBOOK.md) | The reusable recipe distilled from this project |

## Data sources and licence

- **DVF géolocalisées** (DGFiP / Etalab), [data.gouv.fr](https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees), Licence Ouverte. Per its terms, this project does not publish individual transactions or let search engines index them.
- **DPE Logements existants (depuis juillet 2021)** (ADEME), [data.gouv.fr](https://www.data.gouv.fr/datasets/dpe-logements-existants-depuis-juillet-2021/), Licence Ouverte.

Code licence: *(choose one, e.g. MIT, and add a LICENSE file)*.
