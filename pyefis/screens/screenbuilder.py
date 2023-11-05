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
from pyefis.instruments.ai.VirtualVfr import VirtualVfr

import pyavtools.fix as fix
from collections import defaultdict
import re
import pyefis.hmi as hmi

import logging

logger=logging.getLogger(__name__)


funcTempF = lambda x: x * (9.0/5.0) + 32.0 
funcTempC = lambda x: x

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
        # airspeed_tape
        # altimeter_dial
        # altimeter_trend_tape # Testing to do
        # arc_gauge
        # atitude_indicator
        # heading_display
        # heading_tape
        # horizontal_bar_gauge
        # horizontal_situation_indicator
        # turn_coordinator
        # vertical_bar_gauge
        # vsi_dial
        # vsi_pfd  # Testing to do



    def init_screen(self):
        self.layout = self.parent.get_config_item(self,'layout')
        self.instruments = dict() # Each instrument
        self.insturment_config = dict () # configuration for the instruments
        # Setup instruments:
        count = 0
        for i in self.get_config_item('instruments'):
            if 'ganged' in i['type']:
                #ganged instrument
                if 'gang_type' not in i:
                    raise Exception(f"Instrument {i['type']} must also have 'gang_type:' horizontal|vertical specified")
                self.insturment_config[count] = i
                for g in i['groups']:
                    for gi in g['instruments']:
                        gi['type'] = i['type'].replace('ganged_','')
                        gi['options'] = g.get('common_options', dict())|gi.get('options',dict()) #Merge with common_options losing the the instrument
                        self.setup_instruments(count,gi,ganged=True)

                        count += 1     
            else:
                self.setup_instruments(count,i)
            count += 1
        #Place instruments:
        #if self.layout['type'] == 'grid':
        self.grid_layout()
        self.init = True

    def setup_instruments(self,count,i,ganged=False):
        if not ganged:
            self.insturment_config[count] = i
        # Get the default items for this instrument
        #default_items = self.get_instrument_defaults( i['type'])
        #dbkey=None
        #if default_items:
        #    #This instrument has default items
        #    dbkey = default_items
        #else:
        #    #No default for this Instrument, db_item is required
        #    if not 'options' in i and not 'dbkey' in i['options']:
        #        raise Exception(f"Instrument {i['type']} does not have a default dbkey, you must specify options:\n  dbkey:")
        #    if 'options' in i and 'dbkey' in i['options']:
        #        dbkey = i['options']['dbkey']            

        # Process the type of instrument this is and create them
        if i['type'] == 'airspeed_dial':
            self.instruments[count] = airspeed.Airspeed(self)
        if i['type'] == 'airspeed_box':
            self.instruments[count] = airspeed.Airspeed_Box(self)
        if i['type'] == 'airspeed_tape':
            self.instruments[count] = airspeed.Airspeed_Tape(self)
        if i['type'] == 'airspeed_trend_tape':
            self.instruments[count] = vsi.AS_Trend_Tape(self)
        elif i['type'] == 'altimeter_dial':
            self.instruments[count] = altimeter.Altimeter(self)
        elif i['type'] == 'atitude_indicator':
            self.instruments[count] = ai.AI(self)
        elif i['type'] == 'altimeter_tape':
            self.instruments[count] = altimeter.Altimeter_Tape(self)
        elif i['type'] == 'heading_display':
            self.instruments[count] = hsi.HeadingDisplay(self)
        elif i['type'] == 'heading_tape':
            self.instruments[count] = hsi.DG_Tape(self)
        elif i['type'] == 'horizontal_situation_indicator':
            self.instruments[count] = hsi.HSI(self)
        elif i['type'] == 'turn_coordinator':
            self.instruments[count] = tc.TurnCoordinator(self)
        elif i['type'] == 'vsi_dial':
            self.instruments[count] = vsi.VSI_Dial(self)
        # Gauges
        elif i['type'] == 'arc_gauge':
            self.instruments[count] = gauges.ArcGauge(self)
        elif i['type'] == 'horizontal_bar_gauge':
            self.instruments[count] = gauges.HorizontalBar(self)
        elif i['type'] == 'vertical_bar_gauge':
            self.instruments[count] = gauges.VerticalBar(self)
        elif i['type'] == 'virtual_vfr':
            self.instruments[count] = VirtualVfr(self)

         # Set options
        if 'options' in i:
            #loop over each option
            for option,value in i['options'].items():
                if 'egt_mode_switching' == option and (value == True) and i['type'] == 'vertical_bar_gauge':
                    hmi.actions.setEgtMode.connect(self.instruments[count].setMode)
                    next
                if 'dbkey' in option: 
                    self.instruments[count].setDbkey(value)
                    next
                if 'temperature' in option and value == True and 'gauge' in i['type']:
                    self.instruments[count].conversionFunction1 = funcTempF
                    self.instruments[count].unitsOverride1 = u'\N{DEGREE SIGN}F'
                    self.instruments[count].conversionFunction2 = funcTempC
                    self.instruments[count].unitsOverride2 = u'\N{DEGREE SIGN}C'
                    self.instruments[count].unitGroup = 'Temperature'
                    self.instruments[count].setUnitSwitching()
                    next
                else:
                    setattr(self.instruments[count], option, value)


    def lookup_mapping(self,item,mapping=dict()):
          return mapping.get(item,item)

    def signal_mapping(self, inst):
        # returns what signals an instrument needs 
        pass        

    def get_instrument_defaults(self, inst):
        # Always return an array for simplicity
        # a value of boolean false indicates that no default value exists and db_item must be provided
        if inst in ['airspeed_dial','airspeed_tape', 'airspeed_box', 'airspeed_trend_tape']:
            return ['IAS']
        elif inst in ['airspeed_box']:
            return ['IAS','GS','TAS']
        elif inst in ['altimeter_dial', 'altimeter_tape', 'altimeter_trend_tape' ]:
            return ['ALT']
        elif 'atitude_indicator' == inst:
            return ['PITCH','ROLL','ALAT','TAS']
        elif inst in [ 'heading_display', 'heading_tape']:
            return ['HEAD']
        elif 'horizontal_situation_indicator' == inst:
            return ['COURSE','CDI','GSI','HEAD']
        elif 'turn_coordinator' == inst:
            return ['ROT','ALAT']
        elif 'vsi_dial' == inst:
            return ['VS']
        elif 'virtual_vfr' == inst:
            return ['PITCH','LAT','LONG','HEAD','ALT','PITCH','ROLL','ALAT','TAS']

    def get_instrument_default_options(self, inst):
        if inst == 'heading_display':
            return {'font_size': 17}
        
        return false




    def grid_layout(self):
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


            width = r_width = grid_width
            height = r_height = grid_height
            x = r_x = grid_x
            y = r_y = grid_y

            # Here we need the size of the object for things that need to have specific dimensions
            # example the round gauges
            # need to know if a specific type needs a specific ratio or not
            # we will get this from the instrument.
            ratio = False
            logger.debug(f"{c['type']} {'ganged' in c['type']}")
            if  'ganged' not in c['type'] and hasattr( self.instruments[i], 'getRatio'):
                #This instrument needs a specific ratio
                ratio = self.instruments[i].getRatio()
                logger.debug(f"Instrument {c['type']} has ratio 1:{ratio}")
                r_width,r_height,r_x,r_y = self.get_bounding_box(width, height,x,y,ratio)

            if 'move' in c:
                if 'shrink' in c['move']:
                    if (c['move'].get('shrink',0) < 99 ) and (c['move'].get('shrink',0) >= 0):
                        # Valid shrink percentage
                        r_width = r_width - (r_width * c['move'].get('shrink',0)/ 100)
                        r_height = r_height - (r_height * c['move'].get('shrink',0)/ 100)
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
                                x = grid_x + ( grid_width - r_width)
                                justified_horizontal = True
                            if j == 'top':
                                y = grid_y
                                justified_vertical = True
                            elif j == 'bottom':
                                y = grid_y + ( grid_height - r_height)
                                justified_vertical = True
                    # Default is to center
                    if not justified_horizontal:
                        x = grid_x + (( grid_width - r_width) / 2)
                    if not justified_vertical:
                        y = grid_y + (( grid_height - r_height) / 2) 
            elif ratio:
                x = grid_x + (( grid_width - r_width) / 2)
                y = grid_y + (( grid_height - r_height) / 2)

            if 'ganged' in c['type']:
                inst_count = 0
                gang_count = 0
                groups = 0
                for g in c['groups']:
                    inst_count += len(g['instruments'])
                    groups += 1
                if 'horizontal' in c['gang_type']:
                    total_gaps = (groups - 1) * (width * (2/100))
                else: 
                    total_gaps = (groups -1 ) * (height * (6/100))
                gap_size = 0
                if groups > 1:
                    gap_size = total_gaps / ( groups - 1) 
                group = -1
                group_x = x
                group_y = y
                if 'horizontal' in c['gang_type']:
                    group_width = (width - total_gaps) / inst_count 
                    group_height = height
                else:
                    group_height = (height - total_gaps) / inst_count 
                    group_width = width

                for g in c['groups']:
                    # Render some tiles?
                    for ci in g['instruments']:
                        g_width = group_width
                        g_height = group_height
                        g_x = group_x
                        g_y = group_y
                        if hasattr( self.instruments[i], 'getRatio'):
                            g_ratio = self.instruments[i].getRatio()
                            logger.debug(f"Ganged Instrument {c['type']} has ratio 1:{g_ratio}")
                            g_width,g_height,g_x,g_y = self.get_bounding_box(g_width, g_height,g_x,g_y,g_ratio)

                        self.move_resize_inst(i + gang_count,qRound(g_x),qRound(g_y),qRound(g_width),qRound(g_height))
                        try:
                            self.instruments[i + gang_count].setupGauge()
                        except:
                            pass
                        if 'horizontal' in c['gang_type']:
                            group_x += group_width
                        else:
                            group_y += group_height
                        gang_count += 1
                    if 'horizontal' in c['gang_type']:
                        group_x += gap_size
                    else:
                        group_y += gap_size


            else:
                self.move_resize_inst(i,qRound(x),qRound(y),qRound(r_width),qRound(r_height))
            try:
                # Gauges need this run to set them up
                self.instruments[i].setupGauge()
            except:
                pass


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


    def get_bounding_box(self, width, height,x,y,ratio):
        if width < height:
            r_height = width / ratio
            r_width = width
            if height < r_height:
                r_height = height
                r_width = height * ratio
        else:
            r_width = height * ratio
            r_height = height
            if width < r_width:
                r_height = width / ratio
                r_width = width
        # r_height and r_width are in correct ratio to fit within the box
        if r_height == height:
            # It is the width we need to center
            r_y = y
            r_x = x + ((width - r_width)/2)
        else:
            # If is the height we need to center
            r_x = x
            r_y = y + ((height - r_height)/2)
        logger.debug(f"x:{x}, r_x:{r_x} y:{y} r_y:{r_y} width:{width} r_width:{r_width} height:{height} r_height:{r_height}")
        return (r_width,r_height,r_x,r_y)
