"""Download the open Berlin datasets for the voxel build (Sprint 1).

Sources (all open, dl-de/by-2-0 or CC-BY 4.0):
  LoD2 building models  FIS-Broker ATOM, one 1 km x 1 km ZIP per tile
  DGM1 terrain          FIS-Broker ATOM, one 1 km x 1 km ZIP per tile

Tiles are named by their lower-left corner in whole kilometres of EPSG:25833,
so the Alexanderplatz test area (392800, 5820400) is tile (392, 5820).

Usage:
    python pipeline/fetch_open_data.py                  # the 1 km test tile
    python pipeline/fetch_open_data.py --tiles 389,5818 390,5818
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
LOD2_DIR = RAW / "lod2_citygml"
DGM1_DIR = RAW / "dgm1"

BASE = "https://fbinter.stadt-berlin.de/fb/atom"
TEST_TILES = [(392, 5820)]  # Alexanderplatz, 1 km x 1 km


def get_lod2_url(e_km: int, n_km: int) -> str:
    return f"{BASE}/LOD2/LoD2_{e_km}_{n_km}.zip"


def get_dgm1_url(e_km: int, n_km: int) -> str:
    return f"{BASE}/DGM1/DGM1_{e_km}_{n_km}.zip"


def download(url: str, dest: Path) -> Path:
    """Stream url to dest unless it is already there. Writes via a .part file."""
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  have  {dest.relative_to(ROOT)}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    print(f"  get   {url}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with part.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    part.rename(dest)
    return dest


def extract(zip_path: Path, out_dir: Path) -> list[Path]:
    """Extract a tile archive into its own directory. Only members that resolve
    inside out_dir are written (no path traversal from a downloaded archive)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    root = out_dir.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            target = (out_dir / member.filename).resolve()
            if root not in target.parents:
                raise ValueError(f"unsafe member in {zip_path.name}: {member.filename}")
            zf.extract(member, out_dir)
            written.append(target)
    return written


def parse_tile(text: str) -> tuple[int, int]:
    e, n = text.split(",")
    return int(e), int(n)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tiles", nargs="*", type=parse_tile, metavar="E,N",
                    help="tile corners in whole km, e.g. 392,5820 (default: the test tile)")
    ap.add_argument("--no-extract", action="store_true", help="download only")
    args = ap.parse_args(argv)

    tiles = args.tiles or TEST_TILES
    failed = []
    for e_km, n_km in tiles:
        print(f"tile {e_km}_{n_km}")
        for label, url_fn, out_dir in (
            ("LoD2", get_lod2_url, LOD2_DIR),
            ("DGM1", get_dgm1_url, DGM1_DIR),
        ):
            url = url_fn(e_km, n_km)
            zip_path = out_dir / Path(url).name
            try:
                download(url, zip_path)
                if not args.no_extract:
                    members = extract(zip_path, out_dir / f"{e_km}_{n_km}")
                    print(f"  {label}: {len(members)} files in {(out_dir / f'{e_km}_{n_km}').relative_to(ROOT)}")
            except (requests.RequestException, zipfile.BadZipFile, ValueError) as exc:
                print(f"  {label} FAILED: {exc}", file=sys.stderr)
                failed.append((label, e_km, n_km))
    if failed:
        print(f"{len(failed)} download(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
