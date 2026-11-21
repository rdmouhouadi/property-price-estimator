"""
Compare models on the validation split (2024 H2); test is never touched here.
A: all sales, DVF features, every model in the zoo
B: DPE-matched sales 2022+, LightGBM without vs with DPE features (same rows)
Usage: python -m property_price.models.compare [--full]
"""
import sys
import time
from pathlib import Path

import pandas as pd

from property_price.logging_config import get_logger, log_metric
from property_price.models import models_zoo
from property_price.models.dataset import BASE, DPE, dpe_subset, load, sample
from property_price.models.metrics import metrics

log = get_logger(__name__)
REPORT = Path("reports/model_comparison.csv")
QUICK = "--full" not in sys.argv
QUICK_ROWS = 1_000_000


def evaluate(experiment: str, name: str, fn, t: pd.DataFrame, v: pd.DataFrame,
             feats: list[str]) -> dict:
    """
    Evaluate a model on the validation set and log the results.
    Args:
        experiment: The experiment name (e.g., "A" or "B")
        name: The model name
        fn: The model function to evaluate
        t: Training DataFrame
        v: Validation DataFrame
        feats: List of feature names to use for the model
    Returns:
        dict: A dictionary containing the evaluation results and metrics    
    """
    t0 = time.time()
    pred = fn(t, v, feats)
    res = {"experiment": experiment, "model": name,
           "n_train": min(len(t), models_zoo.TRAIN_CAP.get(name, len(t))), "n_valid": len(v),
           "seconds": round(time.time() - t0), **metrics(v, pred)}
    log_metric(log, "result", **res)
    return res


def main() -> None:
    """
    Main function to compare models and log the results.
    Loads the dataset, evaluates each model, and saves the results to a CSV file.
    """
    df = load()
    train, valid = df[df.split == "train"], df[df.split == "valid"]

    tA = sample(train, QUICK_ROWS) if QUICK else train
    rows = [evaluate("A", name, fn, tA, valid, BASE) for name, fn in models_zoo.MODELS.items()]

    tB, vB = dpe_subset(train), valid[valid.has_dpe]
    rows += [
        evaluate("B", "lightgbm_no_dpe", models_zoo.lightgbm, tB, vB, BASE),
        evaluate("B", "lightgbm_with_dpe", models_zoo.lightgbm, tB, vB, DPE),
    ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(REPORT, index=False)
    print("\n" + pd.DataFrame(rows).to_string(index=False))
    log.info("saved %s", REPORT)


if __name__ == "__main__":
    main()