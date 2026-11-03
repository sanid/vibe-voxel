"""Tree voxels from the Berlin Baumbestand inventory (Sprint 2).

Each tree is a 1-voxel trunk with an ellipsoid crown (blueprint phase 3):
    trunk_h  = max(2, round(0.35 * height))
    crown    = ellipsoid, radii (crown_d / 2, crown_d / 2, (height - trunk_h) / 2),
               centred between the trunk top and the tree top
Trees only fill air, so they never overwrite buildings or terrain.
Inputs: street trees (strassenbaeume) and park trees (anlagenbaeume), WFS 2.0 GeoJSON
from gdi.berlin.de; fetched by fetch_open_data.py.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from materials import CROWN_BY_GENUS, MATERIALS

MIN_HEIGHT_M = 2.0
MAX_HEIGHT_M = 40.0  # guard against bad inventory values


@dataclass
class Tree:
    x: float
    y: float
    height: float
    crown_d: float
    genus: str


def load_trees(paths: list[Path]) -> list[Tree]:
    trees = []
    for p in paths:
        for f in json.loads(p.read_text())["features"]:
            props = f["properties"]
            x, y = f["geometry"]["coordinates"]
            h, d = props.get("baumhoehe"), props.get("kronedurch")
            if not h or not d:
                continue
            trees.append(Tree(x=x, y=y, height=float(h), crown_d=float(d), genus=props.get("gattung") or ""))
    return trees


def add_trees(vox: np.ndarray, ground_idx: np.ndarray, origin_e: int, origin_n: int,
              trees: list[Tree]) -> dict:
    """Write trees into vox[z, row, col] in place. ground_idx[row, col] is the terrain
    surface voxel. Returns counts for the report."""
    nz, rows, cols = vox.shape
    placed = skipped_outside = skipped_blocked = 0
    for t in trees:
        col = math.floor(t.x - origin_e)
        row = math.floor(t.y - origin_n)
        if not (0 <= row < rows and 0 <= col < cols):
            skipped_outside += 1
            continue
        g = int(ground_idx[row, col])
        h = min(max(t.height, MIN_HEIGHT_M), MAX_HEIGHT_M)
        trunk_h = max(2, round(0.35 * h))
        if g + 1 >= nz or vox[g + 1, row, col] != 0:
            skipped_blocked += 1
            continue

        # trunk: from the air above the terrain up to the crown's bottom
        vox[g + 1: g + trunk_h + 1, row, col] = MATERIALS["trunk"]

        rx = max(1.0, t.crown_d / 2)
        rz = max(1.0, (h - trunk_h) / 2)
        cz = g + trunk_h + rz  # crown centre, in voxel-index units (cell centres are +0.5)
        ext_x, ext_z = math.ceil(rx), math.ceil(rz)
        z0, z1 = max(0, int(cz - rz) - 1), min(nz, int(math.ceil(cz + rz)) + 2)
        r0, r1 = max(0, row - ext_x), min(rows, row + ext_x + 1)
        c0, c1 = max(0, col - ext_x), min(cols, col + ext_x + 1)
        zz = np.arange(z0, z1) + 0.5 - cz
        yy = np.arange(r0, r1) + 0.5 - (row + 0.5)
        xx = np.arange(c0, c1) + 0.5 - (col + 0.5)
        inside = ((zz[:, None, None] / rz) ** 2
                  + (yy[None, :, None] / rx) ** 2
                  + (xx[None, None, :] / rx) ** 2) <= 1.0
        block = vox[z0:z1, r0:r1, c0:c1]
        mat = MATERIALS[CROWN_BY_GENUS.get(t.genus, "crown_other")]
        block[inside & (block == 0)] = mat
        placed += 1
    return {"placed": placed, "outside_tile": skipped_outside, "blocked": skipped_blocked}
