#!/usr/bin/env bash
# Synthesize basic sound effects locally: tools/sfx.sh <out_dir>
# Stand-ins for Openverse downloads (openverse.org, CC-licensed) when that host isn't reachable.
set -euo pipefail
OUT="${1:?usage: sfx.sh <out_dir>}"; mkdir -p "$OUT"
# whoosh: 0.6s band-passed noise that swells and fades
ffmpeg -v error -y -f lavfi -i "anoisesrc=d=0.6:c=pink:a=0.6" \
  -af "highpass=f=300,lowpass=f=3000,afade=t=in:d=0.4,afade=t=out:st=0.42:d=0.18,loudnorm=I=-16" "$OUT/whoosh.wav"
# hit: punchy impact (pitched-down body + bright transient), audible on phone speakers
ffmpeg -v error -y -f lavfi -i "sine=f=140:d=0.45" -f lavfi -i "anoisesrc=d=0.09:c=white:a=1" \
  -filter_complex "[0]afade=t=out:st=0:d=0.45,volume=2[a];[1]lowpass=f=5000,afade=t=out:st=0:d=0.09[b];[a][b]amix=inputs=2:normalize=0,loudnorm=I=-12" "$OUT/hit.wav"
echo "wrote $OUT/whoosh.wav $OUT/hit.wav"
