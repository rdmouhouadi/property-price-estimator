"""
MLflow setup + champion promotion, shared by training and testing.
"""
import math
import os

import mlflow
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from property_price.logging_config import get_logger

log = get_logger(__name__)

EXPERIMENT = "property-price"
MODEL_NAME = "property-price-estimator"
CHAMPION = "champion"
TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")


def setup() -> None:
    """
    Setup MLflow tracking URI and experiment.
    This function configures the MLflow tracking URI and sets the experiment name for logging.
    """
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT)


def promote_if_better(version: str, test_mdape: float) -> bool:
    """
    Human-readable gate: the new model becomes champion only if it beats the current one.
    this function promotes the model version to champion if it has a better test MdAPE than the current champion.
    Args:
        version: The version of the model to consider for promotion.
        test_mdape: The test MdAPE of the model version.
    Returns:
        bool: True if the model was promoted, False otherwise.
    """
    client = MlflowClient()
    champ = None
    champ_mdape = math.inf
    try:
        champ = client.get_model_version_by_alias(MODEL_NAME, CHAMPION)
    except MlflowException:  # no champion yet
        pass
    if champ is not None and champ.run_id is not None:
        champ_mdape = client.get_run(champ.run_id).data.metrics.get("test_mdape_pct", math.inf)

    if test_mdape < champ_mdape:
        client.set_registered_model_alias(MODEL_NAME, CHAMPION, version)
        log.info("promoted version %s to %s (test MdAPE %.2f%% < %.2f%%)",
                 version, CHAMPION, test_mdape, champ_mdape)
        return True
    log.info("kept champion version %s (%.2f%%); challenger %s scored %.2f%%",
             champ.version if champ else "-", champ_mdape, version, test_mdape)
    return False