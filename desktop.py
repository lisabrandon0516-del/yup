"""Frosted-glass desktop: wallpaper, mica windows, and a child-window manager."""

from __future__ import annotations

from PIL import Image, ImageFilter
from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from open_late.ui.icons import app_label, icon_pixmap
from open_late.ui.theme import ACCENT, DOWN, PAINT, TEXT, ui_font

TASKBAR = 52


def blur_pixmap(pix: QPixmap, radius: float = 18) -> QPixmap:
    if pix.isNull():
        return pix
    qimg = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    width, height = qimg.width(), qimg.height()
    src = Image.frombuffer("RGBA", (width, height), bytes(qimg.constBits()), "raw", "BGRA", qimg.bytesPerLine(), 1)
    blurred = src.filter(ImageFilter.GaussianBlur(radius=radius))
    out = QImage(blurred.tobytes("raw", "BGRA"), blurred.width, blurred.height, QImage.Format.Format_ARGB32)
    return QPixmap.fromImage(out.copy())


def ink_pixmap(pix: QPixmap, color: QColor) -> QPixmap:
    """Recolor a transparent mark so cream artwork reads on a light desk."""
    out = QPixmap(pix.size())
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.drawPixmap(0, 0, pix)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(out.rect(), color)
    painter.end()
    return out


def paint_bloom(pix: QPixmap) -> None:
    """Office canvas. The door cards sit on the same gray as the desk."""
    painter = QPainter(pix)
    painter.fillRect(pix.rect(), QColor("#EEF1F4"))
    painter.fillRect(0, 0, 8, pix.height(), QColor("#0C3B22"))
    painter.end()


class Stage(QWidget):
    """Backdrop that glass panels sample a pre-blurred copy of."""

    def __init__(self, parent=None, paint_fn=paint_bloom):
        super().__init__(parent)
        self.paint_fn = paint_fn
        self._raw = QPixmap()
        self._blur = QPixmap()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def ensure(self) -> None:
        w, h = max(self.width(), 1), max(self.height(), 1)
        if not self._raw.isNull() and self._raw.width() == w and self._raw.height() == h:
            return
        self._raw = QPixmap(w, h)
        self._raw.fill(Qt.GlobalColor.black)
        self.paint_fn(self._raw)
        self._blur = blur_pixmap(self._raw, radius=22)

    def sample(self, rect: QRect) -> QPixmap:
        self.ensure()
        r = rect.intersected(QRect(0, 0, self._blur.width(), self._blur.height()))
        if r.isEmpty():
            return QPixmap()
        return self._blur.copy(r)

    def paintEvent(self, _event) -> None:
        self.ensure()
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._raw)
        painter.end()

    def resizeEvent(self, event) -> None:
        self._raw = QPixmap()
        super().resizeEvent(event)


def _stage_of(widget: QWidget) -> Stage | None:
    current = widget.parentWidget()
    while current is not None:
        if isinstance(current, Stage):
            return current
        current = current.parentWidget()
    return None


def paint_mica(painter: QPainter, widget: QWidget, radius: int = 8) -> None:
    rect = widget.rect()
    path = QPainterPath()
    path.addRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    stage = _stage_of(widget)
    if stage is not None:
        top_left = widget.mapTo(stage, rect.topLeft())
        sample = stage.sample(QRect(top_left, rect.size()))
        if not sample.isNull():
            painter.save()
            painter.setClipPath(path)
            painter.drawPixmap(rect.topLeft(), sample)
            painter.restore()
    painter.setClipPath(path)
    grad = QLinearGradient(0, 0, 0, rect.height())
    grad.setColorAt(0.0, PAINT["fill_top"])
    grad.setColorAt(1.0, PAINT["fill_bottom"])
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(grad)
    painter.drawPath(path)
    wash = QLinearGradient(0, 0, 0, max(28, rect.height() * 0.18))
    wash.setColorAt(0.0, QColor(255, 255, 255, 50))
    wash.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setBrush(wash)
    painter.drawRect(QRect(0, 0, rect.width(), int(max(28, rect.height() * 0.18))))
    painter.setClipping(False)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(0, 0, 0, 28), 1))
    painter.drawRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    painter.setPen(QPen(QColor(255, 255, 255, 160), 1))
    painter.drawRoundedRect(QRectF(rect).adjusted(1.5, 1.5, -1.5, -1.5), max(0, radius - 1), max(0, radius - 1))


