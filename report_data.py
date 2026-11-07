"""Compute every number and chart series for report.html into report_data.json.

Run after model.py --holdout 2025-09-01, --holdout 2026-03-01 and --final fableandastra.
"""
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
import model as M  # noqa: E402

TEAM = "fableandastra"
flats, sales, blocks = M.load()
vals = pd.read_csv(f"valuation_{TEAM}.csv")
out = {}

# ---------- market index ----------
idx = M.repeat_sales_index(sales)
lvl = pd.Series(np.exp(idx.values), index=[f"{1995 + i // 4} Q{i % 4 + 1}" for i in idx.index])
lvl = lvl[lvl.index >= "2010"]
out["index"] = [[k, round(float(v), 4)] for k, v in lvl.items()]
peak = lvl.idxmax()
out["market"] = {"peak_q": peak, "from_peak": float(lvl.iloc[-1] / lvl.max() - 1),
                 "since_2016": float(lvl.iloc[-1] / lvl["2016 Q1"] - 1),
                 "since_2020": float(lvl.iloc[-1] / lvl["2020 Q1"] - 1)}

# ---------- held-out accuracy ----------
def sc(p, a):
    r = M.score(p, a)
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}


hold = {}
for cut in ["2026-03-01", "2025-09-01"]:
    h = pd.read_csv(f"holdout_{cut}.csv", parse_dates=["sold_date"])
    b = h.dropna(subset=["b_median"])
    p = h[h.has_prev]
    hold[cut] = {"model": sc(h.pred, h.price), "median": sc(b.b_median, b.price),
                 "last": sc(p.b_last, p.price), "prev": sc(p.pred, p.price),
                 "noprev": sc(h[~h.has_prev].pred, h[~h.has_prev].price)}
out["holdout"] = hold

hB = pd.read_csv("holdout_2025-09-01.csv", parse_dates=["sold_date"])
err = (hB.pred / hB.price - 1) * 100
bins = np.arange(-30, 32.5, 2.5)
cnt, _ = np.histogram(err.clip(-29.99, 29.99), bins=bins)
out["err_hist"] = [[float(bins[i]), int(c)] for i, c in enumerate(cnt)]
ae = (hB.pred / hB.price - 1).abs()
out["err_bands"] = [{"label": l, "share": float(((ae > lo) & (ae <= hi)).mean())} for l, lo, hi in
                    [("Within 5%", -1, .05), ("5 to 10%", .05, .10), ("10 to 20%", .10, .20), ("Over 20%", .20, 99)]]
rel = hB.pred / hB.price - 1
out["over_under"] = {"over10": float((rel > .10).mean()), "under10": float((rel < -.10).mean())}
pb = []
for l, lo, hi in [("Under $500k", 0, 5e5), ("$500k to 700k", 5e5, 7e5), ("$700k to 900k", 7e5, 9e5), ("$900k to 1.2m", 9e5, 1.2e6)]:
    g = hB[(hB.price >= lo) & (hB.price < hi)]
    pb.append({"label": l, "within10": float(((g.pred / g.price - 1).abs() <= .10).mean()), "n": int(len(g))})
out["price_bands"] = pb

# ---------- confidence tiers (lender view) ----------
def tiers(cutoff, targets):
    """Evidence tier for each target flat, from sales before cutoff only."""
    hist = sales[(sales.sold_date < cutoff) & sales.price.between(150e3, 10e6)]
    recent = hist[hist.sold_date >= cutoff - pd.DateOffset(years=10)]
    own = set(recent.gnaf_id)
    bed_known = flats.set_index("gnaf_id")["bedrooms"]
    hist = hist.assign(bed=hist.bedrooms.fillna(pd.Series(bed_known.reindex(hist.gnaf_id).values, index=hist.index)).fillna(-1))
    bb = hist.groupby([hist.building, hist.bed]).size()
    bl = hist.groupby("building").size()
    t = targets.copy()
    t["bed"] = t["bedrooms"].fillna(-1)
    n_bb = np.array([bb.get((b, d), 0) for b, d in zip(t.building, t.bed)])
    n_b = bl.reindex(t.building).fillna(0).values
    tier = np.where(t.gnaf_id.isin(own) | (n_bb >= 5), "High",
                    np.where(n_b >= 5, "Medium", "Low"))
    return tier


