# Moving Map — specification

Status: SPEC (2026-07-05). Development has not started; work will
happen on a dedicated branch off `display-changes`. Companion specs:
`svs_rendering.md` (rendering lessons), pyAvMap `docs/MFD-Assessment`
(prior art; see section 2), makerplane-data
`docs/canfix_configurator.md` (provider-model precedent).

## 1. What this is

A top-down **moving map instrument** for pyEfis: a widget placed and
sized like any other through the configurator, showing ownship over
terrain with toggleable information layers — terrain relief, airports
with FAA sectional symbology, navaids/waypoints/airways, and an open
**layer-provider model** so future sources (ADS-B weather/traffic via
Stratux, lightning, airspace, range rings, flight plan) plug in
without touching the core.

It is "much more than an instrument", but architecturally it IS one:
registered in `screenbuilder_factory`, options in the editor schema,
a twin preview in the configurator, FIX-database position/track
driving it. Everything we learned shipping the SVS applies.

## 2. Relationship to pyAvMap (decided direction)

pyAvMap is the dormant PyQt5 raster moving map. The MFD assessment
verdict was "scoped yes — port to PyQt6 + screenbuilder instrument".
This spec **supersedes the port**: we build a new, vector-first
pyEfis-native widget that reuses pyEfis's own data backends (the SVS
collectors' sqlite/HGT stack) rather than pyAvMap's chart-raster
pipeline. Rationale: the data, caching, and perf lessons already live
in this repo; a raster **sectional-chart layer** remains attractive
later and slots in as one more provider (section 6), which is where
pyAvMap's tile logic can be mined if wanted.

## 3. Widget architecture

- **Class**: `pyefis/instruments/map/__init__.py`, `MovingMap(QWidget)`
  (plain QWidget + QPainter; no QGraphicsScene — the map repaints as a
  whole on pan/zoom, and layer pixmap caching does the heavy lifting;
  no GL requirement, so it renders offscreen for CI/screenshots and
  runs on GL-less panels).
- **FIX inputs**: LAT/LONG (position), TRACKM/HEAD (orientation), GS
  (ground speed for the track vector), ALT (terrain-relative coloring,
  later TAWS layer). Standard fail/old/bad handling: stale position
  greys the ownship + annunciates; the map does NOT freeze silently.
- **Projection**: local azimuthal-equidistant about the screen
  center — x = (lon-lon0)·M·cos(lat0), y = (lat-lat0)·M, the same
  small-area flat-earth math the SVS uses (`M_PER_DEG_LAT`, shared
  helper). Error is negligible below ~250 NM range. One
  `MapTransform` object (center, range_nm, rotation, widget size)
  owns ALL world->screen math; every layer receives it. No layer does
  its own projection arithmetic (the `_project_point` lesson).
- **Orientation modes**: `north_up` and `track_up` (option +
  runtime-togglable). Track-up rotates the transform, not the layers.
- **Range**: `range_nm` option (default 10), stepped through a
  configurable ladder (2/5/10/20/40/80/160) by HMI actions.
- **Ownship**: fixed at a configurable screen anchor
  (`ownship_position`, percent up from bottom, default 50; 30 gives
  the classic look-ahead offset). Aircraft symbol reuses the AI's
  `aircraft_symbol`/`symbol_color`/`symbol_scale` style vocabulary,
  drawn top-down.

## 4. Layer-provider model (the core design)

```python
class MapLayer:                    # pyefis/instruments/map/layers/base.py
    id: str                        # "terrain", "airports", ...
    label: str                     # button/menu text
    z: int                         # paint order (terrain lowest)
    default_on: bool
    def configure(self, config): ...        # per-layer options dict
    def collect(self, view):  ...           # ASYNC: gather/derive data for
                                            # the view window (worker thread)
    def paint(self, painter, xform): ...    # SYNC: draw cached results
    def on_toggle(self, on): ...            # free/acquire resources
```

