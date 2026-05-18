from __future__ import annotations

import ctypes
from pathlib import Path

import requests
from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QPoint,
    QPointF,
    QRectF,
    Qt,
    QTimer,
    pyqtProperty,
)
from PyQt6.QtGui import (
    QAction,
    QBitmap,
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QWidget

from app.config import (
    BORDER_ALPHA,
    CARD_HEIGHT,
    CARD_RADIUS,
    CARD_WIDTH,
    CARD_X,
    CARD_Y,
    FAILED_ACCENT,
    FONTS,
    FONTS_DIR,
    GREEN,
    RED,
    STATUS_ALPHA,
    SURFACE,
    TRAY_ICON_PATH,
    UNIT_ALPHA,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    YELLOW,
)
from app.autostart import is_autostart_enabled, set_autostart_enabled
from app.data import GlucoseReading
from app.settings import SettingsDialog


GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020


class GlucoseWidget(QWidget):
    def __init__(self, settings, service) -> None:
        super().__init__()
        self._settings = settings
        self._service = service
        self._reading: GlucoseReading | None = None
        self._drag_offset: QPoint | None = None
        self._drag_enabled = False
        self._arrow_bounce_offset = 0.0
        self._font_families = self._load_fonts()
        self._tray = self._create_tray()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)

        if self._settings.x is not None and self._settings.y is not None:
            self.move(self._settings.x, self._settings.y)

        self._extend_frame_into_client_area()
        self._apply_card_mask()
        self._sync_window_interaction()

        self._service.reading_changed.connect(self._update_reading)
        self._service.error_changed.connect(self._mark_failed)

        self._arrow_animation = QPropertyAnimation(self, b"arrowBounceOffset")
        self._arrow_animation.setDuration(850)
        self._arrow_animation.setStartValue(0.0)
        self._arrow_animation.setKeyValueAt(0.5, 4.0)
        self._arrow_animation.setEndValue(0.0)
        self._arrow_animation.setLoopCount(-1)
        self._arrow_animation.setEasingCurve(QEasingCurve.Type.InOutSine)

        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.setInterval(self._settings.idle_timeout_seconds * 1000)
        self.idle_timer.timeout.connect(self._fade_out)
        self.idle_timer.start()

        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.setWindowOpacity(1.0)

    @pyqtProperty(float)
    def arrowBounceOffset(self) -> float:
        return self._arrow_bounce_offset

    @arrowBounceOffset.setter
    def arrowBounceOffset(self, value: float) -> None:
        self._arrow_bounce_offset = value
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._extend_frame_into_client_area()
        self._apply_card_mask()
        self._sync_window_interaction()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        active_color = self._active_color()
        card = QRectF(CARD_X, CARD_Y, CARD_WIDTH, CARD_HEIGHT)

        self._draw_outer_glow(painter, card, active_color)
        self._draw_card(painter, card)
        self._draw_ambient_blob(painter, card, active_color)
        self._draw_accent_bar(painter, card, active_color)
        self._draw_text(painter, card, active_color)
        self._draw_arrow_area(painter, card, active_color)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if not self._drag_enabled:
            event.ignore()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._fade_in()
            self.idle_timer.start()
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_enabled and self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_enabled and event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            self._settings.save_position(self.x(), self.y())
            event.accept()
        else:
            event.ignore()

    def _draw_outer_glow(self, painter: QPainter, card: QRectF, active_color: QColor) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        for expand, opacity in ((5, 0.008), (9, 0.005), (14, 0.003), (18, 0.002)):
            color = QColor(active_color)
            color.setAlphaF(opacity)
            painter.setBrush(color)
            painter.drawRoundedRect(card.adjusted(-expand, -expand, expand, expand), CARD_RADIUS + expand, CARD_RADIUS + expand)

    def _draw_card(self, painter: QPainter, card: QRectF) -> None:
        painter.setBrush(QBrush(QColor(SURFACE)))
        painter.setPen(QPen(QColor(255, 255, 255, BORDER_ALPHA), 1))
        painter.drawRoundedRect(card, CARD_RADIUS, CARD_RADIUS)

    def _draw_ambient_blob(self, painter: QPainter, card: QRectF, active_color: QColor) -> None:
        painter.save()
        clip = QPainterPath()
        clip.addRoundedRect(card, CARD_RADIUS, CARD_RADIUS)
        painter.setClipPath(clip)
        painter.setPen(Qt.PenStyle.NoPen)

        center = QPointF(card.right() - 24, card.top() + 31)
        gradient = QRadialGradient(center, 82)
        inner = QColor(active_color)
        inner.setAlphaF(0.24)
        mid = QColor(active_color)
        mid.setAlphaF(0.11)
        outer = QColor(active_color)
        outer.setAlpha(0)
        gradient.setColorAt(0.0, inner)
        gradient.setColorAt(0.48, mid)
        gradient.setColorAt(1.0, outer)

        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QRectF(card.right() - 108, card.top() - 44, 156, 132))
        painter.restore()

    def _draw_accent_bar(self, painter: QPainter, card: QRectF, active_color: QColor) -> None:
        bar_width = 3
        bar_height = card.height() * 0.6
        bar_x = card.x()
        bar_y = card.y() + (card.height() - bar_height) / 2

        painter.setPen(Qt.PenStyle.NoPen)
        for expand, opacity in ((6, 0.03), (4, 0.08), (2, 0.15)):
            color = QColor(active_color)
            color.setAlphaF(opacity)
            painter.setBrush(color)
            painter.drawRoundedRect(
                QRectF(bar_x - expand, bar_y - expand, bar_width + expand, bar_height + expand * 2),
                2,
                2,
            )

        painter.setBrush(QColor(active_color))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_width, bar_height), 2, 2)

    def _draw_text(self, painter: QPainter, card: QRectF, active_color: QColor) -> None:
        value = self._value_text()
        label = "GLUKOSE · JETZT"
        text_x = card.x() + 18

        label_font = self._font("mono_regular", 9)
        value_font = self._font("display", 44, extra_bold=True)
        unit_font = self._font("mono_light", 10)

        value_fm = QFontMetrics(value_font)
        label_baseline = card.y() + 24
        value_baseline = card.y() + 58

        painter.setFont(label_font)
        painter.setPen(QColor(255, 255, 255, STATUS_ALPHA))
        painter.drawText(QPointF(text_x, label_baseline), label)

        glow_color = QColor(active_color)
        glow_color.setAlphaF(0.15)
        painter.setFont(value_font)
        painter.setPen(glow_color)
        painter.drawText(QPointF(text_x, value_baseline + 2), value)

        painter.setPen(QColor(active_color))
        painter.drawText(QPointF(text_x, value_baseline), value)

        painter.setFont(unit_font)
        painter.setPen(QColor(255, 255, 255, UNIT_ALPHA))
        unit_x = text_x + value_fm.horizontalAdvance(value) + 5
        painter.drawText(QPointF(unit_x, value_baseline), "mmol/L")

    def _draw_arrow_area(self, painter: QPainter, card: QRectF, active_color: QColor) -> None:
        circle_radius = 20
        circle_cx = card.right() - 18 - circle_radius
        circle_cy = card.top() + card.height() / 2 - 5

        circle_color = QColor(active_color)
        circle_color.setAlphaF(0.12)
        painter.setBrush(circle_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(circle_cx, circle_cy), circle_radius, circle_radius)

        bounce = self._arrow_bounce_offset if self._is_fast_trend() else 0.0
        self._draw_arrow(painter, QPointF(circle_cx, circle_cy + bounce), active_color)

        delta = self._delta_text()
        delta_font = self._font("mono_regular", 9)
        delta_fm = QFontMetrics(delta_font)
        delta_color = QColor(active_color)
        delta_color.setAlphaF(0.55)
        painter.setFont(delta_font)
        painter.setPen(delta_color)
        painter.drawText(QPointF(circle_cx - delta_fm.horizontalAdvance(delta) / 2, circle_cy + 33), delta)

    def _draw_arrow(self, painter: QPainter, center: QPointF, active_color: QColor) -> None:
        painter.setPen(
            QPen(
                QColor(active_color),
                2.5,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)

        kind = self._arrow_kind()
        cx = center.x()
        cy = center.y()
        if kind == "fast_up":
            painter.drawLine(QPointF(cx, cy + 11), QPointF(cx, cy - 11))
            painter.drawLine(QPointF(cx - 6, cy - 5), QPointF(cx, cy - 11))
            painter.drawLine(QPointF(cx + 6, cy - 5), QPointF(cx, cy - 11))
        elif kind == "fast_down":
            painter.drawLine(QPointF(cx, cy - 11), QPointF(cx, cy + 11))
            painter.drawLine(QPointF(cx - 6, cy + 5), QPointF(cx, cy + 11))
            painter.drawLine(QPointF(cx + 6, cy + 5), QPointF(cx, cy + 11))
        elif kind == "slow_up":
            painter.drawLine(QPointF(cx - 9, cy + 9), QPointF(cx + 9, cy - 9))
            painter.drawLine(QPointF(cx + 1, cy - 9), QPointF(cx + 9, cy - 9))
            painter.drawLine(QPointF(cx + 9, cy - 9), QPointF(cx + 9, cy - 1))
        elif kind == "slow_down":
            painter.drawLine(QPointF(cx - 9, cy - 9), QPointF(cx + 9, cy + 9))
            painter.drawLine(QPointF(cx + 1, cy + 9), QPointF(cx + 9, cy + 9))
            painter.drawLine(QPointF(cx + 9, cy + 9), QPointF(cx + 9, cy + 1))
        else:
            painter.drawLine(QPointF(cx - 10, cy), QPointF(cx + 10, cy))
            painter.drawLine(QPointF(cx + 4, cy - 6), QPointF(cx + 10, cy))
            painter.drawLine(QPointF(cx + 4, cy + 6), QPointF(cx + 10, cy))

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._settings, self._service, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            self.idle_timer.setInterval(self._settings.idle_timeout_seconds * 1000)
            self._fade_in()

    def _update_reading(self, reading: GlucoseReading) -> None:
        self._reading = reading
        if self._is_fast_trend() and not reading.failed:
            if self._arrow_animation.state() != QPropertyAnimation.State.Running:
                self._arrow_animation.start()
        else:
            self._arrow_animation.stop()
            self._arrow_bounce_offset = 0.0
        self.update()

    def _mark_failed(self, message: str) -> None:
        if self._reading is not None:
            self._reading = GlucoseReading(
                value_mmol=self._reading.value_mmol,
                delta_mmol=self._reading.delta_mmol,
                trend_arrow=self._reading.trend_arrow,
                failed=True,
            )
            self.update()

    def _value_text(self) -> str:
        return f"{self._reading.value_mmol:.1f}" if self._reading else "--"

    def _delta_text(self) -> str:
        if not self._reading:
            return "± 0.0"
        delta = self._reading.delta_mmol
        if abs(delta) < 0.05:
            return "± 0.0"
        arrow = "↑" if delta > 0 else "↓"
        return f"{arrow} {delta:+.1f}"

    def _active_color(self) -> QColor:
        if not self._reading or self._reading.failed:
            return QColor(FAILED_ACCENT)
        if self._reading.value_mmol < self._settings.low_threshold or self._reading.value_mmol > self._settings.high_threshold:
            return QColor(RED)
        if self._is_fast_trend():
            return QColor(RED)
        if self._arrow_kind() in {"slow_up", "slow_down"}:
            return QColor(YELLOW)
        return QColor(GREEN)

    def _arrow_kind(self) -> str:
        arrow = (self._reading.trend_arrow if self._reading else "→").strip()
        if arrow in {"↑↑", "⇈"}:
            return "fast_up"
        if arrow in {"↓↓", "⇊"}:
            return "fast_down"
        if arrow in {"↑"}:
            return "fast_up"
        if arrow in {"↓"}:
            return "fast_down"
        if arrow in {"↗", "↖"}:
            return "slow_up"
        if arrow in {"↘", "↙"}:
            return "slow_down"
        return "stable"

    def _is_fast_trend(self) -> bool:
        return self._arrow_kind() in {"fast_up", "fast_down"}

    def _fade_out(self) -> None:
        self.fade_anim.stop()
        self.fade_anim.setDuration(800)
        self.fade_anim.setStartValue(self.windowOpacity())
        self.fade_anim.setEndValue(self._settings.idle_opacity_percent / 100)
        self.fade_anim.start()

    def _fade_in(self) -> None:
        self.fade_anim.stop()
        self.fade_anim.setDuration(200)
        self.fade_anim.setStartValue(self.windowOpacity())
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()
        self.idle_timer.start()

    def _font(self, key: str, size: int, extra_bold: bool = False) -> QFont:
        spec = FONTS[key]
        family = self._font_families.get(key) or spec.family or spec.fallback
        font = QFont(family)
        font.setPixelSize(size)
        if extra_bold:
            font.setWeight(QFont.Weight.ExtraBold)
        elif key.startswith("mono"):
            font.setWeight(QFont.Weight.Light if key.endswith("light") else QFont.Weight.Normal)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return font

    def _load_fonts(self) -> dict[str, str]:
        FONTS_DIR.mkdir(parents=True, exist_ok=True)
        families: dict[str, str] = {}
        for key, spec in FONTS.items():
            font_path = FONTS_DIR / spec.file_name
            if not font_path.exists():
                self._download_font(spec.url, font_path)
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            loaded = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
            families[key] = loaded[0] if loaded else spec.fallback
        return families

    def _download_font(self, url: str, font_path: Path) -> None:
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            font_path.write_bytes(response.content)
        except Exception:
            pass

    def _extend_frame_into_client_area(self) -> None:
        if not hasattr(ctypes, "windll"):
            return

        class Margins(ctypes.Structure):
            _fields_ = [
                ("cxLeftWidth", ctypes.c_int),
                ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int),
                ("cyBottomHeight", ctypes.c_int),
            ]

        try:
            margins = Margins(-1, -1, -1, -1)
            ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(int(self.winId()), ctypes.byref(margins))
        except Exception:
            pass

    def _create_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(self)
        if TRAY_ICON_PATH.exists():
            tray.setIcon(QIcon(str(TRAY_ICON_PATH)))
        tray.setToolTip("Dextop Glucose Widget")

        menu = tray.contextMenu()
        if menu is None:
            from PyQt6.QtWidgets import QMenu

            menu = QMenu()
            tray.setContextMenu(menu)

        self._drag_action = QAction("Drag and Drop aktivieren", self)
        self._drag_action.setCheckable(True)
        self._drag_action.toggled.connect(self.set_drag_enabled)
        self._autostart_action = QAction("Autostart aktivieren", self)
        self._autostart_action.setCheckable(True)
        self._autostart_action.setChecked(is_autostart_enabled())
        self._autostart_action.toggled.connect(self._set_autostart_enabled)
        refresh_action = QAction("Refresh now", self)
        refresh_action.triggered.connect(self._service.refresh_now)
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._open_settings)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)

        menu.addAction(self._drag_action)
        menu.addAction(self._autostart_action)
        menu.addSeparator()
        menu.addAction(refresh_action)
        menu.addAction(settings_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        tray.activated.connect(self._handle_tray_activated)
        tray.show()
        return tray

    def _handle_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._open_settings()

    def set_drag_enabled(self, enabled: bool) -> None:
        self._drag_enabled = enabled
        self._drag_offset = None
        if hasattr(self, "_drag_action") and self._drag_action.isChecked() != enabled:
            self._drag_action.setChecked(enabled)
        self._sync_window_interaction()
        if enabled:
            self._fade_in()
            self.idle_timer.start()

    def _set_autostart_enabled(self, enabled: bool) -> None:
        try:
            set_autostart_enabled(enabled)
        except Exception as exc:
            if hasattr(self, "_autostart_action"):
                self._autostart_action.blockSignals(True)
                self._autostart_action.setChecked(is_autostart_enabled())
                self._autostart_action.blockSignals(False)
            if self._tray.isVisible():
                self._tray.showMessage(
                    "Autostart konnte nicht geaendert werden",
                    str(exc),
                    QSystemTrayIcon.MessageIcon.Warning,
                    5000,
                )

    def _sync_window_interaction(self) -> None:
        if not hasattr(ctypes, "windll") or int(self.winId()) == 0:
            return
        try:
            user32 = ctypes.windll.user32
            hwnd = int(self.winId())
            exstyle = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if self._drag_enabled:
                exstyle &= ~WS_EX_TRANSPARENT
            else:
                exstyle |= WS_EX_LAYERED | WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle)
        except Exception:
            pass

    def _apply_card_mask(self) -> None:
        mask = QBitmap(self.size())
        mask.fill(Qt.GlobalColor.color0)
        painter = QPainter(mask)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.GlobalColor.color1)
        painter.setPen(Qt.PenStyle.NoPen)
        glow_bounds = QRectF(CARD_X, CARD_Y, CARD_WIDTH, CARD_HEIGHT).adjusted(-18, -18, 18, 18)
        painter.drawRoundedRect(glow_bounds, CARD_RADIUS + 18, CARD_RADIUS + 18)
        painter.end()
        self.setMask(mask)
