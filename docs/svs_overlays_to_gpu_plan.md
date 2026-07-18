# SVS overlays → GPU plan

> **STATUS: COMPLETE — historical plan (Stage 2, overlays on GPU).** All phases
> (0-5: water, obstacles, runways, markings, designator text, airport flags +
> text) shipped. The SVS is now GL-only with no CPU overlay path, and total SVS
> frame cost fell from the ~28 ms measured here to ~7 ms. **Live status for the
> whole SVS GPU effort lives in [svs_structural_plan.md](svs_structural_plan.md)**
> (P1 = flags/text, P2 = CPU-era deletion); this file is historical context only.

## Why

Pyefis's main Python thread is **pegged at 90-95% CPU** during SVS rendering on
Pi 5, capping the display at ~28 FPS even though the Pi 5's GL and CPU are
otherwise idle (other 3 cores at ~75% idle, GPU mostly unused). The GIL serializes
all Python work onto one core, and `_draw_water` / `_draw_runways` /
`_draw_obstacles` are 24+ ms of per-frame Python work — projecting hundreds of
vertices, calling QPainter primitives, querying SQLite.

Today's SVS pipeline is **GL for the terrain mesh only**; every other layer
(water, runways + markings, obstacles, airport flags) is drawn on top in
QPainter on the CPU. That was the right call when the GL renderer was
experimental, but it's now the headline performance bottleneck.

This document is the plan to migrate those overlays into the existing GL
pipeline so the bulk of per-frame work moves to the GPU.

## Current state (commit `60918f6`)

```
SVS frame (28 ms total on Pi 5):
  ├─ gl_terrain  ─────────────  4.1 ms   ← already GPU; the terrain mesh
  ├─ water       ─────────────  14.6 ms  ← CPU, ~200 polys × 32 vertices
  │     ├─ water.query (sqlite)   5.7 ms
  │     ├─ water.project (CPU)    5.8 ms
  │     ├─ water.srtm_sample      0.9 ms
  │     └─ water.drawPolygon      0.6 ms
  ├─ obstacles   ─────────────  5.7 ms   ← CPU, ~25 towers
  ├─ runways     ─────────────  3.6 ms   ← CPU, polygon + markings
  ├─ airports.flag             0.1 ms   ← CPU, cheap
  └─ other                     ~1 ms
```

