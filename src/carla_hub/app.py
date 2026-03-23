from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

from PyQt5.QtCore import QLockFile, QTimer, Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .config import AppConfig, ProjectConfig
from .process_utils import kill_pids, list_processes, run_detached


STYLE = """
QWidget {
    background: #12151b;
    color: #e7edf5;
    font-size: 13px;
}
#hubTitle {
    font-size: 20px;
    font-weight: 700;
}
QFrame#slotCard {
    background: #1b2230;
    border: 1px solid #2a3346;
    border-radius: 12px;
}
QLabel#title {
    font-size: 16px;
    font-weight: 700;
}
QLabel#path {
    color: #aeb8c8;
    font-size: 11px;
}
QLabel#statusOk {
    color: #9fe3a1;
    font-weight: 600;
}
QLabel#statusWarn {
    color: #ffd27a;
    font-weight: 600;
}
QLabel#error {
    color: #ff8f8f;
    min-height: 18px;
}
QPushButton {
    background: #263248;
    border: 1px solid #31405d;
    border-radius: 8px;
    padding: 6px 8px;
    min-height: 28px;
}
QPushButton:hover {
    background: #30415f;
}
QPushButton:pressed {
    background: #1d2940;
}
"""

CARD_COLUMNS = 3


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
class SlotRuntimeState:
    bg_pids: List[int]
    gui_pids: List[int]
    project_exists: bool


@dataclass
class RuntimeSnapshot:
    sinks: Set[str]
    slot_states: Dict[str, SlotRuntimeState]


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

    @property
    def project_label(self) -> str:
        return self.project.name

    def project_exists(self) -> bool:
        return self.project.is_file()

    def bg_pids(self) -> List[int]:
        return self._find_pids(no_gui=True)

    def gui_pids(self) -> List[int]:
        return self._find_pids(no_gui=False)

    def _find_pids(self, *, no_gui: bool | None) -> List[int]:
        project_str = str(self.project)
        result: List[int] = []
        for pid, cmd in list_processes():
            if "carla" not in cmd:
                continue
            if project_str not in cmd:
                continue
            if "carla_hub" in cmd:
                continue
            has_no_gui = "--no-gui" in cmd
            if no_gui is True and has_no_gui:
                result.append(pid)
            elif no_gui is False and not has_no_gui:
                result.append(pid)
            elif no_gui is None:
                result.append(pid)
        return result

    def start_bg(self) -> bool:
        if not self.project_exists():
            self.last_error = f"Missing project: {self.project}"
            return False

        if self.bg_pids() or self.gui_pids():
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


