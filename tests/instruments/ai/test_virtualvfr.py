import importlib
from unittest import mock

import pytest
import yaml
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QGraphicsView, QWidget


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


class RenderableObject:
    def __init__(self, obj_type, lat=0, lng=0, rect=None):
        self.obj_type = obj_type
        self.lat = lat
        self.lng = lng
        self.rect = rect
        self.render = mock.Mock(return_value=rect)

    def typestr(self):
        return self.obj_type


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


def test_virtualvfr_resize_uses_next_metadata_paths_when_current_is_expired(
    fix, fake_pov, qtbot, tmp_path
):
    metadata_path = tmp_path / "metadata.yaml"
    metadata_path.write_text(
        yaml.safe_dump(
            {
                "current_expires": {"year": 2025, "month": 1, "day": 1},
                "next_expires": {"year": 2027, "month": 1, "day": 1},
            }
        )
    )
    _set_vfr_values(fix)
    parent = ConfigParent()
    parent.config["metadata"] = str(metadata_path)
    widget = VirtualVfr(font_percent=0.15)
    widget.myparent = parent

    _show_widget(qtbot, widget)

    pov = fake_pov.instances[-1]
    assert pov.dbpath == str(tmp_path / "next.db")
    assert pov.index_path == str(tmp_path / "next.bin")


def test_virtualvfr_resize_logs_when_next_metadata_is_expired(
    fix, fake_pov, qtbot, tmp_path
):
    metadata_path = tmp_path / "metadata.yaml"
    metadata_path.write_text(
        yaml.safe_dump(
            {
                "current_expires": {"year": 2024, "month": 1, "day": 1},
                "next_expires": {"year": 2025, "month": 1, "day": 1},
            }
        )
    )
    _set_vfr_values(fix)
    parent = ConfigParent()
    parent.config["metadata"] = str(metadata_path)
    widget = VirtualVfr(font_percent=0.15)
    widget.myparent = parent

    with mock.patch.object(vfr_module.log, "info") as info:
        _show_widget(qtbot, widget)

    assert fake_pov.instances[-1].dbpath == str(tmp_path / "next.db")
    info.assert_any_call("The FAA CIFP data is expired")


def test_virtualvfr_resize_keeps_configured_paths_when_metadata_file_is_missing(
    fix, fake_pov, qtbot, tmp_path
):
    _set_vfr_values(fix)
    parent = ConfigParent()
    parent.config["metadata"] = str(tmp_path / "missing.yaml")
    widget = VirtualVfr(font_percent=0.15)
    widget.myparent = parent

    _show_widget(qtbot, widget)

    pov = fake_pov.instances[-1]
    assert pov.dbpath == "/tmp/test-cifp.db"
    assert pov.index_path == "/tmp/test-cifp.bin"


@pytest.mark.parametrize(
    ("expires", "expected_file"),
    [
        ({"year": 2027, "month": 1, "day": 1}, "current"),
        ({"year": 2025, "month": 1, "day": 1}, "current"),
    ],
)
def test_virtualvfr_resize_metadata_without_next_uses_current_paths(
    fix, fake_pov, qtbot, tmp_path, expires, expected_file
):
    metadata_path = tmp_path / "metadata.yaml"
    metadata_path.write_text(yaml.safe_dump({"current_expires": expires}))
    _set_vfr_values(fix)
    parent = ConfigParent()
    parent.config["metadata"] = str(metadata_path)
    widget = VirtualVfr(font_percent=0.15)
    widget.myparent = parent

    _show_widget(qtbot, widget)

    pov = fake_pov.instances[-1]
    assert pov.dbpath == str(tmp_path / f"{expected_file}.db")
    assert pov.index_path == str(tmp_path / f"{expected_file}.bin")


def test_virtualvfr_resize_skips_initial_render_when_vfr_data_failed(
    fix, fake_pov, qtbot
):
    _set_vfr_values(fix)
    fix.db.get_item("LONG").fail = True
    parent = ConfigParent()
    widget = VirtualVfr(font_percent=0.15)
    widget.myparent = parent

    _show_widget(qtbot, widget)

    pov = fake_pov.instances[-1]
    pov.update_heading.assert_called_once_with(281.8)
    pov.render.assert_not_called()


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


