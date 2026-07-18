"""
Water-body polygon loader for the SVS renderer.

Wraps water.sqlite built by tools/build_water_db.py from OSM /
Natural Earth shapefiles. Range-queryable by bbox; returns
WaterPolygon records that the SVS renderer projects via
``_project_polygon_clipped`` and fills with the standard COLOR_WATER.

    db = WaterDB(path)
    for poly in db.polygons_in_range(ac_lat, ac_lon, range_nm):
        for lat, lon in poly.vertices:
            ...

Construction never raises; if the file is missing or unreadable,
``ready`` stays False and queries yield nothing.

Schema (built by tools/build_water_db.py):
    water_polygons(
        id        INTEGER PRIMARY KEY,
        min_lat   REAL NOT NULL,
        max_lat   REAL NOT NULL,
        min_lon   REAL NOT NULL,
        max_lon   REAL NOT NULL,
        kind      TEXT NOT NULL,   -- 'ocean' | 'lake' | 'river' | ...
        elev_ft   REAL,            -- known surface elev (lakes); NULL for ocean
        vertices  BLOB NOT NULL    -- struct-packed <dd>... = list of (lat, lon)
    )
    INDEX idx_bbox ON water_polygons(min_lat, max_lat, min_lon, max_lon)
"""

from __future__ import annotations

import logging
import math
import sqlite3
import struct
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

NM_PER_DEG_LAT = 60.0


@dataclass
class WaterPolygon:
    id        : int
    kind      : str          # 'ocean', 'lake', 'river', ...
    elev_ft   : float | None # known water-surface elev; None = sample SRTM
    vertices  : list = field(default_factory=list)  # [(lat, lon), ...]
    # Pre-tessellated triangle indices (flat list of ints, 3 per
    # triangle, into the ``vertices`` list). Bytes blob in storage,
    # decoded to a Python list at load time so the GPU renderer can
    # convert to whatever it wants. None when the build tool was
    # older than the tessellation schema bump.
    triangles : list | None = None

    @property
    def is_ocean(self) -> bool:
        return self.kind == "ocean"