The `gl_terrain` path renders into an **offscreen FBO**, then `QPainter`
`drawImage`s the result onto the AI viewport. After that, all the QPainter
overlays run on top, in CPU. See [svs_gl.py:344](../src/pyefis/instruments/ai/svs_gl.py#L344)
(`SVSGLRenderer.draw`).

## Target state

Same offscreen FBO pipeline, but the FBO render does **multiple passes** —
terrain, then water, then runways, then obstacles, then flags — all into the
same texture before the QPainter blit. Per-frame Python work in `_draw_water`,
`_draw_runways`, `_draw_obstacles`, `_draw_water` falls to ≤2 ms combined
(just buffer-upload calls and uniform binding). Frame budget drops to ~7 ms
SVS = ~100 FPS headroom.

The trade-off: GL doesn't have native primitives for what QPainter gives us
free — concave polygon fill, perspective-warped text, sub-pixel anti-aliased
lines. Each overlay needs a tessellation / atlas / shader decision. The
runway designator text is the hardest case and has its own section below.

## Architectural decisions to lock in first

### 1. Where do GL overlays render?

**Option A — same FBO as terrain:** Extend `SVSGLRenderer._render_to_image`
to dispatch a sequence of shader programs and meshes after the terrain
draw. One FBO bind, one final `glReadPixels`/`fbo.toImage()`, one
`QPainter.drawImage`. **Chosen** — minimal blit overhead, simplest
architecture, matches the existing pipeline.

Option B (rejected): one FBO per overlay layer with explicit composition.
N+1 blits is wasteful when the same FBO can be re-used.

Option C (rejected): render the SVS directly to the AI's onscreen surface
(skip the FBO). Mixing GL state with Qt's QGraphicsView paint pipeline is
fragile — the existing offscreen indirection was deliberate.

### 2. Vertex format

Most overlays need: world-space position (lat, lon, elev_ft) and per-vertex
color (or a per-draw color uniform). For now use a **shared interleaved
vertex layout** with 5 floats per vertex:

```
vec3 a_world_pos;   // lat (deg), lon (deg), elev (ft)
vec2 a_uv_or_meta;  // u for runway markings; (0,0) when unused
```

Per-feature shaders can ignore `a_uv_or_meta`. Reuse the same vertex shader
projection math the terrain uses; just feed it a `world_pos` instead of
sampling a heightmap.

### 3. Tessellation library

OSM water polygons are **not guaranteed convex** (long meandering lakes,
peninsulas, islands as holes). QPainter handles concave fills natively; GL
doesn't. We need a polygon tessellator.

Options:
- **earcut-python** — pure Python, simple API, MIT, ~1500 LOC, no C deps.
  Handles holes (multi-ring polygons). Used by Mapbox and others. Pip install.
- **libtess2** — C library with Python bindings (`mapbox-earcut` etc.).
  Faster but adds a C dep.
- **Hand-rolled ear-clipping** — ~200 LOC of Python. Avoids the dep but
  reinvents the wheel for an edge-case-heavy algorithm.

**Choice: earcut-python**. Pip-installable, pure Python, fast enough at
build-time (we tessellate once per polygon at DB load, cache the result).

Tessellation should happen **at water DB build time, not at render time**.
Store the triangle index list alongside the vertices in the sqlite BLOB.
This keeps per-frame work to just buffer-upload + draw call.

### 4. Text rendering

Runway designators ("13L", "31R", aim-point numerals) currently use
`QPainter.drawText` with a `quadToQuad` perspective transform. GL doesn't
have native text.

**Choice: pre-render a bitmap font atlas** at startup. One 256×256 R8
texture holds the glyphs we need (`0-9`, `A-Z`, `-`). Each glyph
is a textured quad; the perspective math projects four corner UVs. Cheap
and crisp.

All SVS text moves with its overlay phase — runway designators in Phase 4,
airport-flag identifiers in Phase 5. No interim "text still in QPainter"
hybrid. The non-SVS text widgets (airspeed/altimeter tapes, compass,
HSI digits) are separate widget classes and stay on QPainter.

### 5. Elevation handling for water

Water polygons need a surface elevation per polygon (lake at 535 ft MSL,
ocean at 0 ft, etc.). The existing CPU path samples SRTM at vertex 0 when
the DB doesn't store an explicit `elev_ft`. That batched lookup is now
0.9 ms / frame — keep it on CPU. Store the resolved `elev_ft` per polygon
in a uniform; the GL vertex shader uses it directly. No SRTM sampling on GPU.

### 6. Camera-inside-polygon (the bug we just hit)

The CPU code now detects "camera is inside this water polygon" via PIP
and switches to a foreground-fill projection. On the GPU side, this gets
simpler: **render the polygon's flat water surface as full triangles**,
not just the shoreline outline. When the camera is inside, the triangles
ahead project as the lake's foreground naturally — no clip-and-close-with-
bottom-corners trick needed. The PIP test + 50 NM surround + screen-bottom
corners all go away.

This is one of the strongest arguments for moving water to GL: the entire
class of "polygon projection bugs" disappears because we project the
**filled surface**, not the boundary.

## Migration sequence

Phases are ordered by **value/effort ratio** — water first because it's
60% of the win, simplest tessellation case, and would also collapse the
recent camera-inside bug class.

### Phase 0 — Infrastructure (1 day)
- Add a `_render_overlays` step inside `SVSGLRenderer._render_to_image`,
  after the terrain draw but before `toImage()`.
- Define the shared vertex format. Build one `QOpenGLBuffer` per overlay
  type that we re-upload each frame (the data isn't large — water at 200
  polys × 32 vertices × 5 floats = 32 KB).
- Add a "generic flat-color shader" — vertex shader projects (lat, lon,
  elev_ft) using the same projection math as the terrain shader; fragment
  shader outputs a uniform color. Reused by water, runway polygons, and
  obstacle poles.
- No feature flag: each phase fully replaces its CPU code path in the
  same commit. Forward-only migration; revert is via git if a phase
  regresses. The user has explicitly signed off on this — release-quality
  performance is impossible with the current CPU load, so we ship the
  rewrite rather than maintain two paths.

**Done when:** the new shader compiles + links on Pi, a synthetic test
polygon at known lat/lon renders correctly through the new pipeline,
existing terrain unaffected.

### Phase 1 — Water polygons (1-2 days, biggest win)
- Add `tessellation` table to the water sqlite schema. Pre-tessellate at
  build time via `earcut-python`, store the triangle index list as a
  small BLOB alongside vertices.
- `tools/build_water_db.py` updated to tessellate on insert. Existing DBs
  re-built; the schema bump triggers a one-time rebuild prompt.
- `_draw_water` becomes a buffer upload + draw call per polygon (or one
  batched draw for all in-range polygons via a single VBO + index buffer).
- Delete the camera-inside CPU specials (PIP test, 50 NM surround,
  `_project_polygon_inside`). The GPU path handles it implicitly.
- Keep `min_bbox_diag_deg` size filter — still useful for skipping sub-
  pixel polygons before upload.

**Done when:** water cost drops from ~15 ms to ~1 ms; Lake Grapevine
renders correctly from inside; the X-Plane reference image is matched.

### Phase 2 — Obstacle poles (½ day)
- Each obstacle = base lat/lon, top lat/lon (same lat/lon, top elev_ft =
  base + obstacle height), color from lighting code.
- Render as line segments (two vertices per obstacle, GL_LINES draw).
- The tip marker (small circle) is a textured quad with an atlas circle
  glyph — or six-vertex tri-fan if we don't want a texture.

**Done when:** obstacle rendering cost falls below 1 ms.

### Phase 3 — Runway polygon + side stripes (½ day)
- Runway polygon: 4 corners × 16-segment subdivision = ~60 vertices per
  runway. Tessellate at airport-DB load time, cache.
- Side stripes: same pattern, separate draw call with white-color uniform.
- Distance-adaptive subdivision (already in place CPU-side) carries over.

**Done when:** `runways` cost falls below 1 ms.

### Phase 4 — Runway markings + designator text (1-1.5 days)
- Threshold bars, aiming point, TDZ markers: all flat quads in runway-local
  space. Project per-frame via the shared shader.
- Centerline stripes: same.
- **Designator text**: bitmap-font atlas, generated at startup from
  DejaVu Sans Condensed (the existing font). Atlas covers `0-9`, `A-Z`,
  `-`. ~256×256 R8 single-channel texture. Per-character textured quad
  with U/V from atlas, perspective handled by feeding world-space corners
  to the shared vertex shader (the same projection that places the
  threshold bars on the runway surface). Replaces the existing
  `quadToQuad` + `drawText` per-character CPU path entirely.

**Done when:** `runway.markings` cost falls below 1 ms; designator text
visible, crisp, and correctly tracking with the runway as the aircraft
moves.

### Phase 5 — Airport flags + identifier text (½ day)
- Pole = line segment in the shared GL shader.
- Flag rectangle = quad.
- Identifier text = bitmap-font atlas (reusing the Phase 4 atlas — the
  glyph set is the same).

**Done when:** `airports.flag` cost falls below 0.2 ms; identifier text
visible on each flag.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Tessellation produces malformed triangles for tricky OSM polygons (self-intersecting, near-degenerate) | `earcut-python` is well-tested; fall back to skipping a polygon if tessellation fails (logged warning). |
| Per-vertex uniforms vs interleaved vertex attribs trade-off: small VBOs but many uniform changes per draw | Batch by surface elevation: group polygons with same `elev_ft` into one VBO, one draw call per group. |
| Pi V3D's GL ES 3.0 limits — no GL_TEXTURE_BUFFER, no compute shaders, limited uniform count | Stick to ES 3.0 features used today. Vertex format and shader complexity matches what's there. |
| Bitmap font atlas adds asset to the repo | Generate at startup from a system font (DejaVu) rather than ship a baked atlas. Same fidelity, no asset. |
| Mixed CPU + GPU overlays during phased migration: SVS draws overlay A on GPU, then QPainter draws overlay B on CPU — depth/z-order conflicts | Each migration phase removes the CPU path completely. No mixed state in any single commit. Render order in the FBO is fixed (terrain → water → runways → obstacles → flags) so a partly-migrated state still composites correctly: the CPU QPainter overlay still on the un-migrated layers draws over the FBO blit, on top of all the GPU-rendered layers. |
| Onscreen flicker when an overlay's first GL render compiles | Compile + link all programs at `SVSGLRenderer.__init__`, not lazily on first frame. |
| The screen YAML / config schema needs new keys (overlays_gpu flag, atlas font name) | Additive keys with documented defaults. No backward-incompatible config changes. |

## Performance targets

| Metric | Today | Target |
|---|---|---|
| `frame.svs_total` | 28 ms | **7 ms** |
| `water` (or its GL equivalent) | 14.6 ms | 1 ms |
| `runways` | 3.6 ms | 1 ms |
| `obstacles` | 5.7 ms | 1 ms |
| `gl_terrain` | 4.1 ms | 4.1 ms (unchanged) |
| Visible FPS at DFW | ~22 | **>50** |
| Python main thread CPU | 95% | <40% |

If we hit the targets, the quality controller can shed its L2/L3 levels in
normal flight and only escalate during true overload (multi-airport metro
areas with dense obstacles).

## Testing strategy

- **Unit tests** for tessellation (golden output for a known polygon).
- **Visual harness** runs already cover the rendering; add A/B screenshots
  in the harness comparing CPU-path and GPU-path output for the same pose.
- **Pi end-to-end**: keep `svs_perf_log` on during phased rollout, monitor
  `frame.svs_total` after each phase lands.
- **Quality controller** behavior unchanged — it consumes `frame.svs_total`
  and doesn't care which renderer produced it. Tests stay green.

## Rollback plan

None by design. Each phase commit fully replaces the CPU path for its
overlay; we ship the rewrite, not a configurable hybrid. If a phase
introduces a regression, we revert that commit in git — same as any
other revert. No feature flag is plumbed through; "go forward, debug
the new path" is the explicit project stance.

## Open questions

- Does the Pi V3D's GL ES driver support enough vertex attribs / uniform
  slots for our worst-case shader? Quick test in Phase 0.
- Is `earcut-python` fast enough at DB build time for the ~120,000 Texas
  polygons? Probably yes (it's the bottleneck of Mapbox's vector tile
  pipeline at orders of magnitude more polygons), but measure during
  Phase 1 implementation.
- Do we need depth testing for the overlay z-order, or is render order
  (water → runway → obstacles → flags) sufficient? Likely sufficient
  since every overlay sits at a different world-space elevation; depth
  testing might be necessary if a runway crosses water (a runway on a
  bridge). Defer the decision to when we encounter it.
