#!/usr/bin/env bash
# Renders the hero's film with Blender and makes a video of it to watch (ADR-0092).
#
#   scripts/hero-plate.sh          a draft: 960 by 540, 24 frames a second, quick to render
#   scripts/hero-plate.sh final    the film: 1920 by 1080, 30 frames a second
#
# The frames go to the git-ignored .local/hero-plate/<draft|final>/, and the video beside them. A render that was stopped
# carries on where it left off; `scripts/hero-plate.sh draft fresh` throws the old frames away first, which a change to
# scripts/hero-plate.py needs. Needs Blender 4.2 or later and ffmpeg.
set -euo pipefail

mode="${1:-draft}"
case "$mode" in
  draft) options=(--scale 50 --samples 48 --fps 24); fps=24 ;;
  final) options=(--scale 100 --samples 128 --fps 30); fps=30 ;;
  *) echo "usage: scripts/hero-plate.sh [draft|final] [fresh]" >&2; exit 2 ;;
esac

root="$(cd "$(dirname "$0")/.." && pwd)"
out="$root/.local/hero-plate/$mode"
[ "${2:-}" = "fresh" ] && rm -rf "$out"
mkdir -p "$out/frames"

# Blender: the app on a Mac, or `blender` on the path. HERO_PLATE_RUNNER replaces the whole command, for a Python that has bpy.
if [ -n "${HERO_PLATE_RUNNER:-}" ]; then
  read -r -a runner <<< "$HERO_PLATE_RUNNER"
elif [ -x "/Applications/Blender.app/Contents/MacOS/Blender" ]; then
  runner=("/Applications/Blender.app/Contents/MacOS/Blender" -b -P)
elif command -v blender > /dev/null; then
  runner=(blender -b -P)
else
  echo "Blender was not found. Install it from blender.org, then run this again." >&2
  exit 1
fi
command -v ffmpeg > /dev/null || { echo "ffmpeg was not found (brew install ffmpeg)." >&2; exit 1; }

"${runner[@]}" "$root/scripts/hero-plate.py" -- --frames "$out/frames" "${options[@]}" ${HERO_PLATE_OPTIONS:-}

video="$out/hero-plate-$mode.mp4"
ffmpeg -y -v error -framerate "$fps" -i "$out/frames/frame-%04d.png" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart "$video"
echo "Wrote $video"
if command -v open > /dev/null; then open "$video"; fi
