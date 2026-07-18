# pyEfis / SVS Structural Review

Architectural review of the pyEfis implementation with a focus on the SVS
renderer, produced 2026-06-10 after a full read of `svs.py`, `svs_gl.py`,
the GPU migration plan, the rendering docs, and an app-level survey of the
startup path, screenbuilder, FIX data flow, and repaint mechanics.

## TLDR

The overlays-to-GPU migration is the right call and it's nearly done — but
it's been executed as a *transliteration* of the CPU design onto GL, so the
codebase is currently carrying both eras at once. The five structural moves
that would take this to the next level, in rough order of value:

1. **Declare GL the platform and delete the CPU rendering era** (~1,000
   lines, two parallel implementations of everything)
2. **Unify six projection implementations into one camera matrix** with
   metre-based, camera-relative coordinates — this also fixes a latent
   float32 precision problem and kills the last per-frame CPU clipping work
3. **Decouple rendering from FIX signals**: fixed-rate frame clock + pose
   interpolation — the biggest *perceived* smoothness win available, and it
   fixes the root cause of the pegged main thread
4. **Eliminate the FBO → QImage → QPainter round trip** (a per-frame GPU
   sync + readback that will bite at higher resolutions)
5. **Move geometry assembly to build time** ("scenery tiles") so the
   per-frame Python work approaches zero

Details below, plus a set of cheap "next level" visual wins the new
architecture makes nearly free.

---

## 1. Retire the CPU era — the codebase is paying double rent

Right now [src/pyefis/instruments/ai/svs.py](src/pyefis/instruments/ai/svs.py)
is three programs sharing one class: a legacy CPU rasterizer (four tiers,
shade tables, Gaussian smoothing, QPainterPath bucketing — roughly lines
700–1080), a geometry collector for the GL path, and a config/perf/quality
manager. The cost isn't just size:

- **Every visual decision is implemented twice** and must be kept in sync
  by hand — the comments admit it ("Kept in sync with svs_gl.py" appears on
  SLOPE_EXAG, AMBIENT/DIFFUSE, the color constants, the near-airport
  collapse logic). That's a standing source of drift bugs.
- **The fallback isn't actually equivalent**: the polar tier now renders
  *no water and no obstacles* (svs.py:1066-1077). For a flight display, a
  silently degraded fallback that's missing obstacle depiction is arguably
  worse than an explicit "SVS UNAVAIL" state — a pilot who's been trained
  by the GL picture will assume the absence of a tower means there is no
  tower.
- The `_QualityController` (L0–L3 detail shedding, hysteresis, EMA) was
  built for a 28 FPS CPU world. At 5 ms/frame on the V3D it should never
  leave L0. After Phase 5 lands, it's ~150 lines of machinery guarding
  against a load profile that no longer exists.

**Recommendation:** after Phase 5, delete `cpu_sparse/cpu_dense/cpu_ultra`
outright, and make a deliberate decision about `polar`: either keep it as a
*tested, feature-complete* fallback (it would need water/obstacles back) or
replace the fallback with an explicit annunciated SVS-off state. Also dead
or near-dead: the hand-coded `_AIRPORT_DB` KASE dict,
`_runway_polygon_corners`, `_project_polygon_clipped`, the
`SVSGraphicsItem` placeholder class, `Qt_NoPen`, and the quality
controller. Estimated result: svs.py drops from 2,419 lines to ~1,200.

## 2. One camera, one matrix, one unit system

This is the deepest structural issue. The projection math currently exists
in **six places**: CPU `_project_point`, CPU `_project_polygon_clipped`,
the polar draw loop, the terrain vertex shader (atan-based), the overlay
vertex shader (which contains *two* projections — perspective and legacy
atan2 behind a uniform switch), and the text vertex shader (a third copy of
the perspective path). Each one re-derives heading/pitch/roll trig per
vertex, and the terrain shader still uses the angular model while overlays
use true perspective — they're only *approximately* aligned ("matches the
atan2 path at small angles", svs_gl.py:336-338).

The standard structure that collapses all of this:

- **Per frame, on CPU, compute one 4×4 view-projection matrix** from
  (lat, lon, alt, pitch, roll, heading, FOV): local-tangent ENU frame →
  camera rotation → perspective projection. ~30 lines of numpy, computed
  once.
- **Store all vertex data in ENU metres relative to a local origin** (e.g.
  the heightmap patch origin), not `(lat°, lon°, elev_ft)`. Every shader
  becomes `gl_Position = u_vp_matrix * vec4(a_pos_m, 1.0)` — the terrain,
  overlay, and text shaders share one vertex stage, and terrain/overlays
  align *exactly* by construction.