- **Registry**: `LAYER_REGISTRY` dict + entry-point-style registration
  so out-of-tree layers can be added (the engine/airport provider
  precedent). The widget instantiates layers named in its config,
  ordered by `z`.
- **Threading contract (SVS issue #74 lessons, non-negotiable)**:
  `collect()` runs on worker threads serialised by ONE shared
  collect slot; results are immutable snapshots swapped in for
  `paint()`. Per-feature work in collect() must be vectorised numpy /
  sqlite — no Python per-element loops on the GIL during cruise.
  `paint()` only blits pixmaps and draws pre-transformed primitives.
- **Caching**: each layer caches keyed on (tile/window, range bucket,
  data edition). Terrain caches rendered QImages per tile+zoom;
  vector layers cache query results per window and re-project each
  frame (cheap) or cache pixmaps when static in world space.
- **Real-time toggles**: HMI actions (see 7) flip `layer.enabled` and
  repaint; toggling never reloads data that is still cached.

## 5. v1 layers (Bill's list)

### 5.1 Terrain (z=0, default on)
- Source: the GLO-30/SRTM HGT tree already on the Pi
  (`/data/makerplane-data/terrain/tiles`) through the existing
  `TileCache` — same tiles as the SVS, zero new data.
- Render: hypsometric relief — numpy hillshade (NW light) + the
  sectional-style elevation palette, downsampled per zoom via the
  Track-1c mip pyramid (`TileCache.get_mip` — already built and
  cached; the map is its second consumer). Rendered per-tile to
  QImage on the worker, LRU-cached; repaint = blit + rotate.
- Option `terrain_mode`: `relief` (absolute hypsometric) or
  `caution` (TAWS-style relative coloring vs ALT: amber <1000 ft,
  red <100 ft below aircraft — the SVS clearance palette, top-down).

### 5.2 Airports (z=30, default on)
- Source: NASR `airports.sqlite` via the existing airport_db
  (multi-provider merge included — Canada shows up for free).
- **FAA sectional symbology** (Aeronautical Chart Users' Guide):
  - towered = blue, non-towered = magenta (tower data: NASR TWR file
    — add to the airports pack build; until then all magenta like a
    chart without tower info, annunciated in docs);
  - hard-surface runways 1500-8069 ft: circle with runway-orientation
    tick(s) inside, drawn from the real runway geometry we already
    carry; >8069 ft: runway outline symbol (no circle); unpaved:
    plain circle; seaplane/heli: reserved symbols later.
  - services (fuel) tick marks around the circle: data-gated, later.
  - Labels: ident, declutter by zoom (full name off; ident-only
    under 40 NM; nothing above 80 NM except selected).
- Decluttering is per-zoom and deterministic (grid-bucket keep-top-N
  by runway length) so the picture is stable frame to frame.

### 5.3 Navaids / waypoints / airways (z=40/45, default: navaids on,
airways off)
- **New data**: NASR NAV (VOR/NDB/DME), FIX (named fixes), AWY
  (victor/T-route segments) files -> a new `navdata` pack member
  (`navaids.sqlite`: navaids, fixes, airway segments with from/to
  fix geometry). Built in makerplane-data by the proven cyclical
  pipeline (28-day AIRAC, staged-next included). This is the one new
  data workstream v1 needs; it is already on the makerplane-data
  roadmap ("navaids/fixes = quick win").
- Symbols: sectional-standard — VOR compass rose hexagon, VORTAC /
  VOR-DME variants, NDB stippled disc, fixes as open triangles;
  airways as light blue lines with ident boxes at midpoints.
- CIFP remains GPL-deferred; NASR covers all three feature classes
  for US. (Procedure geometry = future layer, not v1.)

## 6. Future layers (design targets for the provider seam)

Named now so the interfaces stay honest: `range_rings` (trivial,
ships v1 as the provider-model proof), `flight_plan` (route from a
future FMS/GPS source), `traffic` (ADS-B via Stratux — FIX keys or a
side TCP feed; symbol set = TIS-B standard), `metar_flags` /
`fisb_weather` (Stratux FIS-B: NEXRAD raster as a tile layer —
raster layers must be first-class), `lightning`, `airspace` (NASR
CLS_ARSP/SUA — high value, data build like 5.3), `obstacles` (DOF,
already on-device), `sectional_raster` (FAA VFR chart tiles; mine
pyAvMap). Each is "a provider + maybe a pack"; none require core
changes if sections 4's contract holds.

## 7. Controls (buttons/encoder — hardware pending)

The map exposes HMI actions only; binding them to physical buttons /
touch / encoder is screen YAML, decided when the controller exists:

- `map:range_up` / `map:range_down` — step the range ladder.
- `map:orient` — toggle north-up / track-up.
- `map:layer:<id>` — toggle a layer (e.g. `map:layer:airports`).
- `map:layers` — cycle a small on-map layer legend/menu (encoder-
  friendly single-button UX, mirrors the existing listbox patterns).
A transient on-map legend chip shows current range + active layers
for 3 s after any action (so button UX works blind of the menu).

## 8. Configurator integration (standard pipeline)

- Factory registration + Props: `range_nm`, `orientation`,
  `ownship_position`, `layers` (per-layer default-on booleans:
  `layer_terrain`, `layer_airports`, `layer_navaids`,
  `layer_airways`, `layer_range_rings`), `terrain_mode`, symbol
  options, `db paths` (default to /data/makerplane-data locations).
- Editor twin: static top-down preview — a canvas rendering a small
  baked terrain patch (the SVS preview-patch pattern; one scene is
  enough) with sample airport/navaid symbols honoring the layer
  checkboxes. Fidelity rule applies: symbols in the twin ARE the
  widget's symbol code paths, ported once.
- `offscreen_renderable: true` (QPainter-only) — reference PNGs via
  `tools/render_instrument.py`, so the twin gets real renders to
  match, unlike the GL-locked SVS.

## 9. Performance budget (Pi 5, alongside the SVS)

- Target: smooth at 5 Hz map refresh (position interpolation may
  drive up to 10 Hz); the map must never steal the SVS's frame
  budget: collect work rides the SAME shared collect slot the SVS
  collectors use, so the two instruments serialise instead of
  stacking GIL bursts.
- Terrain tile render: <100 ms/tile on the worker, amortised by LRU;
  pan/zoom shows cached tiles immediately, refines async.
- Vector layers: <5 ms paint at 200 features on-screen; declutter
  keeps N bounded.
- Memory: tile cache capped (~150 MB), navaids/airports queries
  windowed by view.

## 10. Phases

- **A — skeleton**: widget + MapTransform + ownship + range rings
  layer + range/orient actions; factory/schema/twin; offscreen
  renders. (The provider model proves out with the trivial layer.)
- **B — terrain**: TileCache + mip hypsometric/hillshade tiles, LRU,
  caution mode.
- **C — airports**: sectional symbols from airport_db + declutter;
  tower data added to the airports pack build (makerplane-data).
- **D — navaids/fixes/airways**: the new navaids.sqlite pack
  (makerplane-data cyclical pipeline) + the two vector layers.
- **E — controls polish**: legend chip, layer menu UX with the real
  controller hardware.
- Each phase ships behind the standard two-repo pipeline (factory ->
  schema -> R2 -> twin) and lands on the Pi for flight eval.

## 11. Decisions (Bill, 2026-07-05)

1. **Split-screen**: expected down the road; since the widget is
   freely placeable/sizable in the configurator, split layouts come
   for free — no special casing, just don't assume full-screen.
2. **Orientation**: configurator property (`orientation`,
   track_up/north_up — pilots fight endlessly; we don't pick sides).
   Boot default track_up.
3. **Pack growth approved** (TWR for tower coloring; more packs
   expected generally).
4. **Range ladder**: configurable property (`range_ladder`, comma
   list; default 2,5,10,20,40,80,160).
5. **Terrain default**: configurator property; default `relief`.

Development branch: `moving-map` (off display-changes).
