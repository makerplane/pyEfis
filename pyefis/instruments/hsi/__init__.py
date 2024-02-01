#  Copyright (c) 2013 Neil Domalik; 2018-2019 Garrett Herschleb
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

import math
import time

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *


from pyefis import common
import pyavtools.fix as fix
from pyefis import common

# TODO: Add CDI and Glide Slope indicators and tick marks but make them
#       configurable.


class HSI(QGraphicsView):
    def __init__(self, parent=None, font_size=15, fontPercent=None, fgcolor=Qt.white, bgcolor=Qt.black, gsi_enabled=False, cdi_enabled=False):
        super(HSI, self).__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0%); border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self.fontPercent = None
        if fontPercent:
            self.fontPercent = fontPercent
            font_size = qRound(self.fontPercent * self.width())
        self.fontSize = font_size
        self.tickSize = self.fontSize * 0.7
        self.fg_color = fgcolor
        self.bg_color = bgcolor
        self.gsi_enabled = gsi_enabled
        self.cdi_enabled = cdi_enabled
        # List for tick mark visibility, Top, Bottom, Right, Left
        self.visiblePointers = [True, True, True, True]

        self._CdiOld = True
        self._CdiBad = True
        self._CdiFail = True

        self._GsiOld = True
        self._GsiBad = True
        self._GsiFail = True

        self._CourseOld = True
        self._CourseBad = True
        self._CourseFail = True

        self._HeadOld = True
        self._HeadBad = True
        self._HeadFail = True

        self._courseDeviation = 0
        self._glideSlopeIndicator = 0
        self.labels = list()

        self.item = fix.db.get_item("COURSE")
        self._headingSelect = self.item.value
        self.item.valueChanged[float].connect(self.setHeadingBug)
        self.item.oldChanged[bool].connect(self.setCourseOld)
        self.item.badChanged[bool].connect(self.setCourseBad)
        self.item.failChanged[bool].connect(self.setCourseFail)
        self.setCourseOld(self.item.old)
        self.setCourseBad(self.item.bad)
        self.setCourseFail(self.item.fail)

        if self.cdi_enabled:
            self.cdidb = fix.db.get_item("CDI")
            self._courseDeviation = self.cdidb.value
            self.cdidb.valueChanged[float].connect(self.setCdi)
            self.cdidb.failChanged[bool].connect(self.setCdiOld)
            self.cdidb.failChanged[bool].connect(self.setCdiFail)
            self.cdidb.failChanged[bool].connect(self.setCdiOld)
            self.setCdiOld(self.cdidb.old)
            self.setCdiBad(self.cdidb.bad)
            self.setCdiFail(self.cdidb.fail)
        else:
            self._CdiOld = False
            self._CdiBad = False
            self._CdiFail = False
        if self.gsi_enabled:
            self.gsidb = fix.db.get_item("GSI")
            self._glideSlopeIndicator = self.gsidb.value
            self.gsidb.valueChanged[float].connect(self.setGsi)
            self.gsidb.failChanged[bool].connect(self.setGsiOld)
            self.gsidb.failChanged[bool].connect(self.setGsiFail)
            self.gsidb.failChanged[bool].connect(self.setGsiOld)
            self.setGsiOld(self.gsidb.old)
            self.setGsiBad(self.gsidb.bad)
            self.setGsiFail(self.gsidb.fail)
        else:
            self._GsiOld = False
            self._GsiBad = False
            self._GsiFail = False

        self.head = fix.db.get_item("HEAD")
        self._heading = self.head.value
        self.head.valueChanged[float].connect(self.setHeading)
        self.head.oldChanged[bool].connect(self.setHeadOld)
        self.head.badChanged[bool].connect(self.setHeadBad)
        self.head.failChanged[bool].connect(self.setHeadFail)
        self.setHeadFail(self.head.fail)
        self.setHeadOld(self.head.old)
        self.setHeadBad(self.head.bad)
        self.setHeadFail(self.head.fail)

        self._courseSelect = 1
        self._showCDI = not self.isOld()
        self._showGSI = not self.isOld()
        self.cardinal = ["N", "E", "S", "W"]
        self.heading_bug = None
        self.myparent = parent
        self.update_period = None

    def getRatio(self):
        # Return X for 1:x specifying the ratio for this instrument
        return 1

    def resizeEvent(self, event):
        if self.fontPercent:
            self.fontSize = qRound(self.fontPercent * self.width())
        self.tickSize = self.fontSize * 0.7
        self.scene = QGraphicsScene(0, 0, self.width(), self.height())
        self.cx = self.width() / 2.0
        self.cy = self.height() / 2.0
        self.r = self.height() / 2.0 - 5.0
        self.cdippw = self.r * 0.5
        self.gsipph = self.r * 0.5

        # Setup Pens
        compassPen = QPen(QColor(self.fg_color), self.fontSize * 0.02)
        textBrush = QBrush(QColor(self.fg_color))
        compassBrush = QBrush(QColor(self.bg_color))
        nobrush = QBrush()

        headingPen = QPen(QColor(Qt.magenta))
        headingBrush = QBrush(QColor(Qt.magenta))
        headingPen.setWidth(1)


        f = QFont()
        f.setFamily ("Sans")
        f.setPixelSize(self.fontSize)

        for count in range(0, 360, 5):
            angle = (count) * math.pi / 180.0
            cosa = math.cos(angle)
            sina = math.sin(angle)
            iy1 = -self.r
            iy2 = -self.r + self.tickSize
            if count % 10 != 0:
                iy2 -= self.tickSize/2
            x1 = (-iy1*sina) + self.cx # (ix*cosa - iy*sina) ix factor removed Since x is 0
            y1 = iy1*cosa + self.cy # (iy*cosa + ix*sina)
            x2 = (-iy2*sina) + self.cx
            y2 = iy2*cosa + self.cy
            self.scene.addLine(x1, y1, x2, y2, compassPen)
            if count % 90 == 0:
                t = self.scene.addSimpleText(self.cardinal[int(count / 90)], f)
                br = t.sceneBoundingRect()
                t.setRotation(count)
                t.setPen(compassPen)
                t.setBrush(textBrush)
                iy3 = -self.r + self.tickSize*1.1
                ix3 = -br.width()/2
                x3 = (ix3*cosa - iy3*sina) + self.cx
                y3 = (iy3*cosa + ix3*sina) + self.cy
                t.setPos(x3, y3)
                self.labels.append(t)
            elif count % 30 == 0:
                text = str(int(count / 10))
                t = self.scene.addSimpleText(text, f)
                br = t.sceneBoundingRect()
                t.setRotation(count)
                t.setPen(compassPen)
                t.setBrush(textBrush)
                iy3 = -self.r + self.tickSize*1.1
                ix3 = -br.width()/2
                x3 = (ix3*cosa - iy3*sina) + self.cx
                y3 = (iy3*cosa + ix3*sina) + self.cy
                t.setPos(x3, y3)
                self.labels.append(t)

        #Draw Heading Bug
        triangle = self.heading_bug_polygon()
        self.heading_bug = self.scene.addPolygon(triangle, headingPen, headingBrush)

        self.setScene(self.scene)
        self.rotate(-self._heading)

        # Draws the static overlay stuff to a pixmap
        self.map = QPixmap(self.width(), self.height())
        self.map.fill(Qt.transparent)
        p = QPainter(self.map)
        p.setRenderHint(QPainter.Antialiasing)
        # set the width and height for conveinience
        # w = self.width()
        # h = self.height()

        p.setPen(QPen(QColor(self.fg_color),self.fontSize * 0.07))
        p.setBrush(QColor(Qt.transparent))
        # Outer ring
        p.drawEllipse(QRectF(self.cx-self.r, self.cy-self.r, self.r*2.0, self.r*2.0))
        # Draw the pointer marks
        p.setPen(QPen(QColor(Qt.yellow), 3))
        if self.visiblePointers[0]:
            # Top Pointer
            p.drawLine(QLineF(self.cx, self.cy - self.r - 5,
                              self.cx, self.cy - self.r + self.fontSize*2))
        if self.visiblePointers[1]:
            # Bottom Pointer
            p.drawLine(QLineF(self.cx, self.cy + self.r + 5,
                              self.cx, self.cy + self.r - self.fontSize*2))
        if self.visiblePointers[2]:
            # Right Pointer
            p.drawLine(QLineF(self.cx + self.r + 5, self.cy,
                              self.cx + self.r - self.fontSize*2, self.cy))
        if self.visiblePointers[3]:
            # Left Pointer
            p.drawLine(QLineF(self.cx - self.r - 5, self.cy,
                              self.cx - self.r + self.fontSize*2, self.cy))

        self.overlay = self.map.toImage()



    def heading_bug_polygon(self):
        inc = int(self.tickSize)
        iyb = -self.r
        points = [ (inc, -self.r),
                  (-inc, -self.r),
                  (0, -self.r + inc)]
        angle = (self._headingSelect) * math.pi / 180
        cosa = math.cos(angle)
        sina = math.sin(angle)

        points = [((ix*cosa - iy*sina), (iy*cosa + ix*sina)) for ix,iy in points]
        points = [QPointF((ix + self.cx), (iy + self.cy)) for ix,iy in points]
        triangle = QPolygonF(points)
        return triangle

    def paintEvent(self, event):
        super(HSI, self).paintEvent(event)

        c = QPainter(self.viewport())

        # Put the static overlay image on the view
        c.drawImage(self.rect(), self.overlay)


        compassPen = QPen(QColor(self.fg_color))
        compassBrush = QBrush(QColor(self.bg_color))
        cdiPen = QPen(QColor(Qt.yellow))
        cdiPen.setWidth(3)
        c.setRenderHint(QPainter.Antialiasing)


        # GSI index tics
        if self.cdi_enabled or self.gsi_enabled:
            c.setPen(compassPen)
            deviation = -1.0
            while deviation <= 1.0:
                c.drawLine(qRound(self.cx - 5), qRound(self.cy + deviation*self.gsipph),
                           qRound(self.cx + 5), qRound(self.cy + deviation*self.gsipph))
                c.drawLine(qRound(self.cx + deviation*self.cdippw), qRound(self.cy - 5),
                           qRound(self.cx + deviation*self.cdippw), qRound(self.cy + 5))
                deviation += 1.0/3.0

            c.setPen(cdiPen)
            self._showCDI = not self.isOld()
            if self._showCDI and self.cdi_enabled:
                x = self.cx + self._courseDeviation * self.cdippw
                c.drawLine(qRound(x), qRound(self.cy + self.r - self.fontSize*2 - 6),
                           qRound(x), qRound(self.cy - self.r + self.fontSize*2 + 6))
       
            self._showGSI = not self.isOld()
            if self._showGSI and self.gsi_enabled:
                y = self.cy - self._glideSlopeIndicator * self.gsipph
                c.drawLine(qRound(self.cx + self.r - self.fontSize*2 - 6), qRound(y),
                           qRound(self.cx - self.r + self.fontSize*2 + 6), qRound(y))

    def getHeading(self):
        return self._heading

    def setHeading(self, heading):
        if heading != self._heading:
            now = time.time()
            newheading = common.bounds(0, 360, heading)
            diff = newheading - self._heading
            if diff > 180:
                diff -= 360
            elif diff < -180:
                diff += 360
            self._heading = newheading
            self.rotate(-diff)
            self.last_update_time = now

    def setHeadOld(self,old):
        self._HeadOld = old

    def setHeadBad(self,bad):
        self._HeadBad = bad

    def setHeadFail(self,fail):
        if fail != self._HeadFail:
            self._HeadFail = fail
            self.changeFail()
 
    heading = property(getHeading, setHeading)

    def isOld(self):
        return self._GsiOld    or self._GsiBad\
            or self._CdiOld    or self._CdiBad\
            or self._HeadOld   or self._HeadBad\
            or self._CourseOld or self._CourseBad

    def isFail(self):
        return self._GsiFail\
            or self._CdiFail\
            or self._HeadBad\
            or self._CourseBad

    def changeFail(self):
        if self.isFail():
            for l in self.labels:
                l.setOpacity(0)
        else:
            for l in self.labels:
                l.setOpacity(1)

    def getHeadingBug(self):
        return self._headingSelect

    def setHeadingBug(self, headingBug):
        if headingBug != self._headingSelect:
            self._headingSelect = common.bounds(0, 360, headingBug)
            if self.heading_bug is not None:
                triangle = self.heading_bug_polygon()
                self.heading_bug.setPolygon(triangle)

    headingBug = property(getHeadingBug, setHeadingBug)

    def setCourseOld(self,old):
        self._CourseOld = old

    def setCourseBad(self,bad):
        self._CourseBad = bad

    def setCourseFail(self,fail):
        if fail != self._CourseFail:
            self._CourseFail = fail
            self.changeFail()

    def getCdi(self):
        return self._courseDeviation

    def setCdi(self, cdi):
        if cdi != self._courseDeviation:
            self._courseDeviation = cdi
            if self.isVisible(): 
                self.update()

    def setCdiOld(self, old):
        if self.cdi_enabled:
            self._CdiOld = old
            if self.isVisible():
                self.update()

    def setCdiBad(self, bad):
        if self.cdi_enabled:
            self._CdiBad = bad
            if self.isVisible():
                self.update()

    def setCdiFail(self, fail):
        if self.cdi_enabled:
            if fail != self._CdiFail:
                self._CdiFail = fail
                self.changeFail()


    cdi = property(getCdi, setCdi)

    def getGsi(self):
        return self._glideSlopeIndicator

    def setGsi(self, gsi):
        if gsi != self._glideSlopeIndicator:
            self._glideSlopeIndicator = gsi
            if self.isVisible(): self.update()

    gsi = property(getGsi, setGsi)

    def setGsiOld(self, old):
        if self.gsi_enabled:
            self._GsiOld = old
            if self.isVisible():
                self.update()

    def setGsiBad(self, bad):
        if self.gsi_enabled:
            self._GsiBad = bad
            if self.isVisible():
                self.update()

    def setGsiFail(self, fail):
        if self.gsi_enabled:
            if fail != self._GsiFail:
                self._GsiFail = fail
                self.changeFail()


    # We don't want this responding to keystrokes
    def keyPressEvent(self, event):
        pass

    # Don't want it acting with the mouse scroll wheel either
    def wheelEvent(self, event):
        pass

    def showEvent(self, event):
        self.update()


