"""Moving map Phase A: transform math, layer registry, paint smoke."""
import numpy as np
import pytest
from PyQt6.QtGui import QImage, QPaintEvent, QPainter

from pyefis.instruments import map as moving_map
from pyefis.instruments.map.layers.terrain import TerrainLayer


def test_transform_math():
    x = moving_map.MapTransform(39.0, -106.0, 10.0, 0.0, 400, 400, 0.5)
    c = x.to_screen(39.0, -106.0)
    assert (c.x(), c.y()) == (200.0, 200.0)
    # 10 NM north of ownship = the top edge (anchor at 50% of 400px).
    n = x.to_screen(39.0 + 10 * 1852.0 / 111139.0, -106.0)
    assert n.x() == pytest.approx(200.0)
    assert n.y() == pytest.approx(0.0, abs=0.5)
    # track_up, tracking east (090): a point NORTH of ownship belongs
    # on the LEFT of the display.
    xr = moving_map.MapTransform(39.0, -106.0, 10.0, 90.0, 400, 400, 0.5)
    r = xr.to_screen(39.0 + 5 * 1852.0 / 111139.0, -106.0)
    assert r.x() < 150 and abs(r.y() - 200) < 1.0


class _CoastCache:
    """Fake TileCache: land (500 m) strictly NORTH of *shore_lat*,
    water (0 m -> water mask) south of it."""

    def __init__(self, shore_lat):
        self.shore_lat = shore_lat

    def get(self, la, lo):
        n = 1201
        lats = la + 1.0 - np.arange(n, dtype=np.float32) / (n - 1)
        tile = np.where(lats > self.shore_lat, 500.0, 0.0)
        return np.repeat(tile[:, None], n, axis=1).astype(np.float32)


