from pathlib import Path
import requests
from tqdm import tqdm

RAW = Path("data/raw")
DVF_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv/{y}/full.csv.gz"
YEARS = range(2021, 2026)

def fetch(url: str, dest: Path):
    """
    Fetch DVF data from the given URL and save it to the specified destination path. 
    If the file already exists, it will skip downloading. 
    The function creates necessary directories if they do not exist and shows a progress bar during the download process.
    """
    if dest.exists():
        print(f"skip {dest}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc=dest.name) as bar:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                bar.update(len(chunk))
        tmp.rename(dest)

if __name__ == "__main__":
    for y in YEARS:
        fetch(DVF_URL.format(y=y), RAW / "dvf" / f"dvf_{y}.csv.gz")