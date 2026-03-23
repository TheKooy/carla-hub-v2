#!/bin/bash

/home/kooy/.config/audio-setup.sh

for i in {1..20}; do
  pactl info >/dev/null 2>&1 && break
  sleep 0.3
done

pgrep -f "easyeffects --gapplication-service" >/dev/null || \
  easyeffects --gapplication-service >/tmp/easyeffects-bg.log 2>&1 &

for i in {1..20}; do
  wpctl status 2>/dev/null | grep -q "easyeffects_source" && break
  sleep 0.3
done

/home/kooy/bin/start_carla_bg.sh

sleep 2

/home/kooy/bin/start_carla_hub.sh

sleep 2

/home/kooy/bin/start_qpwgraph_bg.sh
