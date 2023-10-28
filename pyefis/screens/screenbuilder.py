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

        self.init= False
        self.ai_mapping = dict()
        self.tc_mapping = dict()
        self.hsi_mapping = dict()

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
            elif i['type'] == 'atitude_indicator':
                self.ai_mapping['PITCH'] = self.lookup_mapping('PITCH',i.get('mapping',dict()))
                self.ai_mapping['ROLL'] = self.lookup_mapping('ROLL',i.get('mapping',dict()))
                self.ai_mapping['ALAT'] = self.lookup_mapping('ALAT',i.get('mapping',dict()))
                self.ai_mapping['TAS'] = self.lookup_mapping('TAS',i.get('mapping',dict()))

                self.insturments[count] = ai.AI(self,data = {
                    'PITCH': self.data_items[self.ai_mapping['PITCH']],
                    'ROLL':  self.data_items[self.ai_mapping['ROLL']],
                    'ALAT':  self.data_items[self.ai_mapping['ALAT']],
                    'TAS':   self.data_items[self.ai_mapping['TAS']]
                    }
                )

                self.insturments[count].fontSize = i.get('options',{"font_size": 12}).get('font_size', 12)
                self.insturments[count].bankMarkSize = i.get('options',{'bankMarkSize': 7}).get('bankMarkSize', 7)
                self.insturments[count].pitchDegreesShown = i.get('options',{'pitchDegreesShown': 60}).get('pitchDegreesShown', 60)
            elif i['type'] == 'turn_coordinator':
                self.tc_mapping['ALAT'] = self.lookup_mapping('ALAT',i.get('mapping',dict()))
                self.tc_mapping['ROT'] = self.lookup_mapping('ROT',i.get('mapping',dict()))

                self.insturments[count] = tc.TurnCoordinator(self,data ={
                    'ALAT': self.data_items[self.tc_mapping['ALAT']],
                    'ROT': self.data_items[self.tc_mapping['ROT']],
                    }
                )
            elif i['type'] == 'horizontal_situation_indicator':

                self.hsi_mapping['COURSE'] = self.lookup_mapping('COURSE',i.get('mapping',dict()))
                self.hsi_mapping['CDI'] = self.lookup_mapping('CDI',i.get('mapping',dict()))
                self.hsi_mapping['GSI'] = self.lookup_mapping('GSI',i.get('mapping',dict()))
                self.hsi_mapping['HEAD'] = self.lookup_mapping('HEAD',i.get('mapping',dict()))

                self.insturments[count] = hsi.HSI(self,data ={
                    'COURSE': self.data_items[self.hsi_mapping['COURSE']],
                    'CDI': self.data_items[self.hsi_mapping['CDI']],
                    'GSI': self.data_items[self.hsi_mapping['GSI']],
                    'HEAD': self.data_items[self.hsi_mapping['HEAD']],
                    }
                )
                self.insturments[count].gsi_enabled = i.get('options',{"gsi_enabled": True}).get('gsi_enabled', True)
                self.insturments[count].cdi_enabled = i.get('options',{"cdi_enabled": True}).get('cdi_enabled', True)
            elif i['type'] == 'heading_display':
                self.insturments[count] = hsi.HeadingDisplay(self,data=self.data_items[self.lookup_mapping('HEAD',i.get('mapping',dict()))])
                self.insturments[count].font_size = self.insturments[count].font_size = i.get('options',{"font_size": 17}).get('font_size', 17)  


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
            elif self.insturment_config[inst]['type'] == 'atitude_indicator':
                # Should verify each and only update if for example db_item = 'PITCH'
                self.insturments[inst].setPitchAngle(self.data_items[self.ai_mapping['PITCH']].value)
                self.insturments[inst].setRollAngle(self.data_items[self.ai_mapping['ROLL']].value)
                self.insturments[inst].setLateralAcceleration(self.data_items[self.ai_mapping['ALAT']].value)
                self.insturments[inst].setTrueAirspeed(self.data_items[self.ai_mapping['TAS']].value)
            elif self.insturment_config[inst]['type'] == 'turn_coordinator':
                self.insturments[inst].setLatAcc(self.data_items[self.tc_mapping['ALAT']].value)
                self.insturments[inst].setROT(self.data_items[self.tc_mapping['ROT']].value)
            elif self.insturment_config[inst]['type'] == 'horizontal_situation_indicator':
                self.insturments[inst].setHeadingBug(self.data_items[self.hsi_mapping['COURSE']].value)
                self.insturments[inst].setCdi(self.data_items[self.hsi_mapping['CDI']].value)
                self.insturments[inst].setGsi(self.data_items[self.hsi_mapping['GSI']].value)
                self.insturments[inst].setHeading(self.data_items[self.hsi_mapping['HEAD']].value)
            elif self.insturment_config[inst]['type'] == 'heading_display':
                self.insturments[inst].setHeading(self.data_items[db_item].value)



    def data_redraw(self,db_item):
        print(f"redraw: {db_item}")
        for inst in self.data_distribution[db_item]:
            if self.insturment_config[inst]['type'] == 'vsi_dial':
                self.insturments[inst].setROC(self.data_items[db_item].value)
            elif self.insturment_config[inst]['type'] == 'altimeter_dial':
                self.insturments[inst].setAltimeter(self.data_items[db_item].value)
            elif self.insturment_config[inst]['type'] == 'airspeed_dial':
                self.insturments[inst].setAirspeed(self.data_items[db_item].value)
            elif self.insturment_config[inst]['type'] == 'turn_coordinator':
                self.insturments[inst].setHeading(self.data_items[db_item].value)

            self.insturments[inst].update()
            

    def grid_layout(self):
        count = 1
        for i,c in self.insturment_config.items():
            grid_width = self.width() / int(self.layout['columns'])
            grid_height = self.height() / int(self.layout['rows'])
            grid_x = grid_width * (int(c['column']) - 1) 
            grid_y = grid_height * (int(c['row']) - 1) 

            # Span columns to the right and rows down
            if 'span' in c:
                if 'rows' in c['span']:
                    # spanning rows
                    if c['span']['rows'] >= 2:
                        grid_height = grid_height * int(c['span']['rows'])
                if 'columns' in c['span']:
                    #spanning columns
                    if c['span']['columns'] >= 2:
                        grid_width = grid_width * int(c['span']['columns'])


            width = grid_width
            height = grid_height
            x = grid_x
            y = grid_y

            if 'move' in c:
                if 'shrink' in c['move']:
                    if (c['move'].get('shrink',0) < 99 ) and (c['move'].get('shrink',0) >= 0):
                        # Valid shrink percentage
                        width = grid_width - (grid_width * c['move'].get('shrink',0)/ 100)
                        height = grid_height - (grid_height * c['move'].get('shrink',0)/ 100)
                    else:
                        raise Exception("shrink must be a valid number between 1 and 99")
                    justified_horizontal = False
                    justified_vertical = False 
                    if 'justify' in c['move']:
                        for j in c['move']['justify']:
                            if j == 'left':
                                x = grid_x
                                justified_horizontal = True
                            elif j == 'right':
                                x = grid_x + ( grid_width - width)
                                justified_horizontal = True
                            if j == 'top':
                                y = grid_y
                                justified_vertical = True
                            elif j == 'bottom':
                                y = grid_y + ( grid_height - height)
                                justified_vertical = True
                    
                    # Default is to center
                    if not justified_horizontal:
                        x = grid_x + (( grid_width - width) / 2)
                    if not justified_vertical:
                        y = grid_y + (( grid_height - height) / 2) 
            print(f"{x} {y} {width} {height}")
            self.move_resize_inst(i,qRound(x),qRound(y),qRound(width),qRound(height))
            
    def move_resize_inst(self,inst,x,y,width,height):
        self.insturments[inst].move(x,y)
        self.insturments[inst].resize(width,height)


    def resizeEvent(self, event):
        if not self.init:
            self.init_screen()

        if self.layout['type'] == 'grid':
            self.grid_layout()
    def get_config_item(self, key):
        return self.parent.get_config_item(self, key)
