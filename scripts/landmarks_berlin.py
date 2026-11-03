"""Berlin's curated layer, with the same interface voxelize.py uses for Warsaw's landmarks.py (CITY=berlin).

Labels and camera views for the Mitte map, the Nikolaiviertel as the "historic core" (its 1980s reconstructions are
gabled, plastered in many colours, tiled: the tenement styling Warsaw's Old Town gets), and the Fernsehturm rebuilt as
geometry: the image-matched surface model (DOM1) gets its concrete shaft and sphere roughly, but not the 118 m
antenna, a 3 m mast at most a pixel wide from the air.

Fernsehturm, from the operator's and the Senate's published figures: 368 m to the antenna tip; concrete shaft to
250 m, tapering from 32 m across at its foot to 9 m; the sphere 32 m across, its centre 213 m up (observation deck
203.78 m, restaurant 207.53 m inside its lower half); steel antenna 250-368 m, banded red and white.
"""
import math

import numpy as np
from pyproj import Transformer
from scipy import ndimage
from shapely.geometry import Polygon

import landmarks as _warsaw
from aoi import to_grid

M_SOLID, M_GLASS, M_METAL, M_CONCRETE, M_CLASSIC, M_WINDOW = 0, 2, 6, 13, 20, 21
SOURCES = dict(lidar="Geoportal Berlin DOM1 (image-matched surface, 2021) + DGM1 (terrain), dl-de/zero-2-0",
               ortho="Geoportal Berlin TrueDOP 2024, 20 cm, dl-de/zero-2-0",
               trees="Baumbestand Berlin (Strassen- und Anlagenbaeume), dl-de/zero-2-0")

DECK = None   # set by voxelize.py: the bridge deck tops
PIERS = []    # set by voxelize.py
small_tree = _warsaw.small_tree
label = _warsaw.label

_T = Transformer.from_crs(4326, 25833, always_xy=True)
FT_LATLON = (52.520815, 13.409419)  # the Fernsehturm's axis (matches the TrueDOP 2024 shaft within ~5 m)


def grid_of(lat, lon):
    c, r = to_grid(*_T.transform(lon, lat))
    return float(c), float(r)


