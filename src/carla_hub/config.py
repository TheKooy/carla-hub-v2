from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    filename: str


@dataclass(frozen=True)
class AppConfig:
    project_dir: Path
    qpwgraph_patchbay: Path
    log_dir: Path
    pipewire_latency: str
    poll_ms: int
    easyeffects_wait_name: str
    sink_names: List[str]
    projects: List[ProjectConfig]

    def project_path(self, project: ProjectConfig) -> Path:
        return self.project_dir / project.filename


def load_config(path: str | Path) -> AppConfig:
    config_path = expand_path(str(path))
    data = json.loads(config_path.read_text(encoding="utf-8"))

    projects = [ProjectConfig(**item) for item in data["projects"]]

    cfg = AppConfig(
        project_dir=expand_path(data["project_dir"]),
        qpwgraph_patchbay=expand_path(data["qpwgraph_patchbay"]),
        log_dir=expand_path(data["log_dir"]),
        pipewire_latency=data.get("pipewire_latency", "256/48000"),
        poll_ms=int(data.get("poll_ms", 1000)),
        easyeffects_wait_name=data.get("easyeffects_wait_name", "easyeffects_source"),
        sink_names=list(data.get("sink_names", [])),
        projects=projects,
    )
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    return cfg
