#  Copyright (c) 2013 Neil Domalik, Phil Birkelbach; 2018 Garrett Herschleb
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


try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *

import fix


class VSI(QWidget):
    FULL_WIDTH = 300
    def __init__(self, parent=None, fontsize=20):
        super(VSI, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setFocusPolicy(Qt.NoFocus)
        self.fontSize = fontsize
        self._roc = 0
        self.maxRange = 2000
        self.maxAngle = 170.0
        self.item = fix.db.get_item("VS")
        self.item.valueChanged[float].connect(self.setROC)
        self.item.oldChanged[bool].connect(self.repaint)
        self.item.badChanged[bool].connect(self.repaint)
        self.item.failChanged[bool].connect(self.repaint)

    def resizeEvent(self, event):
        self.background = QPixmap(self.width(), self.height())
        self.r = min(self.width(), self.height()) / 2 - 25
        f = QFont()
        fs = int(round(self.fontSize * self.width() / self.FULL_WIDTH))
        f.setPixelSize(fs)
        fm = QFontMetrics(f)
        p = QPainter(self.background)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(f)
        pen = QPen(QColor(Qt.white))
        pen.setWidth(2)
        p.setPen(pen)
        self.center = QPointF(p.device().width() / 2, p.device().height() / 2)

        p.fillRect(0, 0, self.width(), self.height(), Qt.black)
        p.drawEllipse(self.center, self.r, self.r)

        # Draw tick marks and text
        # ##### This should be condensed#########
        tickCount = self.maxRange // 100
        tickAngle = self.maxAngle / float(tickCount)
        longLine = QLine(0, -self.r, 0, -(self.r - self.fontSize))
        shortLine = QLine(0, -self.r, 0, -(self.r - self.fontSize / 2))
        textRect = QRect(-40, -self.r + self.fontSize, 80, self.fontSize + 10)
        textRInv = QRect(40, self.r - self.fontSize, -80, -self.fontSize - 10)

        pixelsWide = fm.width("0")
        pixelsHigh = fm.height()
        p.translate(self.center)
        p.save()
        p.rotate(-90)
        p.drawLine(longLine)
        transform = QTransform()
        transform.translate(p.device().width() / 2,
                            p.device().height() / 2)
        transform.translate(- self.r + self.fontSize + 5,
                            - pixelsHigh / 2)
        p.setTransform(transform)
        p.drawText(0, 0, pixelsWide, pixelsHigh,
                   Qt.AlignCenter, '0')

        pixelsWide = fm.width("2.0")
        transform = QTransform()
        transform.translate(p.device().width() / 2,
                            p.device().height() / 2)
        transform.translate(self.r - self.fontSize - pixelsWide,
                            - pixelsHigh / 2)
        p.setTransform(transform)
        p.drawText(0, 0, pixelsWide, pixelsHigh,
                   Qt.AlignCenter, '2.0')

        p.restore()
        p.rotate(-90)
        for each in range(1, tickCount + 1):
            p.rotate(tickAngle)
            if each % 5 == 0:
                p.drawLine(longLine)
                if each != 20:
                    p.drawText(textRect, Qt.AlignCenter,
                               str(each))
            else:
                p.drawLine(shortLine)

        p.rotate(-self.maxAngle)
        for each in range(1, tickCount + 1):
            p.rotate(-tickAngle)
            if each % 5 == 0:
                p.drawLine(longLine)
                if each != 20:
                    p.scale(-1.0, -1.0)
                    p.drawText(textRInv, Qt.AlignCenter,
                               str(each))
                    p.scale(-1.0, -1.0)
            else:
                p.drawLine(shortLine)

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        dial = QPainter(self)
        dial.setRenderHint(QPainter.Antialiasing)

        # Draw the Black Background
        dial.fillRect(0, 0, w, h, Qt.black)

        # Insert Background
        dial.drawPixmap(0, 0, self.background)

        # Setup Pens
        f = QFont()
        f.setPixelSize(self.fontSize)

        if self.item.old or self.item.bad:
            warn_font = QFont("FixedSys", 30, QFont.Bold)
            dialPen = QPen(QColor(Qt.gray))
            dialBrush = QBrush(QColor(Qt.gray))
        else:
            dialPen = QPen(QColor(Qt.white))
            dialBrush = QBrush(QColor(Qt.white))
        dialPen.setWidth(2)
        dial.setPen(dialPen)
        dial.setFont(f)
        dial.setBrush(dialBrush)

        if self.item.fail:
            warn_font = QFont("FixedSys", 30, QFont.Bold)
            dial.resetTransform()
            dial.setPen (QPen(QColor(Qt.red)))
            dial.setBrush (QBrush(QColor(Qt.red)))
            dial.setFont (warn_font)
            dial.drawText (0,0,w,h, Qt.AlignCenter, "XXX")
            return

        # Needle Movement
        needle = QPolygon([QPoint(5, 0), QPoint(0, +5), QPoint(-5, 0),
                          QPoint(0, -(h / 2 - 60))])

        # dial_angle = self._roc * -0.0338 # 135deg / 4000 fpm
        dial_angle = self._roc * (self.maxAngle / self.maxRange)
        dial.translate(self.center)
        dial.rotate(dial_angle - 90)
        dial.drawPolygon(needle)

        """ This might not be needed:
        if self.item.bad:
            dial.resetTransform()
            dial.setPen (QPen(QColor(255, 150, 0)))
            dial.setBrush (QBrush(QColor(255, 150, 0)))
            dial.setFont (warn_font)
            dial.drawText (0,0,w,h, Qt.AlignCenter, "BAD")
        elif self.item.old:
            dial.resetTransform()
            dial.setPen (QPen(QColor(255, 150, 0)))
            dial.setBrush (QBrush(QColor(255, 150, 0)))
            dial.setFont (warn_font)
            dial.drawText (0,0,w,h, Qt.AlignCenter, "OLD")
        """


    def getROC(self):
        return self._roc

    def setROC(self, roc):
        if roc != self._roc:
            self._roc = roc
            self.update()

    roc = property(getROC, setROC)


class AS_Trend_Tape(QGraphicsView):
    def __init__(self, parent=None):
        super(AS_Trend_Tape, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self._airspeed = 0
        self._airspeed_diff = 0
        self._airspeed_trend = []
        self.freq = 10

    def resizeEvent(self, event):
        w = self.width()
        h = self.height()
        self.pph = 10
        self.zeroPen = QPen(QColor(Qt.white))
        self.zeroPen.setWidth(4)

        self.scene = QGraphicsScene(0, 0, w, h)

        self.scene.addRect(0, 0, w, h,
                           QPen(QColor(Qt.black)), QBrush(QColor(Qt.black)))

        self.scene.addLine(0, h / 2,
                           w, h / 2,
                           self.zeroPen)

        self.setScene(self.scene)

    def redraw(self):
        self.scene.clear()
        self.scene.addRect(0, 0, self.width(), self.height(),
                           QPen(QColor(Qt.black)), QBrush(QColor(Qt.black)))

        self.scene.addLine(0, self.height() / 2,
                           self.width(), self.height() / 2,
                           self.zeroPen)

        self.centerOn(self.scene.width() / 2,
                      self.height() / 2)

        self._airspeed_diff = (sum(self._airspeed_trend) / len(
                               self._airspeed_trend)) * 60

        self.scene.addRect(self.width() / 2, self.height() / 2,
                           self.width() / 2 + 5,
                           self._airspeed_diff * -self.pph,
                           QPen(QColor(Qt.white)), QBrush(QColor(Qt.white)))

        self.setScene(self.scene)

    def setAS_Trend(self, airspeed):
        if airspeed != self._airspeed:
            if len(self._airspeed_trend) == self.freq:
                del self._airspeed_trend[0]
            self._airspeed_trend.append(airspeed - self._airspeed)
            self._airspeed = airspeed
            self.redraw()
        elif airspeed == self._airspeed:
            if len(self._airspeed_trend) == self.freq:
                del self._airspeed_trend[0]
            self._airspeed_trend.append(airspeed - self._airspeed)
            self._airspeed = airspeed
            self.redraw()

    altimeter = property(setAS_Trend)


class Alt_Trend_Tape(QGraphicsView):
    RIGHT_MARGIN = 5

    def __init__(self, parent=None):
        super(Alt_Trend_Tape, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)

        self.item = fix.db.get_item("VS")
        self.item.valueChanged[float].connect(self.setVs)
        self.item.oldChanged[bool].connect(self.setOld)
        self.item.badChanged[bool].connect(self.setBad)
        self.item.failChanged[bool].connect(self.setFail)
        self._vs = self.item.value
        self.maxvs = 2500
        self.fontsize = 10
        self.indicator_line = None

        self._bad = self.item.bad
        self._old = self.item.old
        self._fail = self.item.fail

    def resizeEvent(self, event):
        w = self.width() - self.RIGHT_MARGIN
        w_2 = w / 2
        h = self.height()

        f = QFont()
        f.setPixelSize(self.fontsize)
        bf = QFont()
        bf.setPixelSize(self.fontsize + 2)
        bf.setBold(True)

        self.scene = QGraphicsScene(0, 0, w, h)
        self.scene.setFont(f)
        self.scene.addRect(0, 0, self.width(), h,
                           QPen(QColor(Qt.black)), QBrush(QColor(Qt.black)))
        t = self.scene.addText("VSI")
        t.setFont(f)
        t.setDefaultTextColor(QColor(Qt.white))
        t.setX(0)
        t.setY(0)
        y = t.boundingRect().height() * .6

        self.vstext = self.scene.addText(str(self._vs))
        self.vstext.setFont(bf)
        self.vstext.setDefaultTextColor(QColor(Qt.white))
        self.vstext.setX(0)
        self.vstext.setY(y)
        self.setVsText()
        self.top_margin = y + self.vstext.boundingRect().height() * 1.2
        remaining_height = self.height() - self.top_margin
        self.zero_y = remaining_height / 2 + self.top_margin

        self.pph = float(remaining_height) / (self.maxvs * 2)

        tapePen = QPen(QColor(Qt.white))
        for i in range(self.maxvs, -self.maxvs - 1, -100):
            y = self.y_offset(i)
            if i % 200 == 0:
                self.scene.addLine(w_2 + 5, y, w, y, tapePen)
                t = self.scene.addText(str(int(i / 100)))
                t.setFont(f)
                t.setDefaultTextColor(QColor(Qt.white))
                t.setX(0)
                t.setY(y - t.boundingRect().height() / 2)
            else:
                self.scene.addLine(w_2 + 10, y, w, y, tapePen)
        self.setScene(self.scene)
        self.redraw()

    def y_offset(self, vs):
        return self.zero_y - vs * self.pph

    def redraw(self):
        y = self.y_offset(self._vs)
        w = self.width() - self.RIGHT_MARGIN
        x = w * 6 / 7
        width = w - x
        if self._vs > 0:
            top = y
            bottom = self.zero_y
        else:
            top = self.zero_y
            bottom = y
        height = bottom - top
        if self._fail:
            if self.indicator_line is not None:
                self.scene.removeItem(self.indicator_line)
                self.indicator_line = None
        elif self.indicator_line is None:
            self.indicator_line = self.scene.addRect(x, top, width, height,
                                                     QPen(QColor(Qt.white)),
                                                     QBrush(QColor(Qt.white)))
        else:
            self.indicator_line.setRect(x, top, width, height)
        self.setVsText()

    def setVs(self, vs):
        if vs != self._vs:
            self._vs = vs
            self.redraw()

    vs = property(setVs)

    def setVsText(self):
        if self._fail:
            self.vstext.setPlainText("XXX")
            self.vstext.setDefaultTextColor (QColor(Qt.red))
        elif self._bad:
            self.vstext.setPlainText("")
            self.vstext.setDefaultTextColor (QColor(255, 150, 0))
        elif self._old:
            self.vstext.setPlainText("")
            self.vstext.setDefaultTextColor (QColor(255, 150, 0))
        else:
            self.vstext.setPlainText(str(int(self._vs)))
            self.vstext.setDefaultTextColor (QColor(Qt.white))

    def getBad(self):
        return self._bad
    def setBad(self, b):
        if self._bad != b:
            self._bad = b
            self.redraw()
    bad = property(getBad, setBad)

    def getOld(self):
        return self._old
    def setOld(self, b):
        if self._old != b:
            self._old = b
            self.redraw()
    old = property(getOld, setOld)

    def getFail(self):
        return self._fail
    def setFail(self, b):
        if self._fail != b:
            self._fail = b
            self.redraw()
    fail = property(getFail, setFail)

