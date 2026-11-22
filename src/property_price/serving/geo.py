"""Address -> commune, coordinates, cadastral section (IGN Géoplateforme + API Carto)."""
import json
from dataclasses import asdict, dataclass

import requests

GEOCODE_URL = "https://data.geopf.fr/geocodage/search"
CADASTRE_URL = "https://apicarto.ign.fr/api/cadastre/parcelle"
TIMEOUT = 10


@dataclass
class Location:
    """Location information for a given address."""
    label: str
    code_commune: str
    code_departement: str
    lat: float
    lon: float
    score: float
    section: str | None   # first 10 chars of the parcel id, same key as in training

    def to_dict(self) -> dict:
        """Convert the Location dataclass to a dictionary.
        Returns:
            dict: A dictionary representation of the Location instance."""
        return asdict(self)


def _departement(citycode: str) -> str:
    """Extract the département code from the citycode.
    Args:
        citycode (str): The city code.
    Returns:
        str: The département code."""
    return citycode[:3] if citycode.startswith("97") else citycode[:2]


def _section(lon: float, lat: float) -> str | None:
    """Get the cadastral section for the given coordinates using the IGN API.
    Args:
        lon (float): The longitude.
        lat (float): The latitude.
    Returns:
        str | None: The cadastral section or None if not found."""
    try:
        geom = json.dumps({"type": "Point", "coordinates": [lon, lat]})
        r = requests.get(CADASTRE_URL, params={"geom": geom}, timeout=TIMEOUT)
        r.raise_for_status()
        feats = r.json().get("features", [])
        idu = feats[0]["properties"].get("idu") if feats else None
        return idu[:10] if idu else None
    except requests.RequestException:
        return None


def locate(address: str) -> Location:
    """Locate the given address using the IGN Géoplateforme API.
    Args:
        address (str): The address to locate.
    Returns:
        Location: The location information for the given address."""
    
    r = requests.get(GEOCODE_URL, params={"q": address, "limit": 1}, timeout=TIMEOUT)
    r.raise_for_status()
    feats = r.json().get("features", [])
    if not feats:
        raise ValueError(f"address not found: {address}")
    props = feats[0]["properties"]
    lon, lat = feats[0]["geometry"]["coordinates"]
    return Location(
        label=props.get("label", address),
        code_commune=props["citycode"],
        code_departement=_departement(props["citycode"]),
        lat=lat, lon=lon,
        score=float(props.get("score", 0)),
        section=_section(lon, lat),
    )