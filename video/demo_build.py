"""Assemble demo.mp4 from the recorded frames and the voice lines.

Usage: python demo_build.py <framesDir> <voiceDir> <out.mp4>
"""
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

frames_dir, voice_dir, out = sys.argv[1:4]
frames = json.load(open(os.path.join(frames_dir, "frames.json")))
lines = json.load(open(os.path.join(frames_dir, "lines.json")))
t0 = frames[0][1]
end = frames[-1][1] - t0 + 0.5

# video: each frame shown until the next one arrives
with open(os.path.join(frames_dir, "list.ffconcat"), "w") as f:
    f.write("ffconcat version 1.0\n")
    for (name, ts), nxt in zip(frames, frames[1:] + [[frames[-1][0], frames[-1][1] + 0.5]]):
        f.write(f"file {name}\nduration {max(0.001, nxt[1] - ts):.4f}\n")
    f.write(f"file {frames[-1][0]}\n")

# audio: each line at the moment it started during recording
SR = 24000
track = np.zeros(int((end + 1) * SR), np.float32)
for L in lines:
    a, _ = sf.read(os.path.join(voice_dir, L["id"] + ".wav"), dtype="float32")
    s = int((L["start"] - t0 + 0.12) * SR)
    track[s:s + len(a)] += a[:len(track) - s]
wav = os.path.join(frames_dir, "voice.wav")
sf.write(wav, track, SR)

subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(frames_dir, "list.ffconcat"),
                "-i", wav, "-map", "0:v", "-map", "1:a",
                "-vf", "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "160k",
                "-t", f"{end:.2f}", "-movflags", "+faststart", out], check=True)
print("wrote", out, f"{end:.1f}s")
