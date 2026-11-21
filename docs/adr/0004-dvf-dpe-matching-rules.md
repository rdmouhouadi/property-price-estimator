# ADR-0004: DVF × DPE matching rules

- **Status:** accepted
- **Date:** 2026-11-21

## Context

DVF (sales) and DPE (energy ratings) share no identifier. To use the rating as a feature, and to measure its effect, each sale must be linked to the rating of the home sold. A wrong link adds noise to the very feature we want to measure.

## Decision

1. **Normalize addresses on both sides:**
   - upper case, accents and punctuation removed;
   - common abbreviations expanded (AV→AVENUE, BD→BOULEVARD, CHE→CHEMIN, IMP→IMPASSE, ST→SAINT, …);
   - house number as an integer.
2. **Candidates:** same commune code, house number, normalized street and property type. DPE address geocoding confidence `ban_score ≥ 0.5`.
3. **Rules applied to candidates:**
   - living area gap `|surface_dpe − surface_dvf| / surface_dvf ≤ 10%`;
   - DPE date between **365 days before** and **30 days after** the sale;
   - **unique both ways:** exactly one candidate per sale and one sale per DPE.
4. **Output keeps every DVF sale,** with DPE columns where matched and a `has_dpe` flag. One file serves the DVF-only and with-DPE models.

All thresholds are parameters at the top of `join_dvf_dpe.py`. Candidates are saved with their surface and date gaps (`data/interim/match_candidates/`), so variants are re-run without redoing the join.

## Results

| Step | Sales |
|---|---:|
| DVF sales | 4,245,617 |
| + same address and type | 2,226,768 |
| + surface within ±10% | 1,618,320 |
| + date window | 1,052,881 |
| = unique both ways | **604,773** |

**External validation:** the *Valeur verte* dataset (France DPE), built independently with near-identical rules, reports 610,000 matches. That's within 1%.

## Alternatives considered

- **Spatial matching** (DVF parcel coordinates vs DPE BAN coordinates): a useful fallback, but less precise for apartments in the same building.
- **Keeping the best candidate instead of requiring uniqueness:** recovers more matches (uniqueness costs 43% at the last step), at the risk of wrong links. Planned as a V1.1 experiment.
- **DPE strictly before the sale:** stricter against leakage. The +30-day tolerance follows prior art (paperwork delays). It's a planned ablation.

## Consequences

- Matched sales are ~14% of all sales (stable at 14–22% per year from 2022; near 0% in 2021, since the new DPE started in July 2021).
- Matched sales are **cleaner** than average (address and surface confirmed), so "with DPE" scores mix the rating's effect with selection. The clean effect is measured on identical rows (Experiment B, [model card](../model-card.md)).

## References

- France DPE, *Valeur verte des logements* (610,000 DVF × ADEME sales): https://www.data.gouv.fr/datasets/valeur-verte-des-logements-ecarts-de-prix-par-etiquette-dpe-610-000-ventes-dvf-x-ademe
- Base Adresse Nationale (BAN): https://adresse.data.gouv.fr/
