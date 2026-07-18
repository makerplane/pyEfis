# SVS OpenGL Renderer — Implementation Plan

> **STATUS: COMPLETE — historical plan (Stage 1, terrain mesh on GPU).** All
> eight steps shipped and are deployed on the Pi 5; the terrain renders at
> ~196 FPS / ~5 ms, over 3x the 60 FPS target. The `opengl` tier is now the
> *only* SVS renderer. **Live status for the whole SVS GPU effort lives in
> [svs_structural_plan.md](svs_structural_plan.md)** (this file is kept for
> historical context only).

The biggest single performance gain available to the SVS on Pi 5-class hardware
is moving the terrain rasterisation off the CPU and onto the V3D GPU. This doc
captures the design, scope, and step-by-step path for that work, organised so
we can stop and ship at each stage.

The `opengl` renderer tier has been a stub in [svs.py](../src/pyefis/instruments/ai/svs.py)
`GRID_SIZES` since the original SVS commit. This document fills it in.

## Why this is the next move

Measured Pi 5 polar frame times at 64×96 (after our tuning):

| Pose             | Frame time | FPS |
|------------------|-----------|-----|
| KSBA offshore    | 124 ms    | 8.1 |
| KASE short final | 137 ms    | 7.3 |

Profile breakdown (estimated, based on x86 / Pi 5 ratio):

* ~60% — vectorised fill-loop / shade-key compute (NumPy on CPU)
* ~25% — per-cell `QPainter` polygon construction (Python + Qt CPU rasteriser)
* ~10% — slope shading + tile sampling
* ~5%  — runways/obstacles/markings overlay

Everything except the overlays is doing geometry work that maps directly onto
GPU primitives. The V3D GPU sitting next to the A76 cores is unused on every
frame.

## Target

* **Stage-1 goal**: 60 FPS sustained on Pi 5 at the polar default grid (or
  better — denser grids become viable).
* **Architectural goal**: opt-in via `renderer: opengl` in SVS config, with a
  clean CPU-polar fallback if GL init fails. No regressions for any of the
  existing tiers.

## Architecture

### Integration: render to an FBO, blit into the existing scene-graph item

We keep the existing `SVSGraphicsItem` / `make_svs_item` integration unchanged
(see [svs.py:1289](../src/pyefis/instruments/ai/svs.py) and
[ai/__init__.py:352](../src/pyefis/instruments/ai/__init__.py)). The AI widget
still hosts SVS as a low-Z QGraphicsItem at `z=0.5`; the pitch ladder still
renders on top via the scene's z-order.

What changes is what `SVSRenderer.draw()` does internally when the configured
tier is `opengl`:

