#  Copyright (c) 2024 Bill Mallard
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.

from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPolygon
from PyQt6.QtCore import Qt, QRect, QPoint, qRound
from PyQt6.QtWidgets import QWidget

import pyavtools.fix as fix


class WindDisplay(QWidget):
    """Displays headwind and crosswind components as two compact rows.

    Subscribes to HWIND and XWIND FIX database keys.
    HWIND > 0 = headwind, < 0 = tailwind.
    XWIND > 0 = from right, < 0 = from left.
    """

    def __init__(self, parent=None, font_family="DejaVu Sans Condensed"):
        super(WindDisplay, self).__init__(parent)
        self.font_family = font_family

        self._hwind = 0.0
        self._xwind = 0.0
        self._hwind_fail = True
        self._hwind_bad = False
        self._xwind_fail = True
        self._xwind_bad = False

        # Default font sizes (overridden in resizeEvent)
        self._row_h = 10
        self._lbl_font = QFont(self.font_family)
        self._val_font = QFont(self.font_family)
        self._arrow_size = 4

        try:
            self._hwind_item = fix.db.get_item("HWIND")
            self._xwind_item = fix.db.get_item("XWIND")
        except KeyError:
            # HWIND/XWIND not available — display dashes, no signals
            return

        self._hwind = self._hwind_item.value
        self._xwind = self._xwind_item.value
        self._hwind_fail = self._hwind_item.fail
        self._xwind_fail = self._xwind_item.fail

        self._hwind_item.valueChanged[float].connect(
            self._on_hwind_changed, Qt.ConnectionType.UniqueConnection
        )
        self._xwind_item.valueChanged[float].connect(
            self._on_xwind_changed, Qt.ConnectionType.UniqueConnection
        )
        self._hwind_item.failChanged.connect(
            self._on_hwind_fail, Qt.ConnectionType.UniqueConnection
        )
        self._xwind_item.failChanged.connect(
            self._on_xwind_fail, Qt.ConnectionType.UniqueConnection
        )
        self._hwind_item.badChanged.connect(
            self._on_hwind_bad, Qt.ConnectionType.UniqueConnection
        )
        self._xwind_item.badChanged.connect(
            self._on_xwind_bad, Qt.ConnectionType.UniqueConnection
        )

    def _on_hwind_changed(self, value):
        self._hwind = value
        self.update()

    def _on_xwind_changed(self, value):
        self._xwind = value
        self.update()

    def _on_hwind_fail(self, fail):
        self._hwind_fail = fail
        self.update()

    def _on_xwind_fail(self, fail):
        self._xwind_fail = fail
        self.update()

    def _on_hwind_bad(self, bad):
        self._hwind_bad = bad
        self.update()

    def _on_xwind_bad(self, bad):
        self._xwind_bad = bad
        self.update()

    def resizeEvent(self, event):
        row_h = self.height() // 2
        lbl_px = max(6, qRound(row_h * 0.28))
        val_px = max(8, qRound(row_h * 0.52))
        self._row_h = row_h
        self._lbl_font = QFont(self.font_family)
        self._lbl_font.setPixelSize(lbl_px)
        self._val_font = QFont(self.font_family)
        self._val_font.setPixelSize(val_px)
        self._arrow_size = max(4, qRound(row_h * 0.28))

    def _draw_row(self, p, y, label, value, fail, bad, arrow_up, arrow_right):
        w = self.width()
        rh = self._row_h
        sz = self._arrow_size

        p.fillRect(QRect(0, y, w, rh), QColor(20, 20, 20))

        if fail:
            text_color = QColor(100, 100, 100)
            arrow_color = QColor(80, 80, 80)
        elif bad:
            text_color = QColor(255, 165, 0)
            arrow_color = QColor(200, 130, 0)
        else:
            text_color = QColor(Qt.GlobalColor.white)
            arrow_color = QColor(0, 200, 200)

        # Label
        lbl_w = qRound(w * 0.30)
        p.setFont(self._lbl_font)
        p.setPen(QPen(QColor(180, 180, 180)))
        p.drawText(
            QRect(2, y, lbl_w, rh),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )

        # Arrow
        arrow_x = lbl_w + qRound(w * 0.12)
        arrow_cy = y + rh // 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(arrow_color))

        if not fail:
            if arrow_up is not None:
                if arrow_up:
                    pts = [
                        QPoint(arrow_x, arrow_cy - sz),
                        QPoint(arrow_x - sz, arrow_cy + sz // 2),
                        QPoint(arrow_x + sz, arrow_cy + sz // 2),
                    ]
                else:
                    pts = [
                        QPoint(arrow_x, arrow_cy + sz),
                        QPoint(arrow_x - sz, arrow_cy - sz // 2),
                        QPoint(arrow_x + sz, arrow_cy - sz // 2),
                    ]
                p.drawPolygon(QPolygon(pts))
            elif arrow_right is not None:
                if arrow_right:
                    pts = [
                        QPoint(arrow_x + sz, arrow_cy),
                        QPoint(arrow_x - sz // 2, arrow_cy - sz),
                        QPoint(arrow_x - sz // 2, arrow_cy + sz),
                    ]
                else:
                    pts = [
                        QPoint(arrow_x - sz, arrow_cy),
                        QPoint(arrow_x + sz // 2, arrow_cy - sz),
                        QPoint(arrow_x + sz // 2, arrow_cy + sz),
                    ]
                p.drawPolygon(QPolygon(pts))

        # Value
        val_x = lbl_w + qRound(w * 0.27)
        val_w = w - val_x - 2
        p.setFont(self._val_font)
        p.setPen(QPen(text_color))
        val_str = "---" if fail else f"{abs(value):.0f}"
        p.drawText(
            QRect(val_x, y, val_w, rh),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            val_str,
        )

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        hw_up = None if self._hwind_fail else (self._hwind >= 0)
        self._draw_row(
            p, 0, "HW", self._hwind,
            self._hwind_fail, self._hwind_bad,
            arrow_up=hw_up, arrow_right=None,
        )

        # XWIND > 0 = from right → arrow points left (←, arrow_right=False)
        xw_right = None if self._xwind_fail else (self._xwind < 0)
        self._draw_row(
            p, self._row_h, "XW", self._xwind,
            self._xwind_fail, self._xwind_bad,
            arrow_up=None, arrow_right=xw_right,
        )

        sep_pen = QPen(QColor(60, 60, 60), 1)
        p.setPen(sep_pen)
        p.drawLine(0, self._row_h, self.width(), self._row_h)
