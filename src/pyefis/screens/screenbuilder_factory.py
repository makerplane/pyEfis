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
from pyefis.instruments import data_status
from pyefis.instruments import gauges
from pyefis.instruments import hsi
from pyefis.instruments import listbox
from pyefis.instruments import map as moving_map
from pyefis.instruments import misc
from pyefis.instruments import tc
from pyefis.instruments import vsi
from pyefis.instruments import weston
from pyefis.instruments import wind
from pyefis.instruments.ai.VirtualVfr import VirtualVfr
from pyefis.screens.instrument_spec import (
    Binding, InstrumentSpec, Prop, FixValue)


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
    # Forward the supported tape options from the screen config. Previously
    # only dbkey was passed, so minorDiv/majorDiv/maxalt/total_decimals/
    # font_mask in the YAML were silently ignored and the tape always used
    # its hardcoded defaults (e.g. a VS tape kept minorDiv=100 no matter what
    # the config said). Only keys present in the config are forwarded, so the
    # constructor defaults still apply to anything unset.
    opts = config.get("options") or {}
    kwargs = {}
    for k in ("dbkey", "maxalt", "majorDiv", "minorDiv", "total_decimals",
              "font_mask", "round_to", "numeric_box", "font_scale",
              "show_trend", "trend_lookahead"):
        if k in opts:
            kwargs[k] = opts[k]
    return altimeter.Altimeter_Tape(
        screen, font_family=font_family, **kwargs)


def build_atitude_indicator(
    screen, config, font_percent=None, font_family=None, replace=None
):
    opts = config.get("options", {}) or {}
    show_fpm = opts.get("show_fpm", True)
    widget = ai.AI(
        screen, font_percent=font_percent, font_family=font_family,
        show_fpm=show_fpm,
    )
    widget.aircraft_symbol = opts.get("aircraft_symbol", "classic")
    widget.symbol_color = opts.get("symbol_color", "yellow")
    if "svs" in opts:
        widget.set_svs_config(opts["svs"])
    return widget


def build_virtual_vfr(
    screen, config, font_percent=None, font_family=None, replace=None
):
    opts = config.get("options", {}) or {}
    widget = VirtualVfr(screen, font_percent=font_percent, font_family=font_family)
    # VirtualVfr inherits set_svs_config from AI; SVS config flows through
    # the same way regardless of which widget type the screen uses.
    widget.aircraft_symbol = opts.get("aircraft_symbol", "classic")
    widget.symbol_color = opts.get("symbol_color", "yellow")
    # SVS config: the legacy nested `svs:` dict, overlaid with the flat svs_*
    # editor options (svs_<key> -> <key>). Only configure SVS when it is
    # actually enabled (or a legacy block is present), so panels that don't use
    # synthetic vision are untouched.
    svs_cfg = dict(opts.get("svs") or {})
    svs_cfg.update({k[4:]: v for k, v in opts.items() if k.startswith("svs_")})
    if opts.get("svs") or svs_cfg.get("enabled"):
        widget.set_svs_config(svs_cfg)
    return widget


def build_button(screen, config, font_percent=None, font_family=None, replace=None):
    opts = config.get("options", {}) or {}
    # Legacy: an external button YAML referenced by path (hand-authored panels).
    if opts.get("config"):
        return button.Button(
            screen,
            config_file=os.path.join(screen.parent.config_path, opts["config"]),
            font_family=font_family,
        )
    # Inline: the instrument's options ARE the button definition (authored in the
    # configurator). Needs at least a dbkey to bind to.
    if opts.get("dbkey"):
        return button.Button(screen, config=dict(opts), font_family=font_family)
    raise ValueError(
        "button needs options: either 'config:' (an external YAML) or inline "
        "fields including 'dbkey:'")


def build_static_text(
    screen, config, font_percent=None, font_family=None, replace=None
):
    return misc.StaticText(
        text=config["options"]["text"], parent=screen, font_family=font_family,
        fontsize=(1.0 if font_percent is None else font_percent),
    )


def build_data_status(
    screen, config, font_percent=None, font_family=None, replace=None
):
    opts = (config or {}).get("options", {}) or {}
    kwargs = {"parent": screen, "font_family": font_family}
    if "status_path" in opts:
        kwargs["status_path"] = opts["status_path"]
    if "continue_screen" in opts:
        kwargs["continue_screen"] = opts["continue_screen"]
    if "update_command" in opts:
        kwargs["update_command"] = opts["update_command"]
    return data_status.DataStatus(**kwargs)


def build_data_annunciation(
    screen, config, font_percent=None, font_family=None, replace=None
):
    opts = (config or {}).get("options", {}) or {}
    kwargs = {"parent": screen, "font_family": font_family}
    if "status_path" in opts:
        kwargs["status_path"] = opts["status_path"]
    if "target_screen" in opts:
        kwargs["target_screen"] = opts["target_screen"]
    return data_status.DataAnnunciation(**kwargs)


def build_listbox(screen, config, font_percent=None, font_family=None, replace=None):
    return listbox.ListBox(
        screen,
        lists=config["options"]["lists"],
        replace=replace,
        font_family=font_family,
    )


# Every instrument type is migrated -- these legacy lookup tables are populated
# entirely from REGISTRY by the fold-back below. They remain (empty here) for
# existing consumers that import them.
INSTRUMENT_FACTORIES = {}

INSTRUMENT_DEFAULTS = {}

# Legacy per-type default options (curated). Empty now that every type is
# migrated; defaults come from each record's Prop defaults.
INSTRUMENT_DEFAULT_OPTIONS = {}


# ---------------------------------------------------------------------------
# Instrument registry -- the single source of truth for migrated instruments.
#
# Each InstrumentSpec carries the builder PLUS the full editor contract: the
# config properties (category 1), the FIX-database values the instrument reads
# (category 2), twin preview hints (category 3), and the editor flags. The
# editor schema exporter and (by derivation) the configurator twins read from
# here -- so the three mirrors can no longer drift. Instruments not yet
# migrated fall back to the curated metadata in pyefis.editor.schema.
#
# Migration pattern (see docs/adding_an_instrument.md): move an instrument's
# entries out of the curated dicts in editor/schema.py and into a record here.
# ---------------------------------------------------------------------------
REGISTRY: dict[str, InstrumentSpec] = {}


