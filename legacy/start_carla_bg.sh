#!/bin/bash

launch_if_missing() {
  local project="$1"
  local log="$2"

  if pgrep -af "carla.*${project}" >/dev/null; then
    return 0
  fi

  pw-jack carla --no-gui "$project" >"$log" 2>&1 &
  sleep 0.8
}

launch_if_missing /home/kooy/.config/carla/projects/ALL.carxp /tmp/carla-all.log
launch_if_missing /home/kooy/.config/carla/projects/GAME.carxp /tmp/carla-game.log
launch_if_missing /home/kooy/.config/carla/projects/CHAT.carxp /tmp/carla-chat.log
launch_if_missing /home/kooy/.config/carla/projects/MEDIA.carxp /tmp/carla-media.log
launch_if_missing /home/kooy/.config/carla/projects/MORE.carxp /tmp/carla-more.log
launch_if_missing /home/kooy/.config/carla/projects/RETOUR-MIC.carxp /tmp/carla-retour-mic.log
launch_if_missing /home/kooy/.config/carla/projects/MICRO.carxp /tmp/carla-micro.log