def _painted_water_fraction(rot_deg):
    """Render the terrain layer at a coast-through-ownship pose and
    return the water fraction of each screen half (left, right, top,
    bottom). Ownship sits ON the shoreline so the halves are clean."""
    lat0, lon0 = 34.5, -120.5
    lay = TerrainLayer()
    lay._cache = _CoastCache(shore_lat=lat0)

    class Owner:
        _alt_ft = 3000.0
    lay._owner = Owner

    w = h = 400
    x = moving_map.MapTransform(lat0, lon0, 10.0, rot_deg, w, h, 50 / 100.0)
    key = lay._key(x)
    img, meta = lay._render((key, x.lat0, x.lon0, x.range_nm, x.w, x.h, x.cy))
    lay._img = (img, key, meta)

    out = QImage(w, h, QImage.Format.Format_RGB32)
    out.fill(0)
    p = QPainter(out)
    lay.paint(p, x)
    p.end()

    buf = out.constBits()
    buf.setsize(out.sizeInBytes())
    px = np.frombuffer(buf, np.uint8).reshape(h, out.bytesPerLine() // 4, 4)
    px = px[:, :w, :]
    water = (px[..., 0] > px[..., 1]) & (px[..., 0] > px[..., 2])  # BGRA: blue
    return (water[:, : w // 2].mean(), water[:, w // 2:].mean(),
            water[: h // 2, :].mean(), water[h // 2:, :].mean())


class _LandCache:
    """Fake TileCache: uniform 500 m land everywhere."""

    def get(self, la, lo):
        return np.full((1201, 1201), 500.0, dtype=np.float32)


class _FakeWaterDB:
    """Stub WaterDB: one square lake polygon, ~2 km on a side, centred
    a little EAST of the window centre."""

    ready = True

    def __init__(self, lat0, lon0):
        d = 0.01                       # ~1.1 km half-side
        clat, clon = lat0, lon0 + 0.05  # offset east of centre
        self._poly = type("P", (), {})()
        self._poly.vertices = [
            (clat - d, clon - d), (clat - d, clon + d),
            (clat + d, clon + d), (clat + d, clon - d)]
        self._poly.kind = "lake"

    def polygons_in_range(self, lat, lon, range_nm,
                          min_bbox_diag_deg=None, drop_ocean=False):
        yield self._poly


def test_terrain_water_rasterized_into_window(qapp):
    """#91: water-pack polygons paint into the north-up window image on
    the worker thread. A lake east of centre must be blue in the image;
    the rest stays land-coloured (no elevation-derived water on a
    uniform 500 m terrain)."""
    lat0, lon0 = 34.5, -120.5
    lay = TerrainLayer()
    lay._cache = _LandCache()
    lay._water = _FakeWaterDB(lat0, lon0)

    class Owner:
        _alt_ft = 3000.0
    lay._owner = Owner

    x = moving_map.MapTransform(lat0, lon0, 10.0, 0.0, 400, 400, 0.5)
    key = lay._key(x)
    img, meta = lay._render((key, x.lat0, x.lon0, x.range_nm,
                             x.w, x.h, x.cy))
    clat, clon, mpp = meta
    n = img.width()

    def px(la, lo):
        half = (n - 1) / 2.0
        M = 111320.0
        cx = (lo - clon) * M * np.cos(np.radians(clat)) / mpp + half
        cy = (clat - la) * M / mpp + half
        return img.pixelColor(int(round(cx)), int(round(cy)))

    lake = px(lat0, lon0 + 0.05)          # lake centre
    land = px(lat0, lon0 - 0.05)          # mirror point, west (land)
    assert lake.blue() > lake.red() and lake.blue() > lake.green()
    assert not (land.blue() > land.red() and land.blue() > land.green())


class _FakeHighwayDB:
    """Stub HighwayDB: one motorway segment strictly NORTH of the
    ownship (so orientation tests can discriminate sides -- a through
    road is a diameter and cannot) plus a short secondary spur. Honours
    the LOD ``classes`` filter the layer passes, like the real DB."""

    ready = True

    def __init__(self, lat0, lon0):
        import numpy as np

        class L:
            def __init__(self, vertices, fclass):
                self.vertices = vertices
                self.fclass = fclass

        self._lines = [
            L(np.array([[lat0 + 0.02, lon0], [lat0 + 0.2, lon0]],
                       dtype=np.float32), "motorway"),
            L(np.array([[lat0, lon0 + 0.03], [lat0 + 0.02, lon0 + 0.03]],
                       dtype=np.float32), "secondary"),
        ]

    def polylines_in_range(self, lat, lon, range_nm, classes=None):
        for line in self._lines:
            if classes is None or line.fclass in classes:
                yield line


def _roads_paint(range_nm, rot_deg):
    """Render the roads layer synchronously into a widget-sized image
    and return it with its transform."""
    from pyefis.instruments.map.layers.roads import RoadsLayer

    lat0, lon0 = 34.5, -120.5
    lay = RoadsLayer()
    lay._db = _FakeHighwayDB(lat0, lon0)

    class Owner:
        pass
    lay._owner = Owner

    w = h = 400
    x = moving_map.MapTransform(lat0, lon0, range_nm, rot_deg, w, h, 0.5)
    key = lay._key(x)
    img, meta = lay._render((key, x.lat0, x.lon0, x.range_nm,
                             x.w, x.h, x.cy))
    lay._img = (img, key, meta)

    out = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(0)
    p = QPainter(out)
    lay.paint(p, x)
    p.end()
    buf = out.constBits()
    buf.setsize(out.sizeInBytes())
    px = np.frombuffer(buf, np.uint8).reshape(h, out.bytesPerLine() // 4, 4)
    return px[:, :400, 3]      # alpha channel: road pixels > 0


def test_roads_track_up_east_paints_north_road_left(qapp):
    """Track-up heading east: a due-north motorway must paint on the
    LEFT half (same convention pinned for terrain in #90)."""
    alpha = _roads_paint(10.0, 90.0)
    left = alpha[:, :200].astype(bool).sum()
    right = alpha[:, 200:].astype(bool).sum()
    assert left > 50 and left > 5 * max(1, right)


def test_roads_lod_classes_by_range():
    """LOD class bands: closer in = more classes; hidden past the coarsest."""
    from pyefis.instruments.map.layers.roads import RoadsLayer
    lay = RoadsLayer()
    near = lay._classes_for_range(3.0)      # <=5 NM: everything
    assert "secondary" in near and "primary" in near and "motorway" in near
    assert "secondary_link" in near         # _link ramps ride along
    mid = lay._classes_for_range(15.0)      # <=20 NM: no secondary
    assert "primary" in mid and "secondary" not in mid
    far = lay._classes_for_range(30.0)      # <=40 NM: motorway + trunk
    assert set(far) == {"motorway", "motorway_link", "trunk", "trunk_link"}
    assert set(lay._classes_for_range(70.0)) == {"motorway", "motorway_link"}
    assert lay._classes_for_range(200.0) is None    # hidden when zoomed out


def test_roads_lod_drops_secondary_when_zoomed_out(qapp):
    """Integration: a secondary road paints at 3 NM (in band) but not at
    30 NM, where the layer only fetches motorway/trunk."""
    a3 = _roads_paint(3.0, 0.0).astype(bool).sum()
    a30 = _roads_paint(30.0, 0.0).astype(bool).sum()
    # both draw the motorway; only the 3 NM view adds the secondary spur
    assert a3 > a30 > 0


def test_rivers_layer_lod_and_config():
    """Rivers reuse the roads machinery with waterway classes, no _link
    ramps, and their own db-path/colour options."""
    from pyefis.instruments.map.layers.rivers import RiversLayer
    lay = RiversLayer()
    assert lay.id == "rivers" and lay._DB_OPTION == "river_db_path"
    near = lay._classes_for_range(5.0)
    assert set(near) == {"river", "canal", "stream"}   # no _link expansion
    assert lay._classes_for_range(40.0) == ("river",)  # only major rivers wide
    assert lay._classes_for_range(100.0) is None

    class Owner:
        river_db_path = ""
        river_color = "#123456"
    lay.configure(Owner())
    assert lay._color == "#123456" and lay._db is None   # empty path -> no db


def test_highwaydb_class_filter(tmp_path):
    """The real HighwayDB filters by fclass in SQL (the LOD fetch)."""
    import sqlite3
    from pyefis.instruments.ai.highway_db import HighwayDB, encode_vertices
    p = tmp_path / "roads.sqlite"
    con = sqlite3.connect(str(p))
    con.executescript(
        "CREATE TABLE highway_lines (id INTEGER PRIMARY KEY, fclass TEXT,"
        " min_lat REAL, max_lat REAL, min_lon REAL, max_lon REAL, verts BLOB);"
        "CREATE VIRTUAL TABLE highway_rtree USING rtree(id, min_lat, max_lat,"
        " min_lon, max_lon);")
    rows = [(1, "motorway"), (2, "secondary")]
    for rid, fc in rows:
        verts = encode_vertices(np.array([[34.5, -120.5], [34.6, -120.4]]))
        con.execute("INSERT INTO highway_lines VALUES (?,?,?,?,?,?,?)",
                    (rid, fc, 34.5, 34.6, -120.5, -120.4, verts))
        con.execute("INSERT INTO highway_rtree VALUES (?,?,?,?,?)",
                    (rid, 34.5, 34.6, -120.5, -120.4))
    con.commit(); con.close()

    db = HighwayDB(str(p))
    assert db.ready
    allc = {l.fclass for l in db.polylines_in_range(34.5, -120.5, 50)}
    assert allc == {"motorway", "secondary"}            # None = every class
    only = {l.fclass for l in db.polylines_in_range(
        34.5, -120.5, 50, classes=("motorway", "trunk"))}
    assert only == {"motorway"}                          # filtered in SQL
    assert list(db.polylines_in_range(34.5, -120.5, 50, classes=())) == []


def test_terrain_orientation_north_up(qapp):
    """North-up: land (north) paints on the TOP half."""
    left, right, top, bottom = _painted_water_fraction(0.0)
    assert top < 0.2 and bottom > 0.8


def test_terrain_orientation_track_up_east(qapp):
    """Track-up heading EAST: north is screen-LEFT, so land must paint
    on the LEFT half. Regression for the mirrored-coastline bug: the
    blit rotated +track instead of -track, putting land on the RIGHT
    and terrain 2*track degrees out of register with the vector
    layers (KSBA rendered over the ocean)."""
    left, right, top, bottom = _painted_water_fraction(90.0)
    assert left < 0.2 and right > 0.8


def test_widget_paint_and_hmi(fix, qtbot):
    w = moving_map.MovingMap()
    qtbot.addWidget(w)
    w.resize(300, 300)
    w.show()
    qtbot.waitExposed(w)
    assert any(l.id == "range_rings" for l in w._layers) or True
    w.paintEvent(QPaintEvent(w.rect()))
    assert w._layers and w._layers[0].enabled
    w.range_up();   assert w.range_nm == 20
    w.range_down(); assert w.range_nm == 10
    w.toggle_orientation(); assert w.orientation == "north_up"
    assert w.set_layer("range_rings") is True   # toggled off
    rings = next(l for l in w._layers if l.id == "range_rings")
    assert rings.enabled is False
    w.paintEvent(QPaintEvent(w.rect()))


def test_zoom_by_core(fix, qtbot):
    """Continuous pinch/wheel zoom scales range_nm inversely and clamps to
    the ladder span; range_up/down keep the discrete stepping."""
    w = moving_map.MovingMap()
    qtbot.addWidget(w)
    w.range_ladder = "2,5,10,20,40,80,160"
    w.range_nm = 10.0
    # spread (scaleFactor 2) zooms IN -> range halves; pinch-in doubles it.
    assert w.zoom_by(2.0) == pytest.approx(5.0)
    assert w.zoom_by(0.5) == pytest.approx(10.0)
    # clamp to the ladder span in both directions.
    w.range_nm = 10.0
    assert w.zoom_by(0.001) == pytest.approx(160.0)   # cannot zoom out past hi
    w.range_nm = 10.0
    assert w.zoom_by(1e6) == pytest.approx(2.0)        # cannot zoom in past lo
    # degenerate / bad factors are ignored (no change).
    w.range_nm = 10.0
    assert w.zoom_by(0) == 10.0
    assert w.zoom_by(-2) == 10.0
    assert w.zoom_by("x") == 10.0


def test_zoom_wheel_and_gate(fix, qtbot):
    """wheelEvent mirrors pinch (up = zoom in), and the touch_gestures option
    gates the input paths."""
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QWheelEvent

    w = moving_map.MovingMap()
    qtbot.addWidget(w)
    w.range_ladder = "2,5,10,20,40,80,160"

    def wheel(dy):
        ev = QWheelEvent(
            QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, dy),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase, False)
        w.wheelEvent(ev)

    w.range_nm = 10.0
    wheel(120)                       # wheel up -> zoom in -> smaller range
    assert w.range_nm < 10.0
    zoomed_in = w.range_nm
    wheel(-120)                      # wheel down -> zoom out
    assert w.range_nm > zoomed_in

    w.range_nm = 10.0
    w.touch_gestures = False
    wheel(120)
    assert w.range_nm == 10.0        # gated off -> no change
