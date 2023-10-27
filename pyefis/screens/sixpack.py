#  Copyright (c) 2016 Phil Birkelbach
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

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from pyefis.instruments import ai
# from pyefis.instruments import gauges
from pyefis.instruments import hsi
from pyefis.instruments import airspeed
from pyefis.instruments import altimeter
from pyefis.instruments import vsi
from pyefis.instruments import tc

import pyavtools.fix as fix
from collections import defaultdict

class Screen(QWidget):
    def __init__(self, parent=None,config=None):
        super(Screen, self).__init__(parent)
        self.parent = parent
        p = self.parent.palette()
        self.screenColor = (0, 0, 0)
        if self.screenColor:
            p.setColor(self.backgroundRole(), QColor(*self.screenColor))
            self.setPalette(p)
            self.setAutoFillBackground(True)

        #self.airspeed = airspeed.Airspeed(self)

        self.ai = ai.AI(self)
        self.ai.fontSize = 12
        self.ai.bankMarkSize = 7
        self.ai.pitchDegreesShown = 60

        #self.altimeter = altimeter.Altimeter(self)

        self.tc = tc.TurnCoordinator(self)

        self.hsi = hsi.HSI(self, font_size=12, fgcolor=Qt.white)
        self.heading_disp = hsi.HeadingDisplay(self, font_size=17, fgcolor=Qt.white)

        self.init= False
        
    def init_screen(self):
        self.layout = self.parent.get_config_item(self,'layout')
        self.data_items = dict()
        self.data_distribution = defaultdict(list)
        self.insturments = dict()
        self.insturment_config = dict ()
        # Setup insturments:
        count = 1
        for i in self.get_config_item('insturments'):
            self.insturment_config[count] = i
            if type(i['db_items']) is list:
                for item in i['db_items']:
                    self.define_data(count,item)
                    self.data_distribution[item].append(count)
            else:
                self.define_data(count,i['db_items'])
                self.data_distribution[i['db_items']].append(count)
            # Process the type of gauge this is
            if i['type'] == 'vsi_dial':
                self.insturments[count] = vsi.VSI_Dial(self,data=self.data_items[self.lookup_mapping('VS',i.get('mapping',dict()))])
            elif i['type'] == 'altimeter_dial':
                self.insturments[count] = altimeter.Altimeter(self,data=self.data_items[self.lookup_mapping('ALT',i.get('mapping',dict()))])
            elif i['type'] == 'airspeed_dial':
                self.insturments[count] = airspeed.Airspeed(self,data=self.data_items[self.lookup_mapping('IAS',i.get('mapping',dict()))])

            count += 1

        #Place insturments:
        if self.layout['type'] == 'grid':
            self.grid_layout()
        self.init = True

    def lookup_mapping(self,item,mapping=dict()):
          return mapping.get(item,item)

    def define_data(self,count,item):
        if not item in self.data_items:
            print(f"db item: {item}")
            self.data_items[item] = fix.db.get_item(item)
            self.data_items[item].valueChanged[float].connect(lambda valueChanged, key=item: self.data_modified(db_item=key) )
            self.data_items[item].valueChanged[str].connect(lambda valueChanged, key=item: self.data_modified(db_item=key))
            self.data_items[item].valueChanged[bool].connect(lambda valueChanged, key=item: self.data_modified(db_item=key))
            self.data_items[item].oldChanged[bool].connect(lambda valueChanged, key=item: self.data_redraw(db_item=key))
            self.data_items[item].badChanged[bool].connect(lambda valueChanged, key=item: self.data_redraw(db_item=key))
            self.data_items[item].failChanged[bool].connect(lambda valueChanged, key=item: self.data_redraw(db_item=key))


    def data_modified(self,db_item):
        print(f"modified: {db_item}")
        for inst in self.data_distribution[db_item]:
            if self.insturment_config[inst]['type'] == 'vsi_dial':
                self.insturments[inst].setROC(self.data_items[db_item].value)
            elif self.insturment_config[inst]['type'] == 'altimeter_dial':
                self.insturments[inst].setAltimeter(self.data_items[db_item].value)
            elif self.insturment_config[inst]['type'] == 'airspeed_dial':
                self.insturments[inst].setAirspeed(self.data_items[db_item].value)


    def data_redraw(self,db_item):
        print(f"redraw: {db_item}")
        for inst in self.data_distribution[db_item]:
            if self.insturment_config[inst]['type'] == 'vsi_dial':
                self.insturments[inst].setROC(self.data_items[db_item].value)
                self.insturments[inst].update()
            elif self.insturment_config[inst]['type'] == 'altimeter_dial':
                self.insturments[inst].setAltimeter(self.data_items[db_item].value)
                self.insturments[inst].update()
            elif self.insturment_config[inst]['type'] == 'airspeed_dial':
                self.insturments[inst].setAirspeed(self.data_items[db_item].value)
                self.insturments[inst].update()


    def grid_layout(self):
        count = 1
        for i,c in self.insturment_config.items():
            width = qRound(self.width() / self.layout['columns'])
            height = qRound(self.height() / self.layout['rows'])
            x = qRound(width * (c['column'] - 1) )
            y = qRound(height * (c['row'] - 1) )
            print(f"width={width} height={height} x={x} y={y}")
            self.move_resize_inst(i,x,y,width,height)
            
    def move_resize_inst(self,inst,x,y,width,height):
        self.insturments[inst].move(x,y)
        self.insturments[inst].resize(width,height)
        #self.insturments[inst].show()

    def vsi_dial(self,count=None,db=None):
        self.insturments[count] = vsi.VSI_Dial(self,data=db)
        #self.db.valueChanged[float].connect(self.insturments[count].setROC)
        #self.db.oldChanged[bool].connect(self.insturments[count].repaint)
        #self.db.badChanged[bool].connect(self.insturments[count].repaint)
        #self.db.failChanged[bool].connect(self.insturments[count].repaint)

    def resizeEvent(self, event):
        if not self.init:
            self.init_screen()
        menu_offset = 30
        instWidth = qRound(self.width()/3)
        instHeight = qRound((self.height()-menu_offset)/2)
        diameter=min(instWidth,instHeight)

        #self.airspeed.move(0,menu_offset)
        #self.airspeed.resize(instWidth,instHeight)

        self.ai.move(instWidth, 0 + menu_offset)
        self.ai.resize(instWidth, instHeight)

        #self.altimeter.move(instWidth*2, 0 + menu_offset)
        #self.altimeter.resize(instWidth,instHeight)

        self.tc.move(0, instHeight + menu_offset)
        self.tc.resize(instWidth, instHeight)

        hdh = self.heading_disp.height()
        hdw = self.heading_disp.width()
        hsi_diameter = diameter - (hdh+30)
        offset = instHeight-hsi_diameter
        self.hsi.move(qRound(instWidth+(instWidth-hsi_diameter)/2), qRound(instHeight + menu_offset + offset-20))
        self.hsi.resize(hsi_diameter,hsi_diameter)
        self.heading_disp.move(qRound(instWidth*1.5-hdw/2), qRound(instHeight + menu_offset+10))

        #self.vsi.move(instWidth * 2, instHeight + menu_offset)
        #self.vsi.resize(instWidth, instHeight)
        if self.layout['type'] == 'grid':
            self.grid_layout()
    def get_config_item(self, key):
        return self.parent.get_config_item(self, key)
