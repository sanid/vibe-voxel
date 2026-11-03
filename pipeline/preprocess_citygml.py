"""Parse LoD2 CityGML tiles into per-building surface records (Sprint 1).

Berlin LoD2 files are CityGML 1.0 in EPSG:25833 with DHHN2016 normal heights.
Each building carries RoofSurface, WallSurface, GroundSurface and ClosureSurface
members, each a set of planar polygons. We keep the polygons as coordinate
arrays; the voxelizer rasterizes them. cjio is not used: a direct parse gives
the same polygons without adding a dependency.

Usage (checks one tile and prints a summary):
    python pipeline/preprocess_citygml.py data/raw/lod2_citygml/392_5820/*.xml
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

NS_BLDG = "{http://www.opengis.net/citygml/building/1.0}"
NS_GML = "{http://www.opengis.net/gml}"

SURFACE_KINDS = {
    "RoofSurface": "roof",
    "WallSurface": "wall",
    "GroundSurface": "ground",
    "ClosureSurface": "closure",
}


@dataclass
class Polygon:
    """A planar polygon. rings[0] is the exterior ring, the rest are holes.
    Each ring is an (n, 3) float array of ETRS89 / UTM 33N x, y and DHHN2016 z."""

    rings: list[np.ndarray]


@dataclass
class Surface:
    kind: str  # roof | wall | ground | closure
    polygons: list[Polygon] = field(default_factory=list)


@dataclass
class Building:
    gml_id: str
    surfaces: list[Surface] = field(default_factory=list)

    def of_kind(self, kind: str) -> list[Surface]:
        return [s for s in self.surfaces if s.kind == kind]


def _pos_list(el: ET.Element) -> np.ndarray:
    """Read a gml:posList (or gml:pos) into an (n, 3) array."""
    pl = el.find(f"{NS_GML}posList")
    if pl is not None and pl.text:
        values = np.array(pl.text.split(), dtype=np.float64)
    else:
        values = np.array(
            [float(v) for p in el.iter(f"{NS_GML}pos") for v in (p.text or "").split()],
            dtype=np.float64,
        )
    if values.size == 0 or values.size % 3:
        raise ValueError("posList is empty or not a multiple of 3")
    return values.reshape(-1, 3)


def _polygons_in(surface_el: ET.Element) -> list[Polygon]:
    polys = []
    for poly_el in surface_el.iter(f"{NS_GML}Polygon"):
        rings = []
        ext = poly_el.find(f"{NS_GML}exterior/{NS_GML}LinearRing")
        if ext is None:
            continue
        rings.append(_pos_list(ext))
        for inn in poly_el.findall(f"{NS_GML}interior/{NS_GML}LinearRing"):
            rings.append(_pos_list(inn))
        polys.append(Polygon(rings=rings))
    return polys


def parse_tile(path: Path) -> list[Building]:
    """Return every building in one CityGML tile."""
    root = ET.parse(path).getroot()
    buildings = []
    for b_el in root.iter(f"{NS_BLDG}Building"):
        b = Building(gml_id=b_el.get("{http://www.opengis.net/gml}id", ""))
        for el in b_el.iter():
            local = el.tag.rsplit("}", 1)[-1]
            kind = SURFACE_KINDS.get(local)
            if kind is None:
                continue
            surf = Surface(kind=kind, polygons=_polygons_in(el))
            if surf.polygons:
                b.surfaces.append(surf)
        buildings.append(b)
    return buildings


def newell_plane(ring: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Least-squares-free plane of a planar ring (Newell's method).
    Returns (centroid, unit normal)."""
    p = ring[:-1] if np.allclose(ring[0], ring[-1]) else ring
    n = np.zeros(3)
    q = np.roll(p, -1, axis=0)
    n[0] = np.sum((p[:, 1] - q[:, 1]) * (p[:, 2] + q[:, 2]))
    n[1] = np.sum((p[:, 2] - q[:, 2]) * (p[:, 0] + q[:, 0]))
    n[2] = np.sum((p[:, 0] - q[:, 0]) * (p[:, 1] + q[:, 1]))
    norm = np.linalg.norm(n)
    if norm == 0:
        raise ValueError("degenerate ring")
    return p.mean(axis=0), n / norm


def plane_height(centroid: np.ndarray, normal: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Height of a non-vertical plane at (x, y)."""
    nz = normal[2]
    if abs(nz) < 1e-6:
        raise ValueError("vertical plane has no height field")
    return centroid[2] - (normal[0] * (x - centroid[0]) + normal[1] * (y - centroid[1])) / nz


def planarity_error(ring: np.ndarray) -> float:
    """Largest distance of a ring's vertices from its best-fit plane, in metres."""
    c, n = newell_plane(ring)
    return float(np.max(np.abs((ring - c) @ n)))


def check_tile(buildings: list[Building]) -> dict:
    """Boundary checks used before voxelizing (the 'verify XML boundary surfaces' step)."""
    counts = {"roof": 0, "wall": 0, "ground": 0, "closure": 0}
    no_roof = no_ground = 0
    worst_planarity = 0.0
    for b in buildings:
        kinds = {s.kind for s in b.surfaces}
        no_roof += "roof" not in kinds
        no_ground += "ground" not in kinds
        for s in b.surfaces:
            counts[s.kind] += len(s.polygons)
            if s.kind == "roof":
                for poly in s.polygons:
                    worst_planarity = max(worst_planarity, planarity_error(poly.rings[0]))
    return {
        "buildings": len(buildings),
        "polygons": counts,
        "buildings_without_roof": no_roof,
        "buildings_without_ground": no_ground,
        "worst_roof_planarity_m": round(worst_planarity, 3),
    }


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    all_b: list[Building] = []
    for p in argv:
        all_b += parse_tile(Path(p))
    summary = check_tile(all_b)
    for k, v in summary.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
