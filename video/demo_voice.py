"""Voice lines for demo.mp4 (Kokoro TTS). Writes one wav per line and demo_lines.json with durations.

Usage: python demo_voice.py <kokoro.onnx> <voices.bin> <out_dir> [voice]
"""
import json
import os
import sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

model, voices, out_dir = sys.argv[1:4]
VOICE = sys.argv[4] if len(sys.argv) > 4 else "bm_george"
SR = 24000
PAUSE = 1.5  # stretch every in-line pause for clearer phrasing
os.makedirs(out_dir, exist_ok=True)

# id, caption, spoken parts (strings are phrases, numbers are pauses, *stressed*)
LINES = [
    ("intro1", "This is Every Flat, Priced, from team FableAndAstra.",
     ["This is Every Flat, Priced,", .15, "from team Fable and Astra."]),
    ("intro2", "We valued all 181,711 flats in the City of Sydney, as at 31 August 2026.",
     ["We valued all one hundred and eighty-one thousand flats in the City of Sydney,", .15,
      "as at the thirty-first of August, twenty twenty-six."]),
    ("run1", "Everything runs from one script.", ["Everything runs from one script."]),
    ("run2", "First, a blind test: train only on sales before March, then price the flats that sold after.",
     ["First, a blind test:", .15, "train only on sales before March,", .1, "then price the flats that sold after."]),
    ("run3", "72% land within 10% of the real price. A suburb median gets 42%.",
     ["*Seventy-two percent* land within ten percent of the real price.", .2, "A suburb median gets forty-two."]),
    ("run3b", "A second blind test, from September 2025, scores 71%. Stable, not lucky.",
     ["A second blind test, from September twenty twenty-five,", .15, "scores seventy-one percent.", .3, "*Stable, not lucky.*"]),
    ("run4", "Then one command writes the submission: every address, no gaps.",
     ["Then one command writes the submission:", .15, "every address, no gaps."]),
    ("data1", "Our report starts with what the data told us.", ["Our report starts with what the data told us."]),
    ("data2", "Most flats have never sold, so we lean on the building and the street.",
     ["Most flats have never sold,", .1, "so we lean on the building and the street."]),
    ("data3", "Bedroom counts only start in 2010, so we fill the gaps from the Microburbs API.",
     ["Bedroom counts only start in twenty ten,", .1, "so we fill the gaps from the Microburbs A P I."]),
    ("data4", "And the market turned this year: a peak in February, a dip in winter, then steady.",
     ["And the market turned this year:", .15, "a peak in February,", .1, "a dip in winter,", .1, "then steady."]),
    ("data5", "No single clue gets more than about half the flats right. Combined, we get seven in ten.",
     ["No single clue gets more than about half the flats right.", .2, "*Combined, we get seven in ten.*"]),
    ("ins0", "Quick wins for buyers: prices are 5% off the peak, a car space adds about $84,000, and higher floors sell for a little more.",
     ["Quick wins for buyers:", .2, "prices are five percent off the peak,", .15, "a car space adds about *eighty-four thousand dollars,*", .15, "and higher floors sell for a little more."]),
    ("ins1", "For buyers, here is what a flat costs in every suburb.",
     ["For buyers,", .1, "here is what a flat costs in every suburb."]),
    ("ins2", "Switch to two bedrooms, and the ranking changes.",
     ["Switch to two bedrooms,", .1, "and the ranking changes."]),
    ("ins3", "Or sort by growth, to see where prices rose fastest.",
     ["Or sort by growth,", .1, "to see where prices rose fastest."]),
    ("mod1", "The model works in four steps.", ["The model works in four steps."]),
    ("mod2", "It only ever sees sales before the split date, and we test it on what sold afterwards.",
     ["It only ever sees sales before the split date,", .1, "and we test it on what sold afterwards."]),
    ("mod3", "We picked sales from 2010 after testing eight different time windows.",
     ["We picked sales from twenty ten", .1, "after testing *eight different time windows.*"]),
    ("res1", "Seven in ten within 10%, and a typical miss of $48,000.",
     ["*Seven in ten* within ten percent,", .1, "and a typical miss of forty-eight thousand dollars."]),
    ("res1b", "R squared is 0.86: our values explain most of why one flat costs more than another.",
     ["R squared is zero point eight six:", .25, "our values explain most of why one flat costs more than another."]),
    ("res2", "It holds up for flats that never sold before, and across price bands.",
     ["It holds up for flats that never sold before,", .1, "and across price bands."]),
    ("res3", "When we miss, we lean slightly high, so lenders should keep a margin.",
     ["When we miss, we lean slightly high,", .1, "so lenders should keep a margin."]),
    ("look1", "Now, the part anyone can use.", ["*Now, the part anyone can use.*"]),
    ("look2", "Pick a suburb, say Zetland, and only the big buildings.",
     ["Pick a suburb,", .1, "say Zetland,", .1, "and only the big buildings."]),
    ("look2b", "Add an evidence filter, and you only see buildings a bank could value from the desk.",
     ["Add an evidence filter,", .15, "and you only see buildings a bank could value *from the desk.*"]),
    ("look3", "Click one, and you see today's value by bedrooms, against the suburb.",
     ["Click one,", .1, "and you see today's value by bedrooms,", .1, "against the suburb."]),
    ("look4", "Below, real sales against what we said beforehand. Most land within 10%.",
     ["Below,", .1, "real sales against what we said beforehand.", .2, "Most land within ten percent."]),
    ("look5", "You can also search any street, like Harris Street.",
     ["You can also search any street,", .1, "like Harris Street."]),
    ("end1", "Under the hood: a LightGBM model on sales from 2010.",
     ["Under the hood:", .1, "a Light G B M model on sales from twenty ten."]),
    ("end2", "Every flat, priced. Thanks for watching.", ["*Every flat, priced.*", .4, "Thanks for watching."]),
]

k = Kokoro(model, voices)


def trim(a, thr=0.01):
    idx = np.where(np.abs(a) > thr)[0]
    return a[idx[0]:idx[-1] + 1] if len(idx) else a


def say(text):
    stressed = text.startswith("*")
    a, _ = k.create(text.strip("*"), voice=VOICE, speed=1.0 * (0.9 if stressed else 1.0), lang="en-gb")
    a = trim(a).astype(np.float32)
    if stressed:
        a = a * 10 ** (3.0 / 20)
    f = min(len(a) // 4, int(0.012 * SR))
    a[:f] *= np.linspace(0, 1, f)
    a[-f:] *= np.linspace(1, 0, f)
    return a


meta = []
for lid, cap, parts in LINES:
    audio = np.concatenate([np.zeros(int(p * PAUSE * SR), np.float32) if isinstance(p, float) else say(p) for p in parts])
    audio /= max(1e-6, np.abs(audio).max()) / 0.9
    sf.write(os.path.join(out_dir, lid + ".wav"), audio, SR)
    meta.append({"id": lid, "caption": cap, "dur": round(len(audio) / SR, 3)})
    print(f"{lid:6s} {len(audio) / SR:5.2f}s  {cap}")
json.dump(meta, open(os.path.join(out_dir, "demo_lines.json"), "w"), indent=1)
print("total speech", round(sum(m["dur"] for m in meta), 1), "s")
