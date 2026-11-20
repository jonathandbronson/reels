#!/usr/bin/env python3
"""Do sound hits land on scene cuts?  python tools/sync_check.py <video.mp4> [--tol 0.1]

Finds cuts with ffmpeg scene detection and strong audio onsets with `hyperframes audio`,
then flags every cut with no strong onset within the tolerance. Exit code 1 if any miss."""
import argparse, json, re, subprocess, sys
from pathlib import Path
from common import ffmpeg, hyperframes

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("--tol", type=float, default=0.1, help="seconds")
ap.add_argument("--scene", type=float, default=0.08, help="ffmpeg scene-change threshold")
ap.add_argument("--strength", type=float, default=0.5, help="minimum onset strength that counts as a hit")
a = ap.parse_args()
video = Path(a.video).resolve()

det = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(video), "-vf", f"select='gt(scene,{a.scene})',showinfo",
                      "-an", "-f", "null", "-"], capture_output=True, text=True)
cuts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", det.stderr)]

res = hyperframes("audio", video, "--only", "onsets", "--json", capture=True)
data = json.loads(res.stdout[res.stdout.index("{"):])
onsets = []


def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "onsets" and isinstance(v, dict):
                onsets.extend(e["t"] for e in v.get("events", []) if e.get("strength", 0) >= a.strength)
            else:
                walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(data)
miss = [c for c in cuts if not any(abs(c - o) <= a.tol for o in onsets)]
print(f"{len(cuts)} cuts, {len(onsets)} strong audio onsets, tolerance {a.tol}s")
for c in cuts:
    print(f"  cut {c:6.2f}s  {'MISSING HIT' if c in miss else 'ok'}")
print(f"{len(miss)} cuts without a hit")
sys.exit(1 if miss else 0)
