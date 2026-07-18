"""
Synthetic Vision System (SVS) terrain renderer for the pyEfis AI widget.

Reads SRTM3 HGT tiles and projects a terrain grid into the AI viewport
using the same pixelsPerDeg coordinate frame as the Flight Path Marker.

GL-required: the only renderer is the GPU pipeline in svs_gl.py
(terrain heightmap mesh + every overlay). If a GL context cannot be
created — or any GL draw fails — the SVS disables itself permanently
for the process and the AI widget annunciates SVS UNAVAIL. There is
no CPU fallback (docs/svs_structural_plan.md P2): a silently degraded
terrain picture that omits obstacles is worse than an honest absence.

Tile format: 1°×1° HGT tiles, big-endian int16, square. Resolution
is inferred from file size per tile: 1201×1201 (SRTM3, 3 arc-sec) and
3601×3601 (1 arc-sec — Copernicus GLO-30 via tools/convert_glo30.py)
coexist in one tile tree. Void values (-32768) are treated as sea
level; GLO-30 has no voids.

SVS is disabled by default. Enable in screen YAML:
    svs:
        enabled: true
        range_nm: 30
        tile_path: /media/terrain/srtm3
"""

import math
import os
import sqlite3
import struct
import threading
import logging
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Lightweight per-frame profiler. Each named segment accumulates wall-clock
# time and a call count; once the report interval elapses we log a single
# summary line and reset. Enabled via ``svs_perf_log: true`` in the SVS
# config block; zero overhead when disabled (the methods check a flag
# before doing any timing math).
# ---------------------------------------------------------------------------
class _SVSPerfLog:
    REPORT_INTERVAL_S = 2.0

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self._accum: dict[str, int] = {}    # ns total since last report
        self._count: dict[str, int] = {}
        self._last_report = time.perf_counter() if enabled else 0.0

    def time(self, name: str):
        """Context manager that times the with-block and adds it to
        the accumulator under *name*. No-ops cleanly when disabled."""
        if not self.enabled:
            return _NoopTimer()
        return _PerfTimer(self, name)

    def add_ns(self, name: str, ns: int):
        if not self.enabled:
            return
        self._accum[name] = self._accum.get(name, 0) + ns
        self._count[name] = self._count.get(name, 0) + 1

    def maybe_report(self, extra_lines=None):
        if not self.enabled:
            return False
        now = time.perf_counter()
        if now - self._last_report < self.REPORT_INTERVAL_S:
            return False
        elapsed = now - self._last_report
        lines = [f"SVS perf (last {elapsed:.1f}s):"]
        for name in sorted(self._accum, key=lambda k: -self._accum[k]):
            n = self._count[name]
            total_ms = self._accum[name] / 1e6
            per_call_ms = total_ms / n if n else 0
            pct = 100.0 * (self._accum[name] / 1e9) / elapsed
            lines.append(
                f"  {name:<30} {n:>5} calls  "
                f"{total_ms:>8.1f}ms total  "
                f"{per_call_ms:>7.2f}ms/call  "
                f"{pct:>5.1f}%")
        if extra_lines:
            lines.extend(extra_lines)
        log.info("\n".join(lines))
        self._accum.clear()
        self._count.clear()
        self._last_report = now
        return True


class _PerfTimer:
    """Tiny context manager that records the with-block duration."""
    __slots__ = ("_p", "_name", "_t0")

    def __init__(self, p, name):
        self._p = p
        self._name = name

    def __enter__(self):
        self._t0 = time.perf_counter_ns()
        return self

    def __exit__(self, *exc):
        self._p.add_ns(self._name, time.perf_counter_ns() - self._t0)
        return False


class _NoopTimer:
    """Returned when profiling is off — zero allocation, zero work."""
    __slots__ = ()
    def __enter__(self): return self
    def __exit__(self, *exc): return False

import numpy as np
from PyQt6.QtGui import QColor, QPainter

log = logging.getLogger(__name__)

# SRTM3 tile constants
SRTM3_SAMPLES = 1201          # samples per side (includes 1-sample overlap)
SRTM3_VOID    = -32768        # void / no-data marker

# Clearance colour thresholds (ft above terrain)
COLOR_SAFE      = QColor(0,   100,  0)    # dark green  — ≥ green threshold
COLOR_CAUTION   = QColor(180, 130,  0)    # amber       — yellow threshold to green
COLOR_WARNING   = QColor(200,  40,  0)    # dark red    — 0 to yellow threshold
COLOR_CONFLICT  = QColor(180,   0, 180)   # magenta     — aircraft at or below terrain
COLOR_WATER     = QColor( 20,  80, 150)   # ocean blue  — SRTM void / open water

# Named terrain palettes selectable via the `palette` SVS config key. Each maps
# the five clearance bands (safe, caution, warning, conflict, water).
# "clearance" is the stock scheme (the module COLOR_* constants); the others
# tune saturation / contrast. set_svs_config copies the chosen set onto the
# instance (self.c_*); _clearance_color falls back to the module constants when
# no palette was selected, so behaviour is identical unless a palette is named.
_PALETTES = {
    "clearance": (COLOR_SAFE, COLOR_CAUTION, COLOR_WARNING, COLOR_CONFLICT,
                  COLOR_WATER),
    "subdued": (QColor(20, 70, 25), QColor(120, 95, 15), QColor(140, 45, 15),
                QColor(150, 0, 150), QColor(25, 60, 105)),
    "high_contrast": (QColor(0, 170, 0), QColor(245, 190, 0), QColor(235, 35, 0),
                      QColor(230, 0, 230), QColor(0, 120, 215)),
}

# Sentinel written into elevation arrays where the source tile was void (ocean).
# Must be far enough negative that real below-sea-level terrain (≥ −430 m) is
# never mistaken for water.
_WATER_SENTINEL = -9999.0

