"""Price one property: address -> location -> market lookup -> features -> model."""

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import polars as pl

from property_price.logging_config import get_logger
from property_price.models.dataset import CATEGORICAL
from property_price.params import params
from property_price.serving.geo import Location, locate

log = get_logger(__name__)
ARTIFACTS = Path("artifacts")
SNAPSHOT = Path("data/processed/market_snapshot.parquet")
TEST_REPORT = Path("reports/test_metrics.json")
K = params("features")["k_shrink"]
CLASSES = "ABCDEFG"


@dataclass
class Property:
    """Property information for price estimation.
    Attributes:
        address (str): The address of the property.
        type_bien (str): The type of the property ("Maison" or "Appartement").
        surface_bati (float): The built surface area.
        pieces (float | None): The number of rooms.
        surface_terrain (float): The land surface area.
        n_dependances (int): The number of outbuildings.
        dpe_class (str | None): The energy rating class ("A".."G")."""
    
    address: str
    type_bien: str                      # "Maison" or "Appartement"
    surface_bati: float
    pieces: float | None = None
    surface_terrain: float = 0.0
    n_dependances: int = 0
    # optional energy-rating (DPE) inputs
    dpe_class: str | None = None        # "A".."G"
    ges_class: str | None = None
    dpe_ep_m2: float | None = None
    annee_construction: int | None = None
    dpe_periode: int | None = None
    etage: int | None = None
    nb_niveaux: float | None = None
    dpe_energie: int | None = None


def shrink(child: float, n: int, parent: float) -> float:
    """Shrinkage of a child mean towards a parent mean, based on the number of observations.
    Args:
        child (float): The mean of the child group.
        n (int): The number of observations in the child group.
        parent (float): The mean of the parent group.
    Returns:
        float: The shrunk mean. """
   
    if n == 0 or math.isnan(child):
        return parent
    if math.isnan(parent):
        return child
    return (n * child + K * parent) / (n + K)


def _ordinal(c: str | None) -> float:
    """Convert a class label to an ordinal number.
    Args:
        c (str | None): The class label.
    Returns:
        float: The ordinal number. """
    return float(CLASSES.index(c.upper()) + 1) if c and c.upper() in CLASSES else math.nan


