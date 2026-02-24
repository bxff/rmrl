"""
Adapter that makes a QPainter look like ReportLab's canvas.Canvas.

This lets rmrl's pen classes (written for ReportLab) render to a QImage
for raster output with textures, without modifying the pen code.
"""

from PyQt5.QtCore import Qt, QLineF
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QTransform, QPainterPath


class QPainterCanvas:
    """Wraps QPainter to expose ReportLab canvas API."""

    def __init__(self, painter):
        self.painter = painter
        self._pen = QPen()
        self._pen.setCapStyle(Qt.RoundCap)
        self._pen.setJoinStyle(Qt.RoundJoin)
        self._brush = None
        self._states = []

    # ---- State management ----

    def saveState(self):
        self.painter.save()
        self._states.append((QPen(self._pen), self._brush))

    def restoreState(self):
        self.painter.restore()
        if self._states:
            self._pen, self._brush = self._states.pop()

    # ---- Line properties ----

    def setLineCap(self, cap):
        """ReportLab cap: 0=butt, 1=round, 2=square"""
        caps = {0: Qt.FlatCap, 1: Qt.RoundCap, 2: Qt.SquareCap}
        self._pen.setCapStyle(caps.get(cap, Qt.RoundCap))

    def setLineJoin(self, join):
        """ReportLab join: 0=miter, 1=round, 2=bevel"""
        joins = {0: Qt.MiterJoin, 1: Qt.RoundJoin, 2: Qt.BevelJoin}
        self._pen.setJoinStyle(joins.get(join, Qt.RoundJoin))

    def setLineWidth(self, w):
        self._pen.setWidthF(max(0.01, w))
        self._brush = None  # revert to solid color

    def setStrokeColor(self, color, alpha=1.0):
        if isinstance(color, (list, tuple)):
            r, g, b = [max(0, min(255, int(c * 255))) for c in color[:3]]
            self._pen.setColor(QColor(r, g, b, int(alpha * 255)))
        else:
            self._pen.setColor(QColor(color))
        self._brush = None  # revert to solid color

    # ---- Texture support (for raster pen modes) ----

    def setTextureBrush(self, texture_image, transform=None):
        """Set a texture brush for the next line draw."""
        brush = QBrush()
        brush.setTextureImage(texture_image)
        if transform is not None:
            brush.setTransform(transform)
        self._brush = brush

    # ---- Drawing ----

    def line(self, x1, y1, x2, y2):
        pen = QPen(self._pen)
        if self._brush:
            pen.setBrush(self._brush)
        self.painter.setPen(pen)
        self.painter.drawLine(QLineF(x1, y1, x2, y2))

    # ---- Path support (for highlighter) ----

    def beginPath(self):
        return _PathProxy()

    def drawPath(self, path_proxy, stroke=1, fill=0):
        pen = QPen(self._pen)
        if self._brush:
            pen.setBrush(self._brush)
        self.painter.setPen(pen)
        if fill:
            self.painter.setBrush(QBrush(self._pen.color()))
        else:
            self.painter.setBrush(Qt.NoBrush)
        self.painter.drawPath(path_proxy._path)


class _PathProxy:
    """Mimics ReportLab's path object."""
    def __init__(self):
        self._path = QPainterPath()

    def moveTo(self, x, y):
        self._path.moveTo(x, y)

    def lineTo(self, x, y):
        self._path.lineTo(x, y)
