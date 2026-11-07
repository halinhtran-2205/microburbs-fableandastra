"""Value every City of Sydney flat at a cutoff date.

Pipeline:
  1. Repeat-sales price index by quarter (citywide), from consecutive sales of the same flat.
  2. Every past sale is moved to cutoff-date dollars with that index.
  3. Time-aware features: this flat's own last sale, and the average of earlier sales in the
     same building, same building + bedroom count, same mesh block and same suburb.
     A sale only ever sees sales dated before it.
  4. LightGBM on log(price in cutoff dollars).

Usage:
  python model.py --holdout 2026-03-01      # build on sales before the split, test on later sales
  python model.py --final team-name         # build on everything up to 31 Aug 2026, write the CSV
"""
import argparse
import os

import lightgbm as lgb
import numpy as np
import pandas as pd

DATA = "data/"
TASK_DATE = pd.Timestamp("2026-08-31")
# The model reads about 2% high in the first months after any split (chosen on the
# 2025-09-01 split, Sep 2025 to Feb 2026, then checked on the 2026-03-01 split).
SHIFT = 0.02
USE_API = os.environ.get("USE_API", "1") == "1"
# time windows (env overrides are for the timeline experiments in timeline.py)
HIST_FROM = os.environ.get("HIST_FROM", "2010-01-01")   # sales used for the index and look-back features; older sales hurt (see README)
TRAIN_FROM = os.environ.get("TRAIN_FROM", "2008-01-01")  # sales used as training targets
DECAY_YEARS = float(os.environ.get("DECAY_YEARS", "6"))  # weight halves roughly every 4 years


# ---------- loading and address parsing ----------

