#!/bin/bash
# Regenerate every 2.0 store media file from the game build in this repository (game/v2web), or from another
# build: MF_WEB=/path/to/minifighter-source/game/dist/v2web store/media_v2/tools/make_all.sh
# Steps can be run alone: make_all.sh shots | video | check
set -euo pipefail
cd "$(dirname "$0")"
what="${1:-all}"
if [ "$what" = all ] || [ "$what" = shots ]; then
  python3 -u shots_raw.py          # real game captures (UI screens, chest reveal, two fights)
  python3 -u compose.py            # headline + frame, every store size, feature graphic
fi
if [ "$what" = all ] || [ "$what" = video ]; then
  python3 -u video_capture.py appstore   # frame-exact takes, 1920x886
  python3 -u video_edit.py               # the cuts, captions and sound
fi
python3 -u manifest.py             # spec check, manifest.json, contact sheets
