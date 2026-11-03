"""Landmark corrections on top of LoD2 (Sprint 2).

Fernsehturm: the LoD2 model tops out at 287 m, but the real spire reaches 368 m
(antenna tip). The thin antenna is under-sampled in the LiDAR-based model, so we extend
the tower column to 368 m with a 1-voxel needle and put a red beacon at the tip.

Anchor: the blueprint gives (392800, 5820400), which is Alexanderplatz. The tower in the
LoD2 data is at (392081, 5820156): the tallest building within 80 m of that point is the
287 m column there. The coordinates below are from the data plus a WGS84 to ETRS89 UTM 33N
conversion of 52.520815 N, 13.409419 E.
"""

from __future__ import annotations

import math

import numpy as np

from materials import MATERIALS

FERNSEHTURM_E = 392081.1
FERNSEHTURM_N = 5820156.2
FERNSEHTURM_TOP_M = 368.0


def apply_fernsehturm(vox: np.ndarray, z_base: int, origin_e: int, origin_n: int) -> tuple[np.ndarray, dict]:
    """Extend the tower column to FERNSEHTURM_TOP_M. Returns the (possibly taller) matrix
    and a report. Only air is written, so the existing tower is kept as it is."""
    row = math.floor(FERNSEHTURM_N - origin_n)
    col = math.floor(FERNSEHTURM_E - origin_e)
    rows, cols = vox.shape[1], vox.shape[2]
    if not (0 <= row < rows and 0 <= col < cols):
        return vox, {"status": "outside tile"}

    column = vox[:, row, col]
    solid = np.flatnonzero(column)
    if solid.size == 0:
        return vox, {"status": "no solid voxels in tower column"}
    top_now = int(solid[-1])
    top_idx = int(round(FERNSEHTURM_TOP_M)) - z_base

    if top_idx >= vox.shape[0]:
        pad = np.zeros((top_idx + 1 - vox.shape[0], rows, cols), dtype=vox.dtype)
        vox = np.concatenate([vox, pad], axis=0)

    if top_idx > top_now:
        vox[top_now + 1: top_idx, row, col] = MATERIALS["building"]
        vox[top_idx, row, col] = MATERIALS["beacon"]
    return vox, {
        "status": "extended",
        "lod2_top_m": z_base + top_now + 1,
        "tip_m": z_base + top_idx,  # the beacon voxel covers [tip_m, tip_m + 1)
        "cell": [row, col],
    }
