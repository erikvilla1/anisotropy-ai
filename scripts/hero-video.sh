#!/usr/bin/env bash
# Turn the licensed hero clip into the site's web copy (ADR-0069).
#
#   scripts/hero-video.sh <original clip>
#
# Keeps the original in .local/media/ and writes public/media/hero.mp4 and public/media/hero.jpg. Both folders are
# git-ignored: the clip's licence forbids a downloadable standalone copy, and this repository is public.
# Needs ffmpeg and ffprobe (macOS: brew install ffmpeg).
set -euo pipefail

src="${1:?usage: scripts/hero-video.sh <original clip>}"
[ -f "$src" ] || { echo "No such file: $src" >&2; exit 1; }
for tool in ffmpeg ffprobe; do
  command -v "$tool" >/dev/null || { echo "$tool is not installed (macOS: brew install ffmpeg)" >&2; exit 1; }
done

root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$root/.local/media" "$root/public/media"
cp "$src" "$root/.local/media/$(basename "$src")"

# The loop: the clip from 1 s to its end, with its last second cross-faded into its first, so the last frame leads back to
# the first without a jump.
duration="$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$src")"
offset="$(awk -v d="$duration" 'BEGIN { if (d < 4) { print "too short"; exit 1 } printf "%.3f", d - 2 }')"

# The web copy: 1920 px wide, greyscale (the page shows it greyscale, so colour would only cost bytes), no sound, H.264 that
# starts playing before it has fully downloaded.
ffmpeg -y -v error -i "$src" -an -filter_complex \
  "[0:v]scale=1920:-2:flags=lanczos,format=gray,split[a][b];\
   [a]trim=start=1,setpts=PTS-STARTPTS[body];\
   [b]trim=end=1,setpts=PTS-STARTPTS[head];\
   [body][head]xfade=transition=fade:duration=1:offset=${offset},format=yuv420p[out]" \
  -map "[out]" -c:v libx264 -preset slow -crf 26 -profile:v high -movflags +faststart "$root/public/media/hero.mp4"

# The poster: the copy's first frame, shown while the clip loads and to visitors who ask for reduced motion.
ffmpeg -y -v error -i "$root/public/media/hero.mp4" -frames:v 1 -q:v 3 "$root/public/media/hero.jpg"

ls -lh "$root/public/media/hero.mp4" "$root/public/media/hero.jpg"
