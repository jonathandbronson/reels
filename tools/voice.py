#!/usr/bin/env python3
"""Voice a reel's script.md, one clip per scene line.

Usage: python tools/voice.py reels/<slug> [--voice am_michael]

Uses ElevenLabs when ELEVENLABS_API_KEY is set (voice id from ELEVENLABS_VOICE_ID),
otherwise the free local Kokoro voice bundled with HyperFrames.

Writes:
  assets/source/voice/<scene>.wav   one clip per line
  assets/source/voice/vo.wav        all lines joined, with GAP seconds between them
  assets/source/voice/timing.json   [{scene, text, start, duration}] in film seconds
"""
import argparse, json, os, re, subprocess, sys, urllib.request
from pathlib import Path
from common import ffmpeg, npx, duration

GAP = 0.35  # silence between lines, seconds
LINE = re.compile(r"^\s*-\s*\[([\w-]+)\]\s*(.+?)\s*$")


def parse_script(path: Path):
    lines = [LINE.match(l) for l in path.read_text(encoding="utf-8").splitlines()]
    out = [(m[1], m[2]) for m in lines if m]
    if not out:
        sys.exit(f"{path}: no '- [scene] text' lines found")
    return out


def eleven(text: str, dest: Path):
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
        data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode(),
        headers={"xi-api-key": os.environ.get("ELEVENLABS_API_KEY", "injected-by-proxy"), "Content-Type": "application/json"},
    )
    mp3 = dest.with_suffix(".mp3")
    mp3.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(mp3), "-ar", "24000", "-ac", "1", str(dest)], check=True)
    mp3.unlink()


def kokoro(text: str, dest: Path, voice: str, cwd: Path):
    subprocess.run([npx(), "hyperframes", "tts", text, "-v", voice, "-o", str(dest)],
                   check=True, cwd=cwd, stdout=subprocess.DEVNULL,
                   env=dict(os.environ, HYPERFRAMES_TELEMETRY_DISABLED="1"))




def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reel")
    ap.add_argument("--voice", default="am_michael", help="Kokoro voice id (local fallback)")
    ap.add_argument("--engine", choices=["auto", "eleven", "kokoro"], default="auto",
                    help="auto = ElevenLabs if ELEVENLABS_API_KEY is set; 'eleven' also works when a "
                         "network proxy injects the key (cloud sessions)")
    a = ap.parse_args()
    reel = Path(a.reel).resolve()
    vdir = reel / "assets/source/voice"
    vdir.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parent.parent
    use_eleven = a.engine == "eleven" or (a.engine == "auto" and bool(os.environ.get("ELEVENLABS_API_KEY")))
    print("voice:", "ElevenLabs" if use_eleven else f"Kokoro ({a.voice}, local)")

    timing, t, parts = [], 0.0, []
    for scene, text in parse_script(reel / "script.md"):
        clip = vdir / f"{scene}.wav"
        eleven(text, clip) if use_eleven else kokoro(text, clip, a.voice, root)
        d = duration(clip)
        timing.append({"scene": scene, "text": text, "start": round(t, 3), "duration": round(d, 3)})
        parts.append(clip)
        t += d + GAP
        print(f"  {scene:<12} {d:5.2f}s  {text}")

    # Join clips with GAP of silence between them.
    inputs, filt = [], ""
    for i, p in enumerate(parts):
        inputs += ["-i", str(p)]
        filt += f"[{i}:a]aresample=24000,aformat=channel_layouts=mono,apad=pad_dur={GAP}[a{i}];"
    filt += "".join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[out]"
    subprocess.run([ffmpeg(), "-v", "error", "-y", *inputs, "-filter_complex", filt,
                    "-map", "[out]", str(vdir / "vo.wav")], check=True)
    (vdir / "timing.json").write_text(json.dumps(timing, indent=2), encoding="utf-8")
    print(f"total {t:.2f}s → {vdir/'vo.wav'}, timing.json")


if __name__ == "__main__":
    main()
