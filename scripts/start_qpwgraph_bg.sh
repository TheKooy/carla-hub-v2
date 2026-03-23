#!/bin/bash
set -euo pipefail

LOG_DIR="$HOME/.local/state/carla-hub/logs"
LOG_FILE="$LOG_DIR/qpwgraph.log"
PATCHBAY_FILE="$HOME/Desktop/firstTestAudioSettings.qpwgraph"

mkdir -p "$LOG_DIR"

if pgrep -x qpwgraph >/dev/null; then
    exit 0
fi

nohup qpwgraph -m -a -x "$PATCHBAY_FILE" \
  >>"$LOG_FILE" 2>&1 < /dev/null &

for i in {1..25}; do
    if pgrep -x qpwgraph >/dev/null; then
        exit 0
    fi
    sleep 0.2
done

exit 1
