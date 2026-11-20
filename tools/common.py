"""Cross-platform helpers shared by the reel tools (Windows, macOS, Linux)."""
import glob, os, platform, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IS_WIN = platform.system() == "Windows"


def which(name: str) -> str | None:
    """shutil.which, which also finds npx.cmd / ffmpeg.exe on Windows."""
    return shutil.which(name)


def need(name: str, hint: str) -> str:
    path = which(name)
    if not path:
        sys.exit(f"'{name}' not found on PATH. {hint}")
    return path


def npx() -> str:
    return need("npx", "Install Node.js 22+ (winget install OpenJS.NodeJS.LTS).")


def ffmpeg() -> str:
    return need("ffmpeg", "Install ffmpeg (winget install Gyan.FFmpeg), then open a new terminal.")


def ffprobe() -> str:
    return need("ffprobe", "ffprobe ships with ffmpeg (winget install Gyan.FFmpeg).")


def hyperframes(*args, cwd=None, capture=False, check=True):
    """Run the HyperFrames CLI from the repo's node_modules, telemetry off."""
    env = dict(os.environ, HYPERFRAMES_TELEMETRY_DISABLED="1")
    return subprocess.run([npx(), "hyperframes", *map(str, args)], cwd=cwd or ROOT, env=env,
                          capture_output=capture, text=capture, check=check)


def find_blender() -> str | None:
    """The Blender app: $BLENDER, then PATH, then the default install folders."""
    env = os.environ.get("BLENDER")
    if env and Path(env).exists():
        return env
    found = which("blender")
    if found:
        return found
    candidates = []
    if IS_WIN:
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("LOCALAPPDATA", "")):
            candidates += glob.glob(os.path.join(base, "Blender Foundation", "Blender*", "blender.exe"))
            candidates += glob.glob(os.path.join(base, "Programs", "Blender Foundation", "Blender*", "blender.exe"))
    elif platform.system() == "Darwin":
        candidates.append("/Applications/Blender.app/Contents/MacOS/Blender")
    candidates = [c for c in candidates if Path(c).exists()]
    # newest version folder last after sorting
    return sorted(candidates)[-1] if candidates else None


def has_bpy_module() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("bpy") is not None
    except Exception:
        return False


def blender_cmd(script: Path, args: list[str]) -> list[str]:
    """Command that runs a Blender Python script headless.

    Prefers the Blender app (uses the GPU); falls back to the `bpy` pip module (CPU, e.g. cloud)."""
    app = find_blender()
    if app:
        return [app, "-b", "--factory-startup", "--python-exit-code", "1", "-P", str(script), "--", *args]
    if has_bpy_module():
        return [sys.executable, str(script), "--", *args]
    sys.exit("Blender not found. Install it (winget install BlenderFoundation.Blender) "
             "or set BLENDER to the full path of blender.exe.")


def script_args() -> list[str]:
    """Arguments meant for a Blender script: everything after '--' (works in the app and in bpy)."""
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]


def duration(path) -> float:
    out = subprocess.run([ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout)
