# ADR-0007: Pipeline and tracking, DVC for how, MLflow for what

- **Status:** accepted
- **Date:** 2026-11-22

## Context

Part 1 was a set of scripts run by hand, in an order only the author knew. Retraining automatically when the rules change needs three things:
- a pipeline that knows which steps depend on which files and settings, and reruns only what changed;
- a record of every training run (settings, scores, model file);
- a clear answer to "which model is in production?", with a rule for replacing it.

## Decision

**DVC for the pipeline** (`dvc.yaml`, `params.yaml`, `dvc.lock`):
- one stage per existing module, with its inputs, outputs and the parameter sections it reads;
- `download_dvf` output marked `persist` (raw data is never deleted on rerun);
- `reports/test_metrics.json` is a DVC metric (`cache: false`, committed to git);
- every setting lives in `params.yaml`, read through `params.py`. A changed parameter reruns exactly the stages that declare it;
- existing outputs were registered with `dvc commit -f` instead of being recomputed;
- exploration (`models_comparison`, `importance`) stays out of the pipeline.

**MLflow for tracking and the registry:**
- local SQLite backend (`sqlite:///mlflow.db`) and `mlruns/`, both git-ignored;
- training logs parameters, validation metrics and the model, and registers a new version of `property-price-estimator`;
- the test step logs its metrics into the same run;
- the `champion` alias marks the version the API serves.

**Promotion gate** (`tracking.promote_if_better`): a new version becomes champion only if its test median error is lower than the champion's.

## Alternatives considered

- **Makefile:** knows file dependencies, not parameters or data versions.
- **Airflow / Prefect:** schedulers. They solve "when", not "what changed", and add a server. Overkill for one machine; a cron or CI schedule can call `dvc repro` later.
- **MLflow Projects / pipelines only:** weaker data versioning than DVC.
- **Weights & Biases:** hosted tracking, account required. MLflow runs fully locally.

## Consequences

- `dvc repro` is the one command that rebuilds anything. `dvc params diff` and `dvc metrics diff` show what changed between commits.
- Roles stay separate: **DVC = how data and models are produced (reproducible); MLflow = what each run gave and which version is in use.**
- **Known weakness of the gate** (found in the retrain demo): it compares two scores computed on different test features (the challenger's at the new coefficient, the champion's at the old one), with no margin. 15.94% vs 15.96% promoted the challenger on noise. V1.1: re-score the champion on the same current features and require a minimum improvement. For rule-change retrains, promote when the challenger is not worse within a tolerance, because the old model is stale under the new rule.
- Still to do: a full `dvc repro --force` from raw data to prove reproducibility end to end, and a DVC remote for the prepared Parquet.

## References

- DVC, *Data pipelines*: https://dvc.org/doc/start/data-pipelines
- DVC, *dvc.yaml parameters*: https://dvc.org/doc/user-guide/project-structure/dvcyaml-files#parameters
- MLflow, *Tracking* and *Model Registry* (aliases): https://mlflow.org/docs/latest/
- DataTalks.Club MLOps Zoomcamp, modules 2 (tracking) and 4 (deployment): https://github.com/DataTalksClub/mlops-zoomcamp
- Chip Huyen (2022), *Designing Machine Learning Systems*, O'Reilly, ch. 6 (evaluation) and 9 (continual learning)
