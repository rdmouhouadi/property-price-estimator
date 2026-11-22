"""Model zoo. Every model: fn(train, valid, feats) -> predictions of log(price/m2) on valid."""

from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from property_price.models.dataset import CATEGORICAL, SEED, sample
from property_price.params import params

# max training rows per model (slow models are trained on a sample)
TRAIN_CAP = {"baseline_section_market": 0, "ridge": 500_000, "random_forest": 300_000}


def _linear_pre(feats: list[str]) -> ColumnTransformer:
    """
    Create a preprocessing pipeline for linear models.
    Categorical features are one-hot encoded, and numerical features are imputed and scaled.
    Args:
        feats: List of feature names to include in the preprocessing
    Returns:
        ColumnTransformer: The preprocessing pipeline
    """

    cats = [c for c in feats if c in CATEGORICAL]
    nums = [c for c in feats if c not in cats]
    return ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), nums),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), cats),
    ])


def baseline_market(t: pd.DataFrame, v: pd.DataFrame, feats: list[str]) -> np.ndarray:
    """
    Predict the neighbourhood's past average.
    No learning is performed; this is a baseline model that uses the market averages from the training data.
    Args:
        t: Training DataFrame (not used in this baseline model)
        v: Validation DataFrame
        feats: List of feature names
    Returns:
        np.ndarray: The predicted values
    """
    return v["mkt_section_12m"].fillna(v["mkt_commune_12m"]).to_numpy()


def ridge(t: pd.DataFrame, v: pd.DataFrame, feats: list[str]) -> np.ndarray:
    """
    Fit a Ridge regression model on the training data and predict on the validation data.
    Args:
        t: Training DataFrame
        v: Validation DataFrame
        feats: List of feature names
    Returns:
        np.ndarray: The predicted values
    """
    t = sample(t, TRAIN_CAP["ridge"])
    m = make_pipeline(_linear_pre(feats), Ridge(alpha=1.0))
    return np.asanyarray(m.fit(t[feats], t["y"]).predict(v[feats]) )


def random_forest(t: pd.DataFrame, v: pd.DataFrame, feats: list[str]) -> np.ndarray:
    """
    Fit a Random Forest regression model on the training data and predict on the validation data.
    Args:
        t: Training DataFrame
        v: Validation DataFrame
        feats: List of feature names
    Returns:
        np.ndarray: The predicted values
    """
    t = sample(t, TRAIN_CAP["random_forest"])
    m = make_pipeline(_linear_pre(feats), RandomForestRegressor(
        n_estimators=200, max_depth=20, min_samples_leaf=5, n_jobs=-1, random_state=SEED))
    return np.asanyarray(m.fit(t[feats], t["y"]).predict(v[feats]))


_p = params("model")
LGBM_PARAMS: dict[str, Any] = {
    k: _p[k] for k in ["learning_rate", "num_leaves", "min_child_samples", 
                       "subsample", "subsample_freq", "colsample_bytree"]
} | {"random_state": _p["seed"], "verbose": -1}


def lightgbm_model(t: pd.DataFrame, v: pd.DataFrame, feats: list[str]) -> lgb.LGBMRegressor:
    """Fitted LightGBM, early stopping on valid (up to 3000 trees)."""
    m = lgb.LGBMRegressor(n_estimators=_p["max_trees"], **LGBM_PARAMS)
    m.fit(t[feats], t["y"], eval_set=[(v[feats], v["y"])],
          callbacks=[lgb.early_stopping(_p["early_stopping_rounds"], verbose=False)])
    return m


def lightgbm_refit(t: pd.DataFrame, feats: list[str], n_estimators: int) -> lgb.LGBMRegressor:
    """Refit with a fixed number of trees (found by early stopping), no validation set."""
    m = lgb.LGBMRegressor(n_estimators=n_estimators, **LGBM_PARAMS)
    return m.fit(t[feats], t["y"])


def lightgbm(t: pd.DataFrame, v: pd.DataFrame, feats: list[str]) -> np.ndarray:
    """
    Fit a LightGBM regression model on the training data and predict on the validation data.
    Args:
        t: Training DataFrame
        v: Validation DataFrame
        feats: List of feature names
    Returns:
        np.ndarray: The predicted values
    """
    return np.asanyarray(lightgbm_model(t, v, feats).predict(v[feats]))


def xgboost(t: pd.DataFrame, v: pd.DataFrame, feats: list[str]) -> np.ndarray:
    """
    Fit an XGBoost regression model on the training data and predict on the validation data.
    Args:
        t: Training DataFrame
        v: Validation DataFrame
        feats: List of feature names
    Returns:
        np.ndarray: The predicted values
    """
    m = xgb.XGBRegressor(n_estimators=3000, learning_rate=0.05, max_depth=10, subsample=0.8,
                         colsample_bytree=0.8, tree_method="hist", enable_categorical=True,
                         max_cat_to_onehot=1, early_stopping_rounds=100,
                         random_state=SEED, n_jobs=-1)
    m.fit(t[feats], t["y"], eval_set=[(v[feats], v["y"])], verbose=False)
    return m.predict(v[feats])


MODELS = {
    "baseline_section_market": baseline_market,
    "ridge": ridge,
    "random_forest": random_forest,
    "lightgbm": lightgbm,
    "xgboost": xgboost,
}