"""Train the chosen model.
(1) fit on train, early-stop on valid -> best number of trees + valid metrics
(2) refit on train+valid with that number of trees -> save model + metadata
Usage: python -m property_price.models.train_valid_model [--features base|dpe]"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np

from property_price.logging_config import RUN_ID, get_logger, log_metric
from property_price.models import models_zoo
from property_price.models.dataset import BASE, DPE, load
from property_price.models.metrics import metrics
from property_price.params import params

import mlflow
import mlflow.lightgbm as mlflow_lightgbm

from property_price import tracking

log = get_logger(__name__)
ARTIFACTS = Path("artifacts")
FEATURE_SETS = {"base": BASE, "dpe": DPE}


def main() -> None:
    """
    Main function to train the chosen model.
    (1) Fit on train, early-stop on valid to determine the best number of trees and validation metrics.
    (2) Refit on train + valid with that number of trees, then save the model and metadata.
    """
    fs = params("model")["feature_set"]
    feats = FEATURE_SETS[fs]

    tracking.setup()
    with mlflow.start_run(run_name=f"train-{RUN_ID}") as run:
        mlflow.set_tags({"pipeline_run_id": RUN_ID, "feature_set": fs})
        mlflow.log_params(params("model") | {"n_features": len(feats), "features": feats})

        df = load()
        train, valid = df[df.split == "train"], df[df.split == "valid"]

        # (1) train -> valid
        m = models_zoo.lightgbm_model(train, valid, feats)
        best = int(m.best_iteration_)
        valid_metrics = metrics(valid, np.asarray(m.predict(valid[feats])))
        log_metric(log, "valid", feature_set=fs, best_iteration=best, **valid_metrics)
        mlflow.log_param("best_iteration", best)
        mlflow.log_metrics({f"valid_{k}": v for k, v in valid_metrics.items()})

        # (2) refit on train + valid (validation data is now just more, and more recent, data)
        full = pd.concat([train, valid])
        log.info("refit on %d rows with %d trees", len(full), best)
        final = models_zoo.lightgbm_refit(full, feats, n_estimators=best)

        # (3) save model + metadata locally (DVC output) + log and register in MLflow
        info = mlflow_lightgbm.log_model(final, name="model", registered_model_name=tracking.MODEL_NAME)

        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        final.booster_.save_model(str(ARTIFACTS / "model.txt"))
        meta = {
            "run_id": RUN_ID,
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": "lightgbm",
            "target": "ln(price_per_m2)",
            "feature_set": fs,
            "features": feats,
            "best_iteration": best,
            "valid_metrics": valid_metrics,
            "train_rows": len(full),
            "train_period": [str(full.date.min()), str(full.date.max())],
            "mlflow_run_id": info.run_id,
            "mlflow_model_uri": info.model_uri,
            "mlflow_registered_model_name": tracking.MODEL_NAME,
            "model_version": str(info.registered_model_version),
        }
        (ARTIFACTS / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        mlflow.log_artifact(str(ARTIFACTS / "metadata.json"), artifact_path="model_metadata")
        log.info("saved model, registered %s version %s", tracking.MODEL_NAME, info.registered_model_version)


if __name__ == "__main__":
    main()