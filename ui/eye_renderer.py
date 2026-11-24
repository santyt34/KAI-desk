"""
ui/eye_renderer.py
==================
60 FPS Procedural Eye, Emotion and Habit Scene Renderer for Troko-Desk.
Renders:
- 12 Parametric Emotions with custom eye shapes, eyebrows and speculars.
- 7 Operational Island States (reposo, escucha, piensa, habla, alerta, notificacion, sueno).
- 15 Animated Procedural Habit Scenes + Celebration Confetti.
- Dynamic Overlays (rubor, corazones, estrellas, gotas de sudor).
- Cursor follow with natural easing and smooth blinking.
"""

from __future__ import annotations

import math
import random
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QLinearGradient,
)
from PyQt6.QtWidgets import QWidget

from config.settings import settings
from core.state_machine import TrokoState
from ui.animation_engine import AnimationEngine, ease_out_bounce, ease_out_quad

logger = logging.getLogger(__name__)

# Colors
ACCENT = QColor(settings.ui_accent_color)
WHITE = QColor("#FFFFFF")
BLACK = QColor("#0A0B10")
DARK_BG = QColor("#11131C")
EYE_BG_TOP = QColor("#1E2235")
EYE_BG_BOTTOM = QColor("#0D0F18")


@dataclass
class _EyeGeometry:
    pupil_x: float = 0.0
    pupil_y: float = 0.0
    openness: float = 1.0        # 0.0 closed, 1.0 wide
    squint_top: float = 0.0      # upper eyelid curve
    squint_bottom: float = 0.0   # lower eyelid curve
    scale_x: float = 1.0
    scale_y: float = 1.0
    tilt: float = 0.0            # angle degrees