This also fixes two latent problems:

- **float32 precision.** The VBOs store longitude in float32: at -119.85°,
  float32 resolution is ~0.7 m. Runway side stripes are 0.9 m wide and
  threshold stripes 1.75 m — that's within one quantization step of visible
  vertex snapping/shimmer on short final. Camera-relative metres have
  millimetre precision.
- **The unit zoo.** One vec3 currently mixes degrees-lat, degrees-lon, and
  feet, and the code is peppered with `111139.0`, `364491.0`, `3.28084`,
  `0.3048`, `1852.0` conversions (the lat-metres constant appears in 14
  separate places). ENU metres at the data boundary makes most of those
  vanish.
- **The CPU near-plane clipper becomes deletable.**
  `_filter_behind_camera_triangles` (~115 lines with Python loops over
  straddling triangles, running every frame on runway polys and markings)
  exists to protect the *legacy atan2* shader path. With hardware
  perspective on by default, GL's w-clipping already handles the near
  plane — and properly, without the 50 m foreground gap the CPU clipper
  imposes as a compromise. Verify the near-field visuals with the clipper
  disabled in perspective mode, then delete it along with the
  `u_use_perspective` A/B switch.

One bonus that falls out: with a real perspective camera, adding the
**earth-curvature drop term** (`-d²/2R` on elevation) is a one-line shader
change. Auto-range was just extended to the true horizon at 50 NM — at
that range the curvature drop is ~2,100 ft, so distant ridgelines currently
render meaningfully too high and the horizon doesn't dip. For a synthetic
*vision* system that's a geometric-honesty issue worth fixing once the
camera is unified.

## 3. Decouple rendering cadence from FIX updates — frame clock + pose interpolation

The app-level survey confirmed there is **no frame clock anywhere**: every
FIX `valueChanged` signal calls `update()` (ai/__init__.py:186), so the AI
repaints as fast as LAT/LONG/ALT/PITCH/ROLL/HEAD updates arrive and the
event loop allows. That's the actual root cause of "main thread pegged at
90–95%": the renderer has no FPS cap, so it always consumes whatever CPU is
left, and frame pacing is whatever the gateway's burst pattern produces.

The structural fix is the one real EFIS firmware uses:

- A **single QTimer at the display rate** (30 Hz is plenty for a panel)
  drives the AI repaint. FIX signals just store values — no `update()`
  calls.
- A small **pose state layer** (lat/lon/alt/pitch/roll/heading + their
  rates) sits between FIX and the renderer, and the frame clock samples it
  with **interpolation/extrapolation** (even a simple alpha-beta filter).
  GPS position arrives at maybe 1–10 Hz; right now the terrain *steps*
  forward at the data rate. Dead-reckoning between updates using
  groundspeed/track makes the terrain glide at 30 Hz. This is the single
  biggest perceived-quality improvement available, and it's invisible in
  any profiler.

This also makes the quality controller's job trivial (a fixed budget per
33 ms tick) and gives a principled place for the perf logging. The same
pattern would benefit the tapes and HSI, but the AI is where it matters.

## 4. Kill the FBO → QImage → QPainter round trip

Per frame the GL path does `fbo.toImage()` — a synchronous `glReadPixels`
that stalls the GPU pipeline — then a CPU `drawImage` into a raster
QGraphicsView (svs_gl.py:813, svs_gl.py:710-713). At 800×600 it's ~1 ms;
at a 1280×800 or 1080p panel it's 4–8 ms of pure readback+blit, plus the
sync stall — it will quietly become the frame budget again exactly when
the system moves to flight hardware with a bigger display.

The overlays-to-GPU plan doc rejected onscreen GL as fragile, but there's
a supported middle path: give the AI's QGraphicsView a **QOpenGLWidget
viewport**. The scene then composites on the GPU, and inside
`_SVSGraphicsItem.paint()` use `painter.beginNativePainting()` to render
terrain+overlays directly into the backing framebuffer (or keep the
offscreen FBO and draw it as a **textured quad** with a shared context —
zero readback either way). The pitch ladder and symbology continue to be
QPainter calls, now executed by Qt's GL paint engine. Nothing about the
screen YAML or z-order model changes. If the truly radical version — the
whole PFD as one GL surface — is ever wanted, this is also the on-ramp,
but it's probably not needed; QPainter symbology on a GL viewport is the
right altitude.

## 5. Move geometry assembly to build time — "scenery tiles"

