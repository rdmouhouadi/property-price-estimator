"""Publish the champion model, its lookup table and model card to Hugging Face Hub."""
import json
from pathlib import Path

from huggingface_hub import HfApi

import os
import sys

def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing environment variable {name} (see .env.example)")
    return value

REPO_ID = env("HF_REPO_ID")
GITHUB_REPO = env("GITHUB_REPO")

FILES = {
    "artifacts/model.txt": "model.txt",
    "artifacts/metadata.json": "metadata.json",
    "data/processed/market_snapshot.parquet": "market_snapshot.parquet",
}

meta = json.loads(Path("artifacts/metadata.json").read_text())
card = Path("docs/model-card.md").read_text(encoding="utf-8")

header = f"""---
license: mit
library_name: lightgbm
pipeline_tag: tabular-regression
tags: [real-estate, france, dvf, dpe, energy-rating]
---

Code, pipeline and docs: https://github.com/{GITHUB_REPO}

"""
Path("artifacts/hf_README.md").write_text(header + card, encoding="utf-8")

api = HfApi()
api.create_repo(REPO_ID, repo_type="model", exist_ok=True)
for local, remote in FILES.items():
    api.upload_file(path_or_fileobj=local, path_in_repo=remote, repo_id=REPO_ID,
                    commit_message=f"model v{meta.get('model_version')}: {remote}")
api.upload_file(path_or_fileobj="artifacts/hf_README.md", path_in_repo="README.md",
                repo_id=REPO_ID, commit_message="model card")
print(f"https://huggingface.co/{REPO_ID}")