# Concepts & Shared Vocabulary

This page defines the ideas and option names that recur across **every** pyEFIS
widget. The per-widget reference pages assume you have read this; they only
document what is *specific* to each widget and link back here for the shared
parts.

> **Audience:** builders and engineers. If you just want to fly, start with the
> [Pilot's Guide](Pilots-Guide). If you want to lay out a screen, read
> [Screen Builder](Screen-Builder) next.

---

## 1. The FIX database (the data bus)

pyEFIS is a **display only**. It draws values it reads from a shared in-memory
table called the **FIX database**, which is fed over TCP by a companion
process, **fix-gateway**. Every live number on screen — airspeed, altitude,
oil pressure, a GPS course — is a **FIX key**.

A FIX key has:

| Property | Meaning |
|----------|---------|
| **value** | the current number (or string/bool) |
| **min / max** | the defined range of the key |
| **units** | e.g. `knots`, `ft`, `degC` |
| quality flags: **old / bad / fail / annunciate** | see [§3 Data quality](#3-data-quality--states) |
| **aux** values | named sub-values attached to the key (see below) |

### Aux values

Gauges read **threshold and range information** from a key's *aux* values, not
from the YAML. The standard aux names a gauge understands are:

`Min`, `Max`, `lowAlarm`, `lowWarn`, `highWarn`, `highAlarm`

So a tachometer's redline, yellow arc, and green arc are defined by the **aux
values of the `TACH1` key** (set in fix-gateway), and any gauge bound to that
key picks them up automatically. The airspeed key (`IAS`) carries aviation
aux values instead: `Vs`, `Vs0`, `Vno`, `Vne`, `Vfe`, `Va`, `Vx`, `Vy`, … —
these drive the colored bands on the airspeed tape.

> **Builder takeaway:** to change where a redline sits, change the key's aux
> value in fix-gateway, *not* the pyEFIS config. The widget just reflects it.

### Binding a widget to a key — `dbkey`

Flight instruments have a **default** key wired in (e.g. the airspeed tape
always reads `IAS`). Generic gauges (`arc_gauge`, `*_bar_gauge`,
`numeric_display`) have **no** default and require you to name the key:

```yaml
- type: arc_gauge
  options:
    name: RPM
    dbkey: TACH1
```

The complete list of which widget reads which key by default lives in
[FIX Database Keys](FIX-Database-Keys).

---

## 2. The color-state model (gauges)

All four generic gauges (`arc_gauge`, `horizontal_bar_gauge`,
`vertical_bar_gauge`, `numeric_display`) share one base class
(`AbstractGauge`), so they share an identical color model. There are **two full
color palettes** — a *good* palette used when the data is healthy and a *bad*
palette used when it is not — and every color is individually overridable.

| Role | `good` default | `bad` default | Option (good / bad) |
|------|----------------|---------------|---------------------|
| Background | black | black | `bg_good_color` / `bg_bad_color` |
| Safe band (green arc/bar) | green | dark gray | `safe_good_color` / `safe_bad_color` |
| Warn band | yellow | dark yellow | `warn_good_color` / `warn_bad_color` |
| Alarm band | red | dark red | `alarm_good_color` / `alarm_bad_color` |
| Text | white | gray | `text_good_color` / `text_bad_color` |
| Pen (pointer/line) | white | gray | `pen_good_color` / `pen_bad_color` |
| Highlight | magenta | dark magenta | `highlight_good_color` / `highlight_bad_color` |

Colors accept Qt color names (`green`, `darkRed`) or hex (`'#00FF00'`,
`'#00000000'` for transparent ARGB).

**How the value color is chosen each frame:**
1. Start from the *good* or *bad* palette depending on the quality flags.
2. The numeric value's color shifts to **warn** if it crosses `lowWarn`/`highWarn`,
   and to **alarm** if it crosses `lowAlarm`/`highAlarm` (from the key's aux values).
3. If the key is **annunciating** (and not failed), the text turns red.
4. If the gauge is the encoder's current selection, it is drawn **orange**
   (see [§6 Encoder](#6-encoder-interaction)).

---

## 3. Data quality — states

Every value carries four independent quality flags from fix-gateway. They are
the difference between "the engine is fine" and "we lost the sensor," and the
widgets render them distinctly:

| Flag | Meaning | Typical rendering |
|------|---------|-------------------|
| **(healthy)** | live, trusted value | normal/"good" palette |
| **old** | value hasn't updated within its timeout | dimmed ("bad" palette); scrolling readouts blank the digits |
| **bad** | value present but flagged untrustworthy | dimmed ("bad" palette) |
| **fail** | sensor/source failed | value forced to 0; gauges show `X`/`XXX` in place of digits |
| **annunciate** | attention requested for this key | text turns red |

When you generate screenshots, the mock database (`tests/conftest.py`)
provides keys pre-set to each of these states (`NUMOK`, `NUMOLD`, `NUMBAD`,
`NUMFAIL`, `NUMANNUNCIATE`, `NUMLOWWARN`, `NUMLOWALARM`, …) precisely so a
single config can show every state side by side.

---

## 4. Fonts, masks & ghosting

These options appear on most text-bearing widgets and are easy to misread, so
they are defined once here.

- **`font_family`** — default `'DejaVu Sans Condensed'`. Aviation "segmented"
  looks use `'DSEG14 Classic'` / `'DSEG7'`; monospace readouts use
  `'DejaVu Sans Mono'`.
- **`font_percent`** — sizes the font as a fraction of the widget height
  (instrument-specific default).
- **`font_mask`** — a *sizing template*. The widget measures this string and
  picks the largest font that still fits it, so the text never overflows or
  jiggles as digits change. `font_mask: "000"` reserves room for three digits;
  `"00.00"` for two-and-two with a decimal point. **Setting a `font_mask` also
  right-justifies the value** (vs. centered when unset).
- **`*_font_mask` variants** — `units_font_mask`, `name_font_mask` size the
  units and name sub-labels the same way.
- **`font_ghost_mask`** (and `units_font_ghost_mask`, `name_font_ghost_mask`) —
  draws a **dim "unlit segment" background** behind the live text, mimicking an
  LCD/LED display where the inactive segments are faintly visible. A common
  pairing is `font_mask: "00.00"` with `font_ghost_mask: "~~.~~"` or `"88.88"`.
- **`font_ghost_alpha`** — opacity (0–255) of the ghost layer; default `50`.

![Numeric display with segmented font and ghosting](../images/numeric_display_segmented_ghosting.png)

---

## 5. Layout: grid, span, move, ganging

How a widget is *placed* is handled by the [Screen Builder](Screen-Builder),
not the widget. The essentials:

- Screens define a virtual **grid** (`rows` × `columns`); the shipped screens
  use `200 × 200`-ish grids so a layout scales to any physical resolution.
- **`row` / `column`** set the top-left cell of the widget.
- **`span: {rows, columns}`** sets how many cells it occupies. The widget is
  drawn as large as possible inside that box **without distorting its aspect
  ratio**, centered by default.
- **`move: {shrink, justify}`** shrinks (by percent) and pushes the widget to a
  `top`/`bottom`/`left`/`right` edge of its span — used to overlay instruments
  (e.g. a small HSI centered on an AI).
- **`ganged_<type>`** repeats one gauge type in a tidy row/column of **groups**,
  with shared `common_options`. This is how the EMS strips (4 EGT bars, 4 CHT
  bars, a power column) are built. See [Screen Builder](Screen-Builder#ganged-instruments).

---

## 6. Encoder interaction

pyEFIS can be driven entirely from **one rotary encoder + button** (for
panel-mount use without a touchscreen). Widgets that support it (`arc_gauge`,
the bar gauges, `numeric_display`, `button`, `listbox`) advertise themselves as
*selectable*:

- Rotating the encoder moves an **orange** selection highlight between widgets,
  in the order set by each widget's **`encoder_order`**.
- Pressing the button **selects** the widget; rotating then changes its value
  (or scrolls a list); pressing again **commits** to the FIX key. Letting it
  time out **reverts**.

Value-editing options shared by the gauges (full detail in
[Screen Builder](Screen-Builder#encoder-control)):

| Option | Effect |
|--------|--------|
| `clipping` | keep the edited value within the key's min/max |
| `encoder_multiplier` | step size per detent (default 1) |
| `encoder_set_real_time` | write the key as you turn (still reverts on timeout) |
| `encoder_num_mask` | digit-by-digit entry using a mask like `"000.0000"` (radio tuning) |
| `encoder_set_key` | write a *different* key than the one displayed |

---

## 7. Preferences & styling

Rather than editing dozens of instruments, the shipped screens are
parameterised through **`preferences.yaml`** (+ your
`preferences.yaml.custom`):

- **`style` / `styles`** — named visual themes (`basic`, `segmented`, …) applied
  per gauge family (`ARC`, `BAR`, `TEXT`).
- **`gauges`** — bind a logical gauge slot (e.g. `ARC1`) to a key/name/options,
  in one place.
- **`enabled`** — feature toggles (`CYLINDER_3: false`, `TRIM_CONTROLS: true`).
  A widget's `disabled:` option may name one of these flags; `not FLAG` inverts.
- **`includes`** — swap which include file fills a named slot (e.g. which button
  bar) without editing every screen.

Full detail and examples: [Preferences & Styling](Preferences-and-Styling).

---

## 8. How `options:` reach a widget

A widget's `options:` block is applied by `apply_options`
(`screens/screenbuilder_options.py`). A handful of keys are special-cased:

- **`dbkey`** → calls the widget's `setDbkey()` (wires it to the FIX key),
- **`encoder_order`** → registers the widget in the screen's encoder selection list,
- **`egt_mode_switching: true`** (on `vertical_bar_gauge`) → connects the EGT mode signal,
- **`temperature` / `pressure` / `altitude: true`** (on gauges/`numeric_display`/
  the altimeter) → enables unit switching.

**Every other option is applied as a direct attribute on the widget instance**
(`setattr(instrument, option, value)`). The practical consequence — and the
basis of this whole reference — is:

> **A widget's available options are its settable instance attributes** (the
> ones assigned in its `__init__`). The option tables on each widget page are
> extracted from exactly those.

`font_family` and `font_percent` are the exception: they are resolved from
[preferences](Preferences-and-Styling) and passed to the constructor, not via
`options:`.

## 9. How to read a widget reference page

Each widget page is organised as:

1. **What it is** — one-paragraph description + screenshot.
2. **YAML `type:`** — the exact string(s) you put in a screen config.
3. **FIX keys** — what it reads/writes (defaults and overrides).
4. **Options** — a table of every option, its default, and what it does,
   extracted from source. Options inherited from the shared model above are
   noted but not re-explained.
5. **Notes / gotchas** — behavior that surprises people.