def _register(spec: InstrumentSpec) -> InstrumentSpec:
    REGISTRY[spec.type] = spec
    return spec


def _bg_opacity_prop():
    """Shared background-opacity control for instruments that paint an opaque
    background box. Percent (0-100): 100 = solid (the default, unchanged), 0 =
    transparent so what's behind shows through. Percent (whole numbers) avoids
    the editor's decimal-input limitation. apply='attr' -> widget.bg_opacity."""
    return Prop("bg_opacity", "integer", default=100, minimum=0, maximum=100,
                step=1, label="Background opacity (%)",
                help="0 = transparent (show what's behind), 100 = solid")


def _ai_overlay_props():
    """Full-granular pitch-ladder + bank-arc properties shared by the attitude
    indicator and the synthetic-vision view (both subclass AI). Prop names match
    the widget attributes (apply='attr'), so the gate verifies each exists and
    its default matches the widget. The tick-width / bank-size knobs only take
    effect when tick_autoscale is off (otherwise they scale with the font)."""
    return [
        Prop("pitchDegreesShown", "number", default=30,
             label="Pitch field of view (deg)",
             help="total vertical pitch span shown"),
        Prop("minorDiv", "integer", default=1, label="Minor division (deg)",
             help="pitch interval between the smallest ladder ticks"),
        Prop("majorDiv", "integer", default=5, label="Major division (deg)",
             help="pitch interval between the longer ladder ticks"),
        Prop("numberedDiv", "integer", default=10,
             label="Numbered division (deg)",
             help="pitch interval at which ladder lines get a number"),
        Prop("visiblePitchAngle", "integer", default=15,
             label="Pitch label range (deg)",
             help="ladder marks fade out beyond this from current pitch"),
        Prop("pitchOpacity", "number", default=0.6, minimum=0.0, maximum=1.0,
             label="Pitch ladder opacity",
             help="pitch-ladder opacity (0 = invisible, 1 = solid)"),
        Prop("bankOpacity", "number", default=1.0, minimum=0.0, maximum=1.0,
             label="Bank display opacity",
             help="bank scale, roll pointer, standard-rate diamonds and "
                  "slip/skid ball together (0 = hidden, 1 = solid)"),
        Prop("horizonOpacity", "number", default=1.0, minimum=0.0,
             maximum=1.0, label="Horizon line opacity",
             help="the white zero-pitch reference line "
                  "(0 = hidden, 1 = solid)"),
        Prop("tick_autoscale", "boolean", default=True,
             label="Auto-scale tick widths to font",
             help="off = use the explicit tick-width / bank-size pixels below"),
        Prop("minorDivWidth", "integer", default=10,
             label="Minor tick width (px)",
             help="length of the minor pitch ticks (auto-scale off)"),
        Prop("majorDivWidth", "integer", default=40,
             label="Major tick width (px)",
             help="length of the major pitch ticks (auto-scale off)"),
        Prop("numberedDivWidth", "integer", default=50,
             label="Numbered tick width (px)",
             help="length of the numbered pitch ticks (auto-scale off)"),
        Prop("drawBankMarkers", "boolean", default=True,
             label="Standard-rate bank markers",
             help="show the bank-angle tick arc across the top"),
        Prop("bankAngleMaximum", "integer", default=25,
             label="Max indicated bank (deg)",
             help="largest bank angle marked on the bank arc"),
        Prop("bankMarkSize", "integer", default=10, label="Bank tick size (px)",
             help="length of the bank-arc ticks (auto-scale off)"),
        Prop("bank_position", "number", default=50, minimum=0, maximum=100,
             label="Bank scale position (%)",
             help="vertical position of the bank-arc centre, percent up "
                  "from the bottom (50 = centred, the classic look); the "
                  "whole cluster incl. pointer and slip ball moves with it"),
        Prop("bank_radius", "number", default=100.0 / 3.0, minimum=10,
             maximum=60, step=0.1, label="Bank scale radius (% height)",
             help="radius of the bank arc as a percent of widget height "
                  "(33.3 = the classic height/3); an explicit "
                  "bankAngleRadius px in YAML overrides it"),
        Prop("pitch_ladder_avoid_bank", "boolean", default=False,
             label="Ladder stops below bank arc",
             help="G1000-style declutter: the ladder climbs into the bank "
                  "arch but stops below the slip/skid ball"),
        # Compass heading scale on the white horizon line.
        Prop("horizon_heading_marks", "boolean", default=False,
             label="Horizon heading marks",
             help="tick marks + labels for compass heading along the horizon"),
        Prop("horizon_heading_interval", "integer", default=10, minimum=1,
             maximum=45, step=1, label="Heading tick interval (deg)",
             help="degrees of heading between the horizon ticks"),
        Prop("horizon_heading_label_interval", "integer", default=20, minimum=5,
             maximum=90, step=5, label="Heading label interval (deg)",
             help="degrees of heading between the numeric labels"),
        Prop("horizon_heading_tick_length", "integer", default=5, minimum=1,
             maximum=30, step=1, label="Heading tick length (px)",
             help="length of the horizon heading ticks (px)"),
        Prop("horizon_heading_color", "color", default="#ffffff",
             label="Heading mark colour",
             help="colour of the horizon heading ticks and labels"),
    ]