class SlotCard(QFrame):
    def __init__(self, slot: CarlaSlot):
        super().__init__()
        self.slot = slot
        self.setObjectName("slotCard")
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        title = QLabel(slot.name)
        title.setObjectName("title")
        outer.addWidget(title)

        self.project_label = QLabel(slot.project_label)
        self.project_label.setObjectName("path")
        self.project_label.setWordWrap(False)
        self.project_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(self.project_label)

        self.status = QLabel()
        self.status.setObjectName("statusOk")
        outer.addWidget(self.status)

        self.pid = QLabel()
        self.pid.setObjectName("path")
        self.pid.setWordWrap(True)
        outer.addWidget(self.pid)

        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setObjectName("error")
        outer.addWidget(self.error)

        btns = QHBoxLayout()
        btns.setSpacing(6)

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

    def on_open(self):
        ok = self.slot.open_gui()
        if not ok:
            QMessageBox.warning(self, self.slot.name, self.slot.last_error or "Cannot open GUI.")

    def on_bg(self):
        self.slot.stop_gui()
        ok = self.slot.start_bg()
        if not ok:
            QMessageBox.warning(self, self.slot.name, self.slot.last_error or "Cannot start background.")

    def on_restart(self):
        ok = self.slot.restart_bg()
        if not ok:
            QMessageBox.warning(self, self.slot.name, self.slot.last_error or "Cannot restart.")

    def on_stop(self):
        self.slot.stop_all()

    def refresh_from_state(self, state: SlotRuntimeState):
        if self.slot.reopen_bg_after_gui_close and not state.gui_pids:
            self.slot.reopen_bg_after_gui_close = False
            if not state.bg_pids and state.project_exists:
                self.slot.start_bg()

        if not state.project_exists:
            status_text = "State: Project missing"
            self.status.setObjectName("statusWarn")
        elif state.gui_pids:
            status_text = "State: GUI open"
            self.status.setObjectName("statusWarn")
        elif state.bg_pids:
            status_text = "State: Background"
            self.status.setObjectName("statusOk")
        else:
            status_text = "State: Stopped"
            self.status.setObjectName("statusWarn")

        self.style().unpolish(self.status)
        self.style().polish(self.status)
        self.status.setText(status_text)

        parts = []
        if state.bg_pids:
            parts.append("BG " + ",".join(map(str, state.bg_pids)))
        if state.gui_pids:
            parts.append("GUI " + ",".join(map(str, state.gui_pids)))
        self.pid.setText("PID: " + (" | ".join(parts) if parts else "—"))

        self.error.setText(self.slot.last_error)

        exists = state.project_exists
        running = bool(state.bg_pids or state.gui_pids)

        self.btn_open.setEnabled(exists)
        self.btn_bg.setEnabled(exists)
        self.btn_restart.setEnabled(exists)
        self.btn_stop.setEnabled(running)


class CarlaHubWindow(QWidget):
    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self.setWindowTitle("Carla Hub V2")
        self.resize(1180, 760)

        self.slots = [CarlaSlot(cfg, p) for p in cfg.projects]
        self.cards: List[SlotCard] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("Carla Hub V2")
        title.setObjectName("hubTitle")
        root.addWidget(title)

        info = QLabel(
            "Open = open real Carla GUI for one project. "
            "BG = ensure background engine. Restart = restart one channel. Stop = stop one channel."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        self.sink_status = QLabel()
        self.sink_status.setObjectName("path")
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

        self.area = QScrollArea()
        self.area.setWidgetResizable(True)

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)

        for idx, slot in enumerate(self.slots):
            card = SlotCard(slot)
            self.cards.append(card)
            row, col = divmod(idx, CARD_COLUMNS)
            self.grid.addWidget(card, row, col)

        for col in range(CARD_COLUMNS):
            self.grid.setColumnStretch(col, 1)

        self.area.setWidget(self.container)
        root.addWidget(self.area)

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

    def build_snapshot(self) -> RuntimeSnapshot:
        processes = list_processes()
        sink_names = set(list_sinks())

        slot_states: Dict[str, SlotRuntimeState] = {}
        for slot in self.slots:
            project_str = str(slot.project)
            bg_pids: List[int] = []
            gui_pids: List[int] = []

            for pid, cmd in processes:
                if "carla" not in cmd:
                    continue
                if project_str not in cmd:
                    continue
                if "carla_hub" in cmd:
                    continue

                if "--no-gui" in cmd:
                    bg_pids.append(pid)
                else:
                    gui_pids.append(pid)

            slot_states[slot.name] = SlotRuntimeState(
                bg_pids=bg_pids,
                gui_pids=gui_pids,
                project_exists=slot.project.is_file(),
            )

        return RuntimeSnapshot(sinks=sink_names, slot_states=slot_states)

    def refresh_sink_status(self, sinks: Set[str]):
        missing = [name for name in self.cfg.sink_names if name not in sinks]
        if missing:
            self.sink_status.setText("Audio buses: missing -> " + ", ".join(missing))
        else:
            self.sink_status.setText("Audio buses: OK")

    def tick(self):
        snapshot = self.build_snapshot()
        self.refresh_sink_status(snapshot.sinks)

        for card in self.cards:
            state = snapshot.slot_states[card.slot.name]
            card.refresh_from_state(state)

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
