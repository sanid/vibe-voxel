"""Exposed-face quads and binary chunks from the voxel matrix (Sprint 2).

Steps:
  1. For each of the six directions, keep the faces of solid voxels whose
     neighbour is air. Outside the tile counts as air.
  2. Split the faces into 64 x 64 m chunks (full height), like the blueprint.
  3. Merge each slice's runs of equal material along one tangent axis, then merge
     runs with the same start, length and material across consecutive rows.
     Vectorized: no per-face Python loop. This is not a full 2D greedy merge;
     it is usually close on LoD2 blocks.
  4. Write each chunk as packed 16-byte quads, gzipped.

Quad record (little-endian, 16 bytes):
    x, y, z   u16   voxel index of the solid voxel's min corner in the tile grid
    w, h      u16   size along the two tangent axes
    normal    u8    0 +x, 1 -x, 2 +y, 3 -y, 4 +z, 5 -z
    material  u8    material id (materials.py)
    flags     u16   reserved (0)
    reserved  u16   reserved (0)
The blueprint used u8 for w and h; u16 is needed because a vertical wall can be
270 m tall, so w and h are widened.
"""

from __future__ import annotations

import gzip
import json
import struct
import sys
from pathlib import Path

import numpy as np

from materials import MATERIALS

CHUNK = 64
QUAD = struct.Struct("<HHHHHBBHH")  # x y z w h normal material flags reserved
assert QUAD.size == 16
RECORD = np.dtype([("x", "<u2"), ("y", "<u2"), ("z", "<u2"), ("w", "<u2"), ("h", "<u2"),
                   ("n", "u1"), ("m", "u1"), ("f", "<u2"), ("r", "<u2")])

# (axis in (z, y, x) order, sign). Normal ids follow the record layout above.
DIRECTIONS = [
    (2, +1, 0),  # +x
    (2, -1, 1),  # -x
    (1, +1, 2),  # +y
    (1, -1, 3),  # -y
    (0, +1, 4),  # +z
    (0, -1, 5),  # -z
]


def exposed_faces(vox: np.ndarray, axis: int, sign: int) -> np.ndarray:
    """uint8 array, same shape as vox: material of solid voxels whose neighbour along
    (axis, sign) is air, else 0."""
    pad = [(0, 0)] * 3
    pad[axis] = (1, 1)
    p = np.pad(vox, pad, constant_values=0)
    if sign > 0:
        nb = np.take(p, np.arange(2, vox.shape[axis] + 2), axis=axis)
    else:
        nb = np.take(p, np.arange(0, vox.shape[axis]), axis=axis)
    return np.where((vox > 0) & (nb == 0), vox, 0).astype(np.uint8)


def merge_slices(mat3: np.ndarray) -> tuple[np.ndarray, ...]:
    """Merge a 3D (s, p, q) array of face materials into quads.
    Returns arrays (s, p0, q0, h_p, w_q, material): h_p along p, w_q along q."""
    s_n, p_n, q_n = mat3.shape
    # Pad each row of the q axis with a zero on both ends, so runs never cross rows.
    padded = np.zeros((s_n, p_n, q_n + 2), dtype=np.uint8)
    padded[:, :, 1:-1] = mat3
    flat = padded.reshape(-1)
    prev = np.concatenate(([0], flat[:-1]))
    nxt = np.concatenate((flat[1:], [0]))
    starts = np.flatnonzero((flat != 0) & (flat != prev))
    ends = np.flatnonzero((flat != 0) & (flat != nxt))  # inclusive
    if starts.size == 0:
        empty = np.empty(0, np.int64)
        return empty, empty, empty, empty, empty, np.empty(0, np.uint8)

    row = starts // (q_n + 2)
    s_idx = row // p_n
    p_idx = row % p_n
    q0 = starts % (q_n + 2) - 1
    wq = (ends - starts) + 1
    mat = flat[starts]

    # Merge runs with equal (s, q0, wq, mat) on consecutive p.
    order = np.lexsort((p_idx, mat, wq, q0, s_idx))
    s_idx, p_idx, q0, wq, mat = s_idx[order], p_idx[order], q0[order], wq[order], mat[order]
    new_group = np.ones(s_idx.size, dtype=bool)
    new_group[1:] = ~(
        (s_idx[1:] == s_idx[:-1]) & (q0[1:] == q0[:-1]) & (wq[1:] == wq[:-1])
        & (mat[1:] == mat[:-1]) & (p_idx[1:] == p_idx[:-1] + 1)
    )
    gid = np.cumsum(new_group) - 1
    first = np.flatnonzero(new_group)
    height = np.bincount(gid)
    return s_idx[first], p_idx[first], q0[first], height, wq[first], mat[first]


