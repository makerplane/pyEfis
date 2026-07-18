#  Copyright (c) 2013 Neil Domalik, 2018-2019 Garrett Herschleb
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

import time

from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *

import pyavtools.fix as fix

from pyefis.instruments.NumericalDisplay import NumericalDisplay
import pyefis.hmi as hmi
from pyefis.instruments import helpers


class Altimeter(QWidget):
    FULL_WIDTH = 300

    def __init__(
        self, parent=None, bg_color=Qt.GlobalColor.black, font_family="DejaVu Sans Condensed"
    ):
        super(Altimeter, self).__init__(parent)
        # Transparent widget background so bg_opacity < 1 reveals what's behind.
        self.setStyleSheet("background: transparent; border: 0px")
        self.font_family = font_family
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._altimeter = 0
        self.bg_color = bg_color
        self.bg_opacity = 100  # percent (100 = solid, the default)
        self.item = fix.db.get_item("ALT")
        self.item.valueChanged[float].connect(self.setAltimeter)
        self.item.oldChanged[bool].connect(self.repaint)
        self.item.badChanged[bool].connect(self.repaint)
        self.item.failChanged[bool].connect(self.repaint)

        self.conversionFunction1 = lambda x: x
        self.conversionFunction2 = lambda x: x
        self.conversionFunction = lambda x: x

    def getRatio(self):
        # Return X for 1:x specifying the ratio for this instrument
        return 1

    # TODO We continuously draw things that don't change.  Should draw the
    # background save to pixmap or something and then blit it and draw arrows.
    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        dial = QPainter(self)
        dial.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = int(round(min(w, h) * 0.45))
        diameter = radius * 2
        center_x = w / 2
        center_y = h / 2

        # Draw the background (bg_opacity percent < 100 lets what's behind show)
        _bg = QColor(self.bg_color)
        _bg.setAlphaF(max(0.0, min(1.0, float(getattr(self, "bg_opacity", 100)) / 100.0)))
        dial.fillRect(0, 0, w, h, _bg)
        dialPen = QPen()
        # Setup Pens
        if self.item.old or self.item.bad:
            warn_font = QFont(self.font_family, 30, QFont.Weight.Bold)
            dialPen.setColor(QColor(Qt.GlobalColor.gray))
            dialBrush = QBrush(QColor(Qt.GlobalColor.gray))
        else:
            dialPen.setColor(QColor(Qt.GlobalColor.white))
            dialBrush = QBrush(QColor(Qt.GlobalColor.white))
        dialPen.setWidth(2)

        # Dial Setup
        dial.setPen(dialPen)
        dial.drawEllipse(
            QRectF(center_x - radius, center_y - radius, diameter, diameter)
        )

        f = QFont(self.font_family)
        fs = int(round(20 * w / self.FULL_WIDTH))
        f.setPixelSize(fs)
        fontMetrics = QFontMetricsF(f)
        dial.setFont(f)
        dial.setPen(dialPen)
        dial.setBrush(dialBrush)

        dial.translate(w / 2, h / 2)
        count = 0
        altimeter_numbers = 0
        while count < 360:
            dial.drawLine(0, -(radius), 0, -(radius - 15))
            x = fontMetrics.horizontalAdvance(str(altimeter_numbers)) / 2
            y = f.pixelSize()
            dial.drawText(
                qRound(-x), qRound(-(radius - 15 - y)), str(altimeter_numbers)
            )
            altimeter_numbers += 1

            dial.rotate(36)
            count += 36
        count = 0
        while count < 360:
            dial.drawLine(0, -(radius), 0, -(radius - 10))

            dial.rotate(7.2)
            count += 7.2

        if self.item.fail:
            warn_font = QFont(self.font_family, 30, QFont.Weight.Bold)
            dial.resetTransform()
            dial.setPen(QPen(QColor(Qt.GlobalColor.red)))
            dial.setBrush(QBrush(QColor(Qt.GlobalColor.red)))
            dial.setFont(warn_font)
            dial.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, "XXX")
            return

        dial.setBrush(dialBrush)
        # Needle Movement
        sm_dial = QPolygonF(
            [QPointF(5, 0), QPointF(0, +5), QPointF(-5, 0), QPointF(0, -(radius - 15))]
        )
        lg_dial = QPolygonF(
            [
                QPointF(10, -(radius / 9)),
                QPointF(5, 0),
                QPointF(0, +5),
                QPointF(-5, 0),
                QPointF(-10, -(radius / 9)),
                QPointF(0, -int(round((radius * 0.6)))),
            ]
        )
        outside_dial = QPolygonF(
            [
                QPointF(7.5, -(radius)),
                QPointF(-7.5, -(radius)),
                QPointF(0, -(radius - 10)),
            ]
        )

        sm_dial_angle = self._altimeter * 0.36 - 7.2
        lg_dial_angle = self._altimeter / 10 * 0.36 - 7.2
        outside_dial_angle = self._altimeter / 100 * 0.36 - 7.2

        dial.rotate(sm_dial_angle)
        dial.drawPolygon(sm_dial)
        dial.rotate(-sm_dial_angle)
        dial.rotate(lg_dial_angle)
        dial.drawPolygon(lg_dial)
        dial.rotate(-lg_dial_angle)
        dial.rotate(outside_dial_angle)
        dial.drawPolygon(outside_dial)

        """ Not sure if this is needed
        if self.item.bad:
            dial.resetTransform()
            dial.setPen (QPen(QColor(255, 150, 0)))
            dial.setBrush (QBrush(QColor(255, 150, 0)))
            dial.setFont (warn_font)
            dial.drawText (0,0,w,h, Qt.AlignmentFlag.AlignCenter, "BAD")
        elif self.item.old:
            dial.resetTransform()
            dial.setPen (QPen(QColor(255, 150, 0)))
            dial.setBrush (QBrush(QColor(255, 150, 0)))
            dial.setFont (warn_font)
            dial.drawText (0,0,w,h, Qt.AlignmentFlag.AlignCenter, "OLD")
        """

    def setUnitSwitching(self):
        """When this function is called the unit switching features are used"""
        self.__currentUnits = 1
        self.unitsOverride = self.unitsOverride1
        self.conversionFunction = self.conversionFunction1
        hmi.actions.setInstUnits.connect(self.setUnits)
        self.update()

    def setUnits(self, args):
        x = args.split(":")
        command = x[1].lower()
        names = x[0].split(",")
        if self.item.key in names or "*" in names or self.unitGroup in names:
            # item = fix.db.get_item(self.dbkey)
            if command == "toggle":
                if self.__currentUnits == 1:
                    self.unitsOverride = self.unitsOverride2
                    self.conversionFunction = self.conversionFunction2
                    self.__currentUnits = 2
                else:
                    self.unitsOverride = self.unitsOverride1
                    self.conversionFunction = self.conversionFunction1
                    self.__currentUnits = 1
            # self.setAuxData(item.aux) # Trigger conversion for aux data
            self.altimeter = self.item.value  # Trigger the conversion for value

    def getAltimeter(self):
        return self._altimeter

    def setAltimeter(self, altimeter):
        cvalue = self.conversionFunction(altimeter)
        if cvalue != self._altimeter:
            self._altimeter = cvalue
            self.update()

    altimeter = property(getAltimeter, setAltimeter)