def test_virtualvfr_latitude_setter_skips_rendering_when_blank(
    fix, fake_pov, qtbot
):
    widget, _parent, pov = _make_widget(fix, fake_pov, qtbot)
    widget.setLatFail(True)
    pov.render.reset_mock()
    widget.update = mock.Mock()

    widget.setLatitude(40.5)

    assert widget.lat == 40.5
    pov.update_position.assert_called_with(40.5, widget.lng)
    pov.render.assert_not_called()
    widget.update.assert_not_called()


def test_virtualvfr_good_fix_setters_render_for_longitude_altitude_and_heading(
    fix, fake_pov, qtbot
):
    widget, _parent, pov = _make_widget(fix, fake_pov, qtbot)
    pov.render.reset_mock()
    widget.update = mock.Mock()

    widget.setLongitude(-83.1)
    widget.setAltitude(1400)
    widget.setHeading(270)

    assert widget.lng == -83.1
    assert widget.missing_lng is False
    assert widget.altitude == 1400
    pov.update_position.assert_any_call(widget.lat, -83.1)
    pov.update_altitude.assert_called_once_with(1400)
    pov.update_heading.assert_called_with(270)
    assert pov.render.call_args_list == [mock.call(widget)] * 3
    assert widget.update.call_count == 3


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


def test_virtualvfr_quality_wrapper_methods_update_each_vfr_flag(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)

    widget.setLngBad(True)
    widget.setHeadBad(True)
    widget.setAltBad(True)
    assert widget._VFRBad["LONG"] is True
    assert widget._VFRBad["HEAD"] is True
    assert widget._VFRBad["ALT"] is True

    widget.setLngOld(True)
    widget.setLatOld(True)
    widget.setAltOld(True)
    assert widget._VFROld["LONG"] is True
    assert widget._VFROld["LAT"] is True
    assert widget._VFROld["ALT"] is True

    widget.setLatFail(True)
    widget.setHeadFail(True)
    widget.setAltFail(True)
    assert widget._VFRFail["LAT"] is True
    assert widget._VFRFail["HEAD"] is True
    assert widget._VFRFail["ALT"] is True


def test_virtualvfr_ai_quality_branches_update_scene_and_redraw(fix, fake_pov, qtbot):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)
    widget.redraw = mock.Mock()

    widget.setVfrBad(True, "PITCH")
    assert widget.getAIBad() is True
    widget.redraw.assert_called_once_with()

    widget.setVfrBad(False, "PITCH")
    assert widget.getAIBad() is False
    assert widget.redraw.call_count == 2

    widget.setOld(True, "ROLL")
    assert widget.getAIOld() is True
    widget.setOld(False, "ROLL")
    assert widget.getAIOld() is False

    widget.setVfrFail(True, "TAS")
    assert widget.getAIFail() is True
    assert QGraphicsView.scene(widget) == widget.fail_scene

    widget.setVfrFail(False, "TAS")
    assert widget.getAIFail() is False
    assert QGraphicsView.scene(widget) == widget.scene


def test_virtualvfr_quality_branches_cover_noop_and_remaining_fail_paths(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)
    widget.redraw = mock.Mock()

    widget.setVfrBad(True, "NOT_AI")
    widget.setOld(True, "NOT_AI")
    widget.setVfrFail(True, "NOT_AI")
    assert widget.redraw.call_count == 0

    widget.setVfrFail(True, "PITCH")
    widget.setVfrFail(True, "ROLL")
    widget.setVfrFail(False, "PITCH")

    assert widget.getAIFail() is True
    assert widget.sky_rect.brush().color() == widget.gray_sky.color()
    assert widget.land_rect.brush().color() == widget.gray_land.color()


def test_virtualvfr_fail_recovery_stays_gray_when_another_ai_failure_remains(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)
    widget.redraw = mock.Mock()
    widget._AIFail["PITCH"] = True
    widget._AIFail["ROLL"] = True

    widget.setVfrFail(False, "PITCH")

    assert widget.getAIFail() is True
    assert widget.sky_rect.brush().color() == widget.gray_sky.color()
    assert widget.land_rect.brush().color() == widget.gray_land.color()