ft = flats.copy()
resid = (ft.is_shop == 0) & (ft.is_office == 0) & ~ft.dwelling_type.isin(
    ["commercial", "industrial", "leisure", "accommodation"])
ft = ft[resid]
ft["tier"] = tiers(M.TASK_DATE + pd.Timedelta(days=1), ft)
hB2 = hB.copy()
hB2 = hB2.merge(flats[["gnaf_id", "building"]].rename(columns={"building": "b2"}), on="gnaf_id", how="left")
hB2["building"] = hB2["b2"].fillna(hB2["building"])
hB2["bedrooms"] = hB2["bed"]
hB2["tier"] = tiers(pd.Timestamp("2025-09-01"), hB2)
tier_out = []
for t in ["High", "Medium", "Low"]:
    g = hB2[hB2.tier == t]
    e = (g.pred / g.price - 1).abs()
    tier_out.append({"tier": t, "within10": float((e <= .10).mean()), "within5": float((e <= .05).mean()),
                     "median_pct": float(e.median()), "test_n": int(len(g)),
                     "share_all": float((ft.tier == t).mean()), "flats": int((ft.tier == t).sum())})
out["tiers"] = tier_out
out["resid_flats"] = int(len(ft))

# ---------- premiums (developer view) ----------
s = sales[(sales.sold_date >= "2018") & sales.price.between(150e3, 10e6)].dropna(subset=["bedrooms"]).copy()
s["alp"] = np.log(s.price) - idx.reindex(M.quarter_id(s.sold_date)).values
s["bb"] = s.building + "|" + s.bedrooms.astype(str)
s = s[s.groupby("bb").alp.transform("size") >= 5]
s["rel"] = s.alp - s.groupby("bb").alp.transform("mean")
car = s.dropna(subset=["car_spaces"]).groupby(s.car_spaces.clip(0, 2)).rel.mean()
out["parking"] = [{"label": l, "pct": float(np.exp(car[k] - car[0.0]) - 1)}
                  for k, l in [(0.0, "No car space"), (1.0, "1 space"), (2.0, "2+ spaces")]]
fl = s.dropna(subset=["floor"])
fl = fl[fl.floor <= 40]
fb = fl.groupby(pd.cut(fl.floor, [0, 2, 5, 10, 20, 40], labels=["1 to 2", "3 to 5", "6 to 10", "11 to 20", "21 to 40"]),
                observed=True).rel.mean()
out["floors"] = [{"label": str(k), "pct": float(np.exp(v - fb.iloc[0]) - 1)} for k, v in fb.items()]

# ---------- suburb ladder (investor view) ----------
v = ft.merge(vals, on="gnaf_id")
v["sub"] = v.suburb.str.replace(r" \(.*\)", "", regex=True)
lad = []
for sub, g in v.groupby("sub"):
    row = {"suburb": sub, "flats": int(len(g)), "all": int(g.value.median())}
    for b in [1, 2, 3]:
        gb = g[g.bedrooms == b]
        row[f"b{b}"] = int(gb.value.median()) if len(gb) >= 30 else None
    lad.append(row)
