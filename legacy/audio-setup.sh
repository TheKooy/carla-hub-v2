#!/bin/bash

create_sink () {
    if ! pactl list short sinks | grep -q "$1"; then
        pactl load-module module-null-sink sink_name=$1 sink_properties=device.description="$2"
    fi
}

create_sink all "🌍ALL"
create_sink game "🎮GAME"
create_sink media "🎵MEDIA"
create_sink chat "💬CHAT"
create_sink more "🔊MORE"
create_sink retour "🎤RETOUR-MICRO"
create_sink micro "🎤MICRO"


echo "Audio buses ready"
