"""Check the mesher against brute force on random volumes.

Each quad is expanded back into unit faces, and the set of (voxel x, y, z, normal, material)
must equal the set of exposed faces found by looking at every voxel directly.
Run: python pipeline/test_mesher.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import greedy_mesher as gm  # noqa: E402

# normal id -> (xyz axis, positive?)
NORMALS = {0: (0, True), 1: (0, False), 2: (1, True), 3: (1, False), 4: (2, True), 5: (2, False)}


def brute_faces(vox: np.ndarray) -> set:
    out = set()
    nz, ny, nx = vox.shape
    for axis, sign, nid in gm.DIRECTIONS:
        f = gm.exposed_faces(vox, axis, sign)
        zs, ys, xs = np.nonzero(f)
        for z, y, x in zip(zs, ys, xs):
            out.add((int(x), int(y), int(z), nid, int(f[z, y, x])))
    return out


def decode(records: np.ndarray) -> tuple[set, int]:
    out = set()
    area = 0
    recs = np.frombuffer(records.tobytes(), dtype=gm.RECORD)
    for r in recs:
        axis, pos = NORMALS[int(r["n"])]
        w, h = int(r["w"]), int(r["h"])
        area += w * h
        xyz = [int(r["x"]), int(r["y"]), int(r["z"])]
        voxel = list(xyz)
        if pos:
            voxel[axis] -= 1
        t0, t1 = [a for a in range(3) if a != axis]
        for i in range(w):
            for j in range(h):
                v = list(voxel)
                v[t0] += i
                v[t1] += j
                out.add((v[0], v[1], v[2], int(r["n"]), int(r["m"])))
    return out, area


def random_volume(rng: np.random.Generator, shape: tuple[int, int, int]) -> np.ndarray:
    nz, ny, nx = shape
    vox = np.zeros(shape, np.uint8)
    for _ in range(12):
        z0, y0, x0 = (int(rng.integers(0, n)) for n in shape)
        dz, dy, dx = (int(rng.integers(1, n // 2 + 2)) for n in shape)
        vox[z0:z0 + dz, y0:y0 + dy, x0:x0 + dx] = int(rng.integers(1, 9))
    return vox


def run(seed: int, shape: tuple[int, int, int]) -> None:
    rng = np.random.default_rng(seed)
    vox = random_volume(rng, shape)
    expected = brute_faces(vox)
    got = set()
    area = 0
    # chunks cover the tile in 64 m blocks; shrink the chunk size for small test volumes
    old = gm.CHUNK
    gm.CHUNK = 8
    try:
        ny, nx = shape[1], shape[2]
        for cy in range((ny + gm.CHUNK - 1) // gm.CHUNK):
            for cx in range((nx + gm.CHUNK - 1) // gm.CHUNK):
                faces, a = decode(gm.chunk_records(vox, cx, cy))
                assert not (got & faces), "a face was emitted by two chunks"
                got |= faces
                area += a
    finally:
        gm.CHUNK = old
    assert got == expected, f"seed {seed}: missing {len(expected - got)}, extra {len(got - expected)}"
    assert area == len(expected), f"seed {seed}: quad area {area} != faces {len(expected)}"
    print(f"seed {seed} {shape}: {len(expected)} faces, quads cover them exactly")


if __name__ == "__main__":
    for seed, shape in [(1, (6, 10, 12)), (2, (9, 17, 15)), (3, (12, 24, 20)), (4, (4, 8, 8))]:
        run(seed, shape)
    print("all mesher checks passed")
