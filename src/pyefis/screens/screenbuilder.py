#  Copyright (c) 2016 Phil Birkelbach
#  Copyright (c) 2026 Eric Blevins
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

from PyQt6.QtGui import QColor
from PyQt6.QtCore import QTimer, qRound
from PyQt6.QtWidgets import QWidget

from pyefis.instruments import weston
from pyefis.screens import screenbuilder_config
from pyefis.screens import screenbuilder_display
from pyefis.screens import screenbuilder_encoder
from pyefis.screens import screenbuilder_factory
from pyefis.screens import screenbuilder_layout
from pyefis.screens import screenbuilder_options
from pyefis.screens import screenbuilder_preferences
from pyefis.screens.screenbuilder_overlay import GridOverlay

import pyavtools.fix as fix
import pyavtools.scheduler as scheduler

import logging

logger = logging.getLogger(__name__)


class Screen(QWidget):
    def __init__(self, parent=None,config=None):
        super(Screen, self).__init__(parent)
        self.parent = parent
        p = self.parent.palette()
        self.screenColor = (0, 0, 0)
        self.encoder = None
        self.encoder_input = None
        self.encoder_button = None
        self.encoder_button_input = None
        self.encoder_list = list()
        self.encoder_list_sorted = list()
        self.encoder_current_selection = None
        self.encoder_timestamp = 0
        self.encoder_timeout = 10000
        self.encoder_timer = QTimer(self)
        self.encoder_control = False
        self.display_state_controller = screenbuilder_display.DisplayStateController(self)
        self.encoder_controller = screenbuilder_encoder.EncoderController(self)
        p.setColor(self.backgroundRole(), QColor(*self.screenColor))
        self.setPalette(p)
        self.setAutoFillBackground(True)

        self.init= False
        self.previous_width = self.width()
        self.previous_height = self.height()

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

    def config_expander(self):
        return screenbuilder_config.InstrumentExpander(
            self.parent.config_path,
            self.parent.preferences,
            self.parent.nodeID,
            self.calc_includes,
        )

    def calc_includes(self,i,p_rows,p_cols):
        return screenbuilder_config.InstrumentExpander(
            self.parent.config_path,
            self.parent.preferences,
            self.parent.nodeID,
            None,
        ).calc_includes(i,p_rows,p_cols)

    def load_instrument(self,i,count,replacements=None,row_p=1,col_p=1,relative_x=0,relative_y=0,inst_rows=0,inst_cols=0,state=False):
        expanded_instruments = self.config_expander().expand(
            i,
            replacements,
            row_p,
            col_p,
            relative_x,
            relative_y,
            inst_rows,
            inst_cols,
            state,
        )
        for inst, this_replacements, state in expanded_instruments:
            if 'ganged' in inst['type']:
                #ganged instrument
                if 'gang_type' not in inst:
                    raise Exception(f"Instrument {inst['type']} must also have 'gang_type:' horizontal|vertical specified")
                self.instrument_config[count] = inst
                for g in inst['groups']:
                    for gi in g['instruments']:
                        gi['type'] = inst['type'].replace('ganged_','')
                        gi['options'] = g.get('common_options', dict())|gi.get('options',dict()) #Merge with common_options losing the the instrument
                        self.setup_instruments(count,gi,ganged=True,replace=this_replacements,state=state)
                        gi_disabled = gi['options'].get('disabled', False)
                        if isinstance(gi_disabled,bool) and gi_disabled == True:
                            self.instruments[count].setVisible(False)
                        elif isinstance(gi_disabled,str):
                            check_not = gi_disabled.split(" ")
                            if check_not[0].lower() == 'not':
                                if self.parent.preferences['enabled'][check_not[1]]:
                                    self.instruments[count].setVisible(False)
                            elif not self.parent.preferences['enabled'][gi_disabled]:
                                self.instruments[count].setVisible(False)
                        else:
                            if state:
                                self.display_state_inst[state].append(count)
                                if state > 1:
                                    self.instruments[count].setVisible(False)
                        count += 1     
            else:
                self.setup_instruments(count,inst,replace=this_replacements,state=state)
                inst_disabled = inst.get('options', False)
                if isinstance(inst_disabled, dict):
                    inst_disabled = inst['options'].get('disabled', False)
                if isinstance(inst_disabled,bool) and inst_disabled == True:
                    self.instruments[count].setVisible(False)
                elif isinstance(inst_disabled,str) and not self.parent.preferences['enabled'][inst_disabled]:
                    self.instruments[count].setVisible(False)
                else:
                    if state:
                        self.display_state_inst[state].append(count)
                        if state > 1:
                           self.instruments[count].setVisible(False)
            count += 1
        return count

    def change_display_states(self):
        self.display_state_controller.change()

    def init_screen(self):

        self.layout = self.get_config_item('layout')
        self.encoder = self.get_config_item('encoder')
        self.encoder_button = self.get_config_item('encoder_button')
        self.encoder_timeout = self.get_config_item('encoder_timeout') or self.encoder_timeout

        self.instruments = dict() # Each instrument
        self.instrument_config = dict () # configuration for the instruments

        self.display_state_controller.configure(self.layout, scheduler)

        # Setup instruments:
        count = 0
        for i in self.get_config_item('instruments'):
            if screenbuilder_config.is_disabled(i, self.parent.preferences):
                continue
            count = self.load_instrument(i,count)
        #Place instruments:
        self.grid_layout()
        self.init = True
        if self.layout.get('draw_grid', False):
            self.grid = GridOverlay(self,self.layout)
            self.grid.move(0,0)
            self.grid.resize(self.width(),self.height())

        self.display_state_controller.register_callback(self.layout)
        self.encoder_controller.configure_inputs(fix)

            
    def setup_instruments(self,count,i,ganged=False,replace=None,state=False):
        if not ganged:
            self.instrument_config[count] = i
        font_percent, font_family = screenbuilder_preferences.apply_preferences(
            i,
            self.parent.preferences,
        )
        self.instruments[count] = screenbuilder_factory.create_instrument(
            self,
            i,
            font_percent=font_percent,
            font_family=font_family,
            replace=replace,
        )

        screenbuilder_options.apply_options(self, count, i, state=state)


    def lookup_mapping(self,item,mapping=dict()):
          return mapping.get(item,item)

    def get_instrument_defaults(self, inst):
        return screenbuilder_factory.get_instrument_defaults(inst)

    def get_instrument_default_options(self, inst):
        return screenbuilder_factory.get_instrument_default_options(inst)

    def get_grid_margins(self):
        return screenbuilder_layout.get_grid_margins(self.layout, self.width(), self.height())

    def get_grid_coordinates(self, column, row ):
        return screenbuilder_layout.get_grid_coordinates(
            self.layout,
            self.width(),
            self.height(),
            column,
            row,
        )

    
    def grid_layout(self):
        self.previous_width = self.width()
        self.previous_height = self.height()

        for i,c in self.instrument_config.items():
            ratio = False
            logger.debug(f"{c['type']} {'ganged' in c['type']}")
            if  'ganged' not in c['type'] and hasattr( self.instruments[i], 'getRatio'):
                #This instrument needs a specific ratio
                ratio = self.instruments[i].getRatio()
                ratio = c.get('ratio', ratio)
                logger.debug(f"Instrument {c['type']} has ratio 1:{ratio}")

            geometry = screenbuilder_layout.get_instrument_geometry(
                self.layout,
                self.width(),
                self.height(),
                c,
                ratio,
            )
            x = geometry['x']
            y = geometry['y']
            width = geometry['width']
            height = geometry['height']
            r_width = geometry['render_width']
            r_height = geometry['render_height']

            if 'ganged' in c['type']:
                ganged_ratio = False
                if hasattr( self.instruments[i], 'getRatio'):
                    ganged_ratio = self.instruments[i].getRatio()
                    ganged_ratio = c.get('ratio', ganged_ratio)
                    logger.debug(f"Ganged Instrument {c['type']} has ratio 1:{ganged_ratio}")

                for gang_count, ganged_geometry in enumerate(
                    screenbuilder_layout.get_ganged_geometries(c, x, y, width, height, ganged_ratio)
                ):
                    g_x, g_y, g_width, g_height = ganged_geometry
                    self.move_resize_inst(i + gang_count,qRound(g_x),qRound(g_y),qRound(g_width),qRound(g_height))
                    try:
                        self.instruments[i + gang_count].setupGauge()
                    except:
                        pass

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

    def initScreen(self):
        if not self.init:
            self.init_screen()

    def resizeEvent(self, event):
        if not self.init:
            self.init_screen()

        if self.previous_width != self.width() or self.previous_height != self.height():
            self.grid_layout()

    def get_config_item(self, key):
        return self.parent.get_config_item(self, key)


    def get_bounding_box(self, width, height,x,y,ratio):
        r_width, r_height, r_x, r_y = screenbuilder_layout.get_bounding_box(width, height,x,y,ratio)
        logger.debug(f"x:{x}, r_x:{r_x} y:{y} r_y:{r_y} width:{width} r_width:{r_width} height:{height} r_height:{r_height}")
        return (r_width,r_height,r_x,r_y)


    def closeEvent(self, event):
        try:
            if hasattr(self, 'encoder_timer') and self.encoder_timer is not None:
                self.encoder_timer.stop()
        except Exception:
            pass

        if 'instruments' not in self.__dict__:
            if event is not None:
                super().closeEvent(event)
            return
        for inst in self.instruments:
            try:
                self.instruments[inst].close()
            except Exception:
                logger.exception("Error closing instrument %s", inst)
                pass
        if event is not None:
            super().closeEvent(event)

    def encoderChanged(self,value=0):
        self.encoder_controller.changed(value)

    def encoderButtonChanged(self,value):
        self.encoder_controller.button_changed(value)
