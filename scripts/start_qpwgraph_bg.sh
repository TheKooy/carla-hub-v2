#!/bin/bash
set -euo pipefail

mkdir -p "$HOME/.local/state/carla-hub/logs"

if pgrep -x qpwgraph >/dev/null; then
    exit 0
fi

nohup qpwgraph -m -a -x "$HOME/Desktop/firstTestAudioSettings.qpwgraph" \
  >"$HOME/.local/state/carla-hub/logs/qpwgraph.log" 2>&1 < /dev/null &

sleep 1

pgrep -x qpwgraph >/dev/null
