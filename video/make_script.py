"""Write pitch_script.md and pitch_captions.srt from the captions in pitch.html."""
import re

import json
caps = [(a, b, "", t) for a, b, t, _ in json.load(open("timing.json"))["caps"]]


def ts(x):
    ms = int(round(float(x) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


open("pitch_captions.srt", "w").write("\n".join(f"{i + 1}\n{ts(a)} --> {ts(b)}\n{t}\n" for i, (a, b, _, t) in enumerate(caps)))
scenes = ["Hook: the city lights up, card 72% never sold", "Title: Every flat. Priced. 181,711 counts up",
          "01 The trick: zoom into Zetland, 6 Kingsborough Way", "01 The trick: bedroom bars for the building",
          "02 The proof: 72% card", "02 The proof: bars 72% vs 50% vs 42%",
          "03 For buyers: suburbs coloured by value", "03 For buyers: +$84k car space",
          "04 For lenders: dots by evidence level", "04 For lenders: orange means it needs a valuer",
          "Market: price line, peak then down 4.9%", "End: summary chips, FableAndAstra card"]
rows = "\n".join(f"| {a} to {b}s | {sc} | {t} |" for (a, b, _, t), sc in zip(caps, scenes))
words = sum(len(t.split()) for *_, t in caps)
open("pitch_script.md", "w").write(f"""# Pitch video voiceover script

`pitch.mp4`: 44.5 s, 1080x1920, silent, captions burned in. Record one take, about {words} words.
Read each line inside its time window. The captions show you where you are.

| Time | On screen | Say |
|---|---|---|
{rows}

## Tips

- Pace: about 2.5 words a second. The finished video already has this voice; the script is for re-recording.
- Say "seventy-two percent" and "eighty-four thousand dollars" in full.
- Add the voice in CapCut or iMovie: import `pitch.mp4`, drop the voice track at 0:00, and nudge it so
  each line starts with its caption. Export 1080x1920 and keep the file under 95 MB.
- Optional quiet background music, about 20 dB under the voice.

`pitch_captions.srt` has the same lines with timings.
""")
print(words, "words")
