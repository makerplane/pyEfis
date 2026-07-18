# Engine & Data Gauges

The four **generic gauges** are the workhorses of the EMS (Engine Monitoring
System) and any data display. They all share the `AbstractGauge` base, so they
share the [color-state model](Concepts#2-the-color-state-model-gauges), the
[data-quality states](Concepts#3-data-quality--states),
[fonts/masks/ghosting](Concepts#4-fonts-masks--ghosting), and the
[encoder model](Concepts#6-encoder-interaction). **Read [Concepts](Concepts)
first** — this page only documents what is specific to each gauge.

| `type:` | Class | Shape | Default `show_units` |
|---------|-------|-------|----------------------|
| `arc_gauge` | `gauges.ArcGauge` | 180° analog arc + digital value | `false` |
| `horizontal_bar_gauge` | `gauges.HorizontalBar` | horizontal bar + value | `true` |
| `vertical_bar_gauge` | `gauges.VerticalBar` | vertical bar + value (EGT/CHT strips) | `true` |
| `numeric_display` | `gauges.NumericDisplay` | number only (color-aware) | `false` |

All four:
- Have **no default FIX key** — you must set `dbkey:` (see [§Common options](#common-options-all-four)).
- Read their green/yellow/red bands and warn/alarm thresholds from the **key's
  aux values** (`Min`/`Max`/`lowWarn`/`lowAlarm`/`highWarn`/`highAlarm`), *not*
  from YAML. See [FIX aux values](Concepts#aux-values).
- Are **encoder-selectable and editable**.
- Can be **ganged** (`ganged_arc_gauge`, `ganged_vertical_bar_gauge`, …) into
  groups — this is how the cylinder strips are built. See
  [Screen Builder → Ganged](Screen-Builder#ganged-instruments).

---

## Common options (all four)

These come from the shared base and behave identically everywhere. Defaults in
**bold**.

| Option | Default | Meaning |
|--------|---------|---------|
| `dbkey` | *(required)* | FIX key the gauge displays |
| `name` | none | label drawn on the gauge |
| `decimal_places` | **1** | digits after the decimal in the value text |
| `show_units` | per-gauge | draw the units string from the key |
| `highlight_key` | none | if the displayed value equals this key's value, draw the highlight (e.g. mark the hottest cylinder via `EGTMAX1`) |
| `temperature` | false | mark the value as a temperature so unit switching (°C/°F) applies |
| `clipping` | false | clamp encoder edits to the key min/max |
| `font_family`, `font_mask`, `font_ghost_mask`, `units_font_mask`, `name_font_mask`, … | see [Concepts §4](Concepts#4-fonts-masks--ghosting) | text sizing / ghosting |
| `bg_*_color`, `safe_*_color`, `warn_*_color`, `alarm_*_color`, `text_*_color`, `pen_*_color`, `highlight_*_color` (each in `_good_` and `_bad_` form) | see [Concepts §2](Concepts#2-the-color-state-model-gauges) | full color palette |
| encoder: `encoder_order`, `encoder_multiplier`, `encoder_set_real_time`, `encoder_num_mask`, `encoder_set_key`, … | see [Concepts §6](Concepts#6-encoder-interaction) | encoder selection & editing |

> Note: `min_size` exists in the constructors but the screen builder always
> creates these gauges with `min_size=False` so they scale to their `span`. You
> do not set it from YAML.

---

## `arc_gauge`

A 180° analog arc (sweeping 45°→135°) with green/yellow/red bands drawn from the
key's aux thresholds, a pointer, and a digital value. Good for round-dial
quantities like RPM, oil pressure, manifold pressure.

![Arc gauge](../images/arc_gauge.png)
![Arc gauge, segmented](../images/arc_gauge_segmented.png)

| Option | Default | Meaning |
|--------|---------|---------|
| `name_location` | **`top`** | where the name sits relative to the value: `top` or `right` |
| `show_units` | **`false`** | |
| `segments` | **0** | if > 0, overlay N discrete segments (LCD-bar-graph look) instead of a smooth arc |
| `segment_gap_percent` | **0.01** | width of the black gaps between segments |
| `segment_alpha` | **180** | darkness (0–255) of the "unfilled" segment overlay |

```yaml
- type: arc_gauge
  row: 0
  column: 0
  span: {rows: 50, columns: 50}
  options:
    name: RPM
    dbkey: TACH1
    decimal_places: 0
    show_units: false
```

---

## `vertical_bar_gauge`

A vertical bar with green/yellow/red bands, an indicator line, and name/value/
units. This is the **EGT/CHT strip** gauge and carries the engine-leaning
machinery.

![Vertical bar gauge](../images/vertical_bar_gauge.png)
![Vertical bar gauge, segmented](../images/vertical_bar_gauge_segmented.png)

| Option | Default | Meaning |
|--------|---------|---------|
| `show_name` / `show_value` / `show_units` | **true** / **true** / **true** | toggle each label |
| `bar_width_percent` | **0.3** | bar width as fraction of widget width |
| `line_width_percent` | **0.5** | indicator-line width as fraction of widget width |
| `small_font_percent` | **0.08** | name/units font size |
| `big_font_percent` | **0.10** | value font size |
| `text_gap` | **3** | px between bar and text |
| `segments` | **0** | discrete-segment overlay |
| `segment_gap_percent` | **0.012** | |
| `segment_alpha` | **180** | |
| `highlight_key` | none | draw the highlight ball when value == this key (mark the hottest cylinder) |
| `egt_mode_switching` | false | enable the EGT mode buttons (normalize/peak/lean) — set via `common_options` on the gang group |
| `normalize_range` | **0** | full-scale span (°) used when in normalize mode; must be > 0 for normalize/lean to show a deflection |

### EGT modes (engine leaning)

When `egt_mode_switching` is on, a `vertical_bar_gauge` responds to mode actions
(driven by the EGT buttons — see [Pilot's Guide](Pilots-Guide)):

| Mode | Behavior |
|------|----------|
| **normal** | absolute value vs. the key's range (default) |
| **peak** | tracks the peak value; once the value falls ≥10° below peak, shows the **delta below peak** in magenta — the classic "X° rich/lean of peak" |
| **normalize** | re-centers the bar on the value captured when normalize was engaged, scaled by `normalize_range`, so all cylinders line up for comparison |
| **reset peak** | clears the stored peak |
| **lean** | shortcut: reset peak + normalize + peak together |

> This is the one gauge where the *mode* (not just the value) changes what you
> see. Document it carefully when you write screens for fuel-injected engines.

---

## `horizontal_bar_gauge`

Same data model as the vertical bar, laid out horizontally. Common for trim
position, fuel, and quantities where a wide short gauge fits the panel better.

![Horizontal bar gauge](../images/horizontal_bar_gauge.png)
![Horizontal bar gauge, segmented](../images/horizontal_bar_gauge_segmented.png)

| Option | Default | Meaning |
|--------|---------|---------|
| `show_name` / `show_value` / `show_units` | **true** / **true** / **true** | toggle each label |
| `bar_divisor` | **4.5** | controls bar thickness (larger = thinner bar relative to height) |
| `segments` | **0** | discrete-segment overlay |
| `segment_gap_percent` | **0.01** | |
| `segment_alpha` | **180** | |

It has **no** `highlight_key`/peak/normalize machinery — those are
vertical-bar-only.

---

## `numeric_display`

A pure numeric readout that — unlike `value_text` or `static_text` — applies the
full gauge color model: it goes yellow/red on warn/alarm thresholds, dims when
old/bad, and shows `XXX` (masked) on fail. Use it wherever a number must signal
its own health.

![Numeric display](../images/numeric_display.png)
![Numeric display, segmented + ghosting](../images/numeric_display_segmented_ghosting.png)

| Option | Default | Meaning |
|--------|---------|---------|
| `show_units` | **false** | draw units to the right of the value |
| `small_font_percent` | **0.4** | units font size relative to the value font |
| `decimal_places` | **1** | (shared) |
| `font_mask` / `font_ghost_mask` / `units_font_mask` | see Concepts | sizing + LCD ghosting |

> Do **not** confuse `numeric_display` (this gauge) with the internal
> `NumericalDisplay` scrolling-drum widget used inside the airspeed/altimeter
> tapes — the latter is not a screen-builder `type:` you place directly.

---

## Ganging gauges (EMS strips)

Prefix any of the four types with `ganged_` to repeat it across **groups**.
Each group is visually separated; `common_options` apply to all members of a
group, and a per-instrument `options:` overrides them. This is exactly how the
4-cylinder EGT/CHT strips and the power column are built.

```yaml
- type: ganged_vertical_bar_gauge
  gang_type: horizontal      # default is vertical
  row: 8
  column: 1
  span: {rows: 5, columns: 27}
  groups:
    - name: EGT
      common_options:
        egt_mode_switching: true
        normalize_range: 400
      instruments:
        - {options: {name: "1", dbkey: EGT11, show_units: false}}
        - {options: {name: "2", dbkey: EGT12, show_units: false}}
        - {options: {name: "3", dbkey: EGT13, show_units: false}}
        - {options: {name: "4", dbkey: EGT14, show_units: false}}
```

See [Screen Builder → Ganged Instruments](Screen-Builder#ganged-instruments)
for the full grouping/`gap`/`encoder_order` rules, and
[Preferences & Styling](Preferences-and-Styling) for binding gauge slots
(`ARC1`, `BAR15`, …) and applying styles in one place.
