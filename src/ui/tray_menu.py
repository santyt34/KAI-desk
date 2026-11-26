"""
ui/tray_menu.py
===============
System-tray icon for KAI-Desk.
Provides quick access to: show/hide island, mute TTS, open text input,
toggle sleep mode and exit.
"""

from __future__ import annotations

import logging

from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.event_bus import bus
from core.state_machine import KAIState, state_machine

logger = logging.getLogger(__name__)


class TrayMenu(QSystemTrayIcon):
    """
    Minimal system-tray icon with contextual menu.
    Requires a valid QApplication instance.
    """

    def __init__(self, island_window, text_input_fn=None) -> None:
        """
        Parameters
        ----------
        island_window : IslandWindow
            Reference to the main island widget.
        text_input_fn : callable | None
            Function to call to open the text-input dialogue.
        """
        # Use a built-in Qt icon as fallback if no custom icon exists
        icon = QIcon.fromTheme("assistant", QApplication.style().standardIcon(
            QApplication.style().StandardPixmap.SP_ComputerIcon  # type: ignore[attr-defined]
        ))
        super().__init__(icon)

        self._island = island_window
        self._text_input_fn = text_input_fn
        self._tts_muted = False

        self.setToolTip("KAI – Virtual Assistant")
        self._build_menu()
        self.activated.connect(self._on_tray_activated)
        logger.info("TrayMenu initialised")

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menu = QMenu()

        # Show / Hide
        self._act_show = QAction("Hide island", menu)
        self._act_show.triggered.connect(self._toggle_visibility)
        menu.addAction(self._act_show)

        # Sleep
        act_sleep = QAction("Sleep / Wake", menu)
        act_sleep.triggered.connect(self._toggle_sleep)
        menu.addAction(act_sleep)

        # TTS mute
        self._act_mute = QAction("Mute voice", menu)
        self._act_mute.setCheckable(True)
        self._act_mute.triggered.connect(self._toggle_mute)
        menu.addAction(self._act_mute)

        menu.addSeparator()

        # Text input
        if self._text_input_fn:
            act_text = QAction("Type a command…", menu)
            act_text.triggered.connect(self._text_input_fn)
            menu.addAction(act_text)
            menu.addSeparator()

        # Exit
        act_exit = QAction("Exit KAI", menu)
        act_exit.triggered.connect(self._quit)
        menu.addAction(act_exit)

        self.setContextMenu(menu)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_visibility()

    def _toggle_visibility(self) -> None:
        if self._island.isVisible():
            self._island.hide()
            self._act_show.setText("Show island")
        else:
            self._island.show()
            self._act_show.setText("Hide island")

    def _toggle_sleep(self) -> None:
        if state_machine.current == KAIState.SLEEPING:
            state_machine.wake()
        else:
            state_machine.sleep()

    def _toggle_mute(self, checked: bool) -> None:
        self._tts_muted = checked
        bus.emit("on_tts_mute", muted=checked)
        logger.info("TTS muted: %s", checked)

    def _quit(self) -> None:
        bus.emit("on_quit")
        QApplication.quit()