# 12-month resale growth per suburb: flats resold Sep 2025 - Aug 2026, annual growth over the hold
r = sales.sort_values(["gnaf_id", "sold_date"])
r = r.assign(pp=r.groupby("gnaf_id").price.shift(), pd_=r.groupby("gnaf_id").sold_date.shift())
r = r[(r.sold_date >= "2025-09-01") & r.pp.notna()]
r["yrs"] = (r.sold_date - r.pd_).dt.days / 365.25
r = r[(r.yrs >= 2) & r.price.between(150e3, 10e6) & r.pp.between(100e3, 10e6)]
r["cagr"] = (r.price / r.pp) ** (1 / r.yrs) - 1
r["sub"] = r.suburb.str.replace(r" \(.*\)", "", regex=True)
g = r.groupby("sub").agg(cagr=("cagr", "median"), n=("cagr", "size"), hold=("yrs", "median"))
for row in lad:
    if row["suburb"] in g.index and g.loc[row["suburb"], "n"] >= 15:
        row["cagr"] = float(g.loc[row["suburb"], "cagr"])
        row["resales"] = int(g.loc[row["suburb"], "n"])
lad = [x for x in lad if x["flats"] >= 300]
out["suburbs"] = sorted(lad, key=lambda x: x["all"])
out["city_cagr"] = float(r.cagr.median())
out["city_resales"] = int(len(r))

# ---------- building map + lookup ----------
v["bed"] = v.bedrooms
bld = v.groupby("building").agg(sub=("sub", "first"), lat=("latitude", "median"), lon=("longitude", "median"),
                                n=("value", "size"), med=("value", "median"))
for b in [1, 2, 3]:
    bld[f"b{b}"] = v[v.bed == b].groupby("building").value.median()
bld = bld[bld.n >= 2].reset_index()
tier_b = ft.groupby("building").tier.agg(lambda x: x.value_counts().idxmax())
bld["tier"] = tier_b.reindex(bld.building).map({"High": 2, "Medium": 1, "Low": 0}).fillna(0).values
out["buildings"] = [[r.building.title(), r.sub, round(r.lat, 5), round(r.lon, 5), int(r.n), int(r.med),
                     None if pd.isna(r.b1) else int(r.b1), None if pd.isna(r.b2) else int(r.b2),
                     None if pd.isna(r.b3) else int(r.b3), int(r.tier)] for r in bld.itertuples()]

# ---------- headline numbers ----------
out["headline"] = {"addresses": int(len(vals)), "never_sold": float(1 - flats.gnaf_id.isin(sales.gnaf_id).mean()),
                   "missing_preds": int(vals.value.isna().sum()),
                   "total_value": float(v.value.sum())}
out["park_dollars_2bed"] = float(np.median(v[v.bed == 2].value) * out["parking"][1]["pct"])

json.dump(out["buildings"], open("buildings_full.json", "w"), separators=(",", ":"))  # with coordinates, for the video
out["buildings"] = [b[:2] + b[4:] for b in out["buildings"]]  # lookup only, no coordinates

# ---------- data story ----------
yr = sales.sold_date.dt.year
ys = sales[yr >= 2005].groupby(yr[yr >= 2005]).agg(n=("price", "size"), bed=("bedrooms", lambda x: x.notna().mean()))
out["years"] = [[int(y), int(r.n), float(r.bed)] for y, r in ys.iterrows()]
raw_bed = pd.read_csv(M.DATA + "flats-city-of-sydney.csv", usecols=["bedrooms"]).bedrooms
out["bed_missing"] = {"input": float(raw_bed.isna().mean()), "with_api": float(flats.bedrooms.isna().mean())}
out["sold_split"] = {"sold": int(flats.gnaf_id.isin(sales.gnaf_id).sum()), "never": int((~flats.gnaf_id.isin(sales.gnaf_id)).sum())}

# when did resold flats last sell? (flats sold 1 Sep 2025 to 31 Aug 2026)
t = sales[sales.sold_date >= "2025-09-01"]
prev = sales[sales.sold_date < "2025-09-01"].groupby("gnaf_id").sold_date.max()
ly = prev.reindex(t.gnaf_id).dt.year
cuts = [(1990, 2009, "Before 2010"), (2010, 2014, "2010 to 2014"), (2015, 2019, "2015 to 2019"),
        (2020, 2025, "2020 to 2025"), (None, None, "Never sold before")]
