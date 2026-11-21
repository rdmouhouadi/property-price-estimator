# PLAYBOOK: tabular "big data" ML on one laptop

A reusable recipe, distilled from this project. Generic steps and rules, without the dead ends (those are in [docs/build-journal.md](docs/build-journal.md) and [docs/troubleshooting.md](docs/troubleshooting.md)).

*Part 2 (MLOps: pipeline, drift, retraining, serving) will be added after it's built.*

---

## 1. Choose the problem

- [ ] **Usable by a real person:** every input must be something the user knows or the system can look up. No "predict X from data nobody has".
- [ ] **Data is public, large enough to matter, and refreshed** (a refresh gives the MLOps story).
- [ ] **Check prior art** before building. Position on what's missing, not on what exists.
- [ ] **Find a dated event that will change the data** (a rule change, a new release). It makes monitoring concrete.

## 2. Set up

- [ ] Standalone **uv**. Never install it into a Store or system Python.
- [ ] `uv init`, then **bound `requires-python`** (e.g. `>=3.11,<3.13`) before adding packages.
- [ ] Folders: `src/<package>/{data,features,models,monitoring}`, `scripts/` for one-offs, `data/{raw,interim,processed}`, `reports/`, `docs/adr/`.
- [ ] `.gitignore`: `data/`, `artifacts/`, `logs/`, `.venv/`.
- [ ] VS Code: select the project interpreter, **enable Auto Save**.
- [ ] Shared logging module from day one (console + JSON lines + `run_id`).
- [ ] Conventional Commits (`feat(data): …`, `fix(models): …`). Commit before every long run.
- [ ] On Windows PowerShell: write files with `Out-File -Encoding utf8` / `Add-Content`, never `>`.

## 3. Get the data

- [ ] Download scripts are **resumable** (write to `.part`, rename at the end, skip existing).
- [ ] If the provider offers SQL/DuckDB/Parquet access, **prefer it over CSV dumps**. You can prune columns at the source.
- [ ] Dump the **schema, enums and row counts** of a relational source to `reports/` before writing any join.

## 4. Read raw data safely

- [ ] **Never trust type inference on big files.** Read everything as strings, then cast only what you need.
- [ ] **Identifiers stay strings:** postcodes, administrative codes, parcel and lot IDs.
- [ ] **Declare CSV dialect explicitly:** delimiter, quote, escape. Never use `ignore_errors` (it drops real rows silently).
- [ ] Convert raw CSV to **Parquet** once. Every later step reads Parquet.

## 5. Process big data on one machine

- [ ] **Joins in SQL (DuckDB), transformations in Polars,** pandas only at the model boundary.
- [ ] Set DuckDB `memory_limit` (~50–60% RAM), `temp_directory`, `threads`, `preserve_insertion_order=false`.
- [ ] Big joins: **materialize the needed columns locally first, then join in hash buckets** (`hash(key) % N = k`). Memory stays flat as data grows.
- [ ] Every step **prints or logs its row counts.** That's your lineage table.
- [ ] Add guard checks even when they remove 0 rows today.
- [ ] Sanity-check results against known facts (market levels, trends).

## 6. Join datasets without a shared key

- [ ] Normalize both sides the same way (case, accents, punctuation, abbreviations, numbers).
- [ ] Save **candidate pairs with their gaps** (surface, date, …), then apply rules as **parameters**. Variants then don't require redoing the join.
- [ ] Require **uniqueness both ways** for precision. Measure what it costs.
- [ ] Print the **match funnel.**
- [ ] **Validate against an independent count** if one exists.
- [ ] Keep all rows of the main table with a `has_x` flag, rather than an inner join.

## 7. Features

- [ ] Every feature must be **computable at prediction time**.
- [ ] Aggregates over past data use **only earlier rows** (window ending the day before). No leakage.
- [ ] Hierarchical averages (fine → coarse) with **shrinkage** for small groups.
- [ ] Check that finer levels correlate better with the target. If not, fix the shrinkage.
- [ ] Harmonise labels whose definition changed over time.

## 8. Evaluation protocol

- [ ] **Split by time** for anything that will predict the future: train (past), validation (recent), test (latest).
- [ ] **A naive baseline** first. Every model must beat it.
- [ ] Compare models on validation with **metrics users understand** (e.g. median % error, % within X%), plus one technical metric.
- [ ] Quick mode (subsample) for exploration, full data for final runs.
- [ ] To measure a feature group's value: **same model, same rows, with vs without.** Never compare across different subsets.
- [ ] **Feature selection:** permutation importance on validation. Drop features with importance ≈0 or < ~2× std. Beware correlated features.
- [ ] Trees **can't extrapolate**. A raw time index is useless for future dates; carry trends through rolling features.
- [ ] **Refit (final fit):** after choosing on validation, retrain on train + validation with the chosen settings (e.g. best number of trees from early stopping).
- [ ] **Test once.** Run it again after changing something, and the test set becomes a second validation set.
- [ ] Optional robustness: walk-forward (expanding window) validation.
- [ ] Training error is not an evaluation. The train-vs-validation gap detects overfitting.
- [ ] Report scores **by segment** and state selection effects honestly.

## 9. Code structure for models

- [ ] `dataset.py` (feature lists, loading), `metrics.py`, `models_zoo.py` (every model is `fn(train, valid, feats) -> predictions`, plus a registry), one script per job: comparison, importance, train/validate/refit, test.
- [ ] Share hyperparameters in one dict (typed `dict[str, Any]`).
- [ ] Save the model in a portable format plus a `metadata.json` (features, settings, validation metrics, training period, `run_id`).

## 10. Document as you go

- [ ] **ADR** for every non-obvious choice: context, decision, alternatives, consequences, references.
- [ ] **Troubleshooting** entry for every error: symptom → cause → fix.
- [ ] **Build journal**, chronological.
- [ ] **Data dictionary, data lineage, model card** before calling V1 done.
- [ ] Write-up for a portfolio: headline numbers first, the hard part, honest limits, what's next.