class Predictor:
    """Predict property price based on address and features."""
    def __init__(self) -> None:
        """Initialize the Predictor by loading the model, market snapshot, and metadata."""

        self.meta = json.loads((ARTIFACTS / "metadata.json").read_text(encoding="utf-8"))
        self.features: list[str] = self.meta["features"]
        self.booster = self._load_model()
        snap = pl.read_parquet(SNAPSHOT)
        self.market = {(r["level"], r["key"], r["type_bien"]): (r["m"], r["n"])
                       for r in snap.iter_rows(named=True)}
        self.mdape = self._typical_error()
        log.info("predictor ready: model version %s, %d market cells",
                 self.meta.get("model_version"), len(self.market))

    def _load_model(self) -> lgb.Booster:
        """Load the LightGBM model from file or MLflow.
        Returns:
            lgb.Booster: The loaded LightGBM model."""
        if os.environ.get("MODEL_SOURCE", "file") == "mlflow":
            import mlflow.lightgbm as mlflow_lightgbm

            from property_price import tracking
            tracking.setup()
            m = mlflow_lightgbm.load_model(f"models:/{tracking.MODEL_NAME}@{tracking.CHAMPION}")
            if isinstance(m, lgb.LGBMModel):    # logged from LGBMRegressor (our case)
                return m.booster_
            if isinstance(m, lgb.Booster):      # logged from a raw Booster
                return m
            raise RuntimeError("could not load the champion model from MLflow")
        return lgb.Booster(model_file=str(ARTIFACTS / "model.txt"))

    def _typical_error(self) -> dict[str, float]:
        """Median % error per property type, from the test report.
        Returns:
            dict[str, float]: A dictionary mapping property types to their median absolute percentage error."""
        
        if not TEST_REPORT.exists():
            return {}
        rep = json.loads(TEST_REPORT.read_text(encoding="utf-8"))
        return {t: rep[f"type_bien={t}"]["mdape_pct"] / 100
                for t in ("Maison", "Appartement") if f"type_bien={t}" in rep}

    def _market_features(self, loc: Location, type_bien: str) -> dict[str, float]:
        """Get market features for a given location and property type.
        Args:
            loc (Location): The location for which to get market features.
            type_bien (str): The type of property.
        Returns:
            dict[str, float]: A dictionary containing the market features."""
        
        def get(level: str, key: str | None) -> tuple[float, int]:
            return self.market.get((level, key, type_bien), (math.nan, 0)) if key else (math.nan, 0)
        dm, _ = get("dept", loc.code_departement)
        cm, cn = get("commune", loc.code_commune)
        sm, sn = get("section", loc.section)
        com = shrink(cm, cn, dm)
        return {"mkt_dept_12m": dm, "mkt_commune_12m": com,
                "mkt_section_12m": shrink(sm, sn, com),
                "mkt_commune_n": float(cn), "mkt_section_n": float(sn)}

    def _row(self, p: Property, loc: Location) -> dict[str, Any]:
        """Create a feature row for the model based on property and location information.
        Args:
            p (Property): The property for which to create the feature row.
            loc (Location): The location of the property.
        Returns:
            dict[str, Any]: A dictionary containing the feature values for the property."""
        
        return {
            "type_bien": p.type_bien, "code_departement": loc.code_departement,
            "surface_bati": p.surface_bati, "pieces": p.pieces,
            "surface_terrain": p.surface_terrain, "n_dependances": p.n_dependances,
            "lat": loc.lat, "lon": loc.lon,
            **self._market_features(loc, p.type_bien),
            "dpe_energie": None if p.dpe_energie is None else str(p.dpe_energie),
            "dpe_class": _ordinal(p.dpe_class), "ges_class": _ordinal(p.ges_class),
            "dpe_ep_m2": p.dpe_ep_m2, "dpe_periode": p.dpe_periode,
            "annee_construction": p.annee_construction, "etage": p.etage,
            "nb_niveaux": p.nb_niveaux,
        }

    def _price(self, row: dict[str, Any], surface: float) -> float:
        """Predict the price of a property based on its features and surface area.
        Args:
            row (dict[str, Any]): The feature values for the property.
            surface (float): The surface area of the property.
        Returns:
            float: The predicted price of the property."""
        
        df = pd.DataFrame([row])[self.features]
        for c in self.features:
            df[c] = df[c].astype("category") if c in CATEGORICAL else df[c].astype(float)
        return float(math.exp(np.asarray(self.booster.predict(df))[0]) * surface)

    def estimate(self, p: Property) -> dict[str, Any]:
        """Estimate the price of a property based on its features and location.
        Args:
            p (Property): The property for which to estimate the price.
        Returns:
            dict[str, Any]: A dictionary containing the estimated price and related information."""
        
        loc = locate(p.address)
        row = self._row(p, loc)
        price = self._price(row, p.surface_bati)
        err = self.mdape.get(p.type_bien, 0.16)
        out: dict[str, Any] = {
            "price_eur": round(price, -3),
            "typical_range_eur": [round(price * (1 - err), -3), round(price * (1 + err), -3)],
            "price_m2": round(price / p.surface_bati),
            "location": loc.to_dict(),
            "model_version": self.meta.get("model_version"),
        }
        if p.dpe_class:   # "what is my energy rating worth?": same home, each label
            out["price_by_dpe_class"] = {
                c: round(self._price(row | {"dpe_class": float(i + 1), "dpe_ep_m2": None},
                                     p.surface_bati), -3)
                for i, c in enumerate(CLASSES)
            }
        return out