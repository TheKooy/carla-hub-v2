#!/bin/bash

if pgrep -f "python3 /home/kooy/bin/carla_hub.py" >/dev/null; then
  exit 0
fi

python3 /home/kooy/bin/carla_hub.py >/tmp/carla-hub.log 2>&1 &
