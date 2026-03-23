#!/bin/bash
set -euo pipefail

mkdir -p "$HOME/.local/state/carla-hub/logs"

if pgrep -f "qpwgraph" >/dev/null; then
    exit 0
fi

qpwgraph -m -a -x "$HOME/Desktop/firstTestAudioSettings.qpwgraph" \
  >"$HOME/.local/state/carla-hub/logs/qpwgraph.log" 2>&1 &