def parse_address(addr: pd.Series) -> pd.DataFrame:
    a = addr.str.upper().fillna("")
    out = pd.DataFrame(index=addr.index)
    # building = street part after the last comma
    out["building"] = a.str.replace(r"^.*,\s*", "", regex=True).str.strip()
    out["is_shop"] = a.str.contains(r"\bSHOP\b").astype(int)
    out["is_office"] = a.str.contains(r"\bOFFICE\b|\bSUITE\b|\bLEVEL\b").astype(int)
    out["is_carspace"] = a.str.contains(r"CAR ?SPACE|PARKING|\bCS\b").astype(int)
    unit = a.str.extract(r"^(?:UNIT|APARTMENT|FLAT|SHOP|SUITE|OFFICE)?\s*([A-Z]?\d+[A-Z]?)\s*,")[0]
    num = pd.to_numeric(unit.str.extract(r"(\d+)")[0], errors="coerce")
    out["unit_num"] = num
    # 1313 -> floor 13, 405 -> floor 4; below 100 the floor is unknown
    out["floor"] = np.where(num >= 100, num // 100, np.nan)
    out["unit_ground"] = unit.str.startswith("G").fillna(False).astype(int)
    return out


def load():
    flats = pd.read_csv(DATA + "flats-city-of-sydney.csv")
    sales = pd.read_csv(DATA + "flat-sales-city-of-sydney.csv", parse_dates=["sold_date"])
    blocks = pd.read_csv(DATA + "blocks-homes-and-people-2021-2026.csv")
    flats = flats.join(parse_address(flats["address"]))
    sales = sales.join(parse_address(sales["address"]))
    blocks = blocks.drop_duplicates("mb").drop(columns=["suburb"])
    api_path = DATA + "api_properties.csv"
    if USE_API and os.path.exists(api_path):
        # physical facts from /v1/suburbs/{suburb}/properties (see fetch_api.py)
        api = pd.read_csv(api_path, low_memory=False).drop_duplicates("gnaf_pid").set_index("gnaf_pid")
        for c in ["bedrooms", "bathrooms", "car_spaces"]:
            v = api[c].where(api[c] <= 10)
            flats[c] = flats[c].fillna(pd.Series(v.reindex(flats.gnaf_id).values, index=flats.index))
        flats["floor"] = flats["floor"].fillna(
            pd.Series(api["floor"].reindex(flats.gnaf_id).values, index=flats.index))
        flats["dwelling_type"] = api["dwelling_type"].reindex(flats.gnaf_id).fillna("unknown").values
        flats["land_size"] = api["land_size"].reindex(flats.gnaf_id).values
    else:
        flats["dwelling_type"] = "unknown"
        flats["land_size"] = np.nan
    return flats, sales, blocks


# ---------- price index ----------

def quarter_id(d: pd.Series) -> pd.Series:
    return (d.dt.year - 1995) * 4 + (d.dt.month - 1) // 3


def repeat_sales_index(sales: pd.DataFrame) -> pd.Series:
    """Bailey-Muth-Nourse repeat-sales index, log level per quarter, last quarter = 0."""
    s = sales[(sales.price.between(150_000, 10_000_000))].sort_values(["gnaf_id", "sold_date"])
    s = s.assign(q=quarter_id(s.sold_date), lp=np.log(s.price))
    prev = s.groupby("gnaf_id").shift(1)
    pairs = pd.DataFrame({"q0": prev.q, "q1": s.q, "d": s.lp - prev.lp}).dropna()
    pairs = pairs[(pairs.q1 > pairs.q0)]
    pairs = pairs[pairs.d.abs() < 1.2]  # drop renovations / data errors
    nq = int(s.q.max()) + 1
    X = np.zeros((len(pairs), nq))
    X[np.arange(len(pairs)), pairs.q1.astype(int)] = 1
    X[np.arange(len(pairs)), pairs.q0.astype(int)] = -1
    X = X[:, 1:]  # first quarter is the base
    gap = (pairs.q1 - pairs.q0).values
    w = 1 / np.sqrt(0.01 + 0.002 * gap)  # longer holds are noisier
    ridge = 3.0  # smooth neighbouring quarters
    D = np.diff(np.eye(nq - 1), axis=0)
    A = np.vstack([X * w[:, None], ridge * D])
    b = np.concatenate([pairs.d.values * w, np.zeros(len(D))])
    beta = np.linalg.lstsq(A, b, rcond=None)[0]
    lvl = np.concatenate([[0.0], beta])
    lvl -= lvl[-1]
    return pd.Series(lvl, index=range(nq))


# ---------- time-aware group features ----------

def prior_group_mean(events: pd.DataFrame, queries: pd.DataFrame, key: str, name: str):
    """For each query (key, date), the mean and count of adjusted log prices of events in the
    same group dated strictly before the query date, with more weight on recent sales."""
    ev = events[[key, "sold_date", "alp"]].dropna(subset=[key])
    ev = ev.groupby([key, "sold_date"]).agg(s=("alp", "sum"), n=("alp", "size")).reset_index()
    ev = ev.sort_values([key, "sold_date"])
    ev["cs"] = ev.groupby(key)["s"].cumsum()
    ev["cn"] = ev.groupby(key)["n"].cumsum()
    q = queries[[key, "qdate"]].copy()
    q["_i"] = np.arange(len(q))
    q["_t"] = q["qdate"] - pd.Timedelta(days=1)
    q = q.sort_values("_t")
    ev = ev.sort_values("sold_date")
    m = pd.merge_asof(q, ev[[key, "sold_date", "cs", "cn"]], left_on="_t", right_on="sold_date",
                      by=key, direction="backward")
    m = m.sort_values("_i")
    out = pd.DataFrame(index=queries.index)
    out[name + "_mean"] = (m["cs"] / m["cn"]).values
    out[name + "_n"] = m["cn"].fillna(0).values
    return out


def last_sale(events: pd.DataFrame, queries: pd.DataFrame):
    ev = events[["gnaf_id", "sold_date", "alp", "price"]].sort_values("sold_date")
    q = queries[["gnaf_id", "qdate"]].copy()
    q["_i"] = np.arange(len(q))
    q["_t"] = q["qdate"] - pd.Timedelta(days=1)
    m = pd.merge_asof(q.sort_values("_t"), ev, left_on="_t", right_on="sold_date",
                      by="gnaf_id", direction="backward").sort_values("_i")
    out = pd.DataFrame(index=queries.index)
    out["last_alp"] = m["alp"].values
    out["last_years"] = ((m["qdate"] - m["sold_date"]).dt.days / 365.25).values
    return out


NUM = ["bedrooms", "bathrooms", "car_spaces", "flats_in_building", "latitude", "longitude",
       "floor", "unit_num", "unit_ground", "is_shop", "is_office", "is_carspace",
       "homes_2021", "homes_2026", "people_2021", "people_2026", "new_homes", "land_size"]
CAT = ["suburb", "block_type", "dwelling_type"]
GROUPS = [("building", "bldg"), ("bldg_bed", "bldgbed"), ("mb", "mb"), ("suburb", "sub"),
          ("sub_bed", "subbed")]


def build_features(rows: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """rows need gnaf_id, qdate and the static columns. events are sales with alp."""
    X = rows.copy()
    for key, name in GROUPS:
        X = X.join(prior_group_mean(events, X, key, name))
    X = X.join(last_sale(events, X))
    for _, name in GROUPS:
        X[name + "_mean"] = X[name + "_mean"].astype(float)
    return X


def add_keys(df):
    bed = df["bedrooms"].fillna(-1).astype(int).astype(str)
    df["bldg_bed"] = df["building"] + "|" + bed
    df["sub_bed"] = df["suburb"] + "|" + bed
    return df


# ---------- training ----------

def fit_predict(flats, sales, blocks, cutoff: pd.Timestamp, seed=0):
    hist = sales[(sales.sold_date < cutoff) & (sales.sold_date >= HIST_FROM)].copy()
    idx = repeat_sales_index(hist)
    hist["alp"] = np.log(hist.price) - idx.reindex(quarter_id(hist.sold_date)).values
    clean = hist[hist.price.between(150_000, 10_000_000)]

    # static attributes for each flat: flats file, gaps filled from its latest sale record
    attrs = (hist.sort_values("sold_date").groupby("gnaf_id")[["bedrooms", "bathrooms", "car_spaces"]]
             .last())
    F = flats.set_index("gnaf_id")
    for c in ["bedrooms", "bathrooms", "car_spaces"]:
        F[c] = F[c].fillna(attrs[c].reindex(F.index))
    F = F.reset_index().merge(blocks, on="mb", how="left")
    F = add_keys(F)

    # every sale gets the flat's static columns; its own attributes win where present
    clean = clean.copy()
    static = F.set_index("gnaf_id")
    for c in ["flats_in_building", "latitude", "longitude", "block_type", "homes_2021", "homes_2026",
              "people_2021", "people_2026", "new_homes", "dwelling_type", "land_size"]:
        clean[c] = static[c].reindex(clean.gnaf_id).values
    for c in ["bedrooms", "bathrooms", "car_spaces"]:
        clean[c] = clean[c].fillna(pd.Series(static[c].reindex(clean.gnaf_id).values, index=clean.index))
    clean = add_keys(clean)
    tr = clean[clean.sold_date >= TRAIN_FROM].copy()
    tr["qdate"] = tr["sold_date"]
    tr = build_features(tr.reset_index(drop=True), clean)
    y = tr["alp"].values

    F["qdate"] = cutoff
    P = build_features(F, clean)

    feats = NUM + CAT + [n + s for _, n in GROUPS for s in ("_mean", "_n")] + ["last_alp", "last_years"]
    for c in CAT:
        cats = pd.Categorical(P[c]).categories
        tr[c] = pd.Categorical(tr[c], categories=cats)
        P[c] = pd.Categorical(P[c], categories=cats)
    age = (cutoff - tr.sold_date).dt.days / 365.25
    w = np.exp(-age / DECAY_YEARS)  # recent sales count more
    params = dict(objective="huber", alpha=0.25, learning_rate=0.03, num_leaves=63,
                  min_data_in_leaf=30, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                  lambda_l2=1.0, verbose=-1, seed=seed)
    preds = []
    for k in range(3):
        params["seed"] = seed + k
        m = lgb.train(params, lgb.Dataset(tr[feats], y, weight=w), num_boost_round=1500)
        preds.append(m.predict(P[feats]))
    P["log_value"] = np.mean(preds, axis=0)
    P["value"] = np.exp(P["log_value"] - SHIFT).round(-3).astype(int)
    imp = pd.Series(m.feature_importance("gain"), index=feats).sort_values(ascending=False)
    return P, idx, imp


def score(pred: pd.Series, actual: pd.Series) -> dict:
    err = (pred - actual) / actual
    return {"n": len(actual), "within_10pct": float((err.abs() <= 0.10).mean()),
            "median_abs_err": float((pred - actual).abs().median()),
            "median_abs_pct": float(err.abs().median()),
            "r2_log": float(1 - np.mean((np.log(pred) - np.log(actual)) ** 2) / np.var(np.log(actual))),
            "r2": float(1 - ((pred - actual) ** 2).sum() / ((actual - actual.mean()) ** 2).sum())}


def baselines(sales, flats, cutoff, test):
    """The task page's two simple baselines, so we can compare like for like."""
    hist = sales[sales.sold_date < cutoff]
    idx = repeat_sales_index(hist)
    h = hist.assign(alp=np.log(hist.price) - idx.reindex(quarter_id(hist.sold_date)).values)
    last = h.sort_values("sold_date").groupby("gnaf_id")["alp"].last()
    rec = h[h.sold_date >= cutoff - pd.DateOffset(years=3)]
    bed = flats.set_index("gnaf_id")["bedrooms"]
    t = test.copy()
    t["bed"] = t["bedrooms"].fillna(pd.Series(bed.reindex(t.gnaf_id).values, index=t.index))
    med = rec.groupby(["suburb", rec["bedrooms"].fillna(-1)])["price"].median()
    t["b_median"] = [med.get((s, b if b == b else -1), np.nan) for s, b in zip(t.suburb, t.bed)]
    t["b_last"] = np.exp(last.reindex(t.gnaf_id).values)
    return t


def holdout(cutoff_str):
    flats, sales, blocks = load()
    cutoff = pd.Timestamp(cutoff_str)
    P, idx, imp = fit_predict(flats, sales, blocks, cutoff)
    test = sales[(sales.sold_date >= cutoff) & (sales.sold_date <= TASK_DATE)].copy()
    # judges: confirmed flats under $1.2m; we mimic with price filter and no shop/office
    test = test[(test.price < 1_200_000) & (test.price >= 150_000) & (test.is_shop == 0)]
    test = baselines(sales, flats, cutoff, test)
    test["pred"] = P.set_index("gnaf_id")["value"].reindex(test.gnaf_id).values
    test["has_prev"] = ~np.isnan(test["b_last"])
    res = {"model": score(test.pred, test.price)}
    b = test.dropna(subset=["b_median"])
    res["suburb_bedroom_median"] = score(b.b_median, b.price)
    res["model_same_rows_as_median"] = score(b.pred, b.price)
    for flag, g in test.groupby("has_prev"):
        res[f"model_prev_sale={flag}"] = score(g.pred, g.price)
        if flag:
            res["last_sale_indexed"] = score(g.b_last, g.price)
    return res, test, idx, imp


def final(team):
    flats, sales, blocks = load()
    P, idx, imp = fit_predict(flats, sales, blocks, TASK_DATE + pd.Timedelta(days=1))
    out = flats[["gnaf_id"]].merge(P[["gnaf_id", "value"]], on="gnaf_id", how="left")
    assert len(out) == 181_711 and out.gnaf_id.is_unique and out.value.notna().all()
    path = f"valuation_{team}.csv"
    out.to_csv(path, index=False, encoding="utf-8")
    return path, P, idx, imp


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout")
    ap.add_argument("--final")
    a = ap.parse_args()
    if a.holdout:
        res, test, idx, imp = holdout(a.holdout)
        print(pd.DataFrame(res).T.round(3).to_string())
        print(imp.head(15).round(0).to_string())
        if os.environ.get("SAVE", "1") == "1":
            test.to_csv(f"holdout_{a.holdout}.csv", index=False)
    if a.final:
        path, P, idx, imp = final(a.final)
        print("wrote", path)
