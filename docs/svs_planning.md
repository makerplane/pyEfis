# SVS Planning: Perspective Alignment, Hardware, and Issue #28 Scope

This document captures three intertwined questions that came up while
considering how SVS relates to the existing Virtual VFR feature, and what
the next concrete step on SVS should be.

## Background

pyEfis already has a runway/airport rendering feature called **Virtual VFR**
(see [`src/pyefis/instruments/ai/VirtualVfr.py`](../src/pyefis/instruments/ai/VirtualVfr.py),
Garrett Herschleb 2018). It draws runways, airport markers, navaids, and
PAPI lights onto the AI viewport using a full 3D spherical-Earth projection
via [`pyavtools.Spatial`](../../pylib/pyavtools/Spatial.py).

The new SVS feature (this branch) renders terrain onto the AI viewport using
a flat-Earth angular approximation that matches the FPM coordinate frame.

The two systems' projections do not agree. This document covers what to do
about that, the hardware budget question that influences the answer, and the
next scoped data-source work (issue #28).

---

## 1. The "fidelity" question: what's actually expensive?

It's tempting to look at Virtual VFR's polished runway and PAPI rendering and
conclude that VVfr uses a more processor-intensive path with higher visual
fidelity. The reverse is closer to the truth.

VVfr's projection math is more **correct** (full 3D, accounts for Earth
curvature and horizon dip), but VVfr does not rasterize terrain. It draws on
the order of:

- A handful of runway quads (4 vertices each)
- A few VOR icons (a small PNG drawn at a screen position)
- PAPI light bars
- Airport identifier text

That total geometry cost is negligible. What makes VVfr **look** polished is
**curated decoration** — `vortac.png`, PAPI light bars, runway centrelines,
threshold labels, airport identifier callouts. None of those are
computationally interesting; they're art and font work.

SVS by contrast spends most of its frame budget on the terrain grid (16k+
quads at `cpu_dense`, 36k at `cpu_ultra`). Terrain is the expensive part.
Adding the same decorations to SVS would be cheap incremental cost.

Conclusion: the gap between VVfr's visual polish and SVS's current state is
not a fidelity ceiling — it's a backlog of decoration work. The four open
SVS data-source issues (#27 obstacles, #28 runways, plus future navaids and
PAPI) map almost exactly onto VVfr feature parity.

---

## 2. Two projections, real mismatch

| Aspect | Virtual VFR | SVS |
|---|---|---|
| Earth model | Spherical, 3D Cartesian | Flat-Earth angular |
| Distance | Through 3D Cartesian | `sqrt(d_lat² + d_lon²) · 111139 m/deg` |
| Horizon location | Below pitch=0 by `view_declination = acos(R/(R+alt))` | At pitch=0 |
| Heading source | `COURSE` (FIX key) — likely a bug | `HEAD` |
| Math library | `pyavtools.Spatial` (Polar/Ray/Plane/Screen) | inline NumPy and `math.atan2` |

### Concrete impact at typical altitudes

The horizon dip is the most visible mismatch. With `R = 20.85e6 ft`:

| Altitude | View declination |
|---|---|
| 1,500 ft | 0.68° |
| 6,000 ft | 1.36° |
| 14,000 ft | 2.07° |
| 30,000 ft | 3.04° |

SVS terrain horizon sits **higher** than VVfr's projection of a runway by
this amount at the same world position. Visible at all SVS altitudes;
becomes obvious above 10,000 ft.

Earth curvature divergence at long range is small (≈ 0.05° at 30 NM) but
grows non-linearly past 50 NM.

### Heading reference inconsistency

