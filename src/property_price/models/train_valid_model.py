"""Train the chosen model.
(1) fit on train, early-stop on valid -> best number of trees + valid metrics
(2) refit on train+valid with that number of trees -> save model + metadata
Usage: python -m property_price.models.train_valid_model [--features base|dpe]"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np

from property_price.logging_config import RUN_ID, get_logger, log_metric
from property_price.models import models_zoo
from property_price.models.dataset import BASE, DPE, load
from property_price.models.metrics import metrics

log = get_logger(__name__)
ARTIFACTS = Path("artifacts")
FEATURE_SETS = {"base": BASE, "dpe": DPE}


def main() -> None:
    """
    Main function to train the chosen model.
    (1) Fit on train, early-stop on valid to determine the best number of trees and validation metrics.
    (2) Refit on train + valid with that number of trees, then save the model and metadata.
    """
    fs = sys.argv[sys.argv.index("--features") + 1] if "--features" in sys.argv else "dpe"
    feats = FEATURE_SETS[fs]
    df = load()
    train, valid = df[df.split == "train"], df[df.split == "valid"]

    # (1) train -> valid
    m = models_zoo.lightgbm_model(train, valid, feats)
    best = int(m.best_iteration_)
    valid_metrics = metrics(valid, np.asarray(m.predict(valid[feats])))
    log_metric(log, "valid", feature_set=fs, best_iteration=best, **valid_metrics)

    # (2) refit on train + valid (validation data is now just more, and more recent, data)
    full = pd.concat([train, valid])
    log.info("refit on %d rows with %d trees", len(full), best)
    final = models_zoo.lightgbm_refit(full, feats, n_estimators=best)

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
    }
    (ARTIFACTS / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("saved %s and metadata.json", ARTIFACTS / "model.txt")


if __name__ == "__main__":
    main()