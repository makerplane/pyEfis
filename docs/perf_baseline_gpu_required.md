# P0 baseline — gpu-required branch

Phase 0 artifacts for [svs_structural_plan.md](svs_structural_plan.md).
Captured 2026-06-10 at branch point `b160c1c` (+ the two P0 bug fixes
noted below, which were required to obtain a valid GL baseline at all).

## Test suite inventory

`pytest tests/instruments/ai/ --no-cov` (with the standing
`test_void_values_replaced_with_zero` deselect):

- **124 passed, 4 failed, 1 skipped** (Windows dev machine, Python 3.13)
- The 4 failures are all in `test_virtualvfr.py` (resize/metadata-expiry
  tests) and are a **pre-existing Windows-only path-separator artifact**:
  the asserts compare `tmp_path / "next.db"` (backslashes) against a
  stored path with a forward slash. Not code breakage; expected to pass
  on POSIX. Candidates for an `os.path.normpath` cleanup in passing.
- 1 skip: `test_svs.py:965` requires a GL context the pytest environment
  doesn't provide.

## Golden screenshots — tests/golden/

800×600, `SVS_RENDERER=opengl`, captured via the harness's new
`SVS_SCREENSHOT` support, **zero GL-fallback warnings** in each run:

| File                  | Pose             | Notes                                  |
|-----------------------|------------------|----------------------------------------|
| ksba_offshore.png     | KSBA offshore    | water, coast, 2-colour airport mode    |
| kase_short_final.png  | KASE short final | mountain terrain, runway markings      |
| kase_10k.png          | KASE 10k MSL     | terrain shading at altitude            |
| dfw_metro.png         | DFW metro        | water polys, obstacles, flags, runways |
| dfw_metro_pi5.png     | DFW metro (Pi 5) | same pose rendered on-target via eglfs |

Known pre-existing visual quirks captured in the goldens (do not treat
as regressions introduced by later phases — but they are real artifacts
later phases may legitimately fix):

- Small blue speckle artifacts inside the magenta ridge at the KASE
  poses (sliver triangles at steep terrain).
- AI symbology (waterline bars, pitch ladder, FPM, flag poles) is part
  of the capture by design — goldens cover the composited widget.

## Perf baseline — DFW pose, sustained render

`SVS_LAT=32.90 SVS_LON=-97.04 SVS_ALT=2500 SVS_HEAD=175 SVS_RANGE=30`,
`SVS_PERF_LOG=1 SVS_ANIMATE=5` (5 deg/s heading sweep, repaint forced at
~30 Hz), 24 s run, last 2 s report quoted. 800×600 viewport on Windows;
the Pi renders at its native DSI panel size.

| Segment (ms/call)          | Windows x86 | Pi 5 (eglfs) |
|----------------------------|-------------|--------------|
| frame.svs_total            | 8.45        | 11.25        |
| gl_terrain                 | 7.05        | 9.24         |
| obstacles (collect+draw)   | 0.87        | 2.43         |
| runways total              | 1.07        | 1.52         |
| water (cached frames)      | 1.21        | 0.81         |
| water.query (cache miss)   | **20.6**    | **15.1**     |
| airports.flag              | 0.03 × 34/frame | 0.04 × 34/frame |
| frame.ai_paintEvent_total  | 9.61        | 13.57        |
| quality controller         | L0, fps_ema 82 | L0, fps_ema 90 |

Observations the later phases should be measured against:

- **The 1 Hz cache-miss hitch is real and visible in the data**:
  `water.query` costs 15–21 ms on the two frames per report window where
  the 1 s TTL caches expire (predicted by plan Phase 8).
- **`airports.flag` runs ~34 sub-calls per frame** on the CPU — the last
  QPainter overlay; Phase 1 removes it.
- Frame cadence in both runs is animation-timer-bound (~30 Hz), not
  render-bound: SVS leaves >20 ms/frame of headroom on the Pi at L0.
