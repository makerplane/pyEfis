import importlib
from unittest import mock

import pytest
from PyQt6.QtWidgets import QApplication, QWidget


vfr_module = importlib.import_module("pyefis.instruments.ai.VirtualVfr")
VirtualVfr = vfr_module.VirtualVfr


@pytest.fixture
def app(qtbot):
    test_app = QApplication.instance()
    if test_app is None:
        test_app = QApplication([])
    return test_app


class ConfigParent(QWidget):
    def __init__(self):
        super().__init__()
        self.config = {
            "metadata": None,
            "dbpath": "/tmp/test-cifp.db",
            "indexpath": "/tmp/test-cifp.bin",
            "refresh_period": 0.25,
        }

    def get_config_item(self, key):
        return self.config.get(key)


class FakePointOfView:
    instances = []

    def __init__(self, dbpath, index_path, refresh_period):
        self.dbpath = dbpath
        self.index_path = index_path
        self.refresh_period = refresh_period
        self.initialize_calls = []
        self.update_position = mock.Mock()
        self.update_altitude = mock.Mock()
        self.update_heading = mock.Mock()
        self.render = mock.Mock()
        FakePointOfView.instances.append(self)

    def initialize(self, *args):
        self.initialize_calls.append(args)


@pytest.fixture
def fake_pov(monkeypatch):
    FakePointOfView.instances = []
    monkeypatch.setattr(vfr_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(vfr_module, "PointOfView", FakePointOfView)
    return FakePointOfView


def _set_vfr_values(fix, lat=39.99, lng=-82.89, altitude=910, course=281.8):
    fix.db.set_value("LAT", lat)
    fix.db.set_value("LONG", lng)
    fix.db.set_value("ALT", altitude)
    fix.db.set_value("COURSE", course)


def _show_widget(qtbot, widget, width=320, height=240):
    qtbot.addWidget(widget)
    widget.resize(width, height)
    widget.show()
    qtbot.waitExposed(widget)


def _make_widget(fix, fake_pov, qtbot, width=320, height=240):
    _set_vfr_values(fix)
    parent = ConfigParent()
    widget = VirtualVfr(font_percent=0.15)
    widget.myparent = parent
    _show_widget(qtbot, widget, width, height)
    return widget, parent, fake_pov.instances[-1]


def test_virtualvfr_resize_initializes_pov_and_renders_when_data_is_good(
    fix, fake_pov, qtbot
):
    widget, _parent, pov = _make_widget(fix, fake_pov, qtbot)

    assert pov.dbpath == "/tmp/test-cifp.db"
    assert pov.index_path == "/tmp/test-cifp.bin"
    assert pov.refresh_period == 0.25
    assert pov.initialize_calls == [
        (
            ["Runway", "Airport"],
            widget.scene.width(),
            widget.lng,
            widget.lat,
            widget.altitude,
            widget.true_heading,
        )
    ]
    pov.update_heading.assert_called_once_with(281.8)
    assert pov.render.call_count == 2
    pov.render.assert_has_calls([mock.call(widget), mock.call(widget)])
    assert widget.rendering_prohibited() is False


def test_virtualvfr_fix_setters_update_pov_and_skip_rendering_when_blank(
    fix, fake_pov, qtbot
):
    widget, _parent, pov = _make_widget(fix, fake_pov, qtbot)
    pov.render.reset_mock()
    widget.update = mock.Mock()

    widget.setLatitude(40.1)
    assert widget.lat == 40.1
    assert widget.missing_lat is False
    pov.update_position.assert_called_with(40.1, widget.lng)
    pov.render.assert_called_once_with(widget)
    widget.update.assert_called_once_with()

    widget.setLngFail(True)
    pov.render.reset_mock()
    widget.update.reset_mock()

    widget.setLongitude(-83.2)
    widget.setAltitude(1200)
    widget.setHeading(35)

    assert widget.lng == -83.2
    assert widget.altitude == 1200
    pov.update_position.assert_any_call(widget.lat, -83.2)
    pov.update_altitude.assert_called_once_with(1200)
    pov.update_heading.assert_called_with(35)
    pov.render.assert_not_called()
    widget.update.assert_not_called()


def test_virtualvfr_quality_flags_clear_vfr_objects_and_drive_blank_state(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)
    runway = widget.scene.addRect(0, 0, 20, 20)
    light = widget.scene.addEllipse(0, 0, 5, 5)
    widget.display_objects = {"runway": runway, "papi": [light]}

    widget.setLatBad(True)

    assert widget.getVfrBad() is True
    assert widget.rendering_prohibited() is True
    assert widget.display_objects == {}
    assert runway.scene() is None
    assert light.scene() is None

    widget.setLatBad(False)
    widget.setHeadOld(True)
    assert widget.getVfrOld() is True

    widget.setHeadOld(False)
    widget.setAltFail(True)
    assert widget.getVfrFail() is True


def test_virtualvfr_runway_render_creates_updates_and_eliminates_scene_items(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot, width=360, height=260)
    widget.gsi = True
    widget.gsi_item.output_value = mock.Mock()

    widget.render_runway(
        (-40, 80),
        (40, 80),
        (-30, -120),
        (30, -120),
        touchdown_distance=10000,
        elevation=0,
        length=5000,
        bearing=90,
        name="RW09L",
        airport_id="KCMH",
        zoom=100,
    )

    expected_keys = {
        "RW09LKCMH",
        "RW09LKCMH_c",
        "RW09LKCMH_e",
        "RW09LKCMH_p",
        "RW09LKCMH09L",
    }
    assert expected_keys.issubset(widget.display_objects)
    assert len(widget.display_objects["RW09LKCMH_p"]) == 4
    assert widget.gsi_item.value == pytest.approx(1.0)
    widget.gsi_item.output_value.assert_called_once_with()

    runway_item = widget.display_objects["RW09LKCMH"]
    old_polygon = runway_item.polygon()
    widget.render_runway(
        (-50, 90),
        (50, 90),
        (-25, -130),
        (25, -130),
        touchdown_distance=10000,
        elevation=0,
        length=5000,
        bearing=90,
        name="RW09L",
        airport_id="KCMH",
        zoom=100,
    )

    assert widget.display_objects["RW09LKCMH"] is runway_item
    assert runway_item.polygon() != old_polygon

    papi_lights = widget.display_objects["RW09LKCMH_p"]
    widget.eliminate_runway("RW09L", "KCMH")

    assert not any(key.startswith("RW09LKCMH") for key in widget.display_objects)
    assert runway_item.scene() is None
    assert all(light.scene() is None for light in papi_lights)


def test_virtualvfr_airport_labels_respect_occupied_space(fix, fake_pov, qtbot):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)

    rect = widget.render_airport((0, 0), "Port Columbus", "KCMH", 100, [])
    blocked = widget.render_airport((0, 0), "Nearby", "KZZZ", 100, [rect])

    assert rect is not None
    assert blocked is None
    assert "KCMH" in widget.display_objects
    assert "KZZZ" not in widget.display_objects


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("RW09L", ["09L", "27R"]),
        ("RW36", ["36", "18"]),
        ("RW18W", ["18W", "36W"]),
    ],
)
def test_virtualvfr_runway_label_reciprocals(fix, fake_pov, qtbot, name, expected):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)

    assert widget.get_runway_labels(name) == expected


def test_virtualvfr_geometry_helpers_cover_vertical_and_diagonal_lines():
    assert vfr_module.get_line([(4, 1), (4, 9)]) == (float("inf"), 0)
    assert vfr_module.F(10, (float("inf"), 0)) == float("inf")

    line = vfr_module.get_line([(0, 2), (4, 10)])
    assert line == pytest.approx((2, 2))
    assert vfr_module.F(6, line) == pytest.approx(14)

    distance, rel_lng = vfr_module.Distance([(-82, 40), (-81, 41)])
    assert distance > 60
    assert rel_lng == pytest.approx(vfr_module.GetRelLng(40 * vfr_module.M_PI / 180.0))
