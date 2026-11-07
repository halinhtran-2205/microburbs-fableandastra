"""Collect everything the pitch video draws into video/video_data.json (API output: not committed).

Needs the team key (MICROBURBS_API_KEY) and report_data.json + buildings_full.json from make_report.py.
"""
import json
import os
import time
import urllib.parse

import pandas as pd
import requests

BASE = "https://api-ht.microburbs.com.au/v1"
HEAD = {"Authorization": f"Bearer {os.environ.get('MICROBURBS_API_KEY', '')}"}


def get(path):
    for attempt in range(5):
        r = requests.get(BASE + path, headers=HEAD, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        return r
    return r


def rings(geom):
    """Outer rings of a Polygon / MultiPolygon, rounded to ~10 m."""
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    return [[[round(x, 5), round(y, 5)] for x, y in p[0]] for p in polys]


rep = json.load(open("report_data.json"))
names = pd.read_csv("data/flats-city-of-sydney.csv", usecols=["suburb"]).suburb.unique()
short = {s["suburb"]: s for s in rep["suburbs"]}
suburbs = []
for n in names:
    r = get(f"/suburbs/{urllib.parse.quote(n)}/shapes/boundary")
    if r.status_code != 200:
        continue
    g = r.json()["data"]["geojson"]["geometry"]
    sn = n.split(" (")[0]
    suburbs.append({"name": sn, "rings": rings(g), "value": short.get(sn, {}).get("all")})
    time.sleep(0.12)

mb = get("/suburbs/Zetland/shapes/mesh-blocks").json()["data"]["geojson"]["features"]
zet_mb = [r for f in mb for r in rings(f["geometry"])]

b = json.load(open("buildings_full.json"))  # name, suburb, lat, lon, flats, median, b1, b2, b3, tier
out = {
    "suburbs": suburbs,
    "zetland_mb": zet_mb,
    "buildings": [[x[2], x[3], x[4], x[5], x[9]] for x in b],
    "hero": next(x for x in b if x[0] == "6 Kingsborough Way"),
    "index": rep["index"],
    "w10": rep["holdout"]["2026-03-01"]["model"]["within_10pct"],
    "median10": rep["holdout"]["2026-03-01"]["median"]["within_10pct"],
    "park": rep["park_dollars_2bed"],
    "tiers": rep["tiers"],
    "never_sold": rep["headline"]["never_sold"],
    "from_peak": rep["market"]["from_peak"],
}
json.dump(out, open("video/video_data.json", "w"), separators=(",", ":"))
print(len(suburbs), "suburbs,", len(zet_mb), "Zetland blocks,", len(out["buildings"]), "buildings")
