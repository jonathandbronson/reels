# reels — how to make a reel

When asked to "make a reel about X", run this pipeline end to end. Each reel is its own
HyperFrames project in `reels/<slug>/`. Load the `/hyperframes` skill before writing scenes
(installed by `python tools/setup.py`); skip its usage beacon (telemetry).

All tools are Python and run on Windows, macOS and Linux. Use `python` (Windows) or `python3`.
Run them from the repo root.

## Pipeline

1. **Research**: check facts before writing. Prefer primary/reputable sources; leave out details
   sources disagree on. List sources in `script.md`.
2. **Scaffold**: `python tools/new_reel.py <slug>` → `reels/<slug>/` (1080×1920, local GSAP).
3. **Script**: write `reels/<slug>/script.md`, one narration line per scene:
   `- [scene-id] What the narrator says.` Hook in the first line, 4–8 scenes, ~25–45 s total.
4. **Voice**: `python tools/voice.py reels/<slug>` → per-scene wavs, `vo.wav`, `timing.json`.
   ElevenLabs if `ELEVENLABS_API_KEY` is set, else the free local Kokoro voice
   (`--voice am_michael|af_heart|bm_george|…`).
5. **3D shots**: one shot per scene, full screen. Write or extend a Blender script in
   `tools/blender/` (`ssus_hq.py` is the reference: modelled ship, ocean modifier, physical sky,
   weathering, underwater volume, camera moves). Render with the wrapper, which runs the Blender
   app headless and uses the GPU:
   ```
   python tools/render_shot.py tools/blender/<script>.py <shot> reels/<slug>/assets/blender/<shot>.mp4 --seconds <scene length + 0.4>
   ```
   - Look-dev first: `--still look.png --res 540x960` renders one frame in seconds. Look at it.
   - `--engine eevee` (default) is fast on any GPU, including Intel Arc. `--engine cycles` is
     path-traced and uses OptiX/CUDA/HIP/oneAPI/Metal when Blender finds a GPU.
   - Render at 24 fps and 1080×1920 when the machine is fast enough; on a slow machine use
     `--fps 12 --res 720x1280` (frames are motion-interpolated and upscaled).
   - Make each shot ~0.4 s longer than its scene so footage never runs out.
6. **Sound**: `python tools/sfx.py reels/<slug>/assets/source/sounds` (whoosh + hit), or
   CC-licensed effects from Openverse. Whoosh ~0.45 s before each cut, hit on it.
7. **Scenes**: one `compositions/<scene-id>.html` per script line; text only (titles, captions,
   counters), the footage lives in the root. Generate `index.html` from `timing.json` with a
   `build_index.py` like `reels/ss-united-states/build_index.py`: full-screen `<video>` per scene,
   a gradient scrim for legibility, scene hosts, voice and sound clips.
8. **Check**: in the reel folder, `npx hyperframes check --json` → fix every error, weigh warnings
   (contrast, safe zones). Then `npx hyperframes snapshot --at …` and look at the frames.
9. **Render**: in the reel folder, `npx hyperframes render -o renders/<slug>.mp4 --quality delivery`.
10. **Sync check**: `python tools/sync_check.py reels/<slug>/renders/<slug>.mp4` → every cut has a hit.

## Folder layout per reel

```
script.md                 narration (one line per scene) + sources
build_index.py            writes index.html from timing.json
assets/source/voice/      tools/voice.py output (vo.wav, timing.json)
assets/source/sounds/     sound effects
assets/blender/           rendered 3D shots
assets/vendor/gsap.min.js local GSAP (no CDN at render time)
compositions/             one scene per file (text and graphics)
index.html                root: full-screen shots, scrim, scene hosts, audio
renders/                  final MP4s (git-ignored)
```

## Rules
- Renders must not touch the network: no CDN scripts, fonts or images by URL.
- Use only media you made or that is openly licensed; note sources in `script.md`.
- On a laptop, render plugged in with Windows power mode set to Best performance.