class EyeRenderer(QWidget):
    """
    Core vector visual renderer for Troko's upper notch island.
    Operates at 60 FPS using QPainter path vector primitives.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        self._state: TrokoState = TrokoState.REPOSO
        self.anim = AnimationEngine()

        # Eye states
        self._left = _EyeGeometry()
        self._right = _EyeGeometry()

        # Cursor and tracking
        self._cursor_local = QPointF(0.0, 0.0)
        self._target_px = 0.0
        self._target_py = 0.0

        # Blinking
        self._blink_next = time.monotonic() + random.uniform(2.5, 5.0)
        self._blink_start: Optional[float] = None
        self._blink_dur = 0.14

        # Habit & productivity state storage
        self.pomodoro_remaining_sec: int = settings.pomodoro_work_minutes * 60
        self.pomodoro_active: bool = False
        self.water_count: int = 6
        self.water_target: int = settings.daily_water_target
        self.habit_progress: float = 0.5  # 0.0 to 1.0

        # Speaking amplitude oscillation
        self._speak_phase: float = 0.0

        # General frame time
        self._time_elapsed: float = 0.0

        # 60 FPS Timer (~16 ms)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(max(1, int(1000 / settings.ui_fps)))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_state(self, state: TrokoState) -> None:
        self._state = state
        self._apply_state_triggers(state)
        self.update()

    def update_cursor(self, global_pos: QPoint) -> None:
        local = self.mapFromGlobal(global_pos)
        self._cursor_local = QPointF(local.x(), local.y())

    def update_pomodoro_countdown(self, seconds_left: int, active: bool = True) -> None:
        self.pomodoro_remaining_sec = max(0, seconds_left)
        self.pomodoro_active = active
        self.update()

    def set_water_progress(self, current: int, target: int = 8) -> None:
        self.water_count = current
        self.water_target = target
        self.update()

    # ------------------------------------------------------------------
    # State Trigger Side-Effects
    # ------------------------------------------------------------------

    def _apply_state_triggers(self, state: TrokoState) -> None:
        w, h = float(self.width()), float(self.height())
        cx = w / 2.0
        cy = h / 2.0

        # Reset blush by default
        self.anim.set_blush(0.0)

        if state == TrokoState.CONTENTO:
            self.anim.set_blush(0.5)
            self.anim.spawn_stars(cx, cy, count=4)
        elif state == TrokoState.ENAMORADO:
            self.anim.set_blush(0.85)
            self.anim.spawn_hearts(cx, cy, count=6)
        elif state == TrokoState.TIMIDO:
            self.anim.set_blush(1.0)
        elif state == TrokoState.ORGULLOSO:
            self.anim.set_blush(0.4)
            self.anim.spawn_stars(cx, cy, count=3)
        elif state == TrokoState.MAREADO:
            self.anim.spawn_stars(cx, cy * 0.7, count=5)
        elif state in (TrokoState.HABIT_EJERCICIO, TrokoState.ALERTA):
            self.anim.spawn_sweat_drops(cx + 35, cy - 10, count=2)
        elif state == TrokoState.FESTEJO:
            self.anim.set_blush(0.7)
            self.anim.spawn_confetti(w, h, count=45)
            self.anim.spawn_stars(cx, cy, count=8)

    # ------------------------------------------------------------------
    # 60 FPS Loop
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        now = time.monotonic()
        dt = 0.016
        self._time_elapsed += dt

        self.anim.update(dt)
        self._update_blinking(now)
        self._update_pupils()
        self._update_state_animations(dt)
        self.update()

    def _update_blinking(self, now: float) -> None:
        if self._state == TrokoState.SUENO:
            self._left.openness = self._right.openness = 0.02
            w, h = float(self.width()), float(self.height())
            self.anim.spawn_zzz(w * 0.72, h * 0.4)
            return

        if self._blink_start is not None:
            elapsed = now - self._blink_start
            half = self._blink_dur / 2.0
            if elapsed < half:
                o = 1.0 - (elapsed / half)
            elif elapsed < self._blink_dur:
                o = (elapsed - half) / half
            else:
                o = 1.0
                self._blink_start = None
                self._blink_next = now + random.uniform(2.5, 6.0)
            self._left.openness = self._right.openness = max(0.04, o)
        elif now >= self._blink_next:
            self._blink_start = now

    def _update_pupils(self) -> None:
        w, h = float(self.width()), float(self.height())
        if w <= 0 or h <= 0:
            return

        if self._state == TrokoState.SUENO:
            self._target_px = self._target_py = 0.0
        elif self._state == TrokoState.PIENSA:
            # Look up-right pensively
            self._target_px = 0.35
            self._target_py = -0.55
        elif self._state == TrokoState.TIMIDO:
            # Look down shyly
            self._target_px = 0.0
            self._target_py = 0.6
        else:
            # Cursor follow
            cx = self._cursor_local.x()
            cy = self._cursor_local.y()
            self._target_px = max(-1.0, min(1.0, (cx - w / 2.0) / (w / 2.0))) * 0.38
            self._target_py = max(-1.0, min(1.0, (cy - h / 2.0) / (h / 2.0))) * 0.38

        alpha = 0.12
        self._left.pupil_x += (self._target_px - self._left.pupil_x) * alpha
        self._left.pupil_y += (self._target_py - self._left.pupil_y) * alpha
        self._right.pupil_x += (self._target_px - self._right.pupil_x) * alpha
        self._right.pupil_y += (self._target_py - self._right.pupil_y) * alpha

    def _update_state_animations(self, dt: float) -> None:
        if self._state == TrokoState.HABLA:
            self._speak_phase += dt * 14.0

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = float(self.width()), float(self.height())

        # 1. Base Notch Island Body
        self._draw_island_body(painter, w, h)

        # 2. Check if a dedicated habit scene is active
        if self._is_habit_scene_active():
            self._draw_habit_scene(painter, w, h)
        else:
            # 3. Standard / Emotion Eye Rendering
            self._draw_eyes_and_face(painter, w, h)

        # 4. Overlays & Particles (blush, hearts, stars, sweat, confetti)
        self.anim.render_particles(painter)

        # 5. Operational Status Badges (check verde "Listo", timer text, etc.)
        self.anim.render_feedback_badge(painter, QRectF(0, 0, w, h))

        painter.end()

    # ------------------------------------------------------------------
    # Island Body Background
    # ------------------------------------------------------------------

    def _draw_island_body(self, painter: QPainter, w: float, h: float) -> None:
        body_path = QPainterPath()
        r = min(h / 2.0, 36.0)
        body_path.addRoundedRect(QRectF(2, 2, w - 4, h - 4), r, r)

        # Background Gradient
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor("#121420"))
        grad.setColorAt(1.0, QColor("#08090E"))
        painter.fillPath(body_path, grad)

        # Ambient Glow / Border
        border_col = QColor(ACCENT)
        border_w = 1.4

        if self._state == TrokoState.ALERTA:
            # Pulsing red
            pulse = (math.sin(self._time_elapsed * 8.0) + 1.0) / 2.0
            border_col = QColor(255, 60, 60, int(150 + 105 * pulse))
            border_w = 2.2
        elif self._state == TrokoState.ESCUCHA:
            # Pulsing cyan
            pulse = (math.sin(self._time_elapsed * 6.0) + 1.0) / 2.0
            border_col = QColor(0, 220, 255, int(140 + 115 * pulse))
            border_w = 2.0
        else:
            border_col.setAlpha(110)

        painter.setPen(QPen(border_col, border_w))
        painter.drawPath(body_path)

    # ------------------------------------------------------------------
    # Eyes & 12 Emotions
    # ------------------------------------------------------------------

    def _draw_eyes_and_face(self, painter: QPainter, w: float, h: float) -> None:
        cy = h / 2.0
        spacing = w * 0.26
        lx = w / 2.0 - spacing
        rx = w / 2.0 + spacing

        # Blush overlay on cheeks
        self.anim.render_blush(painter, lx, rx, cy + h * 0.28, w=28, h=14)

        # Left & Right Eyes
        self._draw_single_eye(painter, lx, cy, is_left=True)
        self._draw_single_eye(painter, rx, cy, is_left=False)

        # Mouth or Voice waveform if speaking / yawning
        self._draw_mouth_details(painter, w / 2.0, cy + h * 0.24)

    def _draw_single_eye(self, painter: QPainter, cx: float, cy: float, is_left: bool) -> None:
        eye = self._left if is_left else self._right
        base_ew = 48.0
        base_eh = 48.0

        # Emotion-specific Geometry Overrides
        ew = base_ew
        eh = base_eh * eye.openness

        state = self._state

        # 1. CONTENTO (Happy squint curve)
        if state in (TrokoState.CONTENTO, TrokoState.FESTEJO):
            self._draw_happy_arc_eye(painter, cx, cy, ew, base_eh, is_left)
            return

        # 2. GUINO (Wink: one eye closed, one open with spark)
        if state == TrokoState.GUINO:
            if is_left:
                self._draw_happy_arc_eye(painter, cx, cy, ew, base_eh, is_left)
                return
            else:
                ew *= 1.15
                eh *= 1.15

        # 3. ENAMORADO (Heart eyes)
        if state == TrokoState.ENAMORADO:
            self._draw_heart_eye(painter, cx, cy, ew * 0.9)
            return

        # 4. MAREADO (Spiral eyes)
        if state == TrokoState.MAREADO:
            self._draw_dizzy_spiral_eye(painter, cx, cy, ew * 0.85)
            return

        # 5. BOSTEZO (Yawn teardrop eyes)
        if state == TrokoState.BOSTEZO:
            eh = base_eh * 0.35

        # 6. SORPRESA (Surprise wide circle)
        elif state == TrokoState.SORPRESA:
            ew *= 1.2
            eh = ew

        # 7. ENFADADO (Angry slanted eyes)
        elif state == TrokoState.ENFADADO:
            self._draw_angry_eye(painter, cx, cy, ew, base_eh, is_left)
            return

        # 8. TRISTE (Sad droopy eyes)
        elif state == TrokoState.TRISTE:
            self._draw_sad_eye(painter, cx, cy, ew, base_eh, is_left)
            return

        # 9. CURIOSO (One bigger than other)
        elif state == TrokoState.CURIOSO:
            if is_left:
                ew *= 1.2
                eh *= 1.2
            else:
                ew *= 0.85
                eh *= 0.85

        # Standard Oval Eye Base
        rect = QRectF(cx - ew / 2.0, cy - eh / 2.0, ew, eh)
        path = QPainterPath()
        path.addEllipse(rect)

        # Eye socket background
        grad = QRadialGradient(rect.center(), ew / 2.0)
        grad.setColorAt(0.0, EYE_BG_TOP)
        grad.setColorAt(1.0, EYE_BG_BOTTOM)
        painter.fillPath(path, grad)

        # Pupil
        if eye.openness > 0.15:
            pr = ew * 0.42
            px = rect.center().x() + eye.pupil_x * (ew * 0.28)
            py = rect.center().y() + eye.pupil_y * (eh * 0.28)

            pupil_rect = QRectF(px - pr / 2.0, py - pr / 2.0, pr, pr)
            painter.setBrush(ACCENT)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(pupil_rect)

            # Specular sparkle
            sp_r = pr * 0.32
            sp_rect = QRectF(pupil_rect.left() + pr * 0.22, pupil_rect.top() + pr * 0.16, sp_r, sp_r)
            painter.setBrush(WHITE)
            painter.drawEllipse(sp_rect)

        # Outline
        painter.setPen(QPen(ACCENT, 1.2))
        painter.drawPath(path)

    def _draw_happy_arc_eye(self, painter: QPainter, cx: float, cy: float, w: float, h: float, is_left: bool) -> None:
        path = QPainterPath()
        hw = w * 0.45
        path.moveTo(cx - hw, cy + 4)
        path.quadTo(cx, cy - h * 0.42, cx + hw, cy + 4)
        painter.setPen(QPen(ACCENT, 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)

    def _draw_heart_eye(self, painter: QPainter, cx: float, cy: float, size: float) -> None:
        pulse = 1.0 + 0.12 * math.sin(self._time_elapsed * 8.0)
        s = (size / 2.0) * pulse
        path = QPainterPath()
        path.moveTo(cx, cy + s * 0.35)
        path.cubicTo(cx - s, cy - s * 0.6, cx - s * 1.2, cy + s * 0.4, cx, cy + s * 1.3)
        path.cubicTo(cx + s * 1.2, cy + s * 0.4, cx + s, cy - s * 0.6, cx, cy + s * 0.35)
        painter.setBrush(QColor("#FF4081"))
        painter.setPen(QPen(WHITE, 1.2))
        painter.drawPath(path)

    def _draw_dizzy_spiral_eye(self, painter: QPainter, cx: float, cy: float, radius: float) -> None:
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._time_elapsed * 320.0)
        path = QPainterPath()
        path.moveTo(0, 0)
        steps = 45
        for i in range(steps):
            angle = i * 0.35
            r = (radius / steps) * i
            path.lineTo(r * math.cos(angle), r * math.sin(angle))
        painter.setPen(QPen(QColor("#FFD600"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)
        painter.restore()

    def _draw_angry_eye(self, painter: QPainter, cx: float, cy: float, w: float, h: float, is_left: bool) -> None:
        rect = QRectF(cx - w / 2.0, cy - h / 2.0, w, h * 0.85)
        path = QPainterPath()
        # Slant down towards centre
        tilt = -14 if is_left else 14
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(tilt)
        path.addEllipse(-w / 2.0, -h * 0.4, w, h * 0.8)
        painter.setBrush(QColor("#24141E"))
        painter.setPen(QPen(QColor("#FF5252"), 2.0))
        painter.drawPath(path)
        # Small intense pupil
        painter.setBrush(QColor("#FF1744"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(-8, -6, 16, 16))
        painter.restore()

    def _draw_sad_eye(self, painter: QPainter, cx: float, cy: float, w: float, h: float, is_left: bool) -> None:
        path = QPainterPath()
        hw = w * 0.45
        path.moveTo(cx - hw, cy - 2)
        path.quadTo(cx, cy + h * 0.38, cx + hw, cy - 2)
        painter.setPen(QPen(QColor("#80D8FF"), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)

    def _draw_mouth_details(self, painter: QPainter, cx: float, cy: float) -> None:
        if self._state == TrokoState.HABLA:
            # Animated waveform mouth
            amp = 6.0 + 4.0 * math.sin(self._speak_phase)
            path = QPainterPath()
            path.moveTo(cx - 16, cy)
            path.quadTo(cx, cy + amp, cx + 16, cy)
            painter.setPen(QPen(ACCENT, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(path)
        elif self._state == TrokoState.BOSTEZO:
            # Open yawn mouth
            painter.setBrush(QColor("#1A1224"))
            painter.setPen(QPen(ACCENT, 1.5))
            painter.drawEllipse(QRectF(cx - 8, cy - 2, 16, 18))

    # ------------------------------------------------------------------
    # 15 Animated Procedural Habit Scenes
    # ------------------------------------------------------------------

    def _is_habit_scene_active(self) -> bool:
        return "habit" in str(self._state) or self._state in (
            TrokoState.HABIT_POMODORO,
            TrokoState.HABIT_AGUA,
            TrokoState.HABIT_LECTURA,
            TrokoState.HABIT_EJERCICIO,
            TrokoState.HABIT_MEDITACION,
            TrokoState.HABIT_CAMINAR,
            TrokoState.HABIT_ESTUDIO,
            TrokoState.HABIT_DORMIR,
            TrokoState.HABIT_COMIDA,
            TrokoState.HABIT_POSTURA,
            TrokoState.HABIT_PAUSA_VISUAL,
            TrokoState.HABIT_AGRADECIMIENTO,
            TrokoState.HABIT_RESPIRACION,
            TrokoState.HABIT_LIMPIEZA,
            TrokoState.HABIT_DESCONEXION,
        )

    def _draw_habit_scene(self, painter: QPainter, w: float, h: float) -> None:
        st = self._state
        cx = w / 2.0
        cy = h / 2.0

        if st == TrokoState.HABIT_POMODORO:
            self._scene_pomodoro_typing(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_AGUA:
            self._scene_water_glass(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_LECTURA:
            self._scene_reading_book(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_EJERCICIO:
            self._scene_workout_weights(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_MEDITACION:
            self._scene_meditation_sun(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_CAMINAR:
            self._scene_walking_steps(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_ESTUDIO:
            self._scene_study_lightbulb(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_DORMIR:
            self._scene_sleep_moon(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_COMIDA:
            self._scene_healthy_apple(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_POSTURA:
            self._scene_posture_stretch(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_PAUSA_VISUAL:
            self._scene_visual_pause_2020(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_AGRADECIMIENTO:
            self._scene_gratitude_journal(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_RESPIRACION:
            self._scene_breath_guide(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_LIMPIEZA:
            self._scene_cleaning_sparkle(painter, cx, cy, w, h)
        elif st == TrokoState.HABIT_DESCONEXION:
            self._scene_digital_zen(painter, cx, cy, w, h)

    # 1. POMODORO (Laptop Typing + Visible Countdown)
    def _scene_pomodoro_typing(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        # Left side: Troko head & mini laptop
        troko_cx = cx - 65
        self._draw_single_eye(painter, troko_cx - 14, cy - 8, is_left=True)
        self._draw_single_eye(painter, troko_cx + 14, cy - 8, is_left=False)

        # Laptop body
        lp_y = cy + 18
        painter.setBrush(QColor("#3A3F58"))
        painter.setPen(QPen(ACCENT, 1.2))
        painter.drawRoundedRect(QRectF(troko_cx - 24, lp_y, 48, 6), 2, 2)
        # Screen glow
        painter.setBrush(QColor("#80D8FF"))
        painter.drawRect(QRectF(troko_cx - 18, lp_y - 14, 36, 14))

        # Typing hands animation
        hand_offset = 3.0 * math.sin(self._time_elapsed * 18.0)
        painter.setBrush(ACCENT)
        painter.drawEllipse(QRectF(troko_cx - 14, lp_y - 2 + hand_offset, 6, 6))
        painter.drawEllipse(QRectF(troko_cx + 8, lp_y - 2 - hand_offset, 6, 6))

        # Right side: Countdown clock
        mins = self.pomodoro_remaining_sec // 60
        secs = self.pomodoro_remaining_sec % 60
        time_str = f"{mins:02d}:{secs:02d}"

        font = painter.font()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 20, 130, 26), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"🍅 {time_str}")

        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#AAAAAA"))
        painter.drawText(QRectF(cx + 14, cy + 6, 120, 18), "Enfoque activo")

    # 2. AGUA (Water Glass 6/8 with Liquid)
    def _scene_water_glass(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        glass_cx = cx - 50
        gw, gh = 28.0, 42.0

        # Glass outline
        glass_rect = QRectF(glass_cx - gw / 2, cy - gh / 2, gw, gh)
        painter.setPen(QPen(QColor("#80D8FF"), 1.8))
        painter.setBrush(QColor(20, 30, 45, 120))
        painter.drawRoundedRect(glass_rect, 4, 4)

        # Liquid level based on water_count / water_target
        frac = min(1.0, max(0.1, self.water_count / float(self.water_target)))
        liq_h = gh * frac
        liq_rect = QRectF(glass_rect.left() + 2, glass_rect.bottom() - liq_h, gw - 4, liq_h - 2)

        liq_grad = QLinearGradient(0, liq_rect.top(), 0, liq_rect.bottom())
        liq_grad.setColorAt(0.0, QColor("#00E5FF"))
        liq_grad.setColorAt(1.0, QColor("#0091EA"))
        painter.fillPath(self._rounded_bottom_path(liq_rect, 3), liq_grad)

        # Text: 6/8 vasos
        font = painter.font()
        font.setPointSize(13)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 5, cy - 18, 140, 22), f"💧 {self.water_count}/{self.water_target} vasos")

        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#00E5FF"))
        painter.drawText(QRectF(cx + 10, cy + 6, 130, 18), "¡Excelente hidratación!")

    # 3. LECTURA (Turning Book Pages)
    def _scene_reading_book(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        bx = cx - 40
        page_curl = math.sin(self._time_elapsed * 5.0) * 8.0

        painter.setPen(QPen(QColor("#D7CCC8"), 1.5))
        painter.setBrush(QColor("#FFF9C4"))
        # Left page
        painter.drawRoundedRect(QRectF(bx - 26, cy - 14, 24, 28), 2, 2)
        # Right page turning
        painter.drawRoundedRect(QRectF(bx + 2, cy - 14 + page_curl, 24, 28), 2, 2)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 15, cy - 14, 130, 28), "📖 Leyendo...")

    # 4. EJERCICIO (Lifting Weights)
    def _scene_workout_weights(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        lift = math.sin(self._time_elapsed * 6.0) * 8.0
        bx = cx - 50

        # Troko eye effort
        self._draw_happy_arc_eye(painter, bx - 12, cy - lift - 2, 24, 18, True)
        self._draw_happy_arc_eye(painter, bx + 12, cy - lift - 2, 24, 18, False)

        # Dumbbell
        painter.setPen(QPen(QColor("#9E9E9E"), 3.0))
        painter.drawLine(int(bx - 28), int(cy - lift), int(bx + 28), int(cy - lift))
        painter.setBrush(QColor("#424242"))
        painter.drawRoundedRect(QRectF(bx - 32, cy - lift - 8, 8, 16), 2, 2)
        painter.drawRoundedRect(QRectF(bx + 24, cy - lift - 8, 8, 16), 2, 2)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 14, 140, 28), "💪 ¡Entrenando!")

    # 5. MEDITACION (Breathing Zen Sun)
    def _scene_meditation_sun(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        breath = (math.sin(self._time_elapsed * 1.5) + 1.0) / 2.0  # 4s cycle
        sun_r = 16.0 + 10.0 * breath
        bx = cx - 45

        # Zen Aura
        grad = QRadialGradient(bx, cy, sun_r * 1.5)
        grad.setColorAt(0.0, QColor(255, 214, 0, int(180 * breath + 40)))
        grad.setColorAt(1.0, QColor(255, 171, 0, 0))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(bx - sun_r * 1.5, cy - sun_r * 1.5, sun_r * 3, sun_r * 3))

        # Peaceful Eyes
        self._draw_happy_arc_eye(painter, bx - 10, cy, 20, 12, True)
        self._draw_happy_arc_eye(painter, bx + 10, cy, 20, 12, False)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        phase_txt = "Inhala..." if breath > 0.5 else "Exhala..."
        painter.drawText(QRectF(cx + 15, cy - 14, 140, 28), f"🧘 {phase_txt}")

    # 6. CAMINAR
    def _scene_walking_steps(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        step_phase = self._time_elapsed * 8.0
        bx = cx - 45
        s1 = math.sin(step_phase) * 6.0
        s2 = -s1

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#00E676"))
        painter.drawEllipse(QRectF(bx - 14, cy + s1, 10, 6))
        painter.drawEllipse(QRectF(bx + 4, cy + s2, 10, 6))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 14, 140, 28), "🚶 Caminando...")

    # 7. ESTUDIO
    def _scene_study_lightbulb(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        bx = cx - 45
        glow = (math.sin(self._time_elapsed * 5.0) + 1.0) / 2.0

        painter.setBrush(QColor(255, 235, 59, int(150 + 105 * glow)))
        painter.setPen(QPen(QColor("#FBC02D"), 1.5))
        painter.drawEllipse(QRectF(bx - 12, cy - 14, 24, 22))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 14, 140, 28), "💡 ¡Estudiando!")

    # 8. DORMIR TEMPRANO
    def _scene_sleep_moon(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        bx = cx - 45
        painter.setBrush(QColor("#FFF59D"))
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.addEllipse(QRectF(bx - 14, cy - 14, 28, 28))
        path2 = QPainterPath()
        path2.addEllipse(QRectF(bx - 6, cy - 18, 26, 26))
        crescent = path.subtracted(path2)
        painter.drawPath(crescent)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 14, 140, 28), "🌙 Hora de dormir")

    # 9. COMIDA SALUDABLE
    def _scene_healthy_apple(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        bx = cx - 45
        painter.setBrush(QColor("#E53935"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(bx - 12, cy - 10, 24, 22))
        # Leaf
        painter.setBrush(QColor("#43A047"))
        painter.drawEllipse(QRectF(bx, cy - 18, 8, 6))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 14, 140, 28), "🍎 Nutrición sana")

    # 10. POSTURA
    def _scene_posture_stretch(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        bx = cx - 45
        painter.setPen(QPen(QColor("#00E5FF"), 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(int(bx), int(cy - 16), int(bx), int(cy + 16))
        painter.drawEllipse(QRectF(bx - 6, cy - 24, 12, 12))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 14, 140, 28), "🧍 Postura recta")

    # 11. PAUSA VISUAL (20-20-20)
    def _scene_visual_pause_2020(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        bx = cx - 45
        self._draw_happy_arc_eye(painter, bx - 10, cy, 20, 12, True)
        self._draw_happy_arc_eye(painter, bx + 10, cy, 20, 12, False)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 14, 140, 28), "👀 Pausa 20-20-20")

    # 12. AGRADECIMIENTO
    def _scene_gratitude_journal(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        bx = cx - 45
        painter.setBrush(QColor("#FFCC80"))
        painter.setPen(QPen(QColor("#E65100"), 1.2))
        painter.drawRoundedRect(QRectF(bx - 12, cy - 14, 24, 28), 2, 2)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 14, 140, 28), "📝 Diario y gratitud")

    # 13. RESPIRACION 4-4-4
    def _scene_breath_guide(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        bx = cx - 45
        r = 10.0 + 8.0 * ((math.sin(self._time_elapsed * 1.8) + 1.0) / 2.0)
        painter.setBrush(QColor(127, 90, 240, 160))
        painter.setPen(QPen(ACCENT, 2.0))
        painter.drawEllipse(QRectF(bx - r, cy - r, r * 2, r * 2))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 14, 140, 28), "🌬️ Respira 4-4-4")

    # 14. LIMPIEZA Y ORDEN
    def _scene_cleaning_sparkle(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        bx = cx - 45
        painter.setPen(QPen(QColor("#FFD600"), 2.0))
        painter.drawLine(int(bx - 10), int(cy + 10), int(bx + 10), int(cy - 10))

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 14, 140, 28), "✨ Orden y ordenado")

    # 15. DESCONEXION DIGITAL
    def _scene_digital_zen(self, painter: QPainter, cx: float, cy: float, w: float, h: float) -> None:
        bx = cx - 45
        painter.setBrush(QColor("#2E7D32"))
        painter.setPen(Qt.PenStyle.NoPen)
        # Leaf shape
        path = QPainterPath()
        path.moveTo(bx, cy - 14)
        path.quadTo(bx + 14, cy, bx, cy + 14)
        path.quadTo(bx - 14, cy, bx, cy - 14)
        painter.drawPath(path)

        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(WHITE)
        painter.drawText(QRectF(cx + 10, cy - 14, 140, 28), "🌿 Desconexión zen")

    def _rounded_bottom_path(self, rect: QRectF, radius: float) -> QPainterPath:
        p = QPainterPath()
        p.moveTo(rect.topLeft())
        p.lineTo(rect.topRight())
        p.lineTo(rect.right(), rect.bottom() - radius)
        p.quadTo(rect.bottomRight(), QPointF(rect.right() - radius, rect.bottom()))
        p.lineTo(rect.left() + radius, rect.bottom())
        p.quadTo(rect.bottomLeft(), QPointF(rect.left(), rect.bottom() - radius))
        p.closeSubpath()
        return p