def test_virtualvfr_quality_branches_cover_missing_ai_scene_items(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)
    widget.redraw = mock.Mock()

    sky_rect = widget.sky_rect
    del widget.sky_rect
    widget.setVfrBad(True, "PITCH")
    widget.setOld(True, "ROLL")
    widget.sky_rect = sky_rect

    fail_scene = widget.fail_scene
    del widget.fail_scene
    widget.setVfrFail(True, "TAS")
    widget.fail_scene = fail_scene

    widget.setVfrFail(True, "ROLL")
    del widget.sky_rect
    widget.setVfrFail(False, "TAS")
    widget.sky_rect = sky_rect

    widget.setVfrFail(False, "ROLL")
    widget.setVfrFail(True, "ALAT")
    del widget.sky_rect
    widget.setVfrFail(False, "ALAT")
    widget.sky_rect = sky_rect

    assert widget.redraw.call_count >= 2


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


def test_virtualvfr_runway_render_covers_hidden_water_and_reciprocal_branches(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot, width=360, height=260)
    widget.hide()

    widget.render_runway(
        (-40, 80),
        (40, 80),
        (-30, -120),
        (30, -120),
        touchdown_distance=10000,
        elevation=0,
        length=5000,
        bearing=90,
        name="RW18W",
        airport_id="KWTR",
        zoom=100,
    )

    assert "RW18WKWTR" not in widget.display_objects

    widget.show()
    qtbot.waitExposed(widget)
    widget.render_runway(
        (40, -120),
        (-40, -120),
        (30, 80),
        (-30, 80),
        touchdown_distance=10000,
        elevation=0,
        length=5000,
        bearing=90,
        name="RW18W",
        airport_id="KWTR",
        zoom=100,
    )

    runway = widget.display_objects["RW18WKWTR"]
    assert runway.brush().color() == QColor("#000070")
    assert "RW18WKWTR36W" in widget.display_objects


@pytest.mark.parametrize("altitude", [455, 577])
def test_virtualvfr_runway_render_covers_additional_papi_angles(
    fix, fake_pov, qtbot, altitude
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot, width=360, height=260)
    widget.altitude = altitude

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
        airport_id=f"KPAPI{altitude}",
        zoom=100,
    )

    assert f"RW09LKPAPI{altitude}_p" in widget.display_objects


def test_virtualvfr_runway_render_removes_existing_centerline_label_and_papi(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot, width=360, height=260)

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
        airport_id="KDEL",
        zoom=100,
    )
    assert "RW09LKDEL_c" in widget.display_objects
    assert "RW09LKDEL09L" in widget.display_objects
    assert "RW09LKDEL_e" in widget.display_objects
    assert "RW09LKDEL_p" in widget.display_objects

    widget.render_runway(
        (-1, 0),
        (1, 0),
        (-1, 0),
        (1, 0),
        touchdown_distance=10000,
        elevation=0,
        length=5000,
        bearing=90,
        name="RW09L",
        airport_id="KDEL",
        zoom=100,
    )

    assert "RW09LKDEL_c" not in widget.display_objects
    assert "RW09LKDEL09L" not in widget.display_objects
    assert "RW09LKDEL27R" not in widget.display_objects
    assert "RW09LKDEL_e" not in widget.display_objects
    assert "RW09LKDEL_p" not in widget.display_objects


def test_virtualvfr_runway_render_small_fresh_runway_and_narrow_label_noop(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot, width=360, height=260)

    widget.render_runway(
        (-1, 0),
        (1, 0),
        (-1, 0),
        (1, 0),
        touchdown_distance=10000,
        elevation=0,
        length=5000,
        bearing=90,
        name="RW09L",
        airport_id="KTINY",
        zoom=100,
    )
    assert "RW09LKTINY_c" not in widget.display_objects

    widget.min_font_width = 1000
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
        airport_id="KNOLABEL",
        zoom=100,
    )
    assert "RW09LKNOLABEL_c" in widget.display_objects
    assert "RW09LKNOLABEL09L" not in widget.display_objects


def test_virtualvfr_runway_render_removes_label_when_font_no_longer_fits(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot, width=360, height=260)

    widget.render_runway(
        (40, 80),
        (-40, 80),
        (-30, -120),
        (30, -120),
        touchdown_distance=10000,
        elevation=0,
        length=5000,
        bearing=90,
        name="RW09L",
        airport_id="KLBL",
        zoom=100,
    )
    assert "RW09LKLBL09L" in widget.display_objects

    widget.min_font_width = 100
    widget.render_runway(
        (40, 80),
        (-40, 80),
        (-30, -120),
        (30, -120),
        touchdown_distance=10000,
        elevation=0,
        length=5000,
        bearing=90,
        name="RW09L",
        airport_id="KLBL",
        zoom=100,
    )

    assert "RW09LKLBL_c" in widget.display_objects
    assert "RW09LKLBL09L" not in widget.display_objects


