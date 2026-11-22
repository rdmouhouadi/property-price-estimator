"""Final evaluation on the 2025 test split. Run ONCE, after all choices are frozen."""
import json
from pathlib import Path

import lightgbm as lgb
import pandas as pd
import numpy as np

from property_price.logging_config import get_logger, log_metric
from property_price.models.dataset import load
from property_price.models.metrics import metrics

import mlflow
from property_price import tracking

log = get_logger(__name__)
ARTIFACTS = Path("artifacts")
REPORT = Path("reports/test_metrics.json")


def main() -> None:
    """
    Main function to evaluate the trained model on the test split.
    Loads the model and metadata, makes predictions on the test set, computes metrics, and saves the results to a JSON file.
    """
    meta = json.loads((ARTIFACTS / "metadata.json").read_text(encoding="utf-8"))
    booster = lgb.Booster(model_file=str(ARTIFACTS / "model.txt"))
    feats = meta["features"]

    df = load(include_test=True)
    test = df[df.split == "test"].reset_index(drop=True)
    pred = np.asarray(booster.predict(test[feats]))

    results = {"overall": metrics(test, pred)}
    for col in ["type_bien", "has_dpe"]:
        for val, g in test.groupby(col, observed=True):
            results[f"{col}={val}"] = metrics(g, pred[g.index])
    for name, res in results.items():
        log_metric(log, "test", segment=name, **res)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"run_id_model": meta["run_id"], **results}, indent=2),
                      encoding="utf-8")
    print("\n" + pd.DataFrame(results).T.to_string())
    log.info("saved %s", REPORT)

    tracking.setup()
    with mlflow.start_run(run_id=meta["mlflow_run_id"]):
        for seg, res in results.items():
            key = seg.replace("=", "_")  # MLflow metric keys cannot contain '='
            prefix = "test_" if seg == "overall" else f"test_{key}_"
            mlflow.log_metrics({f"{prefix}{k}": v for k, v in res.items()})

    tracking.promote_if_better(meta["model_version"], results["overall"]["mdape_pct"])


if __name__ == "__main__":
    main()