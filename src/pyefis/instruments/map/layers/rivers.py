#  SPDX-License-Identifier: GPL-2.0-or-later
#  Moving map rivers layer (#92) -- OSM waterways as polylines.
#
#  Rivers share the highways sqlite schema (same HighwayDB reader, built by
#  tools/build_highway_db.py --preset rivers), so this is just RoadsLayer with
#  its own class bands + colour + db option, per docs/map_layers_roadmap.md
#  section 1.4. The worker-render-once + LOD-by-range machinery is inherited
#  unchanged. This also gives the map the river-as-lines the SVS lacks (#39).

from pyefis.instruments.map.layers import register_layer
from pyefis.instruments.map.layers.roads import RoadsLayer


@register_layer
class RiversLayer(RoadsLayer):
    id = "rivers"
    label = "Rivers"
    z = 9                       # under roads (z=10), over terrain relief
    default_on = True

    _DB_OPTION = "river_db_path"
    _COLOR_OPTION = "river_color"
    _DEFAULT_COLOR = "#4a6d8c"  # muted water blue
    _EXPAND_LINKS = False       # waterways have no _link ramps

    # LOD bands (max range NM -> waterway classes). Major rivers persist to
    # wider range; canals/streams only close in. Keep in sync with
    # tools/build_highway_db.py PRESETS["rivers"].
    _BAND_BASE = (
        (8.0, ("river", "canal", "stream")),
        (25.0, ("river", "canal")),
        (60.0, ("river",)),
    )
    _TIER = {"river": 0, "canal": 1, "stream": 2}
