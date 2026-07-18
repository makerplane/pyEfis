#  Copyright (c) 2018 Phil Birkelbach
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *

import pyavtools.fix as fix
from pyefis.instruments import helpers


class StaticText(QWidget):
    """Represents a simple static text display.  This is very simple and is
    really just here to keep the individual screens from having to have
    a painter object and a redraw event handler"""

    def __init__(
        self,
        text="",
        fontsize=1.0,
        color=QColor(Qt.GlobalColor.white),
        parent=None,
        font_family="DejaVu Sans Condensed",
    ):
        super(StaticText, self).__init__(parent)
        self.font_family = font_family
        self.font_ghost_mask = None
        self.font_ghost_alpha = 50
        self.alignment = "AlignLeft"
        self.font_percent = fontsize
        self.text = text
        self.color = color
        self.font_mask = None

    def resizeEvent(self, event):
        self.Font = QFont(self.font_family)
        if self.font_mask:
            self.font_size = helpers.fit_to_mask(
                self.width(), self.height(), self.font_mask, self.font_family
            )
            self.Font.setPointSizeF(self.font_size)
        else:
            self.Font.setPixelSize(qRound(self.height() * self.font_percent))
        self.textRect = QRectF(0, 0, self.width(), self.height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)

        # Draw Text
        self.align = getattr(Qt.AlignmentFlag, self.alignment)
        opt = QTextOption(self.align)
        p.setFont(self.Font)
        if self.font_ghost_mask:
            alpha = self.color.alpha()
            self.color.setAlpha(self.font_ghost_alpha)
            pen.setColor(self.color)
            p.setPen(pen)
            p.drawText(self.textRect, self.font_ghost_mask, opt)
            self.color.setAlpha(alpha)

        pen.setColor(self.color)
        p.setPen(pen)
        p.drawText(self.textRect, self.text, opt)


