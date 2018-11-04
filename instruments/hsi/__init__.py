#  Copyright (c) 2013 Neil Domalik; 2018 Garrett Herschleb
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
import efis
import fix

class HSI(QWidget):
    def __init__(self, parent=None, font_size=15, fgcolor=Qt.black, bgcolor=Qt.white):
        super(HSI, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setFocusPolicy(Qt.NoFocus)
        self.fontSize = font_size
        self.fg_color = fgcolor
        self.bg_color = bgcolor
        self._heading_key = None
        item = fix.db.get_item("COURSE", True)
        self._headingSelect = item.value
        item.valueChanged[float].connect(self.setHeadingBug)
        self._courseSelect = 1

        self.cdidb = fix.db.get_item("CDI", True)
        self._courseDeviation = self.cdidb.value
        self.cdidb.valueChanged[float].connect(self.setCdi)
        self._showCDI = not self.cdidb.old

        self.gsidb = fix.db.get_item("GSI", True)
        self._glideSlopeIndicator = self.gsidb.value
        self.gsidb.valueChanged[float].connect(self.setGsi)
        self._showGSI = not self.gsidb.old
        self.cardinal = ["N", "E", "S", "W"]

        item = fix.db.get_item("HEAD", True)
        self._heading = item.value
        item.valueChanged[float].connect(self.setHeading)

        #item.oldChanged.connect(self.oldFlag)
        #item.badChanged.connect(self.badFlag)
        #item.failChanged.connect(self.failFlag)



    def resizeEvent(self, event):
        self.cx = self.width() / 2
        self.cy = self.height() / 2 + self.fontSize / 2
        self.r = self.height() / 2 - self.fontSize - 5
        self.cdippw = self.r * .5
        self.gsipph = self.r * .5

    def paintEvent(self, event):
        c = QPainter(self)
        c.setRenderHint(QPainter.Antialiasing)
        f = QFont()
        f.setBold(True)
        f.setFamily ("Sans")
        f.setPixelSize(self.fontSize)
        c.setFont(f)

        #Draw the Black Background
        #c.fillRect(0, 0, self.width(), self.height(), Qt.black)

        # Setup Pens
        compassPen = QPen(QColor(self.fg_color))
        compassBrush = QBrush(QColor(self.bg_color))
        nobrush = QBrush()

        headingPen = QPen(QColor(Qt.red))
        headingBrush = QBrush(QColor(Qt.red))
        headingPen.setWidth(2)

        cdiPen = QPen(QColor(Qt.yellow))
        cdiPen.setWidth(3)

        # Compass Setup
        c.setPen(compassPen)
        c.setBrush(compassBrush)
        c.drawPoint(self.cx, self.cy)
        tr = QRect(self.cx - self.fontSize * 1.5, 3,
                   self.fontSize * 3, self.fontSize + 5)
        c.drawText(tr, Qt.AlignHCenter | Qt.AlignVCenter,
                   str(int(self._heading)))
        c.setBrush(nobrush)
        c.drawRect(tr)

        # Compass Setup
        center = QPointF(self.cx, self.cy)
        c.drawEllipse(center, self.r, self.r)

        c.save()
        c.translate(self.cx, self.cy)
        c.rotate(-(self._heading))

        refsize = self.fontSize*.7
        longLine = QLine(0, -self.r, 0, -(self.r - refsize))
        shortLine = QLine(0, -self.r, 0, -(self.r - refsize / 2))
        textRect = QRect(-40, -self.r + refsize, 80, refsize + 10)
        c.setBrush(compassBrush)
        for count in range(0, 360, 5):
            if count % 10 == 0:
                c.drawLine(longLine)
                if count % 90 == 0:
                    c.drawText(textRect, Qt.AlignHCenter | Qt.AlignVCenter,
                               self.cardinal[int(count / 90)])
                elif count % 30 == 0:
                    c.drawText(textRect, Qt.AlignHCenter | Qt.AlignVCenter,
                               str(int(count / 10)))
            else:
                c.drawLine(shortLine)
            c.rotate(5)

        #Draw Heading Bug
        c.setPen(headingPen)
        c.setBrush(headingBrush)
        delta = self._headingSelect
        c.rotate(delta)
        inc = int(self.fontSize / 2 * 0.8)
        triangle = QPolygon([QPoint(inc, -self.r + 1),
                             QPoint(-inc, -self.r + 1),
                             QPoint(0, -(self.r - inc * 2))])
        c.drawPolygon(triangle)
        c.rotate(-delta)

        c.restore()

        #Non-moving items
        c.setPen(cdiPen)
        c.drawLine(self.cx, self.cy - self.r - 5,
                   self.cx, self.cy - self.r + self.fontSize*2)
        c.drawLine(self.cx, self.cy + self.r - self.fontSize,
                   self.cx, self.cy + self.r - self.fontSize*2)
        c.drawLine(self.cx + self.r - self.fontSize, self.cy,
                   self.cx + self.r - self.fontSize*2, self.cy)
        c.drawLine(self.cx - self.r + self.fontSize, self.cy,
                   self.cx - self.r + self.fontSize*2, self.cy)

        # GSI index tics
        c.setPen(compassPen)
        deviation = -1.0
        while deviation <= 1.0:
            c.drawLine(self.cx - 5, self.cy + deviation*self.gsipph,
                       self.cx + 5, self.cy + deviation*self.gsipph)
            c.drawLine(self.cx + deviation*self.cdippw, self.cy - 5,
                       self.cx + deviation*self.cdippw, self.cy + 5)
            deviation += 1.0/3.0
        c.setPen(cdiPen)
        self._showCDI = not self.cdidb.old
        if self._showCDI:
            x = self.cx + self._courseDeviation * self.cdippw
            c.drawLine(x, self.cy + self.r - self.fontSize*2 - 6,
                   x, self.cy - self.r + self.fontSize*2 + 6)
            
        self._showGSI = not self.gsidb.old
        if self._showGSI:
            y = self.cy - self._glideSlopeIndicator * self.gsipph
            c.drawLine(self.cx + self.r - self.fontSize*2 - 6, y,
                   self.cx - self.r + self.fontSize*2 + 6, y)
            

    def getHeading(self):
        return self._heading

    def setHeading(self, heading):
        if heading != self._heading:
            self._heading = efis.bounds(0, 360, heading)
            self.update()

    heading = property(getHeading, setHeading)

    def getHeadingBug(self):
        return self._headingSelect

    def setHeadingBug(self, headingBug):
        if headingBug != self._headingSelect:
            self._headingSelect = efis.bounds(0, 360, headingBug)
            self.update()

    headingBug = property(getHeadingBug, setHeadingBug)

    def getCdi(self):
        return self._courseDeviation

    def setCdi(self, cdi):
        if cdi != self._courseDeviation:
            self._courseDeviation = cdi
            self.update()

    cdi = property(getCdi, setCdi)

    def getGsi(self):
        return self._glideSlopeIndicator

    def setGsi(self, gsi):
        if gsi != self._glideSlopeIndicator:
            self._glideSlopeIndicator = gsi
            self.update()

    gsi = property(getGsi, setGsi)


class DG_Tape(QGraphicsView):
    def __init__(self, parent=None):
        super(DG_Tape, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self.fontsize = 20
        self._heading = 1
        self._headingSelect = 1
        self._courseSelect = 1
        self._courseDevation = 1
        self.cardinal = ["N", "E", "S", "W", "N"]

        item = fix.db.get_item("HEAD", True)
        item.valueChanged[float].connect(self.setHeading)

        #item.oldChanged.connect(self.oldFlag)
        #item.badChanged.connect(self.badFlag)
        #item.failChanged.connect(self.failFlag)

        #fix.db.get_item("COURSE", True).valueChanged[float].connect(self.setHeadingBug)

    def resizeEvent(self, event):
        w = self.width()
        h = self.height()

        self.dpp = 10
        compassPen = QPen(QColor(Qt.white))
        compassPen.setWidth(2)

        headingPen = QPen(QColor(Qt.red))
        headingPen.setWidth(8)

        f = QFont()
        f.setPixelSize(self.fontsize)

        self.scene = QGraphicsScene(0, 0, 5000, h)
        self.scene.addRect(0, 0, 5000, h,
                           QPen(QColor(Qt.black)), QBrush(QColor(Qt.black)))

        self.setScene(self.scene)

        for i in range(-50, 410, 5):
            if i % 10 == 0:
                self.scene.addLine((i * 10) + w / 2, 0, (i * 10) + w / 2, h / 2,
                                   compassPen)
                if i > 360:
                    t = self.scene.addText(str(i - 360))
                    t.setFont(f)
                    self.scene.setFont(f)
                    t.setDefaultTextColor(QColor(Qt.white))
                    t.setX(((i * 10) + w / 2) - t.boundingRect().width() / 2)
                    t.setY(h - t.boundingRect().height())
                elif i < 1:
                    t = self.scene.addText(str(i + 360))
                    t.setFont(f)
                    self.scene.setFont(f)
                    t.setDefaultTextColor(QColor(Qt.white))
                    t.setX(((i * 10) + w / 2) - t.boundingRect().width() / 2)
                    t.setY(h - t.boundingRect().height())
                else:
                    if i % 90 == 0:
                        t = self.scene.addText(self.cardinal[int(i / 90)])
                        t.setFont(f)
                        self.scene.setFont(f)
                        t.setDefaultTextColor(QColor(Qt.cyan))
                        t.setX(((i * 10) + w / 2) - t.boundingRect().width() / 2)
                        t.setY(h - t.boundingRect().height())
                    else:
                        t = self.scene.addText(str(i))
                        t.setFont(f)
                        self.scene.setFont(f)
                        t.setDefaultTextColor(QColor(Qt.white))
                        t.setX(((i * 10) + w / 2) - t.boundingRect().width() / 2)
                        t.setY(h - t.boundingRect().height())
            else:
                self.scene.addLine((i * 10) + w / 2, 0,
                                   (i * 10) + w / 2, h / 2 - 20,
                                    compassPen)

    def redraw(self):
        self.resetTransform()
        self.centerOn(self._heading * self.dpp + self.width() / 2,
                      self.scene.height() / 2)

    def getHeading(self):
        return self._heading

    def setHeading(self, heading):
        if heading != self._heading:
            self._heading = heading
            self.redraw()

    heading = property(getHeading, setHeading)
