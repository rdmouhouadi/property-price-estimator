# PLAYBOOK: tabular "big data" ML on one laptop, then MLOps

A reusable recipe, distilled from this project. Generic steps and rules, without the dead ends (those are in [docs/build-journal.md](docs/build-journal.md) and [docs/troubleshooting.md](docs/troubleshooting.md)).

Sections 1–10: the model. Sections 11–17: MLOps (pipeline, tracking, serving, monitoring, retraining, CI). Where to learn each tool: [docs/learning-references.md](docs/learning-references.md).

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
- [ ] Log each step and each error **as it happens**. Reconstructing them later loses the dead ends, which are the useful part.

---

# Part 2: MLOps

## 11. Pipeline (DVC)

- [ ] **Wrap the existing modules; don't rewrite them.** One `dvc.yaml` stage per module: `cmd`, `deps` (code + inputs), `outs`, `params`.
- [ ] Mark raw downloads `persist: true` so a rerun never deletes them.
- [ ] Register outputs you already have with **`dvc commit -f`** instead of recomputing hours of work.
- [ ] Test metrics as a DVC `metrics` file (`cache: false`, committed), so `dvc metrics diff` compares commits.
- [ ] Keep exploration (model comparison, importance) **out** of the pipeline. The pipeline is what production reruns.
- [ ] Check the graph with `dvc dag`. Screenshot it for the write-up.
- [ ] Prove reproducibility once: `dvc repro --force` from raw data should give the same test score.

## 12. Parameters

- [ ] **Every knob in `params.yaml`**, read through one cached loader. No constants left in scripts.
- [ ] Each stage declares the parameter **sections** it reads (a whole section, so new keys are tracked too).
- [ ] **Add a new parameter before the code that reads it.** Or read it with a safe default.
- [ ] A rule that can change by law (here, the electricity coefficient) is a parameter, not a constant.

## 13. Tracking and registry (MLflow)

- [ ] Local SQLite backend (`sqlite:///mlflow.db`), git-ignored. No server needed.
- [ ] Training logs parameters, validation metrics and the model, and **registers a new version**. Test logs into the **same run**.
- [ ] Production = an **alias** (`champion`), not a version number. The API loads the alias.
- [ ] **Roles:** DVC = how things are produced; MLflow = what each run gave and what is in use.
- [ ] **Promotion gate, done properly:**
  - score the champion and the challenger on the **same** current test features;
  - require a **margin** (e.g. 0.1 point), not just "lower";
  - after a rule change, "not worse within a tolerance" is enough: the old model is stale under the new rule.

## 14. Serving

- [ ] **API owns the model; the UI is just a client.** FastAPI + Pydantic validation, model loaded once at startup (lifespan), `/health` returns the model version.
- [ ] The API must rebuild **exactly the training features**. Ship the lookup tables it needs (here, a market snapshot) as a pipeline output, rebuilt with every run.
- [ ] Map external-service failures to clear errors (404 not found, 503 service down). Never return a wrong estimate silently.
- [ ] Show **a range next to every number**, and the disclaimer next to the number, not in a footer.
- [ ] Respect the data licence in the product (here: `noindex`, no individual sales shown).
- [ ] Mock external services in tests, so they run offline and in CI.
- [ ] Try the app on contrasting real cases (city centre vs suburb). Differences between them are often the best finding.

## 15. Monitoring

- [ ] **Test every monitor against a simulated version of the drift before trusting it.** A blind monitor gives false confidence.
- [ ] **Monitor the cause, not only the effects.** If you know what can change (a rule, a coefficient, a schema), measure it directly (here: median primary ÷ final energy for electric homes). Distribution tests on labels are diluted when only a segment is affected.
- [ ] Keep a generic distribution test (PSI) as a secondary net for unknown changes, per segment as well as overall.
- [ ] Two kinds of checks: **real** (must be stable: proves harmonisation works) and **simulated** (must fire: proves the detector works). Only real checks raise the alert.
- [ ] Simulated results can be drift by construction. **Backtest on a real past event** if one exists.
- [ ] **Never assume a source keeps its history as it was.** Publishers restate old records under new rules. Check for it (here: `ancienne_*` columns), and use the values as issued for backtests.
- [ ] **Freeze the reference.** Compute it once from the training snapshot, store it, compare against it. A reference recomputed from today's data moves with any restatement.
- [ ] Check what users actually hold: if history was restated, the document in the user's hands may not match what the model learned.
- [ ] One source of truth for the rules (a shared module), used by both features and monitoring.

## 16. Retraining

- [ ] Drift report (JSON) → trigger script → **edit the parameter** → `dvc repro` → gate. The pipeline does the work; the trigger only decides.
- [ ] Keep a person in the loop: the trigger leaves a reviewable diff (`params.yaml`, `dvc.lock`); a human commits.
- [ ] Demo with a `--simulate` flag, then **revert completely**: parameters, `dvc checkout`/`repro`, and the registry alias. Tag demo versions (e.g. `simulated`).
- [ ] Don't revert files with `git checkout` when they also hold uncommitted changes you want to keep.

## 17. CI

- [ ] GitHub Actions on push and PR: `uv sync --locked` (fails on a stale lockfile), **ruff**, **pytest**, `dvc dag` (checks the pipeline definition without data).
- [ ] CI has no data and no model: unit-test the logic on tiny in-memory tables (DuckDB), and **skip** tests that need artifacts when they're absent.
- [ ] Test the rules that matter most (here: label thresholds, harmonisation at the old and new coefficient).
- [ ] CI badge in the README. Screenshot the first green run.

## 18. Deploy and monitor

- [ ] **Publish the model where people can download it** (Hugging Face Hub: weights, metadata, lookup tables, model card). The app downloads from there too.
- [ ] **One app, two modes:** call the API when `API_URL` is set, run it in-process otherwise. Free hosts like Streamlit Cloud run the UI only.
  - **In-process** = the model runs inside the app's own process (a function call). **Remote API** = the model runs in another process/service, reached over HTTP.
  - Trick: embed the FastAPI app itself with `TestClient` + `st.cache_resource`, so both modes run the same code and return the same JSON. No duplicated logic.
  - A model hub is **storage**: the app downloads the files once and runs the model itself.
- [ ] **Configuration in environment variables** (`.env` git-ignored, `.env.example` committed, cloud secrets in the host's settings). Document every variable in one table.
- [ ] **Slim requirements for the deployed app.** Training tools (MLflow, DVC, XGBoost) don't belong in it.
- [ ] **Monitor in four layers**, and know which one alerts:
  1. **Pipeline runs:** structured logs with a `run_id`, followed live (`Get-Content file -Wait` / `tail -f`), plus the tracking UI.
  2. **Data:** a scheduled job compares fresh source data with a **frozen** reference and opens an issue on drift. This is the alerting layer.
  3. **Service:** an uptime ping on the app and the health endpoint.
  4. **Model quality:** log predictions; score the champion when new ground truth arrives (here, each DVF release).
- [ ] Ground truth often arrives months late. Monitor inputs and causes in the meantime.
