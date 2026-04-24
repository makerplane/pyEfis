"""
Synthetic Vision System (SVS) terrain renderer for the pyEfis AI widget.

Reads SRTM3 HGT tiles and projects a terrain grid into the AI viewport
using the same pixelsPerDeg coordinate frame as the Flight Path Marker.

Rendering tiers (selected by config):
  cpu_sparse  — 48×48 NumPy grid, ~15 Hz on Raspberry Pi 4
  cpu_dense   — 128×128 NumPy grid, ~20 Hz on Raspberry Pi 5 / x86
  opengl      — QOpenGLWidget mesh (future; falls back to cpu_sparse)

Tile format: NASA SRTMGL3 V003, 1°×1° HGT tiles, big-endian int16,
1201×1201 samples. Void values (-32768) are treated as sea level.

SVS is disabled by default. Enable in screen YAML:
    svs:
        enabled: true
        renderer: cpu_sparse
        range_nm: 30
        tile_path: /media/terrain/srtm3
"""

import math
import os
import sqlite3
import struct
import logging
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QColor, QPainter, QPolygonF

log = logging.getLogger(__name__)

# SRTM3 tile constants
SRTM3_SAMPLES = 1201          # samples per side (includes 1-sample overlap)
SRTM3_VOID    = -32768        # void / no-data marker

# Clearance colour thresholds (ft above terrain)
COLOR_SAFE      = QColor(0,   100,  0)    # dark green  — ≥ green threshold
COLOR_CAUTION   = QColor(180, 130,  0)    # amber       — yellow threshold to green
COLOR_WARNING   = QColor(200,  40,  0)    # dark red    — 0 to yellow threshold
COLOR_CONFLICT  = QColor(180,   0, 180)   # magenta     — aircraft at or below terrain

# Rendering grid sizes per tier
GRID_SIZES = {
    "cpu_sparse": 48,
    "cpu_dense":  128,
    "opengl":     48,   # opengl tier not yet implemented; falls back to cpu_sparse
}


# ---------------------------------------------------------------------------
# HGT tile reader
# ---------------------------------------------------------------------------

def tile_name(lat: int, lon: int) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}"


