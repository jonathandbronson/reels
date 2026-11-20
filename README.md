# reels

Animated, narrated vertical reels made by Claude Code, with no filming. Each scene's footage is
a 3D shot built and animated in code with Blender, text and captions are HTML animated with GSAP,
and [HyperFrames](https://github.com/heygen-com/hyperframes) renders the result to a 1080×1920 MP4.
Narration comes from ElevenLabs or a free local voice.

Example: `reels/ss-united-states` (39 s, six full-screen 3D shots).

## Setup on Windows (e.g. a laptop with Intel Arc graphics)

1. **Install the tools** in PowerShell, then close and reopen it so PATH updates:
   ```powershell
   winget install -e --id Git.Git
   winget install -e --id OpenJS.NodeJS.LTS
   winget install -e --id Python.Python.3.12
   winget install -e --id Gyan.FFmpeg
   winget install -e --id BlenderFoundation.Blender
   ```
2. **Install Claude Code**: use the Claude desktop app, or install the CLI by following
   https://code.claude.com/docs/en/setup.
3. **Get the repo and set up**:
   ```powershell
   git clone https://github.com/jonathandbronson/reels
   cd reels
   python tools/setup.py
   ```
   The last lines report the Blender version and GPU. `CYCLES_GPU ONEAPI: Intel(R) Arc(TM) …`
   means Cycles can use your GPU. `none` is fine: shots default to EEVEE, which uses the GPU anyway.
4. **Optional, ElevenLabs voice**: create an API key at elevenlabs.io, then run
   `setx ELEVENLABS_API_KEY "your-key"` and open a new terminal. Without it, the free local voice is used.
5. **Check your GPU in Blender (optional)**: open Blender → Edit → Preferences → System →
   Cycles Render Devices → oneAPI. If your Arc GPU is listed, tick it.

If Blender is installed somewhere unusual, set `BLENDER` to the full path of `blender.exe`.

macOS and Linux work the same way: install the same tools (Homebrew / your package manager),
then run `python3 tools/setup.py`.

## Make a reel

Open Claude Code in the `reels` folder and ask: *"make a reel about how the SS United States went
down"*. `CLAUDE.md` holds the steps it follows. By hand:

```powershell
python tools/new_reel.py my-reel
# write reels/my-reel/script.md: one "- [scene] narration" line per scene
python tools/voice.py reels/my-reel
python tools/render_shot.py tools/blender/ssus_hq.py hero reels/my-reel/assets/blender/hero.mp4 --seconds 5.5
python tools/sfx.py reels/my-reel/assets/source/sounds
# write compositions/*.html and build index.html from timing.json, then:
cd reels/my-reel; npx hyperframes check; npx hyperframes render -o renders/my-reel.mp4 --quality delivery; cd ../..
python tools/sync_check.py reels/my-reel/renders/my-reel.mp4
```

Tip: render one frame first to check the look. It takes seconds:
`python tools/render_shot.py tools/blender/ssus_hq.py hero x.mp4 --still look.png --res 540x960`

## Tools

| Tool | What it does |
| --- | --- |
| `tools/setup.py` | Installs packages and skills, checks ffmpeg/Blender, reports GPU |
| `tools/new_reel.py` | Scaffolds `reels/<slug>/` |
| `tools/voice.py` | Narration per scene + `timing.json` (ElevenLabs or local Kokoro) |
| `tools/render_shot.py` | Runs a Blender shot script headless on the GPU (`--engine eevee` / `cycles`) |
| `tools/blender/ssus_hq.py` | Reference shot script: SS United States, ocean, sky, pier, sinking, underwater |
| `tools/sfx.py` | Synthesizes whoosh and hit sound effects |
| `tools/sync_check.py` | Checks that a sound hit lands on every scene cut |

## Rendering speed

| Machine | 1080×1920 frame (ssus_hq) |
| --- | --- |
| Cloud container, 4 CPU cores, Cycles | ~15–18 s (needed 12 fps + interpolation) |
| Laptop GPU (Intel Arc / AMD / Apple), EEVEE | expect a few seconds or less |
| NVIDIA RTX, Cycles OptiX | ~1–2 s |

The laptop and NVIDIA figures are estimates; `--still` gives you a real number in seconds.
