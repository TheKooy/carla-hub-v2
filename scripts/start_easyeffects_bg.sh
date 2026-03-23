#!/bin/bash
set -euo pipefail

mkdir -p "$HOME/.local/state/carla-hub/logs"

pgrep -f "easyeffects --gapplication-service" >/dev/null || \
  easyeffects --gapplication-service \
    >"$HOME/.local/state/carla-hub/logs/easyeffects-bg.log" 2>&1 &