class HeadingDisplay(QWidget):
    def __init__(self, parent=None, font_size=15, fgcolor=Qt.gray, bgcolor=Qt.black, fontPercent=None):
        super(HeadingDisplay, self).__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.fontPercent = fontPercent
        if self.fontPercent:
            font_size = qRound(self.fontPercent * self.height())
        self.fontSize = font_size
        
        self.fg_color = fgcolor
        self.bg_color = bgcolor

        self._Old = True
        self._Bad = True
        self._Fail = True

        self.item = fix.db.get_item("HEAD")
        self.item.valueChanged[float].connect(self.setHeading)
        self.item.failChanged[bool].connect(self.setFail)
        self.item.badChanged[bool].connect(self.setBad)
        self.item.oldChanged[bool].connect(self.setOld)
        self.setOld(self.item.old)
        self.setBad(self.item.bad)
        self.setFail(self.item.fail)

        self._heading = self.item.value

        self.font = QFont()
        self.font.setBold(True)
        self.font.setFamily ("Sans")
        self.font.setPixelSize(self.fontSize)
        t = QGraphicsSimpleTextItem ("999")
        t.setFont (self.font)
        br = t.boundingRect()
        self.resize(qRound(br.width()*1.2), qRound(br.height()*1.2))

    def paintEvent(self, event):
        if self.fontPercent:
            self.fontSize = qRound(self.fontPercent * self.height())
        self.font.setPixelSize(self.fontSize)
        c = QPainter(self)
        compassPen = QPen(QColor(self.fg_color))
        compassBrush = QBrush(QColor(self.bg_color))
        c.setPen(compassPen)
        c.setBrush(compassBrush)
        c.setFont(self.font)
        tr = QRectF(0, 0, self.width()-1, self.height()-1)
        c.drawRect(tr)
        if self._Fail:
            heading_text = "XXX"
            c.setBrush(QBrush(QColor(Qt.red)))
            c.setPen(QPen(QColor(Qt.red)))
        elif self._Bad:
            heading_text = ""
            c.setBrush(QBrush(QColor(255, 150, 0)))
            c.setPen(QPen(QColor(255, 150, 0)))
        elif self._Old:
            heading_text = ""
            c.setBrush(QBrush(QColor(255, 150, 0)))
            c.setPen(QPen(QColor(255, 150, 0)))
        else:
            heading_text = str(int(self._heading))

        c.drawText(tr, Qt.AlignHCenter | Qt.AlignVCenter, heading_text)

    def getHeading(self):
        return self._heading

    def setHeading(self, heading):
        if heading != self._heading:
            self._heading = common.bounds(0, 360, heading)
            if self.isVisible(): self.update()

    heading = property(getHeading, setHeading)

    def setFail(self, fail):
        self._Fail = fail
        self.repaint()

    def setOld(self, old):
        self._Old = old
        self.repaint()

    def setBad(self, bad):
        self._Bad = bad
        self.repaint()

    def showEvent(self, event):
        self.update()

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
        self._heading = item.value

        # TODO Seems the heading tape does not have bad/fail/old
        self.dpp = 10
    def resizeEvent(self, event):
        w = self.width()
        h = self.height()

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
                      self.height() / 2)

    def getHeading(self):
        return self._heading

    def setHeading(self, heading):
        if heading != self._heading:
            self._heading = heading
            self.redraw()

    heading = property(getHeading, setHeading)

    def showEvent(self, event):
        self.redraw()

    # We don't want this responding to keystrokes
    def keyPressEvent(self, event):
        pass

    # Don't want it acting with the mouse scroll wheel either
    def wheelEvent(self, event):
        pass