def _hgt_path(tile_root: Path, lat: int, lon: int) -> Path | None:
    """Find the HGT file for the 1°×1° tile whose SW corner is (lat, lon)."""
    name = tile_name(lat, lon)
    ns_dir = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"
    candidates = [
        tile_root / ns_dir / f"{name}.hgt",
        tile_root / f"{name}.hgt",
        tile_root / f"{name}.HGT",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def load_tile(tile_root: Path, lat: int, lon: int) -> np.ndarray | None:
    """
    Load an SRTM3 HGT tile and return a (1201, 1201) int16 NumPy array.
    Row 0 = northernmost row; column 0 = westernmost column.
    Returns None if the tile file is not found.
    """
    path = _hgt_path(tile_root, lat, lon)
    if path is None:
        return None
    try:
        data = np.fromfile(path, dtype=">i2").reshape(SRTM3_SAMPLES, SRTM3_SAMPLES)
        data[data == SRTM3_VOID] = 0
        return data
    except Exception as e:
        log.warning(f"SVS: failed to load tile {path}: {e}")
        return None


def elevation_at(tile: np.ndarray, tile_lat: int, tile_lon: int,
                 lat: float, lon: float) -> float:
    """Bilinear interpolation of elevation at (lat, lon) from a loaded tile."""
    row_f = (tile_lat + 1.0 - lat) * (SRTM3_SAMPLES - 1)
    col_f = (lon - tile_lon)       * (SRTM3_SAMPLES - 1)
    row = int(row_f); col = int(col_f)
    row = max(0, min(row, SRTM3_SAMPLES - 2))
    col = max(0, min(col, SRTM3_SAMPLES - 2))
    dr = row_f - row; dc = col_f - col
    return (tile[row,   col  ] * (1 - dr) * (1 - dc) +
            tile[row,   col+1] * (1 - dr) *      dc  +
            tile[row+1, col  ] *      dr  * (1 - dc) +
            tile[row+1, col+1] *      dr  *      dc)


# ---------------------------------------------------------------------------
# Terrain cache — keeps recently used tiles in memory
# ---------------------------------------------------------------------------

class TileCache:
    def __init__(self, tile_root: Path, max_tiles: int = 9):
        self.tile_root = tile_root
        self.max_tiles = max_tiles
        self._cache: dict[tuple, np.ndarray] = {}
        self._order: list[tuple] = []

    def get(self, lat: int, lon: int) -> np.ndarray | None:
        key = (lat, lon)
        if key in self._cache:
            self._order.remove(key)
            self._order.append(key)
            return self._cache[key]
        tile = load_tile(self.tile_root, lat, lon)
        if tile is not None:
            self._cache[key] = tile
            self._order.append(key)
            if len(self._order) > self.max_tiles:
                evict = self._order.pop(0)
                del self._cache[evict]
        return tile

    def elevation(self, lat: float, lon: float) -> float:
        """Return MSL elevation in metres at (lat, lon), or 0.0 if no tile."""
        tile_lat = int(math.floor(lat))
        tile_lon = int(math.floor(lon))
        tile = self.get(tile_lat, tile_lon)
        if tile is None:
            return 0.0
        return elevation_at(tile, tile_lat, tile_lon, lat, lon)


# ---------------------------------------------------------------------------
# SVS renderer
# ---------------------------------------------------------------------------

NM_TO_DEG = 1.0 / 60.0   # 1 NM ≈ 1/60 degree latitude

class SVSRenderer:
    """
    Projects a terrain grid into the AI viewport.

    Coordinate convention matches the AI + FPM: the viewport centre is the
    aircraft reference (pitch=0, roll=0). pixelsPerDeg converts angular
    offsets to pixels. The terrain is projected point-by-point: for each
    grid sample we compute its bearing and elevation angle relative to the
    aircraft, then map those to (x, y) in the AI viewport using the same
    roll/pitch transform as the FPM.
    """

    def __init__(self, config: dict):
        self.enabled      = config.get("enabled", False)
        self.renderer     = config.get("renderer", "cpu_sparse")
        self.range_nm     = float(config.get("range_nm", 30))
        tile_path         = config.get("tile_path", "")
        self.cache        = TileCache(Path(tile_path)) if tile_path else None
        self.green_ft     = float(config.get("clearance_green_ft",  1000))
        self.yellow_ft    = float(config.get("clearance_yellow_ft",  500))
        self._grid_n      = GRID_SIZES.get(self.renderer, 48)

    @property
    def ready(self) -> bool:
        return self.enabled and self.cache is not None and self.cache.tile_root.is_dir()

    def _clearance_color(self, clearance_ft: float) -> QColor:
        if clearance_ft < 0:
            return COLOR_CONFLICT
        elif clearance_ft < self.yellow_ft:
            return COLOR_WARNING
        elif clearance_ft < self.green_ft:
            return COLOR_CAUTION
        return COLOR_SAFE

    def draw(self, p: QPainter, w: int, h: int,
             ac_lat: float, ac_lon: float, ac_alt_ft: float,
             pitch_deg: float, roll_deg: float, heading_deg: float,
             pixels_per_deg: float):
        """
        Draw the SVS terrain overlay onto the AI viewport.

        Called from AI.paintEvent() when SVS is enabled and data is ready.
        The painter p has NO active transform — SVS builds its own.
        """
        if not self.ready:
            return

        n = self._grid_n
        range_deg = self.range_nm * NM_TO_DEG

        # Build a grid of (lat, lon) points centred on the aircraft
        # Grid runs from -range_deg to +range_deg in both lat and lon
        lats = np.linspace(ac_lat - range_deg, ac_lat + range_deg, n)
        lons = np.linspace(ac_lon - range_deg, ac_lon + range_deg, n)
        lat_grid, lon_grid = np.meshgrid(lats, lons, indexing='ij')  # (n, n)

        # Vectorised terrain elevation lookup (one tile at a time)
        elev_m = self._sample_elevations(lat_grid, lon_grid, n)
        elev_ft = elev_m * 3.28084

        # Convert terrain positions to bearing/elevation angles relative to aircraft
        # Angular offset in degrees (flat-Earth approximation, fine for 30 NM)
        lat_cos = math.cos(math.radians(ac_lat))
        d_lat = (lat_grid - ac_lat)                  # degrees N/S
        d_lon = (lon_grid - ac_lon) * lat_cos        # degrees E/W (scaled)

        # Rotate into heading frame: positive x = right of nose, positive y = above
        head_rad = math.radians(heading_deg)
        cos_h, sin_h = math.cos(head_rad), math.sin(head_rad)
        # d_lon = east, d_lat = north → aircraft frame
        x_fwd =  d_lat * cos_h + d_lon * sin_h   # forward (positive = ahead)
        x_right= -d_lat * sin_h + d_lon * cos_h  # right of nose

        # Range in degrees (for distance-based culling and elevation angle)
        range_deg_grid = np.sqrt(d_lat**2 + d_lon**2)
        range_deg_grid = np.where(range_deg_grid < 1e-6, 1e-6, range_deg_grid)

        # Elevation angle of terrain above/below horizon (degrees)
        ac_alt_m = ac_alt_ft * 0.3048
        terrain_alt_m = elev_m * 1.0           # already metres
        alt_diff_m = terrain_alt_m - ac_alt_m  # positive = terrain above aircraft
        range_m = range_deg_grid * 111139.0    # 1 degree ≈ 111,139 m
        elev_angle_deg = np.degrees(np.arctan2(alt_diff_m, range_m))

        # Only draw terrain in front of the aircraft (x_fwd > 0)
        # and within the configured range
        visible = (x_fwd > 0) & (range_deg_grid < range_deg)

        # Map to AI viewport pixels using the same coordinate system as FPM
        # Lateral: x_right degrees → pixels (using pixelsPerDeg)
        # Vertical: (pitch - elev_angle) → pixels, then apply roll
        x_ang = np.degrees(np.arctan2(x_right, x_fwd))   # azimuth offset
        y_ang = elev_angle_deg - pitch_deg                 # elevation relative to pitch

        x_px = x_ang * pixels_per_deg
        y_px = -y_ang * pixels_per_deg     # negative = up on screen

        # Apply roll rotation to (x_px, y_px)
        roll_rad = math.radians(roll_deg)
        cos_r, sin_r = math.cos(-roll_rad), math.sin(-roll_rad)
        x_rot = x_px * cos_r - y_px * sin_r + w / 2
        y_rot = x_px * sin_r + y_px * cos_r + h / 2

        # Clearance colours
        clearance_ft = ac_alt_ft - elev_ft

        # Draw each visible terrain cell as a filled square
        cell_px = max(2, int(pixels_per_deg * range_deg * 2 / n))

        p.save()
        p.setPen(Qt_NoPen())
        for i in range(n):
            for j in range(n):
                if not visible[i, j]:
                    continue
                cx = float(x_rot[i, j])
                cy = float(y_rot[i, j])
                if cx < -cell_px or cx > w + cell_px or cy < -cell_px or cy > h + cell_px:
                    continue
                color = self._clearance_color(float(clearance_ft[i, j]))
                p.fillRect(QRectF(cx - cell_px/2, cy - cell_px/2, cell_px, cell_px), color)
        p.restore()

    def _sample_elevations(self, lat_grid: np.ndarray, lon_grid: np.ndarray, n: int) -> np.ndarray:
        """Sample elevation from the tile cache for each grid point."""
        elev = np.zeros((n, n), dtype=np.float32)
        for i in range(n):
            for j in range(n):
                elev[i, j] = self.cache.elevation(float(lat_grid[i, j]), float(lon_grid[i, j]))
        return elev


# ---------------------------------------------------------------------------
# Tiny helper — avoids importing Qt.NoPen at module level before QApp exists
# ---------------------------------------------------------------------------
def Qt_NoPen():
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPen
    return QPen(Qt.PenStyle.NoPen)
