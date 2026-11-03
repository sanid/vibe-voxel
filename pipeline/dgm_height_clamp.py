"""DGM1 terrain grid and per-building height clamping (Sprint 1).

The DGM1 XYZ file is a regular 1 m grid. Points sit at cell centres (x.5, y.5),
x varies fastest, so it loads straight into a 2D array terrain[row, col] with
row = northing index and col = easting index.

Clamp (blueprint phase 2): for each building,
    terrain_min   = min DGM1 over its footprint cells
    building_min  = min z over its GroundSurface vertices
    dz            = terrain_min - building_min
and every roof vertex moves by dz, so the foundation sits on the terrain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class Terrain:
    """A DGM1 grid aligned to 1 m cells. Cell (row, col) has its centre at
    (origin_e + col + 0.5, origin_n + row + 0.5)."""

    z: np.ndarray  # (rows, cols) float64, metres DHHN2016 NH
    origin_e: int
    origin_n: int

    @property
    def shape(self) -> tuple[int, int]:
        return self.z.shape

    def crop(self, rows: int, cols: int) -> "Terrain":
        """The north-east-most window anchored at the grid origin (south-west corner)."""
        return Terrain(z=self.z[:rows, :cols].copy(), origin_e=self.origin_e, origin_n=self.origin_n)

    def cell_of(self, e: float, n: float) -> tuple[int, int]:
        return int(np.floor(n - self.origin_n)), int(np.floor(e - self.origin_e))


def load_dgm1_xyz(path: Path, origin_e: int, origin_n: int, rows: int, cols: int) -> Terrain:
    """Read an XYZ dump of a 1 m DGM1 tile into a grid. Fails if any cell is missing."""
    pts = np.loadtxt(path, dtype=np.float64, ndmin=2)
    if pts.shape[1] != 3:
        raise ValueError(f"{path.name}: expected 3 columns, got {pts.shape[1]}")
    col = np.floor(pts[:, 0] - origin_e).astype(np.int64)
    row = np.floor(pts[:, 1] - origin_n).astype(np.int64)
    if col.min() < 0 or row.min() < 0 or col.max() >= cols or row.max() >= rows:
        raise ValueError(f"{path.name}: points fall outside the {cols} x {rows} grid")
    z = np.full((rows, cols), np.nan)
    z[row, col] = pts[:, 2]
    missing = int(np.isnan(z).sum())
    if missing:
        raise ValueError(f"{path.name}: {missing} grid cells have no elevation")
    return Terrain(z=z, origin_e=origin_e, origin_n=origin_n)


def footprint_terrain_min(terrain: Terrain, rows: np.ndarray, cols: np.ndarray) -> float:
    """Lowest DGM1 value over the given footprint cells."""
    return float(terrain.z[rows, cols].min())


def clamp_offset(terrain_min: float, ground_min: float) -> float:
    """dz that moves a building's ground surface onto the terrain."""
    return terrain_min - ground_min
