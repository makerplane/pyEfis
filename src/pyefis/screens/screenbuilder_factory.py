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

import os

from PyQt6.QtCore import qRound

from pyefis.instruments import ai
from pyefis.instruments import airspeed
from pyefis.instruments import altimeter
from pyefis.instruments import button
from pyefis.instruments import gauges
from pyefis.instruments import hsi
from pyefis.instruments import listbox
from pyefis.instruments import misc
from pyefis.instruments import tc
from pyefis.instruments import vsi
from pyefis.instruments import weston
from pyefis.instruments import wind
from pyefis.instruments.ai.VirtualVfr import VirtualVfr


def build_weston(screen, config, font_percent=None, font_family=None, replace=None):
    options = config["options"]
    kwargs = {
        "socket": options["socket"],
        "ini": os.path.join(screen.parent.config_path, options["ini"]),
        "command": options["command"],
        "args": options["args"],
    }

    if (
        "span" in config
        and {"rows", "columns"} <= set(config["span"])
        and "row" in config
        and "column" in config
    ):
        _grid_x, _grid_y, grid_width, grid_height = screen.get_grid_coordinates(
            config["column"],
            config["row"],
        )
        kwargs["wide"] = qRound(grid_width * config["span"]["columns"])
        kwargs["high"] = qRound(grid_height * config["span"]["rows"])

    return weston.Weston(screen, **kwargs)


def build_altimeter_tape(
    screen, config, font_percent=None, font_family=None, replace=None
):
    dbkey = "ALT"
    if "options" in config and "dbkey" in config["options"]:
        dbkey = config["options"]["dbkey"]
    return altimeter.Altimeter_Tape(screen, font_family=font_family, dbkey=dbkey)


def build_button(screen, config, font_percent=None, font_family=None, replace=None):
    if "options" in config and "config" in config["options"]:
        return button.Button(
            screen,
            config_file=os.path.join(
                screen.parent.config_path, config["options"]["config"]
            ),
            font_family=font_family,
        )
    raise ValueError("button must specify options: config:")


def build_static_text(
    screen, config, font_percent=None, font_family=None, replace=None
):
    return misc.StaticText(
        text=config["options"]["text"], parent=screen, font_family=font_family
    )


def build_listbox(screen, config, font_percent=None, font_family=None, replace=None):
    return listbox.ListBox(
        screen,
        lists=config["options"]["lists"],
        replace=replace,
        font_family=font_family,
    )


