"""Make the pitch voiceover with Kokoro TTS and let the voice set the video's timing.

Lines are read end to end with natural pauses and light stress. The script then writes
timing.json: caption windows that follow the voice, and scene start times, which pitch.html
uses to stretch or shrink each scene so the pictures match what is being said.

Usage: python make_voice.py <kokoro.onnx> <voices.bin> <voice> <out.wav> [speed] [lang]
"""
import json
import sys

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

model, voices, voice, out = sys.argv[1:5]
SPEED = float(sys.argv[5]) if len(sys.argv) > 5 else 1.02
LANG = sys.argv[6] if len(sys.argv) > 6 else "en-gb"
DURATION, SR = 44.5, 24000

# scene, caption text, highlighted words, spoken parts
# (strings are phrases, numbers are pauses in seconds, *phrase* is stressed: a little slower and louder)
LINES = [
    (0, "You want a flat in Sydney. It's never been sold.", ["never", "been", "sold."],
     ["You want a flat in Sydney.", .3, "*It's never been sold.*"]),
    (1, "So what's it worth? We priced every flat in the city.", ["every", "flat"],
     ["So what's it worth?", .35, "*We priced every flat in the city.*"]),
    (2, "Here's the trick. One clue is never enough,", ["trick."],
     ["*Here's the trick.*", .25, "One clue is never enough,"]),
    (2, "so we combine them all: past sales, the building, the bedrooms.", ["combine"],
     ["so we combine them all:", .15, "past sales, the building, the bedrooms."]),
    (3, "We tested it blind, on sales it had never seen.", ["blind,"],
     ["We tested it blind,", .1, "on sales it had never seen."]),
    (3, "Seven in ten came within 10%. Nearly double the usual method.", ["Seven", "in", "ten"],
     ["*Seven in ten came within ten percent.*", .2, "Nearly double the usual method."]),
    (4, "Buyers get a fair price before they bid,", ["fair", "price"],
     ["Buyers get a fair price before they bid,"]),
    (4, "and know a car space adds $84,000.", ["$84,000."],
     ["and know a car space adds", .1, "*eighty-four thousand dollars.*"]),
    (5, "Banks see which flats are safe to value from a desk,", ["safe"],
     ["Banks see which flats are safe to value from a desk,"]),
    (5, "and which need a valuer.", ["valuer."],
     ["and which need a valuer."]),
    (6, "And it's already priced for this year's dip.", ["already"],
     ["And it's already priced for this year's dip."]),
    (7, "FableAndAstra. Every flat, priced.", ["Every", "flat,", "priced."],
     ["Fable and Astra.", .4, "*Every flat, priced.*"]),
]
GAP_SAME, GAP_NEW = 0.2, 0.4  # pause between lines in the same scene / at a scene change

k = Kokoro(model, voices)


def trim(a, thr=0.01):
    idx = np.where(np.abs(a) > thr)[0]
    return a[idx[0]:idx[-1] + 1] if len(idx) else a


def say(text, speed):
    stressed = text.startswith("*")
    a, _ = k.create(text.strip("*"), voice=voice, speed=speed * (0.96 if stressed else 1.0), lang=LANG)
    a = trim(a).astype(np.float32)
    if stressed:
        a = a * 10 ** (2.0 / 20)  # +2 dB
    f = min(len(a) // 4, int(0.012 * SR))  # short fades so joins don't click
    a[:f] *= np.linspace(0, 1, f)
    a[-f:] *= np.linspace(1, 0, f)
    return a


def build(parts, speed):
    return np.concatenate([np.zeros(int(p * SR), np.float32) if isinstance(p, float) else say(p, speed)
                           for p in parts])


clips = [build(parts, SPEED) for *_, parts in LINES]
t, spans = 0.3, []
for i, c in enumerate(clips):
    if i:
        t += GAP_NEW if LINES[i][0] != LINES[i - 1][0] else GAP_SAME
    spans.append((t, t + len(c) / SR))
    t += len(c) / SR
assert t <= DURATION - 0.2, f"voice runs to {t:.2f}s; raise the speed"

track = np.zeros(int(DURATION * SR), dtype=np.float32)
for (a, _), c in zip(spans, clips):
    s = int(a * SR)
    track[s:s + len(c)] += c[:len(track) - s]
track /= max(1e-6, np.abs(track).max()) / 0.9
sf.write(out, track, SR)

# captions follow the voice; each scene starts a moment before its first line
caps = []
for i, ((a, b), (_, text, hl, _)) in enumerate(zip(spans, LINES)):
    nxt = spans[i + 1][0] if i + 1 < len(spans) else DURATION
    caps.append([round(a - 0.05, 2), round(min(b + 0.3, nxt - 0.05), 2), text, hl])
scenes = [0.0]
for sc in range(1, 8):
    first = next(i for i, l in enumerate(LINES) if l[0] == sc)
    scenes.append(round(spans[first][0] - 0.25, 2))
json.dump({"caps": caps, "scenes": scenes, "speed": SPEED}, open("timing.json", "w"), indent=1)
for (a, b), l in zip(spans, LINES):
    print(f"{a:5.2f} to {b:5.2f}  scene {l[0]}  {l[1]}")
print("scenes start at", scenes, "| voice ends", round(t, 2), "| wrote", out)
