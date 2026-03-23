# Carla Hub V2

Personal audio control hub for Linux / Kubuntu with:

- multiple Carla background instances
- EasyEffects service startup
- qpwgraph patchbay loading
- virtual PipeWire sinks
- PyQt5 control UI

## Current status

This branch is a validated working V2 baseline tested on a live Kubuntu session.

## Main components

- `config/projects.json`: shared project configuration
- `scripts/`: startup / restart scripts
- `src/carla_hub/`: Python application
- `legacy/`: snapshot of the original working setup

## Patchbay file

The qpwgraph patchbay file is stored at:

`$HOME/.config/carla-hub/patchbays/main-audio-routing.qpwgraph`

## Notes

This project is currently tailored to a personal audio workflow and local file paths.
