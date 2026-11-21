# Model card: French property price estimator (V1)

## Overview

| | |
|---|---|
| **Task** | estimate the sale price of a house or apartment in France |
| **Model** | LightGBM regressor, 2,646 trees |
| **Target** | ln(price per m²); price = exp(prediction) × living area |
| **Features** | 21: property, location, past local market prices, optional energy-rating (DPE) features |
| **Training data** | 3,454,850 sales, 2021–2024 (DVF), 14% with a matched DPE |
| **Version** | run `8056d1ba`, trained 2026-11-21 |
| **Files** | `artifacts/model.txt` (LightGBM text format), `artifacts/metadata.json` |

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

## Risks and drift

- **DPE rule changes:** the electricity coefficient went from 2.3 to 1.9 on 1 Jan 2026 and goes to 1.7 on 1 Jan 2027. Training labels are harmonised under 1.9. Labels issued from 2027 will not mean the same thing until the model is retrained ([ADR-0005](adr/0005-dpe-coefficient-drift.md)). Monitoring and retraining: part 2.
- **Market shifts:** prices move. Market features use the previous 12 months, and the model should be retrained after each DVF release (April / October).

## Ethical and legal notes

- Data: public open data (Licence Ouverte). DVF terms forbid letting search engines index individual transactions, so the app shows no individual sales and sets `noindex`.
- No personal data is used as a feature.

## References

[Data lineage](data-lineage.md) · [Data dictionary](data-dictionary.md) · [ADRs](adr/) · [Models](models.md)
