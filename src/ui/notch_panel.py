"""
src/ui/notch_panel.py
=====================
Expandable Top Notch Dashboard Panel for KAI.
Replicates the Troko-Desk dashboard functionality from https://trokotec.com/desk/#funciones:
- 5 Modular Views:
    1. Inicio: Daily summary, text/mic input field, KPI stat cards (Agua, Tareas, Enfoque).
    2. Tareas: Interactive checklist with live add/toggle/delete, SQLite persistence.
    3. Hábitos: Water tracker with visual progress, +1 vaso and Deshacer buttons.
    4. Enfoque: Pomodoro 25min focus timer with live countdown, start/pause/reset.
    5. Mi PC: Desktop organizer scanner, loose file category counts, clean now & undo.
- Dark theme matching KAI identity (#0C0E17, #121524, #7F5AF0).
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from actions.file_organizer import scan_desktop, execute_moves, undo_last_move
from actions.habits_tracker import get_today_progress, log_habit
from config.settings import settings
from core.event_bus import bus
from core.state_machine import TrokoState, state_machine
from storage.db import add_task, delete_task, get_tasks, toggle_task

logger = logging.getLogger(__name__)


class NotchPanel(QFrame):
    """
    Expandable dashboard panel docked beneath KAI's notch island.
    """

    taskCountChanged = pyqtSignal(int)
    waterCountChanged = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("notchPanel")
        self.setStyleSheet(
            """
            QFrame#notchPanel {
                background-color: #0F111D;
                border-radius: 18px;
                border: 1px solid #7F5AF0;
            }
            QWidget {
                color: #FFFFFF;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            /* Sidebar navigation tabs */
            QFrame#sideBar {
                background-color: #151828;
                border-top-left-radius: 18px;
                border-bottom-left-radius: 18px;
                border-right: 1px solid #232742;
            }
            QPushButton.navTab {
                background-color: transparent;
                border: none;
                border-radius: 8px;
                color: #94A1B2;
                font-size: 12px;
                font-weight: 600;
                text-align: left;
                padding: 8px 12px;
            }
            QPushButton.navTab:hover {
                background-color: #1F233B;
                color: #FFFFFF;
            }
            QPushButton.navTab[active="true"] {
                background-color: #7F5AF0;
                color: #FFFFFF;
            }
            /* Action Buttons */
            QPushButton.btnPrimary {
                background-color: #7F5AF0;
                border: none;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: bold;
                padding: 6px 14px;
            }
            QPushButton.btnPrimary:hover {
                background-color: #6A45E5;
            }
            QPushButton.btnSecondary {
                background-color: #24283B;
                border: 1px solid #3B4261;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 11px;
                font-weight: bold;
                padding: 6px 14px;
            }
            QPushButton.btnSecondary:hover {
                background-color: #323752;
            }
            QPushButton.btnGreen {
                background-color: #2CB67D;
                border: none;
                border-radius: 8px;
                color: #0F111D;
                font-size: 11px;
                font-weight: bold;
                padding: 6px 14px;
            }
            QPushButton.btnGreen:hover {
                background-color: #249A68;
            }
            QPushButton.btnBlue {
                background-color: #00E5FF;
                border: none;
                border-radius: 8px;
                color: #0F111D;
                font-size: 11px;
                font-weight: bold;
                padding: 6px 14px;
            }
            QPushButton.btnBlue:hover {
                background-color: #00B8D4;
            }
            QLineEdit {
                background-color: #1A1D2E;
                border: 1px solid #333854;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 12px;
                padding: 6px 10px;
            }
            QLineEdit:focus {
                border: 1px solid #7F5AF0;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            """
        )

        self.water_count = 6
        self.water_target = 8
        self.pomodoro_remaining = 25 * 60
        self.pomodoro_active = False

        self._setup_ui()
        self._load_data()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ------------------------------------------------------------------
        # Sidebar Navigation
        # ------------------------------------------------------------------
        sidebar = QFrame(self)
        sidebar.setObjectName("sideBar")
        sidebar.setFixedWidth(145)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(10, 14, 10, 14)
        sb_layout.setSpacing(6)

        # Who header
        who_layout = QHBoxLayout()
        who_label = QLabel("<b>KAI</b>", sidebar)
        who_label.setStyleSheet("font-size: 15px; color: #FFFFFF;")
        self.status_dot = QLabel("●", sidebar)
        self.status_dot.setStyleSheet("color: #2CB67D; font-size: 12px;")
        self.status_text = QLabel("Listo", sidebar)
        self.status_text.setStyleSheet("font-size: 11px; color: #94A1B2;")
        who_layout.addWidget(who_label)
        who_layout.addWidget(self.status_dot)
        who_layout.addWidget(self.status_text)
        who_layout.addStretch()
        sb_layout.addLayout(who_layout)
        sb_layout.addSpacing(10)

        # Navigation Tabs
        self.tab_buttons: list[QPushButton] = []
        tab_specs = [
            ("Inicio", "🏠 Inicio", 0),
            ("Tareas", "📋 Tareas", 1),
            ("Habitos", "💧 Hábitos", 2),
            ("Enfoque", "⏱️ Enfoque", 3),
            ("MiPC", "💻 Mi PC", 4),
        ]

        for name, text, idx in tab_specs:
            btn = QPushButton(text, sidebar)
            btn.setProperty("class", "navTab")
            btn.setProperty("active", "true" if idx == 0 else "false")
            btn.clicked.connect(lambda _, i=idx: self.switch_view(i))
            self.tab_buttons.append(btn)
            sb_layout.addWidget(btn)

        sb_layout.addStretch()
        main_layout.addWidget(sidebar)

        # ------------------------------------------------------------------
        # Main Content Views (Stacked)
        # ------------------------------------------------------------------
        self.views_stack = QStackedWidget(self)
        main_layout.addWidget(self.views_stack)

        self._build_view_inicio()
        self._build_view_tareas()
        self._build_view_habitos()
        self._build_view_enfoque()
        self._build_view_mipc()

    # ------------------------------------------------------------------
    # 1. View: Inicio (Resumen de hoy)
    # ------------------------------------------------------------------
    def _build_view_inicio(self) -> None:
        view = QWidget(self)
        layout = QVBoxLayout(view)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        title = QLabel("<b>Inicio</b>", view)
        title.setStyleSheet("font-size: 16px;")
        sub = QLabel("Tu resumen y control rápido de hoy", view)
        sub.setStyleSheet("font-size: 11px; color: #94A1B2;")
        layout.addWidget(title)
        layout.addWidget(sub)

        # Speak / Write input field
        input_layout = QHBoxLayout()
        self.input_prompt = QLineEdit(view)
        self.input_prompt.setPlaceholderText("Escribe o habla con KAI… (Enter para enviar)")
        self.input_prompt.returnPressed.connect(self._on_prompt_enter)
        btn_mic = QPushButton("🎤", view)
        btn_mic.setProperty("class", "btnSecondary")
        btn_mic.setToolTip("Hablar con KAI")
        btn_mic.clicked.connect(lambda: bus.emit("on_wake"))
        input_layout.addWidget(self.input_prompt)
        input_layout.addWidget(btn_mic)
        layout.addLayout(input_layout)

        # KPI Stats Grid
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(10)

        # Stat 1: Agua
        self.card_water = QFrame(view)
        self.card_water.setStyleSheet("background-color: #161A2D; border-radius: 10px; padding: 8px;")
        cw_layout = QVBoxLayout(self.card_water)
        self.lbl_card_water = QLabel("💧 <b>6/8</b>", self.card_water)
        self.lbl_card_water.setStyleSheet("font-size: 14px; color: #00E5FF;")
        cw_sub = QLabel("vasos de agua", self.card_water)
        cw_sub.setStyleSheet("font-size: 10px; color: #94A1B2;")
        cw_layout.addWidget(self.lbl_card_water)
        cw_layout.addWidget(cw_sub)
        stats_layout.addWidget(self.card_water)

        # Stat 2: Tareas
        self.card_tasks = QFrame(view)
        self.card_tasks.setStyleSheet("background-color: #161A2D; border-radius: 10px; padding: 8px;")
        ct_layout = QVBoxLayout(self.card_tasks)
        self.lbl_card_tasks = QLabel("📋 <b>0</b>", self.card_tasks)
        self.lbl_card_tasks.setStyleSheet("font-size: 14px; color: #A882FF;")
        ct_sub = QLabel("tareas pendientes", self.card_tasks)
        ct_sub.setStyleSheet("font-size: 10px; color: #94A1B2;")
        ct_layout.addWidget(self.lbl_card_tasks)
        ct_layout.addWidget(ct_sub)
        stats_layout.addWidget(self.card_tasks)

        # Stat 3: Enfoque
        self.card_focus = QFrame(view)
        self.card_focus.setStyleSheet("background-color: #161A2D; border-radius: 10px; padding: 8px;")
        cf_layout = QVBoxLayout(self.card_focus)
        self.lbl_card_focus = QLabel("⏱️ <b>25:00</b>", self.card_focus)
        self.lbl_card_focus.setStyleSheet("font-size: 14px; color: #2CB67D;")
        cf_sub = QLabel("bloque de enfoque", self.card_focus)
        cf_sub.setStyleSheet("font-size: 10px; color: #94A1B2;")
        cf_layout.addWidget(self.lbl_card_focus)
        cf_layout.addWidget(cf_sub)
        stats_layout.addWidget(self.card_focus)

        layout.addLayout(stats_layout)
        layout.addStretch()
        self.views_stack.addWidget(view)

    # ------------------------------------------------------------------
    # 2. View: Tareas (Checklist)
    # ------------------------------------------------------------------
    def _build_view_tareas(self) -> None:
        view = QWidget(self)
        layout = QVBoxLayout(view)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        title = QLabel("<b>Tareas</b>", view)
        title.setStyleSheet("font-size: 16px;")
        self.lbl_tasks_sub = QLabel("Cargando tareas...", view)
        self.lbl_tasks_sub.setStyleSheet("font-size: 11px; color: #94A1B2;")
        layout.addWidget(title)
        layout.addWidget(self.lbl_tasks_sub)

        # Add task input
        add_layout = QHBoxLayout()
        self.input_new_task = QLineEdit(view)
        self.input_new_task.setPlaceholderText("Nueva tarea... (Enter para agregar)")
        self.input_new_task.returnPressed.connect(self._on_add_task)
        btn_add = QPushButton("Agregar", view)
        btn_add.setProperty("class", "btnPrimary")
        btn_add.clicked.connect(self._on_add_task)
        add_layout.addWidget(self.input_new_task)
        add_layout.addWidget(btn_add)
        layout.addLayout(add_layout)

        # Tasks Scrollable list
        self.tasks_scroll = QScrollArea(view)
        self.tasks_scroll.setWidgetResizable(True)
        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setContentsMargins(0, 4, 0, 4)
        self.tasks_layout.setSpacing(6)
        self.tasks_layout.addStretch()
        self.tasks_scroll.setWidget(self.tasks_container)
        layout.addWidget(self.tasks_scroll)

        self.views_stack.addWidget(view)

    # ------------------------------------------------------------------
    # 3. View: Hábitos (Water tracker + 15 habits)
    # ------------------------------------------------------------------
    def _build_view_habitos(self) -> None:
        view = QWidget(self)
        layout = QVBoxLayout(view)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        title = QLabel("<b>Hábitos</b>", view)
        title.setStyleSheet("font-size: 16px;")
        sub = QLabel("Tu hidratación y metas diarias", view)
        sub.setStyleSheet("font-size: 11px; color: #94A1B2;")
        layout.addWidget(title)
        layout.addWidget(sub)

        # Water card
        water_frame = QFrame(view)
        water_frame.setStyleSheet("background-color: #141728; border-radius: 12px; padding: 12px; border: 1px solid #282C48;")
        wf_layout = QVBoxLayout(water_frame)
        wf_layout.setSpacing(10)

        wh_layout = QHBoxLayout()
        lbl_w = QLabel("💧 <b>Agua</b>", water_frame)
        lbl_w.setStyleSheet("font-size: 15px; color: #00E5FF;")
        self.lbl_water_detail = QLabel("6 de 8 vasos", water_frame)
        self.lbl_water_detail.setStyleSheet("font-size: 13px; font-weight: bold;")
        wh_layout.addWidget(lbl_w)
        wh_layout.addStretch()
        wh_layout.addWidget(self.lbl_water_detail)
        wf_layout.addLayout(wh_layout)

        # Visual drop progress bar
        self.drops_label = QLabel("💧 💧 💧 💧 💧 💧 ⚪ ⚪", water_frame)
        self.drops_label.setStyleSheet("font-size: 16px;")
        wf_layout.addWidget(self.drops_label)

        # Water action buttons
        act_layout = QHBoxLayout()
        btn_add_water = QPushButton("+1 Vaso", water_frame)
        btn_add_water.setProperty("class", "btnBlue")
        btn_add_water.clicked.connect(self._on_add_water)
        btn_undo_water = QPushButton("Deshacer", water_frame)
        btn_undo_water.setProperty("class", "btnSecondary")
        btn_undo_water.clicked.connect(self._on_undo_water)
        act_layout.addWidget(btn_add_water)
        act_layout.addWidget(btn_undo_water)
        act_layout.addStretch()
        wf_layout.addLayout(act_layout)

        layout.addWidget(water_frame)
        layout.addStretch()
        self.views_stack.addWidget(view)

    # ------------------------------------------------------------------
    # 4. View: Enfoque (Pomodoro)
    # ------------------------------------------------------------------
    def _build_view_enfoque(self) -> None:
        view = QWidget(self)
        layout = QVBoxLayout(view)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(12)

        title = QLabel("<b>Enfoque</b>", view)
        title.setStyleSheet("font-size: 16px;")
        sub = QLabel("Bloques de concentración de 25 min con descansos", view)
        sub.setStyleSheet("font-size: 11px; color: #94A1B2;")
        layout.addWidget(title)
        layout.addWidget(sub)

        focus_card = QFrame(view)
        focus_card.setStyleSheet("background-color: #141728; border-radius: 12px; padding: 14px; border: 1px solid #282C48;")
        fc_layout = QVBoxLayout(focus_card)
        fc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_focus_clock = QLabel("25:00", focus_card)
        self.lbl_focus_clock.setStyleSheet("font-size: 34px; font-weight: bold; color: #2CB67D; font-family: monospace;")
        self.lbl_focus_clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fc_layout.addWidget(self.lbl_focus_clock)

        self.lbl_focus_status = QLabel("25 minutos de enfoque, 5 de descanso.", focus_card)
        self.lbl_focus_status.setStyleSheet("font-size: 11px; color: #94A1B2;")
        self.lbl_focus_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fc_layout.addWidget(self.lbl_focus_status)

        fc_btn_layout = QHBoxLayout()
        self.btn_focus_toggle = QPushButton("Empezar", focus_card)
        self.btn_focus_toggle.setProperty("class", "btnGreen")
        self.btn_focus_toggle.clicked.connect(self._on_toggle_focus)
        btn_focus_reset = QPushButton("Reiniciar", focus_card)
        btn_focus_reset.setProperty("class", "btnSecondary")
        btn_focus_reset.clicked.connect(self._on_reset_focus)
        fc_btn_layout.addStretch()
        fc_btn_layout.addWidget(self.btn_focus_toggle)
        fc_btn_layout.addWidget(btn_focus_reset)
        fc_btn_layout.addStretch()
        fc_layout.addLayout(fc_btn_layout)

        layout.addWidget(focus_card)
        layout.addStretch()
        self.views_stack.addWidget(view)

    # ------------------------------------------------------------------
    # 5. View: Mi PC (Desktop organizer)
    # ------------------------------------------------------------------
    def _build_view_mipc(self) -> None:
        view = QWidget(self)
        layout = QVBoxLayout(view)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        title = QLabel("<b>Mi PC</b>", view)
        title.setStyleSheet("font-size: 16px;")
        self.lbl_pc_sub = QLabel("Tu escritorio · Escaneando archivos...", view)
        self.lbl_pc_sub.setStyleSheet("font-size: 11px; color: #94A1B2;")
        layout.addWidget(title)
        layout.addWidget(self.lbl_pc_sub)

        # Category chips card
        chips_frame = QFrame(view)
        chips_frame.setStyleSheet("background-color: #141728; border-radius: 12px; padding: 12px; border: 1px solid #282C48;")
        cf_layout = QVBoxLayout(chips_frame)

        self.lbl_pc_chips = QLabel("🖼️ Imágenes: 0  |  📄 Documentos: 0  |  📦 Instaladores: 0", chips_frame)
        self.lbl_pc_chips.setStyleSheet("font-size: 12px; color: #E2E8F0;")
        cf_layout.addWidget(self.lbl_pc_chips)

        pc_btn_layout = QHBoxLayout()
        btn_tidy = QPushButton("Ordenar ahora", chips_frame)
        btn_tidy.setProperty("class", "btnGreen")
        btn_tidy.clicked.connect(self._on_tidy_desktop)
        self.btn_tidy_undo = QPushButton("Deshacer", chips_frame)
        self.btn_tidy_undo.setProperty("class", "btnSecondary")
        self.btn_tidy_undo.clicked.connect(self._on_tidy_undo)
        pc_btn_layout.addWidget(btn_tidy)
        pc_btn_layout.addWidget(self.btn_tidy_undo)
        pc_btn_layout.addStretch()
        cf_layout.addLayout(pc_btn_layout)

        hint = QLabel("También puedes decir «KAI, ordena mi escritorio». Nunca borra nada: solo clasifica.", chips_frame)
        hint.setStyleSheet("font-size: 10px; color: #7F5AF0; margin-top: 4px;")
        cf_layout.addWidget(hint)

        layout.addWidget(chips_frame)
        layout.addStretch()
        self.views_stack.addWidget(view)

    # ------------------------------------------------------------------
    # Data Loading & Refresh
    # ------------------------------------------------------------------

    def _load_data(self) -> None:
        self.refresh_tasks()
        self.refresh_water()
        self.refresh_desktop_status()

    def switch_view(self, index: int) -> None:
        self.views_stack.setCurrentIndex(index)
        for i, btn in enumerate(self.tab_buttons):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if index == 1:
            self.refresh_tasks()
        elif index == 2:
            self.refresh_water()
        elif index == 4:
            self.refresh_desktop_status()

    # ------------------------------------------------------------------
    # Prompt Actions
    # ------------------------------------------------------------------

    def _on_prompt_enter(self) -> None:
        txt = self.input_prompt.text().strip()
        if txt:
            self.input_prompt.clear()
            bus.emit("on_transcript", text=txt)
            state_machine.feedback("Enviado", success=True)

    # ------------------------------------------------------------------
    # Tasks logic
    # ------------------------------------------------------------------

    def refresh_tasks(self) -> None:
        tasks = get_tasks()
        pending = sum(1 for t in tasks if not t["completed"])
        self.lbl_tasks_sub.setText(f"{pending} pendientes")
        self.lbl_card_tasks.setText(f"📋 <b>{pending}</b>")
        self.taskCountChanged.emit(pending)

        # Clear layout
        while self.tasks_layout.count() > 1:
            item = self.tasks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for t in tasks:
            row = QFrame()
            row.setStyleSheet("background-color: #171A2B; border-radius: 6px; padding: 4px 8px;")
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(4, 2, 4, 2)

            chk = QCheckBox(t["title"])
            chk.setChecked(t["completed"])
            if t["completed"]:
                chk.setStyleSheet("color: #718096; text-decoration: line-through;")
            else:
                chk.setStyleSheet("color: #FFFFFF;")

            task_id = t["id"]
            chk.toggled.connect(lambda checked, tid=task_id: self._on_toggle_task(tid, checked))

            btn_del = QPushButton("✕")
            btn_del.setFixedSize(20, 20)
            btn_del.setStyleSheet("background: transparent; color: #718096; border: none; font-weight: bold;")
            btn_del.clicked.connect(lambda _, tid=task_id: self._on_delete_task(tid))

            r_layout.addWidget(chk)
            r_layout.addStretch()
            r_layout.addWidget(btn_del)
            self.tasks_layout.insertWidget(self.tasks_layout.count() - 1, row)

    def _on_add_task(self) -> None:
        title = self.input_new_task.text().strip()
        if title:
            add_task(title)
            self.input_new_task.clear()
            self.refresh_tasks()
            state_machine.feedback("Anotado", success=True)

    def _on_toggle_task(self, task_id: int, completed: bool) -> None:
        toggle_task(task_id, completed)
        self.refresh_tasks()

    def _on_delete_task(self, task_id: int) -> None:
        delete_task(task_id)
        self.refresh_tasks()

    # ------------------------------------------------------------------
    # Water logic
    # ------------------------------------------------------------------

    def refresh_water(self) -> None:
        prog = get_today_progress("agua", target=self.water_target)
        self.water_count = prog.get("current_count", 6)
        self.lbl_water_detail.setText(f"{self.water_count} de {self.water_target} vasos")
        self.lbl_card_water.setText(f"💧 <b>{self.water_count}/{self.water_target}</b>")

        # Drops string
        drops = []
        for i in range(self.water_target):
            drops.append("💧" if i < self.water_count else "⚪")
        self.drops_label.setText(" ".join(drops))
        self.waterCountChanged.emit(self.water_count)

    def _on_add_water(self) -> None:
        res = log_habit("agua", amount=1)
        self.water_count = res.get("current_count", self.water_count + 1)
        self.refresh_water()
        if self.water_count >= self.water_target:
            state_machine.celebrate("¡Meta Cumplida!")
        else:
            state_machine.feedback("+1 Vaso", success=True)

    def _on_undo_water(self) -> None:
        res = log_habit("agua", amount=-1)
        self.water_count = max(0, res.get("current_count", self.water_count - 1))
        self.refresh_water()
        state_machine.feedback("Deshecho", success=True)

    # ------------------------------------------------------------------
    # Focus / Pomodoro logic
    # ------------------------------------------------------------------

    def _on_toggle_focus(self) -> None:
        if not self.pomodoro_active:
            self.pomodoro_active = True
            self.btn_focus_toggle.setText("Pausar")
            self.lbl_focus_status.setText("Enfoque activo: ¡a concentrarse!")
            state_machine.transition(TrokoState.HABIT_POMODORO)
        else:
            self.pomodoro_active = False
            self.btn_focus_toggle.setText("Reanudar")
            self.lbl_focus_status.setText("Enfoque en pausa.")
            state_machine.transition(TrokoState.REPOSO)

    def _on_reset_focus(self) -> None:
        self.pomodoro_active = False
        self.pomodoro_remaining = 25 * 60
        self.btn_focus_toggle.setText("Empezar")
        self.lbl_focus_clock.setText("25:00")
        self.lbl_card_focus.setText("⏱️ <b>25:00</b>")
        self.lbl_focus_status.setText("25 minutos de enfoque, 5 de descanso.")
        state_machine.transition(TrokoState.REPOSO)

    def update_pomodoro_tick(self, seconds_left: int) -> None:
        self.pomodoro_remaining = seconds_left
        mins = seconds_left // 60
        secs = seconds_left % 60
        time_str = f"{mins:02d}:{secs:02d}"
        self.lbl_focus_clock.setText(time_str)
        self.lbl_card_focus.setText(f"⏱️ <b>{time_str}</b>")

    # ------------------------------------------------------------------
    # Desktop organizer logic
    # ------------------------------------------------------------------

    def refresh_desktop_status(self) -> None:
        try:
            planned = scan_desktop()
            loose = len(planned)
            self.lbl_pc_sub.setText(f"Tu escritorio · {loose} archivos sueltos")
            cats: dict[str, int] = {}
            for item in planned:
                c = item.get("category", "Misc")
                cats[c] = cats.get(c, 0) + 1
            chips = [f"📁 {k}: {v}" for k, v in cats.items()]
            if chips:
                self.lbl_pc_chips.setText("  |  ".join(chips))
            else:
                self.lbl_pc_chips.setText("✨ ¡Escritorio completamente ordenado!")
        except Exception as exc:
            logger.debug("Failed desktop scan: %s", exc)

    def _on_tidy_desktop(self) -> None:
        try:
            planned = scan_desktop()
            if not planned:
                state_machine.feedback("Ya ordenado", success=True)
                return
            res = execute_moves(planned)
            moved = len(res)
            state_machine.feedback(f"Ordenados {moved}", success=True)
            self.refresh_desktop_status()
        except Exception as exc:
            logger.error("Error organizing desktop: %s", exc)

    def _on_tidy_undo(self) -> None:
        try:
            msg = undo_last_move()
            state_machine.feedback("Deshecho", success=True)
            self.refresh_desktop_status()
        except Exception as exc:
            logger.error("Error undoing desktop organize: %s", exc)
