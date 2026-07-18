# Screen Builder

The **screen builder** lets you define an entire screen layout — every
instrument, where it sits, how big it is, and its options — purely in YAML. No
code. A screen using it sets `module: pyefis.screens.screenbuilder`.

This page covers **layout and placement**. For the catalog of widgets you can
place, see [Widget Reference](Widget-Reference); for the shared concepts
(FIX keys, fonts, colors) see [Concepts](Concepts); for customizing the shipped
screens without editing them, see [Preferences & Styling](Preferences-and-Styling).

```yaml
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 200
      rows: 110
    instruments:
      - type: airspeed_dial
        row: 0
        column: 0
```

---

## The `main` section & `nodeID`

The `main` config carries a `nodeID` that identifies this physical display.
Anywhere in a screen config you can write `{id}` and it is replaced with the
node's id. This matters most for **buttons**: a touchscreen button's FIX key is
written `dbkey: TSBTN{id}12`, so node 1 uses `TSBTN112` and node 2 uses
`TSBTN212` — pressing a button on the pilot's display doesn't trigger the
co-pilot's. See [Screens Overview](Screens-Overview) for how the active screen
set and default screen are chosen.

---

## Layout: the grid

A screen defines a virtual grid with `columns:` and `rows:` (first row/column is
`0`). Instruments are placed and sized in **grid cells**, not pixels, so a
layout scales to any physical resolution.

- Pick a grid that's easy to reason about. A 16:9-ish `200 × 110` is the
  convention for **all screens shipped with pyEFIS**, so layouts can be shared
  and scaled between users. (A `640 × 480` grid lets you place by the pixel, but
  won't transfer cleanly to a different resolution.)
- `font_mask` (per widget) keeps text fitting when a screen is scaled — see
  [Concepts §4](Concepts#4-fonts-masks--ghosting).

### Preview grid

While building, overlay a grid to find row/column positions:

```yaml
    layout:
      columns: 200
      rows: 110
      draw_grid: true
```

![Grid overlay](../images/draw_grid.png)

### Margins

Exclude a region (e.g. behind a menu) so no instrument lands there. Margins are
in **percent** (so they scale), for any of `top` / `bottom` / `left` / `right`:

```yaml
    layout:
      columns: 200
      rows: 110
      margin:
        top: 10
        left: 10
```

![Margin](../images/margin.png)

---

## Placing instruments

`instruments:` is a list, **rendered top to bottom** — later entries draw *over*
earlier ones, which is how you layer (e.g. an HSI on top of an attitude
indicator). At minimum each entry needs `type:`, `row:`, `column:`.

### `span`

`span: {rows, columns}` sets how many cells the instrument occupies. It is drawn
as large as possible inside that box **without distorting its aspect ratio**,
centered by default.

```yaml
      - type: airspeed_dial
        row: 0
        column: 0
        span:
          rows: 55
          columns: 66
```

![Span](../images/span.png)

### `move` — shrink & justify

`move:` gives `shrink:` (percent smaller) and `justify:` (push to `top` /
`bottom` / `left` / `right`). Shrinking without justify stays centered. This is
how you overlay a smaller instrument on a larger one — e.g. center an
`atitude_indicator` and a shrunken `horizontal_situation_indicator` in the same
span.

```yaml
      - type: horizontal_situation_indicator
        row: 50
        column: 50
        span: {rows: 50, columns: 50}
        move:
          shrink: 10
          justify:
            - bottom
```

![Shrink](../images/shrink.png)
![Options + move](../images/options_move.png)

### `options` & `dbkey`

Per-widget settings go under `options:`. Generic gauges need a FIX key:

```yaml
      - type: arc_gauge
        row: 1
        column: 1
        options:
          name: RPM
          dbkey: TACH1
          decimal_places: 0
```

How options reach the widget (the `setattr`/special-case mechanic) is explained
in [Concepts §8](Concepts#8-how-options-reach-a-widget). The per-widget option
tables are in the [Widget Reference](Widget-Reference).

---

## Ganged instruments

Prefix a gauge type with `ganged_` (e.g. `ganged_vertical_bar_gauge`) to repeat
it as a tidy row or column — ideal for cylinder strips and power columns. Gang
vertically by default; set `gang_type: horizontal` for a row.

Each gang has one or more **groups**; groups are visually separated (tune the
spacing with `gap:`). `common_options:` apply to every instrument in a group; a
per-instrument `options:` overrides them. You don't repeat `type:` inside a gang
— it's inherited from the `ganged_` type.

```yaml
      - type: ganged_vertical_bar_gauge
        gang_type: horizontal
        row: 8
        column: 1
        span: {rows: 5, columns: 27}
        groups:
          - name: Power
            instruments:
              - {options: {name: Volt, dbkey: VOLT, decimal_places: 1, show_units: false}}
              - {options: {name: Amp,  dbkey: CURRNT, show_units: false}}
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

The group `name` is currently cosmetic (not used internally). See
[Engine & Data Gauges](Widgets-Engine-Gauges) for the EGT mode behavior.

---

## Includes

Configs get large and you'll want to reuse instrument clusters across screens.
An include is a YAML file whose top level is `instruments:` (built exactly like
a screen's instrument list). Reference it as a `type`:

```yaml
    instruments:
      - type: include,config/includes/side-buttons.yaml
```

You can nest includes (just don't make them recursive). For example
`default.yaml` includes a radio display that itself includes its active/standby
sub-displays.

### Replacements

Reuse one include for multiple devices. `replace:` substitutes `{token}` values
inside the include — e.g. two com radios from one set of includes:

```yaml
      - type: include,includes/mgl/v16/active-display.yaml
        row: 70
        column: 156
        span: {rows: 40, columns: 45}
        replace:
          radio_id: 1
```

Inside the include, `dbkey: COMACTFREQ{radio_id}` becomes `COMACTFREQ1`.

### Relative & scaled includes

An include is authored as if it starts at `0,0`; the `row`/`column` you give it
in the parent shifts the whole cluster there (so you can define something
complex once and drop it anywhere). Add a `span:` to scale the whole include to
a different size.

```yaml
      - type: include,includes/ahrs/virtual_vfr.yaml
        row: 0
        column: 0
        span: {rows: 55, columns: 77.5}
```

---

## Encoder control

pyEFIS can be driven entirely from **one rotary encoder + button** (panel-mount,
no touchscreen). Enable it per screen by naming the encoder and button FIX keys:

```yaml
screens:
  SIXPACK:
    module: pyefis.screens.screenbuilder
    title: Standard Instrument Panel
    encoder: ENC9
    encoder_button: BTN9
```

- Rotating moves an **orange** selection highlight between selectable widgets,
  in the order set by each widget's `encoder_order` (the shipped configs use
  11–20 for buttons, 21–30 for radio parts, 31–40 for EGT mode buttons).
- Pressing **selects**; rotating then edits the value or scrolls a list;
  pressing again **commits**; letting it time out **reverts**.

The selectable widgets are the gauges, `numeric_display`, `button`, and
`listbox`. The full set of value-editing options
(`clipping`, `encoder_multiplier`, `encoder_set_real_time`, `encoder_num_mask`
for digit-by-digit radio tuning, `encoder_set_key`, …) is described in
[Concepts §6](Concepts#6-encoder-interaction), with the per-widget specifics on
each [Widget Reference](Widget-Reference) page.
