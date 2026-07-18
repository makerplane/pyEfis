"""
Unit tests for the SVS terrain renderer (pyefis.instruments.ai.svs).

Tests the HGT tile reader, tile cache, elevation sampling, clearance colour
logic, and SVSRenderer integration with the AI widget — all without a
physical display or real terrain tiles.
"""
import math
import struct
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PyQt6.QtGui import QPaintEvent, QPainter

from pyefis.instruments.ai.svs import (
    SVSRenderer, TileCache,
    tile_name, load_tile, elevation_at,
    COLOR_SAFE, COLOR_CAUTION, COLOR_WARNING, COLOR_CONFLICT,
    SRTM3_SAMPLES, SRTM3_VOID, _WATER_SENTINEL,
    POLAR_DEFAULTS,
)
from pyefis.instruments.ai import AI


# ---------------------------------------------------------------------------
# Helpers — synthetic HGT tile
# ---------------------------------------------------------------------------

def _write_hgt(path: Path, elevation: int = 500):
    """Write a flat-elevation synthetic HGT tile (all samples = elevation)."""
    data = np.full((SRTM3_SAMPLES, SRTM3_SAMPLES), elevation, dtype=">i2")
    data.tofile(path)


def _make_tile_dir(tmp_path: Path, lat: int, lon: int, elevation: int = 500) -> Path:
    """Create a synthetic tile in the standard directory structure."""
    name = tile_name(lat, lon)
    ns_dir = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"
    tile_dir = tmp_path / "srtm3" / ns_dir
    tile_dir.mkdir(parents=True, exist_ok=True)
    _write_hgt(tile_dir / f"{name}.hgt", elevation)
    return tmp_path / "srtm3"


# ---------------------------------------------------------------------------
# Tile naming
# ---------------------------------------------------------------------------

class TestTileNaming:
    def test_positive_lat_lon(self):
        assert tile_name(32, -97) == "N32W097"

    def test_negative_lat(self):
        assert tile_name(-33, 18) == "S33E018"

    def test_equator_prime_meridian(self):
        assert tile_name(0, 0) == "N00E000"

    def test_high_latitude(self):
        assert tile_name(59, 10) == "N59E010"


# ---------------------------------------------------------------------------
# HGT tile loading
# ---------------------------------------------------------------------------

class TestTileLoading:
    def test_load_flat_tile(self, tmp_path):
        root = _make_tile_dir(tmp_path, 32, -97, elevation=1500)
        tile = load_tile(root, 32, -97)
        assert tile is not None
        assert tile.shape == (SRTM3_SAMPLES, SRTM3_SAMPLES)
        assert tile[0, 0] == 1500

    def test_missing_tile_returns_none(self, tmp_path):
        root = tmp_path / "srtm3"
        root.mkdir()
        tile = load_tile(root, 99, 99)
        assert tile is None

    def test_void_values_replaced_with_water_sentinel(self, tmp_path):
        # SRTM void cells mark ocean / no-data. They are replaced with the
        # water sentinel (not 0): coastal interpolation relies on the sentinel
        # magnitude to detect water, and a plain 0 would read as sea-level land.
        name = tile_name(10, 10)
        ns_dir = "N10"
        tile_dir = tmp_path / "srtm3" / ns_dir
        tile_dir.mkdir(parents=True)
        data = np.full((SRTM3_SAMPLES, SRTM3_SAMPLES), SRTM3_VOID, dtype=">i2")
        data.tofile(tile_dir / f"{name}.hgt")
        tile = load_tile(tmp_path / "srtm3", 10, 10)
        assert tile is not None
        assert (tile == _WATER_SENTINEL).all()


# ---------------------------------------------------------------------------
# Elevation interpolation
# ---------------------------------------------------------------------------

class TestElevationAt:
    def test_centre_of_flat_tile(self, tmp_path):
        root = _make_tile_dir(tmp_path, 32, -97, elevation=1000)
        tile = load_tile(root, 32, -97)
        # Centre of the tile
        elev = elevation_at(tile, 32, -97, 32.5, -96.5)
        assert abs(elev - 1000) < 1.0

    def test_sw_corner_of_tile(self, tmp_path):
        root = _make_tile_dir(tmp_path, 32, -97, elevation=800)
        tile = load_tile(root, 32, -97)
        elev = elevation_at(tile, 32, -97, 32.0, -97.0)
        assert abs(elev - 800) < 1.0


# ---------------------------------------------------------------------------
# Tile cache
# ---------------------------------------------------------------------------