def test_virtualvfr_runway_render_removes_extended_line_and_papi_when_offscreen(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot, width=360, height=260)

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
        airport_id="KOFF",
        zoom=100,
    )
    assert "RW09LKOFF_e" in widget.display_objects
    assert "RW09LKOFF_p" in widget.display_objects

    widget.render_runway(
        (1000, 80),
        (1080, 80),
        (1010, -120),
        (1070, -120),
        touchdown_distance=10000,
        elevation=0,
        length=5000,
        bearing=90,
        name="RW09L",
        airport_id="KOFF",
        zoom=100,
    )

    assert "RW09LKOFF_e" not in widget.display_objects
    assert "RW09LKOFF_p" not in widget.display_objects


class NonDeletingDict(dict):
    def __delitem__(self, key):
        pass


def test_virtualvfr_eliminate_runway_covers_duplicate_extended_cleanup(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot, width=360, height=260)
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
        airport_id="KDUP",
        zoom=100,
    )
    widget.display_objects = NonDeletingDict(widget.display_objects)

    widget.eliminate_runway("RW09L", "KDUP")
    widget.display_objects = {}


def test_virtualvfr_eliminate_runway_covers_missing_and_minimal_items(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot, width=360, height=260)

    widget.eliminate_runway("RW01", "KNOPE")

    runway = widget.scene.addRect(0, 0, 20, 20)
    widget.display_objects = {"RW01KMIN": runway}

    widget.eliminate_runway("RW01", "KMIN")

    assert widget.display_objects == {}
    assert runway.scene() is None


@pytest.mark.parametrize(
    ("altitude", "expected_gsi"),
    [
        (0, pytest.approx(-1.0)),
        (550, pytest.approx(0.15, abs=0.02)),
    ],
)
def test_virtualvfr_runway_gsi_clamps_low_and_passes_midrange(
    fix, fake_pov, qtbot, altitude, expected_gsi
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot, width=360, height=260)
    widget.gsi = True
    widget.altitude = altitude
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
        airport_id=f"KGSI{altitude}",
        zoom=100,
    )

    assert widget.gsi_item.value == expected_gsi
    widget.gsi_item.output_value.assert_called_once_with()


def test_virtualvfr_airport_labels_respect_occupied_space(fix, fake_pov, qtbot):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)

    rect = widget.render_airport((0, 0), "Port Columbus", "KCMH", 100, [])
    blocked = widget.render_airport((0, 0), "Nearby", "KZZZ", 100, [rect])

    assert rect is not None
    assert blocked is None
    assert "KCMH" in widget.display_objects
    assert "KZZZ" not in widget.display_objects


def test_virtualvfr_airport_update_nonintersecting_space_and_missing_eliminate(
    fix, fake_pov, qtbot
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)

    rect = widget.render_airport((0, 0), "Port Columbus", "KCMH", 100, [])
    updated = widget.render_airport((30, 30), "Port Columbus", "KCMH", 100, [])
    blocked = widget.render_airport(
        (30, 30),
        "Nearby",
        "KZZZ",
        100,
        [QRectF(-100, -100, 1, 1), updated],
    )
    widget.eliminate_airport("KNOPE")

    assert updated is not None
    assert updated != rect
    assert blocked is None


def test_virtualvfr_navaid_render_updates_and_eliminates_items(fix, fake_pov, qtbot):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)

    widget.render_navaid((12, -8), "APE")
    icon = widget.display_objects["APE"]
    label = widget.display_objects["APE_l"]
    first_x = label.x()

    widget.render_navaid((32, 14), "APE")

    assert widget.display_objects["APE"] is icon
    assert widget.display_objects["APE_l"] is label
    assert label.x() != first_x

    widget.eliminate_navaid("APE")

    assert "APE" not in widget.display_objects
    assert "APE_l" not in widget.display_objects
    assert icon.scene() is None
    assert label.scene() is None