def _svs_props():
    """Synthetic-vision (terrain) options for virtual_vfr. apply='special':
    build_virtual_vfr strips the ``svs_`` prefix and assembles these into the
    dict handed to ``set_svs_config``. They render on the device's GL terrain and
    are NOT shown in the editor twin preview (config-only; makerplane-data#7)."""
    dev = " (rendered on the device; not shown in the editor preview)"
    return [
        Prop("svs_enabled", "boolean", default=False, apply="special",
             label="Synthetic vision enabled", help="master on/off" + dev),
        Prop("svs_tile_path", "string", default="", apply="special",
             label="Terrain tile path",
             help="SRTM3 HGT tile directory on the device"),
        Prop("svs_range_nm", "number", default=50, apply="special",
             label="Range (NM)", help=dev.strip()),
        Prop("svs_auto_range", "boolean", default=True, apply="special",
             label="Auto range by altitude", help=dev.strip()),
        Prop("svs_min_range_nm", "number", default=8, apply="special",
             label="Min auto range (NM)", help=dev.strip()),
        Prop("svs_palette", "enum", default="clearance",
             enum=["clearance", "subdued", "high_contrast"], apply="special",
             label="Terrain palette",
             help="clearance-band colour scheme" + dev),
        Prop("svs_clearance_green_ft", "number", default=1000, apply="special",
             label="Safe clearance (ft)",
             help="green at/above this height over terrain"),
        Prop("svs_clearance_yellow_ft", "number", default=500, apply="special",
             label="Caution clearance (ft)", help="amber above this; red below"),
        Prop("svs_terrain_fill", "boolean", default=True, apply="special",
             label="Fill terrain", help="off = wireframe" + dev),
        Prop("svs_terrain_grid", "number", default=0.35, minimum=0.0, maximum=1.0,
             apply="special", label="Terrain grid", help=dev.strip()),
        Prop("svs_terrain_texture", "number", default=0.35, minimum=0.0,
             maximum=1.0, apply="special", label="Terrain texture",
             help=dev.strip()),
        Prop("svs_safe_gradient", "boolean", default=True, apply="special",
             label="Safe-band gradient", help=dev.strip()),
        Prop("svs_earth_curvature", "boolean", default=True, apply="special",
             label="Earth curvature", help=dev.strip()),
        Prop("svs_haze", "boolean", default=True, apply="special",
             label="Distance haze", help=dev.strip()),
        Prop("svs_haze_distance_nm", "number", default=40, apply="special",
             label="Haze distance (NM)", help=dev.strip()),
        Prop("svs_dof_db_path", "string", default="", apply="special",
             label="Obstacle DB path",
             help="FAA DOF database on the device (optional)"),
        Prop("svs_water_db_path", "string", default="", apply="special",
             label="Water DB path",
             help="water-polygon database on the device (optional)"),
        Prop("svs_highway_db_path", "string", default="", apply="special",
             label="Highway DB path",
             help="highway database on the device (optional)"),
    ]


_register(InstrumentSpec(
    type="atitude_indicator",
    label="Attitude Indicator",
    category="attitude",
    builder=build_atitude_indicator,
    dbkeys=["PITCH", "ROLL", "ALAT", "TAS"],
    keep_aspect=True,
    svs_capable=True,
    properties=[
        Prop("aircraft_symbol", "enum", default="classic",
             enum=["classic", "garmin", "brackets", "none"],
             label="Aircraft symbol",
             help="classic split-wing bars + dot; garmin G3X-style two-tone "
                  "bat wing + horizon barbs; brackets GRT-style L-brackets; "
                  "none hides the symbol (SVS-as-background) "
                  "(g1000/gi275 remain accepted in YAML for back-compat)"),
        Prop("symbol_color", "color", default="#ffff00", label="Symbol colour",
             help="colour of the fixed aircraft reference symbol"),
        Prop("symbol_scale", "number", default=1.0, minimum=0.3, maximum=3.0,
             step=0.05, label="Symbol scale",
             help="multiplies the reference symbol size -- wingspan and "
                  "proportions together (1 = standard)"),
        Prop("show_fpm", "boolean", default=True, label="Flight-path marker",
             help="GPS flight-path marker (needs VS/GS/TRACK/HEAD)"),
        *_ai_overlay_props(),
    ],
    # Attitude is read directly (PITCH/ROLL); no FIX aux values.
    fix_values=[],
    # Representative pose for the twin (matches the render-tool demo so the
    # editor preview reads like a real panel).
    preview={"pitch": -2.0, "roll": 4.0, "slip": 1.0},
))

_register(InstrumentSpec(
    type="arc_gauge",
    label="Arc Gauge",
    category="gauge",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: gauges.ArcGauge(
                 screen, min_size=False, font_family=font_family)),
    keep_aspect=True,
    properties=[
        Prop("dbkey", "fixkey", default="", label="FIX key",
             apply="setter:setDbkey",
             help="FIX-database key whose value this gauge displays"),
        Prop("name", "string", default="", label="Name",
             help="label drawn on the gauge (e.g. OIL P, CHT)"),
        Prop("decimal_places", "integer", default=1, label="Decimal places",
             help="digits after the decimal point in the readout"),
        Prop("show_units", "boolean", default=False, label="Show units",
             help="append the FIX key's engineering units to the readout"),
        Prop("segments", "integer", default=0, label="Segments",
             help="0 = solid band; >0 draws a segmented (LED-style) band"),
        Prop("name_location", "enum", default="top", enum=["top", "right"],
             label="Name location",
             help="where the name label sits relative to the gauge"),
    ],
    # The colour-band thresholds and the value range are FIX-database values
    # (item min/max + aux), set in fix-gateway, not in the panel editor (#64).
    fix_values=[
        FixValue("Min", source="min", label="Range minimum"),
        FixValue("Max", source="max", label="Range maximum"),
        FixValue("lowAlarm", source="aux", label="Low alarm (red)"),
        FixValue("lowWarn", source="aux", label="Low warning (yellow)"),
        FixValue("highWarn", source="aux", label="High warning (yellow)"),
        FixValue("highAlarm", source="aux", label="High alarm (red)"),
    ],
    # Representative 5-zone bands + needle fill so the twin draws a realistic
    # red-yellow-green-yellow-red gauge with no live FIX (fractions of range;
    # the device uses the real min/max + warn/alarm aux).
    preview={"value": "72.0", "fill": 0.72, "low_alarm": 0.10,
             "low_warn": 0.20, "high_warn": 0.80, "high_alarm": 0.90},
))