class ValueDisplay(QWidget):
    def __init__(self, parent=None, font_family="Open Sans", font_percent=None):
        super(ValueDisplay, self).__init__(parent)
        self.font_family = font_family
        self.font_ghost_mask = None
        self.font_ghost_alpha = 50
        # Font height as a fraction of the widget height (used when no font_mask
        # is set). Defaults to 0.9; an explicit font_percent overrides it.
        self.font_percent = 0.9 if font_percent is None else font_percent
        # Display format for the value, a digit mask: "" = as-is (str), "000" =
        # rounded + zero-padded to 3 integer digits (089), "000.0" = 3 integer
        # digits + 1 decimal (089.0).
        self.number_format = ""
        self.name = None
        self._dbkey = None
        self._value = 0.0
        self.fail = False
        self.bad = False
        self.old = False
        self.annunciate = False
        self.alignment = "AlignLeft"
        self.conversionFunction = lambda x: x

        # Prefix label drawn before the value (e.g. "HDG", "CRS") with its own
        # font family / size / colour. Empty prefix_text (the default) = no
        # prefix, so a plain value_text is unchanged.
        self.prefix_text = ""
        self.prefix_font_family = "Open Sans"
        self.prefix_font_percent = 50     # percent of widget height
        self.prefix_color = "#ffffff"
        # Colour of the data value in the good/normal state (bad/old still go
        # grey, annunciate still goes red). Default white matches textGoodColor.
        self.value_color = "#ffffff"
        # Optional visual box at the widget bounds: a background fill and a
        # border, each with its own colour + opacity. border_width 0 and
        # bg_opacity 0 (the defaults) = no box, so a plain value_text is
        # unchanged. The box size IS the widget rect (dragged/resized on screen).
        self.border_color = "#ffffff"
        self.border_width = 0       # px (0 = no border)
        self.border_opacity = 100   # percent
        self.bg_color = "#000000"
        self.bg_opacity = 0         # percent (0 = transparent, no background)

        # These properties can be modified by the parent
        self.outlineColor = QColor(Qt.GlobalColor.darkGray)
        # These are the colors that are used when the value's
        # quality is marked as good
        self.bgGoodColor = QColor(Qt.GlobalColor.black)
        self.textGoodColor = QColor(Qt.GlobalColor.white)
        self.highlightGoodColor = QColor(Qt.GlobalColor.magenta)

        # These colors are used for bad and fail
        self.bgBadColor = QColor(Qt.GlobalColor.black)
        self.textBadColor = QColor(Qt.GlobalColor.gray)
        self.highlightBadColor = QColor(Qt.GlobalColor.darkMagenta)

        # Annunciate changes the text color
        self.textAnnunciateColor = QColor(Qt.GlobalColor.red)

        # The following properties should not be changed by the user.
        # These are the colors that are actually used
        # for drawing gauge.
        self.bgColor = self.bgGoodColor
        self.textColor = self.textGoodColor  # Non value text like units
        self.highlightColor = self.highlightGoodColor

        self.font_mask = None

    def resizeEvent(self, event):
        self.font = QFont(self.font_family)
        if self.font_mask:
            self.font_size = helpers.fit_to_mask(
                self.width(), self.height(), self.font_mask, self.font_family
            )
            self.font.setPointSizeF(self.font_size)
        else:
            self.font.setPixelSize(qRound(self.height() * self.font_percent))
        self.valueRect = QRectF(0, 0, self.width(), self.height())
        # Prefix font: its own family + size. prefix_font_percent is a percent of
        # widget height, accepted as a whole number (50) or a fraction (0.5);
        # falls back to the value's font_percent, then 0.5.
        if self.prefix_text:
            self.prefix_font = QFont(self.prefix_font_family or self.font_family)
            pfp = self.prefix_font_percent
            if pfp is None:
                pfp = self.font_percent
            if pfp and float(pfp) > 1:
                pfp = float(pfp) / 100.0
            self.prefix_font.setPixelSize(
                max(1, qRound(self.height() * (float(pfp) if pfp else 0.5))))

    def _paint_box(self, p):
        # Optional visual box at the widget bounds: background fill + border,
        # each with its own colour and opacity. No-op unless a border or a
        # non-transparent background is configured (default = no box).
        bw = int(getattr(self, "border_width", 0) or 0)
        bgo = int(getattr(self, "bg_opacity", 0) or 0)
        if bw <= 0 and bgo <= 0:
            return
        w = float(self.width())
        h = float(self.height())
        p.save()
        if bgo > 0:
            bg = QColor(self.bg_color)
            bg.setAlpha(max(0, min(255, round(255 * bgo / 100.0))))
            p.setBrush(bg)
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
        if bw > 0:
            bc = QColor(self.border_color)
            bo = int(getattr(self, "border_opacity", 100) or 0)
            bc.setAlpha(max(0, min(255, round(255 * bo / 100.0))))
            pen = QPen(bc)
            pen.setWidth(bw)
            p.setPen(pen)
            inset = bw / 2.0
            p.drawRect(QRectF(inset, inset, w - bw, h - bw))
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(0.0, 0.0, w, h))
        p.restore()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._paint_box(p)

        pen = QPen()
        pen.setWidth(int(self.height() * 0.01))
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)

        self.align = getattr(Qt.AlignmentFlag, self.alignment)
        if self.prefix_text:
            self._paint_with_prefix(p, pen)
            return

        # Draw Value
        p.setFont(self.font)
        opt = QTextOption(self.align)
        if self.font_ghost_mask:
            alpha = self.textColor.alpha()
            self.textColor.setAlpha(self.font_ghost_alpha)
            pen.setColor(self.textColor)
            p.setPen(pen)
            p.drawText(self.valueRect, self.font_ghost_mask, opt)
            self.textColor.setAlpha(alpha)

        pen.setColor(self.textColor)
        p.setPen(pen)
        p.drawText(self.valueRect, self.valueText, opt)

    def _paint_with_prefix(self, p, pen):
        # Inline [prefix][space][value] on a shared baseline, the whole block
        # positioned by self.alignment. The prefix uses its own font/colour; the
        # value keeps the quality-driven self.textColor.
        pf = getattr(self, "prefix_font", None) or self.font
        vfm = QFontMetricsF(self.font)
        pfm = QFontMetricsF(pf)
        pre = self.prefix_text
        val = self.valueText
        pre_w = pfm.horizontalAdvance(pre)
        val_w = vfm.horizontalAdvance(val)
        gap = pfm.horizontalAdvance(" ")
        total = pre_w + gap + val_w
        w = float(self.width())
        h = float(self.height())
        if self.alignment == "AlignRight":
            x = w - total
        elif self.alignment == "AlignCenter":
            x = (w - total) / 2.0
        else:
            x = 0.0
        x = max(0.0, x)
        baseline = (h + vfm.ascent() - vfm.descent()) / 2.0
        p.setFont(pf)
        pc = QColor(self.prefix_color) if self.prefix_color else self.textColor
        pen.setColor(pc)
        p.setPen(pen)
        p.drawText(QPointF(x, baseline), pre)
        p.setFont(self.font)
        pen.setColor(self.textColor)
        p.setPen(pen)
        p.drawText(QPointF(x + pre_w + gap, baseline), val)

    def getValue(self):
        return self._value

    def setValue(self, value):
        if self.fail:
            self._value = 0.0
        else:
            cvalue = self.conversionFunction(value)
            if cvalue != self._value:
                self._value = cvalue
                self.setColors()
                self.update()

    value = property(getValue, setValue)

    def getValueText(self):
        if self.fail:
            return "xxx"
        return self._format_value(self.value)

    def _format_value(self, value):
        # number_format is a digit mask: "" = as-is, "000" = rounded +
        # zero-padded to 3 integer digits (089), "000.0" = 3 integer digits +
        # 1 decimal (089.0). The width passed to format() includes the decimal
        # point so the integer part keeps the requested number of digits.
        fmt = getattr(self, "number_format", "") or ""
        if not fmt:
            return str(value)
        try:
            v = float(value)
        except (TypeError, ValueError):
            return str(value)
        if "." in fmt:
            intpart, decpart = fmt.split(".", 1)
            decimals = len(decpart)
            width = len(intpart) + 1 + decimals
            return f"{v:0{width}.{decimals}f}"
        return f"{v:0{len(fmt)}.0f}"

    valueText = property(getValueText)

    def getDbkey(self):
        return self._dbkey

    def setDbkey(self, key):
        self.item = fix.db.get_item(key)
        self.item.reportReceived.connect(self.setupGauge)
        self.item.annunciateChanged.connect(self.annunciateFlag)
        self.item.oldChanged.connect(self.oldFlag)
        self.item.badChanged.connect(self.badFlag)
        self.item.failChanged.connect(self.failFlag)

        self._dbkey = key
        self.setupGauge()

    dbkey = property(getDbkey, setDbkey)

    # This should get called when the gauge is created and then again
    # anytime a new report of the db item is recieved from the server
    def setupGauge(self):
        # min and max should always be set for FIX Gateway data.
        # set the flags
        self.fail = self.item.fail
        self.bad = self.item.bad
        self.old = self.item.old
        self.annunciate = self.item.annunciate
        self.setColors()
        # set the axuliiary data and the value
        self.setValue(self.item.value)

        try:
            self.item.valueChanged[float].disconnect(self.setValue)
            self.item.valueChanged[int].disconnect(self.setValue)
            self.item.valueChanged[bool].disconnect(self.setValue)
            self.item.valueChanged[str].disconnect(self.setValue)
        except TypeError:
            pass  # One will probably fail all the time

        self.item.valueChanged[self.item.dtype].connect(self.setValue)

    def setColors(self):
        # Configurable value colour overrides the good-state default; bad/old
        # (grey) and annunciate (red) still apply below.
        good = self.textGoodColor
        if getattr(self, "value_color", None):
            good = QColor(self.value_color)
        if self.bad or self.fail or self.old:
            self.bgColor = self.bgBadColor
            self.textColor = self.textBadColor
            self.highlightColor = self.highlightBadColor
        else:
            self.bgColor = self.bgGoodColor
            self.textColor = good
            self.highlightColor = self.highlightGoodColor
        if self.annunciate and not self.fail:
            self.textColor = self.textAnnunciateColor

        self.update()

    def annunciateFlag(self, flag):
        self.annunciate = flag
        self.setColors()

    def failFlag(self, flag):
        self.fail = flag
        if flag:
            self.setValue(0.0)
        else:
            self.setValue(fix.db.get_item(self.dbkey).value)
        self.setColors()

    def badFlag(self, flag):
        self.bad = flag
        self.setColors()

    def oldFlag(self, flag):
        self.old = flag
        self.setColors()