def mesh_chunk(faces: np.ndarray, normal_id: int, axis: int, origin: tuple[int, int, int]) -> np.ndarray:
    """Quads for one direction over one chunk. faces: (z, y, x) material array
    local to the chunk; origin: global (x, y, z) of its min corner.
    Returns a structured array of QUAD records (as a numpy uint8 buffer)."""
    arr = np.moveaxis(faces, axis, 0)  # (s, p, q) with s along the normal axis
    rest = [a for a in range(3) if a != axis]
    s, p0, q0, h_p, w_q, mat = merge_slices(arr)
    if s.size == 0:
        return np.empty((0, 16), dtype=np.uint8)

    # Work in (x, y, z) global coordinates.
    ox, oy, oz = origin
    base = np.array([ox, oy, oz])  # indexed by x, y, z
    # Local (z, y, x) axes to (x, y, z) indexes: z->2, y->1, x->0.
    to_xyz = {0: 2, 1: 1, 2: 0}
    coord = np.zeros((s.size, 3), dtype=np.int64)
    coord[:, to_xyz[axis]] = s
    coord[:, to_xyz[rest[0]]] = p0
    coord[:, to_xyz[rest[1]]] = q0
    size = np.zeros((s.size, 3), dtype=np.int64)
    size[:, to_xyz[rest[0]]] = h_p
    size[:, to_xyz[rest[1]]] = w_q
    # Positive faces sit on the far side of the voxel.
    if normal_id % 2 == 0:
        coord[:, to_xyz[axis]] += 1

    gxyz = coord + base
    buf = np.zeros(s.size, dtype=RECORD)
    buf["x"], buf["y"], buf["z"] = gxyz[:, 0], gxyz[:, 1], gxyz[:, 2]
    # w spans the lower-index tangent axis of the face, h the higher one (x < y < z).
    tangents = [a for a in range(3) if a != to_xyz[axis]]
    buf["w"] = size[:, tangents[0]]
    buf["h"] = size[:, tangents[1]]
    buf["n"] = normal_id
    buf["m"] = mat
    return buf.view(np.uint8).reshape(-1, 16)


def all_faces(vox: np.ndarray) -> list[np.ndarray]:
    """Exposed-face material arrays for the six directions, computed once per tile."""
    return [exposed_faces(vox, axis, sign) for axis, sign, _ in DIRECTIONS]


def chunk_records(vox: np.ndarray, cx: int, cy: int, faces: list[np.ndarray] | None = None) -> np.ndarray:
    """All quads of one chunk, as an (n, 16) uint8 array. Faces use the full tile, so a
    face on a chunk edge is emitted once, by the chunk that owns the solid voxel."""
    x0, y0 = cx * CHUNK, cy * CHUNK
    x1, y1 = min(x0 + CHUNK, vox.shape[2]), min(y0 + CHUNK, vox.shape[1])
    if faces is None:
        faces = all_faces(vox)
    out = []
    for (axis, _, nid), f in zip(DIRECTIONS, faces):
        out.append(mesh_chunk(f[:, y0:y1, x0:x1], nid, axis, (x0, y0, 0)))
    return np.concatenate(out) if out else np.empty((0, 16), np.uint8)


def write_chunks(vox: np.ndarray, out_dir: Path, z_base: int, origin_e: int, origin_n: int) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    nz, ny, nx = vox.shape
    index = {
        "chunk_m": CHUNK,
        "origin_e": origin_e,
        "origin_n": origin_n,
        "z_base_m": z_base,
        "z_levels": nz,
        "record_bytes": 16,
        "normals": ["+x", "-x", "+y", "-y", "+z", "-z"],
        "chunks": [],
    }
    total_quads = 0
    total_area = 0
    faces = all_faces(vox)
    for cy in range((ny + CHUNK - 1) // CHUNK):
        for cx in range((nx + CHUNK - 1) // CHUNK):
            recs = chunk_records(vox, cx, cy, faces)
            name = f"chunk_{cx}_{cy}.bin.gz"
            with gzip.open(out_dir / name, "wb", compresslevel=9) as f:
                f.write(recs.tobytes())
            n = recs.shape[0]
            total_quads += n
            if n:
                fields = np.frombuffer(recs.tobytes(), dtype=RECORD)
                total_area += int((fields["w"].astype(np.int64) * fields["h"]).sum())
            index["chunks"].append({"cx": cx, "cy": cy, "file": name, "quads": int(n)})
    (out_dir / "index.json").write_text(json.dumps(index, indent=1))
    return {"quads": total_quads, "face_area": total_area, "chunks": len(index["chunks"])}


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    tile = argv[0] if argv else "392_5820"
    d = np.load(root / "data" / "processed" / f"voxels_{tile}.npz")
    vox = d["voxels"]
    stats = write_chunks(vox, root / "data" / "processed" / "chunks" / tile,
                         int(d["z_base"]), int(d["origin_e"]), int(d["origin_n"]))
    print(json.dumps(stats, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
