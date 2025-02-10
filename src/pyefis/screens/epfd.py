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

from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *

import pyavtools.fix as fix

from pyefis.instruments import ai
#from pyefis.instruments.ai.VirtualVfr import VirtualVfr
from pyefis.instruments import hsi
from pyefis.instruments import airspeed
from pyefis.instruments import altimeter
from pyefis.instruments import vsi
from pyefis.instruments import tc
from pyefis.instruments import gauges

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

        #self.ai = VirtualVfr(self)
        self.ai = ai.AI(self)
        self.ai.fontSize = 20
        self.ai.pitchDegreesShown = 90
        self.ai.visiblePitchAngle = 22 # Amount of visible pitch angle marks

        self.alt_tape = altimeter.Altimeter_Tape(self)
        self.vsi = vsi.VSI_PFD(self)
        self.as_tape = airspeed.Airspeed_Tape(self)
        # airspeed tape numeral display box
        self.asd_Box = airspeed.Airspeed_Box(self)

        self.hsi = hsi.HSI(self, font_size=20, fg_color="#aaaaaa", bg_color="#aaaaaa")
        self.hsi.tickSize = 12
        # Pointer Visibility [Top, Bottom, Right, Left]
        self.hsi.visiblePointers = [True, True, False, False]
        self.heading_disp = hsi.HeadingDisplay(self, font_size=20, fg_color="#ffffff")
        # self.alt_setting = altimeter.Altimeter_Setting(self)
        self.alt_setting = gauges.NumericDisplay(self)
        self.alt_setting.dbkey = "BARO"
        self.alt_setting.decimal_places = 2

        self.check_engine = CheckEngine(self)
        #self.tc = tc.TurnCoordinator(self, dial=False)

    def resizeEvent(self, event):
        instWidth = self.width()
        instHeight = self.height()
        self.ai.move(0,0)
        self.ai.resize(instWidth, instHeight)

        self.alt_tape.resize(90, instHeight)
        self.alt_tape.move(instWidth -90, 0)

        self.vsi.resize(30, qRound(instHeight/2))
        self.vsi.move(instWidth-130 , 0)

        self.as_tape.resize(90, instHeight)
        self.as_tape.move(0, 0)

        self.asd_Box.resize(40,40)
        self.asd_Box.move(100, qRound(instHeight / 2 + 20))

        hsi_diameter = instHeight
        self.hsi.resize(hsi_diameter, hsi_diameter)
        self.hsi.move(qRound((instWidth-hsi_diameter)/2), qRound(instHeight - hsi_diameter))

        self.heading_disp.move(qRound((instWidth-self.heading_disp.width())/2), 20)

        self.alt_setting.resize(60, 20)
        self.alt_setting.move(instWidth -150, qRound(instHeight/2 + 25)
)

        self.check_engine.move (100, 45)
        # self.check_engine.move (instWidth - self.check_engine.width()-100, 45)
        engine_items = self.get_config_item("check_engine")
        if engine_items is not None and len(engine_items) > 0:
            self.check_engine.init_fix_items(engine_items)

    def change_asd_mode(self, event):
        self.asd_Box.setMode(self.asd_Box.getMode() + 1)

    def get_config_item(self, key):
        return self.parent.get_config_item(self, key)

class CheckEngine(QGraphicsView):
    def __init__(self, parent=None):
        super(CheckEngine, self).__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0%); border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.fontSize = 30
        font = QFont("FixedSys", 10, QFont.Weight.Bold)
        self.text = "Check Engine"
        t = QGraphicsSimpleTextItem (self.text)
        t.setFont (font)
        self.w = t.boundingRect().width()
        self.h = t.boundingRect().height()
        self.resize(qRound(self.w), qRound(self.h))
        self.scene = QGraphicsScene(0, 0, self.w, self.h)
        t = self.scene.addSimpleText (self.text, font)
        t.setPen(QPen(QColor(Qt.GlobalColor.red)))
        t.setBrush(QBrush(QColor(Qt.GlobalColor.red)))
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
