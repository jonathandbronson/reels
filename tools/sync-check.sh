#!/usr/bin/env bash
# Check a rendered reel: do sound hits land on scene cuts?   tools/sync-check.sh reels/<slug>/renders/<file>.mp4
# Prints scene cuts (ffmpeg scene detection) and audio onsets (hyperframes audio),
# then flags each cut with no onset within TOL seconds.
set -euo pipefail
VID="${1:?usage: sync-check.sh <video.mp4> [tolerance_seconds]}"
TOL="${2:-0.1}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cuts=$(ffmpeg -hide_banner -i "$VID" -vf "select='gt(scene,0.08)',showinfo" -an -f null - 2>&1 \
  | grep -o 'pts_time:[0-9.]*' | cut -d: -f2 || true)
onsets=$(cd "$ROOT" && npx hyperframes audio "$(realpath "$VID")" --only onsets --json 2>/dev/null \
  | python3 -c 'import json,sys
d=json.load(sys.stdin)
def walk(o):
    if isinstance(o,dict):
        for k,v in o.items():
            if k=="onsets" and isinstance(v,dict):
                for x in v.get("events",[]):
                    if x.get("strength",0)>=0.5: print(x["t"])  # strong hits only, not every syllable
            else: walk(v)
    elif isinstance(o,list):
        for v in o: walk(v)
walk(d)')

python3 - "$TOL" <<EOF
import sys
tol=float(sys.argv[1])
cuts=[float(x) for x in """$cuts""".split()]
ons=[float(x) for x in """$onsets""".split()]
miss=[c for c in cuts if not any(abs(c-o)<=tol for o in ons)]
print(f"{len(cuts)} cuts, {len(ons)} strong audio onsets, tolerance {tol}s")
for c in cuts: print(f"  cut {c:6.2f}s  {'MISSING HIT' if c in miss else 'ok'}")
print(f"{len(miss)} cuts without a hit")
EOF
