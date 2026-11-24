"""
ui/eye_renderer.py
==================
60 FPS eye / mood renderer for the KAI island.

Draws two animated oval eyes with:
- Natural blink cycle (randomised interval)
- Smooth pupil tracking toward the global cursor position
- State-driven expressions (squint for thinking, wide for alert, etc.)
- Accent-colour glow matching settings.ui_accent_color
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
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import QWidget

from config.settings import settings
from core.state_machine import KAIState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FPS = settings.ui_fps
_FRAME_MS = max(1, int(1000 / _FPS))

_ACCENT = QColor(settings.ui_accent_color)
_WHITE  = QColor("#FFFFFF")
_BLACK  = QColor("#0D0D0D")
_GREY   = QColor("#888888")

# Eye geometry (relative to widget size)
_EYE_SPACING_RATIO = 0.30   # fraction of widget width between eye centres
_EYE_W_RATIO       = 0.22   # eye width as fraction of widget width
_EYE_H_RATIO       = 0.55   # eye height as fraction of widget height
_PUPIL_RATIO       = 0.35   # pupil diameter as fraction of eye width
_MAX_PUPIL_SHIFT   = 0.30   # max pupil offset as fraction of eye half-size

# Blink parameters
_BLINK_MIN_INTERVAL = 2.5   # seconds
_BLINK_MAX_INTERVAL = 6.0   # seconds
_BLINK_DURATION     = 0.12  # seconds to fully close then open


@dataclass
class _EyeState:
    """Per-eye animation state."""
    # Pupil position in [-1, 1] normalised space
    pupil_x: float = 0.0
    pupil_y: float = 0.0
    # Openness: 1.0 = fully open, 0.0 = closed
    openness: float = 1.0

    # Squint level for THINKING: narrows vertical openness
    squint: float = 0.0  # 0 = none, 1 = max squint


class EyeRenderer(QWidget):
    """
    Widget that draws KAI's animated eyes at ~60 FPS.
    Set the current state via :meth:`set_state`.
    Update cursor position via :meth:`update_cursor`.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAutoFillBackground(False)

        self._state: KAIState = KAIState.IDLE
        self._left  = _EyeState()
        self._right = _EyeState()

        # Cursor in widget-local space (initially centre)
        self._cursor_local: QPointF = QPointF(0.0, 0.0)

        # Blink scheduling
        self._blink_next: float = time.monotonic() + self._next_blink_interval()
        self._blink_start: Optional[float] = None

        # Smooth pupil targets
        self._target_px: float = 0.0
        self._target_py: float = 0.0

        # 60 FPS render timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(_FRAME_MS)

        logger.debug("EyeRenderer started at %d FPS", _FPS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_state(self, state: KAIState) -> None:
        self._state = state
        self.update()

    def update_cursor(self, global_pos: QPoint) -> None:
        """Convert global cursor position to widget-local coords."""
        local = self.mapFromGlobal(global_pos)
        self._cursor_local = QPointF(local.x(), local.y())

    # ------------------------------------------------------------------
    # Tick / animation
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        now = time.monotonic()
        self._animate_blink(now)
        self._animate_pupils()
        self.update()

    def _next_blink_interval(self) -> float:
        return random.uniform(_BLINK_MIN_INTERVAL, _BLINK_MAX_INTERVAL)

    def _animate_blink(self, now: float) -> None:
        """Drive the blink cycle."""
        if self._state == KAIState.SLEEPING:
            self._left.openness = self._right.openness = 0.05
            return

        if self._blink_start is not None:
            elapsed = now - self._blink_start
            half = _BLINK_DURATION / 2.0
            if elapsed < half:
                o = 1.0 - (elapsed / half)
            elif elapsed < _BLINK_DURATION:
                o = (elapsed - half) / half
            else:
                o = 1.0
                self._blink_start = None
                self._blink_next = now + self._next_blink_interval()
            self._left.openness = self._right.openness = max(0.05, o)
        elif now >= self._blink_next:
            self._blink_start = now

    def _animate_pupils(self) -> None:
        """Smoothly move pupils toward cursor."""
        if self._state == KAIState.SLEEPING:
            self._target_px = self._target_py = 0.0
        else:
            cx = self._cursor_local.x()
            cy = self._cursor_local.y()
            w, h = self.width(), self.height()
            if w > 0 and h > 0:
                self._target_px = max(-1, min(1, (cx - w / 2) / (w / 2))) * _MAX_PUPIL_SHIFT
                self._target_py = max(-1, min(1, (cy - h / 2) / (h / 2))) * _MAX_PUPIL_SHIFT

        alpha = 0.08  # lerp factor – lower = smoother/slower
        self._left.pupil_x  += (self._target_px - self._left.pupil_x) * alpha
        self._left.pupil_y  += (self._target_py - self._left.pupil_y) * alpha
        self._right.pupil_x += (self._target_px - self._right.pupil_x) * alpha
        self._right.pupil_y += (self._target_py - self._right.pupil_y) * alpha

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_background(painter)
        self._draw_eye(painter, left=True)
        self._draw_eye(painter, left=False)
        painter.end()

    def _draw_background(self, painter: QPainter) -> None:
        w, h = self.width(), self.height()
        bg = QColor("#111111")
        bg.setAlpha(230)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        painter.fillPath(path, bg)

        # Accent glow border
        glow_color = QColor(_ACCENT)
        glow_color.setAlpha(80)
        pen = QPen(glow_color, 1.5)
        painter.setPen(pen)
        painter.drawPath(path)

    def _eye_rect(self, left: bool) -> QRectF:
        """Return the bounding rectangle for one eye."""
        w, h = self.width(), self.height()
        ew = w * _EYE_W_RATIO
        eh = h * _EYE_H_RATIO
        cx = w / 2 + ((-1 if left else 1) * w * _EYE_SPACING_RATIO)
        cy = h / 2
        return QRectF(cx - ew / 2, cy - eh / 2, ew, eh)

    def _draw_eye(self, painter: QPainter, left: bool) -> None:
        eye = self._left if left else self._right
        rect = self._eye_rect(left)

        # -- State-based modifiers ------------------------------------------
        openness = eye.openness
        squint_top = 0.0  # fraction by which top of eye is cut

        if self._state == KAIState.THINKING:
            squint_top = 0.35
        elif self._state == KAIState.HAPPY:
            squint_top = 0.6   # happy squint (curve upward)
        elif self._state == KAIState.ALERT:
            openness = min(1.0, openness * 1.25)

        # Apply openness by shrinking height
        effective_h = rect.height() * openness
        eye_rect = QRectF(
            rect.x(),
            rect.center().y() - effective_h / 2,
            rect.width(),
            effective_h,
        )

        # -- Eye white -------------------------------------------------------
        path = QPainterPath()
        if self._state == KAIState.HAPPY:
            # Arc / squint shape
            path.moveTo(eye_rect.bottomLeft())
            path.quadTo(eye_rect.center(), eye_rect.bottomRight())
            path.lineTo(eye_rect.topRight())
            path.quadTo(QPointF(eye_rect.center().x(), eye_rect.top() + effective_h * 0.3),
                        eye_rect.topLeft())
            path.closeSubpath()
        else:
            path.addEllipse(eye_rect)

        # Gradient fill
        grad = QRadialGradient(eye_rect.center(), eye_rect.width() / 2)
        grad.setColorAt(0, QColor("#1E1E2E"))
        grad.setColorAt(1, QColor("#0A0A14"))
        painter.fillPath(path, grad)

        # Border
        accent_pen = QPen(_ACCENT, 1.2)
        painter.setPen(accent_pen)
        painter.drawPath(path)

        # -- Pupil -----------------------------------------------------------
        if self._state not in (KAIState.SLEEPING, KAIState.HAPPY):
            pr = eye_rect.width() * _PUPIL_RATIO
            px = eye_rect.center().x() + eye.pupil_x * eye_rect.width() / 2
            py = eye_rect.center().y() + eye.pupil_y * eye_rect.height() / 2
            pupil_rect = QRectF(px - pr / 2, py - pr / 2, pr, pr)
            painter.setBrush(_ACCENT)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(pupil_rect)

            # Specular highlight
            highlight = QRectF(
                pupil_rect.x() + pr * 0.2,
                pupil_rect.y() + pr * 0.1,
                pr * 0.28,
                pr * 0.28,
            )
            painter.setBrush(_WHITE)
            painter.drawEllipse(highlight)