def test_virtualvfr_eliminate_missing_navaid_is_noop(fix, fake_pov, qtbot):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)

    widget.eliminate_navaid("NOPE")

    assert widget.display_objects == {}


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("RW09L", ["09L", "27R"]),
        ("RW27", ["27", "09"]),
        ("RW01", ["01", "19"]),
        ("RW36", ["36", "18"]),
        ("RW18W", ["18W", "36W"]),
    ],
)
def test_virtualvfr_runway_label_reciprocals(fix, fake_pov, qtbot, name, expected):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)

    assert widget.get_runway_labels(name) == expected


def test_virtualvfr_largest_font_size_respects_minimum(fix, fake_pov, qtbot):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot)

    assert widget.get_largest_font_size(1) == VirtualVfr.MIN_FONT_SIZE


def test_virtualvfr_largest_font_size_can_iterate_before_fitting(
    fix, fake_pov, qtbot, monkeypatch
):
    widget, _parent, _pov = _make_widget(fix, fake_pov, qtbot, width=400, height=1000)

    class FakeText:
        def __init__(self, _text):
            self.width = 0

        def setFont(self, font):
            self.width = font.pointSize()

        def boundingRect(self):
            return mock.Mock(width=lambda: self.width)

    monkeypatch.setattr(vfr_module, "QGraphicsSimpleTextItem", FakeText)

    old_min_size = VirtualVfr.MIN_FONT_SIZE
    VirtualVfr.MIN_FONT_SIZE = 7
    try:
        assert widget.get_largest_font_size(40) >= VirtualVfr.MIN_FONT_SIZE
    finally:
        VirtualVfr.MIN_FONT_SIZE = old_min_size


def test_virtualvfr_geometry_helpers_cover_vertical_and_diagonal_lines():
    assert vfr_module.get_line([(4, 1), (4, 9)]) == (float("inf"), 0)
    assert vfr_module.F(10, (float("inf"), 0)) == float("inf")

    line = vfr_module.get_line([(0, 2), (4, 10)])
    assert line == pytest.approx((2, 2))
    assert vfr_module.F(6, line) == pytest.approx(14)

    distance, rel_lng = vfr_module.Distance([(-82, 40), (-81, 41)])
    assert distance > 60
    assert rel_lng == pytest.approx(vfr_module.GetRelLng(40 * vfr_module.M_PI / 180.0))


def test_virtualvfr_distance_uses_supplied_relative_longitude():
    distance, rel_lng = vfr_module.Distance([(0, 0), (1, 0)], rel_lng=0.5)

    assert distance == pytest.approx(30)
    assert rel_lng == 0.5


def test_pointofview_show_filters_and_altitude_heading_updates(monkeypatch):
    monkeypatch.setattr(vfr_module.CIFPObjects, "find_objects", lambda *_args: [])
    pov = vfr_module.PointOfView("/db", "/idx", None)
    pov.update_screen = mock.Mock()
    pov.update_cache = mock.Mock()
    pov.approximate_elevation = mock.Mock(return_value=42)

    pov.initialize("Airport", 320, -82.9, 39.9, 1200, 90)
    assert pov.refresh_period == 0.1
    assert pov.show_object_types == {"Airport"}
    assert pov.elevation == 42

    pov.initialize({"Fix", "Runway"}, 320, -82.9, 39.9, 1200, 90)
    assert {"Airport", "Fix", "Runway"}.issubset(pov.show_object_types)

    pov.dont_show("Airport")
    assert "Airport" not in pov.show_object_types

    pov.dont_show(["Fix", "Runway"])
    assert pov.show_object_types == set()

    pov.update_altitude(1300)
    pov.update_heading(180)

    assert pov.altitude == 1300
    assert pov.true_heading == 180
    assert pov.update_screen.call_count == 3


def test_pointofview_update_position_refreshes_cache_elevation_and_screen():
    pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pov.update_cache = mock.Mock()
    pov.approximate_elevation = mock.Mock(return_value=710)
    pov.update_screen = mock.Mock()

    pov.update_position(40.2, -83.3)

    assert pov.gps_lat == 40.2
    assert pov.gps_lng == -83.3
    pov.update_cache.assert_called_once_with()
    assert pov.elevation == 710
    pov.update_screen.assert_called_once_with()


