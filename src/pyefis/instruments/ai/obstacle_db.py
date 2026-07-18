"""
FAA Digital Obstacle File (DOF) loader for the SVS renderer.

Wraps obstacles.sqlite built by tools/build_obstacle_db.py from the
FAA DOF CSV. Range-queryable, returns ObstacleRecord namedtuples that
the SVS renderer projects as vertical poles.

    db = ObstacleDB(path)
    for o in db.obstacles_in_range(ac_lat, ac_lon, range_nm, min_agl_ft=200):
        o.lat, o.lon, o.amsl_ft, o.agl_ft, o.type, o.lighting

Construction never raises; if the file is missing or unreadable, ``ready``
stays False and queries yield nothing.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

NM_PER_DEG_LAT = 60.0

# Lighting code → coarse category. The DOF carries many sub-codes; for
# visual rendering we just need to know "red", "white", or "none/unknown".
LIGHTING_RED   = frozenset(("R", "RED", "M"))                # red obstruction
LIGHTING_WHITE = frozenset(("W", "WHITE", "H", "HD"))        # white / strobe
LIGHTING_DUAL  = frozenset(("D", "DUAL"))                    # day/night dual


@dataclass
class ObstacleRecord:
    oas_no   : str
    lat      : float
    lon      : float
    amsl_ft  : float     # tip elevation, MSL
    agl_ft   : float     # height above ground
    type     : str       # "TOWER", "ANTENNA", "BLDG", "STACK", "WIND TURB", ...
    lighting : str       # raw code; use lighting_category() for {"red","white","dual","none"}
    quantity : int = 1
    city     : str = ""
    state    : str = ""

    def lighting_category(self) -> str:
        c = (self.lighting or "").upper().strip()
        if c in LIGHTING_RED:   return "red"
        if c in LIGHTING_WHITE: return "white"
        if c in LIGHTING_DUAL:  return "dual"
        return "none"

    @property
    def base_amsl_ft(self) -> float:
        """Elevation of the obstacle's base (ground level under it)."""
        return self.amsl_ft - self.agl_ft


class ObstacleDB:
    def __init__(self, sqlite_path: str | Path | None):
        self._path = Path(sqlite_path) if sqlite_path else None
        self._con: sqlite3.Connection | None = None
        if self._path is None or not self._path.is_file():
            log.info("ObstacleDB: %s not found — obstacles disabled", self._path)
            return
        try:
            self._con = sqlite3.connect(str(self._path),
                                        check_same_thread=False)
            self._con.row_factory = sqlite3.Row
        except Exception as e:
            log.warning("ObstacleDB: cannot open %s: %s", self._path, e)
            self._con = None

    @property
    def ready(self) -> bool:
        return self._con is not None

    def obstacles_in_range(self, ac_lat: float, ac_lon: float,
                           range_nm: float, min_agl_ft: float = 200.0):
        """Yield ObstacleRecord for each obstacle whose tip is within
        *range_nm* of the aircraft AND has AGL ≥ *min_agl_ft*."""
        if not self.ready:
            return
        lat_cos = math.cos(math.radians(ac_lat))
        range_deg_lat = range_nm / NM_PER_DEG_LAT
        range_deg_lon = range_deg_lat / max(lat_cos, 1e-6)
        lat_lo = ac_lat - range_deg_lat
        lat_hi = ac_lat + range_deg_lat
        lon_lo = ac_lon - range_deg_lon
        lon_hi = ac_lon + range_deg_lon

        cur = self._con.execute(
            "SELECT oas_no, lat, lon, amsl_ft, agl_ft, type, lighting, "
            "       quantity, city, state "
            "FROM obstacles "
            "WHERE lat BETWEEN ? AND ? "
            "  AND lon BETWEEN ? AND ? "
            "  AND agl_ft >= ?",
            (lat_lo, lat_hi, lon_lo, lon_hi, float(min_agl_ft)))
        range_nm_sq = range_nm * range_nm
        for r in cur:
            d_lat = (r["lat"] - ac_lat) * NM_PER_DEG_LAT
            d_lon = (r["lon"] - ac_lon) * NM_PER_DEG_LAT * lat_cos
            if d_lat * d_lat + d_lon * d_lon > range_nm_sq:
                continue
            yield ObstacleRecord(
                oas_no=r["oas_no"],
                lat=r["lat"], lon=r["lon"],
                amsl_ft=r["amsl_ft"], agl_ft=r["agl_ft"],
                type=(r["type"] or "").strip(),
                lighting=(r["lighting"] or "").strip(),
                quantity=r["quantity"] or 1,
                city=(r["city"] or "").strip(),
                state=(r["state"] or "").strip())
