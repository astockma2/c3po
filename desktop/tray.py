"""System-Tray-Icon (PyQt6).

Port aus C3PO-legacy/ui/tray.py - Lock/Reset-Session entfernt (war an
das alte Permission-Caching gekoppelt, das es in OpenJarvis nicht gibt).
Voice an/aus, Cockpit + Audit-Log oeffnen, Beenden.
"""
from __future__ import annotations

import os
import sys
import threading
import webbrowser
from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMenu, QSystemTrayIcon

from desktop.keyring_helper import set_admin_pin


def _server_port() -> int:
    return int(os.environ.get("C3PO_SERVER_PORT", "8000"))


def _build_icon(active: bool = True) -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor("#00e5ff") if active else QColor("#666666")
    painter.setBrush(QBrush(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(8, 8, 48, 48)
    painter.setBrush(QBrush(QColor("#0a1929")))
    painter.drawEllipse(20, 20, 24, 24)
    painter.end()
    return QIcon(pixmap)


class C3POTray:
    """Tray-Icon mit Status + Menue.

    Parameters
    ----------
    on_quit:
        Callback beim "Beenden"-Klick. Hier sollte der Server-Prozess
        sauber heruntergefahren werden, falls vom Tray gestartet.
    on_toggle_voice:
        Callback beim "Voice deaktivieren/aktivieren"-Klick.
    """

    def __init__(
        self,
        on_quit: Optional[Callable[[], None]] = None,
        on_toggle_voice: Optional[Callable[[], None]] = None,
    ) -> None:
        self._app: Optional[QApplication] = None
        self._tray: Optional[QSystemTrayIcon] = None
        self._on_quit = on_quit
        self._on_toggle_voice = on_toggle_voice
        self._voice_active = True

    def _run(self) -> None:
        port = _server_port()

        self._app = QApplication(sys.argv if hasattr(sys, "argv") else [])
        self._app.setQuitOnLastWindowClosed(False)

        self._tray = QSystemTrayIcon(_build_icon(True))
        self._tray.setToolTip("C3PO Voice-Agent - bereit")

        menu = QMenu()

        status = QAction("C3PO bereit", menu)
        status.setEnabled(False)
        menu.addAction(status)
        menu.addSeparator()

        voice = QAction("Voice deaktivieren", menu)

        def toggle_voice() -> None:
            self._voice_active = not self._voice_active
            voice.setText(
                "Voice aktivieren" if not self._voice_active else "Voice deaktivieren"
            )
            self._tray.setIcon(_build_icon(self._voice_active))
            self._tray.setToolTip(
                "C3PO Voice-Agent - bereit" if self._voice_active else "C3PO - Voice aus"
            )
            if self._on_toggle_voice:
                self._on_toggle_voice()

        voice.triggered.connect(toggle_voice)
        menu.addAction(voice)

        reset_pin = QAction("Admin-PIN zuruecksetzen ...", menu)

        def trigger_pin_reset() -> None:
            pin, ok = QInputDialog.getText(
                None, "Neuen Admin-PIN festlegen",
                "Neuer 4-stelliger PIN:",
                QLineEdit.EchoMode.Password,
            )
            if ok and pin and pin.isdigit() and len(pin) == 4:
                set_admin_pin(pin)
                self._tray.showMessage(
                    "PIN gesetzt", "Neuer Admin-PIN gespeichert.",
                    QSystemTrayIcon.MessageIcon.Information, 3000,
                )
            elif ok:
                self._tray.showMessage(
                    "Ungueltig", "PIN muss 4 Ziffern sein.",
                    QSystemTrayIcon.MessageIcon.Warning, 3000,
                )

        reset_pin.triggered.connect(trigger_pin_reset)
        menu.addAction(reset_pin)

        cockpit = QAction("Cockpit oeffnen ...", menu)
        cockpit.triggered.connect(lambda: webbrowser.open(f"http://127.0.0.1:{port}/"))
        menu.addAction(cockpit)

        logs = QAction("Audit-Log oeffnen ...", menu)
        logs.triggered.connect(lambda: webbrowser.open(f"http://127.0.0.1:{port}/audit/log"))
        menu.addAction(logs)

        menu.addSeparator()

        quit_action = QAction("C3PO beenden", menu)

        def quit_app() -> None:
            if self._on_quit:
                self._on_quit()
            self._app.quit()

        quit_action.triggered.connect(quit_app)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.show()
        self._tray.showMessage(
            "C3PO startet", "Sag 'Hey Jarvis' zum Aktivieren.",
            QSystemTrayIcon.MessageIcon.Information, 3000,
        )
        self._app.exec()

    def start(self) -> threading.Thread:
        """Startet Tray in eigenem Thread."""
        thread = threading.Thread(target=self._run, daemon=True, name="C3PO-Tray")
        thread.start()
        return thread

    def run_blocking(self) -> None:
        """Startet den Tray im aktuellen Thread (Qt-Konformitaet)."""
        self._run()

    def notify(self, title: str, msg: str, level: str = "info") -> None:
        if self._tray is None:
            return
        icon = {
            "info": QSystemTrayIcon.MessageIcon.Information,
            "warning": QSystemTrayIcon.MessageIcon.Warning,
            "critical": QSystemTrayIcon.MessageIcon.Critical,
        }.get(level, QSystemTrayIcon.MessageIcon.Information)
        self._tray.showMessage(title, msg, icon, 4000)

    @property
    def voice_active(self) -> bool:
        return self._voice_active


__all__ = ["C3POTray"]
