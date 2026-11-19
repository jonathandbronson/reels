# reel-studio — how to make a reel

When asked to "make a reel about X", run this pipeline end to end. Each reel is its own
HyperFrames project in `reels/<slug>/`. Load the `/hyperframes` skill before writing scenes
(installed by `./setup.sh`); skip its usage beacon (telemetry).

## Pipeline

1. **Scaffold**: `tools/new-reel.sh <slug>` → `reels/<slug>/` (1080×1920, local GSAP, folders below).
2. **Script**: write `reels/<slug>/script.md`, one narration line per scene:
   `- [scene-id] What the narrator says.` Hook in the first line, 3–8 scenes, ~20–45 s total.
3. **Voice**: `python3 tools/voice.py reels/<slug>` → per-scene wavs, `vo.wav`, `timing.json`.
   ElevenLabs if `ELEVENLABS_API_KEY` is set (needs `api.elevenlabs.io` allowed on the network),
   else the local Kokoro voice (free, offline). `--voice am_michael|af_heart|bm_george|…`
4. **3D shots** (optional): write a Blender script per shot in `tools/blender/` (copy `liner.py`),
   render with `python3 tools/blender/<shot>.py reels/<slug>/assets/blender/<shot>.mp4`.
   CPU only here: ~5 s/frame at 540×960, 16 samples. Keep shots short and slow them with
   `data-playback-rate` rather than rendering more frames.
5. **Sound**: put effects in `assets/source/sounds/`. Prefer CC-licensed files from Openverse
   (`openverse.org`, needs that host allowed); `tools/sfx.sh <dir>` synthesizes a whoosh and hit offline.
6. **Scenes**: one `compositions/<scene-id>.html` per script line. Scene starts/durations come
   from `timing.json`. Root `index.html` holds only scene hosts (`id` = `data-composition-id`),
   the video shots and the `<audio>` clips. Put a whoosh ~0.45 s before each cut and a hit on it.
7. **Check**: in the reel folder, `npx hyperframes check --json` → fix every error, weigh warnings
   (safe zones: keep text between y≈280 and y≈1450). Then `npx hyperframes snapshot --at …` and look.
8. **Render**: `npx hyperframes render -o renders/<slug>.mp4 --quality delivery`.
9. **Sync check**: `tools/sync-check.sh reels/<slug>/renders/<slug>.mp4` — every cut should have a hit.

## Folder layout per reel

```
script.md                 narration, one line per scene
assets/source/voice/      tools/voice.py output (vo.wav, timing.json)
assets/source/sounds/     sound effects
assets/blender/           rendered 3D shots
assets/vendor/gsap.min.js local GSAP (no CDN at render time)
compositions/             one scene per file
index.html                root: scene hosts, shots, audio
renders/                  final MP4s (git-ignored)
```

## Rules
- Renders must not touch the network: no CDN scripts, fonts or images by URL.
- Use only media you made or that is openly licensed; note sources in `script.md`.
