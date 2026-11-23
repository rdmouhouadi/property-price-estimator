# Troubleshooting

Every error hit while building the project (part 1: model, part 2: MLOps), grouped by area. Format: **symptom → cause → fix**. Environment: Windows, PowerShell, VS Code, uv.

## Environment and tooling

**1. `uv add` not found, only `python -m uv` works**
- *Cause:* uv was pip-installed into the Microsoft Store Python, whose `Scripts` folder isn't on PATH.
- *Fix:* `python -m pip uninstall uv`, install standalone uv (`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` or `winget install astral-sh.uv`), reopen the terminal, and let uv manage Python (`uv python install 3.11`).

**2. `uv add … shap` fails building `llvmlite==0.36.0` ("only versions >=3.6,<3.10 are supported")**
- *Cause:* `requires-python = ">=3.11"` is open-ended. uv builds one lockfile for every Python in that range, including future ones, so it backtracked to an ancient llvmlite with no upper bound.
- *Fix:* bound it, with `requires-python = ">=3.11,<3.13"`. Then `shap` was dropped entirely, since LightGBM/XGBoost provide TreeSHAP natively.

**3. WSL: `uv: command not found`, no git identity, project on `/mnt/c`, running as root**
- *Cause:* WSL is a separate Linux (it needs its own uv and git config). `/mnt/c` is slow and clashes with the Windows `.venv`.
- *Fix:* went back to Windows PowerShell. If you use WSL: install uv inside it, keep the project in `~/`, and create a non-root user.

**4. Folder typo `scr/` instead of `src/`**
- *Fix:* `git mv scr src`, which keeps file history.

**5. Pylance: `Import "tqdm" could not be resolved`**
- *Cause:* VS Code isn't using the project's `.venv`.
- *Fix:* *Python: Select Interpreter* → `.venv\Scripts\python.exe`, or `"python.defaultInterpreterPath"` in `.vscode/settings.json`.

**12. `reports/dpe_schema.txt` missing at commit time**
- *Cause:* `reports/` didn't exist when the output was redirected. Also, PowerShell `>` writes UTF-16.
- *Fix:* `mkdir reports`, then `… | Out-File -Encoding utf8 reports/dpe_schema.txt`. Use `Add-Content`, not `echo >>`, for `.gitignore`.

**18. `python -m …train_valid_model` exits instantly with no output**
- *Cause:* `main()` never ran: the file was unsaved, or the `if __name__ == "__main__":` block was missing or mistyped.
- *Fix:* save, check with `Get-Content <file> -Tail 5`.

**19. `train_valid_model.py` committed empty (0 bytes)**
- *Cause:* the code was in the editor but never saved.
- *Fix:* `Get-ChildItem <folder> | Select-Object Name, Length` to spot 0-byte files, save, recommit. Enable *File → Auto Save*.

## Data sources

**6. DVF download: 404 for 2020**
- *Cause:* geo-DVF keeps only the last five years.
- *Fix:* `YEARS = range(2021, 2026)`. No loss, because the new DPE starts in July 2021.

**7. No full DPE CSV on data.ademe.fr**
- *Cause:* the portal is a table viewer, and the data.gouv "main file" is only a link.
- *Fix:* ADEME's remote DuckDB access ([ADR-0003](adr/0003-dpe-source-remote-duckdb.md)).

**11. Polars: `could not parse "14A" as dtype i64 at column 'lot1_numero'`**
- *Cause:* the schema was inferred from the first rows. Later rows broke it.
- *Fix:* read DVF with `infer_schema=False` (all strings), then cast only the needed numeric columns. Codes stay strings (leading zeros, `2A`/`2B`).

**13. DuckDB `read_csv`: "Expected 40 columns, found 41" at line 2,335,553 of `dvf_2021.csv.gz`**
- *Cause:* the quote character was auto-detected as "none" from a 20k-line sample, then a quoted street name containing a comma (`"RUE ANNE, COMTE DE TOURVILLE"`) split in two.
- *Fix:* declare `delim=',', quote='"', escape='"'`. Don't use `ignore_errors`, which would silently drop real sales.

## Memory and performance

**9. How to set DuckDB's memory limit**
- *Fix:* `SET memory_limit` to about 50–60% of RAM, `SET temp_directory` (for disk spill, with 20 GB free), `SET threads = 4`, `SET preserve_insertion_order = false`.

**10. DuckDB `OutOfMemoryException` (5.5 GiB/5.5 GiB) on the 8-table remote DPE join**
- *Cause:* one query building several 20M-row hash tables at once, over the network.
- *Fix:* two stages, both resumable:
  - (A) stream the needed columns of each table to local Parquet;
  - (B) join locally in 8 hash buckets (`hash(dpe_id) % 8 = k`).

## Type checker (Pylance) warnings

None of these break at runtime. They come from libraries typing results as "X or None" or a union. The fix is to make the assumption explicit.

**8. `reportOptionalSubscript` on `fetchone()[0]`, `reportOptionalMemberAccess` on `duckdb.sql(...).show()`**
- *Fix:* `row = …fetchone(); assert row is not None`, and a small `show()` helper with `assert rel is not None`.

**14. `reportReturnType` on LightGBM `.predict()` (`_LGBM_PredictReturnType` includes sparse matrices)**
- *Fix:* `np.asarray(model.predict(X))`.

**15. `reportAttributeAccessIssue`: `importances_std` on `dict[str, Bunch]`**
- *Cause:* `permutation_importance` returns a dict when several scorers are passed.
- *Fix:* `from sklearn.utils import Bunch` and `assert isinstance(pi, Bunch)`.

