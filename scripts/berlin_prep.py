"""Berlin's prep.py: DOM1 (surface), DGM1 (terrain) and TrueDOP 2024 onto the rotated AOI grid (CITY=berlin).

Same output as scripts/prep.py for Warsaw, so voxelize.py reads Berlin unchanged: data/prep.npz with
  dsm  (2D, 2W) float32  surface at 0.5 m   (DOM1 is 1 m: nearest neighbour, so walls stay walls)
  dtm  (D, W)   float32  terrain at 1 m     (bilinear)
  orto (5D, 5W, 3) uint8 colour at 0.2 m    (TrueDOP 2024 is 0.2 m: bilinear)
The XYZ files hold one point per 1 m cell centre (x.5, y.5), x fastest; heights DHHN2016.
"""
import glob
import json
import math

import numpy as np
from PIL import Image
from scipy import ndimage

from aoi import CITY, D, RAW, W, to_world, world_bounds

assert CITY == "berlin"
Image.MAX_IMAGE_PIXELS = None
MINX, MINY, MAXX, MAXY = (math.floor(v) if i < 2 else math.ceil(v) for i, v in enumerate(world_bounds(margin=10)))
NX, NY = MAXX - MINX, MAXY - MINY


def mosaic_xyz(pattern):
    """Cell-centre XYZ tiles -> one north-up 1 m raster over the AOI bounds (row 0 = north), NaN where absent."""
    out = np.full((NY, NX), np.nan, np.float32)
    for p in sorted(glob.glob(f"{RAW}/{pattern}")):
        a = np.fromfile(p, sep=" ", dtype=np.float64).reshape(-1, 3)
        c = np.floor(a[:, 0] - MINX).astype(np.int64)
        r = np.floor(MAXY - a[:, 1]).astype(np.int64)
        k = (c >= 0) & (c < NX) & (r >= 0) & (r < NY)
        out[r[k], c[k]] = a[k, 2]
        print(f"  {p.split('/')[-1]}: {int(k.sum())} points in the AOI")
    miss = int(np.isnan(out).sum())
    if miss:
        print(f"  {miss} cells without data, filled from the nearest")
        _, (ir, ic) = ndimage.distance_transform_edt(np.isnan(out), return_indices=True)
        out = out[ir, ic]
    return out


def mosaic_truedop():
    """TrueDOP JPEG tiles (bounds in index.json) -> one north-up 0.2 m RGB raster over the AOI bounds."""
    res = 0.2
    out = np.zeros((round(NY / res), round(NX / res), 3), np.uint8)
    for t in json.load(open(f"{RAW}/truedop/index.json")):
        x0, y0, x1, y1 = t["bounds"]
        im = np.asarray(Image.open(f"{RAW}/truedop/{t['file']}").convert("RGB"))
        # tile pixel (row 0 = y1) -> output pixel
        oc0, or0 = round((x0 - MINX) / res), round((MAXY - y1) / res)
        a0r, a0c = max(0, -or0), max(0, -oc0)
        b0r, b0c = max(0, or0), max(0, oc0)
        h = min(im.shape[0] - a0r, out.shape[0] - b0r)
        w = min(im.shape[1] - a0c, out.shape[1] - b0c)
        if h > 0 and w > 0:
            out[b0r:b0r + h, b0c:b0c + w] = im[a0r:a0r + h, a0c:a0c + w]
    print(f"  truedop mosaic {out.shape}, empty px {int((out.sum(-1) == 0).sum())}")
    return out


def resample(src, src_res, out_res, order, band=1024):
    """As prep.py: sample the north-up raster (origin MINX, MAXY) on the rotated grid, in row bands."""
    nj, ni = round(D / out_res), round(W / out_res)
    out = np.empty((nj, ni) + src.shape[2:], src.dtype)
    for j0 in range(0, nj, band):
        jj, ii = np.mgrid[j0:min(j0 + band, nj), 0:ni].astype(np.float64)
        x, y = to_world((ii + 0.5) * out_res, (jj + 0.5) * out_res)
        col = (x - MINX) / src_res - 0.5
        row = (MAXY - y) / src_res - 0.5
        if src.ndim == 2:
            out[j0:j0 + band] = ndimage.map_coordinates(src, [row, col], order=order, mode="nearest")
        else:
            for k in range(src.shape[-1]):
                out[j0:j0 + band, :, k] = ndimage.map_coordinates(src[..., k], [row, col], order=order, mode="nearest")
    return out


print("DOM1")
dom = mosaic_xyz("dom1/*.txt")
dsm = resample(dom, 1.0, 0.5, order=0)
del dom
print("DGM1")
dgm = mosaic_xyz("dgm1/*.xyz")
dtm = resample(dgm, 1.0, 1.0, order=1)
del dgm
# the surface is never under the terrain (image matching over water and under bridges can dip below it)
dsm = np.maximum(dsm, np.repeat(np.repeat(dtm, 2, 0), 2, 1))
for n, a in (("dsm", dsm), ("dtm", dtm)):
    print(n, a.shape, float(a.min()), float(a.max()))
print("TrueDOP")
orto = resample(mosaic_truedop(), 0.2, 0.2, order=1)
print("orto", orto.shape, orto.reshape(-1, 3).mean(0))
np.savez_compressed("data/prep.npz", dsm=dsm.astype(np.float32), dtm=dtm.astype(np.float32), orto=orto)
Image.fromarray(orto[::4, ::4]).save("data/orto_preview.jpg", quality=85)
print("done")