[`VirtualVfr.py:72`](../src/pyefis/instruments/ai/VirtualVfr.py#L72) reads:

```python
self.head_item = fix.db.get_item("COURSE")
```

This pulls the **selected/desired course** from the FIX database, not actual
aircraft heading. The variable is named `head_item` and later assigned to
`self.true_heading`, which suggests the original intent was true heading
(`HEAD`). With autopilot tracking course this matches in cruise but diverges
in turns and during course intercept.

This looks like a bug independent of perspective. Worth filing as its own
issue and confirming with the maintainer or the original author before
changing — there may be users who have visually validated the existing
behaviour.

---

## 3. Alignment options

Four approaches, in increasing scope:

1. **Add view-declination correction to SVS** — modify
   [`svs.py:471`](../src/pyefis/instruments/ai/svs.py#L471) to subtract
   `view_declination_deg` from `y_ang`. Roughly 5 lines. Fixes the most
   visible mismatch. Doesn't address curvature at extreme range.

2. **Move SVS to `pyavtools.Spatial`** — replace `_project_point` with the
   Polar/Ray/Screen pipeline VVfr uses. Geometrically exact, but adds
   per-grid-point CPU cost. With 36k quads at `cpu_ultra` this is
   significant; would need vectorisation rework.

3. **Move VVfr to SVS's flat-Earth math** — simpler and faster, matches FPM.
   But loses VVfr's correctness at long range and existing users have
   visually validated the current behaviour. Unlikely to be welcome upstream.

4. **Replicate Virtual VFR features inside SVS, leave VVfr standalone** —
   make SVS feature-complete with its own data sources (NASR airports,
   navaids, obstacles), all projected through SVS's own math. Users pick:
   `svs.enabled: true` for terrain + features, or VVfr for the legacy view.

Option **4** is the path forward. It's largely the existing SVS roadmap
already (issues #27, #28, etc.). SVS already has runway and airport-marker
rendering machinery in [`svs.py:482-571`](../src/pyefis/instruments/ai/svs.py#L482-L571);
it's just driven from a one-airport hardcoded `_AIRPORT_DB` today.

Option **1** is still worth doing in addition: it costs almost nothing and
makes SVS terrain visually consistent with the natural eyepoint geometry,
independent of feature parity work.

---

## 4. Hardware budget

The "Pi" thread runs through the original SVS design. Performance budget
**as designed** (estimates from the SVS docstrings, not measurements):

| Tier | Quads | Target HW | Frame budget |
|---|---|---|---|
| `cpu_sparse` (48²) | 2,304 | Pi 4 | ~67 ms (15 Hz) |
| `cpu_dense` (128²) | 16,384 | Pi 5 / x86 | ~50 ms (20 Hz) |
| `cpu_ultra` (192²) | 36,864 | not benchmarked | unknown |
| `opengl` (native SRTM3) | ~1.5 M | GPU class | trivial |

**We have no actual Pi measurements yet.** The targets are educated guesses
from the original commit. That uncertainty needs to be closed before
deciding on hardware purchases or whether to invest in further CPU
optimisation.

### Two practical paths, in order

1. **Instrument SVS with frame timing** (1-2 hr work). Add a `--profile`
   flag to `tests/visual_svs_test.py` that prints rolling FPS and per-stage
   times (sample, project, fill, lines). Hard numbers on the dev box; rough
   extrapolation to Pi (Pi 4 ≈ 1/8th modern x86 single-thread, Pi 5 ≈
   1/4 to 1/3).

2. **Buy a Raspberry Pi 5** (~$80). Active-cooled. Run the harness, get
   real numbers. Replicating Pi performance via x86 throttling is
   unreliable — different ISA, memory bandwidth, GPU. Real Pi is the only
   honest benchmark.

If we eventually move beyond Pi, a fanless x86 mini-PC (Intel N100 class,
~$150) has plenty of CPU and runs the OpenGL tier when we get there. NVIDIA
Jetson Orin is overkill until we have a GPU renderer to feed it.

Recommendation: **profile first**, since it costs only time and tells us
where we actually stand. Order a Pi 5 if profiling indicates `cpu_dense` is
borderline at typical SVS framerates. Don't go beyond Pi until the OpenGL
tier ships — that's where larger HW pays off.

---

## 5. Issue #28 scope: FAA NASR runway/airport database

This replaces the hardcoded `_AIRPORT_DB` with a real airport / runway
dataset, the highest-impact next step for SVS visual completeness.

### Source data

FAA National Airspace System Resources (NASR), a free public-domain
subscription updated every 56 days (the AIRAC cycle).

- URL pattern: `https://nfdc.faa.gov/webContent/56DaySubscription/<YYYY-MM-DD>/Subscription_AIPNFD_<YYYY-MM-DD>.zip`
- ZIP contains many CSVs; relevant ones:
  - `APT_BASE.csv` — airport reference: ICAO, name, lat/lon, elevation
  - `APT_RWY.csv` — runway: airport ref, designator, length, width
  - `APT_RWY_END.csv` — runway-end: threshold lat/lon/elevation, true bearing

### On-disk layout (mirrors VVfr's CIFP pattern)

```
~/makerplane/pyefis/NASR/
  airports.sqlite      # built database, indexed by (lat_bin, lon_bin)
  cycle.txt            # the 56-day cycle this build came from
  raw/                 # extracted CSVs (optional, can delete after build)
```

### Components (~250-300 LOC total)

1. **Downloader** — `tools/svs_download_nasr.py` (~40 LOC)
   Resolves the current cycle date, downloads ZIP, extracts to staging dir.
   User-facing CLI tool, run once per cycle.

2. **Importer** — `tools/svs_build_airport_db.py` (~100 LOC)
   Parses the three CSVs, joins airport ↔ runway ↔ runway-end. Builds
   SQLite with `airports` / `runways` / `runway_ends` tables. Spatial
   index: integer `(lat_floor, lon_floor)` columns for 1°×1° bin lookup.
   Records cycle date in a metadata table.

3. **Runtime loader** — new module `pyefis.instruments.ai.airport_db`
   (~80 LOC). Opens SQLite read-only. Exposes
   `airports_in_range(ac_lat, ac_lon, range_nm) -> Iterable[AirportRow]`
   returning dataclass-style records the SVS renderer can consume directly.

4. **SVS integration** — modify [`svs.py`](../src/pyefis/instruments/ai/svs.py)
   (~30 LOC). Replace `_AIRPORT_DB` lookup with `airport_db.airports_in_range(...)`.
   Same projection code; only the data source changes. Config option
   `svs.airport_db_path` defaulting to
   `~/makerplane/pyefis/NASR/airports.sqlite`.

5. **Tests** — `tests/instruments/ai/test_airport_db.py` (~80 LOC).
   Build a small fixture SQLite with 3 airports, exercise range query.
   Verify cycle-date reading, missing-DB graceful degradation.

6. **Docs** — update [`docs/svs_rendering.md`](svs_rendering.md) and
   any installation docs (~30 LOC).

### Open questions before implementation

- **License / international**: NASR is US public domain. Are international
  users on the team? If so, the `airport_db` module should support
  pluggable backends so a Canadian / European source can drop in later.
  Easy now, painful retrofit.

- **Profile-first or build-first?** Profiling work (section 4) is
  independent and tells us if any of this needs to fit in a tighter
  performance budget. Recommended order: profile first (1-2 hr), then #28.

---

## Recommended next steps

1. **Profile SVS** — add `--profile` flag to `tests/visual_svs_test.py`,
   capture frame times on the dev box. (1-2 hr)
2. **Add view-declination correction** to SVS terrain projection.
   (~5 lines, immediate visual improvement, independent of #28)
3. **Implement #28** — NASR runway/airport database, per the scope above.
4. **File a separate issue** for the VVfr `COURSE` vs `HEAD` question;
   ask the maintainer / Garrett before changing.
5. **Decide on Pi 5 purchase** based on profiling results.
