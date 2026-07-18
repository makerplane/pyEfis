# SVS VASI/PAPI approach guidance — adoption plan

Plan for porting the legacy VirtualVfr VASI/PAPI visual glidepath guidance into
the GL Synthetic Vision System (SVS). See also
[svs_rendering.md](svs_rendering.md), [svs_planning.md](svs_planning.md), and
[svs_overlays_to_gpu_plan.md](svs_overlays_to_gpu_plan.md).

## What exists today

The PAPI rendering lives in the **legacy VirtualVfr renderer**
([`VirtualVfr.py`](../src/pyefis/instruments/ai/VirtualVfr.py), `render_runway`,
~lines 378-430). It is drawn with **QGraphicsScene items on the CPU**
(`scene.addEllipse`) — entirely separate from the GL SVS pipeline.

The logic:

```text
height_touchdown = aircraft_alt_msl - runway_elevation
approach_angle   = atan(height_touchdown / touchdown_distance)   # degrees
# bucket against a nominal 3-degree glidepath:
< 2.5  -> 4 red   (low)
< 2.8  -> 3 red / 1 white
< 3.2  -> 2 red / 2 white   (on path)
< 3.5  -> 1 red / 3 white
else   -> 0 red / 4 white   (high)
```

It then draws **4 red/white ellipse "lights"** beside the runway threshold, and
separately computes a glideslope deviation `gsi = approach_angle - 3` (clamped to
+/-1), writing it to the FIX `GSI` gauge item (gated by a `self.gsi` flag).

Two properties matter for the port:

- It is **synthetic** — drawn for *every* runway on an *assumed 3-degree* path.
  It is **not** tied to real installed VGSI equipment.
- The geometry is **screen-space**, derived from already-projected runway
  corners, so none of it transfers directly to the GL path.

## The gap in SVS

The GL SVS ([`svs.py`](../src/pyefis/instruments/ai/svs.py) /
[`svs_gl.py`](../src/pyefis/instruments/ai/svs_gl.py)) already draws runway
polygons, FAA surface markings, designators, obstacles, and airport flags — but
**no VASI/PAPI**. Its model is clean to extend:

- Runways arrive as dicts (`thr1/thr2_lat/lon/elev_ft`, `width_ft`, displaced
  thresholds, ...) from
  [`airport_db.py`](../src/pyefis/instruments/ai/airport_db.py).
- Overlays are emitted as **world-space `(lat, lon, elev_ft)` vertex arrays** and
  projected in the vertex shader.
- Billboards (obstacles, flags) are **world-anchored, fixed-pixel quads** — the
  exact pattern PAPI lights need.

## Data finding (decides fidelity)

The airport DB **does not currently carry real VGSI data**. The NASR builder
([`tools/build_airport_db.py`](../tools/build_airport_db.py)) reads
`APT_RWY_END.csv` but extracts only `APCH_LGT_SYSTEM_CODE` (approach *lighting* —
MALSR/ALSF, a different system). NASR's `APT_RWY_END` also publishes the **VGSI
code** (PAPI/VASI, box count, side) and the **visual glide path angle** — we just
do not pull them today. A *real* (only-where-installed, correct-angle)
implementation therefore needs a data-pipeline change.

## Plan — two tiers

### Tier 1 — synthetic PAPI in GL (parity with VirtualVfr, no data dependency)

1. **`_collect_papi(ac_lat, ac_lon, ac_alt_ft, range_nm, heading_deg)`** in
   `svs.py`:
   - Pick the **approach end** (threshold nearer the aircraft) and **gate on
     alignment** — aircraft bearing-to-runway within ~+/-15 degrees of the runway
     heading — so we never paint nonsensical guidance for the departure end.
   - `approach_angle = atan((ac_alt_ft - thr_elev_ft) / horiz_dist_ft)` (the same
     formula); site the box at the **aiming point** (~1000 ft in, beside the
     runway via the existing `perp_lat/perp_lon` vector).
   - Emit 4 **billboarded quads** (fixed pixel size, like obstacles), split into
     two colour groups `{red: verts, white: verts}` by the bucket count.
2. **Draw** in `_render_overlays` (`svs_gl.py`): two `_draw_overlay_primitive`
   calls (red, white) under a `papi` perf segment. It is a handful of quads, so
   re-collect per frame (the red/white split is angle-dependent and cannot use
   the static cached VBO; the cost is trivial).
3. **Config**: `papi: true` under the `svs:` block (default off). Optionally also
   republish the numeric `GSI` FIX deviation by lifting VirtualVfr's `gsi` block,
   so external glideslope gauges keep working.
4. **Tests**: angle -> bucket math, alignment/distance gate, colour split,
   behind-camera cull.

*Effort: ~half a day, no pack rebuild. Looks and behaves like the old PAPI, but
on the GPU and correctly perspective-projected.*

### Tier 2 — real VGSI (data-driven realism), fast-follow

1. Extend [`tools/build_airport_db.py`](../tools/build_airport_db.py) to pull the
   NASR **VGSI code + glide path angle + side** from `APT_RWY_END.csv`; add
   `thr{1,2}_vgsi`, `thr{1,2}_gpa`, `thr{1,2}_vgsi_side` to the `Runway`
   schema/dataclass in
   [`airport_db.py`](../src/pyefis/instruments/ai/airport_db.py).
2. Rebuild + re-upload the **airports pack** (new AIRAC edition via the
   makerplane-data pipeline) and OTA-deploy.
3. SVS then draws VGSI **only where installed**, on the **published angle** (not
   an assumed 3 degrees), the **correct side**, and the **correct type** — PAPI as
   the 4-box row; **VASI** as its 2-bar geometry ("red over white, you're
   alright").

*Effort: ~1 day + one data rebuild/redeploy cycle. The geometry/render code from
Tier 1 is reused, just fed real parameters.*

## Notes / decisions

- **Do not import from VirtualVfr.** It is the legacy screen-space path;
  reimplement the ~15 lines of bucket math cleanly in `svs.py` against world
  coordinates.
- A companion **extended runway centerline** (VirtualVfr also draws one) would
  pair naturally with the PAPI as approach guidance, if wanted.
- Sequencing: this is an SVS fast-follow, after the stabilize-before-upstream-PR
  gate, alongside rivers-as-lines (tracked in #39) and taxiways.

## Acceptance

- Tier 1: flying a 3-degree approach to a runway in X-Plane shows 2 red / 2 white;
  shallow shows more red, steep shows more white; guidance disappears when not
  aligned with / approaching a runway end. Per-frame `papi` cost negligible in
  the SVS profiler.
- Tier 2: VGSI appears only at runway ends that actually have it, on the correct
  side, using the published glide path angle, with VASI rendered as bars and PAPI
  as a 4-box row.
