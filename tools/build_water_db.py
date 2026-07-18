#!/usr/bin/env python3
"""
Build a water-polygon sqlite database for SVS rendering.

Reads polygons from shapefiles (Natural Earth, OSM water-polygons) or
from a simple text format and writes them to a sqlite database the
WaterDB class can query.

Usage:
    # From shapefiles (requires pyshp):
    python build_water_db.py water.sqlite \\
        --ocean  /path/to/ne_10m_ocean.shp \\
        --lake   /path/to/ne_10m_lakes.shp \\
        --osm-water /path/to/water_polygons.shp

    # From a simple text format (no dependencies — useful on the Pi
    # for hand-crafting a small test dataset):
    python build_water_db.py water.sqlite --text input.txt

Text format:
    # Each polygon starts with a 'P kind [elev_ft]' line, followed by
    # vertex lines 'lat lon', ended with a blank line or EOF.
    P ocean
    34.4  -120.0
    34.4  -119.5
    34.0  -119.5
    34.0  -120.0

    P lake 656
    35.78 -81.30
    35.79 -81.28
    ...
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Local import; let it fail loudly if the module is wrong.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from pyefis.instruments.ai.water_db import encode_vertices

# Tessellation library. Pure-data Python interface around the well-
# tested earcut C++ port. Used at build time only; the renderer just
# reads the pre-computed triangle indices from the sqlite BLOB.
import mapbox_earcut as _earcut
import numpy as np


def tessellate_polygon(vertices):
    """Triangulate a single-ring polygon via earcut. Returns a numpy
    array of uint16 indices (3 per triangle) into ``vertices``, or
    None if the input is degenerate / fails tessellation.

    ``vertices`` is a list of (lat, lon) tuples — earcut sees them
    as generic 2D points, so lat/lon vs xy doesn't matter at this
    stage. Each output index is in [0, len(vertices))."""
    if len(vertices) < 3:
        return None
    # earcut wants a flat float64 Nx2 array and a ring-end-index list.
    # Single ring => one element pointing at the end of the vertex
    # array. Multi-ring (outer + holes) support comes later if we
    # need it; current OSM ingest collapses multi-rings into
    # single-ring polygons.
    pts = np.asarray(vertices, dtype=np.float64)
    rings = np.asarray([len(pts)], dtype=np.uint32)
    try:
        idx = _earcut.triangulate_float64(pts, rings)
    except Exception:
        return None
    if idx.size == 0 or (idx.size % 3) != 0:
        return None
    # uint16 caps us at 65535 vertices per polygon — every polygon we
    # store is decimated to <=32 vertices so this is comfortably safe.
    return idx.astype(np.uint16)


SCHEMA = """
CREATE TABLE IF NOT EXISTS water_polygons (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    min_lat   REAL NOT NULL,
    max_lat   REAL NOT NULL,
    min_lon   REAL NOT NULL,
    max_lon   REAL NOT NULL,
    kind      TEXT NOT NULL,
    elev_ft   REAL,
    vertices  BLOB NOT NULL,
    -- Pre-tessellated triangle indices into the ``vertices`` array,
    -- packed as little-endian uint16 (3 indices per triangle). NULL
    -- only when tessellation failed at build time (logged as a
    -- warning). The GPU water renderer uploads these directly to a
    -- GL element-array buffer with one draw call per polygon.
    triangles BLOB
);
CREATE INDEX IF NOT EXISTS idx_bbox
    ON water_polygons(min_lat, max_lat, min_lon, max_lon);
CREATE INDEX IF NOT EXISTS idx_kind ON water_polygons(kind);

