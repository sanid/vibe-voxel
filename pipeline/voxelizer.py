"""Voxelize one DGM1 + LoD2 tile into a 1 m NumPy matrix (Sprint 1).

Output: data/processed/voxels_<E>_<N>.npz, with
    voxels  uint8 (nz, ny, nx), index [z, row, col]; 0 = air
    origin_e, origin_n  easting and northing of cell (row 0, col 0)
    z_base  world height of z index 0 (metres DHHN2016)
    materials  the legend below
and data/processed/report_<E>_<N>.json, the checks run during the build.

Method (heightfield per column, which suits LoD2 extrusions):
  1. Terrain: every column is solid from z_base up to its DGM1 cell.
  2. Buildings: each roof polygon is rasterized on the 1 m grid by cell-centre
     point-in-polygon; the roof plane gives its height at each cell. The building
     moves by the blueprint clamp dz, then its columns are solid from 2 m below
     the terrain up to the roof.
  3. Materials: roof = top voxel of a building column; wall = building voxel with
     a 4-neighbour column lower than itself (air or lower ground); the rest of a
     building is BUILDING.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dgm_height_clamp import Terrain, clamp_offset, footprint_terrain_min, load_dgm1_xyz  # noqa: E402
from preprocess_citygml import Building, newell_plane, parse_tile, plane_height  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

MATERIALS = {"air": 0, "ground": 1, "building": 2, "wall": 3, "roof": 4}
EXTRUDE_M = 2  # building columns sink this far into the terrain, to hide seams


def _inside(px: np.ndarray, py: np.ndarray, rings_xy: list[np.ndarray]) -> np.ndarray:
    """Even-odd point-in-polygon over all rings (holes subtract)."""
    inside = np.zeros(px.shape, dtype=bool)
    for ring in rings_xy:
        x, y = ring[:, 0], ring[:, 1]
        x2, y2 = np.roll(x, -1), np.roll(y, -1)
        for xi, yi, xj, yj in zip(x, y, x2, y2):
            if yi == yj:
                continue
            crosses = (yi > py) != (yj > py)
            x_at = xi + (py - yi) * (xj - xi) / (yj - yi)
            inside ^= crosses & (px < x_at)
    return inside


def _cells_of_polygon(rings: list[np.ndarray], origin_e: int, origin_n: int,
                      rows: int, cols: int) -> tuple[np.ndarray, np.ndarray]:
    """Grid (row, col) indices of cells whose centres lie inside the polygon, clipped to the grid."""
    ext = rings[0]
    c0 = max(int(np.floor(ext[:, 0].min() - origin_e)), 0)
    c1 = min(int(np.floor(ext[:, 0].max() - origin_e)), cols - 1)
    r0 = max(int(np.floor(ext[:, 1].min() - origin_n)), 0)
    r1 = min(int(np.floor(ext[:, 1].max() - origin_n)), rows - 1)
    if c1 < c0 or r1 < r0:
        return np.empty(0, np.int64), np.empty(0, np.int64)
    cc, rr = np.meshgrid(np.arange(c0, c1 + 1), np.arange(r0, r1 + 1))
    px = origin_e + cc.ravel() + 0.5
    py = origin_n + rr.ravel() + 0.5
    rings_xy = [r[:, :2] for r in rings]
    keep = _inside(px, py, rings_xy)
    return rr.ravel()[keep], cc.ravel()[keep]


def _building_roofs(b: Building, terrain: Terrain) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, bool]:
    """Roof heights over the building's footprint cells, after the clamp.
    Returns (rows, cols, z, dz, has_ground)."""
    rows_all, cols_all, z_all = [], [], []
    for surf in b.of_kind("roof"):
        for poly in surf.polygons:
            try:
                centroid, normal = newell_plane(poly.rings[0])
                rr, cc = _cells_of_polygon(poly.rings, terrain.origin_e, terrain.origin_n, *terrain.shape)
            except ValueError:
                continue
            if rr.size == 0 or abs(normal[2]) < 1e-6:
                continue
            px = terrain.origin_e + cc + 0.5
            py = terrain.origin_n + rr + 0.5
            rows_all.append(rr)
            cols_all.append(cc)
            z_all.append(plane_height(centroid, normal, px, py))
    if not rows_all:
        return np.empty(0, np.int64), np.empty(0, np.int64), np.empty(0), 0.0, False

    rows = np.concatenate(rows_all)
    cols = np.concatenate(cols_all)
    z = np.concatenate(z_all)

    ground_zs = [r[:, 2] for s in b.of_kind("ground") for p in s.polygons for r in p.rings]
    has_ground = bool(ground_zs)
    if has_ground:
        dz = clamp_offset(footprint_terrain_min(terrain, rows, cols), float(np.concatenate(ground_zs).min()))
    else:
        dz = 0.0
    return rows, cols, z + dz, dz, has_ground


def build(e_km: int, n_km: int, rows: int = 1000, cols: int = 1000) -> dict:
    tile = f"{e_km}_{n_km}"
    origin_e, origin_n = e_km * 1000, n_km * 1000

    dgm_files = sorted((RAW / "dgm1" / tile).glob("*.xyz"))
    lod2_files = sorted((RAW / "lod2_citygml" / tile).glob("*.xml"))
    if len(dgm_files) != 1 or not lod2_files:
        raise SystemExit(f"expected one DGM1 .xyz and LoD2 .xml under {tile}; run fetch_open_data.py first")

    # DGM1 ATOM files are 2 km x 2 km; the LoD2 tile is 1 km. Load the whole DGM
    # file, then crop to the test window (the grid's south-west corner is the tile corner).
    terrain = load_dgm1_xyz(dgm_files[0], origin_e, origin_n, 2000, 2000).crop(rows, cols)
    z_base = int(np.floor(terrain.z.min())) - EXTRUDE_M
    t_idx = np.floor(terrain.z - z_base).astype(np.int64)  # surface voxel of the terrain

    buildings: list[Building] = []
    for f in lod2_files:
        buildings += parse_tile(f)

    top_z = np.full((rows, cols), -np.inf)
    dzs, no_ground, no_cells = [], 0, 0
    for b in buildings:
        rr, cc, zz, dz, has_ground = _building_roofs(b, terrain)
        if rr.size == 0:
            no_cells += 1
            continue
        no_ground += not has_ground
        dzs.append(dz)
        np.maximum.at(top_z, (rr, cc), zz)

    has_b = np.isfinite(top_z)
    b_idx = np.where(has_b, np.floor(np.where(has_b, top_z, 0) - z_base), -1).astype(np.int64)
    top_idx = np.where(has_b, np.maximum(b_idx, t_idx), t_idx)
    extrude_idx = t_idx - EXTRUDE_M  # first building voxel of a building column

    nz = int(top_idx.max()) + 1
    k = np.arange(nz, dtype=np.int64)[:, None, None]

    vox = np.zeros((nz, rows, cols), dtype=np.uint8)
    vox[k <= t_idx[None]] = MATERIALS["ground"]

    bcol = has_b[None] & (k >= extrude_idx[None]) & (k <= top_idx[None])
    vox[bcol] = MATERIALS["building"]

    # Wall: a building voxel with at least one 4-neighbour column whose top is lower.
    padded = np.pad(top_idx, 1, constant_values=-1)  # outside the tile counts as air
    exposed = np.zeros(vox.shape, dtype=bool)
    for nb in (padded[:-2, 1:-1], padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]):
        exposed |= k > nb[None]
    vox[bcol & exposed & (k < top_idx[None])] = MATERIALS["wall"]
    vox[(k == top_idx[None]) & has_b[None]] = MATERIALS["roof"]

    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / f"voxels_{tile}.npz"
    np.savez_compressed(
        out,
        voxels=vox,
        origin_e=origin_e,
        origin_n=origin_n,
        z_base=z_base,
        cell_m=1,
        materials=np.array(list(MATERIALS)),
    )

    dz_arr = np.array(dzs)
    counts = {name: int((vox == v).sum()) for name, v in MATERIALS.items()}
    report = {
        "tile": tile,
        "grid": {"cols": cols, "rows": rows, "nz": nz, "z_base_m": z_base,
                 "z_top_m": z_base + nz},
        "terrain_m": {"min": round(float(terrain.z.min()), 2), "max": round(float(terrain.z.max()), 2)},
        "buildings": {"total": len(buildings), "placed": len(dzs), "without_roof_cells": no_cells,
                      "without_ground_surface": no_ground},
        "clamp_dz_m": {
            "min": round(float(dz_arr.min()), 2),
            "median": round(float(np.median(dz_arr)), 2),
            "max": round(float(dz_arr.max()), 2),
            "abs_over_1m": int((np.abs(dz_arr) > 1).sum()),
            "abs_over_3m": int((np.abs(dz_arr) > 3).sum()),
        } if dz_arr.size else {},
        "voxel_counts": counts,
        "output": str(out.relative_to(ROOT)),
    }
    (PROCESSED / f"report_{tile}.json").write_text(json.dumps(report, indent=2))
    return report


def main(argv: list[str]) -> int:
    e_km, n_km = 392, 5820  # Alexanderplatz test tile
    if argv:
        e_km, n_km = (int(v) for v in argv[0].split(","))
    report = build(e_km, n_km)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