```
┌─ SVSGraphicsItem.paint(painter, opt, widget) ──────────────────┐
│                                                                │
│  1. SVSGLRenderer.draw():                                      │
│     a. Bind offscreen FBO sized to viewport                    │
│     b. Upload aircraft state + polar params as uniforms        │
│     c. Draw terrain mesh (single glDrawElements call)          │
│        - Vertex shader: polar→geographic→aircraft→screen       │
│        - Fragment shader: Lambertian shading + clearance bucket │
│     d. glReadPixels FBO → QImage (or texture sharing)          │
│                                                                │
│  2. painter.drawImage(viewport_rect, fbo_image)                │
│                                                                │
│  3. Existing CPU code draws runways/obstacles/markings on top  │
│     using the same _project_point() math we have today         │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

Why FBO + blit instead of changing the QGraphicsView viewport to QOpenGLWidget:

* Zero scene-graph architecture change — `SVSGraphicsItem` stays exactly as
  it is. The pitch ladder z-ordering, the graceful FIX-key fallback, the
  airport-proximity colour rule, the runway markings — all untouched.
* The OpenGL context lives entirely inside the renderer; no leakage into the
  rest of pyEfis. If GL fails to initialise, the renderer falls back to polar
  CPU and the rest of the AI widget never knows.
* Easy to A/B benchmark — the per-frame seam between GPU terrain and CPU
  overlays is a natural measurement point.

The cost is the `glReadPixels` (or texture→QImage) round-trip per frame. On
V3D this is fast for a 800×600 viewport (~1-2 ms); it would only become a
bottleneck at much larger viewports.

### Mesh & data path

* **Polar grid topology, identical to CPU**. The `(n_range, n_az)` fan with
  the radial warp stays the same. Builds once at renderer init (or when
  config changes) as an indexed triangle list and uploaded to a VBO. Re-uses
  the existing `radial_warp`, `n_range`, `n_az`, `fov_deg`, `r_min_nm` config
  keys.

* **Elevation as a heightmap texture, not vertex attribute**. We pack the
  SRTM3 tiles overlapping the current aircraft position into a single 2-D
  texture covering ~`2*range_nm` square around the aircraft. The vertex
  shader samples height by `(lat, lon)`. Two big wins:

  * No per-frame VBO upload. The mesh is fixed; only the texture changes,
    and only when the aircraft has moved enough that a new tile band needs
    paging.
  * Trivial to add denser meshes later — the texture covers the same world
    area regardless of mesh density.

* **Tile paging on a worker thread**. When the aircraft moves across an
  integer-degree boundary, fetch new tiles from `TileCache` and update the
  texture. Cheap; happens out of the render hot path.

### Shaders (Stage 1)

Vertex shader inputs:

* `vec2 polar` — `(t, az)` where `t ∈ [0, 1]` parameterises the radial axis
  and `az ∈ [-fov/2, fov/2]` is degrees from the nose
* uniforms: aircraft `lat, lon, alt_ft`, `heading, pitch, roll`, `range_nm`,
  `radial_warp`, screen size, terrain texture sampler

Computation per vertex:

1. `r_nm = r_min + (range_nm - r_min) * pow(t, radial_warp)`
2. `bearing = heading + az`
3. world (lat, lon) of vertex = aircraft (lat, lon) + radial offset
4. elevation = `texture(heightmap, world_uv).r`
5. world position in aircraft local frame (E, N, Up)
6. apply heading/pitch/roll rotation → camera frame
7. project to screen via pixels-per-degree

Pass to fragment shader: world normal, clearance value, water flag.

Fragment shader:

* Lambertian shading against fixed sun direction (same math as our CPU code)
* Look up colour by clearance bucket (safe/caution/warning/conflict/water)
* Apply the same 2-colour airport-proximity rule we have on the CPU side
  (uniforms drive the bucket thresholds; the rule is a `mix()`)

We get the same visual contract as today, just a lot faster.

### Falling back

Init order on first `draw()`:

1. Try `QOpenGLContext.create()` with OpenGL ES 3.0 minimum
2. If it fails or `glGetString(GL_VERSION)` doesn't meet `ES 3.0+`:
   * Log a warning, downgrade `self.renderer = "polar"`, never try GL again
3. Compile + link shaders. Any failure: same fallback.
4. Build VBO and FBO. Same fallback on failure.

The whole `opengl` tier is one big `try` around init. We never hard-fail SVS
because GL was unhappy.

## Scope by stage

### Stage 1 — terrain rasterisation on GPU (this plan)

In scope:

* `opengl` tier rendering full terrain (mesh + Lambertian shading + clearance
  colouring + water + airport-proximity rule)
* CPU overlays (runways, threshold markings, obstacles, airport flags) remain
  as today — `_draw_runways`, `_draw_obstacles`, `_draw_runway_markings`
  unchanged. They draw on top of the GPU terrain image via `QPainter`.
* CPU fallback path preserved

Out of scope (deliberate):

* GPU rendering of vector overlays (runways/obstacles/markings)
* Mipmapping or tessellation
* Heightmap streaming optimisation beyond "load tiles when aircraft crosses
  degree boundary"

### Stage 2 (later, not in this plan)

* Vector overlays on GPU — runways as textured quads with marking textures
  generated once and reused; obstacle poles as instanced quads
* True dynamic LOD via tessellation shader instead of fixed polar grid
* Triple-buffered tile streaming when range_nm is large

## File layout

New module:

```
src/pyefis/instruments/ai/svs_gl.py    — SVSGLRenderer (the GPU path)
    └── shaders/
        ├── terrain.vert
        └── terrain.frag