_register(InstrumentSpec(
    type="airspeed_tape",
    label="Airspeed Tape",
    category="airspeed",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: airspeed.Airspeed_Tape(
                 screen, font_percent=font_percent)),
    dbkeys=["IAS"],
    properties=[
        Prop("edge_fade", "boolean", default=False,
             label="Fade tape edges",
             help="alpha-fade the top and bottom of the scrolling "
                  "scale into the background (SVS shows through)"),
        # NOTE: no editable dbkey -- Airspeed_Tape is hard-wired to IAS (it has
        # no setDbkey and reads the V-speed aux off that item). The old curated
        # schema offered a dbkey option that did nothing; dropped.
        Prop("show_tas", "boolean", default=True, label="Show TAS box",
             help="show the true-airspeed readout box (from TAS)"),
        Prop("show_trend", "boolean", default=True, label="Show trend arrow",
             help="show the acceleration trend vector along the tape"),
        Prop("trend_lookahead", "number", default=6.0,
             label="Trend look-ahead (s)",
             help="seconds ahead the trend vector projects current accel"),
    ],
    # V-speeds come from the IAS item's aux (fix-gateway), not the panel editor.
    fix_values=[
        FixValue("Vs", source="aux", label="Stall, clean (Vs)", units="kt"),
        FixValue("Vs0", source="aux", label="Stall, landing (Vs0)", units="kt"),
        FixValue("Vno", source="aux", label="Max cruise (Vno)", units="kt"),
        FixValue("Vne", source="aux", label="Never-exceed (Vne)", units="kt"),
        FixValue("Vfe", source="aux", label="Flaps-extended (Vfe)", units="kt"),
    ],
    preview={"value": 110, "vs0": 40, "vs": 45, "vno": 125, "vne": 140,
             "vfe": 70},
))

_register(InstrumentSpec(
    type="vsi_dial",
    label="VSI Dial",
    category="vertical_speed",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: vsi.VSI_Dial(screen, font_family=font_family)),
    dbkeys=["VS"],
    keep_aspect=True,
    # VSI_Dial is hard-wired to VS and exposes no editor options today; this
    # record migrates it for catalog completeness. Range is the FIX item's.
    properties=[],
    fix_values=[
        FixValue("Min", source="min", label="Range minimum", units="ft/min"),
        FixValue("Max", source="max", label="Range maximum", units="ft/min"),
    ],
    preview={"value": -350},
))

_register(InstrumentSpec(
    type="airspeed_dial",
    label="Airspeed Dial",
    category="airspeed",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: airspeed.Airspeed(screen, font_family=font_family)),
    dbkeys=["IAS"],
    keep_aspect=True,
    properties=[_bg_opacity_prop()],
    # Fixed steam-gauge face; IAS hard-wired. V-speed arcs come from IAS aux.
    fix_values=[
        FixValue("Vs", source="aux", label="Stall, clean (Vs)", units="kt"),
        FixValue("Vs0", source="aux", label="Stall, landing (Vs0)", units="kt"),
        FixValue("Vno", source="aux", label="Max cruise (Vno)", units="kt"),
        FixValue("Vne", source="aux", label="Never-exceed (Vne)", units="kt"),
        FixValue("Vfe", source="aux", label="Flaps-extended (Vfe)", units="kt"),
    ],
    preview={"value": 110},
))

_register(InstrumentSpec(
    type="altimeter_dial",
    label="Altimeter Dial",
    category="altitude",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: altimeter.Altimeter(screen, font_family=font_family)),
    dbkeys=["ALT"],
    keep_aspect=True,
    properties=[_bg_opacity_prop()],
    preview={"value": 3500},
))

_register(InstrumentSpec(
    type="altimeter_tape",
    label="Altimeter Tape",
    category="altitude",
    builder=build_altimeter_tape,
    dbkeys=["ALT"],
    # All options are consumed by build_altimeter_tape at construction
    # (apply="special"); defaults are the Altimeter_Tape constructor defaults.
    properties=[
        Prop("edge_fade", "boolean", default=False,
             label="Fade tape edges",
             help="alpha-fade the top and bottom of the scrolling "
                  "scale into the background (SVS shows through)"),
        Prop("dbkey", "fixkey", default="ALT", label="FIX key", apply="special",
             help="FIX key driving the tape (default ALT)"),
        Prop("maxalt", "integer", default=50000, label="Max altitude", apply="special",
             help="top of the tape's altitude range (ft)"),
        Prop("majorDiv", "integer", default=200, label="Major division", apply="special",
             help="altitude between labelled tape ticks (ft)"),
        Prop("minorDiv", "integer", default=100, label="Minor division", apply="special",
             help="altitude between the small tape ticks (ft)"),
        Prop("total_decimals", "integer", default=5, label="Total digits", apply="special",
             help="number of digits in the altitude readout"),
        Prop("font_mask", "string", default="00000", label="Font mask", apply="special",
             help="widest string the readout reserves space for (sizing)"),
        Prop("round_to", "number", default=0, label="Round readout to", apply="special",
             help="round the readout to this increment (0 = none)"),
        Prop("numeric_box", "boolean", default=True, label="Show numeric box", apply="special",
             help="show the boxed numeric altitude over the tape"),
        Prop("font_scale", "number", default=1.0, label="Scale-number font scale", apply="special",
             help="multiplier on the tape scale-number font size"),
    ],
    preview={"value": 3500},
))

_register(InstrumentSpec(
    type="vsi_pfd",
    label="VSI (PFD)",
    category="vertical_speed",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: vsi.VSI_PFD(screen, font_family=font_family)),
    dbkeys=["VS"],
    preview={"value": -350},
))

