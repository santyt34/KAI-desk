"""
ui/island_window.py
===================
Frameless, transparent, always-on-top floating "island" window anchored
at the top-centre of the primary screen.  Hosts the EyeRenderer widget
and reacts to state changes via the EventBus (never blocks on AI/audio).
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QCursor, QScreen
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QWidget

from config.settings import settings
from core.event_bus import bus
from core.state_machine import KAIState, state_machine
from ui.eye_renderer import EyeRenderer

logger = logging.getLogger(__name__)


class IslandWindow(QWidget):
    """
    Main island window.

    Flags:
    - FramelessWindowHint  → no title bar / borders
    - WindowStaysOnTopHint → always above other windows
    - Tool                 → no taskbar entry
    - WindowTransparentForInput → pass-through clicks (optional, see toggle)
    """

    def __init__(self) -> None:
        super().__init__()
        self._setup_window()
        self._setup_layout()
        self._connect_events()
        self._start_cursor_tracker()
        logger.info("IslandWindow initialised")

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        # Size & position
        screen: QScreen = QApplication.primaryScreen()
        screen_geom = screen.availableGeometry()
        w = settings.ui_width
        h = settings.ui_height
        x = screen_geom.center().x() - w // 2
        y = screen_geom.top() + 6          # 6px margin from top
        self.setGeometry(x, y, w, h)
        self.setMinimumSize(w, h)
        self.setMaximumSize(w, h)
        self.setWindowOpacity(settings.ui_opacity)
        self.setWindowTitle("KAI")

    def _setup_layout(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.eye_renderer = EyeRenderer(parent=self)
        layout.addWidget(self.eye_renderer)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Event bus → UI state bridge (always called on main thread via Qt)
    # ------------------------------------------------------------------

    def _connect_events(self) -> None:
        """Subscribe to bus events; dispatch to Qt slot via QTimer.singleShot."""
        bus.subscribe("on_state_change", self._on_state_change_threadsafe)
        bus.subscribe("on_quit", lambda **_: self.close())

    def _on_state_change_threadsafe(self, state: str, **_kwargs) -> None:
        """Thread-safe bridge: post state update back to main Qt event loop."""
        # singleShot with 0 ms queues the call on the Qt main thread
        QTimer.singleShot(0, lambda: self._apply_state(state))

    @pyqtSlot()
    def _apply_state(self, state: str) -> None:
        try:
            kai_state = KAIState(state)
        except ValueError:
            logger.warning("Unknown state received: %s", state)
            return
        self.eye_renderer.set_state(kai_state)
        logger.debug("IslandWindow: state → %s", state)

    # ------------------------------------------------------------------
    # Cursor tracking for pupil follow
    # ------------------------------------------------------------------

    def _start_cursor_tracker(self) -> None:
        """Poll global cursor position to feed eye_renderer."""
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._update_cursor)
        # ~30 FPS poll is enough for pupil tracking (renderer runs at 60 FPS)
        self._cursor_timer.start(33)

    def _update_cursor(self) -> None:
        pos = QCursor.pos()
        self.eye_renderer.update_cursor(pos)

    # ------------------------------------------------------------------
    # Mouse interaction (drag to reposition)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        """Double-click toggles sleep/wake."""
        current = state_machine.current
        if current == KAIState.SLEEPING:
            state_machine.wake()
            bus.emit("on_wake")
        else:
            state_machine.sleep()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        logger.info("IslandWindow closing")
        self._cursor_timer.stop()
        super().closeEvent(event)
