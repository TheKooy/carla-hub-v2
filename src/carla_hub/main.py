from __future__ import annotations

import argparse
import time

from .app import CarlaSlot, run_hub
from .config import load_config


def build_slots(cfg):
    return [CarlaSlot(cfg, project_cfg) for project_cfg in cfg.projects]


def cmd_hub(args) -> int:
    cfg = load_config(args.config)
    return run_hub(cfg)


def cmd_start_bg_all(args) -> int:
    cfg = load_config(args.config)
    for slot in build_slots(cfg):
        slot.start_bg()
        time.sleep(0.8)
    return 0


def cmd_stop_all(args) -> int:
    cfg = load_config(args.config)
    for slot in build_slots(cfg):
        slot.stop_all()
    return 0


def cmd_restart_stack(args) -> int:
    cfg = load_config(args.config)
    for slot in build_slots(cfg):
        slot.stop_all()
    time.sleep(2.0)
    for slot in build_slots(cfg):
        slot.start_bg()
        time.sleep(0.8)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="carla-hub")
    parser.add_argument(
        "--config",
        default="config/projects.json",
        help="Path to projects.json",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_hub = sub.add_parser("hub")
    p_hub.set_defaults(func=cmd_hub)

    p_start = sub.add_parser("start-bg-all")
    p_start.set_defaults(func=cmd_start_bg_all)

    p_stop = sub.add_parser("stop-all")
    p_stop.set_defaults(func=cmd_stop_all)

    p_restart = sub.add_parser("restart-stack")
    p_restart.set_defaults(func=cmd_restart_stack)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