# OSM name -> facts (as landmarks.LABELS); `at` (lat, lon) places the label when no OSM area carries the name.
LABELS = {
    "Berliner Fernsehturm": dict(en="TV Tower", kind="TV tower", height=368, year=1969, alt="Fernsehturm Alex",
                                 anchor="top", at=(52.520815, 13.409419)),
    "Brandenburger Tor": dict(en="Brandenburg Gate", kind="city gate", year=1791, by="Carl Gotthard Langhans",
                              at=(52.516275, 13.377704)),
    "Reichstagsgebäude": dict(name="Reichstag", en="Bundestag", kind="parliament", year=1894, rebuilt=1999,
                              alt="Reichstag dome Kuppel Bundestag", anchor="top", at=(52.518589, 13.376665)),
    "Berliner Dom": dict(en="Berlin Cathedral", kind="cathedral", year=1905, anchor="top", at=(52.519067, 13.401106)),
    "Berliner Schloss": dict(name="Humboldt Forum", kind="museum in the rebuilt palace", year=2020,
                             alt="Berliner Schloss Stadtschloss Humboldt Forum", at=(52.5175, 13.4025)),
    "Altes Museum": dict(en="Old Museum", kind="museum", year=1830, by="Karl Friedrich Schinkel", at=(52.519444, 13.398333)),
    "Neues Museum": dict(en="New Museum", kind="museum", year=1855, rebuilt=2009, at=(52.520556, 13.397778)),
    "Pergamonmuseum": dict(kind="museum", year=1930, at=(52.521111, 13.396111)),
    "Bode-Museum": dict(kind="museum", year=1904, anchor="top", at=(52.521944, 13.394722)),
    "Alte Nationalgalerie": dict(en="Old National Gallery", kind="gallery", year=1876, at=(52.520833, 13.398056)),
    "Rotes Rathaus": dict(en="Red Town Hall", kind="town hall", year=1869, anchor="top", at=(52.518498, 13.408539)),
    "Nikolaikirche": dict(en="St Nicholas' Church", kind="church", rebuilt=1987, anchor="top", at=(52.516944, 13.407222)),
    "St. Marienkirche": dict(en="St Mary's Church", kind="church", anchor="top", alt="Marienkirche", at=(52.520833, 13.406944)),
    "Neptunbrunnen": dict(en="Neptune Fountain", kind="fountain", year=1891, at=(52.519444, 13.406389)),
    "Alexanderplatz": dict(kind="square", alt="Alex Weltzeituhr", at=(52.521944, 13.413333)),
    "Gendarmenmarkt": dict(kind="square", at=(52.513667, 13.392722)),
    "Konzerthaus Berlin": dict(name="Konzerthaus", en="Concert Hall", kind="concert hall", year=1821,
                               by="Karl Friedrich Schinkel", at=(52.513611, 13.391944)),
    "Französischer Dom": dict(en="French Cathedral", kind="church", anchor="top", at=(52.514444, 13.392778)),
    "Deutscher Dom": dict(en="German Cathedral", kind="church, exhibition", anchor="top", at=(52.512778, 13.3925)),
    "Staatsoper Unter den Linden": dict(name="Staatsoper", en="State Opera", kind="opera house", year=1742,
                                        at=(52.516667, 13.395)),
    "Neue Wache": dict(kind="memorial", year=1818, by="Karl Friedrich Schinkel", at=(52.517778, 13.395556)),
    "Zeughaus": dict(en="Arsenal, German Historical Museum", kind="museum", year=1706, alt="Deutsches Historisches Museum DHM",
                     at=(52.517778, 13.396944)),
    "St. Hedwigs-Kathedrale": dict(en="St Hedwig's Cathedral", kind="cathedral", year=1773, at=(52.515833, 13.394722)),
    "Bebelplatz": dict(kind="square", at=(52.516389, 13.393889)),
    "Pariser Platz": dict(kind="square", at=(52.516389, 13.378889)),
    "Lustgarten": dict(kind="park", at=(52.518889, 13.399444)),
}
EXTRA_LABELS = {
    "Spree": dict(kind="river", at="river"),
    "Museumsinsel": dict(en="Museum Island", kind="UNESCO World Heritage museums", alt="Museum Island",
                         at=(52.5205, 13.3975)),
    "Nikolaiviertel": dict(kind="old quarter, rebuilt 1987", at=(52.5163, 13.4069)),
}

# The Nikolaiviertel between the Spree, the Muehlendamm, Spandauer Str. and Rathausstr. (TrueDOP 2024)
NIKOLAIVIERTEL = [(52.51790, 13.40455), (52.51800, 13.40755), (52.51735, 13.40905), (52.51580, 13.40930),
                  (52.51545, 13.40750), (52.51585, 13.40510)]


def historic_core():
    return Polygon([grid_of(la, lo) for la, lo in NIKOLAIVIERTEL])