_register(InstrumentSpec(
    type="horizontal_situation_indicator",
    label="Horizontal Situation Indicator (HSI)",
    category="navigation",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: hsi.HSI(screen, font_percent=font_percent,
                                    cdi_enabled=True, gsi_enabled=True,
                                    font_family=font_family)),
    dbkeys=["COURSE", "CDI", "GSI", "HEAD"],
    keep_aspect=True,
    # The factory enables CDI+GSI at construction; the editor toggles honour
    # self.cdi_enabled / self.gsi_enabled at paint time. COURSE/CDI/GSI/HEAD are
    # direct FIX keys (no aux), so no fix_values.
    properties=[
        Prop("cdi_enabled", "boolean", default=True, label="CDI",
             help="show the lateral course-deviation needle (CDI)"),
        Prop("gsi_enabled", "boolean", default=True, label="Glideslope",
             help="show the vertical glideslope needle (GSI)"),
        Prop("fg_color", "color", default="#ffffff", label="Foreground",
             help="compass card, ring and text colour"),
        Prop("bg_color", "color", default="#000000", label="Background",
             help="compass-disc fill colour"),
        # Fills the compass disc (not the box); 0 = transparent over the SVS/PFD.
        _bg_opacity_prop(),
        Prop("needle_color", "color", default="#ffff00", label="Needle color",
             help="colour of the CDI/GSI deviation needles"),
        Prop("needle_width", "integer", default=3, minimum=1, maximum=10,
             step=1, label="Needle width",
             help="width of the CDI/GSI deviation needles (px)"),
        Prop("course_color", "color", default="#ff00ff",
             label="Course pointer color",
             help="selected-course pointer (the magenta CRS triangle)"),
        Prop("source_auto_color", "boolean", default=True,
             label="Source auto-color",
             help="colour the course pointer and CDI by nav source -- magenta "
                  "for GPS, the VOR/LOC colour for a VOR/LOC source (from NAVSRC)"),
        Prop("vloc_color", "color", default="#00ff00", label="VOR/LOC color",
             help="course pointer / CDI colour for a VOR or localizer source "
                  "when source auto-color is on"),
        Prop("source_label_enabled", "boolean", default=True,
             label="Source label",
             help="show the nav-source annunciation (GPS / VLOC1 / VLOC2, or "
                  "VOR/LOC when NAVTYPE is available) on the rose face"),
        Prop("heading_bug_enabled", "boolean", default=False,
             label="Heading bug",
             help="show the cyan heading bug at the selected heading (HEADBUG)"),
        Prop("heading_bug_color", "color", default="#00ffff",
             label="Heading bug color", help="heading-bug colour"),
        Prop("track_indicator_enabled", "boolean", default=True,
             label="Track diamond",
             help="show the magenta GPS ground-track diamond (TRACK), "
                  "above the speed gate"),
        Prop("track_color", "color", default="#ff00ff",
             label="Track diamond color", help="GPS ground-track diamond colour"),
        Prop("track_min_speed", "integer", default=5, minimum=0, maximum=50,
             step=1, label="Track min speed (kt)",
             help="hide the track diamond below this groundspeed (kt)"),
    ],
    preview={"heading": 87, "course": 110, "track": 78, "gs": 120},
))

_register(InstrumentSpec(
    type="heading_tape",
    label="Heading Tape",
    category="navigation",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: hsi.DG_Tape(screen, font_family=font_family)),
    dbkeys=["HEAD"],
    # DG_Tape is hard-wired to HEAD (no setDbkey); the old curated dbkey option
    # was a no-op and is dropped.
    preview={"heading": 87},
))


# Shared option set + FIX values for the AbstractGauge family (arc / bar /
# numeric). Colour bands + range are FIX-database values (item min/max + aux),
# set in fix-gateway, not the panel editor (#64).
def _gauge_fix_values():
    return [
        FixValue("Min", source="min", label="Range minimum"),
        FixValue("Max", source="max", label="Range maximum"),
        FixValue("lowAlarm", source="aux", label="Low alarm (red)"),
        FixValue("lowWarn", source="aux", label="Low warning (yellow)"),
        FixValue("highWarn", source="aux", label="High warning (yellow)"),
        FixValue("highAlarm", source="aux", label="High alarm (red)"),
    ]


def _bar_gauge_props():
    return [
        Prop("dbkey", "fixkey", default="", label="FIX key",
             apply="setter:setDbkey",
             help="FIX-database key whose value this gauge displays"),
        Prop("name", "string", default="", label="Name",
             help="label drawn on the gauge (e.g. OIL P, CHT)"),
        Prop("decimal_places", "integer", default=1, label="Decimal places",
             help="digits after the decimal point in the readout"),
        Prop("show_units", "boolean", default=True, label="Show units",
             help="append the FIX key's engineering units to the readout"),
        Prop("segments", "integer", default=0, label="Segments",
             help="0 = solid bar; >0 draws a segmented (LED-style) bar"),
    ]


_register(InstrumentSpec(
    type="horizontal_bar_gauge",
    label="Horizontal Bar Gauge",
    category="gauge",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: gauges.HorizontalBar(
                 screen, min_size=False, font_family=font_family)),
    properties=_bar_gauge_props(),
    fix_values=_gauge_fix_values(),
    preview={"value": "72", "fill": 0.72},
))

_register(InstrumentSpec(
    type="vertical_bar_gauge",
    label="Vertical Bar Gauge",
    category="gauge",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: gauges.VerticalBar(
                 screen, min_size=False, font_family=font_family)),
    properties=_bar_gauge_props(),
    fix_values=_gauge_fix_values(),
    preview={"value": "72", "fill": 0.72},
))

_register(InstrumentSpec(
    type="turn_coordinator",
    label="Turn Coordinator",
    category="attitude",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: tc.TurnCoordinator(screen, font_family=font_family)),
    dbkeys=["ROT", "ALAT"],
    keep_aspect=True,
    preview={"rate": 8, "ball": 2},
))

_register(InstrumentSpec(
    type="numeric_display",
    label="Numeric Display",
    category="text",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: gauges.NumericDisplay(
                 screen, font_family=font_family)),
    properties=[
        Prop("dbkey", "fixkey", default="", label="FIX key",
             apply="setter:setDbkey",
             help="FIX-database key whose value is displayed"),
        Prop("decimal_places", "integer", default=1, label="Decimal places",
             help="digits after the decimal point in the readout"),
        Prop("font_mask", "string", default="000", label="Font mask",
             help="widest string the readout reserves space for (sizing)"),
        Prop("show_units", "boolean", default=False, label="Show units",
             help="append the FIX key's engineering units to the readout"),
    ],
    fix_values=_gauge_fix_values(),
))

