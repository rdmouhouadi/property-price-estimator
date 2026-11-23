# ADR-0008: Drift detector design, monitor the rule, not only its effects

- **Status:** accepted (detector, retrain loop, real-event backtest 23 Nov 2026) · proposed (frozen reference)
- **Date:** 2026-11-22

## Context

[ADR-0005](0005-dpe-coefficient-drift.md) planned a weekly drift check on new DPEs. The event to catch is known: the electricity coefficient drops from 1.9 to 1.7 on 1 January 2027. Only electric-heated homes are affected: their primary energy per m² drops ~10%, and their label improves only when they sit near a threshold.

The usual approach is a distribution test on the label (PSI, as in Evidently's presets). Before relying on it, we tested it against a **simulated** version of the change: recent real DPEs relabelled at 1.7.

## What the test showed

| Check | Value | Verdict |
|---|---:|---|
| Label PSI, all DPEs, real recent | 0.017 | stable ✅ (harmonisation works) |
| Label PSI, all DPEs, simulated 1.7 | 0.028 | stable ❌ (blind) |
| Label PSI, electric-heated only, simulated 1.7 | 0.033 | stable ❌ (A 4.1→6.3%, B 8.8→12.8%, still under 0.1) |
| Implied coefficient, real recent | 1.900 vs 1.905 | stable ✅ |
| Implied coefficient, simulated 1.7 | 1.70 (−10.75%) | **drift** ✅ |

The change is diluted: most homes aren't electric, and most electric ones don't cross a threshold. **A monitor that can't see the change it was built for gives false confidence.**

## Real-event backtest (23 Nov 2026)

`scripts/backtest_implied_coef.py` replays the detector on the real change of 1 January 2026 (2.3 → 1.9), electric-heated homes, by month.

| | Jul–Dec 2025 | Jan–Jun 2026 |
|---|---:|---:|
| Implied coefficient, **as issued** | 2.301–2.302 | 1.900–1.901 |
| Implied coefficient, **as published today** | 1.905 | 1.900–1.901 |
| Share of ratings whose printed label = published label | 53–55% | 100% |

- **The detector works on the real event:** a 17.4% drop against a 3% alert level, visible in the first month (~100,000 ratings).
- **ADEME restates history.** The main columns (`ep_conso_5_usages_m2`, `classe_bilan_dpe`) of older ratings now hold the values recalculated at 1.9. The values as issued are kept in `ancienne_*_pef` columns. Our first backtest, on the main columns, showed no step at all.
- **Consequence for monitoring:** a reference recomputed from the current snapshot moves with a restatement, and the detector goes blind. **The reference must be frozen:** computed once from the snapshot used for training, saved (e.g. `reports/drift_reference.json`, committed), and compared against on every run.
- **Consequence for serving:** about 46% of electric-heated homes rated in H2 2025 hold a certificate whose label is worse than the published one the model learned. The app should ask for the rating date and re-label pre-2026 electric ratings with `dpe_rules`.

## Decision

- **Primary detector, on the cause:** the *implied coefficient*, median(primary ÷ final energy) over recent electric-heated DPEs. Alert when it moves more than 3% from the reference. It reacts on the first ratings issued under a new rule.
- **Secondary detectors, on the effects:** PSI on labels, for all DPEs and for the electric-heated segment (thresholds 0.1 / 0.2). Kept for unknown changes, with their limits known.
- **PSI written by hand**, not Evidently: ten lines, transparent, no API churn.
- **Shared rules module** (`dpe_rules.py`): thresholds and `harmonised_sql(coef, elec_ids)` are used by both features and drift, so training and monitoring apply the same rule.
- **Retrain loop** (`retrain_on_drift.py`): implied-coefficient drift → new coefficient written into `params.yaml` (rounded to 0.1) → `dvc repro test` → promotion gate ([ADR-0007](0007-pipeline-and-tracking.md)). A person reviews the `params.yaml` / `dvc.lock` diff and commits.
- **Report:** `reports/drift.json` (machine-readable, `drift_detected` counts real checks only) and `reports/drift.html`.

## Alternatives considered

- **Evidently presets:** good defaults, but the same PSI blindness here, plus a heavier dependency.
- **Watching `dpe_version` in ADEME's data:** direct, but depends on ADEME updating the version field on time. Worth adding as a third signal.
- **Monitoring model error on new sales:** the ground truth (DVF) arrives 6–12 months late. Too slow for a dated rule change.

## Consequences

- Lesson for the PLAYBOOK: **test every monitor against a simulated version of the drift before trusting it**, and **monitor the cause (the rule), not only downstream effects**.
- Caveat: on simulated data, the implied coefficient moves partly by construction. The real 2.3 → 1.9 change of January 2026 confirms it on real data (see above).
- Lesson for the PLAYBOOK: **never assume a source keeps its history as it was.** Check whether old records are restated, and freeze monitoring references.
- The approximation (no small-surface rule, mixed energies scaled on total primary energy) is stated in the model card.

## References

- Siddiqi, N. (2006), *Credit Risk Scorecards*, Wiley (origin of PSI and its 0.1 / 0.2 thresholds)
- Chip Huyen (2022), *Designing Machine Learning Systems*, ch. 8, *Data Distribution Shifts and Monitoring*
- Evidently AI docs: https://docs.evidentlyai.com/
- Rabanser, Günnemann, Lipton (2019), *Failing Loudly: An Empirical Study of Methods for Detecting Dataset Shift*, NeurIPS: https://arxiv.org/abs/1810.11953
