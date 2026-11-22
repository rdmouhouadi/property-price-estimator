from fastapi.testclient import TestClient

from property_price.serving import predictor as pred_module
from property_price.serving.api import app
from property_price.serving.geo import Location

FAKE = Location(label="10 Rue de Rivoli 75004 Paris", code_commune="75104",
                code_departement="75", lat=48.855, lon=2.360, score=0.95, section=None)


def test_estimate_and_validation(monkeypatch):
    """Test the /estimate endpoint and input validation of the API.
    This test checks the functionality of the /estimate endpoint by sending valid and invalid requests."""
    monkeypatch.setattr(pred_module, "locate", lambda address: FAKE)   # no network call
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"

        ok = client.post("/estimate", json={"address": "10 rue de Rivoli 75004 Paris",
                                            "type_bien": "Appartement", "surface_bati": 50,
                                            "dpe_class": "D"})
        assert ok.status_code == 200
        body = ok.json()
        assert body["price_eur"] > 0
        assert set(body["price_by_dpe_class"]) == set("ABCDEFG")

        bad = client.post("/estimate", json={"address": "x", "type_bien": "Chateau",
                                             "surface_bati": -5})
        assert bad.status_code == 422