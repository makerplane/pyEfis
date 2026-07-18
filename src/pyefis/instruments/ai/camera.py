"""
Unified SVS camera (P3 of docs/svs_structural_plan.md).

One view-projection matrix, built once per frame on the CPU, consumed
by every GL shader (terrain, overlays, text). Replaces the six separate
projection implementations of the lat/lon era.

Coordinate frame: ENU metres relative to the heightmap patch origin
(its SW corner). East = (lon - origin_lon) * M_PER_DEG_LAT * cos(ac_lat),
north = (lat - origin_lat) * M_PER_DEG_LAT, up = MSL metres. The
longitude scale uses the aircraft's latitude cosine — the same factor
every projection used historically — so terrain sampling and overlay
placement agree exactly.

Screen scale preserves the AI's pixels-per-degree semantics: a point at
a small angle off the nose lands at angle_deg * ppd pixels from centre,
identical to the previous perspective shaders, so the pitch ladder and
FPM stay aligned with no AI-widget changes.

Clip space: x/y are linear in camera-frame metres (true perspective —
GL's w-divide and near-plane clipping interpolate correctly, which is
what lets the CPU near-plane clipper be deleted), w = forward distance
in the pitched frame, z = standard perspective depth over
[Z_NEAR, Z_FAR]. The terrain pass depth-tests against it to resolve
terrain SELF-occlusion (a ridge hiding the slope behind it): without
depth, within-level draw order is grid order, and terrain drawn later
paints over nearer crests — straight-edged mesh-period teeth along
every ridge silhouette ("jagged edge"). Overlays still composite in
painter's order (depth test off outside the terrain pass).
"""

import math
import numpy as np

M_PER_DEG_LAT = 111139.0
M_PER_FT = 0.3048
DEG_PER_RAD = 57.29577951308232
# Geometric earth radius; the curvature drop is d^2 * EARTH_CURVATURE.
EARTH_CURVATURE = 1.0 / (2.0 * 6371000.0)

# Depth range for the z row. Near at 2 m keeps rollout-height ground
# visible to the screen bottom; far at 800 km clears the FL450 horizon.
# 24-bit depth at this ratio resolves ~1.5 m of forward separation at
# 10 km and ~40 m at 50 km — comfortably finer than any terrain
# occlusion the eye can see at those ranges.
Z_NEAR = 2.0
Z_FAR = 800e3


def view_projection(ac_e, ac_n, ac_u, heading_deg, pitch_deg, roll_deg,
                    pixels_per_deg, viewport_w, viewport_h):
    """Build the 4x4 view-projection matrix (numpy float64, row-major)
    mapping ENU-metre world positions to GL clip space.

    Composition: translate(-aircraft) -> heading -> pitch -> roll ->
    pixel scale. Signs and order match the proven Phase-4b perspective
    shader exactly.
    """
    ch, sh = math.cos(math.radians(heading_deg)), math.sin(math.radians(heading_deg))
    cp, sp = math.cos(math.radians(pitch_deg)), math.sin(math.radians(pitch_deg))
    cr, sr = math.cos(math.radians(roll_deg)), math.sin(math.radians(roll_deg))

    T = np.eye(4)
    T[0, 3], T[1, 3], T[2, 3] = -ac_e, -ac_n, -ac_u

    # (e, n, u) -> (right, fwd, up)
    H = np.array([[ch, -sh, 0, 0],
                  [sh,  ch, 0, 0],
                  [0,    0, 1, 0],
                  [0,    0, 0, 1.0]])
    # pitch: positive = nose up; ground moves down-screen
    P = np.array([[1, 0,   0,  0],
                  [0, cp, sp,  0],
                  [0, -sp, cp, 0],
                  [0, 0,   0,  1.0]])
    # roll about the forward axis
    R = np.array([[cr, 0, -sr, 0],
                  [0,  1,  0,  0],
                  [sr, 0,  cr, 0],
                  [0,  0,  0,  1.0]])

    # No unit factor here: clip x/y and clip w are both in camera-frame
    # metres, so the ratio GL forms at the divide is the pure tangent —
    # DEG_PER_RAD * ppd then maps small angles to angle_deg * ppd pixels.
    sx = DEG_PER_RAD * pixels_per_deg * 2.0 / viewport_w
    sy = DEG_PER_RAD * pixels_per_deg * 2.0 / viewport_h
    # rows: clip.x = sx*right, clip.y = sy*up, clip.w = fwd,
    # clip.z = za*fwd + zb — ndc z spans [-1, +1] over [Z_NEAR, Z_FAR]
    # (za + zb/fwd, monotonic in fwd). Points nearer than Z_NEAR are
    # clipped at z = -w exactly where w-clipping used to let them
    # through to degenerate projections.
    za = (Z_FAR + Z_NEAR) / (Z_FAR - Z_NEAR)
    zb = -2.0 * Z_FAR * Z_NEAR / (Z_FAR - Z_NEAR)
    C = np.array([[sx, 0,  0,  0],
                  [0,  0,  sy, 0],
                  [0,  za, 0,  zb],
                  [0,  1,  0,  0.0]])

    return C @ R @ P @ H @ T


def project(vp, e, n, u):
    """Project one ENU point through *vp*. Returns (ndc_x, ndc_y, w);
    the point is in front of the camera when w > 0. Convenience for
    CPU-side checks and tests — the GL pipeline does this in-shader."""
    clip = vp @ np.array([e, n, u, 1.0])
    return clip[0], clip[1], clip[3]
