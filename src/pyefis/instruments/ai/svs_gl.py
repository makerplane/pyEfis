"""
GPU-backed SVS terrain renderer.

P5: renders directly into the AI view's QOpenGLWidget surface between
QPainter.begin/endNativePainting — no offscreen context, no FBO, no
glReadPixels readback. GL resources are created lazily on the widget's
context at first draw.

Step 4 of docs/svs_opengl_plan.md: the polar mesh's elevation comes
from a heightmap texture built from the SRTM3 tiles overlapping the
aircraft. The vertex shader samples height per vertex; the fragment
shader outputs greyscale-by-elevation so a recognisable terrain
silhouette appears at known poses. No Lambertian shading yet — that
arrives in Step 5.

GLSL bumps to ``#version 300 es`` / ``#version 130`` (selected at
shader-compile time based on the actual context's renderable type) so
we can use ``texture()`` and explicit fragment outputs. The Pi 5 V3D
supports ES 3.1; Windows native desktop GL supports GLSL 1.30+.

Any exception in construction or in :meth:`SVSGLRenderer.draw` is
caught by :class:`SVSRenderer`, which permanently downgrades the
configured renderer to ``polar``. So a missing GL driver, an
incompatible Qt build, a runtime shader compile error, or a context
issue degrades to the CPU path silently.
"""

from __future__ import annotations

import logging
import math
import weakref

# PyOpenGL tracks per-context state by default; under Qt's EGL/eglfs
# context it can't find the "current context" and raises during
# stateful calls. Vertex setup goes through Qt-native QOpenGLBuffer +
# setAttributeBuffer; texture setup uses raw GL but the calls we make
# (glGenTextures / glTexImage2D / glTexParameteri / glBindTexture)
# don't store pointers per-context so they're safe.
import OpenGL
OpenGL.STORE_POINTERS = False
OpenGL.ERROR_ON_COPY = True
from OpenGL import GL as gl  # noqa: E402

import numpy as np  # noqa: E402
from PyQt6.QtCore import QRectF  # noqa: E402
from PyQt6.QtGui import (  # noqa: E402
    QColor, QFont, QFontMetricsF, QImage, QMatrix4x4,
    QOpenGLContext, QPainter, QSurfaceFormat,
)
from PyQt6.QtOpenGL import (  # noqa: E402
    QOpenGLBuffer,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
)

from pyefis.instruments.ai.camera import (  # noqa: E402
    view_projection, M_PER_DEG_LAT, M_PER_FT, EARTH_CURVATURE,
)

log = logging.getLogger(__name__)


# Shader source bodies — the #version header gets prepended at compile
# time based on the actual context's renderable type (ES vs desktop).
# Body uses GLSL ES 3.00 / GLSL 1.30 modern syntax: in/out, texture(),
# user-defined fragment output.

_VERT_BODY = """
in vec2 a_cell;                    // cell coords (0..n) in the level grid

uniform float u_ac_alt_ft;
uniform mat4  u_vp;                // unified camera matrix (camera.py)
uniform float u_ac_e;              // aircraft ENU east, metres
uniform float u_ac_n;              // aircraft ENU north, metres
uniform float u_earth_curv;        // 1/(2R_earth), or 0 when disabled
uniform float u_patch_texels;      // heightmap texture dimension in px
uniform vec2  u_patch_extent_m;    // heightmap patch size in ENU metres
uniform vec4  u_tex_xform;         // world-fixed texture transform:
                                   // (x_scale, x_offset, y_scale,
                                   // y_offset). Anchored to the PATCH
                                   // latitude — the aircraft's moving
                                   // lat_cos must never appear here or
                                   // the pattern slides sideways under
                                   // fixed ground features (the
                                   // conveyor-belt drift found in
                                   // flight against the roads).
uniform float u_level_spacing;     // this level's cell size, metres
uniform vec2  u_level_origin;      // this level's SW corner, ENU metres
                                   // (snapped to whole cells — what
                                   // pins vertices to the WORLD)
uniform float u_level_half;        // this level's half extent, metres
uniform float u_morph_on;          // 1 = geomorph toward the next-coarser
                                   // level near the outer edge (0 on the
                                   // outermost level — nothing to match)
uniform sampler2D u_heightmap;     // R32F, single-channel metres

out float v_clearance_ft;
out float v_intensity;
out float v_is_water;
out float v_dist;                  // metres from aircraft (haze)
out vec2  v_tex;                   // world-anchored noise coords

const float M_PER_FT      = 0.3048;
const float FT_PER_M      = 3.28084;
const float SLOPE_EXAG    = 1.0;
const float AMBIENT       = 0.35;
const float DIFFUSE       = 0.65;
const float WATER_THR_M   = -1000.0;
// Geomorph band: fraction of the level half-extent where the blend to
// the next-coarser surface starts / completes. Ends short of 1.0 so the
// visible seam (this level's outer edge, where the coarser level shows
// from underneath) is drawn fully coarse-matched: C0-continuous.
const float MORPH_START   = 0.70;
const float MORPH_END     = 0.95;

// Water-clamped heightmap fetch at an ENU position (same edge-inclusive
// texel-centre mapping as the primary sample in main()).
float hm_height(vec2 p_enu) {
    vec2 uv = (p_enu / u_patch_extent_m * (u_patch_texels - 1.0) + 0.5)
              / u_patch_texels;
    float e = texture(u_heightmap, uv).r;
    return mix(e, 0.0, step(e, WATER_THR_M));
}

void main() {
    // World position: fixed for a given (level origin, cell) — the
    // camera moves through a static mesh, so the terrain surface is
    // sampled at identical points every frame (no swim).
    vec2 exy = u_level_origin + a_cell * u_level_spacing;

    // Heightmap UV: the ENU origin IS the patch SW corner. The patch grid
    // is EDGE-INCLUSIVE (w samples spanning the extent, sample 0 on the SW
    // edge, sample w-1 on the NE edge), so map through texel CENTERS:
    // uv = (frac * (w-1) + 0.5) / w. Without this half-texel correction the
    // sampled ground shifts by up to half a texel, and vertex-to-texel
    // alignment differs between patch rebuilds.
    vec2 uv = (exy / u_patch_extent_m * (u_patch_texels - 1.0) + 0.5)
              / u_patch_texels;

    float elev_m_raw = texture(u_heightmap, uv).r;
    float is_water   = step(elev_m_raw, WATER_THR_M);
    float elev_m     = mix(elev_m_raw, 0.0, is_water);

    // Slope shading: finite differences against neighbour texels.
    vec2 texel_uv = vec2(1.0 / u_patch_texels);
    float elev_e_raw = texture(u_heightmap, uv + vec2(texel_uv.x, 0.0)).r;
    float elev_n_raw = texture(u_heightmap, uv + vec2(0.0, texel_uv.y)).r;
    float elev_e_m   = mix(elev_e_raw, 0.0, step(elev_e_raw, WATER_THR_M));
    float elev_n_m   = mix(elev_n_raw, 0.0, step(elev_n_raw, WATER_THR_M));
    vec2 texel_m = texel_uv * u_patch_extent_m;
    float dE = ((elev_e_m - elev_m) / max(texel_m.x, 1.0)) * SLOPE_EXAG;
    float dN = ((elev_n_m - elev_m) / max(texel_m.y, 1.0)) * SLOPE_EXAG;
    float mag = sqrt(dE * dE + dN * dN + 1.0);
    vec3 normal = vec3(-dE / mag, -dN / mag, 1.0 / mag);
    vec3 sun_dir = normalize(vec3(-1.0, 1.0, 2.0));
    float diff = clamp(dot(normal, sun_dir), 0.0, 1.0);
    v_intensity = AMBIENT + DIFFUSE * diff;

    // --- clipmap vertex-morph band -----------------------------------
    // Near this level's outer edge, morph the vertex height onto the
    // surface the NEXT-COARSER level renders there (bilinear over the
    // four surrounding coarse-grid vertices, which sit on the global
    // 2x-spacing lattice). Terrain then transitions gradually inside
    // the band instead of reshaping ("popping") when a feature crosses
    // a ring seam, and the seam itself is continuous.
    if (u_morph_on > 0.5) {
        vec2 lvl_c = u_level_origin + vec2(u_level_half);
        vec2 dxy = abs(exy - lvl_c);
        float edge_d = max(dxy.x, dxy.y) / u_level_half;
        float w_m = clamp((edge_d - MORPH_START)
                          / (MORPH_END - MORPH_START), 0.0, 1.0);
        if (w_m > 0.0) {
            float s2 = u_level_spacing * 2.0;
            vec2 c0 = floor(exy / s2) * s2;
            vec2 fw = (exy - c0) / s2;
            float h00 = hm_height(c0);
            float h10 = hm_height(c0 + vec2(s2, 0.0));
            float h01 = hm_height(c0 + vec2(0.0, s2));
            float h11 = hm_height(c0 + vec2(s2, s2));
            float h_coarse = mix(mix(h00, h10, fw.x),
                                 mix(h01, h11, fw.x), fw.y);
            elev_m = mix(elev_m, h_coarse, w_m);
        }
    }

    v_clearance_ft = u_ac_alt_ft - elev_m * FT_PER_M;
    v_is_water     = is_water;

    // World-anchored texture coordinate: absolute world position via
    // a per-frame CPU transform that converts frame-ENU x back to
    // longitude and rescales by the constant patch lat_cos.
    v_tex = vec2(exy.x * u_tex_xform.x + u_tex_xform.y,
                 exy.y * u_tex_xform.z + u_tex_xform.w);

    float de = exy.x - u_ac_e;
    float dn = exy.y - u_ac_n;
    float d2 = de * de + dn * dn;
    v_dist = sqrt(d2);
    float drop_m = u_earth_curv * d2;
    gl_Position = u_vp * vec4(exy.x, exy.y, elev_m - drop_m, 1.0);
}
"""

