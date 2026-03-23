#!/usr/bin/env python3
import os
import signal
import subprocess
import sys
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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# --- Configuration -----------------------------------------------------------
PROJECT_DIR = Path.home() / ".config" / "carla" / "projects"
PIPEWIRE_LATENCY = "256/48000"
POLL_MS = 1000

PROJECTS = [
    ("ALL", "ALL.carxp"),
    ("GAME", "GAME.carxp"),
    ("CHAT", "CHAT.carxp"),
    ("MEDIA", "MEDIA.carxp"),
    ("MORE", "MORE.carxp"),
    ("MICRO", "MICRO.carxp"),
    ("RETOUR-MIC", "RETOUR-MIC.carxp"),
]

START_ALL_SCRIPT = "/home/kooy/bin/start_carla_bg.sh"
QPWGRAPH_CMD = ["qpwgraph"]
EASYEFFECTS_CMD = ["easyeffects"]
# -----------------------------------------------------------------------------


def base_env() -> Dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PIPEWIRE_LATENCY", PIPEWIRE_LATENCY)
    return env


def list_processes() -> List[tuple[int, str]]:
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid=,args="],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return []

    result: List[tuple[int, str]] = []
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
        if project_str not in cmd:
            continue
        if "carla" not in cmd:
            continue
        if "carla_hub.py" in cmd:
            continue

        has_no_gui = "--no-gui" in cmd

        if no_gui is True and has_no_gui:
            pids.append(pid)
        elif no_gui is False and not has_no_gui:
            pids.append(pid)
        elif no_gui is None:
            pids.append(pid)

    return pids


def kill_pids(pids: List[int]):
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except PermissionError:
            continue

    # petite attente
    import time
    deadline = time.time() + 3.0
    remaining = pids[:]
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
        except ProcessLookupError:
            continue
        except PermissionError:
            continue


