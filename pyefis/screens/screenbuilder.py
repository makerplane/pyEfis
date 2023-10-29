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
from pyefis.instruments import gauges
from pyefis.instruments import misc

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

        # list of dial types supported so far:
        # airspeed_dial
        # airspeed_trend_tape # Testing to do
        # altimeter_dial
        # altimeter_trend_tape # Testing to do
        # arc_gauge
        # atitude_indicator
        # heading_display
        # horizontal_situation_indicator
        # turn_coordinator
        # vsi_dial
        # vsi_pfd  # Testing to do



    def init_screen(self):
        self.mapping = defaultdict(lambda: defaultdict())

        self.layout = self.parent.get_config_item(self,'layout')
        self.data_items = dict() # Each data item
        self.data_distribution = defaultdict(list) # Keeps track of what instruments need sent what pieces of data
        self.instruments = dict() # Each instrument
        self.insturment_config = dict () # configuration for the instruments
        self.data_signal_routing = defaultdict(lambda: defaultdict(list))  # Keeps track of the reverse maping for each instrument
        self.data_item_signals_defined = defaultdict(lambda: defaultdict(dict))  # Keeps track of the signals that have been setup for a given data item
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
                    self.data_item_signals_defined[count][self.lookup_mapping(d,i.get('mapping',dict()))] = d
            else:
                self.data_item_signals_defined[count][db_items[0]] = 'None'

            # keep track of what instruments use what data items 
            for item in db_items:
                    self.define_data(count,item,i['type'])
                    self.data_distribution[item].append(count)
            # Process the type of instrument this is and create them
            if i['type'] == 'airspeed_dial':
                self.instruments[count] = airspeed.Airspeed(self,data=self.data_items[db_items[0]])
            elif i['type'] == 'altimeter_dial':
                self.instruments[count] = altimeter.Altimeter(self,data=self.data_items[db_items[0]])
            elif i['type'] == 'atitude_indicator':
                self.instruments[count] = ai.AI(self,data=self.get_data_dict(i['type']))
                #self.instruments[count].fontSize = i.get('options',{"font_size": 12}).get('font_size', 12)
                #self.instruments[count].bankMarkSize = i.get('options',{'bankMarkSize': 7}).get('bankMarkSize', 7)
                #self.instruments[count].pitchDegreesShown = i.get('options',{'pitchDegreesShown': 60}).get('pitchDegreesShown', 60)
            elif i['type'] == 'heading_display':
                self.instruments[count] = hsi.HeadingDisplay(self,data=self.data_items[db_items[0]])
            elif i['type'] == 'horizontal_situation_indicator':
                self.instruments[count] = hsi.HSI(self,data=self.get_data_dict(i['type']))
            elif i['type'] == 'turn_coordinator':
                self.instruments[count] = tc.TurnCoordinator(self,data=self.get_data_dict(i['type']))
            elif i['type'] == 'vsi_dial':
                self.instruments[count] = vsi.VSI_Dial(self,data=self.data_items[db_items[0]])
            # Gauges
            elif i['type'] == 'arc_gauge':
                self.instruments[count] = gauges.ArcGauge(self,data=self.data_items[db_items[0]])

            # Set options
            if 'options' in i:
                #loop over each option
                for option,value in i['options'].items():
                    setattr(self.instruments[count], option, value)

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

    def signal_mapping(self, inst):
        # returns what signals an instrument needs 
        pass        

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
        elif 'vsi_dial' == inst:
            return ['VS']

    def get_instrument_default_options(self, inst):
        if i['type'] == 'heading_display':
            return {'font_size': 17}
        
        return false

    def define_data(self, count, item, item_type):
        if not item in self.data_items:
            print(f"db item: {item}")
            self.data_items[item] = fix.db.get_item(item)
            print(self.data_items[item].dtype)
            if self.data_items[item].dtype == float:
                self.data_items[item].valueChanged[float].connect(lambda valueChanged, key=item: self.data_modified(db_item=key) )
            if self.data_items[item].dtype == str:
                self.data_items[item].valueChanged[str].connect(lambda valueChanged, key=item: self.data_modified(db_item=key))
            if self.data_items[item].dtype == bool:
                self.data_items[item].valueChanged[bool].connect(lambda valueChanged, key=item: self.data_modified(db_item=key))
            if self.data_items[item].dtype == int:
                self.data_items[item].valueChanged[int].connect(lambda valueChanged, key=item: self.data_modified(db_item=key))

        # Not All gauges need all of the signals
        # We will only subscribe to the ones we need that have not already been subscripbed
        if 'old' in self.what_signals(item_type) and not ('old' in self.data_item_signals_defined[item][count]):
            self.data_items[item].oldChanged[bool].connect(lambda oldChanged, key=item: self.data_redraw(db_item=key))
            self.data_item_signals_defined[item][count] = 'old'
            self.data_signal_routing[item]['old'].append(count)

        if 'bad' in self.what_signals(item_type) and not ('bad' in self.data_item_signals_defined[item][count]):
            self.data_items[item].badChanged[bool].connect(lambda badChanged, key=item: self.data_redraw(db_item=key))
            self.data_item_signals_defined[item][count] = 'bad'
            self.data_signal_routing[item]['old'].append(count)

        if 'fail' in self.what_signals(item_type) and not ('fail' in self.data_item_signals_defined[item][count]):
            self.data_items[item].failChanged[bool].connect(lambda failChanged, key=item: self.data_redraw(db_item=key))
            self.data_item_signals_defined[item][count] = 'fail'
            self.data_signal_routing[item]['old'].append(count)

        if 'aux' in self.what_signals(item_type) and not ('aux' in self.data_item_signals_defined[item][count]):
            self.data_items[item].auxChanged.connect(lambda auxChanged, key=item: self.aux_data_modified(db_item=key))
            self.data_item_signals_defined[item][count] = 'aux'
            self.data_signal_routing[item]['aux'].append(count)

        if 'ann' in self.what_signals(item_type) and not ('ann' in self.data_item_signals_defined[item][count]):
            self.data_items[item].annunciateChanged[bool].connect(lambda annunciateChanged, key=item: self.report_received(db_item=key))
            self.data_item_signals_defined[item][count] = 'ann'
            self.data_signal_routing[item]['report'].append(count)

        if 'report' in self.what_signals(item_type) and not ('report' in self.data_item_signals_defined[item][count]):
            self.data_items[item].reportReceived.connect(self.report_received)
            self.data_item_signals_defined[item][count] = 'report'
            self.data_signal_routing[item]['report'].append(count)

    def what_signals(self, it):
        # Returns what signals are used for the instrument type
        if 'static' in it:
            return []
        elif 'gauge' in it:
            return ['old', 'bad', 'fail', 'aux', 'ann', 'report' ]
        return ['old', 'bad', 'fail']

    def data_modified(self,db_item):
        print(f"modified: {db_item}")
        for inst in self.data_signal_routing[db_item]['old']:
            self.instruments[inst].setData(db_item,self.data_items[db_item].value)

    def aux_data_modified(self,db_item):
        print(f"aux {db_item}")
        for inst in self.data_signal_routing[db_item]['aux']:
            self.instruments[inst].setAuxData(self.data_items[db_item].aux)

    def report_received(self,db_item='t'):
        print(f"report {db_item}")
        for inst in self.data_signal_routing[db_item]['report']:
            self.instruments[inst].setupGauge()#self.data_items[db_item].aux)

    def data_redraw(self,db_item):
        print(f"redraw: {db_item}")
        for inst in self.data_signal_routing[db_item]['old']:
            self.instruments[inst].update()
            try:
                self.instruments[inst].setupGauge()
            except:
                pass            

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