_FRAG_BODY = """
in float v_clearance_ft;
in float v_intensity;
in float v_is_water;
in float v_dist;
in vec2  v_tex;
out vec4 outColor;

uniform float u_green_ft;        // clearance >= u_green_ft => SAFE
uniform float u_yellow_ft;       // clearance >= u_yellow_ft => CAUTION
uniform float u_near_airport;    // 1.0 => collapse to 2-colour SAFE/CONFLICT
uniform float u_apt_gate_ft;     // collapse only below this MSL elevation
uniform float u_safe_grad;       // 1.0 => clearance-graded SAFE band
uniform float u_tex_amp;         // ground-texture amplitude, 0 = off
uniform float u_grid_amp;        // world-grid darkening, 0 = off
uniform float u_ac_alt_ft;       // aircraft altitude (shared w/ vertex)
uniform float u_haze_inv;        // 1 / haze_distance_m, or 0 = off

// Match the CPU tier's COLOR_* constants in svs.py.
const vec3 COLOR_SAFE     = vec3(0.0,   0.392, 0.0  );  // (  0, 100,   0)
const vec3 COLOR_CAUTION  = vec3(0.706, 0.510, 0.0  );  // (180, 130,   0)
const vec3 COLOR_WARNING  = vec3(0.784, 0.157, 0.0  );  // (200,  40,   0)
const vec3 COLOR_CONFLICT = vec3(0.706, 0.0,   0.706);  // (180,   0, 180)
const vec3 COLOR_WATER    = vec3(0.078, 0.314, 0.588);  // ( 20,  80, 150)

// Washed-out horizon tone the haze fades toward — keyed to the AI's
// sky gradient at the horizon so far terrain melts into the sky.
const vec3 HAZE_COLOR     = vec3(0.65, 0.77, 0.90);
// Low-clearance end of the graded SAFE band — olive/tan, so rising
// terrain warms as it approaches the green threshold (shape-from-
// color, the G1000-style depth cue).
const vec3 COLOR_SAFE_LOW = vec3(0.50, 0.46, 0.22);

float hash2(vec2 p) {
    // Sin-free hash (Hoskins-style): the classic sin() lattice hash
    // collapses at large world coordinates even in highp. Wrapping at
    // 512 cells repeats the pattern every ~77 km — imperceptible.
    p = mod(p, 512.0);
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}
// Procedural mipmapping: fade a noise/grid octave to zero as its
// cells approach pixel scale. Without this, sub-pixel pattern detail
// resamples randomly every frame ("shimmer"/"swim", worst in turns).
float nyquist_fade(vec2 p) {
    float fw = max(fwidth(p.x), fwidth(p.y));
    return 1.0 - smoothstep(0.25, 0.75, fw);
}

float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i),               hash2(i + vec2(1, 0)), u.x),
               mix(hash2(i + vec2(0, 1)),  hash2(i + vec2(1, 1)), u.x),
               u.y);
}

void main() {
    vec3 base;
    if (v_is_water > 0.5) {
        base = COLOR_WATER;
    } else if (v_clearance_ft < 0.0) {
        base = COLOR_CONFLICT;
    } else if (u_near_airport > 0.5
               && (u_ac_alt_ft - v_clearance_ft) < u_apt_gate_ft) {
        // Airport-proximity collapse, elevation-gated (issue #32
        // Option B): only the runway environment — terrain below
        // field elevation + airport_gate_agl_ft — has its warning
        // bands suppressed. Rising terrain inside the proximity
        // radius keeps full red/amber treatment.
        base = COLOR_SAFE;
    } else if (v_clearance_ft < u_yellow_ft) {
        base = COLOR_WARNING;
    } else if (v_clearance_ft < u_green_ft) {
        base = COLOR_CAUTION;
    } else {
        base = COLOR_SAFE;
        if (u_safe_grad > 0.5) {
            // Blend olive->green across 2,500 ft of clearance above
            // the green threshold: ground far below stays deep green,
            // ground rising toward the aircraft warms continuously.
            float t = clamp((v_clearance_ft - u_green_ft) / 2500.0,
                            0.0, 1.0);
            base = mix(COLOR_SAFE_LOW, COLOR_SAFE, t);
        }
    }
    vec3 shaded = base * v_intensity;

    // World-anchored ground texture: two octaves of value noise,
    // strong in the near field and faded out by ~4 NM (the haze owns
    // the far field). Restores the texture gradient + optic flow the
    // eye needs to read slope and closure rate up close.
    if (u_tex_amp > 0.0 && v_is_water < 0.5) {
        // Each octave attenuated by its own Nyquist fade — coarse
        // detail survives to mid-range, fine detail only up close.
        float n = 0.50 * (vnoise(v_tex) - 0.5)
                      * nyquist_fade(v_tex)
                + 0.30 * (vnoise(v_tex * 3.1) - 0.5)
                      * nyquist_fade(v_tex * 3.1)
                + 0.20 * (vnoise(v_tex * 9.7) - 0.5)
                      * nyquist_fade(v_tex * 9.7);
        float amp = u_tex_amp * exp(-v_dist / 7408.0);
        shaded *= 1.0 + amp * n * 2.0;
    }

    // World-anchored surface grid (fishnet): 300 m cells fixed to the
    // ground (v_tex is world metres / 150). Draped cells foreshorten
    // on rising slopes — the dominant foreground slope cue — and
    // stream past with motion. Gaussian fade keeps it foreground-only
    // (~gone past 2 NM); fwidth antialiases to a crisp 1 px line.
    if (u_grid_amp > 0.0 && v_is_water < 0.5) {
        vec2 gp = v_tex * 0.5;
        vec2 g_to_edge = abs(fract(gp) - 0.5);
        vec2 g_aa = fwidth(gp) * 0.75;
        vec2 lm = vec2(1.0) - smoothstep(vec2(0.0), g_aa, g_to_edge);
        float wire = max(lm.x, lm.y);
        float gd = v_dist / 3704.0;   // 2 NM scale
        float gamp = u_grid_amp * exp(-gd * gd) * nyquist_fade(gp);
        shaded *= 1.0 - wire * gamp;
    }

    if (u_haze_inv > 0.0) {
        float fog = 1.0 - exp(-v_dist * u_haze_inv);
        shaded = mix(shaded, HAZE_COLOR, fog);
    }

    outColor = vec4(shaded, 1.0);
}
"""

# ---------------------------------------------------------------------------
# Overlay shader (Phase 0 of the SVS-overlays-to-GPU plan).
# ---------------------------------------------------------------------------
# A "generic flat-color" vertex/fragment pair reused by every overlay we
# migrate off the CPU: water polygons (Phase 1), obstacle poles (Phase 2),
# runway polygon and side stripes (Phase 3), runway markings (Phase 4),
# airport flag poles (Phase 5).
#
# The vertex shader projects a single world-space point (lat, lon, elev_ft)
# to screen using the same math the terrain shader uses (atan2 azimuth +
# pitch/roll rotation). Every overlay shares the projection; only the
# uniform color and per-overlay vertex buffer differ.
#
# Vertices that fall behind the camera (x_fwd <= 0) get z=2.0 in clip
# space, which falls outside the [-w, +w] visible volume so GL clips them
# automatically. Triangles straddling the near plane get clipped per-pixel
# by the GL pipeline — much simpler than the Sutherland-Hodgman the CPU
# path runs.

_OVERLAY_VERT_BODY = """
in vec3 a_world_pos;   // ENU metres (east, north, up-MSL) — see camera.py

uniform mat4  u_vp;
uniform float u_ac_e;
uniform float u_ac_n;
uniform float u_earth_curv;

out float v_dist;

void main() {
    float de = a_world_pos.x - u_ac_e;
    float dn = a_world_pos.y - u_ac_n;
    float d2 = de * de + dn * dn;
    v_dist = sqrt(d2);
    float drop = u_earth_curv * d2;
    gl_Position = u_vp * vec4(
        a_world_pos.x, a_world_pos.y, a_world_pos.z - drop, 1.0);
}
"""

_OVERLAY_FRAG_BODY = """
in float v_dist;
uniform vec4 u_color;
uniform float u_haze_inv;        // 1 / haze_distance_m, or 0 = off
uniform float u_fog_strength;    // per-layer: water 1.0, symbology less
out vec4 outColor;

const vec3 HAZE_COLOR = vec3(0.65, 0.77, 0.90);

void main() {
    vec3 c = u_color.rgb;
    if (u_haze_inv > 0.0 && u_fog_strength > 0.0) {
        float fog = (1.0 - exp(-v_dist * u_haze_inv)) * u_fog_strength;
        c = mix(c, HAZE_COLOR, fog);
    }
    outColor = vec4(c, u_color.a);
}
"""


# ---------------------------------------------------------------------------
# Text overlay shader (Phase 4b — runway designators on the GPU).
# ---------------------------------------------------------------------------
# Each glyph is one textured quad in runway-local space. The vertex
# shader runs the same perspective projection as the flat-color
# overlay shader; the fragment shader samples a single-channel font
# atlas as alpha and discards transparent fragments so the runway
# polygon grey shows through outside the glyph strokes.

_TEXT_VERT_BODY = """
in vec3 a_world_pos;   // ENU metres (east, north, up-MSL)
in vec2 a_uv;          // atlas UV for this quad corner

uniform mat4  u_vp;
uniform float u_ac_e;
uniform float u_ac_n;
uniform float u_earth_curv;

out vec2 v_uv;

void main() {
    float de = a_world_pos.x - u_ac_e;
    float dn = a_world_pos.y - u_ac_n;
    float drop = u_earth_curv * (de * de + dn * dn);
    gl_Position = u_vp * vec4(
        a_world_pos.x, a_world_pos.y, a_world_pos.z - drop, 1.0);
    v_uv = a_uv;
}
"""

_TEXT_FRAG_BODY = """
in vec2 v_uv;
uniform vec4 u_color;
uniform sampler2D u_atlas;
out vec4 outColor;

void main() {
    float alpha = texture(u_atlas, v_uv).r;
    // Discard transparent samples so the underlying runway grey
    // shows through outside the glyph stroke.
    if (alpha < 0.4) discard;
    outColor = vec4(u_color.rgb, 1.0);
}
"""


# Glyphs covered by the designator-text atlas. Runway designators
# are 1-2 numeric digits + optional L/C/R; airport identifiers
# (Phase 5) use the broader A-Z + 0-9 set.
_TEXT_ATLAS_GLYPHS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-"
# Each glyph gets a 64x64 slot in a 512x512 atlas (8x8 grid, 64
# slots, 37 used). 64 px / glyph is enough resolution that
# stretching to a 60 ft runway designator on short final is crisp.
_TEXT_ATLAS_SIZE = 512
_TEXT_ATLAS_SLOT = 64
# FAA AC 150/5340-1L "1" is a plain vertical stroke (no flag /
# foot). Stroke width is 5.33 ft of a 60 ft tall character.
_FAA_STROKE_RATIO = 5.33 / 60.0