@dataclass
class CarlaSlot:
    name: str
    project: Path
    last_error: str = ""
    reopen_bg_after_gui_close: bool = False

    def project_exists(self) -> bool:
        return self.project.is_file()

    def bg_pids(self) -> List[int]:
        return find_carla_pids_for_project(self.project, no_gui=True)

    def gui_pids(self) -> List[int]:
        return find_carla_pids_for_project(self.project, no_gui=False)

    def is_bg_running(self) -> bool:
        return len(self.bg_pids()) > 0

    def is_gui_running(self) -> bool:
        return len(self.gui_pids()) > 0

    def state_text(self) -> str:
        if not self.project_exists():
            return "Projet introuvable"
        if self.is_gui_running():
            return "GUI ouverte"
        if self.is_bg_running():
            return "Arrière-plan"
        return "Arrêté"

    def start_bg(self) -> bool:
        if not self.project_exists():
            self.last_error = f"Projet manquant: {self.project}"
            return False
        if self.is_bg_running() or self.is_gui_running():
            self.last_error = ""
            return True

        safe_name = self.name.lower().replace(" ", "_").replace("-", "_")
        log_path = Path(f"/tmp/carla_{safe_name}.log")

        try:
            with open(log_path, "ab", buffering=0) as f:
                subprocess.Popen(
                    ["pw-jack", "carla", "--no-gui", str(self.project)],
                    env=base_env(),
                    stdout=f,
                    stderr=subprocess.STDOUT,
                )
            self.last_error = ""
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def open_gui(self) -> bool:
        if not self.project_exists():
            self.last_error = f"Projet manquant: {self.project}"
            return False

        if self.is_gui_running():
            self.last_error = "La GUI est déjà ouverte pour ce canal."
            return True

        self.stop_bg()

        try:
            subprocess.Popen(
                ["pw-jack", "carla", str(self.project)],
                env=base_env(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.reopen_bg_after_gui_close = True
            self.last_error = ""
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def stop_bg(self):
        pids = self.bg_pids()
        if pids:
            kill_pids(pids)

    def stop_gui(self):
        pids = self.gui_pids()
        if pids:
            kill_pids(pids)
        self.reopen_bg_after_gui_close = False

    def stop_all(self):
        self.reopen_bg_after_gui_close = False
        self.stop_gui()
        self.stop_bg()

    def restart_bg(self) -> bool:
        self.stop_all()
        return self.start_bg()

    def maintain(self):
        if self.reopen_bg_after_gui_close and not self.is_gui_running():
            self.reopen_bg_after_gui_close = False
            if not self.is_bg_running() and self.project_exists():
                self.start_bg()


class SlotCard(QFrame):
    def __init__(self, slot: CarlaSlot, parent=None):
        super().__init__(parent)
        self.slot = slot

        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("slotCard")
        self.setMinimumWidth(280)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        self.title = QLabel(slot.name)
        self.title.setObjectName("title")
        outer.addWidget(self.title)

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
        self.btn_open = QPushButton("Ouvrir")
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
            QMessageBox.warning(
                self,
                self.slot.name,
                self.slot.last_error or "Impossible d'ouvrir la GUI."
            )

    def on_bg(self):
        self.slot.stop_gui()
        ok = self.slot.start_bg()
        self.refresh()
        if not ok:
            QMessageBox.warning(
                self,
                self.slot.name,
                self.slot.last_error or "Impossible de lancer en arrière-plan."
            )

    def on_restart(self):
        ok = self.slot.restart_bg()
        self.refresh()
        if not ok:
            QMessageBox.warning(
                self,
                self.slot.name,
                self.slot.last_error or "Impossible de relancer."
            )

    def on_stop(self):
        self.slot.stop_all()
        self.refresh()

    def refresh(self):
        self.slot.maintain()

        self.status.setText(f"État : {self.slot.state_text()}")

        bg = self.slot.bg_pids()
        gui = self.slot.gui_pids()

        pid_parts = []
        if bg:
            pid_parts.append("BG " + ",".join(map(str, bg)))
        if gui:
            pid_parts.append("GUI " + ",".join(map(str, gui)))

        self.pid.setText("PID : " + (" | ".join(pid_parts) if pid_parts else "—"))
        self.error.setText(self.slot.last_error)

        exists = self.slot.project_exists()
        self.btn_open.setEnabled(exists)
        self.btn_bg.setEnabled(exists)
        self.btn_restart.setEnabled(exists)
        self.btn_stop.setEnabled(self.slot.is_bg_running() or self.slot.is_gui_running())


class CarlaHub(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Carla Hub")
        self.resize(1080, 720)

        self.slots = [
            CarlaSlot(name=name, project=PROJECT_DIR / filename)
            for name, filename in PROJECTS
        ]
        self.cards = []

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Carla Hub — édition ponctuelle, moteurs en arrière-plan")
        title.setObjectName("hubTitle")
        root.addWidget(title)

        info = QLabel(
            "Ouvrir = coupe l'instance background du canal et ouvre Carla en vraie fenêtre.\n"
            "Quand tu fermes cette fenêtre, le hub relance automatiquement la version arrière-plan du même projet.\n"
            "BG = assure l'instance en arrière-plan. Restart = relance ce canal. Stop = coupe ce canal.\n"
            "Démarrer tout en arrière-plan utilise le script global start_carla_bg.sh."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        top_btns = QHBoxLayout()
        self.btn_start_all = QPushButton("Démarrer tout en arrière-plan")
        self.btn_stop_all = QPushButton("Tout arrêter")
        self.btn_qpwgraph = QPushButton("Ouvrir qpwgraph")
        self.btn_easyeffects = QPushButton("Ouvrir EasyEffects")

        top_btns.addWidget(self.btn_start_all)
        top_btns.addWidget(self.btn_stop_all)
        top_btns.addWidget(self.btn_qpwgraph)
        top_btns.addWidget(self.btn_easyeffects)
        root.addLayout(top_btns)

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

        self.btn_start_all.clicked.connect(self.start_all_from_script)
        self.btn_stop_all.clicked.connect(self.stop_all)
        self.btn_qpwgraph.clicked.connect(self.open_qpwgraph)
        self.btn_easyeffects.clicked.connect(self.open_easyeffects)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(POLL_MS)

    def tick(self):
        for card in self.cards:
            card.refresh()

    def start_all_from_script(self):
        try:
            subprocess.Popen([START_ALL_SCRIPT])
        except Exception:
            QMessageBox.warning(
                self,
                "Carla Hub",
                f"Impossible de lancer {START_ALL_SCRIPT}"
            )

    def stop_all(self):
        for slot in self.slots:
            slot.stop_all()
        self.tick()

    def open_qpwgraph(self):
        subprocess.Popen(QPWGRAPH_CMD)

    def open_easyeffects(self):
        subprocess.Popen(EASYEFFECTS_CMD)

    def closeEvent(self, event):
        event.accept()


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


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)

    lock_path = str(Path.home() / ".cache" / "carla_hub.lock")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lock = QLockFile(lock_path)
    if not lock.tryLock(100):
        sys.exit(0)

    win = CarlaHub()
    win._lock = lock
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
