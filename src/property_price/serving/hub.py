"""Fetch serving files from Hugging Face Hub when they are not present locally."""
import os
from pathlib import Path

from huggingface_hub import hf_hub_download

FILES = {
    "model.txt": Path("artifacts"),
    "metadata.json": Path("artifacts"),
    "market_snapshot.parquet": Path("data/processed"),
}


def ensure_serving_files() -> None:
    repo = os.environ.get("HF_REPO_ID")
    revision = os.environ.get("HF_REVISION")   # optional: pin a commit or tag
    for name, folder in FILES.items():
        if (folder / name).exists():
            continue
        if not repo:
            raise RuntimeError(f"{folder / name} is missing and HF_REPO_ID is not set")
        folder.mkdir(parents=True, exist_ok=True)
        hf_hub_download(repo_id=repo, filename=name, local_dir=folder, revision=revision)