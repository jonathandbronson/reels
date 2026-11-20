#!/usr/bin/env python3
"""One-time setup, safe to re-run:  python tools/setup.py

Installs the HyperFrames CLI + GSAP (npm), the local voice (pip), the HyperFrames skills for
Claude Code, then checks ffmpeg and Blender and reports which GPU Blender can render with."""
import subprocess, sys
from common import ROOT, IS_WIN, which, npx, ffmpeg, hyperframes, find_blender, has_bpy_module, blender_cmd


def step(title):
    print(f"\n== {title}")


step("Node packages (hyperframes, gsap)")
subprocess.run([which("npm") or "npm", "install", "--no-fund", "--no-audit"], cwd=ROOT, check=True)

step("Python packages (local voice)")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "kokoro-onnx", "soundfile"], check=True)

step("HyperFrames skills for Claude Code")
hyperframes("telemetry", "disable", capture=True, check=False)
hyperframes("skills", capture=True, check=False)
print("installed (restart Claude Code to load them)")

step("ffmpeg")
ff = ffmpeg()
print(subprocess.run([ff, "-version"], capture_output=True, text=True).stdout.splitlines()[0])

step("Blender")
app = find_blender()
if app:
    print("app:", app)
elif has_bpy_module():
    print("no Blender app; using the bpy pip module (CPU only)")
else:
    print("NOT FOUND - install it: winget install BlenderFoundation.Blender"
          if IS_WIN else "NOT FOUND - install Blender from blender.org (or pip install bpy for CPU-only)")
if app or has_bpy_module():
    out = subprocess.run(blender_cmd(ROOT / "tools/blender/devices.py", []), capture_output=True, text=True)
    lines = [l for l in out.stdout.splitlines() if l.startswith(("BLENDER", "ENGINES", "CYCLES_GPU"))]
    print("\n".join(lines) or out.stdout[-800:] + out.stderr[-800:])

step("Voice")
import os
print("ElevenLabs:", "key set" if os.environ.get("ELEVENLABS_API_KEY") else
      "no ELEVENLABS_API_KEY - using the free local Kokoro voice")
print("\nSetup done.")