class GlassPanel(QFrame):
    def __init__(self, parent=None, radius: int = 10):
        super().__init__(parent)
        self._radius = radius
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(PAINT["shadow"])
        self.setGraphicsEffect(shadow)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor("#E3E8EE"), 1))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(rect, self._radius, self._radius)
        painter.end()


class CaptionButton(QPushButton):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(40, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        if self.underMouse() and self.kind == "close":
            painter.fillRect(r, QColor(DOWN))
            ink = QColor("#FFFFFF")
        elif self.underMouse():
            painter.fillRect(r, QColor(0, 0, 0, 18))
            ink = QColor(TEXT)
        else:
            ink = QColor("#5C5C5C")
        painter.setPen(QPen(ink, 1.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx, cy = r.center().x(), r.center().y()
        if self.kind == "close":
            painter.drawLine(cx - 5, cy - 5, cx + 5, cy + 5)
            painter.drawLine(cx + 5, cy - 5, cx - 5, cy + 5)
        elif self.kind == "min":
            painter.drawLine(cx - 6, cy, cx + 6, cy)
        else:
            painter.drawRect(QRect(cx - 5, cy - 5, 10, 10))
        painter.end()


class TitleBar(QWidget):
    moved = Signal(QPoint)
    closed = Signal()
    minimized = Signal()
    maximized = Signal()
    pressed = Signal()

    def __init__(self, title: str, app_id: str, parent=None):
        super().__init__(parent)
        self._drag = None
        self.setFixedHeight(38)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 4, 0)
        row.setSpacing(8)
        icon = QLabel()
        icon.setFixedSize(18, 18)
        icon.setPixmap(icon_pixmap(app_id, 18))
        icon.setStyleSheet("background: transparent;")
        self.title = QLabel(title)
        self.title.setFont(ui_font(12, QFont_weight_demi()))
        self.title.setStyleSheet(f"color: {TEXT}; background: transparent;")
        self.min_btn = CaptionButton("min")
        self.max_btn = CaptionButton("max")
        self.close_btn = CaptionButton("close")
        self.min_btn.clicked.connect(self.minimized.emit)
        self.max_btn.clicked.connect(self.maximized.emit)
        self.close_btn.clicked.connect(self.closed.emit)
        row.addWidget(icon)
        row.addWidget(self.title, stretch=1)
        row.addWidget(self.min_btn)
        row.addWidget(self.max_btn)
        row.addWidget(self.close_btn)

    def setTitle(self, title: str) -> None:
        self.title.setText(title)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = event.globalPosition().toPoint()
            self.pressed.emit()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            now = event.globalPosition().toPoint()
            self.moved.emit(now - self._drag)
            self._drag = now
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximized.emit()
        super().mouseDoubleClickEvent(event)


def QFont_weight_demi():
    from PySide6.QtGui import QFont
    return QFont.Weight.DemiBold


class AppWindow(QFrame):
    raised = Signal(str)
    closed_app = Signal(str)
    minimized_app = Signal(str)

    def __init__(self, app_id: str, title: str, parent=None):
        super().__init__(parent)
        self.app_id = app_id
        self._normal_geo = None
        self._maximized = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.bar = TitleBar(title, app_id)
        self.bar.moved.connect(self._nudge)
        self.bar.pressed.connect(self.lift)
        self.bar.closed.connect(self._close)
        self.bar.minimized.connect(self._minimize)
        self.bar.maximized.connect(self.toggle_max)
        layout.addWidget(self.bar)
        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet("background: rgba(0,0,0,32); border: none;")
        layout.addWidget(rule)
        self.body = QWidget()
        self.body.setObjectName("windowBody")
        self.body.setStyleSheet("QWidget#windowBody { background: transparent; }")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        layout.addWidget(self.body, stretch=1)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 10)
        shadow.setColor(PAINT["shadow"])
        self.setGraphicsEffect(shadow)

    def setTitle(self, title: str) -> None:
        self.bar.setTitle(title)

    def clear_body(self) -> None:
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        paint_mica(painter, self, 8)
        painter.end()

    def lift(self) -> None:
        self.raise_()
        self.raised.emit(self.app_id)

    def mousePressEvent(self, event) -> None:
        self.lift()
        super().mousePressEvent(event)

    def _nudge(self, delta: QPoint) -> None:
        self.lift()
        self.move(self.pos() + delta)
        parent = self.parentWidget()
        if parent is not None:
            x = max(-40, min(self.x(), parent.width() - 80))
            y = max(0, min(self.y(), parent.height() - 60))
            self.move(x, y)
        self._maximized = False

    def _close(self) -> None:
        self.hide()
        self.closed_app.emit(self.app_id)

    def _minimize(self) -> None:
        self.hide()
        self.minimized_app.emit(self.app_id)

    def toggle_max(self) -> None:
        shell = self.parentWidget()
        if shell is None:
            return
        if self._maximized and self._normal_geo is not None:
            self.setGeometry(self._normal_geo)
            self._maximized = False
        else:
            self._normal_geo = self.geometry()
            area = getattr(shell, "work_area", lambda: QRect(8, 8, shell.width() - 16, shell.height() - TASKBAR - 16))()
            self.setGeometry(area)
            self._maximized = True
        self.lift()

    @property
    def is_maximized_window(self) -> bool:
        return self._maximized


class DesktopIcon(QPushButton):
    def __init__(self, app_id: str, parent=None, corporate: bool = False):
        super().__init__(parent)
        self.app_id = app_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(80, 78)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(4)
        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(icon_pixmap(app_id, 42))
        icon.setStyleSheet("background: transparent;")
        name = QLabel(app_label(app_id, corporate=corporate))
        name.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        name.setFont(ui_font(11, QFont_weight_demi()))
        name.setStyleSheet(f"color: {TEXT}; background: transparent;")
        name.setWordWrap(False)
        name.setFixedWidth(80)
        layout.addWidget(icon)
        layout.addWidget(name)


class Toast(GlassPanel):
    def __init__(self, title: str, body: str, parent=None, width: int = 360):
        super().__init__(parent, radius=10)
        self.setFixedWidth(width)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(4)
        kicker = QLabel("Urgent note")
        kicker.setFont(ui_font(10, QFont_weight_demi()))
        kicker.setStyleSheet(f"color: {DOWN}; background: transparent;")
        head = QLabel(title)
        head.setFont(ui_font(14, QFont_weight_demi()))
        head.setStyleSheet(f"color: {TEXT}; background: transparent;")
        head.setWordWrap(True)
        text = QLabel(body)
        text.setFont(ui_font(12))
        text.setStyleSheet("color: #5C5C5C; background: transparent;")
        text.setWordWrap(True)
        layout.addWidget(kicker)
        layout.addWidget(head)
        layout.addWidget(text)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        layout.addLayout(self.actions)

    def add_action(self, label: str, slot, primary: bool = False) -> QPushButton:
        button = QPushButton(label)
        if not primary:
            button.setObjectName("quiet")
        button.setMinimumHeight(30)
        button.clicked.connect(slot)
        self.actions.addWidget(button)
        return button


class WindowManager:
    def __init__(self, shell: QWidget):
        self.shell = shell
        self.windows: dict[str, AppWindow] = {}

    def open(self, app_id: str, title: str, geometry: QRect | None = None) -> AppWindow:
        win = self.windows.get(app_id)
        if win is None:
            win = AppWindow(app_id, title, self.shell)
            win.raised.connect(lambda _i: self.shell.lift_chrome())
            win.closed_app.connect(lambda _i: self.shell.lift_chrome())
            win.minimized_app.connect(lambda _i: self.shell.lift_chrome())
            self.windows[app_id] = win
            if geometry is None:
                geometry = QRect(200, 32, 700, 500)
        else:
            win.setTitle(title)
        if geometry is not None and not win.is_maximized_window:
            # Keep a user-dragged position if the window was already visible.
            if not win.isVisible():
                win.setGeometry(geometry)
        win.show()
        win.lift()
        self.shell.lift_chrome()
        return win

    def close(self, app_id: str) -> None:
        win = self.windows.get(app_id)
        if win is not None:
            win.hide()

    def close_all(self) -> None:
        for win in self.windows.values():
            win.hide()
