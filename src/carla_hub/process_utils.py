from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple


def list_processes() -> List[Tuple[int, str]]:
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid=,args="],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return []

    result: List[Tuple[int, str]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        result.append((pid, parts[1]))
    return result


def find_carla_pids_for_project(project: Path, *, no_gui: bool | None) -> List[int]:
    project_str = str(project)
    pids: List[int] = []

    for pid, cmd in list_processes():
        if "carla" not in cmd:
            continue
        if "carla_hub" in cmd:
            continue
        if project_str not in cmd:
            continue

        has_no_gui = "--no-gui" in cmd

        if no_gui is True and has_no_gui:
            pids.append(pid)
        elif no_gui is False and not has_no_gui:
            pids.append(pid)
        elif no_gui is None:
            pids.append(pid)

    return pids


def kill_pids(pids: List[int], timeout: float = 3.0) -> None:
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass

    deadline = time.time() + timeout
    remaining = list(pids)

    while remaining and time.time() < deadline:
        new_remaining = []
        for pid in remaining:
            try:
                os.kill(pid, 0)
                new_remaining.append(pid)
            except ProcessLookupError:
                pass
            except PermissionError:
                new_remaining.append(pid)
        remaining = new_remaining
        if remaining:
            time.sleep(0.15)

    for pid in remaining:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def run_detached(
    cmd: List[str],
    *,
    env: Dict[str, str] | None = None,
    log_path: Path | None = None,
) -> subprocess.Popen:
    stdout_target = subprocess.DEVNULL
    stderr_target = subprocess.DEVNULL

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(log_path, "ab", buffering=0)
        stdout_target = handle
        stderr_target = subprocess.STDOUT

    return subprocess.Popen(
        cmd,
        env=env,
        stdout=stdout_target,
        stderr=stderr_target,
        start_new_session=True,
    )
