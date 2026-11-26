"""
src/ui/island_window.py
=======================
Floating upper "island" / notch window for KAI.
Features:
- Native Notch Capsule anchored top-center of display (#0C0E17 to #121524 with #7F5AF0 glow).
- Smooth Hover Sliding Arrow ("▼"):
    On mouse enter or hover, an animated downward arrow slides downwards smoothly
    giving visual feedback to open the top menu dashboard.
- Expandable Notch Dashboard (NotchPanel):
    Opens with click or hover on the sliding arrow/notch, expanding into the full
    5-section dashboard (Inicio, Tareas, Hábitos, Enfoque, Mi PC).
    Includes auto-close on mouse leave (with 500ms delay), pin toggle, and Escape key close.
- EyeRenderer: 60 FPS procedural white circular eyes with 12 emotions & blinks.
- Contextual confirmation bar for safe file organizer and email drafts.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QCursor, QEnterEvent, QScreen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.settings import settings
from core.event_bus import bus
from core.state_machine import TrokoState, state_machine
from ui.eye_renderer import EyeRenderer
from ui.notch_panel import NotchPanel

logger = logging.getLogger(__name__)

COMPACT_WIDTH = 320
COMPACT_HEIGHT = 58
EXPANDED_WIDTH = 680
EXPANDED_HEIGHT = 410


class ArrowCueButton(QPushButton):
    """
    Subtle sliding chevron pill beneath the notch that moves downwards on hover.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setText("▼")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(18)
        self.setFixedWidth(56)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(
            """
            QPushButton {
                background-color: #1A1D2E;
                color: #A882FF;
                border: 1px solid #7F5AF0;
                border-top: none;
                border-bottom-left-radius: 9px;
                border-bottom-right-radius: 9px;
                font-size: 10px;
                font-weight: bold;
                padding: 0;
                margin: 0;
            }
            QPushButton:hover {
                background-color: #7F5AF0;
                color: #FFFFFF;
                border-color: #A882FF;
            }
            """
        )