The runtime currently rebuilds world-space geometry from primitive
records: `_emit_runway_marking_quads` re-derives every threshold stripe,
TDZ bar, and chevron from runway endpoints; water expands BLOBs; obstacles
regroup by color — all cached at 1 s TTL, which means **once per second
the paint path pays a multi-ms Python hitch** (the cache-miss frame),
visible as periodic jitter even when the mean frame time is 5 ms.

Since this geometry is static in world space, it can all be emitted
**once, at database build time**: store ready-to-upload float32 vertex
arrays (in tile-local ENU metres, per point 2) in the sqlite layers, keyed
by spatial tile. The runtime collapses to: *which tiles are in range →
upload any not resident → draw resident buffers with this frame's matrix*.
The collect/cache/TTL machinery — five parallel cache implementations in
`SVSRenderer.__init__` — all goes away. As a side effect, the four
separate data stores (SRTM tree, airports.sqlite, obstacles.sqlite,
water.sqlite, CIFP fallback) become layers of one versioned scenery-pack
format with one build pipeline under `tools/` and one cycle-currency story
(NASR/DOF are 56-day products — a pack manifest with effective dates gives
an "out of date" annunciation for free).

An intermediate step without the format change: move the existing collect
functions onto a **worker thread** that publishes double-buffered vertex
snapshots; sqlite and numpy both release the GIL, so this genuinely
overlaps with painting.

## Smaller structural observations

- **Module split.** Even after deletions, one file holding tile IO,
  caches, geometry emission, and rendering is hard to test. The collectors
  are already nearly pure functions — split into `svs/geometry.py` (no Qt
  imports, trivially unit-testable), `svs/gl.py`, `svs/data/`. The test
  suite would get meaningfully stronger for free.
- **`_near_airport` queries the airport DB every frame** in the GL path
  (svs_gl.py:817-830), bypassing the 1 s airports cache that exists ten
  lines away in the parent.
- **App-level duplication** (outside SVS, but cheap): all ~43 instruments
  hand-roll the same `fix.db.get_item / valueChanged / oldChanged /
  badChanged / failChanged` boilerplate. A `FixItemMixin` base would
  shrink every instrument and make the fail-flag pattern (documented as a
  convention in CLAUDE.md) impossible to get wrong.

## Next-level features the cleaned-up architecture makes cheap

Once there's one perspective camera and a pure-GL composite path, each of
these is small:

- **Distance fog/haze** — a few lines in the fragment shader
  (`mix(color, horizon_color, fog)`); adds enormous depth perception,
  hides far-field LOD, and is how Garmin/Avidyne SVS reads as "polished."
- **MSAA on the FBO** (V3D does 4×) — one constructor argument;
  de-jaggies every terrain silhouette and runway edge.
- **ADS-B traffic in the SVS scene.** fix-gateway already decodes GDL90
  from the Stratux path; traffic targets as billboarded sprites in the 3D
  view is a genuine capability jump, and the entire plumbing (FIX keys →
  world position → project → textured quad) already exists after Phase 4b.
- **Highway-in-the-sky** boxes along a VVfr/FMS flight plan — same overlay
  shader, magenta quads, classic SVS feature.
- **30 m terrain from Copernicus GLO-30** — see the dedicated section
  below; also fixes the existing northern-Canada coverage hole.
- **Chart/satellite draping** — see the dedicated section below.

## 30 m terrain — and the Canada problem SRTM already has

SRTM is not global: the shuttle's orbit limited the radar swath to
**60°N–56°S**, and that applies to both SRTM3 (in use today) and SRTM1. So
southern Canada (Vancouver, Calgary, Toronto — everything below 60°N) is
covered, but Whitehorse (60.7°N), Yellowknife, Iqaluit, and all of
Yukon/NWT/Nunavut are not. The current `.hgt` pipeline has this hole right
now — the SVS renders missing tiles as water/flat. With Canadian core
developers, the terrain source needs to change regardless of resolution.

The clearly best replacement:

- **Copernicus GLO-30** (ESA): 30 m, truly global pole-to-pole, free,
  public-distribution license, derived from TanDEM-X (newer and generally
  cleaner than SRTM). Distributed as 1°×1° GeoTIFF tiles on AWS Open Data
  and OpenTopography — no login friction.
- Alternatives for completeness: ALOS AW3D30 (JAXA, global, free with
  registration) and ASTER GDEM v3 (83°N, noisier). Canada also publishes
  CDEM/HRDEM under the Open Government Licence — excellent quality but
  Canada-only, so it's a regional enhancement, not the base layer.

