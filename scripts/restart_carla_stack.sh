#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$HOME/.local/state/carla-hub/logs"
RESTART_LOG="$LOG_DIR/restart-stack.log"

mkdir -p "$LOG_DIR"

export PYTHONPATH="$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
export CARLA_HUB_REPO_DIR="$REPO_DIR"

{
  echo "===== $(date '+%F %T') restart_carla_stack.sh ====="

  python3 -m carla_hub.main --config "$REPO_DIR/config/projects.json" restart-stack

  echo "[info] Carla background stack restarted"
  sleep 3

  pkill -x qpwgraph 2>/dev/null || true

  for i in {1..40}; do
      if ! pgrep -x qpwgraph >/dev/null; then
          break
      fi
      sleep 0.2
  done

  echo "[info] Waiting for PipeWire graph to settle"
  sleep 2

  for attempt in 1 2 3; do
      echo "[info] qpwgraph launch attempt $attempt"
      if "$REPO_DIR/scripts/start_qpwgraph_bg.sh"; then
          echo "[ok] qpwgraph relaunched"
          exit 0
      fi
      sleep 1
  done

  echo "[error] qpwgraph failed to relaunch after 3 attempts"
  exit 1
} >>"$RESTART_LOG" 2>&1