out["last_sale_age"] = [{"label": l, "share": float(ly.between(a, b).mean() if a else ly.isna().mean())}
                        for a, b, l in cuts]

# monthly level for 2025-26 from resale pairs (quarterly index for the earlier sale)
r2 = sales[sales.price.between(150e3, 10e6)].sort_values(["gnaf_id", "sold_date"])
r2 = r2.assign(q=M.quarter_id(r2.sold_date))
r2 = r2.assign(pp=r2.groupby("gnaf_id").price.shift(), pq=r2.groupby("gnaf_id").q.shift())
r2 = r2[(r2.sold_date >= "2025-01-01") & r2.pp.notna()]
lvl_m = (np.log(r2.price / r2.pp) + idx.reindex(r2.pq.astype(int)).values).groupby(
    r2.sold_date.dt.to_period("M")).median()
lvl_m = np.exp(lvl_m - lvl_m.iloc[:6].median())
out["monthly"] = [[str(k), round(float(v), 4)] for k, v in lvl_m.items()]

# which single anchor predicts best? (Sep 2025 split, same test sales as the model)
cut = pd.Timestamp("2025-09-01")
h = sales[(sales.sold_date < cut) & (sales.sold_date >= M.HIST_FROM) & sales.price.between(150e3, 10e6)].copy()
ih = M.repeat_sales_index(h)
h["alp"] = np.log(h.price) - ih.reindex(M.quarter_id(h.sold_date)).values
bk = flats.set_index("gnaf_id").bedrooms
h["bed"] = h.bedrooms.fillna(pd.Series(bk.reindex(h.gnaf_id).values, index=h.index))
bb_mean = h.groupby([h.building, h.bed]).alp.mean()
t2 = hB.copy()
t2["bb"] = [np.exp(bb_mean.get((b, d), np.nan)) for b, d in zip(t2.building, t2.bed)]


def w10(p, a):
    m = p.notna()
    return float(((p[m] / a[m] - 1).abs() <= .10).mean()), int(m.sum())


anch = [("Our model", *w10(t2.pred, t2.price)),
        ("Same building, same bedrooms", *w10(t2.bb, t2.price)),
        ("The flat's own last sale", *w10(t2.b_last, t2.price)),
        ("Suburb and bedroom median", *w10(t2.b_median, t2.price))]
out["anchors"] = [{"label": l, "within10": v, "n": n} for l, v, n in anch]

hA_ = pd.read_csv("holdout_2026-03-01.csv")
out["bias_median"] = float(np.median(hA_.pred / hA_.price - 1))

# real sale vs our blind estimate (made 1 Sep 2025, before the sale), per building for the lookup
tb = hB.copy()
tb["bkey"] = tb.building.str.title()
tb["unit"] = tb.address.str.extract(r"^([^,]+),")[0].fillna(tb.address)
out["building_sales"] = {k: [[u, d.strftime("%b %Y"), int(p), int(v)] for u, d, p, v in
                             zip(g.unit, g.sold_date, g.price, g.pred)][:8]
                         for k, g in tb.sort_values("sold_date", ascending=False).groupby("bkey")}

# training set sizes per split
out["train_n"] = {c: int(((sales.sold_date < c) & (sales.sold_date >= M.HIST_FROM)
                          & sales.price.between(150e3, 10e6)).sum()) for c in ["2025-09-01", "2026-03-01"]}

# time-window experiments (Sep 2025 split; see README "Which time periods matter")
out["windows"] = [{"label": "All sales since 1995", "within10": .703},
                  {"label": "Sales from 2010 (used)", "within10": out["holdout"]["2025-09-01"]["model"]["within_10pct"]},
                  {"label": "Sales from 2018 only", "within10": .681}]
json.dump(out, open("report_data.json", "w"), separators=(",", ":"))
print({k: (v if not isinstance(v, list) or len(v) < 8 else f"list[{len(v)}]") for k, v in out.items()
       if k not in ("index", "buildings", "err_hist")})
print("buildings", len(out["buildings"]))