class TestTileCache:
    def test_cache_hit_returns_same_array(self, tmp_path):
        root = _make_tile_dir(tmp_path, 32, -97)
        cache = TileCache(root)
        a = cache.get(32, -97)
        b = cache.get(32, -97)
        assert a is b  # same object from cache

    def test_missing_tile_returns_none(self, tmp_path):
        root = tmp_path / "srtm3"
        root.mkdir()
        cache = TileCache(root)
        assert cache.get(0, 0) is None

    def test_elevation_method(self, tmp_path):
        root = _make_tile_dir(tmp_path, 32, -97, elevation=600)
        cache = TileCache(root)
        elev = cache.elevation(32.5, -96.5)
        assert abs(elev - 600) < 1.0

    def test_elevation_missing_tile_returns_zero(self, tmp_path):
        root = tmp_path / "srtm3"
        root.mkdir()
        cache = TileCache(root)
        assert cache.elevation(32.5, -96.5) == 0.0

    def test_lru_eviction(self, tmp_path):
        for lat in range(5):
            _make_tile_dir(tmp_path, lat, 0, elevation=100 * lat)
        root = tmp_path / "srtm3"
        cache = TileCache(root, max_tiles=3)
        for lat in range(5):
            cache.get(lat, 0)
        assert len(cache._cache) <= 3


# ---------------------------------------------------------------------------
# SVSRenderer configuration
# ---------------------------------------------------------------------------

class TestSVSRendererConfig:
    def test_disabled_by_default(self):
        r = SVSRenderer({})
        assert r.enabled is False
        assert r.ready is False

    def test_enabled_but_no_tile_path(self):
        r = SVSRenderer({"enabled": True})
        assert r.enabled is True
        assert r.ready is False   # no tile_path configured

    def test_enabled_with_valid_tile_path(self, tmp_path):
        root = _make_tile_dir(tmp_path, 32, -97)
        r = SVSRenderer({"enabled": True, "tile_path": str(root)})
        assert r.ready is True

    def test_legacy_renderer_values_accepted_and_ignored(self):
        # GL-required: legacy tier names are accepted for config
        # compatibility but the renderer is always opengl.
        for legacy in ("cpu_sparse", "cpu_dense", "cpu_ultra", "polar"):
            assert SVSRenderer({"renderer": legacy}).renderer == "opengl"

    def test_range_nm_default(self):
        # Bumped from 30 NM to 50 NM when the GL renderer landed —
        # polar-mesh density is no longer the bottleneck so the cap
        # is set to match the heightmap patch's safe reach.
        assert SVSRenderer({}).range_nm == 50.0

    def test_clearance_colors(self, tmp_path):
        root = _make_tile_dir(tmp_path, 32, -97)
        r = SVSRenderer({
            "enabled": True, "tile_path": str(root),
            "clearance_green_ft": 1000, "clearance_yellow_ft": 500,
        })
        assert r._clearance_color(1500) == COLOR_SAFE
        assert r._clearance_color(750)  == COLOR_CAUTION
        assert r._clearance_color(200)  == COLOR_WARNING
        assert r._clearance_color(-50)  == COLOR_CONFLICT


# ---------------------------------------------------------------------------
# AI widget integration
# ---------------------------------------------------------------------------