-- R-Tree spatial index for the bbox query that WaterDB.polygons_in_range
-- does every frame. With the plain B-tree index above, sqlite can only
-- use one inequality predicate efficiently and the query took ~53 ms
-- against the 878k-polygon OSM dataset at KSBA. The R-Tree drops it to
-- sub-millisecond. WaterDB falls back to the B-tree query when this
-- virtual table is missing (older DBs).
CREATE VIRTUAL TABLE IF NOT EXISTS water_rtree USING rtree(
    id,
    min_lat, max_lat,
    min_lon, max_lon
);
"""


_M_PER_DEG = 111_320.0
_BASE_TOL_DEG = 40.0 / _M_PER_DEG       # ~40 m — finer than the SVS can resolve


def _rdp(points, tol_deg):
    """Iterative Douglas-Peucker on an (N, 2) lat/lon array. Shape-preserving:
    every simplified edge stays within ``tol_deg`` of the original outline, so
    unlike stride decimation it can never cut a chord across a winding river or
    a branching reservoir and balloon it into a filled blob. (Same algorithm
    the roads build uses — see tools/build_highway_db.py.)"""
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


def _decimate(vertices, max_vertices):
    """Simplify a polygon ring to <= ``max_vertices`` with Douglas-Peucker,
    escalating the tolerance until it fits. Replaces the old stride decimation,
    which connected every Nth perimeter point and, on long/winding/branching
    water features (rivers, reservoir systems), cut chords across the feature
    and rendered a huge solid blob over dry land. The render side
    (WaterDB._decode_vertices) caps at this same 32, so a stored ring already
    <= the cap is never re-decimated (and re-blobbed) at draw time."""
    n = len(vertices)
    if max_vertices is None or n <= max_vertices:
        return vertices
    pts = np.asarray(vertices, dtype=np.float64)
    tol = _BASE_TOL_DEG
    out = pts
    for _ in range(24):                 # escalate tolerance until under the cap
        out = _rdp(pts, tol)
        if len(out) <= max_vertices:
            return [(float(p[0]), float(p[1])) for p in out]
        tol *= 1.6
    # Pathological ring (near-fractal coastline) — DP still over the cap even at
    # a large tolerance; stride the DP-simplified result as a last resort.
    step = (len(out) - 1) / (max_vertices - 1)
    return [(float(out[int(round(k * step))][0]), float(out[int(round(k * step))][1]))
            for k in range(max_vertices)]


def insert_polygon(con, kind, elev_ft, vertices, max_vertices=None):
    if len(vertices) < 3:
        return False
    # Decimate at build time so the BLOBs stored on disk are small.
    # Reading a 50-100 KB BLOB per polygon at query time was the
    # dominant cost in the perf log; with a 32-vertex cap each BLOB
    # is ~512 bytes and the query is bound by index scanning rather
    # than disk I/O.
    vertices = _decimate(vertices, max_vertices)
    lats = [v[0] for v in vertices]
    lons = [v[1] for v in vertices]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    # Pre-tessellate. The renderer reads these indices directly into a
    # GL element-array buffer at draw time — keeps per-frame Python
    # work down to a buffer upload + glDrawElements call.
    tri_idx = tessellate_polygon(vertices)
    tri_blob = tri_idx.tobytes() if tri_idx is not None else None
    cur = con.execute(
        "INSERT INTO water_polygons "
        "(min_lat, max_lat, min_lon, max_lon, kind, elev_ft, "
        " vertices, triangles) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (min_lat, max_lat, min_lon, max_lon,
         kind, elev_ft, encode_vertices(vertices), tri_blob))
    con.execute(
        "INSERT INTO water_rtree (id, min_lat, max_lat, min_lon, max_lon) "
        "VALUES (?, ?, ?, ?, ?)",
        (cur.lastrowid, min_lat, max_lat, min_lon, max_lon))
    return True


def ring_area_km2(vertices):
    """Approximate area (km^2) of a (lat, lon) ring via the shoelace formula,
    scaled to km at the ring's mean latitude. Good enough to size-filter."""
    import math
    n = len(vertices)
    if n < 3:
        return 0.0
    lat0 = sum(v[0] for v in vertices) / n
    s = 0.0
    for i in range(n):
        lat1, lon1 = vertices[i]
        lat2, lon2 = vertices[(i + 1) % n]
        s += lon1 * lat2 - lon2 * lat1
    area_deg2 = abs(s) / 2.0
    return area_deg2 * 110.574 * (111.320 * math.cos(math.radians(lat0)))


def import_shapefile(con, path, kind, max_vertices, elev_ft=None,
                     min_area_km2=0.0, keep_fclass=None):
    """Import every polygon (and every ring of every multi-polygon) from
    a shapefile into the water_polygons table. Rings smaller than
    ``min_area_km2`` are skipped (declutters tiny ponds; 0 disables).

    ``keep_fclass`` (a set of OSM feature classes) keeps only those classes
    when the shapefile has an ``fclass`` field — used to keep still open water
    (``water``, ``reservoir``) and drop ``riverbank`` (rivers render as filled
    lake-blobs, not rivers) and ``wetland*``. Shapefiles without an ``fclass``
    field (the ocean coastline) are never filtered."""
    try:
        import shapefile  # pyshp
    except ImportError:
        print("ERROR: shapefile import requires pyshp (`pip install pyshp`)",
              file=sys.stderr)
        sys.exit(2)

    sf = shapefile.Reader(str(path))
    fields = [f[0] for f in sf.fields[1:]]
    fclass_idx = fields.index("fclass") if "fclass" in fields else None
    use_fclass = bool(keep_fclass) and fclass_idx is not None
    n = 0
    dropped = 0
    fc_dropped = 0
    records = sf.iterShapeRecords() if use_fclass else (
        (shape, None) for shape in sf.shapes())
    for item in records:
        shape = item.shape if use_fclass else item[0]
        if use_fclass and item.record[fclass_idx] not in keep_fclass:
            fc_dropped += 1
            continue
        if not shape.points:
            continue
        # shape.parts marks the start of each ring; iterate ring by ring.
        parts = list(shape.parts) + [len(shape.points)]
        for k in range(len(parts) - 1):
            ring = shape.points[parts[k]:parts[k + 1]]
            # Shapefile stores (lon, lat); we want (lat, lon).
            vertices = [(p[1], p[0]) for p in ring]
            if min_area_km2 > 0 and ring_area_km2(vertices) < min_area_km2:
                dropped += 1
                continue
            if insert_polygon(con, kind, elev_ft, vertices, max_vertices):
                n += 1
    notes = []
    if dropped:
        notes.append(f"{dropped} below {min_area_km2} km^2")
    if fc_dropped:
        notes.append(f"{fc_dropped} off-class")
    extra = f" ({', '.join(notes)} dropped)" if notes else ""
    print(f"  {Path(path).name}: imported {n} ring(s) as kind={kind}{extra}")
    return n


