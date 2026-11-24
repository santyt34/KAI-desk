"""
ui/animation_engine.py
======================
60 FPS Procedural Animation & Particle Engine for Troko-Desk.
Provides easing interpolations, dynamic particle systems (blush, hearts,
stars, sweat drops, confetti, sleep Zzz) and animated feedback badges.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient


# ---------------------------------------------------------------------------
# Easing Curves
# ---------------------------------------------------------------------------


def ease_out_quad(t: float) -> float:
    return 1.0 - (1.0 - t) * (1.0 - t)


def ease_in_out_quad(t: float) -> float:
    return 2.0 * t * t if t < 0.5 else 1.0 - math.pow(-2.0 * t + 2.0, 2.0) / 2.0


def ease_out_back(t: float, s: float = 1.70158) -> float:
    return 1.0 + (s + 1.0) * math.pow(t - 1.0, 3.0) + s * math.pow(t - 1.0, 2.0)


def ease_out_elastic(t: float) -> float:
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    c4 = (2.0 * math.pi) / 3.0
    return math.pow(2.0, -10.0 * t) * math.sin((t * 10.0 - 0.75) * c4) + 1.0


def ease_out_bounce(t: float) -> float:
    n1 = 7.5625
    d1 = 2.75
    if t < 1.0 / d1:
        return n1 * t * t
    elif t < 2.0 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375


# ---------------------------------------------------------------------------
# Particles & Overlays
# ---------------------------------------------------------------------------


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    life: float = 1.0          # 1.0 to 0.0
    decay: float = 0.02
    color: QColor = field(default_factory=lambda: QColor("#FF6584"))
    rotation: float = 0.0
    v_rot: float = 0.0
    kind: str = "circle"       # heart, star, sweat, confetti, zzz, circle


class AnimationEngine:
    """
    Manages procedural effects at 60 FPS:
    - Particle lifecycle and physics
    - Overlays (rubor, corazones, estrellas, sudor, confeti)
    - Action completion badge (green check + short text)
    """

    def __init__(self) -> None:
        self.particles: List[Particle] = []
        self.blush_intensity: float = 0.0     # 0.0 to 1.0
        self.target_blush: float = 0.0

        # Action feedback badge
        self.badge_active: bool = False
        self.badge_text: str = "Listo"
        self.badge_time: float = 0.0
        self.badge_duration: float = 1.8
        self.badge_success: bool = True

    # ------------------------------------------------------------------
    # Trigger Helpers
    # ------------------------------------------------------------------

    def set_blush(self, intensity: float) -> None:
        self.target_blush = max(0.0, min(1.0, intensity))

    def spawn_hearts(self, origin_x: float, origin_y: float, count: int = 4) -> None:
        for _ in range(count):
            p = Particle(
                x=origin_x + random.uniform(-15, 15),
                y=origin_y + random.uniform(-5, 5),
                vx=random.uniform(-0.8, 0.8),
                vy=random.uniform(-1.8, -0.8),
                size=random.uniform(9.0, 16.0),
                decay=random.uniform(0.012, 0.025),
                color=QColor(255, random.randint(70, 120), random.randint(140, 180), 230),
                rotation=random.uniform(-20, 20),
                v_rot=random.uniform(-1.0, 1.0),
                kind="heart",
            )
            self.particles.append(p)

    def spawn_stars(self, origin_x: float, origin_y: float, count: int = 5) -> None:
        for _ in range(count):
            p = Particle(
                x=origin_x + random.uniform(-30, 30),
                y=origin_y + random.uniform(-20, 20),
                vx=random.uniform(-0.5, 0.5),
                vy=random.uniform(-0.8, 0.5),
                size=random.uniform(8.0, 14.0),
                decay=random.uniform(0.015, 0.03),
                color=QColor(255, 220, 50, 240),
                rotation=random.uniform(0, 360),
                v_rot=random.uniform(3.0, 8.0),
                kind="star",
            )
            self.particles.append(p)

    def spawn_sweat_drops(self, origin_x: float, origin_y: float, count: int = 2) -> None:
        for _ in range(count):
            p = Particle(
                x=origin_x + random.uniform(-8, 8),
                y=origin_y + random.uniform(-5, 5),
                vx=random.uniform(0.5, 1.2),
                vy=random.uniform(0.8, 2.0),
                size=random.uniform(7.0, 11.0),
                decay=random.uniform(0.018, 0.035),
                color=QColor(70, 170, 255, 230),
                kind="sweat",
            )
            self.particles.append(p)

    def spawn_confetti(self, w: float, h: float, count: int = 35) -> None:
        colors = [
            QColor("#FF4081"), QColor("#00E676"), QColor("#FFD600"),
            QColor("#00B0FF"), QColor("#E040FB"), QColor("#FF6D00")
        ]
        for _ in range(count):
            p = Particle(
                x=w / 2 + random.uniform(-w * 0.4, w * 0.4),
                y=h * 0.2 + random.uniform(-10, 20),
                vx=random.uniform(-2.5, 2.5),
                vy=random.uniform(-4.0, -1.0),
                size=random.uniform(5.0, 9.0),
                decay=random.uniform(0.008, 0.018),
                color=random.choice(colors),
                rotation=random.uniform(0, 360),
                v_rot=random.uniform(-8.0, 8.0),
                kind="confetti",
            )
            self.particles.append(p)

    def spawn_zzz(self, origin_x: float, origin_y: float) -> None:
        if random.random() < 0.15:  # trigger periodically
            p = Particle(
                x=origin_x + random.uniform(-5, 15),
                y=origin_y,
                vx=random.uniform(0.4, 0.9),
                vy=random.uniform(-0.9, -0.4),
                size=random.uniform(10.0, 16.0),
                decay=0.012,
                color=QColor(180, 200, 255, 210),
                kind="zzz",
            )
            self.particles.append(p)

    def trigger_feedback_badge(self, text: str = "Listo", success: bool = True) -> None:
        self.badge_active = True
        self.badge_text = text
        self.badge_time = 0.0
        self.badge_success = success

    # ------------------------------------------------------------------
    # Update Cycle (Called every frame at ~60 FPS)
    # ------------------------------------------------------------------

    def update(self, dt: float = 0.016) -> None:
        # Smooth blush
        self.blush_intensity += (self.target_blush - self.blush_intensity) * 0.08

        # Update particles
        alive: List[Particle] = []
        for p in self.particles:
            p.x += p.vx
            p.y += p.vy
            p.rotation += p.v_rot
            p.life -= p.decay

            if p.kind == "confetti":
                p.vy += 0.15  # gravity
                p.vx *= 0.98  # air drag
            elif p.kind == "sweat":
                p.vy += 0.08  # downward slip

            if p.life > 0.0:
                alive.append(p)
        self.particles = alive

        # Update badge
        if self.badge_active:
            self.badge_time += dt
            if self.badge_time >= self.badge_duration:
                self.badge_active = False

    # ------------------------------------------------------------------
    # Render Helpers
    # ------------------------------------------------------------------

    def render_blush(self, painter: QPainter, left_x: float, right_x: float, y: float, w: float = 24, h: float = 12) -> None:
        if self.blush_intensity <= 0.02:
            return

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)

        alpha = int(140 * self.blush_intensity)
        color = QColor(255, 90, 130, alpha)

        for cx in (left_x, right_x):
            rect = QRectF(cx - w / 2, y - h / 2, w, h)
            grad = QRadialGradient(rect.center(), w / 2)
            grad.setColorAt(0.0, color)
            grad.setColorAt(1.0, QColor(255, 90, 130, 0))
            painter.setBrush(grad)
            painter.drawEllipse(rect)

        painter.restore()

    def render_particles(self, painter: QPainter) -> None:
        if not self.particles:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for p in self.particles:
            alpha = int(255 * max(0.0, min(1.0, p.life)))
            c = QColor(p.color)
            c.setAlpha(alpha)

            painter.save()
            painter.translate(p.x, p.y)
            painter.rotate(p.rotation)

            if p.kind == "heart":
                self._draw_heart(painter, p.size, c)
            elif p.kind == "star":
                self._draw_star(painter, p.size, c)
            elif p.kind == "sweat":
                self._draw_sweat(painter, p.size, c)
            elif p.kind == "confetti":
                painter.setBrush(c)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(QRectF(-p.size / 2, -p.size / 4, p.size, p.size / 2))
            elif p.kind == "zzz":
                self._draw_zzz(painter, p.size, c)
            else:
                painter.setBrush(c)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QRectF(-p.size / 2, -p.size / 2, p.size, p.size))

            painter.restore()

        painter.restore()

    def render_feedback_badge(self, painter: QPainter, rect: QRectF) -> None:
        """Renders green checkmark badge with short text."""
        if not self.badge_active:
            return

        t = self.badge_time / self.badge_duration
        # Pop in with bounce, stay, fade out
        if t < 0.2:
            scale = ease_out_back(t / 0.2)
            alpha = 1.0
        elif t > 0.8:
            scale = 1.0
            alpha = max(0.0, (1.0 - t) / 0.2)
        else:
            scale = 1.0
            alpha = 1.0

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        badge_w = 120.0
        badge_h = 32.0
        cx = rect.center().x()
        cy = rect.center().y()

        painter.translate(cx, cy)
        painter.scale(scale, scale)

        badge_rect = QRectF(-badge_w / 2, -badge_h / 2, badge_w, badge_h)

        # Background capsule
        bg_col = QColor("#0D1117")
        bg_col.setAlpha(int(235 * alpha))
        painter.setBrush(bg_col)

        border_col = QColor("#00E676" if self.badge_success else "#FF5252")
        border_col.setAlpha(int(240 * alpha))
        painter.setPen(QPen(border_col, 1.8))
        painter.drawRoundedRect(badge_rect, badge_h / 2, badge_h / 2)

        # Draw checkmark icon
        check_cx = badge_rect.left() + 20
        check_cy = badge_rect.center().y()
        painter.setPen(QPen(border_col, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        path = QPainterPath()
        path.moveTo(check_cx - 6, check_cy)
        path.lineTo(check_cx - 1, check_cy + 5)
        path.lineTo(check_cx + 7, check_cy - 5)
        painter.drawPath(path)

        # Draw short text
        text_col = QColor("#FFFFFF")
        text_col.setAlpha(int(245 * alpha))
        painter.setPen(text_col)
        font = painter.font()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        text_rect = QRectF(check_cx + 10, badge_rect.top(), badge_w - 38, badge_h)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.badge_text)

        painter.restore()

    # ------------------------------------------------------------------
    # Shape Primitives
    # ------------------------------------------------------------------

    def _draw_heart(self, painter: QPainter, size: float, color: QColor) -> None:
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        s = size / 2.0
        path.moveTo(0, s * 0.4)
        path.cubicTo(-s, -s * 0.6, -s * 1.2, s * 0.4, 0, s * 1.3)
        path.cubicTo(s * 1.2, s * 0.4, s, -s * 0.6, 0, s * 0.4)
        painter.drawPath(path)

    def _draw_star(self, painter: QPainter, size: float, color: QColor) -> None:
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        r_outer = size / 2.0
        r_inner = r_outer * 0.45
        path = QPainterPath()
        points = 4
        for i in range(points * 2):
            angle = i * (math.pi / points) - math.pi / 2
            r = r_outer if i % 2 == 0 else r_inner
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        painter.drawPath(path)

    def _draw_sweat(self, painter: QPainter, size: float, color: QColor) -> None:
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        w = size * 0.6
        h = size
        path.moveTo(0, -h / 2)
        path.cubicTo(w / 2, -h * 0.1, w / 2, h / 2, 0, h / 2)
        path.cubicTo(-w / 2, h / 2, -w / 2, -h * 0.1, 0, -h / 2)
        painter.drawPath(path)

    def _draw_zzz(self, painter: QPainter, size: float, color: QColor) -> None:
        painter.setPen(QPen(color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        s = size / 2.0
        path = QPainterPath()
        path.moveTo(-s * 0.6, -s * 0.7)
        path.lineTo(s * 0.6, -s * 0.7)
        path.lineTo(-s * 0.5, s * 0.7)
        path.lineTo(s * 0.6, s * 0.7)
        painter.drawPath(path)