class TestAISVSIntegration:
    def test_ai_svs_none_by_default(self, fix, qtbot):
        widget = AI()
        qtbot.addWidget(widget)
        assert widget.svs is None

    def test_set_svs_config_creates_renderer(self, fix, qtbot, tmp_path):
        root = _make_tile_dir(tmp_path, 32, -97)
        widget = AI()
        qtbot.addWidget(widget)
        widget.set_svs_config({"enabled": True, "tile_path": str(root)})
        assert widget.svs is not None
        assert widget.svs.ready is True

    def test_paint_with_svs_disabled(self, fix, qtbot):
        """paintEvent does not raise when SVS is configured but disabled."""
        widget = AI()
        qtbot.addWidget(widget)
        widget.set_svs_config({"enabled": False})
        widget.resize(400, 300)
        widget.show()
        qtbot.waitExposed(widget)
        widget.paintEvent(QPaintEvent(widget.rect()))

    def test_paint_with_svs_enabled_no_tiles(self, fix, qtbot, tmp_path):
        """paintEvent does not raise when SVS enabled but tile dir is empty."""
        empty_dir = tmp_path / "srtm3"
        empty_dir.mkdir()
        widget = AI()
        qtbot.addWidget(widget)
        widget.set_svs_config({"enabled": True, "tile_path": str(empty_dir)})
        widget.resize(400, 300)
        widget.show()
        qtbot.waitExposed(widget)
        widget.paintEvent(QPaintEvent(widget.rect()))

    def test_paint_with_svs_and_synthetic_tile(self, fix, qtbot, tmp_path):
        """Full paintEvent with a synthetic tile loaded — no crash."""
        fix.db.set_value("LAT", 32.5)
        fix.db.set_value("LONG", -96.5)
        fix.db.set_value("ALT", 3000.0)
        root = _make_tile_dir(tmp_path, 32, -97, elevation=500)
        widget = AI()
        qtbot.addWidget(widget)
        widget.set_svs_config({
            "enabled": True,
            "tile_path": str(root),
            "renderer": "cpu_sparse",
            "range_nm": 10,
        })
        widget.resize(400, 300)
        widget.show()
        qtbot.waitExposed(widget)
        widget.paintEvent(QPaintEvent(widget.rect()))

    def test_land_brush_sky_only_when_svs_drawing(self, fix, qtbot, tmp_path):
        """The brown attitude ground is replaced by sky ONLY while the SVS is
        genuinely drawing terrain; any failure/empty frame falls back to brown,
        and degraded attitude data stays grey."""
        root = _make_tile_dir(tmp_path, 32, -97)
        widget = AI()
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        widget.set_svs_config({"enabled": True, "tile_path": str(root)})
        widget.show()
        qtbot.waitExposed(widget)
        assert hasattr(widget, "land_rect")

        # SVS ready but hasn't painted terrain this frame -> brown fail-safe.
        widget.svs.gl_failed = False
        widget.svs.drew_terrain = False
        widget._update_land_brush()
        assert widget._land_brush_cur is widget.gbrown_brush

        # SVS actually drew terrain -> land becomes sky (no brown sliver).
        widget.svs.drew_terrain = True
        widget._update_land_brush()
        assert widget._land_brush_cur is widget.gblue_brush

        # GL failure mid-flight -> brown attitude ground returns (fail-safe).
        widget.svs.gl_failed = True
        widget._update_land_brush()
        assert widget._land_brush_cur is widget.gbrown_brush

        # Degraded attitude data wins regardless of SVS -> grey.
        widget.svs.gl_failed = False
        widget.svs.drew_terrain = True
        widget.setAIOldPitch(True)
        widget._update_land_brush()
        assert widget._land_brush_cur is widget.gray_land

    def test_land_brush_survives_svs_attr_clobber(self, fix, qtbot, tmp_path):
        """Reproduces the on-device bug locally (no GL needed): the screenbuilder
        assigns YAML `options` as raw attributes, so `self.svs` gets overwritten
        with the `svs:` config DICT after set_svs_config. _svs_drawing must still
        find the live renderer (via _svs_renderer), or the sky-ground silently
        reverts to brown on every real screen."""
        root = _make_tile_dir(tmp_path, 32, -97)
        widget = AI()
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        cfg = {"enabled": True, "tile_path": str(root)}
        widget.set_svs_config(cfg)
        widget.show()
        qtbot.waitExposed(widget)
        widget._svs_renderer.gl_failed = False
        widget._svs_renderer.drew_terrain = True

        # The screenbuilder clobber: self.svs becomes the config dict.
        widget.svs = cfg
        assert isinstance(widget.svs, dict)
        assert widget._svs_drawing() is True          # still finds the renderer
        widget._update_land_brush()
        assert widget._land_brush_cur is widget.gblue_brush   # sky, not brown

    def test_svs_unavail_annunciation_survives_clobber(self, fix, qtbot, tmp_path):
        """SVS enabled but GL failed (e.g. enabled on a machine with no usable
        GPU): the AI must still annunciate SVS UNAVAIL after the screenbuilder
        has clobbered self.svs to the config DICT. The gate reads the live
        renderer via _live_svs; reading self.svs (a dict) would see gl_failed as
        False and silently suppress the warning — a pilot left thinking terrain
        awareness is active when it isn't."""
        root = _make_tile_dir(tmp_path, 32, -97)
        widget = AI()
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        cfg = {"enabled": True, "tile_path": str(root)}
        widget.set_svs_config(cfg)
        widget._svs_renderer.gl_failed = True          # GL init/draw failed -> disabled

        widget.svs = cfg                               # the screenbuilder clobber
        assert isinstance(widget.svs, dict)
        # the old, buggy direct read saw nothing (dict has no gl_failed):
        assert getattr(widget.svs, "gl_failed", False) is False
        # the clobber-safe resolver still finds the failed renderer:
        live = widget._live_svs()
        assert live is widget._svs_renderer
        assert getattr(live, "enabled", False) and getattr(live, "gl_failed", False)
        # paint completes and exercises the SVS UNAVAIL annunciation branch:
        widget.show()
        qtbot.waitExposed(widget)
        widget.paintEvent(QPaintEvent(widget.rect()))

    def test_ai_construction_tolerates_missing_fpm_key(self, fix, qtbot,
                                                      monkeypatch, caplog):
        """If a Flight Path Marker FIX key is undefined (e.g. gateway doesn't
        publish TRACK), the AI widget must still construct — FPM rendering
        is silently disabled, not a hard crash."""
        import pyavtools.fix as _fix
        real_get_item = _fix.db.get_item

        def get_item_no_track(key):
            if key == "TRACK":
                raise KeyError(key)
            return real_get_item(key)

        monkeypatch.setattr(_fix.db, "get_item", get_item_no_track)

        with caplog.at_level("WARNING"):
            widget = AI()
        qtbot.addWidget(widget)
        # FPM key map still includes TRACK and that entry stays in fail-state,
        # so _drawFPM's `any(self._fpm_fail.values())` gate skips rendering.
        assert widget._fpm_fail["TRACK"] is True
        # Paint cycle should still complete without raising.
        widget.resize(400, 300)
        widget.show()
        qtbot.waitExposed(widget)
        widget.paintEvent(QPaintEvent(widget.rect()))
        assert any("TRACK" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# Polar (range, azimuth) tier
# ---------------------------------------------------------------------------

class TestWaterDB:
    """``WaterDB`` is a sqlite-backed range-queryable water polygon
    loader, following the ObstacleDB construct-never-raises pattern."""

    def _build_db(self, tmp_path, rows):
        """Build a minimal water.sqlite with the given polygons.
        ``rows`` is a list of (kind, elev_ft, [(lat, lon), ...])."""
        import sqlite3
        from pyefis.instruments.ai.water_db import encode_vertices
        path = tmp_path / "water.sqlite"
        con = sqlite3.connect(str(path))
        con.execute("""
            CREATE TABLE water_polygons (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                min_lat   REAL NOT NULL,
                max_lat   REAL NOT NULL,
                min_lon   REAL NOT NULL,
                max_lon   REAL NOT NULL,
                kind      TEXT NOT NULL,
                elev_ft   REAL,
                vertices  BLOB NOT NULL
            )
        """)
        for kind, elev_ft, verts in rows:
            lats = [v[0] for v in verts]
            lons = [v[1] for v in verts]
            con.execute(
                "INSERT INTO water_polygons "
                "(min_lat, max_lat, min_lon, max_lon, kind, elev_ft, vertices) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (min(lats), max(lats), min(lons), max(lons),
                 kind, elev_ft, encode_vertices(verts)))
        con.commit()
        con.close()
        return path

    def test_missing_file_stays_not_ready(self, tmp_path):
        from pyefis.instruments.ai.water_db import WaterDB
        db = WaterDB(tmp_path / "does_not_exist.sqlite")
        assert db.ready is False
        # Query yields nothing
        assert list(db.polygons_in_range(0.0, 0.0, 30.0)) == []

    def test_none_path_disables_db(self):
        from pyefis.instruments.ai.water_db import WaterDB
        db = WaterDB(None)
        assert db.ready is False

    def test_bad_schema_caught(self, tmp_path):
        """A sqlite file without the expected schema should leave the
        DB in not-ready state, not crash."""
        import sqlite3
        from pyefis.instruments.ai.water_db import WaterDB
        path = tmp_path / "broken.sqlite"
        con = sqlite3.connect(str(path))
        con.execute("CREATE TABLE some_unrelated_table (x INT)")
        con.commit()
        con.close()
        db = WaterDB(path)
        assert db.ready is False

    def test_polygons_in_range_bbox_filter(self, tmp_path):
        from pyefis.instruments.ai.water_db import WaterDB
        # Three polygons:
        #   - Pacific around KSBA (lat 34, lon -120)
        #   - Atlantic near Cape Hatteras NC (lat 35, lon -75)
        #   - Lake Hickory NC near KHKY (lat 35.78, lon -81.3)
        path = self._build_db(tmp_path, [
            ("ocean", None, [(34.0, -120.5), (34.0, -119.5),
                             (34.5, -119.5), (34.5, -120.5)]),
            ("ocean", None, [(35.0, -75.5), (35.0, -74.5),
                             (35.5, -74.5), (35.5, -75.5)]),
            ("lake", 656.0, [(35.78, -81.32), (35.78, -81.28),
                             (35.80, -81.28), (35.80, -81.32)]),
        ])
        db = WaterDB(path)
        assert db.ready is True

        # Aircraft at KSBA — only Pacific should come back.
        polys = list(db.polygons_in_range(34.4, -119.8, 30.0))
        assert len(polys) == 1
        assert polys[0].kind == "ocean"
        assert polys[0].is_ocean is True
        assert len(polys[0].vertices) == 4

        # Aircraft at KHKY — only the lake should come back.
        polys = list(db.polygons_in_range(35.74, -81.39, 10.0))
        assert len(polys) == 1
        assert polys[0].kind == "lake"
        assert polys[0].elev_ft == 656.0
        assert polys[0].is_ocean is False

        # Aircraft mid-Atlantic far from anywhere mapped.
        polys = list(db.polygons_in_range(0.0, 0.0, 30.0))
        assert polys == []

    def test_vertices_roundtrip(self):
        """``encode_vertices`` / ``_decode_vertices`` should be inverses."""
        from pyefis.instruments.ai.water_db import (
            encode_vertices, _decode_vertices)
        verts = [(34.4275, -119.8546),
                 (34.0, -120.0),
                 (-35.123456789, 174.987654321)]   # exercise negatives + precision
        decoded = _decode_vertices(encode_vertices(verts))
        assert len(decoded) == len(verts)
        for (la, lo), (la2, lo2) in zip(verts, decoded):
            assert abs(la - la2) < 1e-12
            assert abs(lo - lo2) < 1e-12


