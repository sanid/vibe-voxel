#!/bin/sh
# Berlin data pipeline: download (cached) -> prep -> voxelize -> the viewer's side files, into web/public/berlin/data.
# Runs the Warsaw pipeline with CITY=berlin from cities/berlin/, so its relative data/ paths land there
# (cities/berlin/web/public/data is a link to web/public/berlin/data). Needs ~16 GB RAM and ~3 GB disk.
set -e
cd "$(dirname "$0")/../cities/berlin"
export CITY=berlin PYTHONPATH=../../scripts
run() { uv run --project ../.. python "../../scripts/$1"; }
run berlin_fetch.py
run berlin_prep.py
run voxelize.py
run terrain.py
run zones.py
run windows.py
run places.py
# the phenology table is Warsaw's: its DWD series come from stations east of 12.5 deg E, Berlin's region too
PHENOLOGY_TABLE=../../web/public/data/phenology.json run phenology.py
# generic: lit-window statistics by building type
cp ../../web/public/data/windows.json web/public/data/windows.json
# climate: Open-Meteo for central Berlin (falls back to keeping the file that is there when the API refuses)
run climate.py || echo "climate.py failed (Open-Meteo limit?): keeping the existing climate.json"