INSTRUMENT_FACTORIES = {
    "weston": build_weston,
    "airspeed_dial": lambda screen, config, font_percent=None, font_family=None, replace=None: airspeed.Airspeed(
        screen, font_family=font_family
    ),
    "airspeed_box": lambda screen, config, font_percent=None, font_family=None, replace=None: airspeed.Airspeed_Box(
        screen, font_family=font_family
    ),
    "airspeed_tape": lambda screen, config, font_percent=None, font_family=None, replace=None: airspeed.Airspeed_Tape(
        screen, font_percent=font_percent
    ),
    "airspeed_trend_tape": lambda screen, config, font_percent=None, font_family=None, replace=None: vsi.AS_Trend_Tape(
        screen, font_family=font_family
    ),
    "altimeter_dial": lambda screen, config, font_percent=None, font_family=None, replace=None: altimeter.Altimeter(
        screen, font_family=font_family
    ),
    "atitude_indicator": lambda screen, config, font_percent=None, font_family=None, replace=None: ai.AI(
        screen, font_percent=font_percent, font_family=font_family
    ),
    "altimeter_tape": build_altimeter_tape,
    "altimeter_trend_tape": lambda screen, config, font_percent=None, font_family=None, replace=None: vsi.Alt_Trend_Tape(
        screen, font_family=font_family
    ),
    "button": build_button,
    "heading_display": lambda screen, config, font_percent=None, font_family=None, replace=None: hsi.HeadingDisplay(
        screen, font_family=font_family
    ),
    "heading_tape": lambda screen, config, font_percent=None, font_family=None, replace=None: hsi.DG_Tape(
        screen, font_family=font_family
    ),
    "horizontal_situation_indicator": lambda screen, config, font_percent=None, font_family=None, replace=None: hsi.HSI(
        screen,
        font_percent=font_percent,
        cdi_enabled=True,
        gsi_enabled=True,
        font_family=font_family,
    ),
    "numeric_display": lambda screen, config, font_percent=None, font_family=None, replace=None: gauges.NumericDisplay(
        screen, font_family=font_family
    ),
    "value_text": lambda screen, config, font_percent=None, font_family=None, replace=None: misc.ValueDisplay(
        screen, font_family=font_family
    ),
    "static_text": build_static_text,
    "turn_coordinator": lambda screen, config, font_percent=None, font_family=None, replace=None: tc.TurnCoordinator(
        screen, font_family=font_family
    ),
    "vsi_dial": lambda screen, config, font_percent=None, font_family=None, replace=None: vsi.VSI_Dial(
        screen, font_family=font_family
    ),
    "vsi_pfd": lambda screen, config, font_percent=None, font_family=None, replace=None: vsi.VSI_PFD(
        screen, font_family=font_family
    ),
    "arc_gauge": lambda screen, config, font_percent=None, font_family=None, replace=None: gauges.ArcGauge(
        screen, min_size=False, font_family=font_family
    ),
    "horizontal_bar_gauge": lambda screen, config, font_percent=None, font_family=None, replace=None: gauges.HorizontalBar(
        screen, min_size=False, font_family=font_family
    ),
    "vertical_bar_gauge": lambda screen, config, font_percent=None, font_family=None, replace=None: gauges.VerticalBar(
        screen, min_size=False, font_family=font_family
    ),
    "virtual_vfr": lambda screen, config, font_percent=None, font_family=None, replace=None: VirtualVfr(
        screen, font_percent=font_percent, font_family=font_family
    ),
    "listbox": build_listbox,
    "wind_display": lambda screen, config, font_percent=None, font_family=None, replace=None: wind.WindDisplay(
        screen, font_family=font_family
    ),
}


INSTRUMENT_DEFAULTS = {
    "airspeed_dial": ["IAS"],
    "airspeed_tape": ["IAS"],
    "airspeed_trend_tape": ["IAS"],
    "airspeed_box": ["IAS", "GS", "TAS"],
    "altimeter_dial": ["ALT"],
    "altimeter_tape": ["ALT"],
    "altimeter_trend_tape": ["ALT"],
    "atitude_indicator": ["PITCH", "ROLL", "ALAT", "TAS"],
    "heading_display": ["HEAD"],
    "heading_tape": ["HEAD"],
    "horizontal_situation_indicator": ["COURSE", "CDI", "GSI", "HEAD"],
    "turn_coordinator": ["ROT", "ALAT"],
    "vsi_dial": ["VS"],
    "vsi_pfd": ["VS"],
    "virtual_vfr": [
        "PITCH",
        "LAT",
        "LONG",
        "HEAD",
        "ALT",
        "PITCH",
        "ROLL",
        "ALAT",
        "TAS",
    ],
}


INSTRUMENT_DEFAULT_OPTIONS = {
    "heading_display": {"font_size": 17},
}


def create_instrument(
    screen, config, font_percent=None, font_family=None, replace=None
):
    factory = INSTRUMENT_FACTORIES.get(config["type"])
    if factory is None:
        raise ValueError(f"Unknown instrument type '{config['type']}'")
    return factory(
        screen,
        config,
        font_percent=font_percent,
        font_family=font_family,
        replace=replace,
    )


def get_instrument_defaults(instrument_type):
    return INSTRUMENT_DEFAULTS.get(instrument_type)


def get_instrument_default_options(instrument_type):
    return INSTRUMENT_DEFAULT_OPTIONS.get(instrument_type, False)
