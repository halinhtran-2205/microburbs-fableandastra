"""Download every address's physical facts from the Microburbs API, suburb by suburb.

Needs MICROBURBS_API_KEY in the environment. Writes data/api_properties.csv
(API output: keep it out of git).
"""
import os
import time
import urllib.parse

import pandas as pd
import requests

BASE = "https://api-ht.microburbs.com.au/v1"
HEAD = {"Authorization": f"Bearer {os.environ.get('MICROBURBS_API_KEY', '')}"}


def get(url, params):
    for attempt in range(6):
        r = requests.get(url, params=params, headers=HEAD, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        return r
    r.raise_for_status()


def fetch_suburb(name):
    rows, offset = [], 0
    url = f"{BASE}/suburbs/{urllib.parse.quote(name)}/properties"
    while True:
        r = get(url, {"limit": 1000, "offset": offset})
        if r.status_code != 200:
            print(name, r.status_code, r.text[:120])
            return rows
        d = r.json()["data"]
        rows += d["results"]
        offset += d["meta"]["returned"]
        if d["meta"]["returned"] == 0 or offset >= d["meta"]["total"]:
            return rows
        time.sleep(0.12)


if __name__ == "__main__":
    suburbs = pd.read_csv("data/flats-city-of-sydney.csv", usecols=["suburb"]).suburb.unique()
    out = []
    for s in suburbs:
        rows = fetch_suburb(s)
        print(s, len(rows), flush=True)
        out += [dict(r, query_suburb=s) for r in rows]
    pd.DataFrame(out).to_csv("data/api_properties.csv", index=False)
