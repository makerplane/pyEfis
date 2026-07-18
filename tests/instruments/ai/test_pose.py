"""Unit tests for the AI frame-clock pose interpolator (pose.py, P4)."""

import pytest

from pyefis.instruments.ai.pose import PoseSource


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


@pytest.fixture
def clk():
    return FakeClock()


@pytest.fixture
def pose(clk):
    return PoseSource(time_fn=clk)


class TestPoseSource:
    def test_no_data_returns_none(self, pose):
        assert pose.sample() is None

    def test_raw_position_without_dynamics(self, pose, clk):
        pose.set_position(32.9, -97.04)
        pose.set_altitude(2500.0)
        clk.t += 0.5
        lat, lon, alt = pose.sample()
        assert lat == 32.9 and lon == -97.04 and alt == 2500.0

    def test_dead_reckons_east_at_120kt(self, pose, clk):
        pose.set_position(32.9, -97.0)
        pose.set_dynamics(gs_kt=120.0, track_deg=90.0)
        clk.t += 0.5   # 120 kt for 0.5 s = 1/60 NM east
        lat, lon, _ = pose.sample()
        assert lat == pytest.approx(32.9, abs=1e-9)
        import math
        expect = (120.0 * 0.5 / 3600.0) / 60.0 / math.cos(math.radians(32.9))
        assert lon - (-97.0) == pytest.approx(expect, rel=1e-6)

    def test_dead_reckons_north(self, pose, clk):
        pose.set_position(32.9, -97.0)
        pose.set_dynamics(gs_kt=120.0, track_deg=0.0)
        clk.t += 1.0
        lat, lon, _ = pose.sample()
        assert lon == pytest.approx(-97.0, abs=1e-9)
        assert lat - 32.9 == pytest.approx((120.0 / 3600.0) / 60.0, rel=1e-6)

    def test_extrapolation_caps_then_holds(self, pose, clk):
        pose.set_position(32.9, -97.0)
        pose.set_dynamics(gs_kt=120.0, track_deg=0.0)
        clk.t += 2.0
        lat_at_cap, _, _ = pose.sample()
        clk.t += 1.0   # stale (within stale_s=5 though) — capped at 2 s
        lat_later, _, _ = pose.sample()
        assert lat_later == pytest.approx(lat_at_cap, abs=1e-12)

    def test_fresh_fix_resets_baseline(self, pose, clk):
        pose.set_position(32.9, -97.0)
        pose.set_dynamics(gs_kt=120.0, track_deg=0.0)
        clk.t += 1.0
        pose.set_position(32.91, -97.0)   # new GPS fix
        lat, _, _ = pose.sample()
        assert lat == pytest.approx(32.91, abs=1e-9)

    def test_failed_gs_disables_position_extrapolation(self, pose, clk):
        pose.set_position(32.9, -97.0)
        pose.set_dynamics(gs_kt=120.0, track_deg=0.0)
        pose.set_fail("GS", True)
        clk.t += 1.0
        lat, lon, _ = pose.sample()
        assert lat == 32.9 and lon == -97.0

    def test_old_dynamics_still_extrapolate(self, pose, clk):
        # Change-driven sources publish GS/TRACK only when they change;
        # steady-flight values minutes old are normal and must keep
        # the dead reckoning alive (the 2 s cap bounds the risk).
        pose.set_position(32.9, -97.0)
        pose.set_dynamics(gs_kt=120.0, track_deg=0.0)
        clk.t += 60.0
        pose.set_position(32.9, -97.0)   # fresh fix, old dynamics
        clk.t += 1.0
        lat, _, _ = pose.sample()
        assert lat - 32.9 == pytest.approx((120.0 / 3600.0) / 60.0,
                                           rel=1e-6)

    def test_altitude_extrapolates_from_vs(self, pose, clk):
        pose.set_position(32.9, -97.0)
        pose.set_altitude(2500.0)
        pose.set_dynamics(vs_fpm=600.0)
        clk.t += 1.0
        _, _, alt = pose.sample()
        assert alt == pytest.approx(2510.0)   # 600 fpm for 1 s
