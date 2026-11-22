"""REST API: POST /estimate prices one property; GET /health reports the model in use."""
from contextlib import asynccontextmanager
from typing import Literal

import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from property_price.logging_config import get_logger
from property_price.serving.predictor import Predictor, Property

log = get_logger(__name__)
state: dict[str, Predictor] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["predictor"] = Predictor()        # load model + market snapshot once
    yield
    state.clear()


app = FastAPI(
    title="French property price estimator",
    description="Estimate a home's price from public sales (DVF) and, optionally, its energy rating (DPE).",
    version="0.2.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def no_index(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex"   # DVF terms: no search-engine indexing
    return response


class EstimateRequest(BaseModel):
    """Request model for property price estimation."""

    address: str = Field(..., min_length=5, examples=["10 rue de Rivoli 75004 Paris"])
    type_bien: Literal["Maison", "Appartement"]
    surface_bati: float = Field(..., gt=9, le=1000, description="Living area (m²)")
    pieces: int | None = Field(None, ge=1, le=30)
    surface_terrain: float = Field(0, ge=0, description="Land area (m²)")
    n_dependances: int = Field(0, ge=0, le=20, description="Garages, cellars, parking spaces")
    dpe_class: str | None = Field(None, pattern="^[A-Ga-g]$", description="Energy label A–G")
    ges_class: str | None = Field(None, pattern="^[A-Ga-g]$")
    dpe_ep_m2: float | None = Field(None, gt=0, description="Energy use (kWh/m²/year)")
    annee_construction: int | None = Field(None, ge=1500, le=2030)
    etage: int | None = Field(None, ge=0, le=60)


@app.get("/health")
def health() -> dict:
    """Health check endpoint to report the model version and training period.
    Returns:
        dict: A dictionary containing the health status and model information."""
    p = state["predictor"]
    return {"status": "ok", "model_version": p.meta.get("model_version"),
            "trained_on": p.meta.get("train_period")}


@app.post("/estimate")
def estimate(req: EstimateRequest) -> dict:
    """Estimate the price of a property based on the provided features.
    Args:
        req (EstimateRequest): The request containing the property features.
    Returns:
        dict: A dictionary containing the estimated price and other relevant information."""
    try:
        return state["predictor"].estimate(Property(**req.model_dump()))
    except ValueError as e:                       # address not found
        raise HTTPException(status_code=404, detail=str(e))
    except requests.RequestException as e:        # geocoding service unreachable
        log.warning("geocoding failed: %s", e)
        raise HTTPException(status_code=503, detail="Address service unavailable, try again.")