class TestSVSWaterRendering:
    """``_draw_water`` overlays water polygons on top of the terrain
    layer. Sanity-check that it runs without raising at known poses
    and that the DB is wired into the renderer when configured."""

    def _build_db(self, tmp_path, rows):
        # Same minimal builder as TestWaterDB above.
        import sqlite3
        from pyefis.instruments.ai.water_db import encode_vertices
        path = tmp_path / "water.sqlite"
        con = sqlite3.connect(str(path))
        con.execute("""
            CREATE TABLE water_polygons (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                min_lat   REAL NOT NULL, max_lat   REAL NOT NULL,
                min_lon   REAL NOT NULL, max_lon   REAL NOT NULL,
                kind      TEXT NOT NULL, elev_ft   REAL, vertices  BLOB NOT NULL)
        """)
        for kind, elev_ft, verts in rows:
            lats = [v[0] for v in verts]; lons = [v[1] for v in verts]
            con.execute(
                "INSERT INTO water_polygons "
                "(min_lat, max_lat, min_lon, max_lon, kind, elev_ft, vertices) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (min(lats), max(lats), min(lons), max(lons),
                 kind, elev_ft, encode_vertices(verts)))
        con.commit(); con.close()
        return path

    def test_water_db_attached_when_path_configured(self, tmp_path):
        root = _make_tile_dir(tmp_path, 34, -120, elevation=0)
        water = self._build_db(tmp_path, [
            ("ocean", None, [(34.0, -120.5), (34.0, -119.5),
                             (34.5, -119.5), (34.5, -120.5)]),
        ])
        r = SVSRenderer({
            "enabled": True, "tile_path": str(root),
            "water_db_path": str(water),
        })
        assert r.water_db is not None
        assert r.water_db.ready is True

    def test_water_db_disabled_when_path_missing(self, tmp_path):
        root = _make_tile_dir(tmp_path, 34, -120, elevation=0)
        r = SVSRenderer({"enabled": True, "tile_path": str(root)})
        assert r.water_db is not None
        assert r.water_db.ready is False

    def test_draw_water_runs_without_raising_at_ksba(self, tmp_path):
        from PyQt6.QtGui import QImage, QPainter
        # Make a synthetic sea-level tile for the KSBA region so
        # _sample_elevations works.
        root = _make_tile_dir(tmp_path, 34, -120, elevation=0)
        water = self._build_db(tmp_path, [
            ("ocean", None, [
                (34.0, -120.5), (34.0, -119.5),
                (34.5, -119.5), (34.5, -120.5)]),
        ])
        r = SVSRenderer({
            "enabled": True, "tile_path": str(root),
            "water_db_path": str(water), "renderer": "polar",
        })
        img = QImage(400, 300, QImage.Format.Format_RGB32)
        img.fill(0)
        p = QPainter(img)
        try:
            # KSBA short-final pose, looking at the Pacific.
            r.draw(p, 400, 300,
                   34.4275, -119.8546, 500.0,
                   0.0, 0.0, 270.0, 12.0)
        finally:
            p.end()
        # If nothing raised we're good; the polygon should also have
        # produced at least one blue-ish pixel near the bottom-center
        # of the screen at this pose.

    def test_draw_water_skips_when_db_not_ready(self, tmp_path):
        from PyQt6.QtGui import QImage, QPainter
        root = _make_tile_dir(tmp_path, 34, -120, elevation=0)
        r = SVSRenderer({
            "enabled": True, "tile_path": str(root),
            # No water_db_path on purpose.
        })
        img = QImage(400, 300, QImage.Format.Format_RGB32)
        img.fill(0)
        p = QPainter(img)
        try:
            r.draw(p, 400, 300,
                   34.4275, -119.8546, 500.0,
                   0.0, 0.0, 270.0, 12.0)
        finally:
            p.end()


