#!/usr/bin/env python3
"""Scaffold a new vertical reel:  python tools/new_reel.py <slug>

Creates reels/<slug>/ (1080x1920 HyperFrames project) with the folders the pipeline expects,
a local copy of GSAP (renders must not depend on a CDN) and a script.md template."""
import re, shutil, sys
from pathlib import Path
from common import ROOT, hyperframes

if len(sys.argv) != 2 or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sys.argv[1]):
    sys.exit("usage: python tools/new_reel.py <slug>   (lowercase letters, digits, dashes)")
slug = sys.argv[1]
reel = ROOT / "reels" / slug
if reel.exists():
    sys.exit(f"reels/{slug} already exists")

(ROOT / "reels").mkdir(exist_ok=True)
hyperframes("init", slug, "--example", "blank", "--resolution", "portrait", "--skip-skills",
            "--non-interactive", cwd=ROOT / "reels", capture=True)

for d in ("assets/source/voice", "assets/source/sounds", "assets/blender", "assets/vendor", "compositions"):
    (reel / d).mkdir(parents=True, exist_ok=True)
shutil.copy(ROOT / "node_modules/gsap/dist/gsap.min.js", reel / "assets/vendor/gsap.min.js")
index = reel / "index.html"
index.write_text(re.sub(r"https://cdn\.jsdelivr\.net/npm/gsap@[0-9.]+/dist/gsap\.min\.js",
                        "assets/vendor/gsap.min.js", index.read_text(encoding="utf-8")), encoding="utf-8")

(reel / "script.md").write_text("""# Title of the reel

<!-- One narration line per scene. Format:  - [scene-id] What the narrator says.
     Note sources here, and skip facts the sources disagree on. -->
- [hook] First line: the hook.
- [beat2] Second line.
- [payoff] Last line: the payoff.
""", encoding="utf-8")
print(f"Created reels/{slug} - next: write script.md, then  python tools/voice.py reels/{slug}")
