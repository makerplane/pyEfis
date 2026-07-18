"""
Pose interpolation for the AI / SVS frame clock (plan P4).

GPS position arrives at 1-10 Hz; the display renders at 30 Hz. Without
interpolation the terrain visibly steps forward at the data rate.
PoseSource timestamps each position update and dead-reckons between
them using groundspeed/track (and vertical speed for altitude), so the
frame clock can sample a smooth pose every tick.

Pure Python, no Qt — unit-testable with a fake clock. Attitude is NOT
handled here: AHRS pitch/roll/heading arrive at or above display rate
and pass straight through the AI widget's attributes.
"""

import math
import time

NM_PER_DEG = 60.0


class PoseSource:
    """Timestamped position state with dead-reckoned sampling.

    ``set_position`` / ``set_altitude`` record the latest GPS/baro
    values; ``set_dynamics`` records groundspeed (kt), track (deg true)
    and vertical speed (ft/min); ``sample()`` returns (lat, lon, alt_ft)
    extrapolated from the last fix by the elapsed time.

    Extrapolation is capped at ``extrap_cap_s`` (then the pose holds),
    and disabled when a dynamics input is flagged failed. Dynamics are
    deliberately NOT staleness-gated: change-driven sources publish GS
    and TRACK only when they move, so "old" steady-flight values are
    normal — the position cap already bounds how far a wrong speed can
    carry the pose.
    """

    def __init__(self, extrap_cap_s=2.0, time_fn=time.monotonic):
        self._now = time_fn
        self.extrap_cap_s = float(extrap_cap_s)
        self._lat = None
        self._lon = None
        self._alt = None
        self._t_pos = 0.0
        self._t_alt = 0.0
        self._gs = None
        self._track = None
        self._vs = None
        self._t_dyn = 0.0
        self._fail = {}

    # ------------------------------------------------------------------
    def set_position(self, lat, lon):
        self._lat = float(lat)
        self._lon = float(lon)
        self._t_pos = self._now()

    def set_altitude(self, alt_ft):
        self._alt = float(alt_ft)
        self._t_alt = self._now()

    def set_dynamics(self, gs_kt=None, track_deg=None, vs_fpm=None):
        if gs_kt is not None:
            self._gs = float(gs_kt)
        if track_deg is not None:
            self._track = float(track_deg)
        if vs_fpm is not None:
            self._vs = float(vs_fpm)
        self._t_dyn = self._now()

    def set_fail(self, key, failed):
        """Mark a dynamics input (GS / TRACK / VS) failed — failed
        inputs disable the extrapolation that depends on them."""
        self._fail[key] = bool(failed)

    # ------------------------------------------------------------------
    def _dyn_ok(self, *keys):
        return not any(self._fail.get(k, False) for k in keys)

    def sample(self, now=None):
        """Return (lat, lon, alt_ft) for *now*, or None when no
        position has ever been received. Fields with no data return
        the raw stored value (alt may be None)."""
        if self._lat is None or self._lon is None:
            return None
        if now is None:
            now = self._now()

        lat, lon = self._lat, self._lon
        if (self._gs is not None and self._track is not None
                and self._dyn_ok("GS", "TRACK")):
            dt = min(max(now - self._t_pos, 0.0), self.extrap_cap_s)
            d_deg = (self._gs * dt / 3600.0) / NM_PER_DEG
            tr = math.radians(self._track)
            lat = lat + d_deg * math.cos(tr)
            lat_cos = max(math.cos(math.radians(lat)), 1e-6)
            lon = lon + d_deg * math.sin(tr) / lat_cos

        alt = self._alt
        if (alt is not None and self._vs is not None
                and self._dyn_ok("VS")):
            dt = min(max(now - self._t_alt, 0.0), self.extrap_cap_s)
            alt = alt + self._vs * dt / 60.0

        return lat, lon, alt