class TestSVSGLFallback:
    def _draw(self, r, lat=32.5, lon=-96.5, alt_ft=3000.0, heading_deg=0.0):
        from PyQt6.QtGui import QImage
        img = QImage(400, 300, QImage.Format.Format_RGB32)
        img.fill(0)
        painter = QPainter(img)
        try:
            r.draw(painter, 400, 300, lat, lon, alt_ft,
                   0.0, 0.0, heading_deg, 12.0)
        finally:
            painter.end()

    def test_renderer_initially_opengl(self, tmp_path):
        """Construction with renderer='opengl' stores the choice — the
        downgrade happens on first draw, not at config-time."""
        root = _make_tile_dir(tmp_path, 32, -97)
        r = SVSRenderer({
            "enabled": True, "tile_path": str(root),
            "renderer": "opengl",
        })
        assert r.renderer == "opengl"
        assert r._gl_renderer is None
        assert r._gl_init_attempted is False

    def test_draw_failure_disables_svs(self, tmp_path, monkeypatch, caplog):
        """A GL draw failure permanently disables the SVS (UNAVAIL) —
        there is no CPU fallback."""
        import pyefis.instruments.ai.svs_gl as svs_gl
        class DrawFailGL:
            def __init__(self, *a, **kw):
                pass
            def draw(self, *a, **kw):
                raise RuntimeError("simulated GL draw failure")
        monkeypatch.setattr(svs_gl, "SVSGLRenderer", DrawFailGL)
        root = _make_tile_dir(tmp_path, 32, -97, elevation=500)
        r = SVSRenderer({
            "enabled": True, "tile_path": str(root),
            "renderer": "opengl",
            "n_range": 8, "n_az": 12,        # keep the polar fallback cheap
        })
        with caplog.at_level("WARNING"):
            # Draw failures get 3 full re-init attempts (a transient
            # GL hiccup must not blank the SVS for a whole flight)
            # before the permanent UNAVAIL.
            self._draw(r)
            assert r.gl_failed is False
            assert r._gl_draw_failures == 1
            self._draw(r)
            self._draw(r)
        assert r.gl_failed is True
        assert r._gl_renderer is None
        assert any("unavail" in rec.getMessage().lower()
                   for rec in caplog.records)

    def test_failed_svs_never_retries_gl(self, tmp_path, monkeypatch):
        """Once GL has failed, repeated draws are no-ops and never
        re-attempt GL construction."""
        import pyefis.instruments.ai.svs_gl as svs_gl
        calls = {"n": 0}
        class BrokenGL:
            def __init__(self, *a, **kw):
                calls["n"] += 1
                raise RuntimeError("boom")
        monkeypatch.setattr(svs_gl, "SVSGLRenderer", BrokenGL)
        root = _make_tile_dir(tmp_path, 32, -97, elevation=500)
        r = SVSRenderer({
            "enabled": True, "tile_path": str(root),
            "n_range": 8, "n_az": 12,
        })
        for _ in range(4):
            self._draw(r)
        assert calls["n"] == 1
        assert r.gl_failed is True

    def test_init_failure_disables_svs(self, tmp_path, monkeypatch, caplog):
        """If SVSGLRenderer construction itself raises (e.g. a Qt build
        without OpenGL bindings), the SVS disables itself (UNAVAIL)
        instead of crashing."""
        import pyefis.instruments.ai.svs_gl as svs_gl

        class BrokenGL:
            def __init__(self, *a, **kw):
                raise RuntimeError("simulated missing GL bindings")
        monkeypatch.setattr(svs_gl, "SVSGLRenderer", BrokenGL)

        root = _make_tile_dir(tmp_path, 32, -97, elevation=500)
        r = SVSRenderer({
            "enabled": True, "tile_path": str(root),
            "renderer": "opengl",
            "n_range": 8, "n_az": 12,
        })
        with caplog.at_level("WARNING"):
            self._draw(r)
        assert r.gl_failed is True
        assert any("unavail" in rec.getMessage().lower()
                   for rec in caplog.records)

    def test_near_airport_cached_helper(self, tmp_path):
        """SVSRenderer.near_airport reports proximity from the airport
        db and caches the boolean for 1 s (the GL shader needs it per
        frame; sqlite per frame was measurable)."""
        class _StubDB:
            def __init__(self, hit):
                self.ready = True
                self._hit = hit
                self.calls = 0
            def airports_in_range(self, lat, lon, rng):
                self.calls += 1
                if self._hit:
                    yield ("KXYZ", lat, lon)

        r = SVSRenderer({"enabled": True, "airport_proximity_nm": 5.0})
        r.airport_db = _StubDB(True)
        assert r.near_airport(39.22, -106.87) is True
        assert r.near_airport(39.22, -106.87) is True
        assert r.airport_db.calls == 1   # second hit served from cache

        r2 = SVSRenderer({"enabled": True, "airport_proximity_nm": 5.0})
        r2.airport_db = _StubDB(False)
        assert r2.near_airport(39.22, -106.87) is False

        # Proximity disabled -> always False, no query.
        r3 = SVSRenderer({"enabled": True, "airport_proximity_nm": 0.0})
        r3.airport_db = _StubDB(True)
        assert r3.near_airport(39.22, -106.87) is False
        assert r3.airport_db.calls == 0

    def test_step7_patch_centring_keeps_aircraft_inside(self):
        """Step 7: the 2x2 patch origin chosen by ``_patch_origin_for``
        keeps the aircraft at least 0.5 deg from every patch edge so
        the GL sampler's CLAMP_TO_EDGE never lies about terrain ahead
        of the nose. Sweeping a representative grid of (lat, lon)
        positions, the worst-case edge distance must stay >= 0.5 deg."""
        from pyefis.instruments.ai.svs_gl import SVSGLRenderer
        worst = 99.0
        for ac_lat in np.arange(-2.0, 35.5, 0.1):
            for ac_lon in np.arange(-122.0, 5.5, 0.5):
                slat, slon = SVSGLRenderer._patch_origin_for(ac_lat, ac_lon)
                # Patch covers [slat, slat+2] x [slon, slon+2].
                dist = min(ac_lat - slat, slat + 2 - ac_lat,
                           ac_lon - slon, slon + 2 - ac_lon)
                worst = min(worst, dist)
                assert dist > 0.0, (
                    f"aircraft ({ac_lat}, {ac_lon}) fell outside patch "
                    f"({slat}..{slat+2}, {slon}..{slon+2})")
        assert worst >= 0.5 - 1e-6, (
            f"worst-case edge distance {worst:.4f} deg < 0.5 deg buffer; "
            f"patch centring regressed")

    def test_step7_patch_rebuilds_at_half_integer_crossings(self):
        """Step 7: as the aircraft flies steadily north across a
        half-integer-degree boundary, ``_patch_origin_for`` must change
        at exactly N + 0.5, not at integer N. This is the rebuild
        trigger."""
        from pyefis.instruments.ai.svs_gl import SVSGLRenderer
        prev = SVSGLRenderer._patch_origin_for(32.0, -97.5)
        crossings = []
        # Step in tenths from 32.0 northward across 33.0; the rebuild
        # should fire when crossing 32.5 (32 -> 33 patch start).
        for tenth in range(1, 11):
            ac_lat = 32.0 + tenth * 0.1
            origin = SVSGLRenderer._patch_origin_for(ac_lat, -97.5)
            if origin != prev:
                crossings.append((round(ac_lat, 2), prev, origin))
                prev = origin
        assert len(crossings) == 1, (
            f"expected exactly one boundary crossing between 32.0 and "
            f"33.0; got {crossings}")
        crossed_at, before, after = crossings[0]
        # We step in 0.1 increments, so the crossing is detected at the
        # first tested lat >= 32.5.
        assert 32.5 <= crossed_at <= 32.6, (
            f"rebuild should fire as ac_lat crosses 32.5; got {crossed_at}")
        assert after[0] == before[0] + 1, (
            f"patch start_lat should advance by 1 deg at the crossing; "
            f"got {before} -> {after}")

    def test_step7_negative_longitude_handled(self):
        """Step 7: negative longitudes (the western hemisphere) must
        still produce a patch that contains the aircraft. ``floor`` is
        the right choice — ``int(x)`` would round toward zero and skew
        the patch east at every western position."""
        from pyefis.instruments.ai.svs_gl import SVSGLRenderer
        # KASE (Aspen) is at lat 39.22, lon -106.87.
        slat, slon = SVSGLRenderer._patch_origin_for(39.22, -106.87)
        assert slat <= 39.22 < slat + 2
        assert slon <= -106.87 < slon + 2

    def test_step3_polar_mesh_renders(self, tmp_path):
        """Step 3 verification: with a real GL context the renderer
        draws the polar (t, az) mesh with debug colour bands. We can't
        easily pixel-match without ground-truth, so we just verify:
        (a) renderer stays in opengl mode (no fallback fired); (b) some
        non-background pixels appear in the lower half of the screen
        (where the z=0 mesh projects when looking forward at altitude).
        Skips cleanly on headless / offscreen test environments."""
        import pytest
        from PyQt6.QtGui import QImage
        root = _make_tile_dir(tmp_path, 32, -97, elevation=500)
        r = SVSRenderer({
            "enabled": True, "tile_path": str(root),
            "renderer": "opengl",
            "range_nm": 30, "auto_range": False,
        })
        img = QImage(400, 300, QImage.Format.Format_RGB32)
        img.fill(0x000000)
        painter = QPainter(img)
        try:
            r.draw(painter, 400, 300, 32.5, -96.5, 3000.0, 0.0, 0.0, 0.0, 12.0)
        finally:
            painter.end()
        if r.gl_failed or r._gl_draw_failures or r._gl_renderer is None:
            pytest.skip("no GL context in this environment (SVS UNAVAIL)")
        # At altitude with z=0 mesh, the fan should project into the
        # lower portion of the screen (just below the horizon line).
        # Walk a row of pixels there and count anything that isn't the
        # dark grey background (0x0d 0x0d 0x0d ≈ rgb 13,13,13).
        non_bg = 0
        for x in range(50, 350, 5):
            c = img.pixelColor(x, 180)   # below horizon
            if c.red() > 30 or c.green() > 30 or c.blue() > 30:
                non_bg += 1
        assert non_bg > 5, (
            f"expected polar mesh pixels below horizon; only {non_bg} "
            f"non-background samples in scan row")


