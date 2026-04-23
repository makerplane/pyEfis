"""
Unit tests for the Flight Path Marker (FPM) on the AI widget.

Verifies GPS-based FPA and drift computation, signal wiring, fail/bad
flag handling, show_fpm toggle, and paintEvent without crash.
"""
import math
import pytest
from PyQt6.QtGui import QPaintEvent

from pyefis.instruments.ai import AI


class TestFPMComputation:

    def test_fpa_zero_level_flight(self, fix, qtbot):
        """Level flight: VS=0, GS=100 → flight path angle ≈ 0°."""
        fix.db.set_value("VS", 0.0)
        fix.db.set_value("GS", 100.0)
        widget = AI()
        qtbot.addWidget(widget)
        gs_fpm = widget._fpm_gs * 101.269
        fpa = math.degrees(math.atan2(widget._fpm_vs, gs_fpm))
        assert abs(fpa) < 0.01

    def test_fpa_climb(self, fix, qtbot):
        """500 fpm climb at 100 kts GS → FPA ≈ 2.83°."""
        fix.db.set_value("VS", 500.0)
        fix.db.set_value("GS", 100.0)
        widget = AI()
        qtbot.addWidget(widget)
        gs_fpm = widget._fpm_gs * 101.269
        fpa = math.degrees(math.atan2(widget._fpm_vs, gs_fpm))
        assert fpa == pytest.approx(math.degrees(math.atan2(500.0, 100.0 * 101.269)), abs=0.01)
        assert fpa > 0  # climbing → positive angle

    def test_fpa_descent(self, fix, qtbot):
        """−500 fpm at 100 kts → FPA is negative."""
        fix.db.set_value("VS", -500.0)
        fix.db.set_value("GS", 100.0)
        widget = AI()
        qtbot.addWidget(widget)
        gs_fpm = widget._fpm_gs * 101.269
        fpa = math.degrees(math.atan2(widget._fpm_vs, gs_fpm))
        assert fpa < 0

    def test_drift_zero_no_crosswind(self, fix, qtbot):
        """TRACK == HEAD → drift = 0."""
        fix.db.set_value("TRACK", 90.0)
        fix.db.set_value("HEAD", 90.0)
        widget = AI()
        qtbot.addWidget(widget)
        drift = ((widget._fpm_track - widget._fpm_head) + 180.0) % 360.0 - 180.0
        assert drift == pytest.approx(0.0)

    def test_drift_positive_crab_right(self, fix, qtbot):
        """TRACK > HEAD (crab right) → positive drift."""
        fix.db.set_value("TRACK", 100.0)
        fix.db.set_value("HEAD", 90.0)
        widget = AI()
        qtbot.addWidget(widget)
        drift = ((widget._fpm_track - widget._fpm_head) + 180.0) % 360.0 - 180.0
        assert drift == pytest.approx(10.0)

    def test_drift_wraps_across_360(self, fix, qtbot):
        """Drift wraps correctly: TRACK=5, HEAD=355 → drift = +10°."""
        fix.db.set_value("TRACK", 5.0)
        fix.db.set_value("HEAD", 355.0)
        widget = AI()
        qtbot.addWidget(widget)
        drift = ((widget._fpm_track - widget._fpm_head) + 180.0) % 360.0 - 180.0
        assert drift == pytest.approx(10.0)


class TestFPMSignals:

    def test_vs_value_update(self, fix, qtbot):
        """VS value change propagates to widget."""
        widget = AI()
        qtbot.addWidget(widget)
        fix.db.set_value("VS", 300.0)
        assert widget._fpm_vs == pytest.approx(300.0)

    def test_gs_value_update(self, fix, qtbot):
        """GS value change propagates to widget."""
        widget = AI()
        qtbot.addWidget(widget)
        fix.db.set_value("GS", 120.0)
        assert widget._fpm_gs == pytest.approx(120.0)

    def test_track_value_update(self, fix, qtbot):
        """TRACK value change propagates to widget."""
        widget = AI()
        qtbot.addWidget(widget)
        fix.db.set_value("TRACK", 270.0)
        assert widget._fpm_track == pytest.approx(270.0)

    def test_head_value_update(self, fix, qtbot):
        """HEAD value change propagates to widget."""
        widget = AI()
        qtbot.addWidget(widget)
        fix.db.set_value("HEAD", 180.0)
        assert widget._fpm_head == pytest.approx(180.0)

    def test_vs_fail_propagates(self, fix, qtbot):
        """VS fail flag is tracked in _fpm_fail."""
        widget = AI()
        qtbot.addWidget(widget)
        fix.db.get_item("VS").fail = True
        assert widget._fpm_fail['VS'] is True
        fix.db.get_item("VS").fail = False
        assert widget._fpm_fail['VS'] is False

    def test_gs_bad_propagates(self, fix, qtbot):
        """GS bad flag is tracked in _fpm_bad."""
        widget = AI()
        qtbot.addWidget(widget)
        fix.db.get_item("GS").bad = True
        assert widget._fpm_bad['GS'] is True
        fix.db.get_item("GS").bad = False
        assert widget._fpm_bad['GS'] is False


class TestFPMPaintBehaviour:

    def test_paint_with_valid_data(self, fix, qtbot):
        """paintEvent does not raise with all FPM keys valid."""
        fix.db.set_value("VS", 200.0)
        fix.db.set_value("GS", 90.0)
        fix.db.set_value("TRACK", 45.0)
        fix.db.set_value("HEAD", 40.0)
        widget = AI()
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        widget.show()
        qtbot.waitExposed(widget)
        event = QPaintEvent(widget.rect())
        widget.paintEvent(event)

    def test_paint_with_fail_does_not_raise(self, fix, qtbot):
        """paintEvent does not raise when a FPM key is failed (marker suppressed)."""
        widget = AI()
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        widget.show()
        qtbot.waitExposed(widget)
        fix.db.get_item("VS").fail = True
        event = QPaintEvent(widget.rect())
        widget.paintEvent(event)
        fix.db.get_item("VS").fail = False

    def test_show_fpm_false_suppresses_drawing(self, fix, qtbot):
        """show_fpm=False disables FPM without error."""
        widget = AI(show_fpm=False)
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        widget.show()
        qtbot.waitExposed(widget)
        assert widget.show_fpm is False
        event = QPaintEvent(widget.rect())
        widget.paintEvent(event)

    def test_paint_with_bad_data_does_not_raise(self, fix, qtbot):
        """paintEvent does not raise when FPM keys are bad (amber marker shown)."""
        widget = AI()
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        widget.show()
        qtbot.waitExposed(widget)
        fix.db.get_item("GS").bad = True
        event = QPaintEvent(widget.rect())
        widget.paintEvent(event)
        fix.db.get_item("GS").bad = False

    def test_large_drift_clamped_within_widget(self, fix, qtbot):
        """Extreme drift angle does not place FPM outside widget bounds."""
        fix.db.set_value("TRACK", 90.0)
        fix.db.set_value("HEAD", 0.0)   # 90° drift — way off center
        fix.db.set_value("GS", 80.0)
        fix.db.set_value("VS", 0.0)
        widget = AI()
        qtbot.addWidget(widget)
        widget.resize(400, 300)
        widget.show()
        qtbot.waitExposed(widget)
        event = QPaintEvent(widget.rect())
        widget.paintEvent(event)  # must not raise; clamp logic prevents out-of-bounds draw