def build_text_atlas(font_family="DejaVu Sans Condensed"):
    """Build a single-channel font atlas of designator glyphs.

    Returns (atlas_np, uvs) where:
      - atlas_np: uint8 numpy array shape (size, size) with glyph
        coverage as 0-255 (255 = fully covered glyph pixel).
      - uvs: dict mapping each character in _TEXT_ATLAS_GLYPHS to a
        tuple (u0, v0, u1, v1) of the glyph's TIGHT UV bbox in the
        atlas — i.e. the texture region that contains just the glyph
        strokes with no slot padding. Callers size their per-glyph
        quad in runway-local feet according to FAA spec and bind
        this UV box; the perspective shader handles the stretch.

    Generated lazily at SVSGLRenderer init. Uses the existing
    DejaVu Sans Condensed font already shipped with the system
    (the marking-text CPU path used the same font).
    """
    atlas_size = _TEXT_ATLAS_SIZE
    slot = _TEXT_ATLAS_SLOT
    grid = atlas_size // slot   # 8 slots per row
    if len(_TEXT_ATLAS_GLYPHS) > grid * grid:
        raise RuntimeError("text atlas grid too small for glyph set")

    img = QImage(atlas_size, atlas_size,
                 QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        p.setPen(QColor(255, 255, 255, 255))

        font = QFont(font_family, 10)
        # Pixel size sized so a tall glyph fills ~88% of its slot,
        # leaving a small margin for antialiasing tail and clean
        # tight-bbox computation. Bold for FAA marking weight.
        font.setPixelSize(int(slot * 0.88))
        font.setBold(True)
        p.setFont(font)
        metrics = QFontMetricsF(font)
        ascent = metrics.ascent()

        uvs = {}
        for i, ch in enumerate(_TEXT_ATLAS_GLYPHS):
            row = i // grid
            col = i % grid
            sx = col * slot
            sy = row * slot

            if ch == '1':
                # FAA-style plain stroke "1" — vertical rectangle.
                # No font glyph; just fillRect.
                stroke_w = _FAA_STROKE_RATIO * slot
                # Center horizontally in the slot for nicer kerning.
                fx = sx + (slot - stroke_w) * 0.5
                p.fillRect(QRectF(fx, sy, stroke_w, float(slot)),
                           QColor(255, 255, 255, 255))
                u0 = fx / atlas_size
                u1 = (fx + stroke_w) / atlas_size
                v0 = sy / atlas_size
                v1 = (sy + slot) / atlas_size
            else:
                # Tight bounding rectangle of the glyph in font units.
                rect = metrics.tightBoundingRect(ch)
                # tightBoundingRect's origin is at the baseline, with
                # y measured upward from baseline (so rect.top() is
                # negative — top of cap). Position the glyph so its
                # top edge aligns with the slot top.
                baseline_y = sy - rect.top()
                glyph_x = sx - rect.left()
                p.drawText(int(round(glyph_x)),
                           int(round(baseline_y)), ch)
                u0 = sx / atlas_size
                u1 = (sx + rect.width()) / atlas_size
                v0 = sy / atlas_size
                v1 = (sy + rect.height()) / atlas_size
            uvs[ch] = (u0, v0, u1, v1)

        # Obstacle symbol glyphs (FAA VFR-chart shapes), drawn into the
        # next free atlas slots. Keys are multi-char so they can never
        # collide with text glyphs.
        from PyQt6.QtGui import QPolygonF, QPen, QBrush
        from PyQt6.QtCore import QPointF
        sym_specs = ("OBST", "OBST_HIGH")
        base_i = len(_TEXT_ATLAS_GLYPHS)
        pen = QPen(QColor(255, 255, 255, 255))
        pen.setWidthF(slot * 0.09)
        for k, name in enumerate(sym_specs):
            i = base_i + k
            row = i // grid
            col = i % grid
            sx = col * slot
            sy = row * slot
            m = slot * 0.08          # margin inside the slot
            p.setPen(pen)
            p.setBrush(QBrush())     # open (outline) shape
            if name == "OBST":
                # Open triangle, apex up, with a center dot — the
                # standard <1000 ft AGL obstacle symbol.
                tri = QPolygonF([
                    QPointF(sx + slot * 0.5,  sy + m),
                    QPointF(sx + m,           sy + slot - m),
                    QPointF(sx + slot - m,    sy + slot - m)])
                p.drawPolygon(tri)
                p.setBrush(QBrush(QColor(255, 255, 255, 255)))
                p.drawEllipse(QPointF(sx + slot * 0.5,
                                      sy + slot * 0.62),
                              slot * 0.08, slot * 0.08)
            else:
                # High obstacle (>=1000 ft AGL): tall narrow spire
                # with the center dot, echoing the chart symbol.
                tri = QPolygonF([
                    QPointF(sx + slot * 0.5,   sy + m),
                    QPointF(sx + slot * 0.30,  sy + slot - m),
                    QPointF(sx + slot * 0.70,  sy + slot - m)])
                p.drawPolygon(tri)
                p.setBrush(QBrush(QColor(255, 255, 255, 255)))
                p.drawEllipse(QPointF(sx + slot * 0.5,
                                      sy + slot * 0.70),
                              slot * 0.07, slot * 0.07)
            uvs[name] = (sx / atlas_size, sy / atlas_size,
                         (sx + slot) / atlas_size,
                         (sy + slot) / atlas_size)
    finally:
        p.end()

    # Extract alpha channel. ARGB32 little-endian byte order is BGRA,
    # so the alpha byte is at index 3 of every pixel.
    ptr = img.constBits()
    ptr.setsize(atlas_size * atlas_size * 4)
    rgba = np.frombuffer(ptr, dtype=np.uint8).reshape(
        atlas_size, atlas_size, 4)
    atlas_np = rgba[:, :, 3].copy()
    return atlas_np, uvs


# 2-by-2 tile patch around the aircraft, rebuilt on half-degree
# crossings. Tile resolution is per-file (1201 SRTM3 / 3601 GLO-30);
# the patch assembles at the finest resolution present, then decimates
# to fit the GPU texture cap (parent.heightmap_max_px and the driver's
# GL_MAX_TEXTURE_SIZE).
_PATCH_TILES = 2


class SVSGLRenderer:
    """Direct-to-viewport GL renderer (P5).

    Per frame, inside QPainter.begin/endNativePainting on the AI's
    QOpenGLWidget viewport:

    1. Lazy-create programs, mesh, glyph atlas on the current context.
    2. Refresh the heightmap texture on half-degree patch crossings.
    3. Build the unified camera matrix (camera.py).
    4. Draw the terrain fan, then every overlay pass, straight into
       the default framebuffer — no offscreen FBO, no glReadPixels.
    """

    def __init__(self, parent_renderer):
        self._parent = parent_renderer

        # GL resources — built lazily on the first draw, on whatever
        # context is current inside beginNativePainting (the AI's
        # QOpenGLWidget). No context or FBO of our own (P5).
        self._program: QOpenGLShaderProgram | None = None
        self._a_position = -1
        self._vao: QOpenGLVertexArrayObject | None = None
        self._vbo: QOpenGLBuffer | None = None
        self._ibo: QOpenGLBuffer | None = None
        self._index_count = 0
        self._u: dict[str, int] = {}
        # Heightmap texture state. _patch_origin is (start_lat, start_lon)
        # in integer degrees; when it changes we rebuild.
        self._heightmap_tex_id: int | None = None
        self._patch_origin: tuple[int, int] | None = None
        self._patch_texels = 2402.0   # actual texture px, set per build
        self._patch_bounds = (0.0, 0.0, 0.0, 0.0)  # lat_min, lat_max, lon_min, lon_max

        # Overlay pass state (Phase 0 of the overlays-to-GPU plan).
        # The overlay shader is generic — every overlay draw call binds
        # this program, updates one VBO, sets the u_color uniform, and
        # issues a glDrawArrays. Lazily compiled on first frame.
        self._overlay_program: QOpenGLShaderProgram | None = None
        self._overlay_vao: QOpenGLVertexArrayObject | None = None
        self._overlay_vbo: QOpenGLBuffer | None = None
        self._overlay_vbo_capacity = 0   # current GL-side buffer size in floats
        self._overlay_a_world_pos = -1
        self._overlay_u: dict[str, int] = {}
        # Widest line width the driver supports (queried lazily on the
        # first obstacle draw; 1.0 on desktop core profiles, ~10 on V3D).
        self._max_line_width: float | None = None
        # Persistent per-layer VBOs for the large static overlays
        # (water, highways): slot -> {vao, vbo, cap, ref, n, frame}.
        self._layer_buffers = {}
        # Same idea for the textured (atlas) overlays — obstacles,
        # airport flags, designators. Keeps the _to_enu + GPU upload off
        # the per-frame path; re-uploads only when the source array
        # (cached collection) or the ENU frame actually changes.
        self._text_layer_buffers = {}

        # Text overlay state (Phase 4b). Atlas texture + a separate
        # program with the same projection but textured-quad fragment
        # shader. Vertex format is (lat, lon, elev_ft, u, v) — 5
        # floats per vertex.
        self._text_program: QOpenGLShaderProgram | None = None
        self._text_vao: QOpenGLVertexArrayObject | None = None
        self._text_vbo: QOpenGLBuffer | None = None
        self._text_vbo_capacity = 0
        self._text_a_world_pos = -1
        self._text_a_uv = -1
        self._text_u: dict[str, int] = {}
        self._text_atlas_tex_id: int | None = None
        self._text_atlas_uvs: dict[str, tuple] = {}

        log.info("SVSGLRenderer initialised (direct-to-viewport, P5)")

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw(self, painter, w, h, ac_lat, ac_lon, ac_alt_ft,
             pitch_deg, roll_deg, heading_deg, pixels_per_deg,
             range_nm=None, device_pixel_ratio=1.0):
        """Render terrain + overlays directly into the painter's GL
        surface between begin/endNativePainting. Requires the AI view
        to carry a QOpenGLWidget viewport; raises when no GL context
        is current, which SVSRenderer turns into the one-shot
        SVS UNAVAIL state."""
        painter.beginNativePainting()
        _saved = None
        try:
            if QOpenGLContext.currentContext() is None:
                raise RuntimeError(
                    "no current GL context — AI viewport is not a "
                    "QOpenGLWidget")
            if not getattr(self, "_logged_samples", False):
                self._logged_samples = True
                try:
                    log.info("SVS GL surface MSAA samples: %d",
                             int(gl.glGetIntegerv(gl.GL_SAMPLES)))
                except Exception:
                    pass
            # Snapshot the GL state Qt's paint engine caches. The
            # engine tracks its own last-bound textures/program/VAO
            # and does NOT re-bind them after native painting — if we
            # leave different bindings, every scene item drawn after
            # the SVS (pitch ladder text especially) samples whatever
            # texture we left bound. Restore the exact prior bindings
            # before endNativePainting so the engine's cache stays
            # truthful.
            _saved = self._save_gl_state()
            self._ensure_program()
            self._ensure_mesh()
            self._ensure_heightmap(ac_lat, ac_lon)
            self._update_camera(w, h, ac_lat, ac_lon, ac_alt_ft,
                                pitch_deg, roll_deg, heading_deg,
                                pixels_per_deg)
            # Qt leaves the GL viewport undefined inside native
            # painting; set it to the full backing store (device
            # pixels, hence the DPR scale).
            gl.glViewport(0, 0,
                          int(round(w * device_pixel_ratio)),
                          int(round(h * device_pixel_ratio)))
            self._render_frame(
                w, h, ac_lat, ac_lon, ac_alt_ft, pitch_deg, roll_deg,
                heading_deg, pixels_per_deg, range_nm)
        finally:
            if _saved is not None:
                self._restore_gl_state(_saved)
            painter.endNativePainting()

    _STATE_TEX_UNITS = 4

    @staticmethod
    def _save_gl_state():
        state = {
            "active": int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)),
            "program": int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)),
            "vao": int(gl.glGetIntegerv(gl.GL_VERTEX_ARRAY_BINDING)),
            "array_buf": int(gl.glGetIntegerv(
                gl.GL_ARRAY_BUFFER_BINDING)),
            "unpack_align": int(gl.glGetIntegerv(
                gl.GL_UNPACK_ALIGNMENT)),
            "unpack_row_len": int(gl.glGetIntegerv(
                gl.GL_UNPACK_ROW_LENGTH)),
            "tex": [],
        }
        for u in range(SVSGLRenderer._STATE_TEX_UNITS):
            gl.glActiveTexture(gl.GL_TEXTURE0 + u)
            state["tex"].append(int(gl.glGetIntegerv(
                gl.GL_TEXTURE_BINDING_2D)))
        gl.glActiveTexture(state["active"])
        return state

    @staticmethod
    def _restore_gl_state(state):
        for u in range(SVSGLRenderer._STATE_TEX_UNITS):
            gl.glActiveTexture(gl.GL_TEXTURE0 + u)
            gl.glBindTexture(gl.GL_TEXTURE_2D, state["tex"][u])
        gl.glActiveTexture(state["active"])
        gl.glUseProgram(state["program"])
        gl.glBindVertexArray(state["vao"])
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, state["array_buf"])
        # Our atlas/heightmap uploads set tight unpack alignment; a
        # stale value shears Qt's glyph-cache uploads (striped text).
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, state["unpack_align"])
        gl.glPixelStorei(gl.GL_UNPACK_ROW_LENGTH,
                         state["unpack_row_len"])
        gl.glLineWidth(1.0)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _update_camera(self, w, h, ac_lat, ac_lon, ac_alt_ft,
                       pitch_deg, roll_deg, heading_deg, pixels_per_deg):
        """Build the per-frame unified camera (P3): aircraft ENU
        position relative to the heightmap patch origin, the 4x4
        view-projection matrix, and the ENU conversion factors used
        when uploading overlay vertex buffers."""
        import math as _math
        o_lat, o_lon = self._patch_origin
        lat_cos = _math.cos(_math.radians(ac_lat))
        ac_e = (ac_lon - o_lon) * M_PER_DEG_LAT * lat_cos
        ac_n = (ac_lat - o_lat) * M_PER_DEG_LAT
        ac_u = ac_alt_ft * M_PER_FT
        vp = view_projection(ac_e, ac_n, ac_u, heading_deg, pitch_deg,
                             roll_deg, pixels_per_deg, w, h)
        self._frame_vp = QMatrix4x4(*[float(x) for x in vp.ravel()])
        self._frame_ac_e = ac_e
        self._frame_ac_n = ac_n
        self._frame_lat_cos = lat_cos
        self._frame_curv = (EARTH_CURVATURE
                            if getattr(self._parent, "earth_curvature",
                                       True) else 0.0)
        haze_nm = float(getattr(self._parent, "haze_distance_nm", 40.0))
        # Visibility scales with altitude (jet altitudes see much
        # farther than the pattern): the config value is the FLOOR,
        # stretched toward ~90% of the true-horizon distance, capped
        # at 120 NM. At 17,000 ft this puts the haze knee near 90 NM
        # instead of fogging out everything past 40.
        alt_vis = 0.9 * 1.22 * math.sqrt(max(ac_alt_ft, 0.0))
        haze_eff = min(max(haze_nm, alt_vis), 200.0)
        self._frame_haze_inv = (
            1.0 / (haze_eff * 1852.0)
            if getattr(self._parent, "haze", True) and haze_nm > 0
            else 0.0)

    def _to_enu(self, verts):
        """Convert an Nx3 (lat, lon, elev_ft) — or Nx5 with trailing
        UVs — float array to ENU metres in the current patch frame.
        One conversion point for every overlay buffer; collectors stay
        in lat/lon, so patch-origin changes need no cache invalidation
        (the conversion re-runs each upload)."""
        o_lat, o_lon = self._patch_origin
        out = np.empty(verts.shape, dtype=np.float32)
        out[:, 0] = (verts[:, 1] - o_lon) * (M_PER_DEG_LAT
                                             * self._frame_lat_cos)
        out[:, 1] = (verts[:, 0] - o_lat) * M_PER_DEG_LAT
        out[:, 2] = verts[:, 2] * M_PER_FT
        if verts.shape[1] > 3:
            out[:, 3:] = verts[:, 3:]
        return out

    def _render_frame(self, w, h, ac_lat, ac_lon, ac_alt_ft,
                      pitch_deg, roll_deg, heading_deg, pixels_per_deg,
                      range_nm=None):
        """Issue the terrain + overlay draws into the currently bound
        (default) framebuffer. No clear: pixels the polar fan does not
        cover keep the AI's painted sky/ground background — the same
        compositing the transparent-FBO blit used to provide."""
        if True:
            # Bind the heightmap to texture unit 0; the shader's
            # sampler2D uniform points at unit 0.
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._heightmap_tex_id)

            self._program.bind()
            self._vao.bind()
            try:
                p = self._parent
                self._program.setUniformValue(
                    self._u["u_ac_alt_ft"], float(ac_alt_ft))
                self._program.setUniformValue(
                    self._u["u_vp"], self._frame_vp)
                self._program.setUniformValue(
                    self._u["u_ac_e"], float(self._frame_ac_e))
                self._program.setUniformValue(
                    self._u["u_ac_n"], float(self._frame_ac_n))
                self._program.setUniformValue(
                    self._u["u_earth_curv"], float(self._frame_curv))
                self._program.setUniformValue(
                    self._u["u_patch_texels"],
                    float(self._patch_texels))
                self._program.setUniformValue(
                    self._u["u_haze_inv"], float(self._frame_haze_inv))
                self._program.setUniformValue(
                    self._u["u_heightmap"], 0)
                self._program.setUniformValue(
                    self._u["u_green_ft"], float(p.green_ft))
                self._program.setUniformValue(
                    self._u["u_yellow_ft"], float(p.yellow_ft))
                near = self._near_airport(ac_lat, ac_lon)
                self._program.setUniformValue(
                    self._u["u_near_airport"], 1.0 if near else 0.0)
                _apt_elev = getattr(self._parent,
                                    "_near_airport_elev_ft", None)
                gate = ((_apt_elev + float(getattr(
                    self._parent, "airport_gate_agl_ft", 400.0)))
                    if (near and _apt_elev is not None) else 1.0e9)
                self._program.setUniformValue(
                    self._u["u_apt_gate_ft"], float(gate))
                self._program.setUniformValue(
                    self._u["u_safe_grad"],
                    1.0 if getattr(p, "safe_gradient", True) else 0.0)
                self._program.setUniformValue(
                    self._u["u_tex_amp"],
                    float(getattr(p, "terrain_texture", 0.35)))
                self._program.setUniformValue(
                    self._u["u_grid_amp"],
                    float(getattr(p, "terrain_grid", 0.35)))

                # Patch geometry in ENU metres (ENU origin = patch SW
                # corner) and the absolute-world noise offset.
                lat_cos = self._frame_lat_cos
                ext_e = 2.0 * M_PER_DEG_LAT * lat_cos
                ext_n = 2.0 * M_PER_DEG_LAT
                self._program.setUniformValue(
                    self._u["u_patch_extent_m"],
                    float(ext_e), float(ext_n))
                o_lat, o_lon = self._patch_origin
                # Pattern anchored to the world: x converts frame-ENU
                # back to longitude (divide by the FRAME lat_cos) and
                # rescales by the PATCH-CENTRE lat_cos, which is
                # constant between patch rebases.
                lc_patch = math.cos(math.radians(o_lat + 1.0))
                xs = lc_patch / (150.0 * lat_cos)
                xo = o_lon * M_PER_DEG_LAT * lc_patch / 150.0
                self._program.setUniformValue(
                    self._u["u_tex_xform"],
                    float(xs), float(xo),
                    float(1.0 / 150.0),
                    float(o_lat * M_PER_DEG_LAT / 150.0))

                # Clipmap levels, coarse to fine (painter's algorithm
                # ACROSS levels: finer levels overdraw coarser — no
                # seams, no T-junction stitching needed). Each level's
                # origin is snapped to its own spacing: the mesh is
                # pinned to the WORLD, turns change nothing, forward
                # flight only swaps edge cells.
                # WITHIN a level the depth buffer resolves
                # self-occlusion — without it, grid-order triangles
                # behind a ridge paint over the nearer crest
                # (mesh-period sawtooth along every ridge silhouette,
                # the "jagged edge"). Depth is cleared per level so a
                # finer ring still unconditionally overdraws the
                # coarser ground beneath it.
                gl.glEnable(gl.GL_DEPTH_TEST)
                gl.glDepthFunc(gl.GL_LESS)
                gl.glDepthMask(gl.GL_TRUE)
                n_cells = p._clip_cells
                base_m = ext_n / max(self._patch_texels - 1.0, 1.0)
                for k in range(p._clip_levels - 1, -1, -1):
                    gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
                    spacing = base_m * (2 ** k)
                    half = (n_cells / 2.0) * spacing
                    ox = (math.floor(self._frame_ac_e / spacing)
                          * spacing - half)
                    oy = (math.floor(self._frame_ac_n / spacing)
                          * spacing - half)
                    self._program.setUniformValue(
                        self._u["u_level_spacing"], float(spacing))
                    self._program.setUniformValue(
                        self._u["u_level_origin"],
                        float(ox), float(oy))
                    self._program.setUniformValue(
                        self._u["u_level_half"], float(half))
                    # Geomorph toward the next-coarser level; the
                    # outermost level has no coarser target.
                    self._program.setUniformValue(
                        self._u["u_morph_on"],
                        0.0 if k == p._clip_levels - 1 else 1.0)
                    if k == 0:
                        self._ibo.bind()
                        gl.glDrawElements(
                            gl.GL_TRIANGLES, self._index_count,
                            gl.GL_UNSIGNED_INT, None)
                    else:
                        self._ibo_annulus.bind()
                        gl.glDrawElements(
                            gl.GL_TRIANGLES, self._annulus_count,
                            gl.GL_UNSIGNED_INT, None)
            finally:
                # Overlays and Qt's paint engine expect depth testing
                # OFF (painter's-order compositing).
                gl.glDisable(gl.GL_DEPTH_TEST)
                self._vao.release()
                self._program.release()

            # Overlay passes (water, obstacles, runways, markings,
            # designators, flags) draw on top of the terrain in the
            # same framebuffer.
            self._render_overlays(
                w, h, ac_lat, ac_lon, ac_alt_ft,
                pitch_deg, roll_deg, heading_deg, pixels_per_deg,
                range_nm)

            # Leave GL state tidy for Qt's paint engine: unit 0
            # active, nothing bound.
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

    def _near_airport(self, ac_lat: float, ac_lon: float) -> bool:
        """Cached airport-proximity test — see SVSRenderer.near_airport
        (1 s TTL; replaces the per-frame sqlite query)."""
        return bool(self._parent.near_airport(ac_lat, ac_lon))

    # ------------------------------------------------------------------
    # Overlay pass (Phase 0 infrastructure for the overlays-to-GPU plan)
    # ------------------------------------------------------------------
    def _ensure_overlay_program(self):
        if self._overlay_program is not None:
            return
        header = self._shader_header()
        vsrc = header + _OVERLAY_VERT_BODY
        if "es" in header:
            fheader = "#version 300 es\nprecision mediump float;\n"
        else:
            fheader = header
        fsrc = fheader + _OVERLAY_FRAG_BODY
        prog = QOpenGLShaderProgram()
        if not prog.addShaderFromSourceCode(
                QOpenGLShader.ShaderTypeBit.Vertex, vsrc):
            raise RuntimeError(
                f"overlay vertex shader compile failed: {prog.log()}")
        if not prog.addShaderFromSourceCode(
                QOpenGLShader.ShaderTypeBit.Fragment, fsrc):
            raise RuntimeError(
                f"overlay fragment shader compile failed: {prog.log()}")
        if not prog.link():
            raise RuntimeError(f"overlay shader link failed: {prog.log()}")
        self._overlay_a_world_pos = prog.attributeLocation("a_world_pos")
        if self._overlay_a_world_pos < 0:
            raise RuntimeError("overlay shader: a_world_pos not found")
        for name in ("u_vp", "u_ac_e", "u_ac_n", "u_earth_curv",
                     "u_color", "u_haze_inv", "u_fog_strength"):
            loc = prog.uniformLocation(name)
            if loc < 0:
                raise RuntimeError(f"overlay shader: {name} not found")
            self._overlay_u[name] = loc
        self._overlay_program = prog

        self._overlay_vao = QOpenGLVertexArrayObject()
        self._overlay_vao.create()
        self._overlay_vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self._overlay_vbo.create()
        self._overlay_vbo.setUsagePattern(
            QOpenGLBuffer.UsagePattern.DynamicDraw)
        # Allocate the attribute binding once; subsequent draws just
        # re-upload the buffer contents.
        self._overlay_vao.bind()
        try:
            self._overlay_vbo.bind()
            try:
                prog.bind()
                prog.enableAttributeArray(self._overlay_a_world_pos)
                # vec3 floats interleaved, stride = 3 * 4 bytes.
                prog.setAttributeBuffer(
                    self._overlay_a_world_pos, gl.GL_FLOAT, 0, 3, 12)
                prog.release()
            finally:
                self._overlay_vbo.release()
        finally:
            self._overlay_vao.release()

    def _draw_overlay_primitive(self, vertices_np, color_rgba, mode,
                                fog_strength=0.0):
        """Upload ``vertices_np`` (Nx3 float32 array of lat, lon, elev_ft)
        and issue one draw call. ``mode`` is a GL primitive type
        (GL_TRIANGLES, GL_LINES, etc.). ``color_rgba`` is a 4-tuple of
        floats in [0, 1].

        Caller must have already bound the overlay program, set its
        per-frame uniforms (aircraft state, viewport), and have the
        FBO active. This method handles only the buffer upload + draw.
        """
        if vertices_np is None or len(vertices_np) == 0:
            return
        vertices_np = self._to_enu(np.asarray(vertices_np))
        n_floats = vertices_np.size
        n_bytes = n_floats * 4
        # Self-sufficient draw (production multi-widget finding): the
        # pass-level program binding has been observed to DROP between
        # consecutive draws (CURRENT_PROGRAM == 0; Qt-internal root
        # cause unidentified), after which the Qt-side uniform uploads
        # fail silently with GL_INVALID_OPERATION and PyOpenGL blames
        # whatever checked call runs next. Drain any stale error flag,
        # then re-assert our program before touching uniforms.
        gl.glGetError()
        if int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)) !=                 int(self._overlay_program.programId()):
            self._overlay_program.bind()
        self._overlay_vao.bind()
        try:
            self._overlay_vbo.bind()
            try:
                if n_bytes > self._overlay_vbo_capacity:
                    # Allocate a fresh buffer at >= the requested size.
                    self._overlay_vbo.allocate(
                        vertices_np.tobytes(), n_bytes)
                    self._overlay_vbo_capacity = n_bytes
                else:
                    self._overlay_vbo.write(0, vertices_np.tobytes(),
                                            n_bytes)
            finally:
                self._overlay_vbo.release()
            self._overlay_program.setUniformValue(
                self._overlay_u["u_color"],
                float(color_rgba[0]), float(color_rgba[1]),
                float(color_rgba[2]), float(color_rgba[3]))
            self._overlay_program.setUniformValue(
                self._overlay_u["u_fog_strength"], float(fog_strength))
            gl.glDrawArrays(mode, 0, vertices_np.shape[0])
        finally:
            self._overlay_vao.release()

    def _draw_overlay_cached(self, slot, vertices_np, color_rgba, mode,
                             fog_strength=0.0):
        """Like _draw_overlay_primitive, but with a persistent
        per-layer VBO: the ENU conversion and GPU upload run only when
        the source array (or the ENU frame: patch origin / lat_cos)
        changes. The big static layers re-uploaded ~1 MB every frame
        otherwise, felt as small periodic render ticks in flight."""
        if vertices_np is None or len(vertices_np) == 0:
            return
        gl.glGetError()
        if int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)) !=                 int(self._overlay_program.programId()):
            self._overlay_program.bind()
        st = self._layer_buffers.get(slot)
        if st is None:
            vao = QOpenGLVertexArrayObject()
            vao.create()
            vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            vbo.create()
            vbo.setUsagePattern(QOpenGLBuffer.UsagePattern.DynamicDraw)
            vao.bind()
            try:
                vbo.bind()
                try:
                    prog = self._overlay_program
                    prog.enableAttributeArray(
                        self._overlay_a_world_pos)
                    prog.setAttributeBuffer(
                        self._overlay_a_world_pos, gl.GL_FLOAT,
                        0, 3, 12)
                finally:
                    vbo.release()
            finally:
                vao.release()
            st = {"vao": vao, "vbo": vbo, "cap": 0,
                  "ref": None, "n": 0, "frame": None}
            self._layer_buffers[slot] = st
        frame_key = (self._patch_origin,
                     round(self._frame_lat_cos, 4))
        st["vao"].bind()
        try:
            cur = st["ref"]() if st["ref"] is not None else None
            if cur is not vertices_np or st["frame"] != frame_key:
                enu = self._to_enu(np.asarray(vertices_np))
                n_bytes = enu.size * 4
                st["vbo"].bind()
                try:
                    if n_bytes > st["cap"]:
                        st["vbo"].allocate(enu.tobytes(), n_bytes)
                        st["cap"] = n_bytes
                    else:
                        st["vbo"].write(0, enu.tobytes(), n_bytes)
                finally:
                    st["vbo"].release()
                st["ref"] = weakref.ref(vertices_np)
                st["n"] = int(enu.shape[0])
                st["frame"] = frame_key
            self._overlay_program.setUniformValue(
                self._overlay_u["u_color"],
                float(color_rgba[0]), float(color_rgba[1]),
                float(color_rgba[2]), float(color_rgba[3]))
            self._overlay_program.setUniformValue(
                self._overlay_u["u_fog_strength"],
                float(fog_strength))
            gl.glDrawArrays(mode, 0, st["n"])
        finally:
            st["vao"].release()

    # ------------------------------------------------------------------
    # Text overlay pass (Phase 4b — designator text on the GPU)
    # ------------------------------------------------------------------
    def _ensure_text_program(self):
        """Compile the text shader, build the glyph atlas, upload it as
        a GL_R8 texture, and configure the (lat, lon, elev_ft, u, v)
        vertex attribute layout. Idempotent."""
        if self._text_program is not None:
            return
        header = self._shader_header()
        vsrc = header + _TEXT_VERT_BODY
        if "es" in header:
            fheader = "#version 300 es\nprecision mediump float;\n"
        else:
            fheader = header
        fsrc = fheader + _TEXT_FRAG_BODY
        prog = QOpenGLShaderProgram()
        if not prog.addShaderFromSourceCode(
                QOpenGLShader.ShaderTypeBit.Vertex, vsrc):
            raise RuntimeError(
                f"text vertex shader compile failed: {prog.log()}")
        if not prog.addShaderFromSourceCode(
                QOpenGLShader.ShaderTypeBit.Fragment, fsrc):
            raise RuntimeError(
                f"text fragment shader compile failed: {prog.log()}")
        if not prog.link():
            raise RuntimeError(f"text shader link failed: {prog.log()}")
        self._text_a_world_pos = prog.attributeLocation("a_world_pos")
        self._text_a_uv = prog.attributeLocation("a_uv")
        if self._text_a_world_pos < 0 or self._text_a_uv < 0:
            raise RuntimeError(
                "text shader: required attribute not found")
        for name in ("u_vp", "u_ac_e", "u_ac_n", "u_earth_curv",
                     "u_color", "u_atlas"):
            loc = prog.uniformLocation(name)
            if loc < 0:
                raise RuntimeError(f"text shader: {name} not found")
            self._text_u[name] = loc
        self._text_program = prog

        # Build atlas at startup and upload as a single-channel GL_R8
        # texture. ES 3.0 requires the sized internal format GL_R8;
        # data is one byte per pixel from QImage's alpha plane.
        atlas_np, uvs = build_text_atlas()
        self._text_atlas_uvs = uvs
        tex_id = int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_R8,
            _TEXT_ATLAS_SIZE, _TEXT_ATLAS_SIZE, 0,
            gl.GL_RED, gl.GL_UNSIGNED_BYTE, atlas_np.tobytes())
        gl.glTexParameteri(gl.GL_TEXTURE_2D,
                           gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D,
                           gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D,
                           gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D,
                           gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        self._text_atlas_tex_id = tex_id

        self._text_vao = QOpenGLVertexArrayObject()
        self._text_vao.create()
        self._text_vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self._text_vbo.create()
        self._text_vbo.setUsagePattern(
            QOpenGLBuffer.UsagePattern.DynamicDraw)
        # Interleaved vec3 + vec2 = 5 floats = 20 bytes per vertex.
        # a_world_pos: offset 0, 3 floats. a_uv: offset 12, 2 floats.
        self._text_vao.bind()
        try:
            self._text_vbo.bind()
            try:
                prog.bind()
                prog.enableAttributeArray(self._text_a_world_pos)
                prog.setAttributeBuffer(
                    self._text_a_world_pos, gl.GL_FLOAT, 0, 3, 20)
                prog.enableAttributeArray(self._text_a_uv)
                prog.setAttributeBuffer(
                    self._text_a_uv, gl.GL_FLOAT, 12, 2, 20)
                prog.release()
            finally:
                self._text_vbo.release()
        finally:
            self._text_vao.release()

    def _draw_text_quads(self, verts_np, color_rgba):
        """Upload ``verts_np`` (Nx5 float32: lat, lon, elev_ft, u, v)
        and issue one glDrawArrays(GL_TRIANGLES). Caller must have
        bound the text program, set its per-frame uniforms, bound the
        atlas texture to TEXTURE0, and have the FBO active."""
        if verts_np is None or len(verts_np) == 0:
            return
        verts_np = self._to_enu(np.asarray(verts_np))
        n_bytes = verts_np.size * 4
        self._text_vao.bind()
        try:
            self._text_vbo.bind()
            try:
                if n_bytes > self._text_vbo_capacity:
                    self._text_vbo.allocate(verts_np.tobytes(), n_bytes)
                    self._text_vbo_capacity = n_bytes
                else:
                    self._text_vbo.write(0, verts_np.tobytes(), n_bytes)
            finally:
                self._text_vbo.release()
            self._text_program.setUniformValue(
                self._text_u["u_color"],
                float(color_rgba[0]), float(color_rgba[1]),
                float(color_rgba[2]), float(color_rgba[3]))
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, verts_np.shape[0])
        finally:
            self._text_vao.release()

    def _draw_text_quads_cached(self, slot, verts_np, color_rgba):
        """Like _draw_text_quads, but with a persistent per-slot VBO:
        the ENU conversion and GPU upload run only when the source
        array (identity) or the ENU frame (patch origin / lat_cos)
        changes. Obstacle/flag quads come from a TTL-cached collector,
        so the same array object is handed back frame after frame —
        re-converting + re-uploading it every frame was the bulk of the
        obstacle draw cost. Caller must have bound the text program, set
        its per-frame uniforms, and bound the atlas to TEXTURE0."""
        if verts_np is None or len(verts_np) == 0:
            return
        st = self._text_layer_buffers.get(slot)
        if st is None:
            vao = QOpenGLVertexArrayObject()
            vao.create()
            vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            vbo.create()
            vbo.setUsagePattern(QOpenGLBuffer.UsagePattern.DynamicDraw)
            vao.bind()
            try:
                vbo.bind()
                try:
                    prog = self._text_program
                    prog.enableAttributeArray(self._text_a_world_pos)
                    prog.setAttributeBuffer(
                        self._text_a_world_pos, gl.GL_FLOAT, 0, 3, 20)
                    prog.enableAttributeArray(self._text_a_uv)
                    prog.setAttributeBuffer(
                        self._text_a_uv, gl.GL_FLOAT, 12, 2, 20)
                finally:
                    vbo.release()
            finally:
                vao.release()
            st = {"vao": vao, "vbo": vbo, "cap": 0,
                  "ref": None, "n": 0, "frame": None}
            self._text_layer_buffers[slot] = st
        frame_key = (self._patch_origin,
                     round(self._frame_lat_cos, 4))
        st["vao"].bind()
        try:
            cur = st["ref"]() if st["ref"] is not None else None
            if cur is not verts_np or st["frame"] != frame_key:
                enu = self._to_enu(np.asarray(verts_np))
                n_bytes = enu.size * 4
                st["vbo"].bind()
                try:
                    if n_bytes > st["cap"]:
                        st["vbo"].allocate(enu.tobytes(), n_bytes)
                        st["cap"] = n_bytes
                    else:
                        st["vbo"].write(0, enu.tobytes(), n_bytes)
                finally:
                    st["vbo"].release()
                st["ref"] = weakref.ref(verts_np)
                st["n"] = int(enu.shape[0])
                st["frame"] = frame_key
            self._text_program.setUniformValue(
                self._text_u["u_color"],
                float(color_rgba[0]), float(color_rgba[1]),
                float(color_rgba[2]), float(color_rgba[3]))
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, st["n"])
        finally:
            st["vao"].release()

    def _render_text_groups_cached(self, groups, slot_prefix,
                                   w, h, ac_lat, ac_lon, ac_alt_ft,
                                   pitch_deg, roll_deg, heading_deg,
                                   pixels_per_deg):
        """Draw a dict ``{color_rgba: verts_np}`` of textured quads with
        the shared text-program state bound ONCE, then one cached draw
        per colour group. Replaces the previous per-group
        _render_text_overlay loop, which rebound the program, re-set
        every uniform, re-bound the atlas, and re-uploaded the buffer
        for each of the (up to eight) obstacle colour groups every
        frame."""
        if not groups:
            return
        self._ensure_text_program()
        prog = self._text_program
        prog.bind()
        try:
            prog.setUniformValue(self._text_u["u_vp"], self._frame_vp)
            prog.setUniformValue(
                self._text_u["u_ac_e"], float(self._frame_ac_e))
            prog.setUniformValue(
                self._text_u["u_ac_n"], float(self._frame_ac_n))
            prog.setUniformValue(
                self._text_u["u_earth_curv"], float(self._frame_curv))
            prog.setUniformValue(self._text_u["u_atlas"], 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D,
                             int(self._text_atlas_tex_id))
            for color, verts in groups.items():
                if verts is None or verts.size == 0:
                    continue
                self._draw_text_quads_cached(
                    f"{slot_prefix}:{color}", verts, color)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        finally:
            prog.release()

    def _render_text_overlay(self, verts_np, color_rgba,
                             w, h, ac_lat, ac_lon, ac_alt_ft,
                             pitch_deg, roll_deg, heading_deg,
                             pixels_per_deg):
        """Compile-on-demand, bind program + atlas, set uniforms,
        draw, release. The text shader is its own program because
        the fragment stage differs from the flat-color overlay path."""
        if verts_np is None or len(verts_np) == 0:
            return
        self._ensure_text_program()
        prog = self._text_program
        prog.bind()
        try:
            prog.setUniformValue(self._text_u["u_vp"], self._frame_vp)
            prog.setUniformValue(
                self._text_u["u_ac_e"], float(self._frame_ac_e))
            prog.setUniformValue(
                self._text_u["u_ac_n"], float(self._frame_ac_n))
            prog.setUniformValue(
                self._text_u["u_earth_curv"], float(self._frame_curv))
            prog.setUniformValue(self._text_u["u_atlas"], 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D,
                             int(self._text_atlas_tex_id))
            self._draw_text_quads(verts_np, color_rgba)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        finally:
            prog.release()

    def _render_overlays(self, w, h, ac_lat, ac_lon, ac_alt_ft,
                         pitch_deg, roll_deg, heading_deg, pixels_per_deg,
                         range_nm=None):
        """Run every overlay pass that has been migrated to the GPU
        pipeline. Bound after the terrain draw inside the FBO so the
        overlays composite directly with the terrain at full GPU
        speed.

        Phase 1: water polygons (this commit).
        Phase 2+: obstacles, runways, markings, airport flags.
        """
        self._ensure_overlay_program()
        prog = self._overlay_program
        prog.bind()
        try:
            prog.setUniformValue(self._overlay_u["u_vp"],
                                 self._frame_vp)
            prog.setUniformValue(self._overlay_u["u_ac_e"],
                                 float(self._frame_ac_e))
            prog.setUniformValue(self._overlay_u["u_ac_n"],
                                 float(self._frame_ac_n))
            prog.setUniformValue(self._overlay_u["u_earth_curv"],
                                 float(self._frame_curv))
            prog.setUniformValue(self._overlay_u["u_haze_inv"],
                                 float(self._frame_haze_inv))


            # Phase 1 — water.
            p = self._parent
            if (getattr(p, "water_db", None) is not None
                    and p.water_db.ready
                    and range_nm is not None):
                with p._perf.time("water"):
                    with p._perf.time("water.collect"):
                        tris = p._collect_water_triangles(
                            ac_lat, ac_lon, range_nm)
                    if tris is not None and tris.size > 0:
                        # COLOR_WATER from svs.py = (20, 80, 150).
                        color = (20 / 255.0, 80 / 255.0,
                                 150 / 255.0, 1.0)
                        with p._perf.time("water.gl_draw"):
                            self._draw_overlay_cached(
                                "water", tris, color,
                                gl.GL_TRIANGLES, fog_strength=1.0)

            # Highways (issue #35): decimated OSM motorway/trunk
            # polylines draped at terrain elevation. Ground features:
            # full haze, drawn between water and the symbology layers.
            if (getattr(p, "highway_db", None) is not None
                    and p.highway_db.ready
                    and range_nm is not None):
                with p._perf.time("highways"):
                    with p._perf.time("highways.collect"):
                        hwy = p._collect_highways(
                            ac_lat, ac_lon, ac_alt_ft, range_nm)
                    if hwy is not None and hwy.size:
                        with p._perf.time("highways.gl_draw"):
                            self._draw_overlay_cached(
                                "highways", hwy,
                                (0.10, 0.10, 0.10, 1.0),
                                gl.GL_LINES, fog_strength=1.0)

            # Obstacles: world-scaled FAA-symbol billboards (the
            # Garmin/ForeFlight SVS convention) — one screen-facing
            # quad per obstacle, base at the ground, tip at the
            # obstacle top, so the symbol's size IS the vertical
            # extent and perspective growth gives the closure cue.
            # Triangle-with-dot below 1000 ft AGL, spire above.
            if (getattr(p, "obstacle_db", None) is not None
                    and p.obstacle_db.ready
                    and range_nm is not None):
                with p._perf.time("obstacles"):
                    with p._perf.time("obstacles.collect"):
                        self._ensure_text_program()
                        groups = p._collect_obstacles(
                            ac_lat, ac_lon, ac_alt_ft, range_nm,
                            self._text_atlas_uvs)
                    if groups:
                        with p._perf.time("obstacles.gl_draw"):
                            prog.release()
                            try:
                                self._render_text_groups_cached(
                                    groups, "obstacle",
                                    w, h, ac_lat, ac_lon,
                                    ac_alt_ft, pitch_deg,
                                    roll_deg, heading_deg,
                                    pixels_per_deg)
                            finally:
                                prog.bind()

            # Phase 3 — runway polygons (the asphalt-coloured quad).
            # One big triangle list across every visible runway, one
            # draw call. Designator text still CPU until Phase 4b.
            if (getattr(p, "airport_db", None) is not None
                    and p.airport_db.ready
                    and range_nm is not None):
                with p._perf.time("runway.polygon"):
                    with p._perf.time("runway.polygon.collect"):
                        rwy_tris = p._collect_runway_polygons(
                            ac_lat, ac_lon, ac_alt_ft, range_nm,
                            heading_deg)
                    if rwy_tris is not None and rwy_tris.size > 0:
                        # RWY_FILL = (55, 55, 55) asphalt grey. Cached-VBO path:
                        # the polygon collector returns a stable array per TTL,
                        # so the ENU convert + ~MB upload only re-run when the
                        # runway set or patch origin changes, not every frame.
                        with p._perf.time("runway.polygon.gl_draw"):
                            self._draw_overlay_cached(
                                "runway_poly",
                                rwy_tris,
                                (55/255.0, 55/255.0, 55/255.0, 1.0),
                                gl.GL_TRIANGLES, fog_strength=0.4)

                # Phase 4a — non-text runway markings (threshold bars,
                # aiming point, TDZ, centerline stripes, side stripes,
                # chevrons). One big white triangle list per frame.
                # heading_deg is passed because the behind-camera
                # triangle filter depends on it.
                with p._perf.time("runway.markings"):
                    with p._perf.time("runway.markings.collect"):
                        mk_tris = p._collect_runway_markings(
                            ac_lat, ac_lon, ac_alt_ft, range_nm,
                            heading_deg)
                    if mk_tris is not None and mk_tris.size > 0:
                        # WHITE marking colour (245, 245, 245). Cached-VBO path
                        # (markings collector is TTL-cached, stable identity).
                        with p._perf.time("runway.markings.gl_draw"):
                            self._draw_overlay_cached(
                                "runway_markings",
                                mk_tris,
                                (245/255.0, 245/255.0,
                                 245/255.0, 1.0),
                                gl.GL_TRIANGLES)

            # Phase 4b — runway designator text. Collected as
            # (lat, lon, elev_ft, u, v) quads per glyph; drawn with
            # the dedicated text shader + glyph-atlas texture. The
            # text program is released here so the smoke-test path
            # below still sees the overlay program bound.
            if (getattr(p, "airport_db", None) is not None
                    and p.airport_db.ready
                    and range_nm is not None):
                with p._perf.time("runway.designator"):
                    with p._perf.time("runway.designator.collect"):
                        # Ensure the atlas exists before the parent can
                        # use its UVs to lay out per-glyph quads.
                        self._ensure_text_program()
                        des_verts = p._collect_runway_designator_quads(
                            ac_lat, ac_lon, ac_alt_ft, range_nm,
                            heading_deg, self._text_atlas_uvs)
                    if des_verts is not None and des_verts.size > 0:
                        # Release the overlay program around the text
                        # draw; the text shader needs to be the active
                        # program. Rebind after so the smoke-test
                        # diagnostic still has the overlay program.
                        prog.release()
                        try:
                            # Cached-VBO text path: the designator collector is
                            # async/TTL-cached (stable array identity), so the
                            # per-glyph quad upload only re-runs when the runway
                            # set or patch origin changes -- not every frame.
                            # Single white colour -> a one-entry group dict.
                            with p._perf.time("runway.designator.gl_draw"):
                                self._render_text_groups_cached(
                                    {(245/255.0, 245/255.0, 245/255.0, 1.0):
                                     des_verts},
                                    "runway_designator",
                                    w, h, ac_lat, ac_lon, ac_alt_ft,
                                    pitch_deg, roll_deg, heading_deg,
                                    pixels_per_deg)
                        finally:
                            prog.bind()

            # Phase 5 — airport flags + identifier text. Pole =
            # GL_LINES, flag rectangle = yellow triangles, identifier
            # = black glyph quads INSIDE the flag body (issue #36)
            # via the Phase 4b atlas.
            if (getattr(p, "airport_db", None) is not None
                    and p.airport_db.ready
                    and range_nm is not None):
                with p._perf.time("airports.flag"):
                    self._ensure_text_program()
                    flags = p._collect_airport_flags(
                        ac_lat, ac_lon, ac_alt_ft, range_nm,
                        pixels_per_deg, self._text_atlas_uvs)
                    if flags is not None:
                        FLAG_YELLOW = (1.0, 220 / 255.0, 0.0, 1.0)
                        FLAG_DIM = (0.40, 0.345, 0.0, 1.0)
                        TEXT_N = (0.0, 0.0, 0.0, 1.0)
                        TEXT_M = (0.45, 0.45, 0.45, 1.0)
                        # Terrain-masked flags (behind ridges) draw
                        # dimmed so they read as "behind", not "on" the
                        # near mountain. Poles + flag rectangles go
                        # through the cached overlay VBOs and the
                        # identifier text through the cached text VBOs,
                        # so a static flag field doesn't re-convert +
                        # re-upload every frame (the same fix obstacles
                        # got — this was 9 ms/frame at metro density).
                        for sfx, pc, qc in (
                                ("", FLAG_YELLOW, FLAG_YELLOW),
                                ("_masked", FLAG_DIM, FLAG_DIM)):
                            poles = flags.get("poles" + sfx)
                            if poles is not None and poles.size:
                                self._set_pole_line_width()
                                self._draw_overlay_cached(
                                    "flag_poles" + sfx, poles, pc,
                                    gl.GL_LINES, fog_strength=0.4)
                                gl.glLineWidth(1.0)
                            tris = flags.get("flags" + sfx)
                            if tris is not None and tris.size:
                                self._draw_overlay_cached(
                                    "flag_tris" + sfx, tris, qc,
                                    gl.GL_TRIANGLES, fog_strength=0.4)
                        # Identifier text: both variants under one text-
                        # program binding, keyed by colour so the normal
                        # (black) and masked (grey) glyph buffers stay
                        # distinct cached slots.
                        text_groups = {}
                        tn = flags.get("text")
                        if tn is not None and tn.size:
                            text_groups[TEXT_N] = tn
                        tm = flags.get("text_masked")
                        if tm is not None and tm.size:
                            text_groups[TEXT_M] = tm
                        if text_groups:
                            prog.release()
                            try:
                                self._render_text_groups_cached(
                                    text_groups, "flag",
                                    w, h, ac_lat, ac_lon, ac_alt_ft,
                                    pitch_deg, roll_deg, heading_deg,
                                    pixels_per_deg)
                            finally:
                                prog.bind()

            # Smoke-test triangle path (kept for diagnostics).
            if getattr(p, "_gl_overlay_smoketest", False):
                d_deg = 0.1
                test_elev = float(ac_alt_ft) - 2000.0
                tri = np.array([
                    [ac_lat + d_deg, ac_lon,        test_elev],
                    [ac_lat + d_deg, ac_lon + d_deg, test_elev],
                    [ac_lat,         ac_lon + d_deg, test_elev],
                ], dtype=np.float32)
                self._draw_overlay_primitive(
                    tri, (1.0, 0.0, 1.0, 1.0), gl.GL_TRIANGLES)
        finally:
            prog.release()

    def _set_pole_line_width(self):
        """Set the 2 px pole line width, clamped to what the driver
        accepts. Probe by trying: core-profile desktop contexts reject
        widths > 1.0 with GL_INVALID_VALUE even though the
        GL_ALIASED_LINE_WIDTH_RANGE query advertises a wide range."""
        if self._max_line_width is None:
            try:
                gl.glLineWidth(2.0)
                self._max_line_width = 2.0
            except Exception:
                self._max_line_width = 1.0
        gl.glLineWidth(self._max_line_width)

    def _shader_header(self) -> str:
        """Pick the right #version header for the active context."""
        fmt = QOpenGLContext.currentContext().format()
        if fmt.renderableType() == QSurfaceFormat.RenderableType.OpenGLES:
            # Pi 5 V3D supports ES 3.0+. precision required on ES.
            return "#version 300 es\nprecision highp float;\n"
        # Desktop GL 3.0 → GLSL 1.30; same in/out syntax, no precision
        # qualifier (it'd be a syntax error on desktop).
        return "#version 130\n"

    def _ensure_program(self):
        if self._program is not None:
            return
        header = self._shader_header()
        vsrc = header + _VERT_BODY
        # Fragment needs explicit precision for ES 3.0; on desktop it's
        # ignored. We add it inside the body's frag header below.
        fheader = header
        if "es" in header:
            # ES requires explicit precision in fragment too.
            # highp float: the world-anchored noise hash needs it
            # (mediump falls apart at continental coordinates);
            # ES 3.0 guarantees fragment highp support.
            fheader = ("#version 300 es\nprecision highp float;\n"
                       "precision mediump sampler2D;\n")
        fsrc = fheader + _FRAG_BODY
        prog = QOpenGLShaderProgram()
        if not prog.addShaderFromSourceCode(
                QOpenGLShader.ShaderTypeBit.Vertex, vsrc):
            raise RuntimeError(
                f"vertex shader compile failed: {prog.log()}")
        if not prog.addShaderFromSourceCode(
                QOpenGLShader.ShaderTypeBit.Fragment, fsrc):
            raise RuntimeError(
                f"fragment shader compile failed: {prog.log()}")
        if not prog.link():
            raise RuntimeError(f"shader link failed: {prog.log()}")
        self._a_position = prog.attributeLocation("a_cell")
        if self._a_position < 0:
            raise RuntimeError("a_cell attribute missing after link")
        for name in ("u_ac_alt_ft",
                     "u_vp", "u_ac_e", "u_ac_n", "u_earth_curv",
                     "u_patch_texels", "u_haze_inv",
                     "u_patch_extent_m", "u_tex_xform",
                     "u_level_spacing", "u_level_origin",
                     "u_level_half", "u_morph_on",
                     "u_heightmap",
                     "u_green_ft", "u_yellow_ft", "u_near_airport",
                     "u_apt_gate_ft", "u_safe_grad", "u_tex_amp",
                     "u_grid_amp"):
            loc = prog.uniformLocation(name)
            if loc < 0:
                log.warning("uniform %s not found (optimised out?)", name)
            self._u[name] = loc
        self._program = prog

    def _ensure_mesh(self):
        if self._vao is not None:
            return

        vao = QOpenGLVertexArrayObject()
        if not vao.create():
            raise RuntimeError("could not create QOpenGLVertexArrayObject")

        verts, indices, annulus_idx = self._build_clipmap_template()

        vao.bind()
        try:
            vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            if not vbo.create():
                raise RuntimeError("could not create vertex buffer")
            vbo.setUsagePattern(QOpenGLBuffer.UsagePattern.StaticDraw)
            vbo.bind()
            vbo.allocate(verts.tobytes(), int(verts.nbytes))

            self._program.bind()
            try:
                self._program.enableAttributeArray(self._a_position)
                self._program.setAttributeBuffer(
                    self._a_position, gl.GL_FLOAT, 0, 2, 0)
            finally:
                self._program.release()

            ibo = QOpenGLBuffer(QOpenGLBuffer.Type.IndexBuffer)
            if not ibo.create():
                raise RuntimeError("could not create index buffer")
            ibo.setUsagePattern(QOpenGLBuffer.UsagePattern.StaticDraw)
            ibo.bind()
            ibo.allocate(indices.tobytes(), int(indices.nbytes))
        finally:
            vao.release()

        # Annulus IBO for the outer levels (bound in place of the full
        # IBO per draw — element binding is VAO state, so rebinding
        # inside the bound VAO swaps it).
        ibo_a = QOpenGLBuffer(QOpenGLBuffer.Type.IndexBuffer)
        ibo_a.create()
        ibo_a.setUsagePattern(QOpenGLBuffer.UsagePattern.StaticDraw)
        vao.bind()
        ibo_a.bind()
        ibo_a.allocate(annulus_idx.tobytes(), int(annulus_idx.nbytes))
        ibo.bind()   # leave the full IBO as the VAO default
        vao.release()

        self._vao = vao
        self._vbo = vbo
        self._ibo = ibo
        self._ibo_annulus = ibo_a
        self._index_count = int(indices.size)
        self._annulus_count = int(annulus_idx.size)

        log.info(
            "SVSGLRenderer clipmap template: %d vertices, %d indices "
            "(%d cells, %d levels)",
            verts.shape[0], self._index_count,
            self._parent._clip_cells, self._parent._clip_levels)

    @staticmethod
    def _patch_origin_for(ac_lat: float, ac_lon: float) -> tuple[int, int]:
        """Pick the 2x2-tile patch origin that keeps the aircraft at
        least 0.5 deg (~30 NM) from every edge. With ``floor(x - 0.5)``
        the rebuild happens at HALF-integer degree boundaries (..., -0.5,
        0.5, 1.5, ...); at every boundary the aircraft is 0.5 deg inside
        the new patch on the side it just crossed from, and 1.5 deg from
        the far edge.

        With the old ``floor(x - 1.0)`` the aircraft sat at the patch
        edge just before integer-degree crossings, so the
        ``GL_CLAMP_TO_EDGE`` heightmap sampler painted fake-flat terrain
        ahead of the nose."""
        return (int(math.floor(ac_lat - 0.5)),
                int(math.floor(ac_lon - 0.5)))

    def _ensure_heightmap(self, ac_lat: float, ac_lon: float):
        """(Re)build the heightmap texture when the aircraft crosses
        into a new 2x2-tile patch. See :meth:`_patch_origin_for` for
        the centring choice."""
        origin = self._patch_origin_for(ac_lat, ac_lon)
        start_lat, start_lon = origin
        if (self._heightmap_tex_id is not None
                and self._patch_origin == origin):
            return

        patch = self._build_patch(start_lat, start_lon)
        h, w = patch.shape
        self._patch_texels = float(w)

        if self._heightmap_tex_id is None:
            tex_id_arr = gl.glGenTextures(1)
            # PyOpenGL returns either an int or a numpy array of ints
            # depending on count; coerce to int either way.
            self._heightmap_tex_id = int(
                tex_id_arr if np.isscalar(tex_id_arr) else tex_id_arr[0])

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._heightmap_tex_id)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_R32F,
            w, h, 0,
            gl.GL_RED, gl.GL_FLOAT, patch.tobytes())
        # Linear filtering of float textures requires
        # OES_texture_float_linear on ES; if unavailable the driver
        # will fall back to nearest. Either is fine for Step 4.
        gl.glTexParameteri(gl.GL_TEXTURE_2D,
                           gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D,
                           gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D,
                           gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D,
                           gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)

        self._patch_origin = origin
        # Bounds: the 2x2 patch covers
        # lat ∈ [start_lat, start_lat + 2], lon ∈ [start_lon, start_lon + 2].
        self._patch_bounds = (
            float(start_lat), float(start_lat + 2),
            float(start_lon), float(start_lon + 2))
        log.info(
            "SVSGLRenderer heightmap built: 2x2 patch from (%d, %d), "
            "shape %dx%d",
            start_lat, start_lon, w, h)

    @staticmethod
    def _resample_tile(tile: np.ndarray, n: int) -> np.ndarray:
        """Bilinearly resample a square tile to n x n (used to bring a
        coarser SRTM3 tile up to the patch resolution when the tile
        tree mixes resolutions)."""
        src_n = tile.shape[0]
        if src_n == n:
            return tile
        x = np.linspace(0.0, src_n - 1.0, n)
        idx = np.arange(src_n, dtype=np.float64)
        rows = np.empty((src_n, n), dtype=np.float32)
        for i in range(src_n):
            rows[i] = np.interp(x, idx, tile[i])
        out = np.empty((n, n), dtype=np.float32)
        for j in range(n):
            out[:, j] = np.interp(x, idx, rows[:, j])
        return out

    def _build_patch(self, start_lat: int, start_lon: int) -> np.ndarray:
        """Assemble four 1-degree tiles into a square float32 patch
        with (0, 0) = SW corner. Tiles may be 1201 (SRTM3) or 3601
        (GLO-30) per file; the patch assembles at the finest
        resolution present, then decimates by powers of two until it
        fits within parent.heightmap_max_px and the driver's
        GL_MAX_TEXTURE_SIZE. CPU elevation sampling is unaffected —
        it reads native tiles from the cache."""
        cache = self._parent.cache
        tiles = {}
        max_n = 0
        for di in range(_PATCH_TILES):
            for dj in range(_PATCH_TILES):
                t = cache.get(start_lat + di, start_lon + dj)
                tiles[(di, dj)] = t
                if t is not None:
                    max_n = max(max_n, t.shape[0])
        N = max_n if max_n else 1201
        # Assemble WITHOUT duplicating the shared tile edges: a 3601-px
        # GLO-30 tile spans its degree INCLUSIVE of both edges, so adjacent
        # tiles overlap by one row/col and the patch has 2*(N-1)+1 unique
        # samples per side -- row i sits exactly at global native grid index
        # start*(N-1) + i. That keeps the power-of-two decimation below
        # PHASE-ANCHORED to the global grid ((N-1) per degree is even), so
        # every rebuild's decimated texels describe the SAME ground as the
        # previous patch's. The old duplicated-seam layout (2N per side, N
        # odd) flipped the sampling parity at every patch rebuild, and the
        # whole scene visibly reshaped at half-degree crossings -- the
        # residual terrain "morphing", worst over steep relief.
        stride = N - 1
        side = _PATCH_TILES * stride + 1
        patch = np.zeros((side, side), dtype=np.float32)
        # Place missing tiles (zeros) first so a present neighbour's real
        # values win the shared row/col.
        order = sorted(tiles.items(), key=lambda kv: kv[1] is not None)
        for (di, dj), tile in order:
            if tile is None:
                tile_data = np.zeros((N, N), dtype=np.float32)
            else:
                tile_data = self._resample_tile(
                    tile.astype(np.float32, copy=False), N)
            # Flip top-to-bottom so row 0 of the placement = south.
            tile_data = tile_data[::-1, :]
            patch[di * stride:di * stride + N,
                  dj * stride:dj * stride + N] = tile_data

        cap = int(getattr(self._parent, "heightmap_max_px", 4096))
        try:
            gl_max = int(gl.glGetIntegerv(gl.GL_MAX_TEXTURE_SIZE))
            # Only honor a real, positive driver limit. Without a current GL
            # context (unit tests / headless) glGetIntegerv may RETURN 0 rather
            # than raising — min(cap, 0) would collapse the heightmap to 1px.
            if gl_max > 0:
                cap = min(cap, gl_max)
        except Exception:
            pass   # no current context — config cap only
        step = 1
        while patch.shape[0] // step > cap:
            step *= 2
        if step > 1:
            patch = np.ascontiguousarray(patch[::step, ::step])
            log.info(
                "SVSGLRenderer heightmap decimated x%d to %dpx "
                "(cap %d)", step, patch.shape[0], cap)
        return patch

    def _build_clipmap_template(self):
        """One (n+1) x (n+1) vertex grid of integer cell coordinates,
        reused for every clipmap level via the u_level_spacing /
        u_level_origin uniforms."""
        n = self._parent._clip_cells
        m = n + 1
        i_grid, j_grid = np.mgrid[0:m, 0:m]
        verts = np.column_stack([
            j_grid.ravel(), i_grid.ravel()]).astype(np.float32)
        ci, cj = np.mgrid[0:n, 0:n]

        def make_idx(mask):
            a = ci[mask].ravel()
            b = cj[mask].ravel()
            v00 = (a * m + b)
            v10 = ((a + 1) * m + b)
            v01 = (a * m + b + 1)
            v11 = ((a + 1) * m + b + 1)
            idx = np.empty(v00.size * 6, dtype=np.uint32)
            idx[0::6] = v00
            idx[1::6] = v10
            idx[2::6] = v01
            idx[3::6] = v10
            idx[4::6] = v11
            idx[5::6] = v01
            return idx

        full = make_idx(np.ones((n, n), dtype=bool))
        # Annulus: outer levels skip the centre hole that finer levels
        # cover. Hole half-width = n/4 - 1 cells: one coarse cell of
        # margin against the independent per-level snapping, so the
        # finer level always overlaps the hole edge (no gaps), while
        # the screen-dominant near region stops being drawn twice.
        h = n // 4 - 1
        lo, hi = n // 2 - h, n // 2 + h
        hole = ((ci >= lo) & (ci < hi) & (cj >= lo) & (cj < hi))
        annulus = make_idx(~hole)
        return verts, full, annulus
