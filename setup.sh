#!/usr/bin/env bash
# One-time setup for reel-studio. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"
npm install                                   # hyperframes CLI + gsap
pip install -q kokoro-onnx soundfile bpy==5.3.0  # local voice fallback + Blender as a Python module
npx hyperframes skills >/dev/null             # HyperFrames skills for Claude Code (~/.claude/skills)
npx hyperframes telemetry disable >/dev/null 2>&1 || true
npx hyperframes doctor | grep -E '✓|✗' || true