_register(InstrumentSpec(
    type="value_text",
    label="Value Text",
    category="text",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: misc.ValueDisplay(
                 screen, font_family=font_family, font_percent=font_percent)),
    properties=[
        Prop("dbkey", "fixkey", default="", label="FIX key",
             apply="setter:setDbkey",
             help="FIX-database key whose value is displayed"),
        Prop("font_mask", "string", default="", label="Font mask",
             help="widest string the text reserves space for (sizing)"),
        Prop("number_format", "string", default="", label="Number format",
             help="Digit mask: blank = as-is; 000 = 089 (rounded, "
                  "zero-padded); 000.0 = 089.0 (with decimals)"),
        # Prefix label (e.g. HDG, CRS) before the value, with its own font /
        # size / colour. Empty prefix_text = no prefix.
        Prop("prefix_text", "string", default="", label="Prefix text",
             help="static label drawn before the value (e.g. HDG, CRS)"),
        Prop("prefix_font_family", "enum", default="Open Sans",
             enum=["DejaVu Sans Condensed", "DejaVu Sans", "DejaVu Sans Mono",
                   "B612", "Inter", "Roboto", "Open Sans"],
             label="Prefix font", help="font family for the prefix label"),
        Prop("prefix_font_percent", "integer", default=50, minimum=1,
             maximum=100, step=1, label="Prefix font size (%)",
             help="prefix height as a percent of the widget height"),
        Prop("prefix_color", "color", default="#ffffff", label="Prefix colour",
             help="colour of the prefix label"),
        Prop("value_color", "color", default="#ffffff", label="Value colour",
             help="colour of the data value (good/normal state)"),
        # Optional visual box at the widget bounds (border + background); the box
        # size is the widget rect itself. border_width 0 + bg_opacity 0 = no box.
        Prop("border_color", "color", default="#ffffff", label="Border colour",
             help="colour of the box border"),
        Prop("border_width", "integer", default=0, minimum=0, maximum=20, step=1,
             label="Border width (px)",
             help="box border thickness in pixels; 0 = no border"),
        Prop("border_opacity", "integer", default=100, minimum=0, maximum=100,
             step=1, label="Border opacity (%)", help="box border opacity"),
        Prop("bg_color", "color", default="#000000", label="Background colour",
             help="box background fill colour"),
        Prop("bg_opacity", "integer", default=0, minimum=0, maximum=100, step=1,
             label="Background opacity (%)",
             help="box background opacity; 0 = transparent (no fill)"),
    ],
))

_register(InstrumentSpec(
    type="static_text",
    label="Static Text",
    category="text",
    builder=build_static_text,
    properties=[
        Prop("text", "string", default="Text", label="Text", required=True,
             apply="special", help="the fixed text to display"),
        Prop("alignment", "enum", default="AlignLeft",
             enum=["AlignLeft", "AlignCenter", "AlignRight"], label="Alignment",
             help="horizontal text alignment within the widget"),
        Prop("font_mask", "string", default="", label="Font mask",
             help="widest string the text reserves space for (sizing)"),
    ],
))

_register(InstrumentSpec(
    type="airspeed_box",
    label="Airspeed Box",
    category="airspeed",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: airspeed.Airspeed_Box(screen, font_family=font_family)),
    dbkeys=["IAS", "GS", "TAS"],
    # Deprecated in favour of the Value Text widget (configurable prefix, value
    # colour and box). Hidden from the palette but kept in the schema so panels
    # that already place it still load and render.
    hidden=True,
))

_register(InstrumentSpec(
    type="airspeed_trend_tape",
    label="Airspeed Trend Tape",
    category="airspeed",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: vsi.AS_Trend_Tape(screen, font_family=font_family)),
    dbkeys=["IAS"],
))

_register(InstrumentSpec(
    type="altimeter_trend_tape",
    label="Altimeter Trend Tape",
    category="altitude",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: vsi.Alt_Trend_Tape(screen, font_family=font_family)),
    # The widget reads VS (vertical speed) directly; the legacy curated default
    # was "ALT", a key it never consumes.
    dbkeys=["VS"],
    preview={"value": 500},
    properties=[
        # AC 23.1311-1C 8.11 / AC 25-11B A.6: the VS range should suit the
        # airplane's climb/descent performance (VSI-DISP-001; closes the
        # vsi_widget_spec 7 "configurable range" open item).
        Prop("maxvs", "integer", default=2500, minimum=500, maximum=10000,
             step=100, label="Range (ft/min)",
             help="full scale, plus and minus; pick to suit the airplane's "
                  "climb/descent performance (AC 23.1311-1C 8.11)"),
        Prop("minorDiv", "integer", default=100, minimum=25, maximum=1000,
             step=25, label="Tick interval (ft/min)",
             help="minor tick mark every N ft/min"),
        Prop("numberedDiv", "integer", default=200, minimum=50, maximum=2000,
             step=50, label="Numbered interval (ft/min)",
             help="numbered graduation every N ft/min (labels print in "
                  "hundreds: 2400 ft/min prints as 24)"),
        Prop("bg_color", "color", default="#000000", label="Background",
             help="tape face colour"),
        _bg_opacity_prop(),
    ],
))

