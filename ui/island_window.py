"""
src/ui/island_window.py
=======================
Frameless, transparent, always-on-top floating upper "island" / notch window
for KAI. Anchored at the top-centre of the display.
Hosts EyeRenderer, hover animations, habit interaction controls, feedback badges
and action confirmations.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QCursor, QEnterEvent, QScreen
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QLabel,
    QFrame,
)

from config.settings import settings
from core.event_bus import bus
from core.state_machine import TrokoState, state_machine
from ui.eye_renderer import EyeRenderer

logger = logging.getLogger(__name__)


class IslandWindow(QWidget):
    """
    Main floating upper notch window for KAI.
    Flags: FramelessWindowHint | WindowStaysOnTopHint | Tool
    """

    def __init__(self) -> None:
        super().__init__()
        self._drag_pos = None
        self._confirmation_data = None

        self._setup_window()
        self._setup_layout()
        self._connect_events()
        self._start_cursor_tracker()
        logger.info("KAI IslandWindow initialised")

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

        screen: QScreen = QApplication.primaryScreen()
        screen_geom = screen.availableGeometry() if screen else None
        w = settings.ui_width
        h = settings.ui_height
        if screen_geom:
            x = screen_geom.center().x() - w // 2
            y = screen_geom.top() + 4
        else:
            x, y = 100, 10
        self.setGeometry(x, y, w, h)
        self.setMinimumSize(w, h)
        self.setWindowOpacity(settings.ui_opacity)
        self.setWindowTitle("KAI")

    def _setup_layout(self) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)

        # Eye and Mood Renderer Widget
        self.eye_renderer = EyeRenderer(parent=self)
        self.main_layout.addWidget(self.eye_renderer)

        # Habit Quick Controls Bar (Visible during habits like Water or Pomodoro)
        self.habit_bar = QFrame(self)
        self.habit_bar.setStyleSheet(
            """
            QFrame {
                background-color: #121422;
                border-radius: 10px;
                border: 1px solid #7F5AF0;
                padding: 2px;
            }
            QPushButton {
                background-color: #1E2238;
                color: #FFFFFF;
                border: 1px solid #3B4261;
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7F5AF0;
            }
            """
        )
        self.habit_layout = QHBoxLayout(self.habit_bar)
        self.habit_layout.setContentsMargins(6, 2, 6, 2)
        self.habit_layout.setSpacing(6)

        self.btn_habit_action1 = QPushButton("+1 Vaso", self.habit_bar)
        self.btn_habit_action2 = QPushButton("Deshacer", self.habit_bar)
        self.btn_habit_action1.clicked.connect(self._on_habit_action1_click)
        self.btn_habit_action2.clicked.connect(self._on_habit_action2_click)

        self.habit_layout.addStretch()
        self.habit_layout.addWidget(self.btn_habit_action1)
        self.habit_layout.addWidget(self.btn_habit_action2)
        self.habit_layout.addStretch()

        self.habit_bar.hide()
        self.main_layout.addWidget(self.habit_bar)

        # Contextual confirmation action bar (for file organization, email drafts)
        self.action_bar = QFrame(self)
        self.action_bar.setStyleSheet(
            """
            QFrame {
                background-color: #141726;
                border-radius: 12px;
                border: 1px solid #7F5AF0;
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
        self.main_layout.addWidget(self.action_bar)
        self.setLayout(self.main_layout)

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
        QTimer.singleShot(0, lambda: self.eye_renderer.update_pomodoro_countdown(seconds_left, active=True))

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

        st_val = str(troko_state.value if hasattr(troko_state, "value") else troko_state).lower()

        # Update Habit Control Bar
        if st_val == "agua":
            self.btn_habit_action1.setText("+1 Vaso")
            self.btn_habit_action2.setText("Deshacer")
            self.habit_bar.show()
            self.setFixedHeight(settings.ui_height + 36)
        elif st_val == "pomodoro":
            self.btn_habit_action1.setText("Pausar")
            self.btn_habit_action2.setText("Detener")
            self.habit_bar.show()
            self.setFixedHeight(settings.ui_height + 36)
        else:
            self.habit_bar.hide()
            if not self.action_bar.isVisible():
                self.setFixedHeight(settings.ui_height)

    # ------------------------------------------------------------------
    # Habit Button Actions
    # ------------------------------------------------------------------

    def _on_habit_action1_click(self) -> None:
        st_val = str(state_machine.current.value if hasattr(state_machine.current, "value") else state_machine.current).lower()
        if st_val == "agua":
            from actions.habits_tracker import log_habit
            res = log_habit("agua", amount=1)
            self.eye_renderer.set_water_progress(res.get("current_count", 6))
            state_machine.feedback("+1 Vaso", success=True)
        elif st_val == "pomodoro":
            state_machine.feedback("Pomodoro", success=True)

    def _on_habit_action2_click(self) -> None:
        st_val = str(state_machine.current.value if hasattr(state_machine.current, "value") else state_machine.current).lower()
        if st_val == "agua":
            from actions.habits_tracker import log_habit
            res = log_habit("agua", amount=-1)
            self.eye_renderer.set_water_progress(max(0, res.get("current_count", 5)))
            state_machine.feedback("Deshecho", success=True)
        elif st_val == "pomodoro":
            state_machine.transition(TrokoState.REPOSO)
            state_machine.feedback("Listo", success=True)

    # ------------------------------------------------------------------
    # Contextual Confirmation UI
    # ------------------------------------------------------------------

    def _show_confirmation_bar(self, title: str, callback_data: dict) -> None:
        self._confirmation_data = callback_data
        self.action_label.setText(title)
        self.action_bar.show()
        self.setFixedHeight(settings.ui_height + 44)

    def _hide_confirmation_bar(self) -> None:
        self.action_bar.hide()
        self._confirmation_data = None
        self.setFixedHeight(settings.ui_height)

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
    # Hover & Cursor Tracking
    # ------------------------------------------------------------------

    def enterEvent(self, event: QEnterEvent) -> None:
        self.eye_renderer.set_hover(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.eye_renderer.set_hover(False)
        super().leaveEvent(event)

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
        # Tap on island triggers active state or listen
        if event.button() == Qt.MouseButton.LeftButton and hasattr(self, "_drag_pos"):
            cur = state_machine.current
            st_val = str(cur.value if hasattr(cur, "value") else cur).lower()
            if st_val == "agua":
                from actions.habits_tracker import log_habit
                res = log_habit("agua", amount=1)
                self.eye_renderer.set_water_progress(res.get("current_count", 6))
                state_machine.feedback("+1 Vaso", success=True)
            elif st_val == "reposo":
                bus.emit("on_wake")
                state_machine.transition(TrokoState.ESCUCHA)

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
