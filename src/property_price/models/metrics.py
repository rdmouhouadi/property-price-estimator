"""Score log(price/m2) predictions as prices in EUR."""

import numpy as np
import pandas as pd


def metrics(v: pd.DataFrame, pred_log: np.ndarray) -> dict:
    """
    Compute metrics for log(price/m2) predictions, returning a dictionary of metrics.
    Args:
        v: The DataFrame containing the true values
        pred_log: The predicted log(price/m2) values
    Returns:
        dict: A dictionary of computed metrics
    """
    
    true = v["valeur"].to_numpy()
    price = np.exp(pred_log) * v["surface_bati"].to_numpy()
    ape = np.abs(price - true) / true
    return {
        "mae_eur": round(float(np.mean(np.abs(price - true))), 0),
        "mdape_pct": round(float(np.median(ape) * 100), 2),
        "within_10_pct": round(float(np.mean(ape <= 0.10) * 100), 1),
        "within_20_pct": round(float(np.mean(ape <= 0.20) * 100), 1),
        "rmse_log": round(float(np.sqrt(np.mean((pred_log - v["y"].to_numpy()) ** 2))), 4),
    }