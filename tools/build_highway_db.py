#!/usr/bin/env python3
"""
Build the polyline database the SVS + moving map read (issue #35, #92).

Input: a Geofabrik state "free shapefile" bundle layer --
``gis_osm_roads_free_1.shp`` for roads, ``gis_osm_waterways_free_1.shp``
for rivers (both carry an ``fclass`` field). Filters to the requested
classes, Douglas-Peucker decimates each polyline (default 40 m tolerance --
finer than the display can resolve), and stores (lat, lon) float32 blobs
in an R-tree-indexed sqlite the runtime HighwayDB reads (same schema for
both -- the roads/rivers map layers differ only in class set + colour).

Presets pick the class set (moving-map roads LOD wants primary/secondary
arterials, not just interstates); ``--classes`` overrides:

    # roads (default preset): motorway/trunk/primary/secondary + ramps
    python tools/build_highway_db.py --dest highways.sqlite \
        path/to/colorado/gis_osm_roads_free_1.shp [more .shp ...]

    # rivers (#92): same schema, waterway classes, own sqlite
    python tools/build_highway_db.py --preset rivers --dest rivers.sqlite \
        path/to/colorado/gis_osm_waterways_free_1.shp [more .shp ...]

Requires pyshp (like build_water_db.py). Data (c) OpenStreetMap
contributors, ODbL.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from pyefis.instruments.ai.highway_db import encode_vertices  # noqa: E402

# Class presets by data layer. Roads carry primary/secondary now (not just the
# motorway/trunk interstates) so the moving-map roads layer can add arterials
# as it zooms in (docs/map_layers_roadmap.md section 1). Rivers reuse the same
# schema with OSM waterway classes (#92). Keep the road tiers in sync with the
# roads layer LOD bands (map/layers/roads.py _BAND_BASE).
PRESETS = {
    "roads": ("motorway", "motorway_link", "trunk", "trunk_link",
              "primary", "primary_link", "secondary", "secondary_link"),
    "rivers": ("river", "canal", "stream"),
}
DEFAULT_CLASSES = PRESETS["roads"]
M_PER_DEG = 111139.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS highway_lines (
    id INTEGER PRIMARY KEY,
    fclass TEXT NOT NULL,
    min_lat REAL, max_lat REAL, min_lon REAL, max_lon REAL,
    verts BLOB NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS highway_rtree USING rtree(
    id, min_lat, max_lat, min_lon, max_lon
);
"""


def rdp(points: np.ndarray, tol_deg: float) -> np.ndarray:
    """Iterative Douglas-Peucker on an (N, 2) lat/lon array."""
    n = len(points)
    if n < 3:
        return points
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        seg = points[a:b + 1]
        d = seg[-1] - seg[0]
        L = np.hypot(d[0], d[1])
        if L < 1e-12:
            dist = np.hypot(seg[:, 0] - seg[0, 0], seg[:, 1] - seg[0, 1])
        else:
            dist = np.abs(d[0] * (seg[0, 1] - seg[:, 1])
                          - d[1] * (seg[0, 0] - seg[:, 0])) / L
        i = int(np.argmax(dist))
        if dist[i] > tol_deg:
            keep[a + i] = True
            stack.append((a, a + i))
            stack.append((a + i, b))
    return points[keep]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("shapefiles", nargs="+")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--preset", choices=sorted(PRESETS), default="roads",
                    help="class set to keep (default roads); ignored if "
                         "--classes is given")
    ap.add_argument("--classes", nargs="*", default=None,
                    help="explicit fclass list (overrides --preset)")
    ap.add_argument("--tolerance-m", type=float, default=40.0)
    args = ap.parse_args()
    if not args.classes:
        args.classes = list(PRESETS[args.preset])

    import shapefile  # pyshp

    con = sqlite3.connect(args.dest)
    con.executescript(SCHEMA)
    classes = set(args.classes)
    tol_deg = args.tolerance_m / M_PER_DEG
    total = kept = 0
    next_id = (con.execute(
        "SELECT COALESCE(MAX(id), 0) FROM highway_lines")
        .fetchone()[0]) + 1

    for shp in args.shapefiles:
        print(f"reading {shp} ...")
        sf = shapefile.Reader(shp)
        fields = [f[0] for f in sf.fields[1:]]
        fclass_i = fields.index("fclass")
        for sr in sf.iterShapeRecords():
            total += 1
            fclass = sr.record[fclass_i]
            if fclass not in classes:
                continue
            # shapefile points are (lon, lat); split multi-part lines
            pts = np.asarray(sr.shape.points, dtype=np.float64)
            parts = list(sr.shape.parts) + [len(pts)]
            for a, b in zip(parts[:-1], parts[1:]):
                seg = pts[a:b]
                if len(seg) < 2:
                    continue
                latlon = np.column_stack([seg[:, 1], seg[:, 0]])
                latlon = rdp(latlon, tol_deg)
                con.execute(
                    "INSERT INTO highway_lines "
                    "(id, fclass, min_lat, max_lat, min_lon, max_lon,"
                    " verts) VALUES (?,?,?,?,?,?,?)",
                    (next_id, fclass,
                     float(latlon[:, 0].min()), float(latlon[:, 0].max()),
                     float(latlon[:, 1].min()), float(latlon[:, 1].max()),
                     encode_vertices(latlon)))
                con.execute(
                    "INSERT INTO highway_rtree VALUES (?,?,?,?,?)",
                    (next_id,
                     float(latlon[:, 0].min()), float(latlon[:, 0].max()),
                     float(latlon[:, 1].min()), float(latlon[:, 1].max())))
                next_id += 1
                kept += 1
    con.commit()
    con.execute("VACUUM")
    con.close()
    print(f"done: {kept} polylines kept of {total} roads -> {args.dest}")


if __name__ == "__main__":
    main()