The migration is gentler than it sounds: a build-time converter that
resamples GLO-30 GeoTIFFs into the existing HGT tile format (1-arc-sec HGT
is the same layout at 3601×3601 instead of 1201×1201) leaves `TileCache`,
the heightmap patch builder, and the shaders essentially untouched — one
constant changes. The real work is GPU memory: a 2×2° patch at 1 arc-sec
in R32F is ~207 MB. Practical options are a 16-bit quantized texture
(Mesa's V3D driver exposes `EXT_texture_norm16`), R16F half-float (~4–8 m
quantization at mountain elevations — marginal), or keeping R32F with a
smaller/tiled patch scheme. Worth a quick experiment on the Pi 5 before
committing. The SRTM3 terrain downloader in progress in the
`faa-cifp-data` repo is where a GLO-30 fetcher would naturally live.

## Chart/satellite draping

**The concept.** Today the fragment shader colors terrain by clearance
bucket. Draping means the terrain mesh keeps providing the 3D *shape*,
but the surface *color* comes from sampling a second texture — a
georeferenced raster of a VFR chart or satellite imagery — at each
fragment's geographic position. This is how ForeFlight's 3D preview,
Garmin's topo-blended SVS, and X-Plane ortho scenery work. The
architecture is unusually well set up for it: the terrain vertex shader
already computes a patch-relative UV from lat/lon to sample the heightmap
(svs_gl.py:142-147). Draping is *the same UV* pointed at a second sampler.

**Runtime changes are small:**

1. Pass the existing heightmap UV to the fragment shader as a varying.
2. Add a `u_chart` sampler: `vec3 base = texture(u_chart, v_uv).rgb;`
   instead of the clearance-bucket constants, still modulated by the
   Lambertian intensity so hills stay readable.
3. Upload a chart patch texture alongside the heightmap patch, rebuilt on
   the same half-degree boundary crossings — that machinery already
   exists.

**The real work is the build-time tool**, and it's mostly GDAL plumbing:

- **FAA sectionals** are published as georeferenced GeoTIFFs, public
  domain. One wrinkle: they're in Lambert conformal conic projection
  (pyAvMap's `avchart_proj.py` deals with this same math today), so the
  tool is essentially `gdalwarp` to equirectangular + slice into 1°×1°
  tiles matching the heightmap grid. At 2048 px/degree that's ~50 m/pixel
  — comparable to what a sectional resolves at SVS viewing distances.
- **Memory**: a 2×2° RGB patch at 4096² is ~50 MB raw, but ES 3.0
  *mandates* ETC2 texture compression — pre-compress at build time and
  it's ~12 MB on the GPU, uploaded once per half-degree of travel.

**The Canada angle matters here too**, in the opposite direction from
terrain: Canadian VNC charts are **NavCanada-licensed and not freely
redistributable**, unlike FAA charts. Two consequences. First, chart tiles
must be a user-supplied data path (like the SRTM tiles) rather than
something the project ships — Canadian users source their own VNCs, the
build tool ingests whatever GeoTIFFs it's given. Second, this makes
**satellite the better default global layer**: Sentinel-2 cloudless
mosaics (e.g. the EOX s2maps product) are global including the high
Arctic, 10 m resolution, and free with attribution. A satellite base with
charts as an optional regional layer serves the Canadian developers as
first-class citizens.

**The safety-concept decision** is the part to think hardest about:
clearance coloring isn't decoration, it's the terrain-awareness function.
Draping shouldn't silently replace it. The right shape is what Garmin
does — chart/satellite as the base color, with the **CONFLICT/WARNING
tint blended on top** when clearance is low
(`mix(chartColor, warningColor, 0.5)` for cells above or near aircraft
altitude), so a draped display still goes magenta where terrain will hurt
you. Water polygons can be skipped in draped mode since the imagery shows
water natively. Mode selection (clearance / chart / satellite / hybrid)
is a natural screen-YAML key plus an HMI action, same pattern as existing
config.

Two smaller caveats: charts are bright (mostly white paper) so a
night-dimming multiplier is worth building in from the start, and chart
text drapes onto terrain at arbitrary perspective angles — readable in
practice at typical pitch angles, but it's why "satellite for the 3D
view, chart on the moving map" is the combination most products converge
on.

## Suggested starting points

The camera-matrix unification (point 2) and the frame-clock/interpolation
work (point 3) are the two to start with, and they're independent of
finishing Phase 5. Either can be turned into a phased plan doc in the
style of `docs/svs_overlays_to_gpu_plan.md`.