**16. `reportArgumentType` flood on `LGBMRegressor(**LGBM_PARAMS)`**
- *Cause:* `dict(...)` was inferred as `dict[str, float]`, so unpacking "passes float" to every parameter.
- *Fix:* `LGBM_PARAMS: dict[str, Any] = {...}`.

## Libraries

**17. `LGBMDeprecationWarning: The argument 'eval_set' is deprecated, use 'eval_X' and 'eval_y'`**
- *Status:* still works. Update when pinning versions for Docker.

**20. No INFO log lines from scripts run with `python -m` (exit code 0)**
- *Cause:* the module's `__name__` is `"__main__"`, outside the `property_price` logger tree where the handlers are, so INFO messages are dropped.
- *Fix:* `get_logger` prefixes non-package names with `property_price.` ([ADR-0006](adr/0006-logging.md)).

## Part 2: MLOps

**21. Pylance on `client.get_run(champ.run_id)` in `tracking.promote_if_better`**
- *Cause:* `ModelVersion.run_id` is typed `Optional[str]`, because a registered version can exist without a run.
- *Fix:* read the alias inside `try/except`, then read the champion's metric only when `champ is not None and champ.run_id is not None`. Otherwise the champion's score is infinity, so the first model is always promoted.

**22. `reportPrivateImportUsage`: "lightgbm" is not exported from module "mlflow"**
- *Cause:* MLflow loads its flavours lazily, so `mlflow.lightgbm` isn't a declared export of `mlflow`.
- *Fix:* `import mlflow.lightgbm as mlflow_lightgbm`, then call `mlflow_lightgbm.log_model(...)`. Keep `import mlflow` for `start_run` and `log_metrics`.

**23. Pylance on `m.booster_` after `mlflow.lightgbm.load_model`**
- *Cause:* the return type is `Booster | LGBMModel | None`.
- *Fix:* `isinstance` checks: an `LGBMModel` gives `.booster_`, a `Booster` is used as is, anything else raises a `RuntimeError` at API startup, not at the first request.

**24. `KeyError: 'electric_energy_ids'` in `build_features` during `retrain_on_drift` (`dvc repro` exit 255)**
- *Cause:* the code reading the new parameter landed before the parameter itself was added to `params.yaml`.
- *Fix:* add `dpe_rules.electric_energy_ids` (the IDs from the drift log), and make the `features` stage track the whole `dpe_rules` section in `dvc.yaml`, so DVC reruns it when the IDs change.
- *Rule:* add a new parameter to `params.yaml` before the code that reads it.

**25. `Object of type "DuckDBPyRelation" is not callable` on `duckdb.sql(q).fetchone()` (Pylance `reportCallIssue`)**
- *Cause:* in duckdb's type stubs, `DuckDBPyRelation` resolves `fetchone` through a catch-all `__getattr__` that returns another relation. Runtime is fine.
- *Fix:* use a connection, which is typed properly: `con = duckdb.connect()`, then `con.execute(q).fetchone()` and `assert row is not None`.

**26. CI badge shows as a broken image, then "no status"**
- *Cause:* the workflow file was `ci.yaml` but the badge URL pointed to `ci.yml`. After renaming, the badge showed "no status": the renamed file is a new workflow with no history yet, and GitHub caches badge images.
- *Fix:* match the file name exactly (or copy the markdown from Actions → workflow → "…" → *Create status badge*), and pin the branch: `badge.svg?branch=main`.

**27. PowerShell `ParserError` on `uv run python -c "...duckdb.sql(\"SELECT ...\")"`**
- *Cause:* PowerShell doesn't treat `\"` as an escaped quote (it uses a backtick or doubled quotes), so the string breaks.
- *Fix:* put any Python with nested quotes in a script file under `scripts/` instead of a `-c` one-liner.

**28. Pylance "Cannot access attribute `pl`" on `con.execute(q).pl()`**
- *Cause:* a gap in duckdb's type stubs; works at runtime.
- *Fix:* `fetchall()` for printing, and `COPY (query) TO 'file.csv' (HEADER)` to save.

**29. `401 Unauthorized` ("Invalid username or password") on `api/repos/create` when pushing to Hugging Face**
- *Cause:* no valid token reached the script: login not saved, a read-only or Inference token, or a wrong `HF_TOKEN` in `.env` overriding the login.
- *Fix:* create a **Write** token (or fine-grained with repo create + write), `uv run hf auth login`, check with `uv run hf auth whoami`; or set `HF_TOKEN` in the git-ignored `.env`.

**30. `uv sync` after deleting `.venv`: "Failed to install streamlit… `Scripts\streamlit.exe`: Access is denied (os error 5)"**
- *Cause:* a running process (Streamlit or uvicorn from the old environment, a terminal with it still activated) or antivirus held the file.
- *Fix:* stop the processes (`Get-Process streamlit, uvicorn, python | Stop-Process -Force`), `deactivate` or open a new terminal, `Remove-Item -Recurse -Force .venv`, `uv sync`.

**31. CI lint fails with ruff I001 (unsorted imports) after adding `import sys` / `from pathlib import Path` to the app**
- *Fix:* `uv run ruff check src tests --fix`. Keep `property_price` imports inside functions, or after the `sys.path` block with `# noqa: E402`. Run ruff before every commit (or a pre-commit hook).
- *Related:* the "requirements up to date" CI step first compared with a copy exported to `/tmp`; it failed on uv's header comment (which records the output path). Regenerate in place and use `git diff --exit-code` instead.
