# Attitude Indicator & Synthetic Vision

The **attitude indicator** (`atitude_indicator`) is the artificial horizon: a
moving sky/ground background behind a fixed aircraft symbol, with a pitch
ladder, bank-angle scale, slip/skid ball, standard-rate-turn markers, and a
GPS flight-path marker.

**Virtual VFR** (`virtual_vfr`) is a subclass of the attitude indicator that
adds geographic symbology — airports, runways, extended centerlines, PAPI, and
navaids — projected onto the horizon from FAA CIFP/NASR data.

Both widgets can additionally render a **Synthetic Vision (SVS)** terrain view
behind the pitch ladder. SVS is enabled the same way on either widget — through
a nested `svs:` block — and is covered in the last section.

These widgets are part of the [Flight Instruments](Widgets-Flight-Instruments)
family. Unlike the generic gauges, they have **fixed default FIX keys** and a
**small, specific set of options** (they do not use the gauge
[color-state model](Concepts#2-the-color-state-model-gauges)). **Read
[Concepts](Concepts) first** for how `options:` reach a widget and what the
data-quality states mean.

| `type:` | Class | Default FIX keys | Adds over base |
|---------|-------|------------------|----------------|
| `atitude_indicator` | `ai.AI` | `PITCH`, `ROLL`, `ALAT`, `TAS` | artificial horizon + FPM |
| `virtual_vfr` | `ai.VirtualVfr.VirtualVfr` | `PITCH`, `LAT`, `LONG`, `HEAD`, `ALT`, `ROLL`, `ALAT`, `TAS` | airport / runway / navaid overlay |

> **Spelling gotcha:** the YAML `type:` is **`atitude_indicator`** — the
> historical misspelling (one "t") is the real key the screen builder matches.
> `attitude_indicator` will not work.

---

## `atitude_indicator`

A standard PFD-style artificial horizon. The blue/brown background pitches and
rolls behind a fixed aircraft reference symbol. It draws a pitch ladder, a
bank-angle scale with standard-rate-turn diamonds, an inclinometer (slip/skid)
ball driven by lateral acceleration, and a GPS flight-path marker.

![Attitude indicator](../images/atitude_indicator.png)

**`type:`** `atitude_indicator` &nbsp;→&nbsp; class `ai.AI`

### FIX keys

The attitude indicator wires these keys at construction (defaults from
`INSTRUMENT_DEFAULTS`); they are **not** settable from YAML:

| Key | Drives |
|-----|--------|
| `PITCH` | pitch angle (clamped ±90°) |
| `ROLL` | bank angle (clamped ±180°) |
| `ALAT` | lateral acceleration → slip/skid ball (clamped ±0.3) |
| `TAS` | true airspeed → standard-rate-turn bank markers |

It additionally **listens** for the flight-path-marker and SVS-position keys if
they exist in the FIX database — `VS`, `GS`, `TRACK`, `HEAD`, `VPATH` (FPM) and
`LAT`, `LONG`, `ALT`, `MAGVAR` (SVS). Each is wired through a
missing-key guard: if the key is not defined, the widget logs a warning and the
related feature stays disabled rather than crashing. The flight-path marker
requires `VS`, `GS`, `TRACK`, and `HEAD` to be present and healthy; `VPATH` is
used in preference to `atan2(VS, GS)` when published.

> Quality flags on `PITCH`/`ROLL`/`ALAT`/`TAS` change the background: **old** or
> **bad** turns the sky/ground grey; **fail** swaps in a failure scene showing a
> red `XXX`. (Virtual VFR extends this — see below.)

### Options

These are the options the screen-builder factory (`build_atitude_indicator`)
reads from the `options:` block, plus the host-widget attributes it applies.
Defaults in **bold**.

| Option | Default | Meaning |
|--------|---------|---------|
| `show_fpm` | **`true`** | draw the GPS flight-path marker (the "velocity vector" circle). Passed to the constructor. |
| `aircraft_symbol` | **`classic`** | fixed reference symbol style. `classic` = split wing bars + centre dot; `garmin` / `gi275` / `gi-275` / `g1000` = GI-275-style tapered wing wedges + centre boresight. |
| `symbol_color` | **`yellow`** | colour of the aircraft reference symbol (any Qt colour name; invalid names fall back to yellow). |
| `svs` | none | nested block enabling Synthetic Vision — see [Enabling Synthetic Vision](#enabling-synthetic-vision-svs). |
| `horizon_heading_marks` | **`false`** | draw a compass heading scale on the white horizon line: short vertical ticks with numeric labels that ride the horizon and scroll as the aircraft turns (driven by magnetic `HEAD`; aligns with the SVS terrain). |
| `horizon_heading_interval` | **`10`** | degrees of heading between ticks. |
| `horizon_heading_label_interval` | **`20`** | degrees of heading between labels (cardinal letters at N/E/S/W, else the heading in tens, e.g. 060 → "6"). |
| `horizon_heading_tick_length` | **`5`** | tick length, pixels. |
| `horizon_heading_color` | **`#ffffff`** | colour of the heading ticks and labels. |

`font_percent` and `font_family` come from
[preferences](Preferences-and-Styling), not `options:` (see
[Concepts §8](Concepts#8-how-options-reach-a-widget)). `font_percent` sizes the
pitch-ladder numerals and tick widths.

> The pitch-ladder geometry (`pitchDegreesShown`, `minorDiv`/`majorDiv`/
> `numberedDiv`, `bankAngleMaximum`, `pitchOpacity`, `drawBankMarkers`, …) and the
> horizon heading marks above are exposed as editor options in the
> [configurator](https://pyefis.aerocommons.org) (each with a hover tooltip); the
> shipped screens otherwise leave the geometry at code defaults.
> `pitchDegreesShown` is fixed at 30° top-to-bottom, which sets the horizontal
> field of view that SVS terrain — and the heading scale — share. These options
> apply to both `atitude_indicator` and `virtual_vfr` (they share the AI base).

---

## `virtual_vfr`

Virtual VFR is the attitude indicator **plus a geographic overlay**. It
subclasses `ai.AI`, so it inherits the full horizon, pitch ladder, bank scale,
slip ball, FPM, and SVS support — then projects nearby airports and runways onto
the scene from FAA data.

![Virtual VFR](../images/virtual_vfr.png)

**`type:`** `virtual_vfr` &nbsp;→&nbsp; class `ai.VirtualVfr.VirtualVfr`

### What it adds over the attitude indicator

- **Runways** drawn as filled polygons in their true geographic position, with
  the runway-number label, a dashed **centerline**, and a dashed **extended
  centerline** down to the bottom of the view when the threshold is in front of
  you.
- **PAPI lights** at each runway, coloured red/white from the computed approach
  angle. When the glideslope indicator is enabled it can drive the `GSI` FIX key
  from the deviation off a 3° path.
- **Airport identifiers** as text labels (collision-avoided against each other).
- **Navaids** (VORTAC icon + label).

These are computed by an internal `PointOfView` projector that reads airport and
runway records from the **FAA CIFP** database, caching the 1°×1° blocks around
the aircraft and refreshing as position changes.

### FIX keys

In addition to the base AI keys (`PITCH`, `ROLL`, `ALAT`, `TAS`), Virtual VFR
reads the position/heading keys needed to place the overlay:

| Key | Drives |
|-----|--------|
| `LAT` / `LONG` | aircraft position (projection origin) |
| `ALT` | aircraft altitude (approach-angle / PAPI math) |
| `COURSE` | view heading used to orient the projection |
| `GSI` | **written** with the computed glideslope deviation when GSI is active |

> Note: although `INSTRUMENT_DEFAULTS` lists `HEAD` for `virtual_vfr`, the widget
> actually binds the **`COURSE`** key as its heading source in the constructor.
> The heading is treated as the true heading for the geographic projection.

If `LAT`/`LONG`/`COURSE`/`ALT` are flagged **old**, **bad**, or **fail**, the
overlay is **blanked** (all runway/airport/navaid objects removed) and only the
plain attitude horizon shows — Virtual VFR overrides `setOld`, `setVfrBad`, and
`setVfrFail` to drop the geographic objects when the data cannot be trusted, so
it never paints a stale runway picture.

### Options

Virtual VFR is built by `build_virtual_vfr`, which reads the **same** options
the attitude indicator does:

| Option | Default | Meaning |
|--------|---------|---------|
| `aircraft_symbol` | **`classic`** | reference symbol style (as above) |
| `symbol_color` | **`yellow`** | reference symbol colour |
| `svs` | none | nested Synthetic Vision block (see below) |

Note `build_virtual_vfr` does **not** read `show_fpm` — Virtual VFR uses the
inherited FPM default (on). The CIFP data location is **not** taken from the
widget's `options:`; it comes from the screen/config-level items the widget
reads from its parent (`dbpath`, `indexpath`, `refresh_period`, and an optional
`metadata` file that picks the most recent of a current/next CIFP cycle).

> **Uncertainty:** Virtual VFR's CIFP `dbpath`/`indexpath`/`metadata` are pulled
> from `self.myparent.get_config_item(...)`, i.e. from the screen/profile config
> rather than the widget `options:` block. The exact config level where those are
> set is outside the widget source read for this page — confirm against your
> profile/`config.yaml` before relying on the paths.

---

## Enabling Synthetic Vision (SVS)

Both `atitude_indicator` and `virtual_vfr` can render a **GPU terrain view**
behind the pitch ladder, replacing the flat brown "ground" with shaded synthetic
terrain (and overlaying water, obstacles, runways, and runway markings). SVS is
enabled through a **nested `svs:` block inside `options:`** — the screen-builder
factory passes that block straight to the widget's `set_svs_config()`, which
constructs the `SVSRenderer`.

SVS sits at scene z-order `0.5`: it covers the static blue/brown background but
stays **behind** the pitch ladder and symbology (z = 1). When it is actively
drawing terrain, the below-horizon fill is painted sky-blue so the synthetic
terrain *is* the ground. SVS is **GL-required**: if a GL context or draw fails it
disables itself for the process and the widget annunciates **SVS UNAVAIL** in
amber rather than silently showing a degraded picture.

### The nested `svs:` block

The essential keys are `enabled: true` plus the **data paths** that tell the
renderer where to find terrain and feature data:

| `svs:` key | Meaning |
|------------|---------|
| `enabled` | master switch — must be `true` for any terrain to draw (default `false`) |
| `tile_path` | directory of terrain elevation tiles (HGT heightmaps) |
| `nasr_db_path` | airport/runway sqlite (FAA NASR — the preferred source) |
| `dof_db_path` | obstacle sqlite (FAA Digital Obstacle File — towers/antennas) |
| `water_db_path` | water-polygon sqlite (oceans, lakes, rivers) |
| `highway_db_path` | highway/road sqlite |

(If NASR is unavailable, the renderer falls back to `cifp_path` /
`cifp_index_path` for airport data. Many other renderer-tuning keys exist —
`range_nm`, `auto_range`, `haze`, `n_range`/`n_az`/`fov_deg`, `msaa_samples`,
`frame_rate`, `z_value`, … — but those are the **SVS renderer's** options and are
documented separately, not here.)

### Example

```yaml
- type: virtual_vfr
  row: 0
  column: 0
  span: {rows: 100, columns: 100}
  options:
    aircraft_symbol: gi275
    symbol_color: yellow
    svs:
      enabled: true
      tile_path: /data/makerplane-data/terrain/tiles
      nasr_db_path: /data/makerplane-data/nasr/airports.sqlite
      dof_db_path: /data/makerplane-data/dof/obstacles.sqlite
      water_db_path: /data/makerplane-data/water/current/water.sqlite
      highway_db_path: /data/makerplane-data/highways/highways.sqlite
```

Any data file that is missing or unreadable is handled gracefully — that feature
layer simply does not draw; it never breaks the renderer.

### Full SVS reference

The terrain renderer (tiers, polar-fan LOD, auto-range, haze, runway markings,
obstacles, water, and all the tuning keys) is documented in detail in
[docs/svs_rendering.md](https://github.com/billmallard/pyEfis/blob/gpu-required/docs/svs_rendering.md).
Design rationale and the original NASR-import plan live in `docs/svs_planning.md`.

---

See also: [Concepts](Concepts) · [Widget Reference](Widget-Reference) ·
[Flight Instruments](Widgets-Flight-Instruments) · [Pilot's Guide](Pilots-Guide)
