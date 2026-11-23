# ADR-0005: DPE coefficient changes, harmonise the label and monitor drift

- **Status:** accepted (harmonisation, V1) · accepted with changes (monitoring and retraining, built 22 Nov 2026: see [ADR-0008](0008-drift-detector-design.md))
- **Date:** 2026-11-21

## Context

The DPE label depends on a conversion coefficient for electricity (final → primary energy). It keeps changing:

| Period | Coefficient |
|---|---|
| until 31 Dec 2025 | 2.3 |
| from 1 Jan 2026 | 1.9 |
| from 1 Jan 2027 | 1.7 |

The same home can get a better label with no work done. A model trained on old labels then receives new ones: this is a **known, dated regime change** (concept drift on one feature).

## Decision

### V1: harmonise the training labels

- Use ADEME's recalculated values under 1.9: `coalesce(nouvelle_classe_bilan_dpe_pef, classe_bilan_dpe)` and `coalesce(nouvelle_ep_conso_5_usages_m2_pef, ep_conso_5_usages_m2)`. Every training label then follows one rule.
- Keep `dpe_version` (2.6 = the 1.9 coefficient) to tell which rule produced a rating.

### Part 2: detect and retrain

- **Weekly:** pull new DPEs and compare them with the training reference: class distribution (especially for electric heating), energy use per m², heating mix. An Evidently report runs, and if drift is found, a retrain is triggered.
- **Harmonise step in the pipeline:** recompute labels under the current coefficient from consumption and heating-energy fields. The coefficient lives in `params.yaml`. It's approximate, because the label also depends on the CO₂ threshold; this is stated in the model card.
- **Twice a year:** on each DVF release, check accuracy on the newest sales.
- **Human gate:** promote only if the challenger beats the champion on the newest sales.
- **Demo before January 2027:** recompute a sample of recent labels at 1.7, feed them in as "new data", and show the drift alert → retrain → evaluation loop.

## As built (22 Nov 2026)

- The coefficient lives in `params.yaml` (`dpe_rules.elec_coefficient`) and the harmonise step is `dpe_rules.harmonised_sql`, used by features and drift.
- The weekly Evidently check was replaced: label PSI turned out blind to the 2027 change. The primary detector is the implied coefficient ([ADR-0008](0008-drift-detector-design.md)).
- The 1.7 demo ran end to end: drift → retrain → gate. The gate needs a fairer comparison ([ADR-0007](0007-pipeline-and-tracking.md)).

## Consequences

- The training data is consistent today, without our own recalculation.
- The 2027 change is a real event the monitoring should catch live. That's the core of the MLOps write-up.

## References

- Ministère de l'Économie (2025), *Un nouveau DPE au 1er janvier 2026 pour favoriser le chauffage électrique*: https://www.economie.gouv.fr/actualites/un-nouveau-dpe-au-1er-janvier-2026-pour-favoriser-le-chauffage-electrique
- Ministère de la Transition écologique (2026), *Arrêté abaissant le facteur de conversion de l'électricité à 1,7 au 1er janvier 2027*: https://www.ecologie.gouv.fr/presse/dpe-audits-energetiques-publication-larrete-abaissant-facteur-conversion-lelectricite-17-1er
- Evidently AI docs: https://docs.evidentlyai.com/