_register(InstrumentSpec(
    type="moving_map",
    label="Moving Map",
    category="navigation",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: moving_map.MovingMap(
                 screen, font_family=font_family)),
    dbkeys=["LAT", "LONG", "TRACKM"],
    properties=[
        Prop("range_nm", "number", default=10.0, minimum=1, maximum=500,
             label="Range (NM)",
             help="distance from the ownship anchor to the top edge",
             bindable=Binding("index_ladder", key_option="range_key",
                              ladder_option="range_ladder")),
        Prop("range_key", "fixkey", default="",
             label="Range control key",
             help="optional FIX key that cycles the range at runtime (a button "
                  "'change value wrap' / the knob steps the ladder index). "
                  "Empty = fixed range"),
        Prop("range_ladder", "string", default="2,5,10,20,40,80,160",
             label="Range ladder",
             help="comma list of ranges the range buttons step through"),
        Prop("orientation", "enum", default="track_up",
             enum=["track_up", "north_up"], label="Orientation",
             help="track-up rotates the world; north-up rotates ownship",
             bindable=Binding("enum", key_option="orientation_key")),
        Prop("orientation_key", "fixkey", default="",
             label="Orientation control key",
             help="optional FIX key that switches orientation at runtime "
                  "(0=track_up, 1=north_up). Empty = fixed"),
        Prop("touch_gestures", "boolean", default=True,
             label="Touch gestures",
             help="pinch to zoom the range (two-finger pan is tracked in "
                  "#99); mouse wheel mirrors zoom on desktop. Off = "
                  "touch/wheel input ignored"),
        Prop("ownship_position", "number", default=50, minimum=0,
             maximum=100, label="Ownship position (%)",
             help="ownship anchor, percent up from the bottom "
                  "(30 = classic look-ahead offset)"),
        Prop("symbol_color", "color", default="#ffff00",
             label="Ownship colour",
             help="colour of the top-down ownship symbol"),
        Prop("layer_range_rings", "boolean", default=True,
             label="Layer: range rings",
             help="concentric half/full range rings with labels"),
        Prop("layer_terrain", "boolean", default=True,
             label="Layer: terrain",
             help="hillshaded hypsometric terrain relief"),
        Prop("tile_path", "string", default="",
             label="Terrain tile path",
             help="GLO-30/SRTM HGT tree (the SVS tile_path; on the Pi "
                  "/data/makerplane-data/terrain/tiles)"),
        Prop("layer_roads", "boolean", default=True,
             label="Layer: roads",
             help="roads from the highways pack, LOD by range: interstates "
                  "when zoomed out (<=80 NM), arterials added as you zoom "
                  "in (primary <=20 NM, secondary <=5 NM)"),
        Prop("highway_db_path", "string", default="",
             label="Roads db path",
             help="highways.sqlite (the SVS highway_db_path; on the Pi "
                  "/data/makerplane-data/highways/current/"
                  "highways.sqlite)"),
        Prop("road_color", "color", default="#c0c0c0",
             label="Road colour",
             help="road line colour (arterial classes draw thinner and "
                  "slightly transparent)"),
        Prop("layer_rivers", "boolean", default=True,
             label="Layer: rivers",
             help="rivers/waterways as lines from the rivers pack (#92), "
                  "LOD by range: major rivers when zoomed out, canals and "
                  "streams added close in"),
        Prop("river_db_path", "string", default="",
             label="Rivers db path",
             help="rivers.sqlite (shares the highways schema; on the Pi "
                  "/data/makerplane-data/rivers/current/rivers.sqlite)"),
        Prop("river_color", "color", default="#4a6d8c",
             label="River colour",
             help="waterway line colour (smaller waterways draw thinner "
                  "and slightly transparent)"),
        Prop("layer_airports", "boolean", default=True,
             label="Layer: airports",
             help="FAA sectional airport symbols with ident labels "
                  "(declutters by zoom)"),
        Prop("nasr_db_path", "string", default="",
             label="Airport db path",
             help="NASR airports.sqlite (the SVS nasr_db_path; on the "
                  "Pi /data/makerplane-data/navdata/current/"
                  "airports.sqlite)"),
        Prop("layer_navaids", "boolean", default=True,
             label="Layer: navaids",
             help="VOR/NDB symbols with ident and frequency"),
        Prop("layer_fixes", "boolean", default=False,
             label="Layer: waypoints",
             help="named fixes as open triangles (shown at/below 20 NM)"),
        Prop("layer_airways", "boolean", default=False,
             label="Layer: airways",
             help="victor/T-route segments with idents"),
        Prop("navaid_db_path", "string", default="",
             label="Navaid db path",
             help="navaids.sqlite (tools/build_navaid_db.py; on the Pi "
                  "/data/makerplane-data/navaids/current/navaids.sqlite)"),
        Prop("terrain_mode", "enum", default="relief",
             enum=["relief", "caution"], label="Terrain mode",
             help="relief = sectional-style hypsometric; caution = "
                  "TAWS-style amber/red relative to altitude"),
        Prop("water_db_path", "string", default="",
             label="Water db path",
             help="water.sqlite (the SVS water_db_path; on the Pi "
                  "/data/makerplane-data/water/current/water.sqlite). "
                  "When set, lakes and coastline from the water pack "
                  "are rasterized into the terrain image"),
        Prop("water_max_vertices", "number", default=512, minimum=16,
             maximum=1024, step=16, label="Water vertex cap",
             help="per-polygon vertex cap for map water rasterization "
                  "(higher = more coastline/lake detail per rebuild)"),
    ],
))

_register(InstrumentSpec(
    type="wind_display",
    label="Wind Display",
    category="wind",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: wind.WindDisplay(screen, font_family=font_family)),
    dbkeys=["HWIND", "XWIND"],
))

# --- Special / non-instrument types --------------------------------------
# These are migrated for catalog completeness but, unlike the gauges/dials,
# cannot be built in isolation (they need a live screen for config_path, embed
# an external process, or read host files), so builds_in_isolation=False keeps
# them out of the gate's construction probe. Their config is consumed inside the
# builder (apply="special"), not setattr'd onto the widget.

_register(InstrumentSpec(
    type="weston",
    label="Weston",
    category="system",
    builder=build_weston,
    # Upstream feature (Eric Blevins, 2023): embeds a weston/waydroid surface
    # under X11. Linux/X11 only -- inert on other platforms.
    offscreen_renderable=False,
    builds_in_isolation=False,
    properties=[
        Prop("socket", "string", required=True, apply="special",
             label="Wayland socket", help="weston -S socket name"),
        Prop("ini", "string", required=True, apply="special",
             label="weston.ini", help="path (under the config dir) to weston.ini"),
        Prop("command", "string", required=True, apply="special",
             label="Command", help="program to launch inside the compositor"),
        Prop("args", "string", required=True, apply="special",
             label="Arguments", help="arguments passed to the command"),
    ],
))

# A soft touchscreen button (Eric Blevins' Button widget). Its definition is
# either inline (these options -- authored in the configurator) or an external
# YAML referenced by the legacy 'config' path. All props are apply="special":
# build_button consumes the options directly (the widget reads self.config), so
# they are NOT setattr'd onto the widget. The conditions/actions behaviour block
# is a later phase (docs: makerplane-data/docs/soft_controls_configurator.md).
_register(InstrumentSpec(
    type="button",
    label="Button",
    category="control",
    builder=build_button,
    builds_in_isolation=False,
    offscreen_renderable=False,
    properties=[
        Prop("text", "string", default="", apply="special",
             label="Text", help="button label (use \\n for two lines)"),
        Prop("type", "enum", default="simple",
             enum=["simple", "toggle", "repeat"], apply="special",
             label="Type",
             help="simple = click; toggle = on/off state; repeat = "
                  "auto-repeat while held"),
        Prop("dbkey", "fixkey", default="", required=True, apply="special",
             label="FIX key",
             help="backing touchscreen-button key (TSBTN...); the configurator "
                  "assigns it automatically"),
        Prop("bg_color", "color", default="#101418", apply="special",
             label="Background colour", help="button fill colour"),
        Prop("fg_color", "color", default="#00ffff", apply="special",
             label="Text colour", help="button label colour"),
        Prop("transparent", "boolean", default=False, apply="special",
             label="Transparent background",
             help="draw no fill so what is behind the button shows through"),
        Prop("hover_show", "boolean", default=False, apply="special",
             label="Show only on hover",
             help="hide the button until the pointer is over it"),
        # Legacy: an external button YAML referenced by path (hand-authored
        # panels). Leave blank to use the inline fields above.
        Prop("config", "string", default="", apply="special",
             label="Config file (legacy)",
             help="path to an external button YAML; blank = use the fields above"),
    ],
))

