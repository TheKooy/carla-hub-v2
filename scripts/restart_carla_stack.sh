#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
export CARLA_HUB_REPO_DIR="$REPO_DIR"

python3 -m carla_hub.main --config "$REPO_DIR/config/projects.json" restart-stack

sleep 3

pkill -f qpwgraph 2>/dev/null || true
sleep 1

"$REPO_DIR/scripts/start_qpwgraph_bg.sh"
