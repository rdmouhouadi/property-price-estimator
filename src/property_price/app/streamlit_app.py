"""Streamlit front end: calls the FastAPI service, shows the estimate and the energy-rating what-if."""

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

SRC = Path(__file__).resolve().parents[2]          # .../src
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

API_URL = os.environ.get("API_URL")   # set -> call FastAPI; unset -> run the API in-process


@st.cache_resource(show_spinner="Loading the model (first start only)...")
def _local_client():
    """Create a FastAPI TestClient that runs the API in-process (no network).
    Returns:
        A TestClient instance that can be used to call the API endpoints."""
    from fastapi.testclient import TestClient

    from property_price.serving.api import app

    client = TestClient(app)
    client.__enter__()          # runs FastAPI's lifespan: loads the predictor once
    return client


def call_api(method: str, path: str, **kwargs):
    """Call the API, either via HTTP (if API_URL is set) or in-process (if not).
    Args:
        method (str): The HTTP method to use.
        path (str): The API endpoint path.
        **kwargs: Additional arguments for the request.
    Returns:
        The response from the API."""
    if API_URL:
        return requests.request(method, f"{API_URL}{path}", timeout=30, **kwargs)
    return _local_client().request(method, path, **kwargs)


CLASSES = list("ABCDEFG")

st.set_page_config(page_title="What is my home worth?", page_icon="🏠", layout="wide")
st.title("🏠 What is my home worth?")
st.caption("Estimate based on public sales (DVF, 2021–2025) and, optionally, the energy rating (DPE). "
           "A first estimate, not a professional valuation.")

left, right = st.columns([1, 1.4], gap="large")

with left:
    """Property features"""
    with st.form("property"):
        address = st.text_input("Address", "10 rue de Rivoli 75004 Paris")
        type_bien = st.radio("Type", ["Appartement", "Maison"], horizontal=True,
                             format_func=lambda t: "Apartment" if t == "Appartement" else "House")
        c1, c2 = st.columns(2)
        surface = c1.number_input("Living area (m²)", 10.0, 1000.0, 50.0, step=1.0)
        pieces = c2.number_input("Rooms", 1, 30, 2)
        c3, c4 = st.columns(2)
        terrain = c3.number_input("Land (m²)", 0.0, 100000.0, 0.0, step=10.0)
        dependances = c4.number_input("Garages / cellars", 0, 20, 0)

        with st.expander("Energy rating (optional)"):
            dpe = st.selectbox("Energy label (DPE)", ["I don't know"] + CLASSES, index=4)
            annee = st.number_input("Construction year (0 = unknown)", 0, 2030, 0)
            etage = st.number_input("Floor (apartments, -1 = unknown)", -1, 60, -1)

        submitted = st.form_submit_button("Estimate", type="primary", use_container_width=True)

if submitted:
    payload = {
        "address": address, "type_bien": type_bien, "surface_bati": surface,
        "pieces": int(pieces), "surface_terrain": terrain, "n_dependances": int(dependances),
        "dpe_class": None if dpe == "I don't know" else dpe,
        "annee_construction": annee or None,
        "etage": None if etage < 0 else int(etage),
    }
    try:
        #r = requests.post(f"{API_URL}/estimate", json=payload, timeout=30) --- old code, replaced by call_api() to support in-process FastAPI
        r = call_api("POST", "/estimate", json=payload)
    except requests.RequestException:
        st.error("The estimation service is unreachable. Is the API running?")
        st.stop()
    if r.status_code != 200:
        st.error(r.json().get("detail", f"Error {r.status_code}"))
        st.stop()
    res = r.json()

    with right:
        """Estimated price and typical range"""
        lo, hi = res["typical_range_eur"]
        st.metric("Estimated price", f"{res['price_eur']:,.0f} €".replace(",", " "))
        st.write(f"**Typical range:** {lo:,.0f} € – {hi:,.0f} €  ·  "
                 f"**{res['price_m2']:,.0f} €/m²**".replace(",", " "))
        st.caption("Half of real sale prices fall within the typical range "
                   "(median error measured on 2025 sales the model never saw).")
        st.write(f"📍 {res['location']['label']}")
        st.map(pd.DataFrame([{"lat": res["location"]["lat"], "lon": res["location"]["lon"]}]),
               zoom=14, height=220, size=10, use_container_width=True)

        if "price_by_dpe_class" in res:
            st.subheader("What is my energy rating worth?")
            prices = res["price_by_dpe_class"]
            colors = ["#2438d8" if c == payload["dpe_class"] else "#a1a99d" for c in CLASSES]
            fig = go.Figure(go.Bar(x=CLASSES, y=[prices[c] for c in CLASSES], marker_color=colors,
                                   hovertemplate="Label %{x}: %{y:,.0f} €<extra></extra>"))
            fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0),
                              yaxis=dict(title="Estimated price (€)",
                                         range=[min(prices.values()) * 0.95,
                                                max(prices.values()) * 1.02]),
                              xaxis=dict(title="Energy label"))
            st.plotly_chart(fig, use_container_width=True)
            gap = prices["C"] - prices.get(payload["dpe_class"], prices["C"])
            if gap > 0:
                st.write(f"Same home rated **C**: about **+{gap:,.0f} €**.".replace(",", " "))
            st.caption("An association learned from local sales, not a guaranteed gain from renovating.")

        st.caption(f"Model version {res['model_version']}.")