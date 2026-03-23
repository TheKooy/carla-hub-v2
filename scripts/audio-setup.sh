#!/bin/bash
set -euo pipefail

create_sink() {
    local name="$1"
    local description="$2"

    if ! pactl list short sinks | awk '{print $2}' | grep -Fxq "$name"; then
        pactl load-module module-null-sink \
            sink_name="$name" \
            sink_properties=device.description="$description" >/dev/null
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
