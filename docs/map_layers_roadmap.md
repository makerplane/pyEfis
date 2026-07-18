# Moving-map layers roadmap — roads/rivers LOD + FAA raster charts

Status: PLAN (2026-07-10). Two new-capability workstreams for the top-down
moving map (`src/pyefis/instruments/map/`), building on the shipped provider
seam (`moving_map_spec.md`) and the terrain mosaic work
(`map_wide_range_perf_plan.md`). Companion: makerplane-data `docs/terrain.md`
(the pack pipeline these ride).

## 0. Where the map is today (grounding)

`MovingMap` (`map/__init__.py`) is a plain QWidget/QPainter instrument: a frame
clock (10 Hz, pose-gated, #89), a `MapTransform` that owns all world->screen
math, and a z-ordered **layer registry** (`map/layers/__init__.py`). Layers that
do heavy vertex/tile work follow the **terrain pattern**: a worker renders a
north-up overlay image once per snapped window; `paint()` only rotate-blits.
That pattern exists to avoid the SVS #74 failure mode (per-vertex Python at the
frame clock rate).

Live layers: `range_rings`, `terrain` (relief + water rasterized in),
`roads`, `airports`, `navaids` (+ `fixes`/`airways` options). The provider seam
was explicitly designed (spec section 6) so a new layer is "a provider + maybe a
pack" with no core changes -- including **raster/tile layers as first-class**
(`sectional_raster`, `fisb_weather` are named there).

**Roads already exist** (`map/layers/roads.py`, reads `highways.sqlite` via
`HighwayDB`). This roadmap is *enrichment + LOD*, not greenfield, for
roads/rivers; charts are genuinely new.

---

## Workstream 1 -- Roads + Rivers with real LOD

### 1.1 The two gaps (measured from the code)

1. **Thin data.** `tools/build_highway_db.py` filters OSM to `motorway/trunk`
   (+ `_link` ramps) *only* (`DEFAULT_CLASSES`). The map shows sparse interstates
   and reads as empty. The layer already *queries* `primary` and minor classes
   (`roads.py` `_MAJOR`) -- the data just isn't in the pack.
2. **Binary LOD.** `roads.py` has two thresholds (`_SHOW_RANGE=40`,
   `_DECLUTTER_RANGE=20` NM) and a single 40 m RDP decimation. No zoom-tiered
   detail.

### 1.2 Data changes (makerplane-data + `build_highway_db.py`)

- **Expand classes** to `motorway / trunk / primary / secondary` (+ `_link`s).
  Stop there: `tertiary/residential` is visual clutter for aviation and explodes
  size. These four give the landmark network a pilot actually uses (interstates,
  US highways, major arterials).
