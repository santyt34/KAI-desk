"""
src/ui/eye_renderer.py
======================
60 FPS Procedural Eye, Emotion, and Habit Scene Renderer for KAI.
Features:
- KAI Visual Identity: Floating dark notch capsule (#0C0E17 to #121524) with
  subtle lilac/purple border glow (#7F5AF0) and two expressive circular white eyes.
- 12 Parametric Emotions:
    1. Contento (joyful curved arcs + blush + sparkling stars)
    2. Enamorado (pulsing heart eyes + floating hearts + blush)
    3. Sorpresa (wide luminous circular eyes + specular highlights)
    4. Orgulloso (confident curved eyes + raised brows + soft sparkle)
    5. Guiño (asymmetric wink: one happy arc + one bright open eye)
    6. Bostezo (droopy sleepy squint + open yawning mouth + drifting Zzz)
    7. Molesto (furrowed angled eyebrows + narrowed eyes + subtle warm glow)
    8. Escucha (attentive circular eyes + cyan/lilac audio pulse ring)
    9. Mareado (spinning hypnotic spirals + orbiting stars)
    10. Festejo (dancing joyful arcs + confetti burst + blush)
    11. Saludo (friendly greeting eyes + animated waving hand vector)
    12. Ánimo (radiant determined eyes + starburst energy rays)
- 7 Operational Island States:
    reposo, escucha, piensa, habla, alerta, notificacion, sueno.
- Integrated SceneGenerator for 15 habit scenes + live Pomodoro timer.
- Natural smooth blinking, cursor tracking (QCursor.pos), hover reaction.
"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

from config.settings import settings
from core.state_machine import TrokoState
from ui.animation_engine import AnimationEngine
from ui.scene_generator import SceneGenerator

logger = logging.getLogger(__name__)

# Colors & KAI Identity
ACCENT_LILAC = QColor("#7F5AF0")
ACCENT_LILAC_LIGHT = QColor("#A882FF")
WHITE = QColor("#FFFFFF")
BLACK = QColor("#0A0B10")
CAPSULE_TOP = QColor("#121524")
CAPSULE_BOTTOM = QColor("#0C0E17")
EYE_SOCKET_BG = QColor("#181B2D")


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
    60 FPS procedural vector renderer for KAI's floating upper notch island.
    Draws directly via QPainter vector paths without missing raster assets.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        self._state: TrokoState = TrokoState.REPOSO
        self.anim = AnimationEngine()
        self.scene_gen = SceneGenerator()

        # Eye geometries
        self._left = _EyeGeometry()
        self._right = _EyeGeometry()

        # Cursor and tracking
        self._cursor_local = QPointF(0.0, 0.0)
        self._target_px = 0.0
        self._target_py = 0.0
        self._is_hovered: bool = False

        # Blinking logic
        self._blink_next = time.monotonic() + random.uniform(2.5, 5.0)
        self._blink_start: Optional[float] = None
        self._blink_dur = 0.14
        self._async_blink_offset: float = 0.0

        # Habit & productivity state storage
        self.pomodoro_remaining_sec: int = settings.pomodoro_work_minutes * 60
        self.pomodoro_active: bool = False
        self.water_count: int = 6
        self.water_target: int = settings.daily_water_target
        self.habit_progress: float = 0.5

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

    def set_hover(self, hovered: bool) -> None:
        self._is_hovered = hovered
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
        w, h = float(self.width() or 280), float(self.height() or 52)
        cx = w / 2.0
        cy = h / 2.0

        # Reset blush by default
        self.anim.set_blush(0.0)

        st_val = str(state.value if hasattr(state, "value") else state).lower()

        if st_val == "contento":
            self.anim.set_blush(0.55)
            self.anim.spawn_stars(cx, cy, count=4)
        elif st_val == "enamorado":
            self.anim.set_blush(0.85)
            self.anim.spawn_hearts(cx, cy, count=6)
        elif st_val == "orgulloso":
            self.anim.set_blush(0.4)
            self.anim.spawn_stars(cx, cy - 8, count=3)
        elif st_val == "mareado":
            self.anim.spawn_stars(cx, cy * 0.6, count=6)
        elif st_val in ("ejercicio", "alerta", "habit_ejercicio"):
            self.anim.spawn_sweat_drops(cx + 38, cy - 10, count=2)
        elif st_val == "festejo":
            self.anim.set_blush(0.7)
            self.anim.spawn_confetti(w, h, count=50)
            self.anim.spawn_stars(cx, cy, count=8)
        elif st_val == "animo":
            self.anim.spawn_sparks(cx, cy, count=10)
        elif st_val == "saludo":
            self.anim.spawn_stars(cx + 45, cy - 10, count=3)

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
        st_val = str(self._state.value if hasattr(self._state, "value") else self._state).lower()
        if st_val == "sueno":
            self._left.openness = self._right.openness = 0.02
            w, h = float(self.width() or 280), float(self.height() or 52)
            if random.random() < 0.04:
                self.anim.spawn_zzz(w * 0.72, h * 0.38)
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
                # Introduce occasional micro asynchronous blink
                self._async_blink_offset = random.choice([0.0, 0.0, 0.02, -0.02])
            o = max(0.04, o)
            self._left.openness = max(0.04, min(1.0, o + self._async_blink_offset))
            self._right.openness = max(0.04, min(1.0, o - self._async_blink_offset))
        elif now >= self._blink_next:
            self._blink_start = now

    def _update_pupils(self) -> None:
        w, h = float(self.width() or 280), float(self.height() or 52)
        if w <= 0 or h <= 0:
            return

        st_val = str(self._state.value if hasattr(self._state, "value") else self._state).lower()

        if st_val == "sueno":
            self._target_px = self._target_py = 0.0
        elif st_val == "piensa":
            # Glances upward and slightly to the right
            self._target_px = 0.35
            self._target_py = -0.55
        elif st_val == "orgulloso":
            self._target_px = 0.1
            self._target_py = -0.15
        elif st_val == "molesto":
            self._target_px = 0.0
            self._target_py = 0.1
        else:
            # Smooth cursor following with dampening
            cx = self._cursor_local.x()
            cy = self._cursor_local.y()
            self._target_px = max(-1.0, min(1.0, (cx - w / 2.0) / (w / 2.0))) * 0.42
            self._target_py = max(-1.0, min(1.0, (cy - h / 2.0) / (h / 2.0))) * 0.42

        alpha = 0.14
        self._left.pupil_x += (self._target_px - self._left.pupil_x) * alpha
        self._left.pupil_y += (self._target_py - self._left.pupil_y) * alpha
        self._right.pupil_x += (self._target_px - self._right.pupil_x) * alpha
        self._right.pupil_y += (self._target_py - self._right.pupil_y) * alpha

    def _update_state_animations(self, dt: float) -> None:
        st_val = str(self._state.value if hasattr(self._state, "value") else self._state).lower()
        if st_val in ("habla", "speaking"):
            self._speak_phase += dt * 14.0

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = float(self.width()), float(self.height())

        # 1. Base KAI Notch Capsule (Dark gradient + subtle lilac border)
        self._draw_capsule_body(painter, w, h)

        # 2. Render Habit Scene if in Habit State, or 12 Emotions/Eyes
        if self._is_habit_scene_active():
            self._draw_habit_scene(painter, w, h)
        else:
            self._draw_kai_eyes_and_face(painter, w, h)

        # 3. Dynamic Overlays & Particles (blush, hearts, stars, sweat, confetti, zzz)
        self.anim.render_particles(painter)

        # 4. Feedback badge (green check + feedback text)
        self.anim.render_feedback_badge(painter, QRectF(0, 0, w, h))

        painter.end()

    # ------------------------------------------------------------------
    # Capsule Body
    # ------------------------------------------------------------------

    def _draw_capsule_body(self, painter: QPainter, w: float, h: float) -> None:
        r = min(h / 2.0, 36.0)
        capsule_path = QPainterPath()
        capsule_path.addRoundedRect(QRectF(2, 2, w - 4, h - 4), r, r)

        # Dark background gradient: #121524 to #0C0E17
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, CAPSULE_TOP)
        grad.setColorAt(1.0, CAPSULE_BOTTOM)
        painter.fillPath(capsule_path, grad)

        # Subtle lilac/purple border (#7F5AF0) with dynamic operational states
        border_col = QColor(ACCENT_LILAC)
        border_w = 1.3

        st_val = str(self._state.value if hasattr(self._state, "value") else self._state).lower()

        if st_val == "alerta":
            pulse = (math.sin(self._time_elapsed * 8.0) + 1.0) / 2.0
            border_col = QColor(255, 60, 60, int(150 + 105 * pulse))
            border_w = 2.0
        elif st_val == "escucha":
            pulse = (math.sin(self._time_elapsed * 6.0) + 1.0) / 2.0
            border_col = QColor(0, 229, 255, int(140 + 115 * pulse))
            border_w = 1.8
        elif self._is_hovered:
            border_col = QColor(ACCENT_LILAC_LIGHT)
            border_col.setAlpha(220)
            border_w = 1.6
        else:
            border_col.setAlpha(125)

        painter.setPen(QPen(border_col, border_w))
        painter.drawPath(capsule_path)

        # Additional operational state subtle top glow ring
        if st_val == "escucha":
            wave_r = (math.sin(self._time_elapsed * 5.0) + 1.0) / 2.0
            glow_col = QColor(0, 229, 255, int(35 * wave_r))
            painter.setBrush(glow_col)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(4, 4, w - 8, h - 8), r - 2, r - 2)

    # ------------------------------------------------------------------
    # KAI Eyes & 12 Emotions
    # ------------------------------------------------------------------

    def _draw_kai_eyes_and_face(self, painter: QPainter, w: float, h: float) -> None:
        cy = h / 2.0
        spacing = w * 0.22
        lx = w / 2.0 - spacing
        rx = w / 2.0 + spacing

        # Cheek blush
        self.anim.render_blush(painter, lx, rx, cy + h * 0.28, w=26, h=12)

        # Draw left and right eyes
        self._draw_kai_eye(painter, lx, cy, is_left=True)
        self._draw_kai_eye(painter, rx, cy, is_left=False)

        # Operational details (thinking dots, speaking waves, yawn, notification bell)
        self._draw_operational_overlays(painter, w, h, cy)

    def _draw_kai_eye(self, painter: QPainter, cx: float, cy: float, is_left: bool) -> None:
        eye = self._left if is_left else self._right
        base_size = 38.0

        if self._is_hovered:
            base_size *= 1.08  # Curious dilation on hover

        st_val = str(self._state.value if hasattr(self._state, "value") else self._state).lower()

        # --- 12 EMOTIONS ---

        # 1. CONTENTO & FESTEJO (Happy curved arcs)
        if st_val in ("contento", "festejo"):
            self._draw_happy_arc(painter, cx, cy, base_size)
            return

        # 2. ENAMORADO (Heart eyes)
        if st_val == "enamorado":
            self._draw_heart_eye(painter, cx, cy, base_size)
            return

        # 3. SORPRESA (Wide round luminous eyes)
        if st_val == "sorpresa":
            self._draw_circular_white_eye(painter, cx, cy, base_size * 1.25, eye, dilated=True)
            return

        # 4. ORGULLOSO (Confident squint + eyebrow)
        if st_val == "orgulloso":
            self._draw_proud_eye(painter, cx, cy, base_size, is_left)
            return

        # 5. GUIÑO (Wink: left eye winks arc, right eye bright open)
        if st_val in ("guino", "guiño"):
            if is_left:
                self._draw_happy_arc(painter, cx, cy, base_size)
                # Outer twinkle star
                painter.setPen(QPen(QColor("#FFD600"), 1.8))
                painter.drawLine(int(cx - base_size * 0.55), int(cy - 4), int(cx - base_size * 0.55), int(cy + 4))
                painter.drawLine(int(cx - base_size * 0.55 - 4), int(cy), int(cx - base_size * 0.55 + 4), int(cy))
            else:
                self._draw_circular_white_eye(painter, cx, cy, base_size * 1.1, eye)
            return

        # 6. BOSTEZO (Sleepy squint)
        if st_val == "bostezo":
            self._draw_sleepy_squint(painter, cx, cy, base_size)
            return

        # 7. MOLESTO (Furrowed angled eyebrows + narrowed eyes)
        if st_val == "molesto":
            self._draw_annoyed_eye(painter, cx, cy, base_size, is_left)
            return

        # 8. ESCUCHA (Attentive circular eye + cyan pupil sparkle)
        if st_val in ("escucha", "escucha_activa"):
            self._draw_circular_white_eye(painter, cx, cy, base_size, eye, cyan_tint=True)
            return

        # 9. MAREADO (Spinning hypnotic spiral)
        if st_val == "mareado":
            self._draw_dizzy_spiral(painter, cx, cy, base_size * 0.85)
            return

        # 10. SALUDO (Friendly bright eye with tilt)
        if st_val == "saludo":
            self._draw_circular_white_eye(painter, cx, cy, base_size, eye)
            if not is_left:
                self._draw_waving_hand_icon(painter, cx + 32, cy - 6)
            return

        # 11. ÁNIMO (Radiant determined eyes with starburst spark)
        if st_val in ("animo", "ánimo"):
            self._draw_circular_white_eye(painter, cx, cy, base_size * 1.15, eye, energetic=True)
            return

        # 12. SUEÑO (Closed calm arcs)
        if st_val == "sueno":
            self._draw_sleep_arc(painter, cx, cy, base_size)
            return

        # Default / Reposo / Piensa / Alerta: Circular White Eye
        h_scale = eye.openness
        self._draw_circular_white_eye(painter, cx, cy, base_size, eye, height_scale=h_scale)

    def _draw_circular_white_eye(
        self,
        painter: QPainter,
        cx: float,
        cy: float,
        size: float,
        eye: _EyeGeometry,
        dilated: bool = False,
        cyan_tint: bool = False,
        energetic: bool = False,
        height_scale: float = 1.0,
    ) -> None:
        """
        KAI's core eye: Pure circular white base with subtle inner depth
        and natural pupil/specular cursor follow.
        """
        ew = size
        eh = size * max(0.08, height_scale)

        rect = QRectF(cx - ew / 2.0, cy - eh / 2.0, ew, eh)
        path = QPainterPath()
        path.addEllipse(rect)

        # Pure white circular body with subtle lilac glow
        painter.setBrush(WHITE)
        painter.setPen(QPen(ACCENT_LILAC, 1.2))
        painter.drawPath(path)

        # Only draw pupil & specular if eye is open enough
        if eye.openness > 0.2:
            pr = ew * (0.34 if dilated else 0.28)
            px = rect.center().x() + eye.pupil_x * (ew * 0.25)
            py = rect.center().y() + eye.pupil_y * (eh * 0.25)

            pupil_rect = QRectF(px - pr / 2.0, py - pr / 2.0, pr, pr)

            pupil_color = QColor("#00E5FF") if cyan_tint else (QColor("#7F5AF0") if energetic else BLACK)
            painter.setBrush(pupil_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(pupil_rect)

            # Specular sparkle highlight
            sp_r = pr * 0.38
            sp_rect = QRectF(pupil_rect.left() + pr * 0.2, pupil_rect.top() + pr * 0.15, sp_r, sp_r)
            painter.setBrush(WHITE)
            painter.drawEllipse(sp_rect)

            # Secondary micro sparkle
            if energetic or dilated:
                sp2_r = pr * 0.22
                sp2_rect = QRectF(pupil_rect.right() - pr * 0.35, pupil_rect.bottom() - pr * 0.35, sp2_r, sp2_r)
                painter.drawEllipse(sp2_rect)

    def _draw_happy_arc(self, painter: QPainter, cx: float, cy: float, size: float) -> None:
        path = QPainterPath()
        hw = size * 0.44
        path.moveTo(cx - hw, cy + 3)
        path.quadTo(cx, cy - size * 0.38, cx + hw, cy + 3)
        painter.setPen(QPen(WHITE, 3.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)

    def _draw_heart_eye(self, painter: QPainter, cx: float, cy: float, size: float) -> None:
        pulse = 1.0 + 0.12 * math.sin(self._time_elapsed * 8.0)
        s = (size / 2.2) * pulse
        path = QPainterPath()
        path.moveTo(cx, cy + s * 0.35)
        path.cubicTo(cx - s, cy - s * 0.6, cx - s * 1.2, cy + s * 0.4, cx, cy + s * 1.3)
        path.cubicTo(cx + s * 1.2, cy + s * 0.4, cx + s, cy - s * 0.6, cx, cy + s * 0.35)
        painter.setBrush(QColor("#FF4081"))
        painter.setPen(QPen(WHITE, 1.4))
        painter.drawPath(path)

    def _draw_proud_eye(self, painter: QPainter, cx: float, cy: float, size: float, is_left: bool) -> None:
        # Half-closed smug eye
        rect = QRectF(cx - size * 0.45, cy - size * 0.22, size * 0.9, size * 0.45)
        path = QPainterPath()
        path.addRoundedRect(rect, 4, 4)
        painter.setBrush(WHITE)
        painter.setPen(QPen(ACCENT_LILAC, 1.2))
        painter.drawPath(path)

        # Eyebrow curved up
        brow = QPainterPath()
        hw = size * 0.4
        brow_y = cy - size * 0.35
        brow.moveTo(cx - hw, brow_y + (2 if is_left else -2))
        brow.quadTo(cx, brow_y - 4, cx + hw, brow_y + (-2 if is_left else 2))
        painter.setPen(QPen(ACCENT_LILAC_LIGHT, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(brow)

    def _draw_annoyed_eye(self, painter: QPainter, cx: float, cy: float, size: float, is_left: bool) -> None:
        tilt = -16 if is_left else 16
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(tilt)

        # Oval eye narrowed
        rect = QRectF(-size * 0.45, -size * 0.28, size * 0.9, size * 0.56)
        path = QPainterPath()
        path.addEllipse(rect)
        painter.setBrush(WHITE)
        painter.setPen(QPen(QColor("#FF5252"), 1.4))
        painter.drawPath(path)

        # Sharp pupil
        painter.setBrush(BLACK)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(-5, -4, 10, 10))

        painter.restore()

        # Eyebrow slant downward towards center
        brow = QPainterPath()
        hw = size * 0.42
        by = cy - size * 0.4
        if is_left:
            brow.moveTo(cx - hw, by - 3)
            brow.lineTo(cx + hw, by + 4)
        else:
            brow.moveTo(cx - hw, by + 4)
            brow.lineTo(cx + hw, by - 3)
        painter.setPen(QPen(QColor("#FF5252"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(brow)

    def _draw_sleepy_squint(self, painter: QPainter, cx: float, cy: float, size: float) -> None:
        path = QPainterPath()
        hw = size * 0.42
        path.moveTo(cx - hw, cy - 2)
        path.quadTo(cx, cy + size * 0.28, cx + hw, cy - 2)
        painter.setPen(QPen(WHITE, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)

    def _draw_sleep_arc(self, painter: QPainter, cx: float, cy: float, size: float) -> None:
        path = QPainterPath()
        hw = size * 0.4
        path.moveTo(cx - hw, cy)
        path.quadTo(cx, cy + 5, cx + hw, cy)
        painter.setPen(QPen(WHITE, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)

    def _draw_dizzy_spiral(self, painter: QPainter, cx: float, cy: float, radius: float) -> None:
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self._time_elapsed * 320.0)
        path = QPainterPath()
        path.moveTo(0, 0)
        steps = 42
        for i in range(steps):
            angle = i * 0.35
            r = (radius / steps) * i
            path.lineTo(r * math.cos(angle), r * math.sin(angle))
        painter.setPen(QPen(QColor("#FFD600"), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)
        painter.restore()

    def _draw_waving_hand_icon(self, painter: QPainter, cx: float, cy: float) -> None:
        wave_angle = math.sin(self._time_elapsed * 10.0) * 18.0
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(wave_angle)
        painter.setPen(QPen(WHITE, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(ACCENT_LILAC)
        # Cute waving mitten / hand
        hand_path = QPainterPath()
        hand_path.addRoundedRect(QRectF(-6, -10, 12, 16), 5, 5)
        hand_path.addEllipse(QRectF(4, -6, 6, 6))
        painter.drawPath(hand_path)
        painter.restore()

    def _draw_operational_overlays(self, painter: QPainter, w: float, h: float, cy: float) -> None:
        st_val = str(self._state.value if hasattr(self._state, "value") else self._state).lower()
        cx = w / 2.0

        # Speaking: animated sound waveform bars
        if st_val in ("habla", "speaking"):
            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(5):
                bar_x = cx - 18 + i * 9
                amp = math.sin(self._speak_phase + i * 0.8)
                bar_h = 4.0 + 8.0 * max(0.2, (amp + 1.0) / 2.0)
                painter.setBrush(ACCENT_LILAC_LIGHT)
                painter.drawRoundedRect(QRectF(bar_x, cy + h * 0.22 - bar_h / 2.0, 4, bar_h), 2, 2)

        # Thinking: 3 floating animated dots
        elif st_val == "piensa":
            for i in range(3):
                phase = (self._time_elapsed * 4.0 + i * 0.8) % (2.0 * math.pi)
                dot_y = cy - h * 0.3 + math.sin(phase) * 3.0
                painter.setBrush(QColor("#80D8FF"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(cx - 10 + i * 10, dot_y, 4, 4))

        # Yawning: open mouth
        elif st_val == "bostezo":
            painter.setBrush(QColor("#1A1224"))
            painter.setPen(QPen(ACCENT_LILAC, 1.4))
            painter.drawEllipse(QRectF(cx - 7, cy + h * 0.18, 14, 16))

        # Notification: golden bell indicator
        elif st_val == "notificacion":
            bell_swing = math.sin(self._time_elapsed * 8.0) * 12.0
            painter.save()
            painter.translate(cx, cy - h * 0.32)
            painter.rotate(bell_swing)
            painter.setBrush(QColor("#FFD600"))
            painter.setPen(QPen(WHITE, 1.0))
            painter.drawEllipse(QRectF(-4, -4, 8, 8))
            painter.restore()

    # ------------------------------------------------------------------
    # 15 Habit Scenes Delegation
    # ------------------------------------------------------------------

    def _is_habit_scene_active(self) -> bool:
        st_val = str(self._state.value if hasattr(self._state, "value") else self._state).lower()
        return "habit" in st_val or st_val in (
            "pomodoro", "agua", "lectura", "ejercicio", "meditacion",
            "caminar", "estudio", "dormir_temprano", "comida_saludable",
            "postura", "pausa_visual", "agradecimiento", "respiracion",
            "limpieza", "desconexion",
        )

    def _draw_habit_scene(self, painter: QPainter, w: float, h: float) -> None:
        st_val = str(self._state.value if hasattr(self._state, "value") else self._state).lower()
        meta = {
            "pomodoro_remaining_sec": self.pomodoro_remaining_sec,
            "pomodoro_active": self.pomodoro_active,
            "water_count": self.water_count,
            "water_target": self.water_target,
        }
        self.scene_gen.render_scene(
            scene_name=st_val,
            painter=painter,
            cx=w / 2.0,
            cy=h / 2.0,
            w=w,
            h=h,
            time_elapsed=self._time_elapsed,
            metadata=meta,
        )