def test_pointofview_update_cache_matches_runways_and_purges_stale_blocks(monkeypatch):
    runway_09 = vfr_module.CIFPObjects.Runway()
    runway_09.airport_id = "KCMH"
    runway_09.name = "RW09L"
    runway_09.lat = 40
    runway_09.lng = -83
    runway_09.elevation = 800
    runway_27 = vfr_module.CIFPObjects.Runway()
    runway_27.airport_id = "KCMH"
    runway_27.name = "RW27R"
    runway_27.lat = 40.01
    runway_27.lng = -83.01
    runway_27.elevation = 810
    calls = []

    def find_objects(_dbpath, _index_path, lat, lng):
        calls.append((lat, lng))
        if (lat, lng) == (40, -83):
            return [runway_09, runway_27]
        return []

    monkeypatch.setattr(vfr_module.CIFPObjects, "find_objects", find_objects)
    pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pov.gps_lat = 40.1
    pov.gps_lng = -83.2
    pov.object_cache[(10, 10)] = ["old"]

    pov.update_cache()

    assert len(calls) == 9
    assert runway_09.matched() is True
    assert runway_27 not in pov.object_cache[(40, -83)]
    assert (10, 10) not in pov.object_cache

    calls.clear()
    pov.update_cache()
    assert calls == []


def test_pointofview_update_cache_with_prepopulated_blocks_loops_without_loading(monkeypatch):
    calls = []
    monkeypatch.setattr(
        vfr_module.CIFPObjects,
        "find_objects",
        lambda *_args: calls.append(_args) or [],
    )
    pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pov.gps_lat = 40.1
    pov.gps_lng = -83.2
    pov.object_cache = {
        (lat, lng): []
        for lat in range(39, 42)
        for lng in range(-84, -81)
    }

    pov.update_cache()

    assert calls == []


def test_pointofview_update_cache_handles_unmatched_mismatched_and_bad_runways(
    monkeypatch,
):
    class FakeRunway:
        def __init__(self, match_result=False, raises=False):
            self.match_result = match_result
            self.raises = raises

        def matched(self):
            return False

        def match(self, _other):
            if self.raises:
                raise ValueError("bad runway")
            return self.match_result

    monkeypatch.setattr(vfr_module.CIFPObjects, "Runway", FakeRunway)
    monkeypatch.setattr(vfr_module.CIFPObjects, "find_objects", lambda *_args: [])

    pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pov.object_cache = {(0, 0): [FakeRunway(False), FakeRunway(False)]}
    pov.update_cache()
    assert pov.object_cache[(0, 0)] == []

    pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pov.object_cache = {(0, 0): [FakeRunway(raises=True), FakeRunway(False)]}
    pov.update_cache()
    assert pov.object_cache[(0, 0)] == []

    pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pov.object_cache = {(0, 0): [FakeRunway(False)]}
    with mock.patch.object(vfr_module.log, "debug") as debug:
        pov.update_cache()
    assert pov.object_cache[(0, 0)] == []
    debug.assert_called_once()


def test_pointofview_approximate_elevation_uses_nearest_runway():
    far_runway = vfr_module.CIFPObjects.Runway()
    far_runway.lat = 41
    far_runway.lng = -84
    far_runway.elevation = 900
    near_runway = vfr_module.CIFPObjects.Runway()
    near_runway.lat = 40.1
    near_runway.lng = -83.1
    near_runway.elevation = 720
    pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pov.gps_lat = 40
    pov.gps_lng = -83
    pov.object_cache = {(40, -83): [far_runway, near_runway, object()]}

    assert pov.approximate_elevation() == 720


def test_pointofview_approximate_elevation_keeps_first_when_second_is_farther():
    near_runway = vfr_module.CIFPObjects.Runway()
    near_runway.lat = 40.1
    near_runway.lng = -83.1
    near_runway.elevation = 720
    far_runway = vfr_module.CIFPObjects.Runway()
    far_runway.lat = 41
    far_runway.lng = -84
    far_runway.elevation = 900
    pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pov.gps_lat = 40
    pov.gps_lng = -83
    pov.object_cache = {(40, -83): [near_runway, far_runway]}

    assert pov.approximate_elevation() == 720


