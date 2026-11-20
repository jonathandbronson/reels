#!/usr/bin/env python3
"""Synthesize basic sound effects offline:  python tools/sfx.py <out_dir>

Writes whoosh.wav (put ~0.45 s before a cut) and hit.wav (on the cut). Stand-ins for
CC-licensed effects from Openverse (openverse.org)."""
import subprocess, sys
from pathlib import Path
from common import ffmpeg

if len(sys.argv) != 2:
    sys.exit("usage: python tools/sfx.py <out_dir>")
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
ff = ffmpeg()

# whoosh: 0.6 s of band-limited pink noise that swells and fades
subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "anoisesrc=d=0.6:c=pink:a=0.6", "-af",
                "highpass=f=300,lowpass=f=3000,afade=t=in:d=0.4,afade=t=out:st=0.42:d=0.18,loudnorm=I=-16",
                str(out / "whoosh.wav")], check=True)
# hit: punchy impact (pitched body + bright transient), audible on phone speakers
subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=140:d=0.45", "-f", "lavfi", "-i",
                "anoisesrc=d=0.09:c=white:a=1", "-filter_complex",
                "[0]afade=t=out:st=0:d=0.45,volume=2[a];[1]lowpass=f=5000,afade=t=out:st=0:d=0.09[b];"
                "[a][b]amix=inputs=2:normalize=0,loudnorm=I=-12", str(out / "hit.wav")], check=True)
print(f"wrote {out / 'whoosh.wav'} and {out / 'hit.wav'}")