_register(InstrumentSpec(
    type="listbox",
    label="Listbox",
    category="list",
    builder=build_listbox,
    builds_in_isolation=False,
    properties=[
        # Structured option (list of {name, file}); represented as a single
        # config value until the Prop model grows an explicit list/object kind.
        Prop("lists", "string", required=True, apply="special",
             label="Lists", help="selectable lists -- list of {name, file} entries"),
    ],
))

_register(InstrumentSpec(
    type="data_status",
    label="Data Status",
    category="system",
    builder=build_data_status,
    builds_in_isolation=False,
    # The data-management boot screen is built-in (gui forces it on boot); it is
    # not a user-placed instrument, so hide it from the configurator palette.
    hidden=True,
    # The builder also accepts optional status_path / continue_screen /
    # update_command; left out of the panel (they default sensibly) until there
    # is a reason to expose host-path plumbing in the editor.
))

_register(InstrumentSpec(
    type="data_annunciation",
    label="Data Annunciation",
    category="system",
    builder=build_data_annunciation,
    builds_in_isolation=False,
    # Optional status_path / target_screen handled by the builder; not exposed.
))

_register(InstrumentSpec(
    type="virtual_vfr",
    label="Virtual VFR / Synthetic Vision",
    category="attitude",
    builder=build_virtual_vfr,
    # Deduped from the legacy default (which listed PITCH twice).
    dbkeys=["PITCH", "LAT", "LONG", "HEAD", "ALT", "ROLL", "ALAT", "TAS"],
    svs_capable=True,
    offscreen_renderable=False,   # QOpenGLWidget SVS terrain; hangs offscreen
    builds_in_isolation=False,    # GL widget needs a real screen
    # Not keep_aspect: the SVS view fills its box (a wide PFD background),
    # unlike the square attitude dial.
    properties=[
        Prop("aircraft_symbol", "enum", default="classic",
             enum=["classic", "garmin", "brackets", "none"],
             label="Aircraft symbol",
             help="classic split-wing bars + dot; garmin G3X-style two-tone "
                  "bat wing + horizon barbs; brackets GRT-style L-brackets; "
                  "none hides the symbol (SVS-as-background) "
                  "(g1000/gi275 remain accepted in YAML for back-compat)"),
        Prop("symbol_color", "color", default="#ffff00", label="Symbol colour",
             help="colour of the fixed aircraft reference symbol"),
        Prop("symbol_scale", "number", default=1.0, minimum=0.3, maximum=3.0,
             step=0.05, label="Symbol scale",
             help="multiplies the reference symbol size -- wingspan and "
                  "proportions together (1 = standard)"),
        # SVS-only: raise the level-flight horizon so the ground area expands
        # (more room for instruments like the HSI in the lower third). The whole
        # attitude reference -- horizon, ladder, symbol, terrain -- shifts up
        # together, so level flight still reads correctly. 50 = centred default,
        # which leaves the plain Attitude Indicator unchanged.
        Prop("horizon_position", "integer", default=50, minimum=40, maximum=80,
             step=1, label="Horizon position (% up)",
             help="50 = centred (default); ~67 = two-thirds up the screen"),
        # Editor preview only: the device renders real SVS terrain; this picks
        # which stylised backdrop the configurator twin shows for layout.
        Prop("preview_scene", "enum", default="mountains",
             enum=["mountains", "approach", "final"],
             label="Preview scene (editor)", apply="special",
             help="which stylised backdrop the editor twin shows (preview "
                  "only; the device renders real terrain)"),
        Prop("show_fpm", "boolean", default=True, label="Flight-path marker",
             help="GPS flight-path marker (needs VS/GS/TRACK/HEAD)"),
        *_ai_overlay_props(),
        *_svs_props(),
    ],
))

_register(InstrumentSpec(
    type="heading_display",
    label="Heading Display",
    category="navigation",
    builder=(lambda screen, config, font_percent=None, font_family=None,
             replace=None: hsi.HeadingDisplay(screen, font_family=font_family)),
    dbkeys=["HEAD"],
    # Deprecated in favour of the Value Text widget (a HEAD-bound value with a
    # "HDG" prefix, colour and box). Hidden from the palette but kept in the
    # schema so panels that already place it still load and render.
    hidden=True,
    properties=[
        # Default fg is light grey (#aaaaaa) -- the widget default was the
        # darker Qt "gray" (#808080); aligned for readability + a matching
        # editor default. font_size is intentionally NOT exposed: the widget
        # recomputes it from the box size on resize (fit_to_mask), so it was a
        # no-op option. Use the common font_percent to scale instead.
        Prop("fg_color", "color", default="#aaaaaa", label="Foreground",
             help="heading-text colour"),
        Prop("bg_color", "color", default="#000000", label="Background",
             help="background-box fill colour"),
        _bg_opacity_prop(),
    ],
))


# Fold the registry back into the legacy lookup tables so existing consumers
# keep working AND migrated instruments are sourced from the registry (the
# single source of truth). As instruments migrate, these literal dicts shrink;
# once everything is migrated they can be removed entirely.
for _t, _spec in REGISTRY.items():
    if _spec.builder is not None:
        INSTRUMENT_FACTORIES[_t] = _spec.builder
    if _spec.dbkeys:
        INSTRUMENT_DEFAULTS[_t] = list(_spec.dbkeys)


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