# Polar (range, azimuth) mesh defaults for the GL terrain renderer — a
# forward-facing fan centred on the aircraft, with a radial warp that
# concentrates samples near the aircraft (finer near, coarser far). See
# docs/svs_rendering.md for the rationale.
#
# Cells = n_range × n_az. At the defaults below: 80 × 120 = 9,600 cells —
# 42% fewer quads than cpu_dense (16k) but ~25% faster per frame and
# noticeably crisper in the near-field thanks to the radial LOD. Tuned
# from an A/B sweep at 39.20 N / 106.85 W, 12,000 ft, head 150°.
POLAR_DEFAULTS = {
    "n_range":     80,    # radial samples
    "n_az":        120,   # azimuthal samples
    "fov_deg":     140.0, # total forward field-of-view (±70°)
    "radial_warp": 1.5,   # outer cell ~10× inner cell at default n_range
    "r_min_nm":    0.05,  # epsilon at r=0 to avoid the singularity
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
    Load an HGT tile and return a square float32 NumPy array.
    Row 0 = northernmost row; column 0 = westernmost column.
    Resolution is inferred from the file size (1201 SRTM3 /
    3601 GLO-30 — any square side is accepted).
    Returns None if the tile file is not found.
    """
    path = _hgt_path(tile_root, lat, lon)
    if path is None:
        return None
    try:
        data = np.fromfile(path, dtype=">i2")
        n = int(round(data.size ** 0.5))
        if n * n != data.size:
            log.warning(f"SVS: tile {path} is not square "
                        f"({data.size} samples); skipped")
            return None
        data = data.reshape(n, n).astype(np.float32)
        data[data == SRTM3_VOID] = _WATER_SENTINEL
        return data
    except Exception as e:
        log.warning(f"SVS: failed to load tile {path}: {e}")
        return None


def elevation_at(tile: np.ndarray, tile_lat: int, tile_lon: int,
                 lat: float, lon: float) -> float:
    """Bilinear interpolation of elevation at (lat, lon) from a loaded
    tile (resolution taken from the tile's own shape)."""
    n = tile.shape[0]
    row_f = (tile_lat + 1.0 - lat) * (n - 1)
    col_f = (lon - tile_lon)       * (n - 1)
    row = int(row_f); col = int(col_f)
    row = max(0, min(row, n - 2))
    col = max(0, min(col, n - 2))
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
        # The async water collector samples elevations from a worker
        # thread while the render thread also reads tiles.
        self._lock = threading.Lock()
        # Coarse pyramid tiles are tiny (a whole national window fits), so
        # cache far more of them than native tiles (terrain_mip_pyramid.md).
        self._mip: dict[tuple, np.ndarray] = {}
        self._mip_order: list[tuple] = []
        self._mip_max = 512
        # Coarse whole-extent mosaics (one memmap per level) -- wide-range
        # renders slice these instead of opening hundreds of per-degree files
        # (docs/map_wide_range_perf_plan.md). Lazily loaded, kept resident.
        self._mosaic: dict[int, object] = {}

    def get(self, lat: int, lon: int) -> np.ndarray | None:
        key = (lat, lon)
        with self._lock:
            if key in self._cache:
                self._order.remove(key)
                self._order.append(key)
                return self._cache[key]
        tile = load_tile(self.tile_root, lat, lon)
        if tile is not None:
            with self._lock:
                if key not in self._cache:
                    self._cache[key] = tile
                    self._order.append(key)
                    if len(self._order) > self.max_tiles:
                        evict = self._order.pop(0)
                        del self._cache[evict]
        return tile

    def get_mip(self, lat: int, lon: int, level: int) -> np.ndarray | None:
        """Coarse pyramid tile for (lat, lon) at ``level`` (0 = native).

        Levels >= 1 read a pre-built downsampled tile from
        ``<tile_root>/.mip/<level>/<NSdir>/<name>.hgt`` -- an ordinary smaller
        square ``>i2`` HGT (``load_tile`` infers the side from file size, and
        ``_sample`` keys off ``t.shape[0]``, so nothing else changes). A missing
        level file (an edition built without a pyramid) falls back to the native
        tile, so old data still renders -- just slow at range. Spec:
        docs/terrain_mip_pyramid.md."""
        if level <= 0:
            return self.get(lat, lon)
        key = (lat, lon, level)
        with self._lock:
            if key in self._mip:
                self._mip_order.remove(key)
                self._mip_order.append(key)
                return self._mip[key]
        tile = load_tile(self.tile_root / ".mip" / str(level), lat, lon)
        if tile is None:
            return self.get(lat, lon)          # no pyramid here -> native
        with self._lock:
            if key not in self._mip:
                self._mip[key] = tile
                self._mip_order.append(key)
                if len(self._mip_order) > self._mip_max:
                    evict = self._mip_order.pop(0)
                    del self._mip[evict]
        return tile

    def get_mosaic(self, level: int):
        """Coarse whole-extent mosaic for ``level``, or ``None`` if not built.

        Returns ``(memmap, meta)`` for ``.mip/mosaic/L<level>.{hgt,json}`` -- one
        memory-mapped big-endian int16 array covering the tile tree's extent, so
        a wide-range render slices its window in a single vectorized bilinear
        instead of opening hundreds of per-degree files (the measured cold-I/O
        bottleneck; docs/map_wide_range_perf_plan.md). meta keys: rows, cols,
        spd (samples per degree), lat_n (north lat of row 0), lon_w (west lon of
        col 0). Row r -> lat = lat_n - r/spd; col c -> lon = lon_w + c/spd."""
        with self._lock:
            if level in self._mosaic:
                return self._mosaic[level]
        import json
        mdir = self.tile_root / ".mip" / "mosaic"
        jp = mdir / f"L{level}.json"
        dp = mdir / f"L{level}.hgt"
        val = None
        if jp.exists() and dp.exists():
            try:
                meta = json.loads(jp.read_text())
                arr = np.memmap(dp, dtype=">i2", mode="r",
                                shape=(meta["rows"], meta["cols"]))
                val = (arr, meta)
            except Exception as e:
                log.warning(f"SVS: mosaic L{level} unreadable: {e}")
        with self._lock:
            self._mosaic[level] = val
        return val

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
        # GL-required: the legacy tier names (cpu_sparse/dense/ultra,
        # polar) are accepted for config compatibility but ignored.
        _renderer_cfg = config.get("renderer", "opengl")
        if _renderer_cfg != "opengl":
            log.warning(
                "SVS: renderer '%s' is deprecated — the SVS is "
                "GL-required and the key is ignored", _renderer_cfg)
        self.renderer     = "opengl"
        # range_nm cap. Default 50 NM matches the GL heightmap patch
        # (2 deg = ~120 NM wide at mid-latitudes; 50 NM cap leaves
        # comfortable margin against patch-edge sampling). The
        # previous 30 NM default was from the CPU era when polar
        # mesh density was the bottleneck.
        self.range_nm     = float(config.get("range_nm", 50))
        # Cap on the GL heightmap patch texture dimension. A 2x2-deg
        # patch of 1-arc-sec tiles is natively 7202 px — beyond the
        # Pi V3D's max texture size and 207 MB of R32F — so the patch
        # builder decimates by 2 to ~3601 px (~60 m effective, still
        # finer than SRTM3's 90 m). CPU elevation sampling always uses
        # full native resolution from disk.
        self.heightmap_max_px = int(config.get("heightmap_max_px", 4096))
        # Distance haze (P7): exponential fog toward a washed-out
        # horizon tone. Adds depth perception and hides far-field LOD.
        # Terrain and water fog fully; awareness symbology (obstacles,
        # runway surface, flags) at reduced strength; markings and
        # text not at all.
        self.haze = bool(config.get("haze", True))
        self.haze_distance_nm = float(config.get("haze_distance_nm", 40.0))
        # Depth-perception aids (after KRIL flight feedback):
        # safe_gradient blends the SAFE band by clearance — terrain
        # approaching the green threshold warms toward olive/tan, so
        # rising ground visibly ramps long before it trips amber.
        # terrain_texture is the amplitude of a world-anchored
        # procedural noise modulation, strong near and faded by ~4 NM
        # — restores the texture gradient / optic flow the eye uses
        # to read slope and closure (0 disables).
        self.safe_gradient = bool(config.get("safe_gradient", True))
        self.terrain_texture = float(config.get("terrain_texture", 0.35))
        # World-anchored surface grid (NASA-SVS style fishnet), 300 m
        # cells draped on the terrain and gaussian-faded by ~2 NM.
        # Unlike the deleted mesh wireframe (camera-relative), this is
        # glued to the GROUND: cells foreshorten on rising slopes and
        # stream past with motion — the strongest foreground slope /
        # closure cue available. Value = darkening amplitude, 0 = off.
        self.terrain_grid = float(config.get("terrain_grid", 0.35))
        tile_path         = config.get("tile_path", "")
        self.cache        = TileCache(Path(tile_path)) if tile_path else None

        # Optional airport / runway database. NASR gives full
        # CONUS coverage with widths/markings/displaced thresholds for
        # Tier C rendering, CIFP gives coarser nationwide coverage.
        from pyefis.instruments.ai.airport_db import make_airport_db
        self.airport_db = make_airport_db(config)
        # Within this distance, runways render with painted surface markings
        # (FAA AC 150/5340-1L). Beyond it, the symbol-style grey rectangle.
        self.detail_distance_nm = float(config.get("detail_distance_nm", 3.0))
        # When the aircraft is within this distance of ANY airport in the
        # database, terrain colouring collapses to a 2-colour scheme:
        # SAFE (green) for terrain below the aircraft, CONFLICT (magenta)
        # for terrain above. The 500/1000 ft warning/caution bands are
        # suppressed — they would otherwise paint the whole pattern area
        # red on a normal landing approach. Set to 0 to disable.
        self.airport_proximity_nm = float(config.get("airport_proximity_nm", 5.0))
        # Issue #32 Option B: the proximity collapse only applies to
        # terrain within this height above the nearest airport's field
        # elevation (the runway environment). Terrain rising above the
        # gate keeps its full red/amber clearance bands even inside
        # the proximity radius — a hillside a mile past the runway
        # must never render benign green.
        self.airport_gate_agl_ft = float(
            config.get("airport_gate_agl_ft", 400.0))

        # Optional FAA DOF obstacle database. Renders towers, antennas,
        # tall buildings as vertical poles. ``obstacle_min_agl_ft`` filters
        # the ~636k nationwide records down to charted obstacles worth
        # showing (default 200 ft, matching the FAA charting threshold).
        from pyefis.instruments.ai.obstacle_db import ObstacleDB
        self.obstacle_db = ObstacleDB(config.get("dof_db_path", "") or None)
        self.obstacle_min_agl_ft = float(config.get("obstacle_min_agl_ft", 200.0))

        # Optional water-polygon database (oceans + lakes + rivers as
        # OSM / Natural Earth vector polygons). When configured, water
        # bodies are painted on top of the terrain layer with the
        # standard COLOR_WATER blue, fixing the "sea-level cells look
        # like SAFE-green terrain" problem the SRTM-only path leaves
        # at coastlines and over lakes.
        from pyefis.instruments.ai.water_db import WaterDB
        # water_max_vertices caps the per-polygon vertex count at load
        # time. OSM coastline polygons can carry thousands of vertices
        # at 30 m spacing — finer detail than the cockpit display can
        # resolve at typical SVS ranges, and a real CPU bottleneck on
        # the Python projection loop. None = use WaterDB's default.
        self.water_db = WaterDB(
            config.get("water_db_path", "") or None,
            max_vertices=config.get("water_max_vertices"))
        # Major-highway polylines (issue #35) — OSM motorway/trunk
        # from tools/build_highway_db.py. Optional like everything.
        from pyefis.instruments.ai.highway_db import HighwayDB
        self.highway_db = HighwayDB(
            config.get("highway_db_path", "") or None)
        self.green_ft     = float(config.get("clearance_green_ft",  1000))
        self.yellow_ft    = float(config.get("clearance_yellow_ft",  500))
        # Terrain colour palette: copy the named band colours onto the instance
        # (default "clearance" == the stock COLOR_* constants -> no change).
        _pal = _PALETTES.get(str(config.get("palette", "clearance")).lower(),
                             _PALETTES["clearance"])
        (self.c_safe, self.c_caution, self.c_warning,
         self.c_conflict, self.c_water) = _pal
        self.terrain_fill  = config.get("terrain_fill", True)
        self.auto_range    = config.get("auto_range", True)
        self.min_range_nm  = float(config.get("min_range_nm", 8.0))

        # OpenGL tier state — see docs/svs_opengl_plan.md. The renderer
        # is lazy-constructed inside draw(), so we can probe Qt's OpenGL
        # context capability at a point where a QPainter is available
        # rather than at SVSRenderer init time.
        self._gl_renderer        = None
        self._gl_init_attempted  = False
        # Set on any GL init/draw failure: SVS is permanently disabled
        # for this process and the AI widget annunciates SVS UNAVAIL.
        self.gl_failed           = False
        # Draw-time GL failures get a few full re-init attempts before
        # the permanent UNAVAIL (a transient hiccup must not blank the
        # SVS for the rest of a flight); init failures stay one-shot.
        self._gl_draw_failures   = 0
        # True only while the SVS actually painted terrain this frame. The AI
        # reads it to drop its brown fallback ground (showing sky in the gap
        # above the synthetic terrain) ONLY when SVS is genuinely drawing — so
        # any failure/empty frame falls back to the brown attitude ground.
        self.drew_terrain        = False
        # Cached airport-proximity boolean (see near_airport()).
        self._near_airport_cache = None
        self._near_airport_cache_time = 0.0
        # Field elevation (ft) of the nearest in-proximity airport,
        # cached alongside the boolean; None when not near one.
        self._near_airport_elev_ft = None

        # Per-frame profiler. ``svs_perf_log: true`` in the SVS config
        # turns on a lightweight per-segment timing pass that prints a
        # summary line every couple of seconds. Off by default; zero
        # overhead when disabled.
        self._perf = _SVSPerfLog(
            enabled=bool(config.get("svs_perf_log", False)))
        if self._perf.enabled:
            log.info("SVS perf logging enabled")

        # Cached airport list — the airport_db query (+ runway dict
        # construction) was ~10 ms / frame at DFW with 15-20 airports
        # in range. At typical cruise/approach speeds the airport set
        # changes glacially, so refreshing this once a second is plenty.
        # The cache key is wall-clock; we don't bother invalidating on
        # position change because the range query naturally covers a
        # 60 NM (range_nm * 2) box and we don't move that fast.
        self._airports_cache = None
        self._airports_cache_time = 0.0
        # Cached water-vertex triangle array for the GPU overlay path.
        # The polygons in range don't change per-frame (at 100 kt the
        # aircraft moves 50 m / s — the visible water-polygon set
        # turns over on the order of seconds, not frames), so we keep
        # the float32 vertex array from one collection valid for ~1 s.
        # Per-frame cost drops from a 13 ms sqlite-walk + triangle-
        # expansion to a cheap timestamp compare.
        self._water_tris_cache = None
        self._water_tris_cache_time = 0.0
        self._water_tris_cache_key = None  # rounded (lat, lon, range_nm)
        # Async water collection (first piece of plan P8 Track 2):
        # the sqlite walk + triangle expansion for a large water set
        # costs tens of ms — far over the frame budget — so it runs
        # on a worker thread and the render thread keeps drawing the
        # previous array until the new one swaps in.
        self._water_worker = None
        self._water_worker_lock = threading.Lock()
        self._water_result = None          # (key, array) from worker
        # Async highway collection — same worker pattern as water.
        self._hwy_cache = None
        self._hwy_cache_key = None
        self._hwy_cache_time = 0.0
        self._hwy_worker = None
        self._hwy_worker_lock = threading.Lock()
        self._hwy_result = None
        # Shared "one collector refreshes at a time" slot (issue #74).
        # The water, highway, and obstacle workers used to fire together
        # when a position key rolled over, stacking their GIL-held Python
        # bursts into a single render-stalling spike on a low-level
        # approach (~42% of samples combined). A collector claims this
        # non-blocking before spawning; if another holds it the collector
        # serves its stale cache this round and tries again next frame, so
        # at most one worker's burst (~14%) overlaps the render thread.
        self._collect_slot = threading.Lock()
        # Generic async cache slots (airports, obstacles, ...).
        self._async_state = {}
        # Obstacle pole vertex cache (Phase 2). Same TTL strategy as
        # water; key includes altitude bucket because the
        # conflict-vs-lit grouping depends on aircraft altitude.
        self._obstacles_cache = None
        self._obstacles_cache_time = 0.0
        self._obstacles_cache_key = None
        # Runway-polygon triangle cache (Phase 3). Same TTL/key
        # strategy as water — polygon vertex data is aircraft-
        # position-agnostic at the world-space level.
        self._runway_polys_cache = None
        self._runway_polys_cache_time = 0.0
        self._runway_polys_cache_key = None
        # Runway-marking triangle cache (Phase 4a). All the non-text
        # markings (threshold bars, aiming point, TDZ, centerline,
        # side stripes, chevrons) batched into one white triangle
        # list per frame. Designator text stays CPU until Phase 4b.
        self._runway_markings_cache = None
        self._runway_markings_cache_time = 0.0
        self._runway_markings_cache_key = None
        # Airport-flag vertex cache (Phase 5). Key includes ppd
        # because the billboard sizing depends on it.
        self._flags_cache = None
        self._flags_cache_time = 0.0
        self._flags_cache_key = None

        # Earth-curvature drop (d^2 / 2R) applied to projected
        # geometry in the GL shaders. At the 50 NM horizon range the
        # drop is ~2,100 ft — without it distant ridges render too
        # high and the horizon never dips. Config-gated for A/B.
        self.earth_curvature = bool(config.get("earth_curvature", True))

        # Clipmap terrain (P8 Track 1a): nested world-snapped grid
        # levels. cells = grid resolution per level; levels doubles
        # the spacing each ring out. Defaults cover ~120 km at the
        # outermost level with the inner level at heightmap-texel
        # spacing.
        self._clip_cells  = int(config.get("clipmap_cells", 64))
        self._clip_levels = int(config.get("clipmap_levels", 7))
        # Legacy polar-fan parameters — accepted and retained for
        # config compatibility (the Pi config sets n_range), no
        # longer consulted by the renderer.
        # Polar mesh parameters for the GL terrain fan.
        self._n_range      = int(config.get("n_range",
                                            POLAR_DEFAULTS["n_range"]))
        self._n_az         = int(config.get("n_az",
                                            POLAR_DEFAULTS["n_az"]))
        self._fov_deg      = float(config.get("fov_deg",
                                              POLAR_DEFAULTS["fov_deg"]))
        self._radial_warp  = float(config.get("radial_warp",
                                              POLAR_DEFAULTS["radial_warp"]))
        self._r_min_nm     = float(config.get("r_min_nm",
                                              POLAR_DEFAULTS["r_min_nm"]))

    @property
    def ready(self) -> bool:
        return self.enabled and self.cache is not None and self.cache.tile_root.is_dir()

    def _auto_range_nm(self, ac_lat: float, ac_lon: float,
                       ac_alt_ft: float) -> float:
        """Compute the effective rendered range in NM, scaling down from
        ``range_nm`` based on AGL and MSL when ``auto_range`` is on.
        Shared by the polar/CPU rasterisation path and the GL overlay
        path so both honour the same auto-scale rule."""
        _agl_elev, _ = self._sample_elevations(
            np.array([[ac_lat]]), np.array([[ac_lon]]))
        ac_ground_m = float(_agl_elev[0, 0])
        agl_ft = ac_alt_ft - ac_ground_m * 3.28084
        if self.auto_range:
            # Distance to the visual horizon in NM. For an observer
            # at altitude h above a sphere of radius R, the horizon
            # is at d ~= 1.22 * sqrt(h_ft) NM. Render up to that
            # distance so the polar mesh + water polygons + airport
            # markers extend all the way to where they'd actually be
            # visible from the cockpit. Previously this was 0.1 *
            # sqrt(h) — that was tuned for the CPU rendering era
            # when each polar quad was Python work; with the GPU
            # path the extra reach is essentially free.
            horizon_range = 1.22 * math.sqrt(max(0.0, agl_ft))
            return min(self.range_nm,
                       max(self.min_range_nm, horizon_range))
        return self.range_nm

    def _clearance_color(self, clearance_ft: float) -> QColor:
        # Use the selected palette's band colours; fall back to the module
        # constants if set_svs_config has not run (palette unset == stock).
        if clearance_ft < 0:
            return getattr(self, "c_conflict", COLOR_CONFLICT)
        elif clearance_ft < self.yellow_ft:
            return getattr(self, "c_warning", COLOR_WARNING)
        elif clearance_ft < self.green_ft:
            return getattr(self, "c_caution", COLOR_CAUTION)
        return getattr(self, "c_safe", COLOR_SAFE)

    def draw(self, p: QPainter, w: int, h: int,
             ac_lat: float, ac_lon: float, ac_alt_ft: float,
             pitch_deg: float, roll_deg: float, heading_deg: float,
             pixels_per_deg: float, device_pixel_ratio: float = 1.0):
        """
        Draw the SVS terrain overlay onto the AI viewport.

        Called from AI.paintEvent() when SVS is enabled and data is ready.
        The painter p has NO active transform — SVS builds its own.
        """
        # Reset every frame; set True only once terrain is actually painted
        # (below). Every early return / failure path leaves it False, so the
        # AI keeps its brown fallback ground as the fail-safe.
        self.drew_terrain = False
        # Wall-clock gap between consecutive SVS.draw calls. If the
        # SVS internals add up to (say) 65 ms but the gap is 500 ms,
        # the missing ~435 ms is happening OUTSIDE SVS — Qt repaint
        # loop, other instruments on the screen, FPM/pitch ladder
        # paint passes, etc. Crucial signal when chasing perf.
        now_ns = time.perf_counter_ns()
        last = getattr(self, "_perf_last_draw_ns", 0)
        if last and self._perf.enabled:
            self._perf.add_ns("frame.gap_between_svs", now_ns - last)
        self._perf_last_draw_ns = now_ns
        # Start the SVS-internal work timer. The quality controller
        # uses this rather than the gap above — if Qt isn't repainting
        # because nothing else changed on screen, we still want to
        # paint at L0 instead of pinning at L3 for no reason. SVS
        # internal time is what the controller can actually push on.
        svs_t0_ns = now_ns
        if not self.ready or self.gl_failed:
            return

        # ------------------------------------------------------------------
        # GL-required dispatch. Lazy-init the GL renderer on first draw —
        # the earliest point a Qt OpenGL context can be created. Any
        # failure (init or draw) permanently disables the SVS for this
        # process; the AI widget annunciates SVS UNAVAIL. No CPU
        # fallback exists (docs/svs_structural_plan.md P2).
        # ------------------------------------------------------------------
        if self._gl_renderer is None:
            if self._gl_init_attempted:
                self.gl_failed = True
                return
            self._gl_init_attempted = True
            try:
                from pyefis.instruments.ai.svs_gl import SVSGLRenderer
                self._gl_renderer = SVSGLRenderer(self)
            except Exception as e:
                log.warning(
                    "SVS: OpenGL renderer unavailable (%s) — SVS is "
                    "GL-required; disabling (SVS UNAVAIL)", e)
                self.gl_failed = True
                return
        try:
            with self._perf.time("auto_range"):
                range_nm = self._auto_range_nm(ac_lat, ac_lon, ac_alt_ft)
            with self._perf.time("gl_terrain"):
                self._gl_renderer.draw(
                    p, w, h, ac_lat, ac_lon, ac_alt_ft,
                    pitch_deg, roll_deg, heading_deg,
                    pixels_per_deg, range_nm, device_pixel_ratio)
            # Terrain painted successfully — the AI may now show sky (not brown)
            # above the synthetic terrain.
            self.drew_terrain = True
        except Exception:
            import traceback
            tb = traceback.format_exc()
            self._gl_draw_failures += 1
            # Breadcrumb for post-flight diagnosis — production logging
            # is not reliably captured, and the exception detail is the
            # whole ballgame for a mid-air failure.
            try:
                with open("/tmp/svs_gl_failure.log", "a") as f:
                    f.write("=== draw failure %d at %s ===%s%s%s"
                            % (self._gl_draw_failures, time.ctime(),
                               "\n", tb, "\n"))
            except OSError:
                pass
            self._gl_renderer = None
            if self._gl_draw_failures >= 3:
                log.warning(
                    "SVS: OpenGL draw failed %d times — disabling "
                    "(SVS UNAVAIL). Last error: %s",
                    self._gl_draw_failures, tb)
                self.gl_failed = True
            else:
                log.warning(
                    "SVS: OpenGL draw failed (attempt %d/3), will "
                    "re-initialise: %s", self._gl_draw_failures, tb)
                self._gl_init_attempted = False
            return
        svs_dt_ns = time.perf_counter_ns() - svs_t0_ns
        if self._perf.enabled:
            self._perf.add_ns("frame.svs_total", svs_dt_ns)
        self._perf.maybe_report()

    # Number of segments along each long runway edge. The angular
    # angular projection of the GL era produced a CURVE on screen from a
    # straight 3D line — a runway edge offset perpendicular from the
    # centerline traces a hyperbolic-ish arc, mild in the far field
    # and sharper near the camera. The runway polygon was drawn from
    # just four corners (a chord through that curve), which read
    # visibly different from the markings (each independently
    # projected and naturally following the curve). Subdividing every
    # 1/_RUNWAY_LONG_EDGE_SEGMENTS of the runway length gives the
    # polygon roughly the same shape as the markings cluster.
    _RUNWAY_LONG_EDGE_SEGMENTS = 16

    # Cache TTL/key strategy for the runway-polygon triangle buffer.
    _RUNWAY_POLYS_CACHE_TTL_S = 1.0
    _RUNWAY_POLYS_CACHE_POS_STEP_DEG = 0.01

    def _collect_runway_polygons(self, ac_lat, ac_lon, ac_alt_ft, range_nm,
                                 heading_deg=None):
        """Assemble every visible runway's polygon as a flat triangle
        list ready for GL upload. Returns a single Nx3 float32 array
        of (lat, lon, elev_ft) vertices — three per triangle, fan-
        triangulated from the polygon's first corner. Returns None
        when no runways are visible.

        Each runway picks its long-edge subdivision count the same
        way the CPU path did (1 / 5 NM thresholds). The cache key
        is the coarsened aircraft position + range_nm; the airports
        cache already throttles the per-frame DB hit so this cache
        layer just amortises the corner / triangulate work."""
        if (getattr(self, "airport_db", None) is None
                or not self.airport_db.ready):
            return None

        now = time.perf_counter()
        step = max(0.01, range_nm / 2000.0)
        key = (round(ac_lat / step) * step,
               round(ac_lon / step) * step,
               round(range_nm / 5.0) * 5.0)
        lat_cos = math.cos(math.radians(ac_lat))

        if (self._runway_polys_cache is not None
                and self._runway_polys_cache_key == key):
            return self._runway_polys_cache
        range_m = self.range_nm * 1852.0
        airports = self._get_airports_cached(ac_lat, ac_lon)
        all_tris = []
        for label, ref_lat, ref_lon, ref_elev_ft, runways in airports:
            d_lat_ref = ref_lat - ac_lat
            d_lon_ref = (ref_lon - ac_lon) * lat_cos
            if (math.sqrt(d_lat_ref ** 2 + d_lon_ref ** 2)
                    * 111139.0 > range_m):
                continue
            for rwy in runways:
                t1_lat, t1_lon = rwy["thr1_lat"], rwy["thr1_lon"]
                t2_lat, t2_lon = rwy["thr2_lat"], rwy["thr2_lon"]
                t1_elev = rwy["thr1_elev_ft"]
                t2_elev = rwy["thr2_elev_ft"]
                dl = t2_lat - t1_lat
                dm = (t2_lon - t1_lon) * lat_cos
                rwy_len = math.sqrt(dl ** 2 + dm ** 2)
                if rwy_len < 1e-9:
                    continue
                perp_lat = -dm / rwy_len
                perp_lon =  dl / rwy_len / lat_cos
                hw = (rwy["width_ft"] / 2.0) / 364491.0

                d_lat_r = (0.5 * (t1_lat + t2_lat) - ac_lat)
                d_lon_r = (0.5 * (t1_lon + t2_lon) - ac_lon) * lat_cos
                rwy_dist_nm = math.sqrt(
                    d_lat_r * d_lat_r + d_lon_r * d_lon_r) * 60.0
                if rwy_dist_nm <= 1.0:
                    n_subdiv = self._RUNWAY_LONG_EDGE_SEGMENTS
                elif rwy_dist_nm <= 5.0:
                    n_subdiv = 8
                else:
                    n_subdiv = 4

                # Strip-triangulate between the two long edges. Each
                # emitted triangle is bounded by one along-segment
                # in size — fan triangulation from one corner gave
                # us some triangles that span the full runway
                # length, which under our atan2 projection produced
                # the "grey extending outside the runway" and
                # "green through the middle" artifacts the user
                # reported. Strip keeps each triangle small so the
                # behind-camera filter culls only the ones that
                # actually straddle the near plane, not whole
                # sections of the polygon.
                left_pts  = []
                right_pts = []
                for k in range(n_subdiv + 1):
                    f = k / n_subdiv
                    base_lat = t1_lat + f * (t2_lat - t1_lat)
                    base_lon = t1_lon + f * (t2_lon - t1_lon)
                    base_elev = t1_elev + f * (t2_elev - t1_elev)
                    right_pts.append((
                        base_lat + perp_lat * hw,
                        base_lon + perp_lon * hw,
                        base_elev))
                    left_pts.append((
                        base_lat - perp_lat * hw,
                        base_lon - perp_lon * hw,
                        base_elev))
                tris = []
                for k in range(n_subdiv):
                    L0 = left_pts[k]
                    R0 = right_pts[k]
                    L1 = left_pts[k + 1]
                    R1 = right_pts[k + 1]
                    tris.extend((R0, L0, L1, R0, L1, R1))
                all_tris.append(
                    np.asarray(tris, dtype=np.float32))

        if not all_tris:
            result = None
        else:
            result = np.concatenate(all_tris, axis=0)
        self._runway_polys_cache = result
        self._runway_polys_cache_key = key
        self._runway_polys_cache_time = now
        return result

    # ------------------------------------------------------------------
    # Phase 4a: non-text runway markings (threshold bars, aiming point,
    # TDZ markers, centerline stripes, side stripes, displaced-
    # threshold chevrons). All emit white triangles in world space.
    # Designator text continues to render via QPainter until Phase 4b
    # adds the bitmap-font atlas.
    # ------------------------------------------------------------------
    _RUNWAY_MARKINGS_CACHE_TTL_S = 1.0
    _RUNWAY_MARKINGS_CACHE_POS_STEP_DEG = 0.01

    def _emit_runway_marking_quads(self, rwy, rwy_dist_nm, out):
        """Append world-space triangle vertices for every non-text
        marking on ``rwy`` into ``out`` (a list that grows with
        ``(lat, lon, elev_ft)`` tuples — 6 per quad). Mirrors the
        layout decisions of ``_draw_runway_markings`` exactly so the
        GPU output matches the CPU rendering. Designator text is NOT
        emitted; that stays on the CPU path until Phase 4b."""
        t1_lat, t1_lon = rwy["thr1_lat"], rwy["thr1_lon"]
        t2_lat, t2_lon = rwy["thr2_lat"], rwy["thr2_lon"]
        t1_elev = rwy["thr1_elev_ft"]
        t2_elev = rwy["thr2_elev_ft"]
        length_ft = float(rwy.get("length_ft") or 0.0)
        width_ft  = float(rwy.get("width_ft")  or 100.0)
        d1 = float(rwy.get("thr1_displaced_ft") or 0.0)
        d2 = float(rwy.get("thr2_displaced_ft") or 0.0)
        m1 = (rwy.get("thr1_marking") or "").upper()
        m2 = (rwy.get("thr2_marking") or "").upper()

        lat_cos = math.cos(math.radians(t1_lat))
        d_lat = (t2_lat - t1_lat)
        d_lon = (t2_lon - t1_lon) * lat_cos
        rwy_deg_len = math.sqrt(d_lat * d_lat + d_lon * d_lon)
        if rwy_deg_len < 1e-9:
            return
        if length_ft <= 0:
            length_ft = rwy_deg_len * 364491.0

        perp_lat = -d_lon / rwy_deg_len
        perp_lon =  d_lat / rwy_deg_len / lat_cos
        ft_per_deg_lat = 364491.0

        def rwy_point(along_ft, across_ft, height_ft=0.0):
            f = max(0.0, min(1.0, along_ft / length_ft))
            clat = t1_lat + f * (t2_lat - t1_lat)
            clon = t1_lon + f * (t2_lon - t1_lon)
            celev = t1_elev + f * (t2_elev - t1_elev)
            across_deg = across_ft / ft_per_deg_lat
            return (clat + perp_lat * across_deg,
                    clon + perp_lon * across_deg,
                    celev + height_ft)

        def quad(a0, c0, a1, c1, a2, c2, a3, c3, height_ft=0.0):
            p0 = rwy_point(a0, c0, height_ft)
            p1 = rwy_point(a1, c1, height_ft)
            p2 = rwy_point(a2, c2, height_ft)
            p3 = rwy_point(a3, c3, height_ft)
            out.extend((p0, p1, p2, p0, p2, p3))

        def tri(a0, c0, a1, c1, a2, c2, height_ft=0.0):
            p0 = rwy_point(a0, c0, height_ft)
            p1 = rwy_point(a1, c1, height_ft)
            p2 = rwy_point(a2, c2, height_ft)
            out.extend((p0, p1, p2))

        # _interior_detail used to gate the per-pixel-detail markings
        # (aiming point, TDZ, centerline) past 1.5 NM because the CPU
        # path couldn't afford the QPainter polygon fills at that
        # distance. The GPU path doesn't care — emit them at the full
        # detail_distance_nm range. Leaving the variable here as
        # always-True so the downstream branch reads naturally.
        _interior_detail = True

        for thr_along, sign, marking, displaced in (
                (d1,                  +1, m1, d1),
                (length_ft - d2,      -1, m2, d2)):
            usable_remaining = (length_ft - d1 - d2)
            if usable_remaining < 100.0:
                continue

            # Threshold bars (PIR / NPI)
            if marking in ("PIR", "NPI"):
                n_stripes = max(4, min(16, int(round(width_ft / 12.5))))
                stripe_w_ft = 5.75
                bar_len_ft  = 150.0
                span = 0.45 * width_ft * 2.0
                step = span / max(n_stripes, 1)
                first = -span / 2.0 + step / 2.0
                bar_a0 = thr_along
                bar_a1 = thr_along + sign * bar_len_ft
                for k in range(n_stripes):
                    c = first + k * step
                    quad(bar_a0, c - stripe_w_ft / 2,
                         bar_a0, c + stripe_w_ft / 2,
                         bar_a1, c + stripe_w_ft / 2,
                         bar_a1, c - stripe_w_ft / 2)

            # Aiming point (PIR / NPI). The standard 36 ft offset is
            # for wide runways; on narrow ones (e.g. 100 ft) the outer
            # edge would hang past the pavement — pull the pair inboard
            # so it clears the side stripes, or skip when there is no
            # room between centerline and edge.
            if (_interior_detail and marking in ("PIR", "NPI")
                    and usable_remaining > 2400.0):
                aim_a0 = thr_along + sign * 1000.0
                aim_a1 = aim_a0 + sign * 150.0
                aim_c = min(36.0, width_ft * 0.5 - 5.0 - 15.0)
                if aim_c >= 20.0:
                    for c_center in (-aim_c, +aim_c):
                        quad(aim_a0, c_center - 15.0,
                             aim_a0, c_center + 15.0,
                             aim_a1, c_center + 15.0,
                             aim_a1, c_center - 15.0)

            # TDZ markers (PIR only)
            if (_interior_detail and marking == "PIR"
                    and usable_remaining > 3000.0):
                STRIPE_LEN = 75.0
                STRIPE_W   = 6.0
                STRIPE_GAP = 5.0
                centerline_offset = 36.0
                # Drop any stripe whose outer edge would hang past
                # the pavement (narrow runways: a 100 ft PIR runway
                # only has room for one stripe per side at the 36 ft
                # offset; the FAA spec reduces the pattern on narrow
                # runways the same way). Keep 5 ft clear of the edge
                # so TDZ never touches the side stripes.
                max_c = width_ft * 0.5 - 5.0
                for dist_ft, n_stripes in ((500.0, 3), (1500.0, 2),
                                           (2500.0, 1)):
                    if dist_ft + STRIPE_LEN > usable_remaining:
                        continue
                    a0 = thr_along + sign * dist_ft
                    a1 = a0 + sign * STRIPE_LEN
                    for side in (-1.0, +1.0):
                        for k in range(n_stripes):
                            c_inner = side * (
                                centerline_offset
                                + k * (STRIPE_W + STRIPE_GAP))
                            c_outer = c_inner + side * STRIPE_W
                            if abs(c_outer) > max_c:
                                continue
                            c_lo, c_hi = (min(c_inner, c_outer),
                                          max(c_inner, c_outer))
                            quad(a0, c_lo, a0, c_hi,
                                 a1, c_hi, a1, c_lo)

            # Displaced-threshold chevrons (triangles, not quads).
            if displaced > 50.0:
                if sign > 0:
                    chev_start, chev_end = 0.0, displaced
                else:
                    chev_start, chev_end = length_ft - displaced, length_ft
                CHEV_LEN = 90.0
                CHEV_HW  = 20.0
                pos = (chev_start + 50.0 if sign > 0
                       else chev_end - 50.0)
                while ((sign > 0 and pos + CHEV_LEN < chev_end - 30.0)
                       or (sign < 0 and pos - CHEV_LEN >
                           chev_start + 30.0)):
                    tip_a  = pos + sign * CHEV_LEN
                    base_a = pos
                    tri(base_a, -CHEV_HW, tip_a, 0.0, base_a, +CHEV_HW)
                    pos += sign * 200.0

        # Side stripes (PIR only) — full usable length, subdivided.
        # Strip-triangulated (not fan-triangulated) so every emitted
        # triangle is bounded by one stripe-segment in size. A fan
        # from one corner of a 10000 ft × 3 ft rectangle produces
        # very long triangles, and when the camera is close to the
        # runway some of those triangles straddle the near plane —
        # which under our atan2-based projection paints big wedge
        # artifacts across the lower viewport.
        usable_a0 = d1
        usable_a1 = length_ft - d2
        if "PIR" in (m1, m2) and usable_a1 - usable_a0 > 200.0:
            STRIPE_W = 3.0
            if rwy_dist_nm is None or rwy_dist_nm <= 0.5:
                n_sub = self._RUNWAY_LONG_EDGE_SEGMENTS
            elif rwy_dist_nm <= 1.5:
                n_sub = 8
            else:
                n_sub = 4
            for side in (-1.0, +1.0):
                c_in  = side * (width_ft * 0.5 - STRIPE_W)
                c_out = side * (width_ft * 0.5)
                c_lo, c_hi = min(c_in, c_out), max(c_in, c_out)
                # Build the two long edges as separate vertex lists,
                # then strip-triangulate between them.
                along = [usable_a0 + (k / n_sub) * (usable_a1 - usable_a0)
                         for k in range(n_sub + 1)]
                lo_verts = [rwy_point(a, c_lo) for a in along]
                hi_verts = [rwy_point(a, c_hi) for a in along]
                for k in range(n_sub):
                    p_lo_k  = lo_verts[k]
                    p_hi_k  = hi_verts[k]
                    p_lo_k1 = lo_verts[k + 1]
                    p_hi_k1 = hi_verts[k + 1]
                    out.extend((
                        p_lo_k, p_hi_k,  p_hi_k1,
                        p_lo_k, p_hi_k1, p_lo_k1,
                    ))

        # Centerline stripes (always, LOD-gated). Real centerlines
        # begin beyond the runway numbers: the designator block is
        # anchored 380 ft from the usable threshold and spans to
        # ~450 ft in the two-row (parallel-runway letter) layout, so
        # any end carrying a designator pushes the centerline start
        # to 500 ft. Unmarked-designator ends keep the old offsets.
        if _interior_detail:
            STRIPE_LEN = 120.0
            STRIPE_GAP = 80.0
            CL_WIDTH   = 3.0
            _des1 = (rwy.get("thr1_designator") or "").strip()
            _des2 = (rwy.get("thr2_designator") or "").strip()
            cl_a0 = usable_a0 + (500.0 if _des1 else
                                 (200.0 if m1 in ("PIR", "NPI") else 50.0))
            cl_a1 = usable_a1 - (500.0 if _des2 else
                                 (200.0 if m2 in ("PIR", "NPI") else 50.0))
            a = cl_a0
            while a + STRIPE_LEN < cl_a1:
                quad(a,              -CL_WIDTH / 2.0,
                     a,              +CL_WIDTH / 2.0,
                     a + STRIPE_LEN, +CL_WIDTH / 2.0,
                     a + STRIPE_LEN, -CL_WIDTH / 2.0)
                a += STRIPE_LEN + STRIPE_GAP

    def _collect_runway_markings(self, ac_lat, ac_lon, ac_alt_ft, range_nm,
                                 heading_deg):
        """Assemble every visible runway's non-text marking quads
        into one big triangle list. Uses the same close-runway gate
        and marking-budget logic as the CPU ``_draw_runways`` loop
        (Phase 3 left that in place), and respects the quality-
        controller's detail-distance + max-markings limits. Cached
        for 1 s keyed by coarsened aircraft position. Near-plane
        clipping is the GL pipeline's job (true perspective, P3).

        Returns ``None`` when no marking quads are emitted."""
        if (getattr(self, "airport_db", None) is None
                or not self.airport_db.ready):
            return None
        now = time.perf_counter()
        step = max(0.01, range_nm / 2000.0)
        key = (round(ac_lat / step) * step,
               round(ac_lon / step) * step,
               round(range_nm / 5.0) * 5.0,
               round(self.detail_distance_nm, 2))
        if (self._runway_markings_cache is not None
                and self._runway_markings_cache_key == key):
            return self._runway_markings_cache

        lat_cos = math.cos(math.radians(ac_lat))
        range_m = self.range_nm * 1852.0
        airports = self._get_airports_cached(ac_lat, ac_lon)
        # Render markings for EVERY runway within detail_distance_nm
        # (a few thousand extra triangles cost essentially nothing on
        # V3D). The distance gate stays because past ~3 NM the
        # markings are sub-pixel anyway.
        q_detail_distance_nm = self.detail_distance_nm

        out = []
        for label, ref_lat, ref_lon, ref_elev_ft, runways in airports:
            d_lat_ref = ref_lat - ac_lat
            d_lon_ref = (ref_lon - ac_lon) * lat_cos
            if (math.sqrt(d_lat_ref ** 2 + d_lon_ref ** 2)
                    * 111139.0 > range_m):
                continue
            for rwy in runways:
                t1_lat, t1_lon = rwy["thr1_lat"], rwy["thr1_lon"]
                t2_lat, t2_lon = rwy["thr2_lat"], rwy["thr2_lon"]
                d_lat_r = (0.5 * (t1_lat + t2_lat) - ac_lat)
                d_lon_r = (0.5 * (t1_lon + t2_lon) - ac_lon) * lat_cos
                rwy_dist_nm = math.sqrt(
                    d_lat_r * d_lat_r + d_lon_r * d_lon_r) * 60.0
                if rwy_dist_nm > q_detail_distance_nm:
                    continue
                self._emit_runway_marking_quads(rwy, rwy_dist_nm, out)

        result = (np.asarray(out, dtype=np.float32)
                  if out else None)
        self._runway_markings_cache = result
        self._runway_markings_cache_key = key
        self._runway_markings_cache_time = now
        return result

    # ------------------------------------------------------------------
    # Phase 4b: runway designator text. Per-glyph (lat, lon, elev_ft,
    # u, v) quads laid out in runway-local feet according to FAA
    # AC 150/5340-1L and bound to the glyph-atlas texture. The GL
    # perspective shader handles the foreshortening — no more
    # quadToQuad / K-strip CPU work.
    # ------------------------------------------------------------------

    # Per-character widths in feet (FAA AC 150/5340-1L). "1" gets a
    # plain vertical stroke; letters L/C/R are wider; everything else
    # at 20 ft.
    _DESIG_CHAR_H_FT   = 60.0
    _DESIG_CHAR_GAP_FT = 5.0
    _DESIG_ROW_GAP_FT  = 20.0
    _DESIG_STROKE_FT   = 5.33
    # Anchor distance from the usable threshold (inward along runway).
    # Same number the CPU path used so the on-runway position is
    # unchanged after migration.
    _DESIG_CENTER_OFFSET_FT = 380.0

    @classmethod
    def _designator_char_width_ft(cls, ch):
        if ch == '1':
            return cls._DESIG_STROKE_FT
        if ch in ('L', 'C', 'R'):
            return 24.0
        return 20.0

    def _collect_runway_designator_quads(self, ac_lat, ac_lon, ac_alt_ft,
                                         range_nm, heading_deg,
                                         atlas_uvs):
        """Emit textured quads for every visible runway designator.

        Returns an Nx5 float32 array of interleaved (lat, lon, elev_ft,
        u, v) vertices, 6 per character glyph (two triangles). Caller
        binds the text shader + glyph-atlas texture and issues one
        glDrawArrays(GL_TRIANGLES) on the whole buffer.

        Mirrors the layout decisions of the retired CPU
        ``_draw_runway_markings`` designator branch: each end of each
        runway gets a designator anchored 380 ft inward from the
        usable threshold; runways with a parallel-runway suffix
        letter (L/C/R) lay the number row "far" from the threshold
        and the letter row "near" (closer to the threshold).

        Honours the same detail_distance_nm gate as
        ``_collect_runway_markings``; past that distance the glyphs
        are sub-pixel and not worth the upload."""
        if (getattr(self, "airport_db", None) is None
                or not self.airport_db.ready):
            return None
        if not atlas_uvs:
            return None

        lat_cos = math.cos(math.radians(ac_lat))
        range_m = self.range_nm * 1852.0
        airports = self._get_airports_cached(ac_lat, ac_lon)
        q_detail_distance_nm = self.detail_distance_nm

        out = []
        for label, ref_lat, ref_lon, ref_elev_ft, runways in airports:
            d_lat_ref = ref_lat - ac_lat
            d_lon_ref = (ref_lon - ac_lon) * lat_cos
            if (math.sqrt(d_lat_ref ** 2 + d_lon_ref ** 2)
                    * 111139.0 > range_m):
                continue
            for rwy in runways:
                t1_lat, t1_lon = rwy["thr1_lat"], rwy["thr1_lon"]
                t2_lat, t2_lon = rwy["thr2_lat"], rwy["thr2_lon"]
                d_lat_r = (0.5 * (t1_lat + t2_lat) - ac_lat)
                d_lon_r = (0.5 * (t1_lon + t2_lon) - ac_lon) * lat_cos
                rwy_dist_nm = (math.sqrt(
                    d_lat_r * d_lat_r + d_lon_r * d_lon_r) * 60.0)
                if rwy_dist_nm > q_detail_distance_nm:
                    continue
                self._emit_runway_designator_quads(rwy, atlas_uvs, out)

        if not out:
            return None
        return np.asarray(out, dtype=np.float32)

    def _emit_runway_designator_quads(self, rwy, atlas_uvs, out):
        """Append per-glyph textured-quad vertices for both ends of
        ``rwy`` into ``out`` (a flat list of (lat, lon, elev_ft, u, v)
        tuples — 6 per glyph). Matches the FAA AC 150/5340-1L
        designator layout the CPU path implemented before Phase 4b."""
        t1_lat, t1_lon = rwy["thr1_lat"], rwy["thr1_lon"]
        t2_lat, t2_lon = rwy["thr2_lat"], rwy["thr2_lon"]
        t1_elev = rwy["thr1_elev_ft"]
        t2_elev = rwy["thr2_elev_ft"]
        length_ft = float(rwy.get("length_ft") or 0.0)
        d1 = float(rwy.get("thr1_displaced_ft") or 0.0)
        d2 = float(rwy.get("thr2_displaced_ft") or 0.0)
        des1 = (rwy.get("thr1_designator") or "").strip().upper()
        des2 = (rwy.get("thr2_designator") or "").strip().upper()

        lat_cos = math.cos(math.radians(t1_lat))
        d_lat = (t2_lat - t1_lat)
        d_lon = (t2_lon - t1_lon) * lat_cos
        rwy_deg_len = math.sqrt(d_lat * d_lat + d_lon * d_lon)
        if rwy_deg_len < 1e-9:
            return
        if length_ft <= 0:
            length_ft = rwy_deg_len * 364491.0

        perp_lat = -d_lon / rwy_deg_len
        perp_lon =  d_lat / rwy_deg_len / lat_cos
        ft_per_deg_lat = 364491.0

        def world_point(along_ft, across_ft):
            f = max(0.0, min(1.0, along_ft / length_ft))
            clat = t1_lat + f * (t2_lat - t1_lat)
            clon = t1_lon + f * (t2_lon - t1_lon)
            celev = t1_elev + f * (t2_elev - t1_elev)
            across_deg = across_ft / ft_per_deg_lat
            return (clat + perp_lat * across_deg,
                    clon + perp_lon * across_deg,
                    celev)

        CHAR_H = self._DESIG_CHAR_H_FT
        CHAR_GAP = self._DESIG_CHAR_GAP_FT
        ROW_GAP = self._DESIG_ROW_GAP_FT
        CENTER_OFF = self._DESIG_CENTER_OFFSET_FT

        def emit_row(chars, row_center_along, sign):
            if not chars:
                return
            widths = [self._designator_char_width_ft(c) for c in chars]
            total_w = sum(widths) + CHAR_GAP * max(0, len(chars) - 1)
            # Row spans 60 ft along the runway: top edge is "far" from
            # the threshold (+sign), bottom edge is "near" (-sign).
            top_a = row_center_along + sign * (CHAR_H / 2.0)
            bot_a = row_center_along - sign * (CHAR_H / 2.0)
            # Pilot's left edge of the row.
            cur_across = -sign * (total_w / 2.0)
            for ch, cw in zip(chars, widths):
                uv = atlas_uvs.get(ch)
                if uv is None:
                    cur_across += sign * (cw + CHAR_GAP)
                    continue
                u0, v0, u1, v1 = uv
                sL = cur_across
                sR = cur_across + sign * cw
                # World-space quad corners. UV box is oriented so that
                # v0 = TOP of the glyph in the atlas (because QImage's
                # y axis grows downward, matching atlas top→bottom).
                # In the world, "top" of the glyph corresponds to the
                # row's "top_a" (far from threshold). Pilot reads
                # bottom-up — so we map v0 -> top_a (far from thr),
                # v1 -> bot_a (near thr), u0 -> sL, u1 -> sR.
                p_tl = world_point(top_a, sL)
                p_tr = world_point(top_a, sR)
                p_br = world_point(bot_a, sR)
                p_bl = world_point(bot_a, sL)
                v_tl = (p_tl[0], p_tl[1], p_tl[2], u0, v0)
                v_tr = (p_tr[0], p_tr[1], p_tr[2], u1, v0)
                v_br = (p_br[0], p_br[1], p_br[2], u1, v1)
                v_bl = (p_bl[0], p_bl[1], p_bl[2], u0, v1)
                out.extend((v_tl, v_tr, v_br, v_tl, v_br, v_bl))
                cur_across += sign * (cw + CHAR_GAP)

        for thr_along, sign, designator in (
                (d1,             +1, des1),
                (length_ft - d2, -1, des2)):
            if not designator:
                continue
            usable_remaining = (length_ft - d1 - d2)
            if usable_remaining < 100.0:
                continue
            # Split into "numbers" row + optional parallel-runway letter.
            if designator[-1] in ('L', 'C', 'R'):
                number_part = designator[:-1]
                letter_part = designator[-1]
            else:
                number_part = designator
                letter_part = ""
            center_along = thr_along + sign * CENTER_OFF
            if letter_part:
                # Two-row layout. Numbers far from threshold (+sign),
                # letter near threshold (-sign).
                row_offset = (CHAR_H + ROW_GAP) / 2.0
                emit_row(number_part,
                         center_along + sign * row_offset, sign)
                emit_row(letter_part,
                         center_along - sign * row_offset, sign)
            else:
                emit_row(number_part, center_along, sign)

    # Cached snapshot expires after this many seconds. At 100 kt the
    # aircraft moves 0.028 NM/sec — well under the range_nm threshold
    # — so the airport set near the edge of range changes only every
    # few seconds. Re-querying the sqlite-backed airport_db every
    # frame was ~6-10 ms / frame at DFW; once per second is plenty.
    _AIRPORTS_CACHE_TTL_S = 1.0

    def _get_airports_cached(self, ac_lat, ac_lon):
        """Return the airport-list iteration result, refreshed at most
        once every ``_AIRPORTS_CACHE_TTL_S`` seconds. Returns a list
        (already materialised from the underlying generator) so it can
        be re-iterated across cached frames."""
        # Key-based (was 1 s TTL): the TTL made every collector with
        # the same epoch rebuild in the same frame once per second —
        # the metronome tick Bill heard at DFW. Position fully
        # determines the result; rebuild only on ~0.6 NM of movement.
        # Position step scales with range (jet speeds crossed the old
        # fixed 0.6 NM step every ~6 s, rebuilding 100 NM datasets
        # whose content had barely changed).
        step = max(0.01, self.range_nm / 2000.0)
        key = (round(ac_lat / step) * step, round(ac_lon / step) * step)
        return self._async_cache(
            "airports", key,
            lambda: list(self._airports_in_range(ac_lat, ac_lon))) or []

    def _async_cache(self, name, key, builder):
        """Generic key-based cache whose rebuilds run on a daemon
        worker: the render thread gets the previous value (or None on
        cold start) instead of paying the rebuild — at metro density
        the airports query + obstacle quad emission were tens of ms,
        landing as ticks whenever a position key rolled over."""
        st = self._async_state.setdefault(name, {
            "key": None, "val": None, "res": None,
            "worker": None, "lock": threading.Lock()})
        with st["lock"]:
            if st["res"] is not None:
                r_key, r_val = st["res"]
                st["res"] = None
                st["key"], st["val"] = r_key, r_val
            if st["key"] == key:
                return st["val"]
            if (st["worker"] is None or not st["worker"].is_alive()) \
                    and self._collect_slot.acquire(blocking=False):
                def run():
                    try:
                        v = builder()
                        with st["lock"]:
                            st["res"] = (key, v)
                    except Exception:
                        log.warning("%s worker failed", name,
                                    exc_info=True)
                    finally:
                        self._collect_slot.release()
                st["worker"] = threading.Thread(target=run, daemon=True)
                st["worker"].start()
            return st["val"]

    def _airports_in_range(self, ac_lat, ac_lon):
        """Yield ``(label, ref_lat, ref_lon, elev_ft, runways)`` records from
        whichever data source is configured. Each runway dict carries the
        threshold positions, width, and (for NASR) the Tier C fields:
        marking type, displaced threshold offset, designators, TDZ elev."""
        if getattr(self, "airport_db", None) is not None and self.airport_db.ready:
            for ap in self.airport_db.airports_in_range(
                    ac_lat, ac_lon, min(self.range_nm, 50.0)):
                # ICAO codes are 4 letters incl. leading K for CONUS. Strip
                # it so the cockpit label reads "SBA" rather than "KSBA".
                label = ap.icao[1:] if (len(ap.icao) == 4 and ap.icao[0] == 'K') else ap.icao
                runways = [{
                    "thr1_lat": r.thr1_lat, "thr1_lon": r.thr1_lon, "thr1_elev_ft": r.thr1_elev_ft,
                    "thr2_lat": r.thr2_lat, "thr2_lon": r.thr2_lon, "thr2_elev_ft": r.thr2_elev_ft,
                    "width_ft": r.width_ft,
                    "length_ft": r.length_ft,
                    "thr1_designator": r.thr1_designator,
                    "thr2_designator": r.thr2_designator,
                    "thr1_marking": r.thr1_marking,
                    "thr2_marking": r.thr2_marking,
                    "thr1_displaced_ft": r.thr1_displaced_ft,
                    "thr2_displaced_ft": r.thr2_displaced_ft,
                } for r in ap.runways]
                yield label, ap.ref_lat, ap.ref_lon, ap.elev_ft, runways

    # Cache TTL for the assembled water-triangle vertex array. Matches
    # the airports cache; the visible polygon set turns over slowly
    # enough that one refresh per second is plenty.
    _WATER_TRIS_CACHE_TTL_S = 1.0
    # Position-grid step in degrees that invalidates the cache early.
    # 0.01 deg ~ 0.6 NM — once the aircraft has moved more than that,
    # the polygon set near the visible-range edge could be stale and
    # we refresh regardless of TTL. Cheap defensive check; the actual
    # threshold for visible churn is closer to range_nm * 0.1.
    _WATER_TRIS_CACHE_POS_STEP_DEG = 0.01

    def _collect_water_triangles(self, ac_lat, ac_lon, range_nm):
        """Collect every visible water polygon, look up its surface
        elevation, and expand its pre-tessellated triangles into a
        single Nx3 float32 numpy array of (lat, lon, elev_ft) vertex
        coordinates ready for direct upload to the GPU overlay shader.
        Returns None when nothing is visible.

        The result is cached for ``_WATER_TRIS_CACHE_TTL_S`` seconds
        keyed by a coarsened aircraft position so repeat calls within
        the same frame and across consecutive frames return
        instantly. The vertex data itself is aircraft-position-
        independent — the GPU shader handles the projection — so as
        long as the visible polygon SET hasn't churned the cached
        array is valid.
        """
        if (getattr(self, "water_db", None) is None
                or not self.water_db.ready):
            return None

        now = time.perf_counter()
        step = max(0.01, range_nm / 2000.0)
        key = (round(ac_lat / step) * step,
               round(ac_lon / step) * step,
               round(range_nm / 5.0) * 5.0)
        # Purely key-based: the key encodes coarsened position and
        # range, which fully determine the result — a TTL on top only
        # forced an identical rebuild every second, and the worker's
        # GIL bursts stalled render frames (flight report: noticeable
        # pauses). Rebuilds now happen only on actual movement
        # (~0.6 NM) or range change.
        if (self._water_tris_cache is not None
                and self._water_tris_cache_key == key):
            return self._water_tris_cache

        # Promote a finished worker result, or kick the worker and
        # keep rendering the previous (slightly stale) water set —
        # never block the frame on the collect.
        with self._water_worker_lock:
            if self._water_result is not None:
                r_key, r_arr = self._water_result
                self._water_result = None
                self._water_tris_cache = r_arr
                self._water_tris_cache_key = r_key
                self._water_tris_cache_time = now
                if r_key == key:
                    return r_arr
            busy = (self._water_worker is not None
                    and self._water_worker.is_alive())
            if not busy and self._collect_slot.acquire(blocking=False):
                self._water_worker = threading.Thread(
                    target=self._water_collect_worker,
                    args=(key, ac_lat, ac_lon, range_nm),
                    daemon=True)
                self._water_worker.start()
        return self._water_tris_cache

    def _water_collect_worker(self, key, ac_lat, ac_lon, range_nm):
        try:
            arr = self._collect_water_sync(ac_lat, ac_lon, range_nm)
            with self._water_worker_lock:
                self._water_result = (key, arr)
        except Exception:
            log.warning("water collect worker failed", exc_info=True)
        finally:
            self._collect_slot.release()

    def _collect_water_sync(self, ac_lat, ac_lon, range_nm):

        # Sentinel mapped to sea level. Same convention the previous
        # CPU path used.
        WATER_SENTINEL_M = _WATER_SENTINEL / 3.28084

        # Distance-adaptive size filter — sub-pixel polygons get
        # rejected at SQL level before BLOB decode. K=50 keeps the
        # angular size of the smallest rendered polygon roughly
        # constant across the auto-range band; see the tuning table
        # in the Phase 1 commit.
        # Clamp the scaling so climbing never culls river-sized
        # polygons: auto-range grows with altitude, and an unclamped
        # filter deleted rivers around pattern altitude (flight
        # report 2026-06-12 — a river visibly vanished in the climb).
        # The K=50 scaling was a CPU-era collect-cost guard; with the
        # GPU pipeline the only cost is a slightly larger 1 Hz
        # collect, well inside budget.
        # Water collection capped at 100 NM (the only layer that was
        # uncapped — at the FL300 215 NM range its rebuild area grew
        # 18x and kept the workers hot).
        range_nm = min(range_nm, 100.0)
        min_diag_m = 50.0 * min(range_nm, 12.0)
        min_diag_deg = min_diag_m / 111139.0
        with self._perf.time("water.query"):
            polys = [pp for pp in self.water_db.polygons_in_range(
                ac_lat, ac_lon, range_nm,
                min_bbox_diag_deg=min_diag_deg)
                if len(pp.vertices) >= 3]
        if not polys:
            return None

        # Batched SRTM lookup for inland polygons that don't carry a
        # known surface elevation. Sample point per polygon: vertex 0.
        needs_sample_idx = []
        sample_lats = []
        sample_lons = []
        for i, poly in enumerate(polys):
            if poly.is_ocean or poly.elev_ft is not None:
                continue
            needs_sample_idx.append(i)
            vlat, vlon = poly.vertices[0]
            sample_lats.append(vlat)
            sample_lons.append(vlon)
        sampled_ft = {}
        if needs_sample_idx:
            with self._perf.time("water.srtm_sample"):
                arr_lat = np.asarray(sample_lats,
                                     dtype=np.float64)[:, None]
                arr_lon = np.asarray(sample_lons,
                                     dtype=np.float64)[:, None]
                elev_m_arr, _ = self._sample_elevations(arr_lat, arr_lon)
            elev_m_flat = elev_m_arr[:, 0]
            for k, i in enumerate(needs_sample_idx):
                e = float(elev_m_flat[k])
                if e <= WATER_SENTINEL_M / 2.0:
                    sampled_ft[i] = 0.0
                else:
                    sampled_ft[i] = e * 3.28084

        # Expand each polygon's pre-tessellated triangle index list
        # into raw vertex coordinates. The GL path uses glDrawArrays
        # with non-indexed triangles — simpler than maintaining a
        # separate index buffer, and total vertex volume is small
        # (200 polygons * ~30 triangles * 3 verts * 12 bytes = 216 KB
        # at worst). All per-polygon work is vectorised — no Python
        # loop over individual triangles — so the cost is bounded by
        # the per-polygon numpy overhead, ~50 us per polygon.
        all_tris = []
        for i, poly in enumerate(polys):
            if poly.is_ocean:
                surface_ft = 0.0
            elif poly.elev_ft is not None:
                surface_ft = float(poly.elev_ft)
            else:
                surface_ft = sampled_ft.get(i, 0.0)

            n_v = len(poly.vertices)
            tri_idx = poly.triangles
            if tri_idx is None:
                # Pre-tessellation DB — fall back to a fan from v0.
                # Correct for convex polygons, approximation for
                # concave ones. Re-run tools/build_water_db.py over
                # the source shapefiles to get true tessellation.
                tri_idx = np.empty((n_v - 2) * 3, dtype=np.int32)
                tri_idx[0::3] = 0
                tri_idx[1::3] = np.arange(1, n_v - 1, dtype=np.int32)
                tri_idx[2::3] = np.arange(2, n_v,     dtype=np.int32)
            else:
                tri_idx = np.asarray(tri_idx, dtype=np.int32)
            # Clip indices defensively; the build tool may emit one
            # malformed entry on a tessellation edge case.
            np.clip(tri_idx, 0, n_v - 1, out=tri_idx)
            verts_np = np.asarray(poly.vertices, dtype=np.float32)
            picked = verts_np[tri_idx]   # (n_idx, 2) — fancy indexing
            buf = np.empty((picked.shape[0], 3), dtype=np.float32)
            buf[:, 0:2] = picked
            buf[:, 2] = surface_ft
            all_tris.append(buf)

        if not all_tris:
            return None
        return np.concatenate(all_tris, axis=0)

    # ------------------------------------------------------------------
    # Highways (issue #35): decimated OSM polylines draped on the
    # terrain — per-vertex SRTM elevation, expanded to GL_LINES pairs.
    # Collected asynchronously (same pattern as water): the sqlite
    # walk + elevation sampling never blocks a frame.
    # ------------------------------------------------------------------
    _HWY_CACHE_TTL_S = 1.0
    _HWY_CACHE_POS_STEP_DEG = 0.01

    def _collect_highways(self, ac_lat, ac_lon, ac_alt_ft, range_nm):
        if (getattr(self, "highway_db", None) is None
                or not self.highway_db.ready):
            return None
        now = time.perf_counter()
        step = max(0.01, range_nm / 2000.0)
        # Position-only key. The LOS masking (#73) uses the CURRENT altitude when
        # the collection runs, and a moving aircraft already refreshes this on
        # position change (~1 s), so the occlusion stays current without an
        # altitude bucket. An altitude bucket here re-ran the costly query on
        # every 200 ft of descent -- a worker-thread burst that stalled the
        # render loop on final approach (the #73 perf regression).
        key = (round(ac_lat / step) * step,
               round(ac_lon / step) * step,
               round(range_nm / 5.0) * 5.0)
        # Purely key-based — see the water collector note.
        if (self._hwy_cache is not None
                and self._hwy_cache_key == key):
            return self._hwy_cache
        with self._hwy_worker_lock:
            if self._hwy_result is not None:
                r_key, r_arr = self._hwy_result
                self._hwy_result = None
                self._hwy_cache = r_arr
                self._hwy_cache_key = r_key
                self._hwy_cache_time = now
                if r_key == key:
                    return r_arr
            busy = (self._hwy_worker is not None
                    and self._hwy_worker.is_alive())
            if not busy and self._collect_slot.acquire(blocking=False):
                self._hwy_worker = threading.Thread(
                    target=self._hwy_collect_worker,
                    args=(key, ac_lat, ac_lon, ac_alt_ft, range_nm),
                    daemon=True)
                self._hwy_worker.start()
        return self._hwy_cache

    def _hwy_collect_worker(self, key, ac_lat, ac_lon, ac_alt_ft, range_nm):
        try:
            arr = self._collect_highways_sync(ac_lat, ac_lon, ac_alt_ft, range_nm)
            with self._hwy_worker_lock:
                self._hwy_result = (key, arr)
        except Exception:
            log.warning("highway collect worker failed", exc_info=True)
        finally:
            self._collect_slot.release()

    # Highway LOD (flight-tuned at DFW): collection hard-capped at
    # 20 NM (beyond that the lines are sub-pixel and haze-buried, and
    # query area scales with r^2); past 8 NM only motorways survive
    # (no trunks, no ramps) at half vertex density. Cuts the metro
    # worst-case line-raster load by roughly an order of magnitude.
    _HWY_MAX_NM = 20.0
    _HWY_NEAR_NM = 8.0

    def _collect_highways_sync(self, ac_lat, ac_lon, ac_alt_ft, range_nm):
        rng = min(range_nm, self._HWY_MAX_NM)
        lat_cos = math.cos(math.radians(ac_lat))
        near_deg2 = (self._HWY_NEAR_NM / 60.0) ** 2
        lines = []
        for hl in self.highway_db.polylines_in_range(
                ac_lat, ac_lon, rng):
            v = hl.vertices
            if len(v) < 2:
                continue
            mid = v[len(v) // 2]
            d2 = ((mid[0] - ac_lat) ** 2
                  + ((mid[1] - ac_lon) * lat_cos) ** 2)
            if d2 > near_deg2:
                if hl.fclass != "motorway":
                    continue
                if len(v) > 3:
                    v = np.vstack([v[::2], v[-1:]])
            lines.append(v)
        if not lines:
            return None
        # Batched SRTM elevation for every vertex of every polyline.
        all_pts = np.concatenate(lines, axis=0)
        elev_m, _ = self._sample_elevations(
            all_pts[:, 0][None, :], all_pts[:, 1][None, :])
        elev_ft = (elev_m[0] * 3.28084).astype(np.float32)
        # Terrain line-of-sight masking (issue #73), vectorised over every
        # vertex at once (issue #74): the per-vertex sight-line loop was the
        # biggest GIL-held burst on the highway worker at low altitude. With no
        # depth test a road behind a ridge would draw over the near slope, so a
        # GL_LINES pair is emitted only where BOTH endpoints have a clear line
        # of sight -- the road disappears behind a ridge and reappears beyond.
        masked_all = self._los_masked_batch(
            ac_lat, ac_lon, ac_alt_ft,
            all_pts[:, 0], all_pts[:, 1], elev_ft, lat_cos)
        vis_all = ~masked_all
        out = []
        i = 0
        for v in lines:
            k = len(v)
            seg = np.empty((k, 3), dtype=np.float32)
            seg[:, 0:2] = v
            seg[:, 2] = elev_ft[i:i + k]
            vis = vis_all[i:i + k]
            i += k
            seg_ok = vis[:-1] & vis[1:]      # per-segment: both ends visible
            if not seg_ok.any():
                continue
            starts = seg[:-1][seg_ok]
            ends = seg[1:][seg_ok]
            pairs = np.empty((2 * starts.shape[0], 3), dtype=np.float32)
            pairs[0::2] = starts
            pairs[1::2] = ends
            out.append(pairs)
        if not out:
            return None
        return np.concatenate(out, axis=0)

    # Obstacle color groups (RGBA in [0, 1]) — match the QPen colors
    # the CPU path used in pre-Phase-2 commits.
    _OBSTACLE_COLOR_GROUPS = (
        ("conflict",  (200/255,   0/255, 200/255, 1.0)),  # tip above aircraft
        ("lit_red",   (220/255,  60/255,  60/255, 1.0)),  # red-lit, below aircraft
        ("lit_white", (230/255, 230/255, 230/255, 1.0)),  # white/dual-lit
        ("unlit",     (160/255, 160/255, 160/255, 1.0)),  # unlit fallback
    )

    # Cache the obstacle-pole vertex arrays the same way water does —
    # the polygon set changes glacially compared to the frame rate.
    _OBSTACLES_CACHE_TTL_S = 1.0
    _OBSTACLES_CACHE_POS_STEP_DEG = 0.01

    def _collect_obstacles(self, ac_lat, ac_lon, ac_alt_ft, range_nm,
                           atlas_uvs):
        """Group every visible obstacle by color and return a dict
        ``{color_rgba: np.ndarray(N*6, 5)}`` of textured billboard
        quads (lat, lon, elev_ft, u, v) — one world-scaled FAA symbol
        per obstacle, base at ground level, tip at the obstacle top,
        facing the aircraft. Returns empty dict when the obstacle DB
        isn't configured.

        Cached for ``_OBSTACLES_CACHE_TTL_S`` seconds keyed by
        coarsened (lat, lon, alt, range_nm). The cache key includes
        altitude because the conflict-vs-lit grouping depends on
        whether each tip is above/below the aircraft."""
        if (getattr(self, "obstacle_db", None) is None
                or not self.obstacle_db.ready
                or not atlas_uvs):
            return {}

        now = time.perf_counter()
        step = max(0.01, range_nm / 2000.0)
        key = (round(ac_lat / step) * step,
               round(ac_lon / step) * step,
               round(ac_alt_ft / 200.0) * 200.0,  # 200 ft alt bucket
               round(range_nm / 5.0) * 5.0)
        return self._async_cache(
            "obstacles", key,
            lambda: self._build_obstacles(
                ac_lat, ac_lon, ac_alt_ft, range_nm, atlas_uvs)) or {}

    # Line-of-sight terrain masking (KRIL/GJT flight report: a far
    # airport behind intervening ridges drew its flag over the near
    # mountain, falsely reading as "on it"). Sample terrain along the
    # straight line from the aircraft to a marker; if a ridge rises
    # above that sight line by more than _LOS_CLEAR_FT, the marker is
    # terrain-masked and gets dimmed (vs the foreground full-colour).
    _LOS_CLEAR_FT = 75.0

    def _los_masked(self, ac_lat, ac_lon, ac_alt_ft,
                    t_lat, t_lon, t_alt_ft, lat_cos):
        if self.cache is None:
            return False
        d_lat = t_lat - ac_lat
        d_lon = (t_lon - ac_lon) * lat_cos
        dist_nm = math.sqrt(d_lat * d_lat + d_lon * d_lon) * 60.0
        if dist_nm < 1.0:
            return False
        n = int(min(24, max(4, dist_nm)))   # ~1 sample / NM, 4..24
        for k in range(1, n):
            f = k / n
            lat = ac_lat + f * (t_lat - ac_lat)
            lon = ac_lon + f * (t_lon - ac_lon)
            sight_ft = ac_alt_ft + f * (t_alt_ft - ac_alt_ft)
            terr_ft = self.cache.elevation(lat, lon) * 3.28084
            if terr_ft > sight_ft + self._LOS_CLEAR_FT:
                return True
        return False

    def _los_masked_batch(self, ac_lat, ac_lon, ac_alt_ft,
                          t_lats, t_lons, t_alts_ft, lat_cos):
        """Vectorised :meth:`_los_masked` over many targets at once.

        Returns a bool array (True = terrain-masked) for the ``(n,)``
        target arrays. Replaces the per-vertex Python sight-line loop on
        the highway collect worker -- the biggest GIL-held burst at low
        altitude (issue #74): a single batched terrain sample over an
        ``(n, steps)`` grid instead of ``n * steps`` scalar
        ``cache.elevation`` calls. Uses ``_sample_elevations`` (the same
        batched sampler the draped vertex elevations come from), so the
        sight-line terrain is consistent with the road altitude."""
        n = int(np.asarray(t_lats).shape[0])
        masked = np.zeros(n, dtype=bool)
        if self.cache is None or n == 0:
            return masked
        t_lats = np.asarray(t_lats, dtype=np.float64)
        t_lons = np.asarray(t_lons, dtype=np.float64)
        t_alts_ft = np.asarray(t_alts_ft, dtype=np.float64)
        d_lat = t_lats - ac_lat
        d_lon = (t_lons - ac_lon) * lat_cos
        dist_nm = np.sqrt(d_lat * d_lat + d_lon * d_lon) * 60.0
        far = dist_nm >= 1.0          # near targets are never masked
        if not far.any():
            return masked
        NS = 23                       # interior samples (~1/NM, capped like the scalar)
        fr = np.arange(1, NS + 1, dtype=np.float64) / (NS + 1)
        lat_s = ac_lat + fr[None, :] * (t_lats[:, None] - ac_lat)
        lon_s = ac_lon + fr[None, :] * (t_lons[:, None] - ac_lon)
        sight_ft = ac_alt_ft + fr[None, :] * (t_alts_ft[:, None] - ac_alt_ft)
        terr_m, _ = self._sample_elevations(lat_s, lon_s)
        terr_ft = terr_m * 3.28084
        occluded = terr_ft > (sight_ft + self._LOS_CLEAR_FT)
        return far & occluded.any(axis=1)

    def _build_obstacles(self, ac_lat, ac_lon, ac_alt_ft, range_nm,
                         atlas_uvs):

        # Build per-color-group billboard quads: world-scaled symbol,
        # base at the ground, tip at the obstacle top, horizontal
        # extent tangential to the sight line so the quad faces the
        # aircraft. FAA glyph choice by height AGL.
        lat_cos = math.cos(math.radians(ac_lat))
        FT_PER_DEG = 364491.0
        by_color = {name: [] for name, _ in self._OBSTACLE_COLOR_GROUPS}
        by_color_m = {name: [] for name, _ in self._OBSTACLE_COLOR_GROUPS}
        # Cap the obstacle query box well in (was 50 nm): beyond ~15 nm
        # obstacles are sub-pixel and haze-buried, and near a metro a 50 nm box
        # builds thousands of Python ObstacleRecords on the worker thread each
        # refresh -- the GIL-held burst that stalled the render loop on approach.
        for obs in self.obstacle_db.obstacles_in_range(
                ac_lat, ac_lon, min(range_nm, 15.0),
                min_agl_ft=self.obstacle_min_agl_ft):
            if obs.amsl_ft >= ac_alt_ft:
                group = "conflict"
            else:
                cat = obs.lighting_category()
                if cat == "red":
                    group = "lit_red"
                elif cat in ("white", "dual"):
                    group = "lit_white"
                else:
                    group = "unlit"
            height_ft = max(obs.amsl_ft - obs.base_amsl_ft, 50.0)
            glyph = "OBST_HIGH" if height_ft >= 1000.0 else "OBST"
            uv = atlas_uvs.get(glyph)
            if uv is None:
                continue
            u0, v0, u1, v1 = uv
            # Tangential (screen-rightward) unit direction at the
            # obstacle, same billboard frame the airport flags use.
            d_lat = obs.lat - ac_lat
            d_lon = (obs.lon - ac_lon) * lat_cos
            brg = math.atan2(d_lon, d_lat)
            t_lat = -math.sin(brg)
            t_lon = math.cos(brg) / lat_cos
            half_w_deg = (height_ft * 0.45) / FT_PER_DEG
            base = obs.base_amsl_ft
            top = base + height_ft
            bl = (obs.lat - t_lat * half_w_deg,
                  obs.lon - t_lon * half_w_deg, base, u0, v1)
            br = (obs.lat + t_lat * half_w_deg,
                  obs.lon + t_lon * half_w_deg, base, u1, v1)
            tr = (obs.lat + t_lat * half_w_deg,
                  obs.lon + t_lon * half_w_deg, top, u1, v0)
            tl = (obs.lat - t_lat * half_w_deg,
                  obs.lon - t_lon * half_w_deg, top, u0, v0)
            if self._los_masked(ac_lat, ac_lon, ac_alt_ft,
                                obs.lat, obs.lon, top, lat_cos):
                by_color_m[group].extend((tl, tr, br, tl, br, bl))
            else:
                by_color[group].extend((tl, tr, br, tl, br, bl))

        result = {}
        DIM = 0.4
        for name, rgba in self._OBSTACLE_COLOR_GROUPS:
            if by_color[name]:
                result[rgba] = np.asarray(by_color[name],
                                          dtype=np.float32)
            if by_color_m[name]:
                drgba = (rgba[0] * DIM, rgba[1] * DIM,
                         rgba[2] * DIM, rgba[3])
                result[drgba] = np.asarray(by_color_m[name],
                                           dtype=np.float32)
        return result

    # ------------------------------------------------------------------
    # Phase 5: airport flags + identifier text on the GPU. The pole is
    # a world-space line segment; the flag rectangle and identifier
    # glyphs are distance-billboarded — sized in world units so they
    # project to roughly constant pixels (matching the fixed-pixel CPU
    # flags they replace). The identifier renders INSIDE the flag body
    # in black (issue #36) rather than beside it.
    # ------------------------------------------------------------------
    _FLAGS_CACHE_TTL_S = 1.0
    _FLAGS_CACHE_POS_STEP_DEG = 0.01
    _FLAG_POLE_HT_FT = 2000.0
    _FLAG_CHAR_PX = 9.0     # target on-screen glyph height
    _FLAG_PAD_PX = 2.0      # flag border around the identifier text
    _FLAG_GAP_PX = 1.5      # inter-glyph gap
    _FLAG_MIN_DIST_M = 300.0  # skip the flag when essentially overhead

    def _collect_airport_flags(self, ac_lat, ac_lon, ac_alt_ft,
                               range_nm, ppd, atlas_uvs):
        """Build GL vertex arrays for every in-range airport flag.

        Returns ``{"poles": Nx3, "flags": Nx3, "text": Nx5}`` float32
        arrays (poles as GL_LINES pairs, flag rectangles and glyph
        quads as triangles), or None when nothing is in range.

        The flag rectangle and glyphs are laid out in a billboard
        plane at the pole tip: horizontal axis tangential to the
        sight line (reads as screen-rightward), vertical axis in
        elevation. World sizes are derived from the airport's current
        distance so the projected flag stays ~constant-pixel like the
        old screen-space CPU flags. With the 1 s cache TTL the size
        lags distance changes by under a second — invisible at
        aircraft speeds. Under roll the flags stay world-horizontal
        (they bank with the terrain), which replaces the old
        screen-aligned behaviour and matches how the rest of the SVS
        scene moves."""
        if (getattr(self, "airport_db", None) is None
                or not self.airport_db.ready
                or not atlas_uvs or not ppd):
            return None

        now = time.perf_counter()
        step = max(0.01, range_nm / 2000.0)
        key = (round(ac_lat / step) * step,
               round(ac_lon / step) * step,
               round(range_nm / 5.0) * 5.0, round(ppd, 1))
        if (self._flags_cache is not None
                and self._flags_cache_key == key):
            return self._flags_cache

        lat_cos = math.cos(math.radians(ac_lat))
        range_m = min(self.range_nm, 50.0) * 1852.0
        DEG_PER_RAD = 57.29577951308232
        FT_PER_DEG = 364491.0

        poles, flag_tris, text_verts = [], [], []
        poles_m, flag_tris_m, text_verts_m = [], [], []
        for label, ref_lat, ref_lon, ref_elev_ft, _runways in \
                self._get_airports_cached(ac_lat, ac_lon):
            d_lat = ref_lat - ac_lat
            d_lon = (ref_lon - ac_lon) * lat_cos
            dist_deg = math.sqrt(d_lat * d_lat + d_lon * d_lon)
            dist_m = dist_deg * 111139.0
            if dist_m > range_m or dist_m < self._FLAG_MIN_DIST_M:
                continue

            top_elev = ref_elev_ft + self._FLAG_POLE_HT_FT
            if self._los_masked(ac_lat, ac_lon, ac_alt_ft,
                                ref_lat, ref_lon, ref_elev_ft, lat_cos):
                tp, tf, tt = poles_m, flag_tris_m, text_verts_m
            else:
                tp, tf, tt = poles, flag_tris, text_verts
            tp.append((ref_lat, ref_lon, ref_elev_ft))
            tp.append((ref_lat, ref_lon, top_elev))

            # Billboard frame at the pole tip. px2deg converts a pixel
            # target to the degree-unit world offset that projects to
            # that many pixels at this distance (inverse of the
            # overlay shader's small-angle scale).
            brg = math.atan2(d_lon, d_lat)
            t_lat = -math.sin(brg)                # screen-rightward,
            t_lon = math.cos(brg) / lat_cos       # in lat/lon degrees
            px2deg = dist_deg / (DEG_PER_RAD * ppd)

            def bb_point(px_right, px_down):
                off = px_right * px2deg
                return (ref_lat + t_lat * off,
                        ref_lon + t_lon * off,
                        top_elev - px_down * px2deg * FT_PER_DEG)

            chars = [(ch, atlas_uvs[ch]) for ch in label
                     if ch in atlas_uvs]
            ch_px = self._FLAG_CHAR_PX
            widths = []
            for _ch, (u0, v0, u1, v1) in chars:
                aspect = (u1 - u0) / max(v1 - v0, 1e-6)
                widths.append(ch_px * max(0.2, min(aspect, 1.2)))
            text_w = (sum(widths)
                      + self._FLAG_GAP_PX * max(0, len(chars) - 1))
            fw = text_w + 2.0 * self._FLAG_PAD_PX
            fh = ch_px + 2.0 * self._FLAG_PAD_PX

            c00 = bb_point(0.0, 0.0)
            c10 = bb_point(fw, 0.0)
            c11 = bb_point(fw, fh)
            c01 = bb_point(0.0, fh)
            tf.extend((c00, c10, c11, c00, c11, c01))

            x = self._FLAG_PAD_PX
            for (ch, (u0, v0, u1, v1)), cw in zip(chars, widths):
                p_tl = bb_point(x, self._FLAG_PAD_PX)
                p_tr = bb_point(x + cw, self._FLAG_PAD_PX)
                p_br = bb_point(x + cw, self._FLAG_PAD_PX + ch_px)
                p_bl = bb_point(x, self._FLAG_PAD_PX + ch_px)
                v_tl = (*p_tl, u0, v0)
                v_tr = (*p_tr, u1, v0)
                v_br = (*p_br, u1, v1)
                v_bl = (*p_bl, u0, v1)
                tt.extend((v_tl, v_tr, v_br, v_tl, v_br, v_bl))
                x += cw + self._FLAG_GAP_PX

        if not poles and not poles_m:
            result = None
        else:
            def _arr(x):
                return (np.asarray(x, dtype=np.float32) if x else None)
            result = {
                "poles": _arr(poles), "flags": _arr(flag_tris),
                "text": _arr(text_verts),
                "poles_masked": _arr(poles_m),
                "flags_masked": _arr(flag_tris_m),
                "text_masked": _arr(text_verts_m),
            }
        self._flags_cache = result
        self._flags_cache_key = key
        self._flags_cache_time = now
        return result

    # Cached airport-proximity test. The GL terrain shader needs one
    # boolean per frame (2-colour collapse near airports); re-querying
    # sqlite every frame cost ~0.3-1 ms for a value that changes on a
    # seconds timescale.
    _NEAR_AIRPORT_CACHE_TTL_S = 1.0

    def near_airport(self, ac_lat, ac_lon):
        """True when any airport in the database lies within
        ``airport_proximity_nm`` of the aircraft. 1 s TTL cache."""
        if (self.airport_proximity_nm <= 0.0
                or getattr(self, "airport_db", None) is None
                or not self.airport_db.ready):
            return False
        # Key-based like every other collector cache (the 1 s TTL
        # re-ran the sqlite query + runway-object construction on the
        # render thread every second).
        step = 0.01
        key = (round(ac_lat / step) * step, round(ac_lon / step) * step)
        if (self._near_airport_cache is not None
                and getattr(self, "_near_airport_cache_key", None)
                    == key):
            return self._near_airport_cache
        hit = False
        best_elev = None
        best_d2 = None
        for ap in self.airport_db.airports_in_range(
                ac_lat, ac_lon, self.airport_proximity_nm):
            hit = True
            ap_lat = getattr(ap, "ref_lat", None)
            ap_lon = getattr(ap, "ref_lon", None)
            elev = getattr(ap, "elev_ft", None)
            if elev is None:
                continue
            if ap_lat is None or ap_lon is None:
                d2 = 0.0
            else:
                d2 = (ap_lat - ac_lat) ** 2 + (ap_lon - ac_lon) ** 2
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2
                best_elev = float(elev)
        self._near_airport_cache = hit
        self._near_airport_elev_ft = best_elev if hit else None
        self._near_airport_cache_key = key
        return hit

    def _sample_elevations(self, lat_grid: np.ndarray,
                           lon_grid: np.ndarray) -> tuple:
        """
        Sample elevation for the entire grid in one vectorised pass.
        Returns (elev_m, is_water) — same shape as the input grids —
        with is_water marking ocean (SRTM void tiles or missing tiles).

        Points over ocean are initialised to _WATER_SENTINEL; bilinear
        interpolation near coastlines may produce large-negative values that are
        also caught by the water mask.  Elevation is clamped to 0 m after masking
        so clearance arithmetic is not affected by the sentinel.
        """
        elev = np.full(lat_grid.shape, _WATER_SENTINEL, dtype=np.float32)

        tile_lat_grid = np.floor(lat_grid).astype(np.int32)
        tile_lon_grid = np.floor(lon_grid).astype(np.int32)

        keys = np.unique(
            np.stack([tile_lat_grid.ravel(), tile_lon_grid.ravel()], axis=1),
            axis=0
        )

        for tile_lat, tile_lon in keys:
            tile = self.cache.get(int(tile_lat), int(tile_lon))
            if tile is None:
                continue  # missing tile file — stays as water sentinel

            mask = (tile_lat_grid == tile_lat) & (tile_lon_grid == tile_lon)
            lats = lat_grid[mask]
            lons = lon_grid[mask]

            n = tile.shape[0]
            row_f = (tile_lat + 1.0 - lats) * (n - 1)
            col_f = (lons - tile_lon)        * (n - 1)

            row = np.clip(np.floor(row_f).astype(np.int32), 0, n - 2)
            col = np.clip(np.floor(col_f).astype(np.int32), 0, n - 2)
            dr  = (row_f - row).astype(np.float32)
            dc  = (col_f - col).astype(np.float32)

            elev[mask] = (tile[row,     col    ] * (1 - dr) * (1 - dc) +
                          tile[row,     col + 1] * (1 - dr) *      dc  +
                          tile[row + 1, col    ] *      dr  * (1 - dc) +
                          tile[row + 1, col + 1] *      dr  *      dc)

        # Two water cases:
        #   1. Missing tile (open ocean, no HGT file) — stays at _WATER_SENTINEL
        #   2. Void-filled SRTM product — ocean pixels are exactly 0.0
        # Both are detected here; elev is clamped to 0 so clearance maths is clean.
        is_water = (elev < (_WATER_SENTINEL / 2.0)) | (elev == 0.0)
        elev = np.where(is_water, 0.0, elev)
        return elev, is_water


# ---------------------------------------------------------------------------
# Scene-graph wrapper — lets SVS participate in the same z-order system
# as the pitch ladder, runways, and other items in the AI scene.
# ---------------------------------------------------------------------------
def make_svs_item(renderer: "SVSRenderer", ai_widget):
    """Build a QGraphicsItem subclass instance that delegates to *renderer*.

    The item reads pose state (lat/lon/alt/pitch/roll/heading/ppd) from the
    parent ``ai_widget`` at paint time. Z-value defaults to one below the
    pitch ladder (ladder is z=1); override with ``setZValue`` after creation
    or via the ``z_value`` SVS config key picked up by the AI widget.
    """
    from PyQt6.QtCore    import QRectF
    from PyQt6.QtWidgets import QGraphicsItem

    class _SVSGraphicsItem(QGraphicsItem):
        def __init__(self, _renderer, _ai):
            super().__init__()
            self._renderer = _renderer
            self._ai       = _ai

        def boundingRect(self):
            # Generous rect so Qt never culls the item — SVS uses
            # resetTransform() internally and draws in pure viewport pixels,
            # so the scene-coordinate bounds don't actually constrain output.
            return QRectF(-1e6, -1e6, 2e6, 2e6)

        def paint(self, painter, option, widget=None):
            if self._renderer is None or not self._renderer.ready:
                return
            ai = self._ai
            vp = ai.viewport()
            ppd = getattr(ai, 'pixelsPerDeg',
                          vp.height() / ai.pitchDegreesShown)
            # SVS does its geographic projection in true-north
            # coordinates, so subtract local magnetic variation from
            # the magnetic HEAD before projecting. _magvar defaults to
            # 0 when the FIX MAGVAR key isn't published — in that case
            # the SVS picture sits with a constant rotation equal to
            # local variation, which is small enough not to break the
            # picture but worth correcting where the data is available.
            head_true = ai._fpm_head - getattr(ai, "_magvar", 0.0)
            # SVSRenderer.draw does its own save/resetTransform/restore so the
            # outer scene transform is preserved for the next item in z order.
            # Depress the terrain camera by horizon_position's look-down angle
            # so the terrain horizon rises to match the AI's raised reference
            # (no-op when horizon_position == 50). Sign verified on the Pi --
            # if the terrain horizon moves the wrong way, flip the subtraction.
            pitch_for_svs = ai._pitchAngle - ai._horizon_offset_deg()
            self._renderer.draw(
                painter, vp.width(), vp.height(),
                ai._svs_lat, ai._svs_lon, ai._svs_alt,
                pitch_for_svs, ai._rollAngle, head_true,
                ppd, vp.devicePixelRatioF())

    return _SVSGraphicsItem(renderer, ai_widget)