def adjust_heights(top, feats, note):
    """Around the Fernsehturm only its pavilion stands (the folded roofs, ~13 m): the image-matched surface smeared the
    shaft onto them, a 3 x 3 m column to 124 m 41 m north of the axis. Cells 19-75 m from the axis are capped at 16 m
    (the shaft and sphere inside 19 m are rebuilt in details())."""
    cx, cy = grid_of(*FT_LATLON)
    D, W = top.shape
    r0, r1, c0, c1 = max(int(cy) - 76, 0), min(int(cy) + 77, D), max(int(cx) - 76, 0), min(int(cx) + 77, W)
    rr, cc = np.mgrid[r0:r1, c0:c1]
    d = np.hypot(rr + 0.5 - cy, cc + 0.5 - cx)
    sub = top[r0:r1, c0:c1]
    m = (d > 19) & (d < 75) & (sub > 16)
    sub[m] = 16
    note(f"Fernsehturm surroundings: {int(m.sum())} smeared cells capped at the pavilion's 16 m")


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# The landmarks' own materials where OSM gives none (or a near-black tag): sandstone masonry with the plain "classic"
# shading (no office window grid), copper roofs gone green (Commons photos; TrueDOP 2024 for the roofs).
SANDSTONE, SANDSTONE_L, COPPER = "#cbbc9c", "#d8ccb1", "#6e9b88"
STYLES = {
    "Berliner Dom": (SANDSTONE, COPPER),
    "Reichstagsgebäude": ("#c9bc9f", None),
    "Brandenburger Tor": (SANDSTONE_L, SANDSTONE_L),  # the attic is stone; the Quadriga is drawn in copper on it
    "Berliner Schloss": ("#d6c2a2", "#878a8e"),  # OSM's roof #727682 graded to lavender; the TrueDOP roofs read slate grey
    "Altes Museum": (SANDSTONE_L, None),
    "Neues Museum": ("#cdbf9f", None),
    "Pergamonmuseum": (SANDSTONE, None),
    "Bode-Museum": ("#c7b99b", COPPER),
    "Alte Nationalgalerie": ("#c9b99a", None),
    "Konzerthaus Berlin": (SANDSTONE_L, COPPER),
    "Französischer Dom": (SANDSTONE_L, COPPER),
    "Deutscher Dom": (SANDSTONE_L, COPPER),
    "St. Hedwigs-Kathedrale": (SANDSTONE_L, COPPER),
    "Staatsoper Unter den Linden": ("#e1c7b3", None),
    "Zeughaus": ("#dcc3ad", None),
    "Neue Wache": (SANDSTONE_L, None),
}


def _style(f):
    return STYLES.get(_warsaw._name(f) or "")


def wall_override(f, pal):
    s = _style(f)
    return pal(_hex(s[0]), M_CLASSIC) if s else None


def roof_override(f, pal):
    s = _style(f)
    return pal(_hex(s[1]), 12, q=12) if s and s[1] else None


def apply_zones(vol, g, feats, pal, bmask, note):
    return None


def apply_stripes(vol, g, bmask, pal, osm, cells_of, note):
    return []  # floodlit pitches: none mapped in the AOI


# ---------------------------------------------------------------- the Fernsehturm