class WaterDB:
    # Per-polygon vertex cap applied on load. OSM coastline polygons
    # routinely carry thousands of vertices at ~30 m spacing — far
    # finer than any 5" / 7" cockpit display can resolve at 30 NM
    # range. The CPU projection loop is per-vertex Python work, so
    # uncapped polygons make pyEfis unusable when the camera is near
    # a complex coastline. 64 vertices around any polygon is enough
    # to read the shape at typical SVS distances; tunable per-config
    # for users who want denser coastlines on larger displays.
    DEFAULT_MAX_VERTICES = 32

    def __init__(self, sqlite_path: str | Path | None,
                 max_vertices: int | None = None):
        self._path = Path(sqlite_path) if sqlite_path else None
        self._con: sqlite3.Connection | None = None
        self._max_vertices = (max_vertices
                              if max_vertices is not None
                              else self.DEFAULT_MAX_VERTICES)
        # True when an R-Tree spatial index virtual table is present;
        # we then use it for bbox queries instead of the plain B-tree
        # index on min/max columns. R-Tree is ~50x faster on KSBA-
        # scale queries against the 878k-polygon OSM dataset.
        self._has_rtree = False
        self._has_triangles = False
        if self._path is None or not self._path.is_file():
            log.info("WaterDB: %s not found — water rendering disabled",
                     self._path)
            return
        try:
            self._con = sqlite3.connect(str(self._path),
                                        check_same_thread=False)
            self._con.row_factory = sqlite3.Row
            # Sanity-check the schema. If the table or column shape is
            # wrong we drop back to "not ready" rather than crashing
            # downstream.
            self._con.execute(
                "SELECT id, min_lat, max_lat, min_lon, max_lon, "
                "       kind, elev_ft, vertices "
                "FROM water_polygons LIMIT 0")
            # Probe for the R-Tree virtual table; older DBs without
            # it fall back to the plain bbox query.
            try:
                self._con.execute(
                    "SELECT id FROM water_rtree LIMIT 0")
                self._has_rtree = True
                log.info("WaterDB: using R-Tree spatial index")
            except sqlite3.OperationalError:
                log.info(
                    "WaterDB: no R-Tree found, falling back to bbox "
                    "B-tree index (slower; rebuild with current "
                    "build_water_db.py for R-Tree)")
            # Probe for the triangles column (added in the SVS-overlays-
            # to-GPU migration). Pre-tessellation DBs work too — the
            # renderer will fall back to a fan triangulation when the
            # column is missing.
            try:
                self._con.execute(
                    "SELECT triangles FROM water_polygons LIMIT 0")
                self._has_triangles = True
            except sqlite3.OperationalError:
                log.info(
                    "WaterDB: no triangles column found; GPU water "
                    "renderer will fan-tessellate at draw time "
                    "(slower; rebuild with current build_water_db.py "
                    "for pre-tessellation)")
        except Exception as e:
            log.warning("WaterDB: cannot open %s: %s", self._path, e)
            self._con = None

    @property
    def ready(self) -> bool:
        return self._con is not None

    def polygons_in_range(self, ac_lat: float, ac_lon: float,
                          range_nm: float,
                          min_bbox_diag_deg: float | None = None,
                          drop_ocean: bool = False):
        """Yield ``WaterPolygon`` for each polygon whose bounding box
        overlaps the aircraft's ``range_nm`` square. The yielded
        polygons may extend well beyond the range — the SVS clipper
        handles geometric clipping in screen space.

        ``min_bbox_diag_deg`` rejects polygons whose bbox diagonal is
        below this threshold (in degrees) at the SQL level — useful
        for dropping sub-pixel ponds before paying the BLOB-decode and
        per-vertex projection cost. The check is done on the squared
        diagonal so the SQL stays multiplication-only. Ocean polygons
        are NEVER filtered by size — a coastline poly's bbox can be
        tiny (small bay, inlet) yet still cover the visible field —
        UNLESS ``drop_ocean`` is set.

        ``drop_ocean`` excludes ``kind == 'ocean'`` polygons entirely and
        subjects everything else to the size floor. At wide zoom the terrain
        void-water already shows oceans, so dropping the (never-size-filtered,
        vertex-heavy) coastline here is the cheap way to keep only large inland
        lakes — e.g. the Great Lakes — for orientation.
        """
        if not self.ready:
            return
        lat_cos = math.cos(math.radians(ac_lat))
        range_deg_lat = range_nm / NM_PER_DEG_LAT
        range_deg_lon = range_deg_lat / max(lat_cos, 1e-6)
        lat_lo = ac_lat - range_deg_lat
        lat_hi = ac_lat + range_deg_lat
        lon_lo = ac_lon - range_deg_lon
        lon_hi = ac_lon + range_deg_lon
        min_d2 = (min_bbox_diag_deg * min_bbox_diag_deg
                  if min_bbox_diag_deg else None)

        if self._has_rtree:
            # R-Tree virtual-table overlap: sqlite walks the spatial
            # index and returns only the polygons whose bbox actually
            # overlaps the query bbox. Sub-millisecond vs ~50 ms for
            # the B-tree fallback at OSM dataset scale.
            tri_expr = ("p.triangles" if self._has_triangles
                        else "NULL AS triangles")
            sql = (
                "SELECT p.id, p.kind, p.elev_ft, p.vertices, "
                f"       {tri_expr}, "
                "       p.min_lat, p.max_lat, p.min_lon, p.max_lon "
                "FROM water_polygons p "
                "JOIN water_rtree r ON r.id = p.id "
                "WHERE r.min_lat <= ? AND r.max_lat >= ? "
                "  AND r.min_lon <= ? AND r.max_lon >= ?")
            params = (lat_hi, lat_lo, lon_hi, lon_lo)
            if drop_ocean:
                sql += " AND p.kind != 'ocean'"
            if min_d2 is not None:
                size = ("((p.max_lat-p.min_lat)*(p.max_lat-p.min_lat) "
                        "+ (p.max_lon-p.min_lon)*(p.max_lon-p.min_lon)) >= ?")
                sql += (f" AND ({size})" if drop_ocean
                        else f" AND (p.kind = 'ocean' OR {size})")
                params = params + (min_d2,)
            cur = self._con.execute(sql, params)
        else:
            tri_expr = ("triangles" if self._has_triangles
                        else "NULL AS triangles")
            sql = (
                "SELECT id, kind, elev_ft, vertices, "
                f"       {tri_expr}, "
                "       min_lat, max_lat, min_lon, max_lon "
                "FROM water_polygons "
                "WHERE max_lat > ? AND min_lat < ? "
                "  AND max_lon > ? AND min_lon < ?")
            params = (lat_lo, lat_hi, lon_lo, lon_hi)
            if drop_ocean:
                sql += " AND kind != 'ocean'"
            if min_d2 is not None:
                size = ("((max_lat-min_lat)*(max_lat-min_lat) "
                        "+ (max_lon-min_lon)*(max_lon-min_lon)) >= ?")
                sql += (f" AND ({size})" if drop_ocean
                        else f" AND (kind = 'ocean' OR {size})")
                params = params + (min_d2,)
            cur = self._con.execute(sql, params)
        cap = self._max_vertices
        for r in cur:
            yield WaterPolygon(
                id=r["id"],
                kind=(r["kind"] or "").strip().lower(),
                elev_ft=r["elev_ft"],
                vertices=_decode_vertices(r["vertices"], cap),
                triangles=_decode_triangles(r["triangles"]))


