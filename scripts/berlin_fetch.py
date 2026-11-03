"""Download the Berlin inputs for the voxel build (CITY=berlin, run from cities/berlin/).

Berlin's open data stands in for the Warsaw sources one for one:
  GUGiK NMPT (LiDAR surface, 0.5 m)  ->  DOM1   bildbasiertes Oberflaechenmodell, 1 m, 2 km tiles (FIS-Broker ATOM)
  GUGiK NMT (terrain, 1 m)           ->  DGM1   Digitales Gelaendemodell, 1 m, 2 km tiles (FIS-Broker ATOM)
  GUGiK orthophoto 2025              ->  TrueDOP 2024, 20 cm (gdi.berlin.de WMS truedop_2024): no building lean
  Geofabrik Mazowieckie extract      ->  BBBike Berlin extract (Geofabrik is unreachable from the build box)
  Warsaw tree inventory              ->  Baumbestand Berlin, street and park trees (WFS 2.0)
Licences: dl-de/zero-2-0 (Geoportal Berlin), ODbL (OSM).

Outputs under data/raw/: dom1/*.xyz, dgm1/*.xyz, truedop/*.jpg (+ index.json of their bounds),
osm.json (Overpass-style, via osm_pbf.py), trees/berlin_trees.json.
"""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import requests
from pyproj import Transformer

from aoi import CITY, RAW, world_bounds

assert CITY == "berlin", "run with CITY=berlin from cities/berlin/"
RAWP = Path(RAW)
ATOM = "https://fbinter.stadt-berlin.de/fb/atom"
WMS = "https://gdi.berlin.de/services/wms/truedop_2024"
WFS = "https://gdi.berlin.de/services/wfs/baumbestand"
BBBIKE = "https://download.bbbike.org/osm/bbbike/Berlin/Berlin.osm.pbf"
UA = {"User-Agent": "berlin-vibe-voxel/0.1"}


def get(url, dest, timeout=600):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(4):
        try:
            with requests.get(url, stream=True, timeout=timeout, headers=UA) as r:
                r.raise_for_status()
                with part.open("wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            part.rename(dest)
            return dest
        except requests.RequestException as e:
            print(f"  retry {attempt + 1}: {url}: {e}", file=sys.stderr)
    raise RuntimeError(f"failed: {url}")


def safe_extract(zp, out):
    out.mkdir(parents=True, exist_ok=True)
    root = out.resolve()
    with zipfile.ZipFile(zp) as z:
        for m in z.infolist():
            t = (out / m.filename).resolve()
            if m.is_dir() or root not in t.parents:
                continue
            if not t.exists():
                z.extract(m, out)


x0, y0, x1, y1 = world_bounds(margin=20)
print(f"AOI bounds EPSG:25833 {x0:.0f} {y0:.0f} {x1:.0f} {y1:.0f}")

# DOM1 / DGM1: 2 km tiles named by their even-km south-west corner
for e in range(int(x0 // 2000 * 2), int(x1 // 1000) + 1, 2):
    for n in range(int(y0 // 2000 * 2), int(y1 // 1000) + 1, 2):
        for kind, path in (("dom1", f"DOM/DOM1_{e}_{n}.zip"), ("dgm1", f"DGM1/DGM1_{e}_{n}.zip")):
            zp = get(f"{ATOM}/{path}", RAWP / kind / Path(path).name)
            safe_extract(zp, RAWP / kind)
            print(f"  {kind} {e}_{n}")

# TrueDOP 2024: 800 m tiles at 20 cm (4000 px), JPEG, plus their bounds
TILE, PX = 800, 4000
index = []
ty0, tx0 = int(y0 // TILE) * TILE, int(x0 // TILE) * TILE
for ty in range(ty0, int(y1) + 1, TILE):
    for tx in range(tx0, int(x1) + 1, TILE):
        dest = RAWP / "truedop" / f"truedop_{tx}_{ty}.jpg"
        url = (f"{WMS}?service=WMS&version=1.3.0&request=GetMap&layers=truedop_2024&styles=&crs=EPSG:25833"
               f"&bbox={tx},{ty},{tx + TILE},{ty + TILE}&width={PX}&height={PX}&format=image/jpeg")
        get(url, dest)
        index.append(dict(file=dest.name, bounds=[tx, ty, tx + TILE, ty + TILE], px=PX))
(RAWP / "truedop" / "index.json").write_text(json.dumps(index, indent=1))
print(f"  truedop {len(index)} tiles")

# OSM: the BBBike extract, cut to the AOI + 100 m like fetch_osm.sh does for Warsaw
pbf = get(BBBIKE, RAWP / "osm" / "Berlin.osm.pbf")
t = Transformer.from_crs(25833, 4326, always_xy=True)
bx0, by0, bx1, by1 = world_bounds(margin=100)
p = [t.transform(x, y) for x in (bx0, bx1) for y in (by0, by1)]
bb = "%.4f,%.4f,%.4f,%.4f" % (min(q[1] for q in p), min(q[0] for q in p), max(q[1] for q in p), max(q[0] for q in p))
if not (RAWP / "osm.json").exists():
    script = Path(__file__).with_name("osm_pbf.py")
    subprocess.run(["uv", "run", "--with", "osmium", "python", str(script), str(pbf), bb, str(RAWP / "osm.json")], check=True)
print(f"  osm bbox {bb}")

# Baumbestand: 1 km tiles over the AOI, both layers; each request checked against numberMatched
trees, seen = [], set()
for layer in ("strassenbaeume", "anlagenbaeume"):
    for e in range(int(x0 // 1000), int(x1 // 1000) + 1):
        for n in range(int(y0 // 1000), int(y1 // 1000) + 1):
            q = (f"{WFS}?service=WFS&version=2.0.0&request=GetFeature&typeNames=baumbestand:{layer}"
                 f"&srsName=urn:ogc:def:crs:EPSG::25833&bbox={e * 1000},{n * 1000},{e * 1000 + 1000},{n * 1000 + 1000},"
                 f"urn:ogc:def:crs:EPSG::25833")
            dest = get(q + "&outputFormat=application/json", RAWP / "trees" / f"{layer}_{e}_{n}.json")
            feats = json.loads(dest.read_text())["features"]
            hits = requests.get(q + "&resultType=hits", timeout=120, headers=UA).text
            matched = int(hits.split('numberMatched="')[1].split('"')[0])
            if matched != len(feats):
                raise RuntimeError(f"{dest.name}: {len(feats)} of {matched} features")
            for f in feats:
                gid = f["properties"].get("gisid") or f["id"]
                if gid in seen:
                    continue
                seen.add(gid)
                pr = f["properties"]
                (x, y) = f["geometry"]["coordinates"][:2]
                trees.append(dict(id=gid, x=x, y=y, layer=layer, genus=pr.get("gattung"), species=pr.get("art_bot"),
                                  species_de=pr.get("art_dtsch"), height=pr.get("baumhoehe"),
                                  crown=pr.get("kronedurch"), trunk_cm=pr.get("stammumfg"), planted=pr.get("pflanzjahr")))
(RAWP / "trees" / "berlin_trees.json").write_text(json.dumps(trees, ensure_ascii=False))
print(f"  trees {len(trees)}")
