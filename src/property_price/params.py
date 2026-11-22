"""
Read params.yaml once; every script gets its settings from here.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PARAMS_FILE = Path("params.yaml")


@lru_cache
def load_params() -> dict[str, Any]:
    """
    Load the params.yaml file and return its contents as a dictionary.
    Returns:
        dict[str, Any]: The contents of the params.yaml file as a dictionary.
    """
    with PARAMS_FILE.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def params(section: str) -> dict[str, Any]:
    """
    Get the parameters for a specific section from the params.yaml file.
    Args:
        section (str): The section for which to retrieve parameters.
    Returns:
        dict[str, Any]: The parameters for the specified section.
    """
    return load_params()[section]