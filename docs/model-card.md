# Model card: French property price estimator (V1)

## Overview

| | |
|---|---|
| **Task** | estimate the sale price of a house or apartment in France |
| **Model** | LightGBM regressor, 2,646 trees |
| **Target** | ln(price per m²); price = exp(prediction) × living area |
| **Features** | 21: property, location, past local market prices, optional energy-rating (DPE) features |
| **Training data** | 3,454,850 sales, 2021–2024 (DVF), 14% with a matched DPE |
| **Version** | registered model `property-price-estimator` **v1**, alias `champion` (MLflow); first trained 2026-11-21, run `8056d1ba` |
| **Files** | `artifacts/model.txt` (LightGBM text format), `artifacts/metadata.json` (features, settings, MLflow run ID, model version) |
| **Serving** | FastAPI `POST /estimate` + Streamlit app ([ADR-0009](adr/0009-serving.md)) |

## Intended use

- A **first estimate** for owners, buyers and the curious, with an error range, before talking to a professional.
- Comparing a property with and without a better energy label, **as an association learned from local sales**.

## Not intended for

- Mortgage, tax, legal or insurance decisions.
- Properties outside the training scope: Alsace, Moselle and Mayotte (absent from DVF), new builds sold off-plan, commercial premises, multi-dwelling sales.
- Claiming that renovating *causes* a given price gain.

## Performance

**Test set: 2025, 790,767 sales, scored once.**

| Segment | Median error | Within 10% | Within 20% | Mean error |
|---|---:|---:|---:|---:|
| All sales | 16.0% | 33.2% | 59.5% | €48,945 |
| Apartments | 13.6% | 38.1% | 66.9% | €38,973 |
| Houses | 18.2% | 29.4% | 53.8% | €56,675 |
| With a matched DPE | 11.9% | 43.1% | 72.6% | €39,805 |
| Without a matched DPE | 17.2% | 30.9% | 56.4% | €51,129 |

Validation (H2 2024): median error 16.3%, within 20% 58.4%. Test ≈ validation, so there's no sign of overfitting.

**Effect of the DPE, measured cleanly** (Experiment B: same model, same 73,344 validation sales): median error 14.3% → 12.5% (−13%), within 20% 65.2% → 71.3%.

## How it was evaluated

- Split by time: train < July 2024, validate H2 2024, test 2025.
- Model and features chosen on validation only. Refit on train + validation with the number of trees found by early stopping. Test scored once.
- Five approaches compared ([models](models.md), `reports/model_comparison.csv`). LightGBM was chosen: tied with XGBoost on accuracy, and 2.5× faster.

## Limitations

- **Missing information:** DVF records no condition, view, renovation, or floor for houses. Part of every price is out of reach, which is why houses score worse.
- **Selection:** matched sales are cleaner than average (address and surface confirmed). The "with DPE" segment's better score is partly selection.
- **Validation slightly optimistic:** the validation set was also used for early stopping.
- **Coverage:** 14% of training sales have a DPE. The rating features are empty for the rest.
- **Rare areas:** sections or communes with few past sales fall back to commune or département prices, so estimates there are coarser.

## How estimates are served

- The user gives an address. IGN geocoding gives the commune and coordinates; the cadastre gives the parcel and its cadastral section.
- The latest 12-month market prices come from a snapshot rebuilt by the pipeline, with the same shrinkage as training.
- The **range shown is ± the test median error for the property type** (13.6% apartments, 18.2% houses). It is a typical error, not a calibrated interval: about half of real prices fall outside it.
- **"What is my energy rating worth?"** re-scores the same home with each label A–G (energy figure cleared). It's an association learned from local sales, not a renovation promise.

### Observations from the app

- Same 50 m² apartment, label D: **10 rue de Rivoli, Paris 4e → €587,000 (€11,750/m²), G → A +4%**; **Le Pecq (78) → €206,000 (€4,127/m²), G → A +13%**. The green value is larger where location weighs less in the price.
- **Pre-2026 certificates (electric heating):** ADEME restated older ratings at the 1.9 coefficient, and the model learned the restated labels. About 46% of electric-heated homes rated in H2 2025 hold a certificate with a worse label than the published one. Users entering such a label get an estimate biased slightly low. Not yet corrected in the app (planned: ask for the rating date and re-label).
- In central Paris, A and B give the same estimate (a plateau): few A/B sales there, so the trees don't split between them. Read differences between neighbouring labels as rough.

## Risks and drift

- **DPE rule changes:** the electricity coefficient went from 2.3 to 1.9 on 1 Jan 2026 and goes to 1.7 on 1 Jan 2027. Training labels are harmonised under 1.9. Labels issued from 2027 will not mean the same thing until the model is retrained ([ADR-0005](adr/0005-dpe-coefficient-drift.md)).
- **Monitoring** ([ADR-0008](adr/0008-drift-detector-design.md)): the primary detector is the implied coefficient (median primary ÷ final energy for electric-heated homes, alert at ±3%). Replayed on the real January 2026 change, it drops from 2.30 to 1.90 (−17%) in the first month. The reference must be frozen, because ADEME restates history. Label PSI, overall and for electric homes, is a secondary check: in a simulation of the 2027 change it stayed under its alert threshold.
- **Retraining:** a drift alert writes the new coefficient into `params.yaml` and reruns the pipeline. Re-labelling is approximate: electric-heated homes are re-scored with 2021 thresholds (energy and emissions, worst of both), without the small-surface rule, and mixed-energy homes are scaled on total primary energy.
- **Demo at 1.7 (simulated):** retrained model v2 scored 15.94% median error vs 15.96%. It was promoted, then reverted (tagged `simulated`). The promotion gate compares scores computed on different features and has no margin, so this difference is noise. Fix planned (V1.1).
- **Market shifts:** prices move. Market features use the previous 12 months, and the model should be retrained after each DVF release (April / October).

## Ethical and legal notes

- Data: public open data (Licence Ouverte). DVF terms forbid letting search engines index individual transactions, so the app shows no individual sales and sets `noindex`.
- No personal data is used as a feature.

## References

[Data lineage](data-lineage.md) · [Data dictionary](data-dictionary.md) · [ADRs](adr/) · [Models](models.md)