def test_pointofview_render_sorts_labels_and_renders_other_objects_immediately():
    pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pov.gps_lat = 40
    pov.gps_lng = -83
    pov.display_width = 320
    pov.show_object_types = {"Airport", "Custom"}
    pov.do_render = True
    display = object()
    custom = RenderableObject("Custom", lat=40.5, lng=-83.5)
    near_airport = RenderableObject("Airport", lat=40, lng=-83, rect=QRectF(0, 0, 5, 5))
    far_airport = RenderableObject("Airport", lat=41, lng=-84, rect=None)
    hidden_fix = RenderableObject("Fix", lat=40.2, lng=-83.2)
    airport_space_snapshots = []
    near_airport.render.side_effect = (
        lambda *_args: airport_space_snapshots.append(("near", list(_args[-1])))
        or near_airport.rect
    )
    far_airport.render.side_effect = (
        lambda *_args: airport_space_snapshots.append(("far", list(_args[-1])))
        or far_airport.rect
    )
    pov.object_cache = {
        (40, -83): [far_airport, custom, hidden_fix, near_airport],
    }

    pov.render(display)

    custom.render.assert_called_once_with(pov, display, 320, (-83, 40))
    far_airport.render.assert_called_once()
    assert airport_space_snapshots == [
        ("near", []),
        ("far", [QRectF(0, 0, 5, 5)]),
    ]
    hidden_fix.render.assert_not_called()
    assert pov.do_render is False

    pov.render(display)
    assert custom.render.call_count == 1


def test_pointofview_update_screen_throttles_and_handles_poles(monkeypatch):
    pov = vfr_module.PointOfView("/db", "/idx", 100)
    pov.last_time = 1000
    monkeypatch.setattr(vfr_module.time, "time", lambda: 1000.5)

    pov.update_screen()
    assert pov.do_render is False

    pole_pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pole_pov.gps_lat = 90
    pole_pov.gps_lng = 0
    pole_pov.display_width = 320
    pole_pov.altitude = 1000
    pole_pov.update_screen()
    assert pole_pov.view_screen is None

    normal_pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    normal_pov.gps_lat = 40
    normal_pov.gps_lng = -83
    normal_pov.display_width = 320
    normal_pov.altitude = -100
    normal_pov.elevation = 500
    normal_pov.update_screen()
    assert normal_pov.view_screen is not None
    assert normal_pov.do_render is True


def test_pointofview_update_screen_can_flip_westward_yvec(monkeypatch):
    monkeypatch.setattr(vfr_module, "yvec_points_east", lambda *_args: False)
    pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pov.gps_lat = 40
    pov.gps_lng = -83
    pov.display_width = 320
    pov.altitude = 1000

    pov.update_screen()

    assert pov.view_screen is not None


def test_pointofview_point2d_returns_none_when_projection_fails():
    pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pov.gps_lat = 40
    pov.gps_lng = -83
    pov.display_width = 320
    pov.altitude = 1000
    pov.elevation = 0
    pov.update_screen()
    pov.view_screen = mock.Mock()
    pov.view_screen.point2D.side_effect = RuntimeError("projection failed")

    assert pov.point2D(40, -83, debug=True) is None


def test_pointofview_point2d_returns_projection_without_debug_logging():
    pov = vfr_module.PointOfView("/db", "/idx", 0.25)
    pov.gps_lat = 40
    pov.gps_lng = -83
    pov.display_width = 320
    pov.altitude = 1000
    pov.elevation = 0
    pov.update_screen()
    pov.view_screen = mock.Mock()
    pov.view_screen.point2D.return_value = "projected"

    assert pov.point2D(40, -83) == "projected"


class ThetaVector:
    def __init__(self, theta):
        self.theta = theta

    def __copy__(self):
        return ThetaVector(self.theta)

    def mult(self, _factor):
        pass

    def add(self, _other):
        pass

    def to_polar(self):
        return mock.Mock(theta=self.theta)


@pytest.mark.parametrize(
    ("vector_theta", "pov_theta", "expected"),
    [
        (8, 1, True),
        (-8, -1, False),
    ],
)
def test_yvec_points_east_wraps_theta_differences(vector_theta, pov_theta, expected):
    assert (
        vfr_module.yvec_points_east(
            ThetaVector(vector_theta),
            pov_position=object(),
            pov_polar=mock.Mock(theta=pov_theta),
        )
        is expected
    )
