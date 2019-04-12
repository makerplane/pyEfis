#  Copyright (c) 2016 Phil Birkelbach; 2019 Garrett Herschleb
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

import pyavtools.fix as fix

from instruments import ai
from instruments.ai.VirtualVfr import VirtualVfr
from instruments import hsi
from instruments import airspeed
from instruments import altimeter
from instruments import vsi
from instruments import tc

class Screen(QWidget):
    def __init__(self, parent=None):
        super(Screen, self).__init__(parent)
        self.parent = parent
        p = self.parent.palette()

        self.screenColor = (0,0,0)
        if self.screenColor:
            p.setColor(self.backgroundRole(), QColor(*self.screenColor))
            self.setPalette(p)
            self.setAutoFillBackground(True)

        self.ai = VirtualVfr(self)
        self.ai.fontSize = 20
        self.ai.pitchDegreesShown = 90

        self.alt_tape = altimeter.Altimeter_Tape(self)
        self.alt_Trend = vsi.Alt_Trend_Tape(self)
        self.as_tape = airspeed.Airspeed_Tape(self)
        #self.as_Trend = vsi.AS_Trend_Tape(self)
        self.asd_Box = airspeed.Airspeed_Mode(self)
        #self.parent.change_asd_mode.connect(self.change_asd_mode)
        self.hsi = hsi.HSI(self, font_size=12, fgcolor="#0030FF")
        self.heading_disp = hsi.HeadingDisplay(self, font_size=12, fgcolor="#0030FF")
        self.alt_setting = altimeter.Altimeter_Setting(self)
        self.check_engine = CheckEngine(self)
        self.tc = tc.TurnCoordinator(self, dial=False)

    def resizeEvent(self, event):
        instWidth = self.width()- 80
        instHeight = self.height() - 130
        self.ai.move(0, 40)
        self.ai.resize(instWidth, instHeight)

        self.alt_tape.resize(90, instHeight)
        self.alt_tape.move(instWidth -90, 40)

        self.alt_Trend.resize(40, instHeight)
        self.alt_Trend.move(instWidth , 40)

        self.as_tape.resize(90, instHeight)
        self.as_tape.move(0, 40)

        #self.as_Trend.resize(10, instHeight)
        #self.as_Trend.move(90, 100)

        self.asd_Box.resize(90, 60)
        self.asd_Box.move(0, instHeight + 50)

        hsi_diameter=instWidth/5
        self.hsi.resize(hsi_diameter, hsi_diameter)
        self.hsi.move((instWidth-hsi_diameter)/2, instHeight - hsi_diameter + 65)
        self.heading_disp.move((instWidth-self.heading_disp.width())/2,
                    instHeight - hsi_diameter - self.heading_disp.height() + 65)

        self.alt_setting.resize(90, 60)
        self.alt_setting.move(instWidth -100, instHeight + 50)
        self.check_engine.move (instWidth - self.check_engine.width()-100, 45)
        engine_items = self.get_config_item("check_engine")
        if engine_items is not None and len(engine_items) > 0:
            self.check_engine.init_fix_items(engine_items)

        tc_width = instWidth * .23
        self.tc.resize (tc_width, tc_width)
        self.tc.move ((instWidth-tc_width)/2, instHeight-tc_width*.10)

    def change_asd_mode(self, event):
        self.asd_Box.setMode(self.asd_Box.getMode() + 1)

    def get_config_item(self, key):
        return self.parent.get_config_item(self, key)

class CheckEngine(QGraphicsView):
    def __init__(self, parent=None):
        super(CheckEngine, self).__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0%); border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.Antialiasing)
        self.setFocusPolicy(Qt.NoFocus)
        self.fontSize = 30
        font = QFont("FixedSys", 10, QFont.Bold)
        self.text = "Check Engine"
        t = QGraphicsSimpleTextItem (self.text)
        t.setFont (font)
        self.w = t.boundingRect().width()
        self.h = t.boundingRect().height()
        self.resize(self.w, self.h)
        self.scene = QGraphicsScene(0, 0, self.w, self.h)
        t = self.scene.addSimpleText (self.text, font)
        t.setPen(QPen(QColor(Qt.red)))
        t.setBrush(QBrush(QColor(Qt.red)))
        self.setScene(self.scene)
        self.fix_items = None
        self.hide()

    def init_fix_items(self, items):
        self.fix_items = [fix.db.get_item(i) for i in items]
        for i in self.fix_items:
            i.oldChanged[bool].connect(self.setStatus)
            i.badChanged[bool].connect(self.setStatus)
            i.failChanged[bool].connect(self.setStatus)
            i.annunciateChanged[bool].connect(self.setStatus)
        self.setStatus(0)

    def setStatus(self, b):
        show = False
        for i in self.fix_items:
            if i.bad or i.old or i.fail or i.annunciate:
                show = True
                break
        if show:
            self.show()
        else:
            self.hide()