def fernsehturm(vol, g, pal, note):
    """Shaft, sphere and antenna as geometry, centred on the tower's published position; the pavilion at its foot
    (the folded roofs, up to ~13 m) stays as the surface model has it. Everything else within 19 m of the axis above
    13 m is cleared first: the matched surface smeared the shaft and the sphere's shadow side."""
    cx, cy = grid_of(*FT_LATLON)
    r0, c0 = int(cy), int(cx)
    D, W = g.shape
    if not (25 <= r0 < D - 25 and 25 <= c0 < W - 25):
        note("Fernsehturm: outside the map")
        return None
    gz = int(np.median(g[r0 - 20:r0 + 21, c0 - 20:c0 + 21]))
    H = vol.shape[0]
    need = gz + 369
    if need > H:
        note(f"Fernsehturm: volume too low ({H} < {need})")
        return None
    concrete = pal((214, 211, 203), M_SOLID)
    # the sphere's steel facets as plain light greys (the metal shading mirrored the dark sky: a black ball at dusk);
    # the antenna's red bands stay metal, which the shader lights red at night like the obstruction lamps
    steel = pal((196, 201, 206), M_SOLID)
    steel_d = pal((168, 175, 182), M_SOLID)
    band = pal((58, 70, 78), M_WINDOW)
    red = pal((196, 52, 40), M_METAL)
    white = pal((236, 234, 228), M_SOLID)
    rr, cc = np.mgrid[r0 - 20:r0 + 21, c0 - 20:c0 + 21]
    d = np.hypot(rr + 0.5 - cy, cc + 0.5 - cx)
    blk = vol[gz + 13:, r0 - 20:r0 + 21, c0 - 20:c0 + 21]
    blk[:, d <= 19] = 0
    n = 0
    for z in range(13, 369):
        zz = gz + z
        if z < 250:  # the shaft, a cone 32 m -> 9 m across
            rad = 16.0 - (16.0 - 4.5) * z / 250.0
            m = d <= rad
            vol[zz, rr[m], cc[m]] = concrete
            n += int(m.sum())
        dz = z + 0.5 - 213.0
        if abs(dz) <= 16.0:  # the sphere
            rad = math.sqrt(16.0 ** 2 - dz ** 2)
            shell = (d <= rad) & (d > rad - 2.2)
            col = band if -11.5 <= dz <= -4.5 else (steel if (int(z) // 3) % 2 else steel_d)
            vol[zz, rr[shell], cc[shell]] = col
            inner = d <= rad - 2.2
            vol[zz, rr[inner], cc[inner]] = concrete
            n += int((d <= rad).sum())
        if z >= 250:  # the antenna: 3 m to 300 m, 2 m to 340 m, then a single voxel to the tip, banded
            rad = 1.6 if z < 300 else 1.1 if z < 340 else 0.5
            m = d <= max(rad, 0.5)
            if not m.any():
                m = (rr == r0) & (cc == c0)
            vol[zz, rr[m], cc[m]] = red if ((z - 250) // 7) % 2 == 0 else white
            n += int(m.sum())
    note(f"Fernsehturm rebuilt: {n} voxels, foot at {gz} (grid {c0}, {r0}), tip {gz + 368}")
    return (c0, r0, gz)


# ---------------------------------------------------------------- labels and views
def brandenburger_tor(vol, g, topi, feats, pal, note):
    """The gate's five passages, carved through the main block (the outline's cells standing 60 % of its height or
    more; the guardhouse wings beside it stay): the middle one 5.65 m wide, the others 3.8 m, the piers between them
    equal, open to 11 m (the Doric columns are 15 m with their entablature); the Quadriga on the attic as a copper
    block 6 x 3 m, 5 m tall (figures as published by the Senate; the passage widths of the 1791 design)."""
    f = next((f for f in feats if f["tags"].get("name") == "Brandenburger Tor" and not f["part"]), None)
    if f is None:
        note("Brandenburger Tor: no outline in OSM")
        return
    rr, cc = f["rr"], f["cc"]
    t = topi[rr, cc]
    main = t >= 0.6 * t.max()
    rr, cc = rr[main], cc[main]
    rect = np.array(f["geom"].minimum_rotated_rectangle.exterior.coords)[:4]
    e1, e2 = rect[1] - rect[0], rect[2] - rect[1]
    ax = e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2
    ax = ax / np.linalg.norm(ax)
    s_ = (cc + 0.5) * ax[0] + (rr + 0.5) * ax[1]
    s0, L = s_.min(), s_.max() - s_.min() + 1
    widths = np.array([3.8, 3.8, 5.65, 3.8, 3.8])
    if widths.sum() > 0.7 * L:
        widths *= 0.7 * L / widths.sum()
    pier = (L - widths.sum()) / 6
    edges, x = [], pier
    for w in widths:
        edges.append((x, x + w))
        x += w + pier
    n = 0
    for r, c, s in zip(rr, cc, s_ - s0):
        if any(a <= s + 0.5 < b for a, b in edges):
            gz = int(g[r, c])
            vol[gz:gz + 11, r, c] = 0
            n += 1
    copper = pal((95, 138, 118), M_METAL)
    mid = s0 + L / 2
    k = np.abs(s_ - mid) <= 3
    if k.any():
        perp = np.array([-ax[1], ax[0]])
        q = (cc + 0.5) * perp[0] + (rr + 0.5) * perp[1]
        k &= np.abs(q - np.median(q)) <= 1.5
        for r, c in zip(rr[k], cc[k]):
            col = np.nonzero(vol[:, r, c])[0]
            z0 = int(col[-1]) + 1
            vol[z0:z0 + 5, r, c] = copper
    note(f"Brandenburger Tor: 5 passages carved ({n} columns, block {L:.0f} m long, piers {pier:.1f} m), Quadriga {int(k.sum())} cells")


def details(vol, g, top, topi, bmask, feats, pal, C, osm, cells_of, note, leaf_ids=()):
    ft = fernsehturm(vol, g, pal, note)
    brandenburger_tor(vol, g, topi, feats, pal, note)

    def top_at(r, c):
        col = np.nonzero(vol[:, r, c])[0]
        return int(col[-1]) + 1 if len(col) else int(g[r, c])

    D, W = g.shape
    found = {}
    for oid, typ, t, geom in osm.areas:
        n = t.get("name")
        if n not in LABELS or n in found:
            continue
        facts = LABELS[n]
        if facts.get("anchor") == "top":
            rr, cc = cells_of(geom)
            if len(rr) == 0:
                continue
            k = np.argmax(topi[rr, cc] + g[rr, cc])
            r, c = int(rr[k]), int(cc[k])
        else:
            p = geom.representative_point() if not geom.contains(geom.centroid) else geom.centroid
            r, c = int(p.y), int(p.x)
        if 0 <= r < D and 0 <= c < W:
            found[n] = label(n, facts, c, r, top_at(r, c))
    for n, facts in LABELS.items():  # not an OSM area here (a node, another name): at its coordinates
        if n in found:
            continue
        c, r = (int(v) for v in grid_of(*facts["at"]))
        if 0 <= r < D and 0 <= c < W:
            found[n] = label(n, facts, c, r, top_at(r, c))
            note("label at coordinates (no OSM area by that name):", n)
    if ft is not None:  # the tower's label on its tip, wherever OSM puts the outline
        c0, r0, gz = ft
        found["Berliner Fernsehturm"].update(x=c0, y=r0, z=gz + 368)
    labels = [found[n] for n in LABELS if n in found]
    for n, facts in EXTRA_LABELS.items():
        if facts["at"] == "river":
            c, r = river_spot(vol, g, C)
        else:
            c, r = (int(v) for v in grid_of(*facts["at"]))
        if 0 <= r < D and 0 <= c < W:
            labels.append(label(n, facts, c, r, top_at(r, c)))
    note("labels:", [l["name"] for l in labels])
    return labels, make_views(found, g, ft)


def river_spot(vol, g, C):
    """The Spree's label: on open water 15 m from both banks, as far from bridge decks and the map's edge as can be."""
    D, W = g.shape
    rr, cc = np.mgrid[0:D, 0:W]
    water = np.take_along_axis(vol, (g - 1)[None].astype(np.intp), 0)[0] == C["water"]
    lab, n = ndimage.label(water)
    if n == 0:
        return W // 2, D // 2
    water = lab == np.argmax(np.bincount(lab.ravel())[1:]) + 1
    open_ = ndimage.distance_transform_edt(water) >= 12
    deck = DECK > 0 if DECK is not None else np.zeros((D, W), bool)
    far = ndimage.distance_transform_edt(~deck) if deck.any() else np.full((D, W), 1e9)
    edge = np.minimum.reduce([rr, cc, D - 1 - rr, W - 1 - cc])
    score = np.where(open_, np.minimum(far, edge), -1)
    r, c = np.unravel_index(np.argmax(score), score.shape)
    return int(c), int(r)


def make_views(found, g, ft):
    """Camera presets in three.js coords (x = col, y = up, z = row)."""
    D, W = g.shape

    def at(name, up=0.0):
        l = found[name]
        return [l["x"] + 0.5, float(g[int(l["y"]), int(l["x"])]) + up, l["y"] + 0.5]

    def add(t, off):
        return [t[0] + off[0], t[1] + off[1], t[2] + off[2]]

    views = {}
    tv = [ft[0] + 0.5, ft[2], ft[1] + 0.5] if ft else at("Berliner Fernsehturm")
    dom = at("Berliner Dom")
    mid = [(tv[0] + dom[0]) / 2, tv[1] + 20, (tv[2] + dom[2]) / 2]
    views["overview"] = dict(label="Overview", target=mid, pos=add(mid, (-520, 760, 1080)))
    views["tower"] = dict(label="Fernsehturm", target=add(tv, (0, 190, 0)), pos=add(tv, (380, 300, 330)))
    bt = at("Brandenburger Tor", 12)
    views["gate"] = dict(label="Brandenburger Tor", target=bt, pos=add(bt, (210, 55, 30)))
    rt = at("Reichstagsgebäude", 25)
    views["reichstag"] = dict(label="Reichstag", target=rt, pos=add(rt, (260, 150, 260)))
    ai = at("Altes Museum", 15)
    views["museums"] = dict(label="Museum Island", target=ai, pos=add(ai, (330, 260, 420)))
    al = at("Alexanderplatz", 10)
    views["alex"] = dict(label="Alexanderplatz", target=al, pos=add(al, (240, 170, 330)))
    gm = at("Gendarmenmarkt", 15)
    views["gendarmenmarkt"] = dict(label="Gendarmenmarkt", target=gm, pos=add(gm, (220, 150, 260)))
    # down Unter den Linden from the gate to the tower, low over the trees
    views["linden"] = dict(label="Unter den Linden", target=add(tv, (0, 120, 0)), pos=add(bt, (-160, 70, 10)))
    mid_ = [W * 0.52, float(np.median(g)) + 10, D * 0.45]
    views["city"] = dict(label="Whole map", target=mid_, pos=add(mid_, (0, 2600, 1700)))
    return views


def MIN_H(g):
    """voxelize.py makes the volume at least this tall: the Fernsehturm's tip, 368 m over its foot, plus a margin."""
    cx, cy = grid_of(*FT_LATLON)
    r0, c0 = int(cy), int(cx)
    D, W = g.shape
    if not (0 <= r0 < D and 0 <= c0 < W):
        return 0
    return int(np.median(g[max(r0 - 20, 0):r0 + 21, max(c0 - 20, 0):c0 + 21])) + 372


# how far away (m) each label shows (labels.py's FAR_TIERS for Warsaw): the whole map for what defines the city
FAR = {9000: {"Berliner Fernsehturm", "Brandenburger Tor", "Reichstag", "Berliner Dom", "Humboldt Forum", "Spree",
              "Museumsinsel", "Rotes Rathaus", "Alexanderplatz"},
       5000: {"Altes Museum", "Neues Museum", "Pergamonmuseum", "Bode-Museum", "Alte Nationalgalerie", "Gendarmenmarkt",
              "Konzerthaus", "Französischer Dom", "Deutscher Dom", "Staatsoper", "Nikolaikirche", "St. Marienkirche",
              "Nikolaiviertel", "Zeughaus", "St. Hedwigs-Kathedrale", "Lustgarten", "Pariser Platz", "Neptunbrunnen"}}


def assemble(curated, osm, top_at):
    """Berlin's labels.assemble: the curated labels with their distance tier, most prominent first."""
    out = []
    for l in curated:
        l = dict(l)
        l["far"] = next((d for d, names in FAR.items() if l["name"] in names), 1800)
        for k in [k for k, v in l.items() if v is None]:
            del l[k]
        out.append(l)
    out.sort(key=lambda l: -l["far"])
    return out
