from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from PyQt5.QtCore import QLockFile, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .config import AppConfig, ProjectConfig
from .process_utils import find_carla_pids_for_project, kill_pids, run_detached


STYLE = """
QWidget {
    background: #12151b;
    color: #e7edf5;
    font-size: 14px;
}
#hubTitle {
    font-size: 22px;
    font-weight: 700;
}
QFrame#slotCard {
    background: #1b2230;
    border: 1px solid #2a3346;
    border-radius: 14px;
}
QLabel#title {
    font-size: 18px;
    font-weight: 700;
}
QLabel#path {
    color: #aeb8c8;
    font-size: 12px;
}
QLabel#error {
    color: #ff8f8f;
    min-height: 36px;
}
QPushButton {
    background: #263248;
    border: 1px solid #31405d;
    border-radius: 10px;
    padding: 8px 10px;
}
QPushButton:hover {
    background: #30415f;
}
QPushButton:pressed {
    background: #1d2940;
}
"""


def base_env(pipewire_latency: str) -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PIPEWIRE_LATENCY", pipewire_latency)
    return env


def repo_dir() -> Path:
    value = os.environ.get("CARLA_HUB_REPO_DIR")
    if value:
        return Path(value).resolve()
    return Path.cwd()


def list_sinks() -> List[str]:
    try:
        out = subprocess.run(
            ["pactl", "list", "short", "sinks"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except Exception:
        return []

    names: List[str] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            names.append(parts[1])
    return names


@dataclass
class CarlaSlot:
    cfg: AppConfig
    project_cfg: ProjectConfig
    last_error: str = ""
    reopen_bg_after_gui_close: bool = False

    @property
    def name(self) -> str:
        return self.project_cfg.name

    @property
    def project(self) -> Path:
        return self.cfg.project_path(self.project_cfg)

    @property
    def log_path(self) -> Path:
        safe_name = self.name.lower().replace(" ", "_").replace("-", "_")
        return self.cfg.log_dir / f"carla_{safe_name}.log"

    def project_exists(self) -> bool:
        return self.project.is_file()

    def bg_pids(self) -> List[int]:
        return find_carla_pids_for_project(self.project, no_gui=True)

    def gui_pids(self) -> List[int]:
        return find_carla_pids_for_project(self.project, no_gui=False)

    def is_bg_running(self) -> bool:
        return bool(self.bg_pids())

    def is_gui_running(self) -> bool:
        return bool(self.gui_pids())

    def state_text(self) -> str:
        if not self.project_exists():
            return "Project missing"
        if self.is_gui_running():
            return "GUI open"
        if self.is_bg_running():
            return "Background"
        return "Stopped"

    def start_bg(self) -> bool:
        if not self.project_exists():
            self.last_error = f"Missing project: {self.project}"
            return False

        if self.is_bg_running() or self.is_gui_running():
            self.last_error = ""
            return True

        try:
            run_detached(
                ["pw-jack", "carla", "--no-gui", str(self.project)],
                env=base_env(self.cfg.pipewire_latency),
                log_path=self.log_path,
            )
            self.last_error = ""
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def open_gui(self) -> bool:
        if not self.project_exists():
            self.last_error = f"Missing project: {self.project}"
            return False

        try:
            self.stop_bg()
            run_detached(
                ["pw-jack", "carla", str(self.project)],
                env=base_env(self.cfg.pipewire_latency),
                log_path=self.log_path,
            )
            self.reopen_bg_after_gui_close = True
            self.last_error = ""
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def stop_bg(self) -> None:
        kill_pids(self.bg_pids())

    def stop_gui(self) -> None:
        kill_pids(self.gui_pids())

    def stop_all(self) -> None:
        kill_pids(self.bg_pids() + self.gui_pids())
        self.reopen_bg_after_gui_close = False

    def restart_bg(self) -> bool:
        self.stop_all()
        return self.start_bg()

    def maintain(self) -> None:
        if self.reopen_bg_after_gui_close and not self.is_gui_running():
            self.reopen_bg_after_gui_close = False
            if not self.is_bg_running():
                self.start_bg()


class SlotCard(QFrame):
    def __init__(self, slot: CarlaSlot):
        super().__init__()
        self.slot = slot
        self.setObjectName("slotCard")

        outer = QVBoxLayout(self)

        title = QLabel(slot.name)
        title.setObjectName("title")
        outer.addWidget(title)

        self.project_label = QLabel(str(slot.project))
        self.project_label.setWordWrap(True)
        self.project_label.setObjectName("path")
        outer.addWidget(self.project_label)

        self.status = QLabel()
        outer.addWidget(self.status)

        self.pid = QLabel()
        outer.addWidget(self.pid)

        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setObjectName("error")
        outer.addWidget(self.error)

        btns = QHBoxLayout()
        self.btn_open = QPushButton("Open")
        self.btn_bg = QPushButton("BG")
        self.btn_restart = QPushButton("Restart")
        self.btn_stop = QPushButton("Stop")

        btns.addWidget(self.btn_open)
        btns.addWidget(self.btn_bg)
        btns.addWidget(self.btn_restart)
        btns.addWidget(self.btn_stop)
        outer.addLayout(btns)

        self.btn_open.clicked.connect(self.on_open)
        self.btn_bg.clicked.connect(self.on_bg)
        self.btn_restart.clicked.connect(self.on_restart)
        self.btn_stop.clicked.connect(self.on_stop)

        self.refresh()

    def on_open(self):
        ok = self.slot.open_gui()
        self.refresh()
        if not ok:
            QMessageBox.warning(self, self.slot.name, self.slot.last_error or "Cannot open GUI.")

    def on_bg(self):
        self.slot.stop_gui()
        ok = self.slot.start_bg()
        self.refresh()
        if not ok:
            QMessageBox.warning(self, self.slot.name, self.slot.last_error or "Cannot start background.")

    def on_restart(self):
        ok = self.slot.restart_bg()
        self.refresh()
        if not ok:
            QMessageBox.warning(self, self.slot.name, self.slot.last_error or "Cannot restart.")

    def on_stop(self):
        self.slot.stop_all()
        self.refresh()

    def refresh(self):
        self.slot.maintain()

        self.status.setText(f"State: {self.slot.state_text()}")

        bg = self.slot.bg_pids()
        gui = self.slot.gui_pids()

        parts = []
        if bg:
            parts.append("BG " + ",".join(map(str, bg)))
        if gui:
            parts.append("GUI " + ",".join(map(str, gui)))

        self.pid.setText("PID: " + (" | ".join(parts) if parts else "—"))
        self.error.setText(self.slot.last_error)

        exists = self.slot.project_exists()
        self.btn_open.setEnabled(exists)
        self.btn_bg.setEnabled(exists)
        self.btn_restart.setEnabled(exists)
        self.btn_stop.setEnabled(self.slot.is_bg_running() or self.slot.is_gui_running())


class CarlaHubWindow(QWidget):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("Carla Hub V2")
        self.resize(1100, 760)

        self.slots = [CarlaSlot(cfg, p) for p in cfg.projects]
        self.cards: List[SlotCard] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Carla Hub V2 — background engines + safe GUI editing")
        title.setObjectName("hubTitle")
        root.addWidget(title)

        info = QLabel(
            "Open = stop the background instance for one channel and open the real Carla GUI.\n"
            "When the GUI closes, the background instance is restarted automatically.\n"
            "BG = ensure background. Restart = restart one channel. Stop = stop one channel."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self.sink_status = QLabel()
        root.addWidget(self.sink_status)

        top = QHBoxLayout()
        self.btn_start_all = QPushButton("Start all BG")
        self.btn_stop_all = QPushButton("Stop all")
        self.btn_repair_sinks = QPushButton("Repair sinks")
        self.btn_restart_stack = QPushButton("Restart stack")
        self.btn_qpwgraph = QPushButton("Open qpwgraph")
        self.btn_easyeffects = QPushButton("Open EasyEffects")

        top.addWidget(self.btn_start_all)
        top.addWidget(self.btn_stop_all)
        top.addWidget(self.btn_repair_sinks)
        top.addWidget(self.btn_restart_stack)
        top.addWidget(self.btn_qpwgraph)
        top.addWidget(self.btn_easyeffects)
        root.addLayout(top)

        area = QScrollArea()
        area.setWidgetResizable(True)
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(12)

        for idx, slot in enumerate(self.slots):
            card = SlotCard(slot)
            self.cards.append(card)
            row, col = divmod(idx, 2)
            grid.addWidget(card, row, col)

        area.setWidget(container)
        root.addWidget(area)

        self.btn_start_all.clicked.connect(self.start_all)
        self.btn_stop_all.clicked.connect(self.stop_all)
        self.btn_repair_sinks.clicked.connect(self.repair_sinks)
        self.btn_restart_stack.clicked.connect(self.restart_stack)
        self.btn_qpwgraph.clicked.connect(self.open_qpwgraph)
        self.btn_easyeffects.clicked.connect(self.open_easyeffects)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(self.cfg.poll_ms)

        self.tick()

    def refresh_sink_status(self):
        actual = set(list_sinks())
        missing = [name for name in self.cfg.sink_names if name not in actual]
        if missing:
            self.sink_status.setText("Audio buses: missing -> " + ", ".join(missing))
        else:
            self.sink_status.setText("Audio buses: OK")

    def tick(self):
        self.refresh_sink_status()
        for card in self.cards:
            card.refresh()

    def start_all(self):
        for slot in self.slots:
            slot.start_bg()
        self.tick()

    def stop_all(self):
        for slot in self.slots:
            slot.stop_all()
        self.tick()

    def repair_sinks(self):
        script = repo_dir() / "scripts" / "audio-setup.sh"
        try:
            subprocess.Popen([str(script)])
        except Exception as exc:
            QMessageBox.warning(self, "Carla Hub V2", f"Cannot run {script}\n\n{exc}")

    def restart_stack(self):
        script = repo_dir() / "scripts" / "restart_carla_stack.sh"
        try:
            subprocess.Popen([str(script)])
        except Exception as exc:
            QMessageBox.warning(self, "Carla Hub V2", f"Cannot run {script}\n\n{exc}")

    def open_qpwgraph(self):
        try:
            subprocess.Popen(
                ["qpwgraph", "-m", "-a", "-x", str(self.cfg.qpwgraph_patchbay)]
            )
        except Exception as exc:
            QMessageBox.warning(self, "Carla Hub V2", str(exc))

    def open_easyeffects(self):
        try:
            subprocess.Popen(["easyeffects"])
        except Exception as exc:
            QMessageBox.warning(self, "Carla Hub V2", str(exc))


def run_hub(cfg: AppConfig) -> int:
    app = QApplication([])
    app.setStyleSheet(STYLE)

    lock_path = Path.home() / ".cache" / "carla_hub_v2.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(lock_path))
    if not lock.tryLock(100):
        return 0

    win = CarlaHubWindow(cfg)
    win._lock = lock
    win.show()
    return app.exec_()
