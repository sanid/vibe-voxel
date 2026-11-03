# Berlin Vibe Voxel: plan and status

Branch `berlin-vibe-voxel`. Berlin Mitte built by the Warsaw pipeline and shown in the Warsaw viewer
(`web/berlin/index.html`, served at `/berlin/`). How to build and the source table: README.md, section "Berlin".

## Where it started

The first blueprint ("Berlin Vibe Voxel: Architecture & Implementation Blueprint") proposed a new project:
LoD2 CityGML models, DGM1 terrain, the Baumbestand tree register, DOP20 orthophotos and GTFS transit, voxelized by a
new Python ETL into binary chunks for a new Three.js viewer, over four sprints. Sprints 1-3 were built that way
first (commits `ba2ac7e`, `cf6f9fa`, `32ee334`) and gave a working but plain viewer. Since the goal is to look like
warsaw-vibe-voxel, that code was replaced (commit `e2d064d`) by running the Warsaw pipeline and engine on Berlin's
data. The old code stays in the history.

Corrections to the blueprint found along the way:
- The Fernsehturm is at 392081 E, 5820156 N (EPSG:25833). The blueprint's 392800, 5820400 is Alexanderplatz.
- DGM1 is at `fb/atom/DGM1/DGM1_<E>_<N>.zip`, in 2 km tiles, not 1 km.
- The blueprint's DOP20 WMS URLs return 404. The working orthophoto is `gdi.berlin.de/services/wms/truedop_2024`
  (TrueDOP 2024, 20 cm).
- The Baumbestand WFS layers are `baumbestand:strassenbaeume` and `baumbestand:anlagenbaeume`.
- A surface model exists: `fb/atom/DOM/DOM1_<E>_<N>.zip` (image-matched, 1 m, 2021). It stands in for Warsaw's LiDAR,
  so LoD2 is not needed.

## Done

- [x] City switch in the pipeline (`scripts/aoi.py`, `CITY=berlin`): EPSG:25833, anchored on the Fernsehturm, rotated
      6.4 deg to the Friedrichstadt grid, 3300 x 1500 m from the Reichstag to Alexanderplatz.
- [x] Fetch and prep (`scripts/berlin_fetch.py`, `scripts/berlin_prep.py`): DOM1, DGM1, TrueDOP 2024, BBBike OSM,
      Baumbestand (counts checked against the WFS).
- [x] `scripts/landmarks_berlin.py`: 29 labels, 9 camera views, the Nikolaiviertel as the tiled historic core,
      sandstone and copper for 17 landmarks, the Fernsehturm rebuilt to 368 m, the Brandenburger Tor's passages and
      Quadriga, the smear around the tower removed.
- [x] Trees from Baumbestand (`scripts/trees.py`), foliage seasons from the DWD table (`scripts/phenology.py`).
- [x] Traffic from OSM: trams M1, M2, M4, M5, M6, M8, 12; S-Bahn and DB tracks; 127 signalled junctions.
- [x] Viewer: second page, `web/src/place.ts` for the sun's position, credits and Warsaw-only features.
- [x] One-command rebuild: `sh scripts/build_berlin.sh`.
- [x] Checked in headless Chromium (software GL): loads in ~80 s; day, golden hour and night render.

## Next

Ordered by what most improves the result for the effort.

1. **Berlin climate.** `climate.json` is Warsaw's, labelled as a stand-in, because Open-Meteo refused the request
   (daily limit). Rerun `CITY=berlin uv run --project ../.. python ../../scripts/climate.py` from `cities/berlin/`
   with `PYTHONPATH=../../scripts`, then copy nothing: it writes `web/public/berlin/data/climate.json`.
2. **The 19 m depression by Alexanderplatz** (~392350-392500 E, 5820050-5820375 N, 13 m below the Spree's level).
   Check it against the TrueDOP and OSM (likely a construction pit). If it is a pit, leave it; if it is a data gap,
   fill it from the neighbouring terrain in `berlin_prep.py`.
3. **Real GPU check.** The renders so far are SwiftShader. Run `web/tools/shot.mjs` with `URL=http://localhost:5173/berlin/`
   on a machine with a GPU, and the phone engine (`?shape=budget`), to measure load time and frame rate.
4. **More landmark curation**, as Warsaw has for its own:
   - Reichstag: the glass dome (the surface model shows it as a blob).
   - Berliner Dom: cleaner dome shapes (the image-matched surface is lumpy).
   - Brandenburger Tor: OSM's main block is 34 m long; check the passage widths against photos.
   - Park Inn and the Alexanderplatz towers: facades read as blue glass; Park Inn is pale with dark windows.
   - Konzerthaus, Französischer and Deutscher Dom, Rotes Rathaus tower: compare with photos from the same viewpoint.
5. **Tiergarten trees.** The spring orthophoto shows bare crowns, so park trees come mostly from the canopy height
   and read as tall columns. Use a summer orthophoto (another TrueDOP year) for the leaf colour, or cap and widen
   crowns from the tree register's crown diameters.
6. **Spree.** No river gauge (`flood.py` is the Vistula's). Either hide the river UI for Berlin explicitly or write a
   Spree version with its regulated level (Mühlendamm lock).
7. **Larger map.** Extend west over the Tiergarten to the Siegessäule and Potsdamer Platz, or east along
   Karl-Marx-Allee. Memory grows with the area: ~10 GB peak at 3300 x 1500 m.
8. **Search and labels.** Add Wikidata-ranked labels as Warsaw has (`scripts/notable.py`, `scripts/labels.py`), and
   German/English search keywords in `scripts/places.py` (its kind keywords are Polish).
9. **Publish.** Build `web/` and host both pages; add a Berlin `og:image` preview to `web/berlin/index.html`.

## Files

- Pipeline: `scripts/aoi.py`, `scripts/berlin_fetch.py`, `scripts/berlin_prep.py`, `scripts/landmarks_berlin.py`,
  `scripts/build_berlin.sh`, plus small city-aware edits in `voxelize.py`, `trees.py`, `osm.py`, `traffic.py`,
  `climate.py`, `phenology.py`, `places.py`, `windows.py`.
- Build folder: `cities/berlin/` (raw downloads and caches in `cities/berlin/data/`, not committed;
  `cities/berlin/web/public/data` links to the output).
- Output: `web/public/berlin/data/` (~12 MB).
- Viewer: `web/berlin/index.html`, `web/src/place.ts`, edits in `web/src/main.ts`, `web/src/sun.ts`,
  `web/src/sim/dance.ts`, `web/vite.config.js`.
