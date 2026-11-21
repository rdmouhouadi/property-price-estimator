# Data lineage

Row counts at every step, from raw files to the test set. Run of 21 Nov 2026.

## DPE (ADEME)

| Step | Rows | Notes |
|---|---:|---|
| Remote `dpe` table | 20,200,182 | all DPEs since July 2021, including old-method, replaced, buildings, new builds |
| Kept: new method, active, not replaced, dated ≥ 2021-07-01, house or apartment | **15,672,018** | one row per DPE (`rows = distinct_dpe`) |
| … without an address | 3.2% | |
| … without a class | 0% | |

Labels: apartments A 103k · B 544k · C 4.54M · D 3.32M · E 1.59M · F 510k · G 253k. Houses A 170k · B 266k · C 1.22M · D 1.52M · E 883k · F 461k · G 300k.

Timing: stage A (8 tables → local Parquet) about 1m45; stage B (bucketed join) about 1 min; memory limit 5 GB.

## DVF (2021–2025)

Raw scale: about 3.5M rows per year (2024: 3,499,931 rows × 40 columns), several rows per sale.

| Step | Sales |
|---|---:|
| Sales (`Vente`), all property types | 6,803,387 |
| … containing a dwelling | 4,732,172 |
| … exactly one dwelling | 4,461,989 |
| … no commercial premises | 4,371,869 |
| … single consistent price | 4,371,869 (guard: removes 0 today) |
| … price 15k–10M € | 4,334,007 |
| … living area 9–1000 m² | 4,332,126 |
| … price/m² within P1–P99 of département × type | **4,245,617** |

Excluded by design: off-plan sales (VEFA), exchanges, auctions, building land, expropriations.

| Year | Apartments | median €/m² | Houses | median €/m² |
|---|---:|---:|---:|---:|
| 2021 | 423,465 | 3,118 | 592,968 | 2,041 |
| 2022 | 426,251 | 3,326 | 546,345 | 2,199 |
| 2023 | 340,575 | 3,333 | 427,415 | 2,180 |
| 2024 | 301,696 | 3,239 | 396,135 | 2,118 |
| 2025 | 345,310 | 3,325 | 445,457 | 2,168 |

## DVF × DPE join

| Step | Sales |
|---|---:|
| DVF sales | 4,245,617 |
| same address and type | 2,226,768 |
| surface within ±10% | 1,618,320 |
| DPE dated −365 / +30 days | 1,052,881 |
| unique both ways | **604,773** (independent count: 610,000) |

Match rate by year: apartments 2.0% · 17.2% · 21.6% · 21.7% · 22.1%; houses 1.2% · 14.4% · 18.0% · 17.3% · 17.1% (2021 → 2025).

## Features and splits

| Split | Period | Sales | with DPE |
|---|---|---:|---:|
| train | 2021-01-01 → 2024-06-30 | 3,068,036 | 12.4% |
| valid | 2024-07-01 → 2024-12-31 | 386,814 | 19.0% |
| test | 2025-01-01 → 2025-12-31 | 790,767 | 19.3% |

Correlation with the target (train): `mkt_section_12m` 0.839 · `mkt_commune_12m` 0.824 · `mkt_dept_12m` 0.739.

## Models

| Artifact | Rows | Period |
|---|---:|---|
| Final model (refit on train + valid) | 3,454,850 | 2021-01-01 → 2024-12-31 |
| Test evaluation (once) | 790,767 | 2025 |