- Pi `gl_terrain` (9.2 ms) is higher than the 5.1 ms recorded in
  docs/svs_rendering.md's earlier 800×600 measurement — consistent with
  the larger native panel resolution and range 30 at a metro pose.
  Phase 5's FBO-readback elimination should be measured against this
  number at the same pose.

Post-P1/P2 checkpoint (same DFW pose, Pi 5, 2026-06-10): with all
overlays GPU-side and the CPU era deleted, frame.svs_total fell to
10.11 ms (gl_terrain 9.66) and airports.flag to 0.2 ms in one GL pass.

Raw logs: not committed (transient `/tmp` captures); re-run with the
harness env vars above to regenerate.

## Bugs found and fixed during P0

Both were prerequisites for a valid baseline; committed on this branch:

1. **Desktop GL: `glLineWidth(2.0)` killed the GL renderer.** Core-ish
   desktop contexts (Windows dev machine) raise GL_INVALID_VALUE for
   line widths > 1.0 (and the `GL_ALIASED_LINE_WIDTH_RANGE` query still
   advertises a wide range, so probe-by-trying is required). The
   obstacle pass tripped it on the first frame containing obstacles and
   the one-shot fallback **silently downgraded every Windows
   "opengl" run to polar**. Anyone who captured "GL" screenshots on
   Windows before this fix was looking at the polar tier. Fixed in
   svs_gl.py (probe once, clamp). This is also a concrete argument for
   plan P2's explicit SVS-UNAVAIL failure policy over silent fallback.
2. **eglfs: startup crash `wrapped C/C++ object ... deleted`.**
   `AI.resizeEvent` replaces `self.scene` every resize; the destroyed
   scene deletes the C++ side of the SVS QGraphicsItem it still owns,
   and the next `_attach_svs_item_if_ready` dereferences the dead
   wrapper. Windows survives on GC timing; the Pi's fullscreen startup
   resize sequence crashes. Fixed in ai/__init__.py (detach before
   scene swap + self-healing re-attach that rebuilds the wrapper).

## Config-key audit (for P2/P3 removals)

- `renderer:` — used by the Pi's local (uncommitted)
  `src/pyefis/config/includes/ahrs/virtual_vfr.yaml` (`renderer: opengl`)
  and by tests/harness. **No shipped YAML under src/pyefis/config/
  carries an `svs:` block at all.** P2 must keep accepting the key
  (ignore + deprecation log) for the Pi config's sake.
- `quality_control` — appears in **no** YAML, tests, or harness; only in
  svs.py itself. Free to delete with the controller.
- `gl_overlay_perspective` — appears in **no** YAML; referenced only in
  svs.py/svs_gl.py and the plan. Free to delete in P3.
- The Pi's live SVS config also sets: `tile_path`, `nasr_db_path`,
  `dof_db_path`, `water_db_path`, `range_nm: 50`, `auto_range`,
  `grid_lines`, `svs_perf_log: true`, `airport_proximity_nm`, `n_range: 64`
  — all surviving keys.

## Harness additions (tests/visual_svs_test.py)

New env vars added for this baseline and all later phase verification:
`SVS_WATER_PATH` (default: first `water/water_rtree*.sqlite`),
`SVS_PERF_LOG`, `SVS_ANIMATE` (deg/s heading sweep, forces ~30 Hz
repaints), `SVS_SCREENSHOT` + `SVS_SCREENSHOT_DELAY_MS`
(capture-and-exit, used for goldens).

## Pi 5 access

`ssh pyefis` (see CLAUDE.md). pyEfis runs as the user-level systemd unit
`pyefis.service` and owns the display — stop it before harness runs on
eglfs, restart after:

    systemctl --user stop pyefis.service
    cd ~/pyEfis && QT_QPA_PLATFORM=eglfs SVS_TILE_PATH=$HOME/EarthData/srtm3 \
      <harness env vars> .venv/bin/python tests/visual_svs_test.py
    systemctl --user start pyefis.service

The Pi checkout is the user's test rig (branch `svs-opengl` with local
config modifications) — leave its tree as found.