```

Edits to existing files:

* [svs.py](../src/pyefis/instruments/ai/svs.py)
  * `SVSRenderer.__init__`: when `renderer == "opengl"`, instantiate
    `SVSGLRenderer` lazily on first draw; on init failure, log + downgrade
    to `"polar"`.
  * `SVSRenderer.draw()`: dispatch terrain rasterisation to the GL renderer
    when present, then call the existing overlay paths on the same painter.
  * Update `GRID_SIZES`: remove the "opengl falls back to cpu_sparse" comment.
* [docs/svs_rendering.md](svs_rendering.md): add an `opengl` tier row to the
  tier table once measured.

New tests:

* `tests/instruments/ai/test_svs_gl.py`
  * Skip when no GL context available (CI may not have one)
  * Shader compile test
  * Pixel-diff test: render the same pose with `polar` and `opengl`,
    assert mean Δcolour < threshold (won't be bit-identical because of GL
    interpolation differences, but should be visually equivalent)
  * Fallback test: monkey-patch `QOpenGLContext.create()` to fail, assert
    `SVSRenderer` reverts to `"polar"`

## Implementation steps (executable order)

Numbered so we can stop and verify after each step.

### Step 1 — scaffolding + fallback machinery
* Create `svs_gl.py` with an `SVSGLRenderer` class whose `draw()` raises
  `NotImplementedError`
* Add lazy instantiation + try/except fallback in `SVSRenderer.__init__`
* Verify: existing tests pass; `renderer: opengl` config logs warning, falls
  back to `polar`, no behavioural change

### Step 2 — minimal triangle on screen
* Create the `QOpenGLContext`, FBO, basic shaders that draw a single coloured
  quad covering the viewport
* `SVSGLRenderer.draw()` renders to FBO, reads back to `QImage`, painter
  draws the image
* Verify: visual harness shows the test colour where SVS terrain used to be

### Step 3 — polar mesh
* Build the polar (range, az) mesh as an indexed triangle strip (or list)
  in vertex shader-friendly coordinates
* Vertex shader: convert `(t, az)` to screen pixels using uniforms for
  aircraft state, ignoring elevation (z=0 plane)
* Fragment shader: flat colour per cell band (debug visualisation)
* Verify: harness shows the polar grid as flat-shaded coloured fan

### Step 4 — heightmap texture
* Add `_load_heightmap(ac_lat, ac_lon)` that builds a single-channel float
  texture from the SRTM tiles overlapping the visible area
* Vertex shader samples elevation from the texture
* No shading yet — output elevation as greyscale
* Verify: harness shows recognisable terrain silhouette at known poses

### Step 5 — Lambertian shading + clearance colour
* Compute world normal in the vertex shader (finite difference on neighbour
  heightmap samples) and pass to fragment
* Fragment shader applies the same lighting + clearance-bucket logic our
  CPU code uses
* Verify: pixel-diff against `polar` CPU at known poses; mean delta < some
  small threshold

### Step 6 — airport proximity 2-colour mode
* Pass `near_airport` as a uniform; fragment shader switches bucket rules
* Verify: at KSBA on final, terrain reads green/magenta, no red — matching
  the CPU path

### Step 7 — tile paging
* When aircraft crosses an integer-degree lat or lon boundary, rebuild the
  heightmap texture from the new tile set
* Verify: continuous flight across a tile boundary shows no visual artefact

### Step 8 — perf measurement and tier doc update
* Bench on Pi 5 at KSBA and KASE poses
* Update `docs/svs_rendering.md` tier table with measured frame times
* Update `docs/svs_hardware_options.md` with new "is Pi 5 enough?" verdict

## Verification

* All existing 31 SVS tests pass at every step
* All 133 screenbuilder tests pass at every step
* Pi 5 visual harness shows correct rendering at KSBA, KASE, Aspen, an
  offshore-Pacific pose (water rendering check), and a southern-hemisphere
  pose if data available
* Frame-time measurement: ideally >30 FPS at the polar default grid; the
  goal is 60 FPS

## Risks / open questions

* **`glReadPixels` cost on V3D**: untested. If it's slower than expected
  (>5 ms at 800×600), we may need to use `QOpenGLWidget` as the viewport
  directly instead of FBO+blit, accepting the larger architectural change.
* **PyOpenGL vs QOpenGLFunctions**: PyOpenGL is more familiar but PyQt6 has
  Qt-native bindings via `QOpenGLFunctions`. Native Qt bindings have better
  context lifetime guarantees and are recommended; we should use them.
* **Heightmap precision**: 16-bit float texture is enough for SRTM3 (1-foot
  precision over typical altitude ranges), but bilinear filtering of
  elevation across coastlines may produce different artefacts than the
  CPU code's explicit water-mask logic. May need a separate water-mask
  texture.
* **Shader portability**: Pi 5 is OpenGL ES 3.1; an N100 Linux box is
  desktop OpenGL 4.6. We write shaders against ES 3.0 minimum and let both
  paths consume them.
* **Test coverage in CI**: GitHub Actions runners may not have GL. Tests
  for the GL path need a clean skip when no context can be created.

## Decision points before implementation starts

1. **Native Qt OpenGL bindings vs PyOpenGL?** Recommendation: native
   `QOpenGLFunctions` + `QOpenGLShaderProgram` — fewer dependencies, better
   lifetime semantics.
2. **Pi 5 testing rhythm**: do we deploy to the Pi after each step (slow,
   accurate) or only after major steps (fast, risk of late surprises)?
   Recommendation: Step 2, 4, 5, 8.
3. **What about the visual harness?** It currently bench-renders to an
   offscreen image at known poses. We need a GL-capable harness path —
   either run it under `QT_QPA_PLATFORM=eglfs` on the Pi, or `xcb`/`wayland`
   on the dev box.
