#  Copyright (c) 2024 Bill Mallard
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.

from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtCore import Qt, QRect, qRound
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
        # Label and value share one small font — wind is supplemental info.
        px = max(6, qRound(row_h * 0.40))
        self._row_h = row_h
        self._lbl_font = QFont(self.font_family)
        self._lbl_font.setPixelSize(px)
        self._val_font = QFont(self.font_family)
        self._val_font.setPixelSize(px)

    # Sign deadband: values within ±DEADBAND_KT round to 0 and display with the
    # positive-axis label. Avoids label flicker from sensor noise around zero.
    DEADBAND_KT = 0.5

    def _hw_label(self, value, fail):
        if fail:
            return "HW"
        return "TW" if value < -self.DEADBAND_KT else "HW"

    def _xw_label(self, value, fail):
        if fail:
            return "RX"
        return "LX" if value < -self.DEADBAND_KT else "RX"

    def _draw_row(self, p, y, label, value, fail, bad):
        w = self.width()
        rh = self._row_h

        if fail:
            text_color = QColor(100, 100, 100)
        elif bad:
            text_color = QColor(255, 165, 0)
        else:
            text_color = QColor(Qt.GlobalColor.white)

        # Use the actual label-text width so the value sits snug against the
        # label — leaves the rest of the row (plenty for 3-digit values) on the
        # right. All labels are 2 chars; "HW" is widest in the proportional
        # font we use, so measure that.
        p.setFont(self._lbl_font)
        fm = p.fontMetrics()
        label_x = 7
        label_box_w = fm.horizontalAdvance("HW")
        gap = max(3, fm.horizontalAdvance(" "))

        p.setPen(QPen(text_color))
        p.drawText(
            QRect(label_x, y, label_box_w, rh),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            label,
        )

        val_x = label_x + label_box_w + gap
        val_w = w - val_x - 2
        p.setFont(self._val_font)
        p.setPen(QPen(text_color))
        if fail:
            val_str = "---"
        elif bad:
            val_str = "X"
        else:
            val_str = f"{abs(round(value))}"
        p.drawText(
            QRect(val_x, y, val_w, rh),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            val_str,
        )

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._draw_row(
            p, 0,
            self._hw_label(self._hwind, self._hwind_fail),
            self._hwind, self._hwind_fail, self._hwind_bad,
        )
        # Tighten vertical spacing — second row stacks at ~0.65 row_h instead
        # of 1.0, pulling it ~10-15 px closer for typical PFD sizing.
        self._draw_row(
            p, qRound(self._row_h * 0.65),
            self._xw_label(self._xwind, self._xwind_fail),
            self._xwind, self._xwind_fail, self._xwind_bad,
        )

