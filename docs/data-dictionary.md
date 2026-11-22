# Data dictionary

Columns of the two processed datasets. All identifiers are **strings** (see [ADR-0001](adr/0001-data-processing-stack.md)).

## `data/processed/sales_enriched.parquet`: one row per residential sale

### From DVF (`dvf_sales.parquet`)

| Column | Type | Source | Meaning |
|---|---|---|---|
| `id_mutation` | str | DVF `id_mutation` | sale identifier |
| `date` | date | `date_mutation` | date of sale |
| `valeur` | float | `valeur_fonciere` | sale price (€), per sale, never summed across rows |
| `prix_m2` | float | derived | `valeur / surface_bati` |
| `type_bien` | str | `type_local` | `Maison` (house) or `Appartement` (apartment) |
| `surface_bati` | float | `surface_reelle_bati` | living area of the dwelling (m²) |
| `pieces` | float | `nombre_pieces_principales` | main rooms |
| `surface_carrez` | float | `lot1_surface_carrez` | Carrez area of the first lot (apartments) |
| `surface_terrain` | float | `surface_terrain` | land area, each parcel counted once per sale (m²), 0 if none |
| `n_dependances` | int | derived | number of outbuildings (garages, cellars, parking) in the sale |
| `adresse_numero`, `adresse_suffixe`, `adresse_nom_voie` | str | DVF | address of the dwelling row |
| `code_postal`, `code_commune`, `nom_commune`, `code_departement` | str | DVF | location codes (INSEE commune code, `2A`/`2B` for Corsica) |
| `id_parcelle` | str | DVF | cadastral parcel; first 10 characters = cadastral section |
| `lat`, `lon` | float | geo-DVF | parcel centroid (WGS-84) |

### From DPE (null when `has_dpe` is false)

| Column | Type | Source (ADEME table.column) | Meaning |
|---|---|---|---|
| `has_dpe` | bool | derived | a unique DPE match was found ([ADR-0004](adr/0004-dvf-dpe-matching-rules.md)) |
| `dpe_age_days` | int | derived | days between DPE and sale (>0 = DPE before sale) |
| `date_dpe` | date | `dpe_administratif.date_etablissement_dpe` | date of the diagnosis |
| `dpe_version` | str | `dpe_administratif.enum_version_id` | method version (2.6 = electricity coefficient 1.9) |
| `classe_dpe` | str A–G | `dpe_ep_conso.classe_bilan_dpe` | energy label as issued |
| `classe_dpe_pef19` | str A–G | `dpe_ep_conso.nouvelle_classe_bilan_dpe_pef` | label recalculated under coefficient 1.9 |
| `classe_ges` | str A–G | `dpe_emission_ges.classe_emission_ges` | CO₂ (GES) label |
| `ep_m2`, `ep_m2_pef19` | float | `dpe_ep_conso` | primary energy use per m² per year (as issued / under 1.9) |
| `ef_m2` | float | `dpe_ef_conso.conso_5_usages_m2` | final energy use per m² per year |
| `ges_m2` | float | `dpe_emission_ges.emission_ges_5_usages_m2` | CO₂ emissions per m² per year |
| `energie_id` | int | `dpe.enum_type_energie_chauffage_principal_id` | main heating energy (see `dpe_enum_type_energie`) |
| `annee_construction` | int | `dpe_caracteristique_generale` | construction year |
| `periode_id` | int | `…enum_periode_construction_id` | construction period: 1 = before 1948, 2 = 1948–1974, … 10 = after 2021 |
| `nb_niveaux` | float | `…nombre_niveau_logement` | number of levels of the dwelling |
| `etage` | int | `dpe_t_adresse.compl_etage_appartement` | floor (apartments) |
| `dpe_genere_immeuble` | bool | derived from method id | apartment DPE generated from a whole-building DPE |
| `surface_dpe` | float | `…surface_habitable_logement` | living area in the DPE (m²) |

## `data/processed/features.parquet`: model input

| Column | Meaning | Used in final model |
|---|---|---|
| `y` | target: ln(price per m²) | target |
| `type_bien`, `code_departement` | categorical | ✓ |
| `surface_bati`, `pieces`, `surface_terrain`, `n_dependances`, `lat`, `lon` | property and location | ✓ |
| `mkt_section_12m` | mean y, same type, same cadastral section, previous 365 days (excluding the sale day), shrunk toward commune | ✓ |
| `mkt_commune_12m` | same at commune level, shrunk toward département | ✓ |
| `mkt_dept_12m` | same at département level | ✓ |
| `mkt_section_n`, `mkt_commune_n` | number of past sales behind those averages | ✓ |
| `dpe_class`, `ges_class` | label as ordinal 1 (A) … 7 (G); DPE class harmonised under `params.yaml` → `dpe_rules.elec_coefficient` (1.9 today) by `dpe_rules.harmonised_sql` | ✓ |
| `dpe_ep_m2` | energy use per m², harmonised under the same coefficient | ✓ |
| `dpe_periode`, `annee_construction`, `dpe_energie`, `etage`, `nb_niveaux` | from DPE | ✓ |
| `t_months`, `month` | time index, month of year | ✗ dropped (no importance) |
| `dpe_genere_immeuble` | see above | ✗ dropped (no importance) |
| `split` | `train` < 2024-07-01 ≤ `valid` < 2025-01-01 ≤ `test` | – |

Shrinkage: `(n · child_mean + 20 · parent_mean) / (n + 20)`, falling back to the parent level when the child has no past sales.