class Altimeter_Tape(QGraphicsView):
    def __init__(
        self,
        parent=None,
        dbkey="ALT",
        maxalt=50000,
        fontsize=15,
        font_percent=None,
        font_family="DejaVu Sans Condensed",
        majorDiv=200,
        minorDiv=100,
        total_decimals=5,
        font_mask="00000",
        round_to=0,
        numeric_box=True,
        font_scale=1.0,
        show_trend=None,
        trend_lookahead=6.0,
        trend_window=3.0,
        trend_min_change=20.0,
    ):
        super(Altimeter_Tape, self).__init__(parent)
        # Checkbox option: alpha-fade the scrolling scale into the
        # background over the top/bottom 15% of the tape.
        self.edge_fade = False
        self.setStyleSheet("background: transparent")
        self.font_family = font_family
        self.font_mask = font_mask
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.font_percent = font_percent
        if self.font_percent:
            self.fontsize = qRound(self.width() * self.font_percent)
            self.pph = self.fontsize / 50
        else:
            self.fontsize = fontsize
            self.pph = 0.3

        self.item = fix.db.get_item(dbkey)
        self._altimeter = self.item.value
        self.backgroundOpacity = 0.3
        self.foregroundOpacity = 0.6
        self.majorDiv = majorDiv
        self.minorDiv = minorDiv

        self.maxalt = maxalt
        self._maxalt = maxalt
        self.total_decimals = total_decimals
        # Round the value shown in the numeric box to this step (0 = off). For a
        # jittery source like VS, rounding to e.g. 100 makes the box snap in
        # 100-fpm steps instead of the digits scrolling continuously; the tape
        # scroll itself stays smooth (it uses the unrounded value).
        self.round_to = round_to
        # When False, the embedded numeric readout box is omitted entirely and
        # only the scrolling tape (with its fixed read pointer) is shown.
        self.numeric_box = numeric_box
        # Multiplier on the tape's scale-number (tick label) font size.
        self.font_scale = font_scale
        self.myparent = parent

        # 6-second altitude-trend indicator (AC 23.1311-1C sec 17.8.b): a cyan
        # vector predicting where the altitude will be trend_lookahead seconds
        # ahead, for level-off look-ahead. It is an ALTITUDE cue, so default it
        # on only for an ALT tape -- a VS tape shares this class and should not
        # sprout a trend-of-VS. An explicit show_trend (config/caller) always wins.
        self.show_trend = (dbkey == "ALT") if show_trend is None else show_trend
        self.trend_lookahead = trend_lookahead
        self.trend_window = trend_window
        self.trend_min_change = trend_min_change
        self._trend_history = []   # (monotonic_time, altitude) samples
        self._trend_px = 0.0

        self.conversionFunction1 = lambda x: x
        self.conversionFunction2 = lambda x: x
        self.conversionFunction = lambda x: x

    def resizeEvent(self, event):
        if self.font_percent:
            self.fontsize = qRound(self.width() * self.font_percent)
        self.pph = self.height() / 1000
        w = self.width()
        w_2 = w / 2
        h = self.height()
        f = QFont(self.font_family)
        if self.font_mask:
            self.font_size = helpers.fit_to_mask(
                self.width() * 0.55,
                self.height() * 0.05,
                self.font_mask,
                self.font_family,
            )
            f.setPointSizeF(self.font_size * self.font_scale)
        else:
            f.setPixelSize(qRound(self.fontsize * self.font_scale))
        self.height_pixel = (
            self.maxalt * 2 * self.pph + h
        )  # + abs(self.minalt*self.pph)
        dialPen = QPen(QColor(Qt.GlobalColor.white))
        dialPen.setWidth(int(self.height() * 0.005))

        self.scene = QGraphicsScene(0, 0, w, self.height_pixel)
        x = self.scene.addRect(
            0,
            0,
            w,
            self.height_pixel,
            QPen(QColor(32, 32, 32)),
            QBrush(QColor(32, 32, 32)),
        )
        x.setOpacity(self.backgroundOpacity)

        for i in range(self.maxalt * 2, -1, -self.minorDiv):
            y = self.y_offset(i)
            alt = i - self.maxalt
            # Three tick tiers denoting the standard increments (AC 23.1311-1C
            # sec 17.8.a): 1,000-ft longest, 500-ft intermediate, minorDiv short.
            # Labels ride every 1,000-ft tick and every majorDiv tick, so a
            # config's chosen label spacing is preserved while the 500/1,000-ft
            # sense of altitude is reinforced.
            if alt % 1000 == 0:
                tick_x0 = w_2                       # longest
                labeled = True
            elif alt % 500 == 0:
                tick_x0 = w_2 + 15                  # intermediate
                labeled = (alt % self.majorDiv == 0)
            elif alt % self.majorDiv == 0:
                tick_x0 = w_2 + 15                  # labeled major
                labeled = True
            else:
                tick_x0 = w_2 + 30                  # short minor
                labeled = False
            l = self.scene.addLine(tick_x0, y, w, y, dialPen)
            l.setOpacity(self.foregroundOpacity)
            if labeled:
                t = self.scene.addText(str(alt))
                t.setFont(f)
                self.scene.setFont(f)
                t.setDefaultTextColor(QColor(Qt.GlobalColor.white))
                t.setX(0)
                t.setY(y - t.boundingRect().height() / 2)
                t.setOpacity(self.foregroundOpacity)
        self.setScene(self.scene)

        nbh = w / 1.20
        box_w = qRound(w / 1.20)
        self.numeric_box_pos = QPoint(0, qRound(h / 2 - (nbh / 1.45) / 2))
        if self.numeric_box:
            self.numerical_display = NumericalDisplay(
                self, total_decimals=self.total_decimals, scroll_decimal=2
            )
            self.numerical_display.resize(box_w, qRound(nbh / 1.45))
            self.numerical_display.move(self.numeric_box_pos)
            self.numerical_display.show()
            self.numerical_display.value = self._altimeter
        else:
            self.numerical_display = None
        # Read-pointer position (drawn in paintEvent) — same spot whether or not
        # the numeric box is shown, so the tape stays readable.
        self.numeric_box_pos.setX(self.numeric_box_pos.x() + box_w)
        self.numeric_box_pos.setY(
            qRound(self.numeric_box_pos.y() + (nbh / 1.45) / 2) + 1
        )
        self.centerOn(
            self.scene.width() / 2, self.y_offset(self._altimeter + self.maxalt)
        )
        self.setAltOld(self.item.old)
        self.setAltBad(self.item.bad)
        self.setAltFail(self.item.fail)
        self.item.valueChanged[float].connect(self.setAltimeter)
        self.item.oldChanged[bool].connect(self.setAltOld)
        self.item.badChanged[bool].connect(self.setAltBad)
        self.item.failChanged[bool].connect(self.setAltFail)

    def y_offset(self, alt):
        return self.height_pixel - (alt * self.pph) - self.height()

    def redraw(self):
        if not self.isVisible():
            return
        self.resetTransform()
        self.centerOn(
            self.scene.width() / 2, self.y_offset(self._altimeter + self.maxalt)
        )
        if self.numerical_display is not None:
            if self.round_to:
                self.numerical_display.value = (
                    round(self._altimeter / self.round_to) * self.round_to
                )
            else:
                self.numerical_display.value = self._altimeter

    #  Index Line that doesn't move to make it easy to read the altimeter.
    def paintEvent(self, event):
        # edge_fade (percent of height, 0 = off): melt the scrolling
        # scale in/out at the top and bottom instead of hard-clipping.
        _fade = bool(getattr(self, "edge_fade", False))
        if _fade > 0:
            helpers.render_view_edge_faded(self, 15.0)
        else:
            super(Altimeter_Tape, self).paintEvent(event)
        w = self.width()
        h = self.height()
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        marks = QPen(Qt.GlobalColor.white, 1)
        p.translate(self.numeric_box_pos.x(), self.numeric_box_pos.y())
        p.setPen(marks)
        p.setBrush(QBrush(Qt.GlobalColor.black))
        triangle_size = w / 8
        p.drawConvexPolygon(
            QPolygonF(
                [
                    QPointF(0, -triangle_size),
                    QPointF(0, triangle_size),
                    QPointF(triangle_size, 0),
                ]
            )
        )

        # Altitude-trend vector (AC 23.1311-1C sec 17.8.b) -- a cyan look-ahead
        # from the read pointer: up when climbing, down when descending. Only
        # shown once it clears a noise floor so a level-flight jitter stays quiet.
        if self.show_trend:
            noise_floor_px = self.trend_min_change * self.pph
            if abs(self._trend_px) >= noise_floor_px:
                trend_color = QColor(0, 220, 255)
                line_w = max(2, qRound(w / 40))
                p.setPen(QPen(trend_color, line_w))
                p.setBrush(QBrush(trend_color))
                max_trend_px = qRound(h * 0.45)
                trend_y = max(-max_trend_px, min(max_trend_px, qRound(-self._trend_px)))
                x0 = qRound(triangle_size * 1.3)
                p.drawLine(x0, 0, x0, trend_y)
                arrow = max(3, qRound(w / 14))
                if trend_y < 0:      # climbing
                    tip = [QPointF(x0, trend_y),
                           QPointF(x0 - arrow, trend_y + arrow),
                           QPointF(x0 + arrow, trend_y + arrow)]
                else:                # descending
                    tip = [QPointF(x0, trend_y),
                           QPointF(x0 - arrow, trend_y - arrow),
                           QPointF(x0 + arrow, trend_y - arrow)]
                p.drawPolygon(QPolygonF(tip))

    def setUnitSwitching(self):
        """When this function is called the unit switching features are used"""
        self.__currentUnits = 1
        self.unitsOverride = self.unitsOverride1
        self.conversionFunction = self.conversionFunction1
        hmi.actions.setInstUnits.connect(self.setUnits)
        if self.isVisible():
            self.update()

    def setUnits(self, args):
        x = args.split(":")
        command = x[1].lower()
        names = x[0].split(",")
        if self.item.key in names or "*" in names or self.unitGroup in names:
            # item = fix.db.get_item(self.dbkey)
            if command == "toggle":
                if self.__currentUnits == 1:
                    self.unitsOverride = self.unitsOverride2
                    self.conversionFunction = self.conversionFunction2
                    self.__currentUnits = 2
                else:
                    self.unitsOverride = self.unitsOverride1
                    self.conversionFunction = self.conversionFunction1
                    self.__currentUnits = 1
            # self.setAuxData(item.aux) # Trigger conversion for aux data
            self.altimeter = self.item.value  # Trigger the conversion for value

    def getAltimeter(self):
        return self._altimeter

    def _push_trend(self, now, value):
        """Update the trend history and derive self._trend_px -- the look-ahead
        offset in scene pixels (positive = climbing -> vector up)."""
        self._trend_history.append((now, value))
        cutoff = now - self.trend_window
        while self._trend_history and self._trend_history[0][0] < cutoff:
            self._trend_history.pop(0)
        if len(self._trend_history) >= 2:
            t0, v0 = self._trend_history[0]
            t1, v1 = self._trend_history[-1]
            dt = t1 - t0
            if dt >= 0.1:
                rate = (v1 - v0) / dt                       # units per second
                self._trend_px = rate * self.trend_lookahead * self.pph
            else:
                self._trend_px = 0.0
        else:
            self._trend_px = 0.0

    def setAltimeter(self, altimeter):
        cvalue = self.conversionFunction(altimeter)
        if self.show_trend:
            self._push_trend(time.monotonic(), cvalue)
        if cvalue != self._altimeter:
            self._altimeter = cvalue
            self.redraw()
        elif self.show_trend:
            # value unchanged but the trend may have decayed -- repaint the cue.
            self.viewport().update()

    altimeter = property(getAltimeter, setAltimeter)

    def setAltOld(self, b):
        if self.numerical_display is not None:
            self.numerical_display.old = b

    def setAltBad(self, b):
        if self.numerical_display is not None:
            self.numerical_display.bad = b

    def setAltFail(self, b):
        if self.numerical_display is not None:
            self.numerical_display.fail = b

    # We don't want this responding to keystrokes
    def keyPressEvent(self, event):
        pass

    # Don't want it acting with the mouse scroll wheel either
    def wheelEvent(self, event):
        pass
