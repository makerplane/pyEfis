"""Unit tests for the unified SVS camera (camera.py, plan P3)."""

import math
import pytest

from pyefis.instruments.ai.camera import (
    view_projection, project, M_PER_DEG_LAT, DEG_PER_RAD, EARTH_CURVATURE,
)

PPD = 12.0
W, H = 800, 600


def _vp(heading=0.0, pitch=0.0, roll=0.0, ac=(0.0, 0.0, 300.0)):
    return view_projection(ac[0], ac[1], ac[2], heading, pitch, roll,
                           PPD, W, H)


class TestViewProjection:
    def test_point_dead_ahead_at_eye_level_is_screen_centre(self):
        vp = _vp()
        x, y, w = project(vp, 0.0, 5000.0, 300.0)
        assert w == pytest.approx(5000.0)
        assert x == pytest.approx(0.0, abs=1e-9)
        assert y == pytest.approx(0.0, abs=1e-9)

    def test_point_behind_has_negative_w(self):
        vp = _vp()
        _, _, w = project(vp, 0.0, -5000.0, 300.0)
        assert w < 0

    def test_small_angle_matches_pixels_per_deg(self):
        # A point 1 degree right of the nose must land ppd pixels right
        # of centre (the AI's screen-scale contract).
        vp = _vp()
        d = 5000.0
        r = d * math.tan(math.radians(1.0))
        x, _, w = project(vp, r, d, 300.0)
        px = (x / w) * (W / 2.0)
        assert px == pytest.approx(PPD * 1.0, rel=1e-3)

    def test_heading_rotates_world(self):
        # Heading 090: a point due east is dead ahead.
        vp = _vp(heading=90.0)
        x, y, w = project(vp, 5000.0, 0.0, 300.0)
        assert w == pytest.approx(5000.0)
        assert x == pytest.approx(0.0, abs=1e-9)

    def test_pitch_up_moves_ground_point_down_screen(self):
        x0, y0, w0 = project(_vp(), 0.0, 5000.0, 0.0)      # ground ahead
        x1, y1, w1 = project(_vp(pitch=10.0), 0.0, 5000.0, 0.0)
        assert y1 / w1 < y0 / w0   # NDC y is positive-up

    def test_roll_rotates_screen(self):
        # Right-of-nose point, 30 deg right roll: screen x shrinks by
        # cos(30), picks up a y component.
        vp = _vp(roll=30.0)
        d, r = 5000.0, 500.0
        x, y, w = project(vp, r, d, 300.0)
        x_flat, _, _ = project(_vp(), r, d, 300.0)
        assert x == pytest.approx(x_flat * math.cos(math.radians(30.0)),
                                  rel=1e-6)
        assert y != pytest.approx(0.0)

    def test_translation_is_aircraft_relative(self):
        vp = view_projection(1000.0, 2000.0, 300.0, 0.0, 0.0, 0.0,
                             PPD, W, H)
        x, y, w = project(vp, 1000.0, 7000.0, 300.0)
        assert w == pytest.approx(5000.0)
        assert x == pytest.approx(0.0, abs=1e-9)

    def test_curvature_constant_drops_about_right(self):
        # ~50 NM: the geometric drop is ~676 m (2,200 ft).
        d = 50.0 * 1852.0
        assert d * d * EARTH_CURVATURE == pytest.approx(672.7, rel=0.01)
