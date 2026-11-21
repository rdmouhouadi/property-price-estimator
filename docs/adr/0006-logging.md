# ADR-0006: Logging

- **Status:** accepted
- **Date:** 2026-11-21

## Context

The pipeline will run unattended (scheduled jobs, CI, containers). We need to know what each run did, how many rows each step kept, and where it failed, in a form both people and tools can read.

## Decision

- **Python's standard `logging`.** No extra dependency, and it's what libraries (MLflow, Airflow, LightGBM) already use.
- **One shared module,** `src/property_price/logging_config.py`. Scripts call `get_logger(__name__)` and never configure logging themselves.
- **Two outputs:**
  - console, human-readable;
  - `logs/pipeline.jsonl`, one JSON object per event, parseable by CI and monitoring.
- **`run_id`** on every line (from the `RUN_ID` environment variable, or generated), so one execution can be followed end to end.
- **`log_metric(logger, msg, **fields)`** for structured events, such as lineage row counts and model metrics, whose fields become JSON keys.
- **In Docker:** `LOG_TO_FILE=0`, stdout only, and the platform collects logs.
- **Scope:** logs record *what happened*. MLflow (part 2) records *experiment parameters, metrics and models*.

## Consequences

- When a module runs with `python -m`, its `__name__` is `"__main__"`, which sits outside the package's logger tree, so INFO messages were silently dropped. `get_logger` now prefixes such names with `property_price.` ([troubleshooting #20](../troubleshooting.md)).
- The `print` calls in the `data/` scripts will be converted during part 2.

## References

- Python logging HOWTO: https://docs.python.org/3/howto/logging.html
- The Twelve-Factor App, *Logs*: https://12factor.net/logs
