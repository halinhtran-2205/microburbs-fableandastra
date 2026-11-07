# Every Flat, Priced

**Team FableAndAstra · Microburbs Hackathon, 7 November 2026 · Task 5: Value every flat**

We put a price on all **181,711** flats and units in the City of Sydney, as at **31 August 2026**.
That includes the 72% that have never been sold, so a buyer or a bank can price any flat in seconds.

| | |
|---|---|
| **Submission** | [`valuation_fableandastra.csv`](valuation_fableandastra.csv): 181,711 rows, `gnaf_id,value` |
| **Report** | [Open the interactive report](https://halinhtran-2205.github.io/microburbs-fableandastra/report.html) (charts and building lookup), or [`report.html`](report.html) |
| **Pitch** | [`pitch.mp4`](pitch.mp4): 45 seconds |
| **Demo** | [`demo.mp4`](demo.mp4): up to 3 minutes |

## The problem

Most flats in the city have no sale on record, and 73% of the addresses we had to value have no
bedroom count. You can't look up what they last sold for, and a suburb average is a blunt tool:
on our test it got only 42% of flats within 10% of their real price.

## What we built

A valuation model that gives every address a price and an evidence rating (High, Medium or Low),
plus an interactive report where you can look up any building, filter by suburb, size, value and
evidence, and see how our estimates compared with real sales there.

**Who it helps**

- **Buyers and sellers** get a fair price to check before they negotiate.
- **Landlords and investors** can value every flat they own or are thinking of buying.
- **Lenders** can see which flats are safe to value from a desk and which need a valuer.

## Results

We trained only on sales before a split date, valued every flat on that date, and compared with
real sales afterwards. Like the judges, we kept sales under $1.2m and dropped shops.

| Test | Sales | Within 10% | Typical miss | R² (log price) |
|---|---|---|---|---|
| Split 1 Mar 2026, sales to 31 Aug 2026 | 930 | **72.0%** | $48k | 0.86 |
| Split 1 Sep 2025, sales to 31 Aug 2026 | 2,068 | **71.2%** | $48k | 0.87 |
| Suburb and bedroom median (same 930 sales) | 930 | 41.9% | $100k | 0.23 |
| Flat's own last sale, moved to today (flats sold before) | 553 | 50.4% | $80k | 0.38 |

In plain words: about 7 in 10 flats sold within 10% of our value, 1.7 times as often as a suburb
median. No predictions are missing.

## The clever step

**No single clue is enough, so we combine them all.**
On its own, a flat's last sale gets 53% of test flats within 10%, the building average for its
bedroom count gets 47%, and a suburb median gets 42%. Each clue is right where the others are wrong.

Our model gathers every clue that existed before the valuation date:

1. **Adjust every price to today** with our own repeat-sales index, built from flats that sold twice.
2. **Look back** at earlier sales of the flat, its building, the same bedroom count in that building,
   its mesh block and its suburb. A sale never sees itself or anything later, so there is no leakage.
3. **Add the flat's details**: bedrooms, bathrooms, parking, building size, location, and the floor,
   read from the unit number (Unit 1313 is on floor 13).
4. **Combine** them with a LightGBM model (gradient-boosted trees, Huber loss on log price,
   three seeds averaged), then trim values by 2% because the model reads slightly high after a market turn.

Together the clues reach 71 to 72%, and flats that never sold still get a value from their building and street.

## What the data taught us

- **Use sales from 2010 onwards.** We tested eight time windows. Older sales have no bedroom counts and
  blurred the building averages; dropping them lifted the score on both tests. Cutting back to 2018
  hurt, because many flats last sold in the early 2010s.
- **The market turned in 2026.** Prices peaked in February, dipped in May and June, then held steady.
  We value at the July and August level.
- **Parking and height matter.** A car space adds about 7% (around $84k on a typical 2-bedroom flat).
  Floors 11 to 20 sell about 4% above the lowest floors of the same building.

## Data and licences

| Source | Used for | Licence |
|---|---|---|
| Microburbs supplied files (flats, flat sales, repeat sales, blocks) | input, sales history, block counts | Day-only use, **not in this repo** |
| Microburbs API, `/v1/suburbs/{suburb}/properties` and shapes | bedrooms, bathrooms, parking, floor, dwelling type; video map | Data © Microburbs, raw output **not in this repo** |
| Open G-NAF | address IDs | © Geoscape Australia, Commonwealth licence |
| ABS Census 2021 | homes and people per mesh block | © Commonwealth of Australia, CC BY 4.0 |

Only information dated on or before 31 August 2026 is used. API facts have no as-at date; where the
file also had a bedroom count, the two agreed 98.6% of the time.

## How to run

```bash
pip install pandas numpy lightgbm requests
```

1. Put the four supplied CSVs in `data/` (they are not in this repo).
2. Optional: download property facts from the API with your team key (about 200 calls).

```bash
MICROBURBS_API_KEY=your-key python fetch_api.py
```

3. Run the two held-out tests (about a minute each).

```bash
python model.py --holdout 2026-03-01
```

```bash
python model.py --holdout 2025-09-01
```

4. Write the submission.

```bash
python model.py --final fableandastra
```

5. Rebuild the report.

```bash
python make_report.py
```

Set `USE_API=0` to run without the API facts.

## Repository

| Path | What it is |
|---|---|
| `model.py` | Price index, look-back features, LightGBM, held-out tests, submission CSV |
| `fetch_api.py` | Downloads property facts from the Microburbs API |
| `report_data.py`, `report_template.html`, `make_report.py` | Build the interactive `report.html` |
| `video/` | Pitch video source: scenes (`pitch.html`), renderer (`render.js`), voiceover (`make_voice.py`, Kokoro TTS), script and captions |
| `valuation_fableandastra.csv` | The submission |

## Team

FableAndAstra, Microburbs Hackathon at UTS Business School, 7 November 2026.

Estimates are automated and indicative only, not financial advice or a formal valuation.
Data © Microburbs.
