#!/usr/bin/env python3
"""Render a Blender shot script headless, on the GPU when available.

  python tools/render_shot.py tools/blender/ssus_hq.py hero reels/<slug>/assets/blender/hero.mp4 --seconds 5.2
  python tools/render_shot.py tools/blender/ssus_hq.py hero x.mp4 --still look.png        # one look-dev frame

Everything after the script path is passed to the script. Uses the Blender app (set BLENDER to its
path if it isn't found); falls back to the `bpy` pip module (CPU only) when no app is installed."""
import subprocess, sys, time
from pathlib import Path
from common import blender_cmd

if len(sys.argv) < 2:
    sys.exit(__doc__)
script = Path(sys.argv[1]).resolve()
cmd = blender_cmd(script, sys.argv[2:])
print("running:", " ".join(f'"{c}"' if " " in c else c for c in cmd[:2]), "…", script.name, *sys.argv[2:4])
t = time.time()
rc = subprocess.run(cmd).returncode
print(f"done in {time.time() - t:.0f}s (exit {rc})")
sys.exit(rc)