class IslandWindow(QWidget):
    """
    Main floating upper notch window for KAI.
    Flags: FramelessWindowHint | WindowStaysOnTopHint | Tool
    """

    def __init__(self) -> None:
        super().__init__()
        self._drag_pos = None
        self._confirmation_data = None
        self._is_open = False
        self._is_pinned = False
        self._hover_leave_timer = QTimer(self)
        self._hover_leave_timer.setSingleShot(True)
        self._hover_leave_timer.timeout.connect(self._on_hover_timeout_close)

        self._arrow_slide_offset = 0.0

        self._setup_window()
        self._setup_layout()
        self._connect_events()
        self._start_cursor_tracker()
        logger.info("KAI IslandWindow initialised with expandable notch dashboard")

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

        self._apply_geometry(COMPACT_WIDTH, COMPACT_HEIGHT)
        self.setWindowOpacity(settings.ui_opacity)
        self.setWindowTitle("KAI")

    def _apply_geometry(self, w: int, h: int) -> None:
        screen: QScreen = QApplication.primaryScreen()
        screen_geom = screen.availableGeometry() if screen else None
        if screen_geom:
            x = screen_geom.center().x() - w // 2
            y = screen_geom.top() + 2
        else:
            x, y = 100, 4
        self.setGeometry(x, y, w, h)
        self.setFixedSize(w, h)

    def _setup_layout(self) -> None:
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # 1. Notch Capsule Container
        self.capsule_container = QWidget(self)
        capsule_layout = QVBoxLayout(self.capsule_container)
        capsule_layout.setContentsMargins(0, 0, 0, 0)
        capsule_layout.setSpacing(0)

        # Eye and Mood Renderer Widget
        self.eye_renderer = EyeRenderer(parent=self.capsule_container)
        self.eye_renderer.setFixedHeight(COMPACT_HEIGHT - 6)
        capsule_layout.addWidget(self.eye_renderer)
        self.root_layout.addWidget(self.capsule_container)

        # 2. Sliding Arrow Bar (Centered directly beneath the notch capsule)
        self.arrow_container = QWidget(self)
        self.arrow_layout = QHBoxLayout(self.arrow_container)
        self.arrow_layout.setContentsMargins(0, 0, 0, 0)
        self.arrow_layout.setSpacing(0)
        self.arrow_layout.addStretch()

        self.btn_arrow = ArrowCueButton(self.arrow_container)
        self.btn_arrow.clicked.connect(self.toggle_panel)
        self.arrow_layout.addWidget(self.btn_arrow)

        self.arrow_layout.addStretch()
        self.root_layout.addWidget(self.arrow_container)

        # 3. Contextual Confirmation Action Bar
        self.action_bar = QFrame(self)
        self.action_bar.setStyleSheet(
            """
            QFrame {
                background-color: #141726;
                border-radius: 12px;
                border: 1px solid #7F5AF0;
                margin: 4px;
                padding: 4px;
            }
            QPushButton {
                background-color: #24283B;
                color: #FFFFFF;
                border: 1px solid #3B4261;
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#btnConfirm {
                background-color: #2CB67D;
                color: #FFFFFF;
                border: none;
            }
            QPushButton#btnConfirm:hover {
                background-color: #249A68;
            }
            QPushButton#btnCancel:hover {
                background-color: #E53935;
            }
            QLabel {
                color: #EEEEEE;
                font-size: 11px;
            }
            """
        )
        self.action_layout = QHBoxLayout(self.action_bar)
        self.action_layout.setContentsMargins(8, 4, 8, 4)

        self.action_label = QLabel("Confirmación", self.action_bar)
        self.btn_confirm = QPushButton("Confirmar", self.action_bar)
        self.btn_confirm.setObjectName("btnConfirm")
        self.btn_cancel = QPushButton("Cancelar", self.action_bar)
        self.btn_cancel.setObjectName("btnCancel")

        self.btn_confirm.clicked.connect(self._on_action_confirm)
        self.btn_cancel.clicked.connect(self._on_action_cancel)

        self.action_layout.addWidget(self.action_label)
        self.action_layout.addStretch()
        self.action_layout.addWidget(self.btn_confirm)
        self.action_layout.addWidget(self.btn_cancel)

        self.action_bar.hide()
        self.root_layout.addWidget(self.action_bar)

        # 4. Expandable Dashboard Panel (NotchPanel)
        self.dashboard_panel = NotchPanel(parent=self)
        self.dashboard_panel.hide()
        self.root_layout.addWidget(self.dashboard_panel)

    # ------------------------------------------------------------------
    # Event Connections
    # ------------------------------------------------------------------

    def _connect_events(self) -> None:
        bus.subscribe("on_state_change", self._on_state_change_threadsafe)
        bus.subscribe("on_feedback_badge", self._on_feedback_badge_threadsafe)
        bus.subscribe("on_pomodoro_tick", self._on_pomodoro_tick_threadsafe)
        bus.subscribe("on_request_confirmation", self._on_request_confirmation_threadsafe)
        bus.subscribe("on_quit", lambda **_: self.close())

    def _on_state_change_threadsafe(self, state: str, **kwargs) -> None:
        QTimer.singleShot(0, lambda: self._apply_state(state, **kwargs))

    def _on_feedback_badge_threadsafe(self, text: str = "Listo", success: bool = True, **_) -> None:
        QTimer.singleShot(0, lambda: self.eye_renderer.anim.trigger_feedback_badge(text, success))

    def _on_pomodoro_tick_threadsafe(self, seconds_left: int, **_) -> None:
        QTimer.singleShot(0, lambda: self._on_pomodoro_tick(seconds_left))

    def _on_pomodoro_tick(self, seconds_left: int) -> None:
        self.eye_renderer.update_pomodoro_countdown(seconds_left, active=True)
        self.dashboard_panel.update_pomodoro_tick(seconds_left)

    def _on_request_confirmation_threadsafe(self, title: str, callback_data: dict, **_) -> None:
        QTimer.singleShot(0, lambda: self._show_confirmation_bar(title, callback_data))

    @pyqtSlot()
    def _apply_state(self, state: str, **kwargs) -> None:
        try:
            troko_state = TrokoState(state)
        except ValueError:
            logger.warning("Unknown state received: %s", state)
            return

        self.eye_renderer.set_state(troko_state)

        # Update panel status label
        st_val = str(troko_state.value if hasattr(troko_state, "value") else troko_state).lower()
        readable_status = {
            "reposo": "Listo",
            "escucha": "Escuchando",
            "piensa": "Pensando",
            "habla": "Hablando",
            "alerta": "Alerta",
            "sueno": "Dormido",
            "pomodoro": "Enfoque",
        }.get(st_val, st_val.capitalize())
        self.dashboard_panel.status_text.setText(readable_status)

        # When listening or speaking, if desired, open panel or pulse
        if st_val == "escucha":
            self.dashboard_panel.status_dot.setStyleSheet("color: #00E5FF; font-size: 12px;")
        elif st_val == "alerta":
            self.dashboard_panel.status_dot.setStyleSheet("color: #FF5252; font-size: 12px;")
        else:
            self.dashboard_panel.status_dot.setStyleSheet("color: #2CB67D; font-size: 12px;")

    # ------------------------------------------------------------------
    # Panel Expand / Collapse with Smooth Arrow Transition
    # ------------------------------------------------------------------

    def toggle_panel(self) -> None:
        if self._is_open:
            self.close_panel()
        else:
            self.open_panel()

    def open_panel(self, pinned: bool = False) -> None:
        if self._is_open:
            return
        self._hover_leave_timer.stop()
        self._is_open = True
        self._is_pinned = pinned

        self.btn_arrow.setText("▲")
        self.btn_arrow.setToolTip("Cerrar panel de KAI (Esc)")
        self.dashboard_panel.show()
        self.dashboard_panel._load_data()

        self._apply_geometry(EXPANDED_WIDTH, EXPANDED_HEIGHT)
        state_machine.wake()

    def close_panel(self) -> None:
        if not self._is_open:
            return
        self._hover_leave_timer.stop()
        self._is_open = False
        self._is_pinned = False

        self.btn_arrow.setText("▼")
        self.btn_arrow.setToolTip("Abrir menú de KAI")
        self.dashboard_panel.hide()

        self._apply_geometry(COMPACT_WIDTH, COMPACT_HEIGHT)

    # ------------------------------------------------------------------
    # Hover Detection & Sliding Arrow Animation
    # ------------------------------------------------------------------

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hover_leave_timer.stop()
        self.eye_renderer.set_hover(True)

        # Arrow slides downwards smoothly by 4px on hover
        if not self._is_open:
            self.btn_arrow.setStyleSheet(
                """
                QPushButton {
                    background-color: #7F5AF0;
                    color: #FFFFFF;
                    border: 1px solid #A882FF;
                    border-top: none;
                    border-bottom-left-radius: 9px;
                    border-bottom-right-radius: 9px;
                    font-size: 11px;
                    font-weight: bold;
                    margin-top: 2px;
                }
                """
            )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.eye_renderer.set_hover(False)

        # Reset arrow style
        if not self._is_open:
            self.btn_arrow.setStyleSheet(
                """
                QPushButton {
                    background-color: #1A1D2E;
                    color: #A882FF;
                    border: 1px solid #7F5AF0;
                    border-top: none;
                    border-bottom-left-radius: 9px;
                    border-bottom-right-radius: 9px;
                    font-size: 10px;
                    font-weight: bold;
                    margin-top: 0px;
                }
                """
            )
            # Gentle delay to auto-close if left open and unpinned
            self._hover_leave_timer.start(500)
        elif not self._is_pinned:
            self._hover_leave_timer.start(600)

        super().leaveEvent(event)

    def _on_hover_timeout_close(self) -> None:
        # If cursor is truly outside window geometry, fold back
        cursor_pos = QCursor.pos()
        if not self.geometry().contains(cursor_pos) and not self._is_pinned and self._is_open:
            self.close_panel()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and self._is_open:
            self.close_panel()
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Contextual Confirmation UI
    # ------------------------------------------------------------------

    def _show_confirmation_bar(self, title: str, callback_data: dict) -> None:
        self._confirmation_data = callback_data
        self.action_label.setText(title)
        self.action_bar.show()
        if not self._is_open:
            self.setFixedHeight(COMPACT_HEIGHT + 44)

    def _hide_confirmation_bar(self) -> None:
        self.action_bar.hide()
        self._confirmation_data = None
        if not self._is_open:
            self.setFixedHeight(COMPACT_HEIGHT)

    def _on_action_confirm(self) -> None:
        if self._confirmation_data:
            bus.emit("on_confirmation_resolved", confirmed=True, data=self._confirmation_data)
        state_machine.feedback("Confirmado", success=True)
        self._hide_confirmation_bar()

    def _on_action_cancel(self) -> None:
        if self._confirmation_data:
            bus.emit("on_confirmation_resolved", confirmed=False, data=self._confirmation_data)
        state_machine.feedback("Cancelado", success=False)
        self._hide_confirmation_bar()

    # ------------------------------------------------------------------
    # Cursor Tracking
    # ------------------------------------------------------------------

    def _start_cursor_tracker(self) -> None:
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._update_cursor)
        self._cursor_timer.start(33)

    def _update_cursor(self) -> None:
        pos = QCursor.pos()
        self.eye_renderer.update_cursor(pos)

    # ------------------------------------------------------------------
    # Mouse Interaction (Drag, Click, Double-Click)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        # Tap on notch capsule triggers open or listen
        if event.button() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            # Check if clicked inside the capsule area
            click_y = event.position().y()
            if click_y <= COMPACT_HEIGHT:
                cur = state_machine.current
                st_val = str(cur.value if hasattr(cur, "value") else cur).lower()
                if st_val == "agua":
                    from actions.habits_tracker import log_habit
                    res = log_habit("agua", amount=1)
                    self.eye_renderer.set_water_progress(res.get("current_count", 6))
                    self.dashboard_panel.refresh_water()
                    state_machine.feedback("+1 Vaso", success=True)
                elif not self._is_open:
                    self.toggle_panel()

    def mouseDoubleClickEvent(self, event) -> None:
        """Double click toggles sleep / wake."""
        cur = state_machine.current
        st_val = str(cur.value if hasattr(cur, "value") else cur).lower()
        if st_val == "sueno":
            state_machine.wake()
            state_machine.feedback("¡Despierto!", success=True)
            bus.emit("on_wake")
        else:
            state_machine.sleep()
            state_machine.feedback("Zzz...", success=True)

    def closeEvent(self, event) -> None:
        self._cursor_timer.stop()
        super().closeEvent(event)
