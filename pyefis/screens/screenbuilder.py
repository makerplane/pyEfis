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
        self.inst_name_map = {
            # This allows us to easily change the name used in the config
            # Figured once all gauges were done a common naming scheme 
            # might be more obvious
            # Code_Name: Config_Name
            "ASID":  "airspeed_dial",
            "ALTD":  "altimeter_dial",
            "AG":    "arc_gauge",
            "AI":    "atitude_indicator",
            "HEADD": "heading_display",
            "HSI":   "horizontal_situation_indicator",
            "TC":    "turn_coordinator",
            "VSID":  "vsi_dial"

        }


    def init_screen(self):
        self.mapping = defaultdict(lambda: defaultdict())

        self.layout = self.parent.get_config_item(self,'layout')
        self.data_items = dict()
        self.data_distribution = defaultdict(list)
        self.instruments = dict()
        self.insturment_config = dict ()
        # Setup instruments:
        count = 1
        for i in self.get_config_item('instruments'):
            self.insturment_config[count] = i
            # Get the default items for this instrument
            default_items = self.get_instrument_defaults( i['type'])
            db_items = []
            if default_items:
                #This instrument has default items
                db_items = default_items
            else:
                #No default for this Instrument, db_item is required
                if not 'db_item' in i:
                    raise Exception(f"Instrument {i['type']} does not have a default data item, you must specify db_item:")
                else:
                    db_items = [i['db_item']]

            # deal with mapping
            if len(db_items) > 1:
                # Mapping is specified and is only valid for instrument that have multiple items
                for d in default_items:
                    self.mapping[i['type']][d] = self.lookup_mapping(d,i.get('mapping',dict()))

            # keep track of what instruments use what data items 
            for item in db_items:
                    self.define_data(count,item)
                    self.data_distribution[item].append(count)
            # Process the type of gauge this is and create them
            if i['type'] == 'airspeed_dial':
                self.instruments[count] = airspeed.Airspeed(self,data=self.data_items[self.lookup_mapping('IAS',i.get('mapping',dict()))])
            elif i['type'] == 'altimeter_dial':
                self.instruments[count] = altimeter.Altimeter(self,data=self.data_items[self.lookup_mapping('ALT',i.get('mapping',dict()))])
            elif i['type'] == 'atitude_indicator':
                self.instruments[count] = ai.AI(self,data=self.get_data_dict(i['type']))
                self.instruments[count].fontSize = i.get('options',{"font_size": 12}).get('font_size', 12)
                self.instruments[count].bankMarkSize = i.get('options',{'bankMarkSize': 7}).get('bankMarkSize', 7)
                self.instruments[count].pitchDegreesShown = i.get('options',{'pitchDegreesShown': 60}).get('pitchDegreesShown', 60)
            elif i['type'] == 'heading_display':
                self.instruments[count] = hsi.HeadingDisplay(self,data=self.data_items[self.lookup_mapping('HEAD',i.get('mapping',dict()))])
                self.instruments[count].font_size = self.instruments[count].font_size = i.get('options',{"font_size": 17}).get('font_size', 17)
            elif i['type'] == 'horizontal_situation_indicator':
                self.instruments[count] = hsi.HSI(self,data=self.get_data_dict(i['type']))
                self.instruments[count].gsi_enabled = i.get('options',{"gsi_enabled": True}).get('gsi_enabled', True)
                self.instruments[count].cdi_enabled = i.get('options',{"cdi_enabled": True}).get('cdi_enabled', True)
            elif i['type'] == 'turn_coordinator':
                self.instruments[count] = tc.TurnCoordinator(self,data=self.get_data_dict(i['type']))
            elif i['type'] == self.inst_name_map['VSID']:
                self.instruments[count] = vsi.VSI_Dial(self,data=self.data_items[self.lookup_mapping('VS',i.get('mapping',dict()))])


            count += 1
        #Place instruments:
        if self.layout['type'] == 'grid':
            self.grid_layout()
        self.init = True

    def get_data_dict(self,inst):
        #Returns a dict with the data items a multi-item gauge needs
        r = dict()
        for name, item in self.mapping[inst].items():
            r[name] = self.data_items[item]
        return r

    def lookup_mapping(self,item,mapping=dict()):
          return mapping.get(item,item)

    def get_instrument_defaults(self, inst):
        # Always return an array for simplicity
        # a value of boolean false indicates that no default value exists and db_item must be provided
        if 'airspeed_dial' == inst:
            return ['IAS']
        elif 'altimeter_dial' == inst:
            return ['ALT']
        elif 'atitude_indicator' == inst:
            return ['PITCH','ROLL','ALAT','TAS']
        elif 'heading_display' == inst:
            return ['HEAD']
        elif 'horizontal_situation_indicator' == inst:
            return ['COURSE','CDI','GSI','HEAD']
        elif 'turn_coordinator' == inst:
            return ['ROT','ALAT']
        elif self.inst_name_map['VSID'] == inst:
            return ['VS']

    def get_instrument_default_options(self, inst):
        if i['type'] == 'heading_display':
            return {'font_size': 17}
        
        return false

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
            if   self.insturment_config[inst]['type'] == 'airspeed_dial':
                self.instruments[inst].setAirspeed(self.data_items[db_item].value)
            elif self.insturment_config[inst]['type'] == 'altimeter_dial':
                self.instruments[inst].setAltimeter(self.data_items[db_item].value)
            elif self.insturment_config[inst]['type'] == 'atitude_indicator':
                # Should verify each and only update if for example db_item = 'PITCH'
                self.instruments[inst].setPitchAngle(self.data_items[self.mapping[self.inst_name_map['AI']]['PITCH']].value)
                self.instruments[inst].setRollAngle(self.data_items[self.mapping[self.inst_name_map['AI']]['ROLL']].value)
                self.instruments[inst].setLateralAcceleration(self.data_items[self.mapping[self.inst_name_map['AI']]['ALAT']].value)
                self.instruments[inst].setTrueAirspeed(self.data_items[self.mapping[self.inst_name_map['AI']]['TAS']].value)
            elif self.insturment_config[inst]['type'] == 'heading_display':
                self.instruments[inst].setHeading(self.data_items[db_item].value)
            elif self.insturment_config[inst]['type'] == 'horizontal_situation_indicator':
                self.instruments[inst].setHeadingBug(self.data_items[self.mapping[self.inst_name_map['HSI']]['COURSE']].value)
                self.instruments[inst].setCdi(self.data_items[self.mapping[self.inst_name_map['HSI']]['CDI']].value)
                self.instruments[inst].setGsi(self.data_items[self.mapping[self.inst_name_map['HSI']]['GSI']].value)
                self.instruments[inst].setHeading(self.data_items[self.mapping[self.inst_name_map['HSI']]['HEAD']].value)
            elif self.insturment_config[inst]['type'] == 'turn_coordinator':
                self.instruments[inst].setLatAcc(self.data_items[self.mapping[self.inst_name_map['TC']]['ALAT']].value)
                self.instruments[inst].setROT(self.data_items[self.mapping[self.inst_name_map['TC']]['ROT']].value)
            elif self.insturment_config[inst]['type'] == self.inst_name_map['VSID']:
                self.instruments[inst].setROC(self.data_items[db_item].value)




    def data_redraw(self,db_item):
        print(f"redraw: {db_item}")
        for inst in self.data_distribution[db_item]:
            if self.insturment_config[inst]['type'] == 'airspeed_dial':
                self.instruments[inst].setAirspeed(self.data_items[db_item].value)
            elif self.insturment_config[inst]['type'] == 'altimeter_dial':
                self.instruments[inst].setAltimeter(self.data_items[db_item].value)
            elif self.insturment_config[inst]['type'] == self.inst_name_map['VSID']:
                self.instruments[inst].setROC(self.data_items[db_item].value)

            self.instruments[inst].update()
            

    def grid_layout(self):
        count = 1
        for i,c in self.insturment_config.items():
            topm = 0
            leftm = 0
            rightm = 0
            bottomm = 0
            # Margins in %
            if 'margin' in self.layout:
                if 'top' in self.layout['margin'] and self.layout['margin']['top'] > 0 and self.layout['margin']['top'] < 100:
                    topm = self.height() * ( self.layout['margin']['top'] / 100 )
                if 'bottom' in self.layout['margin'] and self.layout['margin']['bottom'] > 0 and self.layout['margin']['bottom'] < 100:
                    bottomm = self.height() * ( self.layout['margin']['bottom'] / 100 )
                if 'left' in self.layout['margin'] and self.layout['margin']['left'] > 0 and self.layout['margin']['left'] < 100:
                    leftm = self.height() * ( self.layout['margin']['left'] / 100 )
                if 'right' in self.layout['margin'] and self.layout['margin']['right'] > 0 and self.layout['margin']['right'] < 100:
                    rightm = self.height() * ( self.layout['margin']['right'] / 100 )

            grid_width = ( self.width() - leftm - rightm ) / int(self.layout['columns'])
            grid_height = ( self.height() - topm - bottomm ) / int(self.layout['rows'])
            grid_x = leftm + grid_width * (int(c['column']) - 1) 
            grid_y = topm + grid_height * (int(c['row']) - 1) 
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
        self.instruments[inst].move(x,y)
        self.instruments[inst].resize(width,height)


    def resizeEvent(self, event):
        if not self.init:
            self.init_screen()

        if self.layout['type'] == 'grid':
            self.grid_layout()
    def get_config_item(self, key):
        return self.parent.get_config_item(self, key)
