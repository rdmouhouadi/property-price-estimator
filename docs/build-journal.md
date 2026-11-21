# Build journal

What was done, in order, and why. Links point to the decisions (ADRs) and the problems hit ([troubleshooting](troubleshooting.md)).

## Saturday 21 Nov 2026: the ML part

**1. Choose the problem.** The brief: tabular, big or semi-big, simple, and **useful to real people**, with a model people can download. A first idea, energy-consumption forecasting from smart meters, was dropped, because users don't have the input data. A property price estimator works: anyone knows their commune, surface and rooms. Prior art checked: Valia (DVF estimator), the *Valeur verte* dataset (DVF × DPE), VendreBien, Copilot Immo. The estimator itself exists. The angle no one covers: **detecting DPE rule changes and retraining automatically** ([ADR-0005](adr/0005-dpe-coefficient-drift.md)).

**2. Set up.**
- Repo scaffold, uv environment with a bounded Python range, data stack Polars/DuckDB/pyarrow, ML stack scikit-learn/LightGBM/XGBoost/Optuna/Plotly ([ADR-0001](adr/0001-data-processing-stack.md)).
- `data/` git-ignored. Conventional Commits.
- Issues: #1–#5.

**3. Download DVF.** `download_dvf.py` gets geo-DVF `full.csv.gz` per year, 2021–2025, resumable (#6).

**4. Find the DPE data.** No full CSV (#7). Found ADEME's remote DuckDB: `dpe_setup.py` attaches it, and `scripts/dpe_inspect.py` dumped schema, enums and row counts to `reports/dpe_schema.txt`. That mapped the table links and property-type codes ([ADR-0003](adr/0003-dpe-source-remote-duckdb.md)).
- **Discovery:** ADEME already publishes labels recalculated under the new electricity coefficient, which gives the harmonisation step for free.

**5. Extract DPE.** The first single-query attempt ran out of memory (#9, #10). The rewrite:
- stage A pulls the needed columns per table to local Parquet;
- stage B joins locally in 8 hash buckets;
- result: 15,672,018 DPEs in under 3 minutes within 5 GB.

**6. Explore DVF.** Type inference broke on `14A` (#11), so DVF is read all-as-strings. Cleaning rules set: ordinary sales only, one row per sale, exactly one dwelling, outbuildings counted, price never summed. First commit.

**7. Clean DVF.** `clean_dvf.py`:
- DuckDB converts csv.gz → Parquet, with explicit quoting (#13);
- Polars rebuilds one row per sale, applies the filters and prints lineage counts;
- result: 4,245,617 sales. Medians match the known market levels.

**8. Join DVF × DPE.** `join_dvf_dpe.py`:
- normalized addresses, candidates saved with surface and date gaps, rules as parameters;
- result: **604,773** unique matches, vs 610,000 in the independent Valeur verte dataset ([ADR-0004](adr/0004-dvf-dpe-matching-rules.md)).

**9. Restructure.** The data stage is done, so the scripts moved into the `src/property_price/{data,features,models,monitoring}` package (hatchling build, run with `python -m`), and exploration scripts moved to `scripts/`.

**10. Build features.** `build_features.py`:
- target ln(price/m²);
- leak-free 12-month rolling market prices by cadastral section, commune and département, with shrinkage;
- harmonised DPE class as an ordinal;
- time split: train < Jul 2024, valid H2 2024, test 2025.
- Check: section correlation 0.839 > commune 0.824 > département 0.739.

**11. Logging.** A shared `logging_config.py`: console + JSON lines, `run_id`, `log_metric` ([ADR-0006](adr/0006-logging.md)).

**12. Compare models.** The single script was refactored into `dataset.py`, `metrics.py`, `models_zoo.py` (every model is `fn(train, valid, feats) -> predictions`), `models_comparison.py` and `importance.py`.
- **Experiment A:** LightGBM best (17.5%), tied with XGBoost, faster.
- **Experiment B:** the DPE cuts the median error by 13% on identical rows.
- Issues: #14–#17.

**13. Select features.** Permutation importance: the neighbourhood market price dominates, and the construction period is the top DPE feature. Dropped `t_months` (trees can't extrapolate time), `month` and `dpe_genere_immeuble`.

**14. Train the final model.** `train_valid_model.py`:
- fit on train with early stopping on validation → 2,646 trees, validation 16.3%;
- refit on train + validation (the refit / final fit);
- saved to `artifacts/`.
- Issues: #18–#20.

**15. Test once.** `test_model.py` on 2025: **median error 16.0%, 59.5% within 20%**, apartments 13.6%, houses 18.2%. Test ≈ validation, so no overfitting.

**16. Write-up.** Portfolio case study, part 1: *What is a home's energy rating worth?*

**17. Docs and GitHub repo.** README, architecture, 6 ADRs, data dictionary, lineage, model card, models, troubleshooting, this journal, roadmap, PLAYBOOK.

## Sunday 22 Nov 2026: the MLOps part

*(to be written)*
