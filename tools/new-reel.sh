#!/usr/bin/env bash
# Scaffold a new vertical reel: tools/new-reel.sh <slug>
# Creates reels/<slug>/ with the folder layout the pipeline expects.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SLUG="${1:?usage: new-reel.sh <slug>}"
DIR="$ROOT/reels/$SLUG"
[ -e "$DIR" ] && { echo "reels/$SLUG already exists" >&2; exit 1; }

cd "$ROOT/reels"
HYPERFRAMES_TELEMETRY_DISABLED=1 npx hyperframes init "$SLUG" --example blank \
  --resolution portrait --skip-skills --non-interactive >/dev/null

mkdir -p "$DIR"/{assets/source/voice,assets/source/sounds,assets/blender,assets/vendor,compositions}
# GSAP is served locally: renders must not depend on a CDN.
cp "$ROOT/node_modules/gsap/dist/gsap.min.js" "$DIR/assets/vendor/gsap.min.js"
sed -i 's#https://cdn.jsdelivr.net/npm/gsap@[0-9.]*/dist/gsap.min.js#assets/vendor/gsap.min.js#' "$DIR/index.html"

cat > "$DIR/script.md" <<'EOF'
# Title of the reel

<!-- One narration line per scene. Format:  - [scene-id] What the narrator says. -->
- [hook] First line: the hook.
- [beat2] Second line.
- [payoff] Last line: the payoff.
EOF
echo "Created reels/$SLUG — next: write script.md, then  python3 tools/voice.py reels/$SLUG"
