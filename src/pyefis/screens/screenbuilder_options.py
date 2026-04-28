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

import pyefis.hmi as hmi


funcTempF = lambda x: x * (9.0/5.0) + 32.0
funcTempC = lambda x: x

funcPressHpa = lambda x: x * 33.863889532610884
funcPressInHg = lambda x: x

funcAltitudeMeters = lambda x: x / 3.28084
funcAltitudeFeet = lambda x: x


def configure_unit_switching(instrument, unit_group, unit1, unit2, conversion1, conversion2):
    instrument.conversionFunction1 = conversion1
    instrument.unitsOverride1 = unit1
    instrument.conversionFunction2 = conversion2
    instrument.unitsOverride2 = unit2
    instrument.unitGroup = unit_group
    instrument.setUnitSwitching()


def apply_options(screen, index, config, state=False):
    if 'options' not in config:
        return

    instrument = screen.instruments[index]
    for option, value in config['options'].items():
        if 'encoder_order' == option and not state:
            if callable(getattr(instrument, 'enc_selectable', None)):
                screen.encoder_list.append({'inst': index, 'order': config['options']['encoder_order']})
            continue

        if 'egt_mode_switching' == option and value == True and config['type'] == 'vertical_bar_gauge':
            hmi.actions.setEgtMode.connect(instrument.setMode)
            continue

        if 'dbkey' in option:
            if callable(getattr(instrument, 'setDbkey', None)):
                instrument.setDbkey(value)
            else:
                setattr(instrument, option, value)
            continue

        if 'temperature' in option and value == True and ('gauge' in config['type'] or config['type'] == 'numeric_display'):
            configure_unit_switching(
                instrument,
                'Temperature',
                u'\N{DEGREE SIGN}F',
                u'\N{DEGREE SIGN}C',
                funcTempF,
                funcTempC,
            )
            continue

        elif 'pressure' in option and value == True and ('gauge' in config['type'] or config['type'] == 'numeric_display'):
            configure_unit_switching(
                instrument,
                'Pressure',
                'inHg',
                'hPa',
                funcPressInHg,
                funcPressHpa,
            )
            continue

        elif 'altitude' in option and value == True and (config['type'] in ['gauge', 'numeric_display','altimeter_tape','altimeter_dial']):
            configure_unit_switching(
                instrument,
                'Altitude',
                'Ft',
                'M',
                funcAltitudeFeet,
                funcAltitudeMeters,
            )
            continue

        else:
            setattr(instrument, option, value)
