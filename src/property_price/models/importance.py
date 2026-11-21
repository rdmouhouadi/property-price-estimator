"""Permutation importance of the with-DPE LightGBM on validation -> feature selection."""
from pathlib import Path

import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.utils import Bunch

from property_price.logging_config import get_logger
from property_price.models import models_zoo
from property_price.models.dataset import DPE, SEED, dpe_subset, load, sample

log = get_logger(__name__)
REPORT = Path("reports/permutation_importance_dpe.csv")


def main() -> None:
    """
    Main function to compute permutation importance of the LightGBM model with DPE features.
    Loads the dataset, trains the model, computes permutation importance, and saves the results to a CSV file.
    """
    df = load()
    train, valid = df[df.split == "train"], df[df.split == "valid"]
    tB, vB = dpe_subset(train), valid[valid.has_dpe]

    model = models_zoo.lightgbm_model(tB, vB, DPE)
    vs = sample(vB, 50_000)
    pi = permutation_importance(model, vs[DPE], vs["y"], n_repeats=3, random_state=SEED,
                                scoring="neg_mean_absolute_error", n_jobs=1)
    assert isinstance(pi, Bunch)
    imp = (pd.DataFrame({"feature": DPE, "importance": pi.importances_mean,
                         "std": pi.importances_std})
           .sort_values("importance", ascending=False))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    imp.to_csv(REPORT, index=False)
    print("\n" + imp.to_string(index=False))
    log.info("saved %s", REPORT)


if __name__ == "__main__":
    main()