# ---------------------------------------------------------------------------
# Highway terrain occlusion (issue #73)
# ---------------------------------------------------------------------------

class _StubPolyline:
    def __init__(self, vertices, fclass="motorway"):
        self.vertices = np.asarray(vertices, dtype=np.float64)
        self.fclass = fclass


class _StubHighwayDB:
    ready = True

    def __init__(self, polylines):
        self._polylines = polylines

    def polylines_in_range(self, ac_lat, ac_lon, rng):
        return list(self._polylines)


class TestHighwayOcclusion:
    """Issue #73: a road behind a ridge (no line of sight) must be DROPPED, not
    drawn over the near slope (the SVS has no depth test). Verifies the
    per-vertex LOS filtering in ``_collect_highways_sync`` — a GL_LINES pair is
    emitted only where both endpoints are visible. The LOS math itself
    (``_los_masked``) is stubbed so the segment-selection logic is tested
    deterministically without terrain tiles."""

    AC_LAT, AC_LON, AC_ALT = 39.0, -107.0, 12000.0
    # five vertices marching north, ~0.6 NM apart, midpoint within HWY_NEAR_NM
    # so no LOD decimation kicks in.
    VERTS = [(39.00 + 0.01 * i, -107.0) for i in range(5)]

    def _renderer(self, los_fn):
        r = SVSRenderer({})
        r.highway_db = _StubHighwayDB([_StubPolyline(self.VERTS)])
        r._sample_elevations = lambda lat_g, lon_g: (
            np.zeros_like(lat_g, dtype=np.float32), None)
        r._los_masked = los_fn

        # The collector now masks via the vectorised _los_masked_batch
        # (issue #74); adapt the per-vertex stub so these cases still drive it.
        def _batch(ac_lat, ac_lon, ac_alt, t_lats, t_lons, t_alts, lat_cos):
            return np.array(
                [bool(los_fn(ac_lat, ac_lon, ac_alt, float(la), float(lo),
                             float(al), lat_cos))
                 for la, lo, al in zip(t_lats, t_lons, t_alts)], dtype=bool)
        r._los_masked_batch = _batch
        return r

    def test_occluded_middle_segment_dropped(self):
        # mask only the middle vertex (lat 39.02) -> a ridge hides it
        masked = lambda *a: 39.015 < a[3] < 39.025
        arr = self._renderer(masked)._collect_highways_sync(
            self.AC_LAT, self.AC_LON, self.AC_ALT, 10.0)
        assert arr is not None
        # segments (v0,v1) and (v3,v4) survive; both touching v2 are gone
        assert arr.shape[0] == 4
        lats = {round(float(x), 2) for x in arr[:, 0]}
        assert 39.02 not in lats                 # the occluded vertex
        assert {39.00, 39.01, 39.03, 39.04} <= lats

    def test_all_visible_keeps_every_segment(self):
        arr = self._renderer(lambda *a: False)._collect_highways_sync(
            self.AC_LAT, self.AC_LON, self.AC_ALT, 10.0)
        assert arr.shape[0] == 2 * (len(self.VERTS) - 1)   # 4 segments -> 8 verts

    def test_all_occluded_returns_none(self):
        arr = self._renderer(lambda *a: True)._collect_highways_sync(
            self.AC_LAT, self.AC_LON, self.AC_ALT, 10.0)
        assert arr is None

    def test_los_batch_masks_behind_ridge(self):
        """_los_masked_batch (issue #74) — the vectorised LOS that replaced
        the per-vertex loop — masks a target a ridge hides and keeps clear
        ones, matching _los_masked's intent."""
        r = SVSRenderer({})
        r.cache = object()              # non-None so the batch proceeds

        def _sample(lat_g, lon_g):      # tall ridge spanning lat 39.04..39.06
            out = np.where((lat_g >= 39.04) & (lat_g <= 39.06), 3000.0, 0.0)
            return out.astype(np.float32), None
        r._sample_elevations = _sample

        lat_cos = float(np.cos(np.radians(39.0)))
        t_lats = np.array([39.02, 39.10, 39.03])   # front, behind ridge, front
        t_lons = np.full(3, -107.0)
        t_alts = np.zeros(3)
        masked = r._los_masked_batch(39.0, -107.0, 500.0,
                                     t_lats, t_lons, t_alts, lat_cos)
        assert list(map(bool, masked)) == [False, True, False]
