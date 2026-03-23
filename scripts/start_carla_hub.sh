#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
export CARLA_HUB_REPO_DIR="$REPO_DIR"

mkdir -p "$HOME/.local/state/carla-hub/logs"

python3 -m carla_hub.main --config "$REPO_DIR/config/projects.json" hub \
  >"$HOME/.local/state/carla-hub/logs/carla-hub-ui.log" 2>&1 &
