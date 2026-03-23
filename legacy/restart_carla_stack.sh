#!/bin/bash

pkill -f "carla --no-gui" 2>/dev/null
pkill -x carla 2>/dev/null

sleep 2

/home/kooy/bin/start_carla_bg.sh

sleep 3

pkill -f qpwgraph 2>/dev/null
sleep 1

/home/kooy/bin/start_qpwgraph_bg.sh