- **Class-based LOD lives in the LAYER, not the data** (realized design). The
  class->range-band map is a small fixed table in `roads.py` (`_BAND_BASE`), and
  the layer pushes the band's class set into the DB query (`HighwayDB.
  polylines_in_range(classes=...)` -> SQL `fclass IN (...)`), so no new column or
  schema migration is needed and old motorway/trunk-only DBs keep working. (A
  data-driven `minzoom` column stays an option only if per-region band tuning is
  ever wanted.)
- **Footprint / delivery.** Adding primary+secondary multiplies polyline count;
  ship the highways pack **region-tiered + compressed** like terrain (Geofabrik
  extracts are already per-state, so region grouping is natural), opt-in by
  region. Rides the cloud pipeline (`packtools/cloud`) we just extended.
- **Geometry LOD -- DEFERRED.** Start with one RDP tolerance + class `minzoom`.
  Add multi-resolution geometry (coarser RDP for wide zoom, mip-style per line)
  only if wide-zoom vertex budgets bite. Measure with the existing
  `_MAX_VERTICES` budget first.

### 1.3 Render changes (`roads.py`)

- Replace the two thresholds with a **zoom -> class-set table** tied to the range
  ladder, pushing the class filter into SQL (`WHERE fclass IN (...)`) so the
  worker fetches only what it draws (no fetch-then-discard):

  | range | classes drawn |
  |---|---|
  | <=5 NM | motorway, trunk, primary, secondary |
  | 10-20 NM | motorway, trunk, primary |
  | 40 NM | motorway, trunk |
  | 80 NM | motorway |
  | >=160 NM | hidden |

- Per-class pen styling (interstate vs US-highway vs arterial: width + colour).
- Keep the worker-render-once + `_MAX_VERTICES` budget + off-window bbox reject
  already in `_render`.

### 1.4 Rivers (#92) -- a near-copy

`roads.py`'s header already notes it: rivers share the highways sqlite schema, so
a `rivers` layer is a config variation of the roads layer. Build from OSM
waterways (`gis_osm_waterways`), same `minzoom`/LOD approach (major rivers wide,
all waterways close). This also resolves SVS #39 (rivers-as-lines) on the map
side. Own layer id/colour/z; otherwise the same worker + LOD table.

### 1.5 Effort

Low. Layer edits ~an afternoon; the real work is the data rebuild + republish,
which rides the pipeline. **No hardware dependency -- can start immediately.**

---

## Workstream 2 -- FAA raster charts (sectional, IFR Low, IFR High)

Georeferenced raster charts, public-domain, **28/56-day cyclical** (they
*expire* -- unlike terrain, they fit the existing `cycles.py` AIRAC/DOF date
math and the DATA currency annunciation). Strategic point: build this once as a
**first-class raster-tile layer** and sectional / IFR-low / IFR-high *and* future
FIS-B NEXRAD weather (Stratux) all ride the same machinery (spec section 6:
"raster layers must be first-class").

### 2.1 Projection -- see section 3

The whole projection question lives here (the chart *tile grid*), and it is
smaller than it looks because the display is ownship-local. Section 3 is the
decision.

### 2.2 Build (makerplane-data, new toolchain)

- Warp each source chart into the chosen tile grid (section 3) and cut a standard
  **XYZ / MBTiles pyramid** of 256px PNG tiles (e.g. z6-z11). LOD is *native* to
  the pyramid -- no separate LOD logic.
- Toolchain = GDAL (`gdalwarp` + `gdal2tiles`). The terrain container
  deliberately has **no GDAL**, so charts need a **separate GDAL build image** (or
  a dedicated chart stage). Keep it out of the terrain image.
- Package per **region + chart-type**, opt-in, compressed (PNG already
  compressed). Charts are the heaviest data yet -- do not ship CONUS-all by
  default. New pack content under the reserved `charts` kind (already in
  `packmeta.KINDS`, a BULK_KIND, labeled "Charts"); a zip tile pack like terrain.
- Cyclical: charts expire, so wire the currency window (effective/expires) and
  let the on-device DATA flag annunciate stale charts (the machinery exists).

### 2.3 Runtime (`charts` / `sectional_raster` layer)

- A **tile layer**: LRU tile cache, windowed by view, exactly like the terrain
  layer's worker+cache+blit.
- Per visible tile: invert tile(x,y,z) -> lat/lon (per the tile-set's CRS,
  section 3), forward-project the 4 corners through `MapTransform`, and blit with
  a quad warp (`QTransform.quadToQuad`). Per-tile warp error is negligible at
  these zooms.
- z **below** the vector layers (roads/airports/navaids paint on top of the
  chart); z above/replacing terrain relief (section 2.4).

### 2.4 Interactions / decisions

- **Chart vs terrain relief -- DECIDED: auto-suppress relief** under a live
  chart (Bill, 2026-07-10). A sectional bakes in terrain shading, so the chart is
  the basemap and the relief layer turns off while a chart is active; vector
  overlays (roads/airports/navaids) stay on top.
- **Chart selection -- DECIDED: explicit toggle only** among the three types
  (sectional / IFR-low / IFR-high), like `orientation` (Bill, 2026-07-10). **No**
  altitude/phase auto-switching -- a neat idea, but out of scope at this
  automation level.

### 2.5 Phases

- **CH-1** -- raster-tile-layer foundation + VFR sectional, ONE region, pyramid
  built locally; prove reprojection + blit on the Pi. (De-risks section 3.)
- **CH-2** -- chart pack pipeline in makerplane-data (GDAL build image, cyclical,
  region packs, manifest + expiry annunciation), publish sectional.
- **CH-3** -- IFR Low + IFR High as chart-type modes (same pipeline).
- **CH-4** -- chart/terrain interaction, altitude-auto selection, configurator
  twin.

### 2.6 Effort

High -- CH-1/CH-2 are the bulk (new build toolchain + a reprojecting raster
layer). But the raster-tile layer is reused by FIS-B NEXRAD weather later, so it
is a strategic foundation, not a one-off.

---

## 3. Projection (the decision behind charts, and global-use posture)

### 3.1 The display projection is already global-correct

`MapTransform` is **ownship-centered local azimuthal-equidistant**, recomputed
every frame. The math is its small-area linearization (equirectangular about
ownship: `east = dlon*(m/deg)*cos(lat0)`, `north = dlat*(m/deg)`). There is **no
fixed global projection baked in** -- the map is *local everywhere*, so it has no
"whole-globe" distortion (no Greenland problem); scale is true at the aircraft.

One approximation: a single `cos(lat0)` for the window, so E-W scale drifts ~3-4%
at the 160 NM edge (worse at continental range / high latitude). The lever for
wide / high-latitude accuracy is upgrading `to_screen` to the **true
azimuthal-equidistant (great-circle) forward formula** -- bounded, optional,
relevant only if very wide or polar views must be metric-accurate.

### 3.2 Projection only matters for the chart TILE GRID

Because the display is ownship-local, the raster tile grid is an intermediate the
runtime always **warps out of**. Any distortion in the tile grid (e.g. Mercator's
high-latitude blowup) stays in the tile store and never reaches the screen except
as one-time resample softness. So we pick the tile grid on its own merits --
global coverage, source fidelity, tooling -- not display quality.

### 3.3 Options for the tile grid

| Option | Global coverage | Fidelity | Tooling | Notes |
|---|---|---|---|---|
| **A. Web Mercator (3857)** | undefined >85 deg; wastes high-lat | good | best (every slippy tool) | the projection with the distortions Bill dislikes; weak toward poles |
| **B. Geodetic lat/lon (4326)** | uniform global, no polar blowup | good | standard (`gdal2tiles -p geodetic`, WMTS) | clean global-neutral grid |
| **C. Native source (FAA = LCC)** | regional by design | best (near-identity resample) | custom | max US fidelity, but per-region params, not one global grid |
| **D. Metadata-driven** | any | any | mixed | each tile-set carries a CRS descriptor |

### 3.4 Decision: D, defaulting to 4326 (Bill, 2026-07-10)

Each chart tile-set ships a small **CRS descriptor**; the runtime inverts
tile -> lat/lon per that CRS, then forward-projects to the ownship display. US
charts tile in **4326** (global-neutral, no Mercator poles, standard tooling);
native-LCC or any national grid drops in later with **zero runtime change**. The
per-window warp is the same tiny quad-warp regardless of grid, so 4326 costs
nothing over Mercator while sidestepping its global sins. This is the future-proof
choice for eventual worldwide use, where different countries' charts use different
projections -- a metadata-driven warp swallows all of them.

Net global-use posture: the **display** is already local-correct (optionally
upgrade to true great-circle azimuthal for very wide views); the **chart tiles**
are metadata-driven so no single global projection is ever baked in.

---

## 4. Sequencing

1. **Roads enrichment + LOD** (now -- quick, visible, no new toolchain, rides the
   pipeline). Add **rivers** alongside (near-copy).
2. **CH-1 sectional foundation** -- the reprojecting raster-tile layer is the
   strategic unlock; prove it on one region before the full CONUS chart build.
3. **CH-2 / CH-3** chart pipeline + IFR, then **CH-4** polish.

Each ships behind the standard two-repo pipeline (factory -> schema -> R2 asset ->
configurator twin) and lands on the Pi for flight eval, same as every prior map
phase.

## 5. Decisions

1. **Roads LOD -- class-based `minzoom` first** (Bill, 2026-07-10). Full
   geometry-mip tiers deferred until vertex budgets demand them.
2. **Chart tile grid -- metadata-driven, 4326 default** (Bill, 2026-07-10). Each
   tile-set carries a CRS descriptor; US charts tile in 4326; native/other grids
   drop in later with no runtime change.
3. **Chart vs terrain relief -- auto-suppress relief under a live chart** (Bill,
   2026-07-10).
4. **Chart selection -- explicit toggle among the three types only** (Bill,
   2026-07-10). No altitude auto-switching.

## 6. Non-goals

- Not `tertiary/residential` roads (clutter, size).
- Not on-device chart warping from GeoTIFFs (GDAL at frame rate -- charts are
  pre-tiled in the cloud).
- Not procedure/approach-plate geometry (separate, CIFP-deferred).
- Not a new display projection *requirement* -- the true-great-circle upgrade
  (3.1) is optional, taken only if wide/polar accuracy demands it.
