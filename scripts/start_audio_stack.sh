#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

mkdir -p "$HOME/.local/state/carla-hub/logs"

for i in {1..40}; do
  pactl info >/dev/null 2>&1 && break
  sleep 0.3
done

"$REPO_DIR/scripts/audio-setup.sh"
"$REPO_DIR/scripts/start_easyeffects_bg.sh"

for i in {1..40}; do
  wpctl status 2>/dev/null | grep -q "easyeffects_source" && break
  sleep 0.3
done

"$REPO_DIR/scripts/start_carla_bg.sh"

sleep 2

"$REPO_DIR/scripts/start_carla_hub.sh"

sleep 2

"$REPO_DIR/scripts/start_qpwgraph_bg.sh"