def import_text(con, path, max_vertices):
    """Import polygons from the documented text format."""
    cur_kind = None
    cur_elev = None
    cur_verts: list = []
    n = 0

    def flush():
        nonlocal cur_verts, n
        if cur_kind and len(cur_verts) >= 3:
            if insert_polygon(con, cur_kind, cur_elev, cur_verts, max_vertices):
                n += 1
        cur_verts = []

    with open(path, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                if line == "":
                    flush()
                continue
            if line.startswith("P "):
                flush()
                parts = line.split()
                cur_kind = parts[1].lower()
                cur_elev = float(parts[2]) if len(parts) >= 3 else None
            else:
                lat_s, lon_s = line.split()
                cur_verts.append((float(lat_s), float(lon_s)))
    flush()
    print(f"  {Path(path).name}: imported {n} polygon(s)")
    return n


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", help="sqlite output path")
    p.add_argument("--ocean", action="append", default=[],
                   help="ocean shapefile (no surface elev; SRTM may be 0/void)")
    p.add_argument("--lake", action="append", default=[],
                   help="lake shapefile; elev sampled from SRTM at render time")
    p.add_argument("--river", action="append", default=[],
                   help="river polygon shapefile")
    p.add_argument("--osm-water", action="append", default=[],
                   help="generic OSM water shapefile (kind='water')")
    p.add_argument("--text", action="append", default=[],
                   help="text-format polygon file (see module docstring)")
    p.add_argument("--max-vertices", type=int, default=32,
                   help="cap polygons to this many vertices via stride "
                        "decimation; on-disk BLOBs shrink ~150x for OSM "
                        "coastlines and per-frame water.query goes from "
                        "~50ms to under 1ms. Default 32 (matches "
                        "WaterDB.DEFAULT_MAX_VERTICES). Pass 0 to disable.")
    p.add_argument("--min-area-km2", type=float, default=0.0,
                   help="drop inland-water rings smaller than this area "
                        "(km^2) to declutter tiny ponds. Applies to "
                        "--lake/--river/--osm-water only; the ocean layer "
                        "is never filtered (coastline integrity). Default "
                        "0 disables filtering.")
    p.add_argument("--keep-fclass", nargs="*", default=None,
                   help="for OSM shapefiles with an 'fclass' field, keep only "
                        "these classes (e.g. water reservoir). Drops 'riverbank' "
                        "(rivers fill as lake-blobs) and 'wetland*'. The ocean "
                        "layer (no fclass) is unaffected. Omit to keep all.")
    p.add_argument("--ocean-max-vertices", type=int, default=None,
                   help="vertex cap for the --ocean (coastline) layer; defaults "
                        "to --max-vertices, which is the recommendation -- ocean "
                        "should match inland. Coastlines DO need the detail: a low "
                        "cap smooths coastal bays/inlets into land (at cap 32 the "
                        "Baie de Gaspe rendered as land). Only ~1 in 100 ocean "
                        "polygons are complex enough to use the cap; open ocean "
                        "simplifies to a few verts regardless, so matching the "
                        "inland cap is nearly free (~+10pct).")
    args = p.parse_args()
    max_verts = args.max_vertices if args.max_vertices > 0 else None
    ov = args.ocean_max_vertices if args.ocean_max_vertices is not None else args.max_vertices
    ocean_verts = ov if ov > 0 else None
    min_area = args.min_area_km2
    keep_fclass = set(args.keep_fclass) if args.keep_fclass else None

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(str(out))
    con.executescript(SCHEMA)

    total = 0
    for path in args.ocean:
        total += import_shapefile(con, path, "ocean", ocean_verts)
    for path in args.lake:
        total += import_shapefile(con, path, "lake", max_verts,
                                  min_area_km2=min_area, keep_fclass=keep_fclass)
    for path in args.river:
        total += import_shapefile(con, path, "river", max_verts,
                                  min_area_km2=min_area, keep_fclass=keep_fclass)
    for path in args.osm_water:
        total += import_shapefile(con, path, "water", max_verts,
                                  min_area_km2=min_area, keep_fclass=keep_fclass)
    for path in args.text:
        total += import_text(con, path, max_verts)
    con.commit()
    con.close()
    filt = f", min-area={min_area} km^2" if min_area > 0 else ""
    ocn = f", ocean cap={ocean_verts}" if ocean_verts != max_verts else ""
    print(f"-> {out} ({total} polygons, vertex cap={max_verts}{ocn}{filt})")


if __name__ == "__main__":
    main()