def _decode_vertices(blob: bytes, max_vertices: int | None = None) -> list:
    """Unpack a struct-packed <dd... bytes blob into [(lat, lon), ...].

    When ``max_vertices`` is set and the polygon has more vertices than
    that, stride-decimate uniformly down to the cap (always preserving
    the first and last points so the polygon's bounding extent is
    intact). This is the simplest possible cartographic simplification
    — Douglas-Peucker would preserve curvature better but isn't worth
    the per-load CPU when the screen can't resolve the difference at
    typical SVS distances.

    Uses numpy.frombuffer for the bulk decode — at ~200 polygons /
    frame in the GPU water path each saved millisecond shows up in
    the visible frame rate, and the Python ``struct.unpack_from``
    loop was visible in the profile."""
    if not blob:
        return []
    import numpy as _np
    pts = _np.frombuffer(blob, dtype="<f8").reshape(-1, 2)
    n = pts.shape[0]
    if max_vertices and n > max_vertices:
        # Even-stride decimation preserving indices 0 and n-1.
        idx = _np.round(_np.linspace(0, n - 1, max_vertices)).astype(int)
        pts = pts[idx]
    # Return as a list of plain Python tuples — the GPU collector
    # immediately re-wraps them with np.asarray, but the rest of the
    # codebase (and tests) treats vertices as a list-of-tuples.
    return [tuple(row) for row in pts.tolist()]


def encode_vertices(vertices) -> bytes:
    """Pack [(lat, lon), ...] into a struct-packed <dd... bytes blob.
    Inverse of ``_decode_vertices``; used by the build tool."""
    buf = bytearray(len(vertices) * 16)
    for i, (lat, lon) in enumerate(vertices):
        struct.pack_into("<dd", buf, i * 16, float(lat), float(lon))
    return bytes(buf)


def _decode_triangles(blob):
    """Unpack a uint16 little-endian triangle-index blob into a flat
    list of ints (3 entries per triangle). Returns None when the
    polygon was inserted by a pre-tessellation build of the DB and
    has no triangles stored."""
    if not blob:
        return None
    n = len(blob) // 2
    return list(struct.unpack(f"<{n}H", blob))
