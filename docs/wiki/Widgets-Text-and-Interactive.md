# Text & Interactive Widgets

This page covers the simple **text/value displays** and the two **interactive**
widgets. They do not share the `AbstractGauge` color-state machinery of the
[engine gauges](Widgets-Engine-Gauges); read [Concepts](Concepts) first for the
shared vocabulary (the FIX database, `dbkey`, fonts/masks/ghosting, the encoder
model). This page documents only what is specific to each widget.

| `type:` | Class | What it is | Interactive? |
|---------|-------|------------|--------------|
| `static_text` | `misc.StaticText` | a fixed label — no FIX key | no |
| `value_text` | `misc.ValueDisplay` | a plain readout of one FIX key (dim on old/bad/fail, red on annunciate) | no |
| `button` | `button.Button` | a stateful pushbutton driven by a per-button config file: shows data, changes color/text on conditions, and fires actions | yes (encoder-selectable) |
| `listbox` | `listbox.ListBox` | a scrollable table of user-defined lists that writes FIX keys when an item is selected | yes (encoder-selectable) |

> The two text widgets are deliberately "dumb" — if you want a number that goes
> yellow/red on its own thresholds, use [`numeric_display`](Widgets-Engine-Gauges#numeric_display)
> instead.

---

## `static_text`

A fixed label drawn once and never updated from the database. Used for panel
titles, units that never change, or any caption.

![Static text](../images/static_text.png)

**YAML `type:`** `static_text`

**FIX keys:** none.

The factory passes `text` and `font_family` to the constructor; every other
option is applied as an instance attribute (see [Concepts §8](Concepts#8-how-options-reach-a-widget)).

| Option | Default | Meaning |
|--------|---------|---------|
| `text` | `""` *(required, passed to constructor)* | the string to display |
| `alignment` | **`AlignLeft`** | Qt alignment-flag name, e.g. `AlignLeft`, `AlignCenter`, `AlignRight` |
| `font_family` | **`DejaVu Sans Condensed`** | resolved from preferences / passed to constructor |
| `font_percent` | **1.0** | font height as a fraction of the widget height (ignored when `font_mask` is set) |
| `font_mask` | none | sizing template; when set, the font is sized to fit this string instead of using `font_percent` (see [Concepts §4](Concepts#4-fonts-masks--ghosting)) |
| `font_ghost_mask` | none | dim "unlit segment" string drawn behind the text |
| `font_ghost_alpha` | **50** | opacity (0–255) of the ghost layer |
| `color` | white | text color (a `QColor`) |

```yaml
- type: static_text
  row: 0
  column: 0
  span: {rows: 10, columns: 40}
  options:
    text: "OIL"
    alignment: AlignCenter
```

---

## `value_text`

A plain readout of a single FIX key. It reflects the key's quality flags — it
dims to gray when the value is **old / bad / fail**, turns the text **red** when
the key is **annunciating**, and prints `xxx` when the key is **failed** — but,
unlike the gauges, it does **not** apply warn/alarm threshold colors.

![Value text](../images/value_text.png)

**YAML `type:`** `value_text`

**FIX keys:** no default — set `dbkey:`.

| Option | Default | Meaning |
|--------|---------|---------|
| `dbkey` | *(required)* | FIX key whose value is displayed (special-cased to `setDbkey()`, see [Concepts §8](Concepts#8-how-options-reach-a-widget)) |
| `name` | none | optional label attribute |
| `alignment` | **`AlignLeft`** | Qt alignment-flag name |
| `font_family` | **`Open Sans`** | resolved from preferences / passed to constructor |
| `font_percent` | **0.9** | font height as a fraction of the widget height (ignored when `font_mask` is set) |
| `font_mask` | none | sizing template (see [Concepts §4](Concepts#4-fonts-masks--ghosting)) |
| `font_ghost_mask` | none | dim "unlit segment" backing string |
| `font_ghost_alpha` | **50** | opacity (0–255) of the ghost layer |
| `number_format` | none | digit mask for the value: blank = as-is; `000` = `089` (rounded, zero-padded); `000.0` = `089.0` (with decimals) |
| `prefix_text` | none | static label drawn inline **before** the value (e.g. `HDG`, `CRS`); empty = no prefix |
| `prefix_font_family` | **`Open Sans`** | font family for the prefix label |
| `prefix_font_percent` | **50** | prefix height as a percent of the widget height |
| `prefix_color` | **`#ffffff`** | colour of the prefix label |
| `value_color` | **`#ffffff`** | colour of the data value (good/normal state; bad/old still grey, annunciate still red) |
| `border_color` | **`#ffffff`** | box border colour |
| `border_width` | **0** | box border thickness in px (0 = no border) |
| `border_opacity` | **100** | box border opacity (%) |
| `bg_color` | **`#000000`** | box background fill colour |
| `bg_opacity` | **0** | box background opacity (%); 0 = transparent (no fill) |

The optional **box** (border + background) is drawn at the widget bounds — the
same rectangle you drag/resize on screen — under the text. With `border_width`
and `bg_opacity` both at 0 (the defaults) there is no box, so existing displays
are unchanged.

The prefix is drawn in its own font/size/colour, baseline-aligned with the value
and positioned by `alignment` — so `prefix_text: HDG` over `dbkey: HEAD` gives a
Garmin-style **`HDG 114`** with the label and value styled independently.

Color attributes exist on the instance and can be overridden, but they are named
in this widget's own form (not the gauge `_good_`/`_bad_` form): `textGoodColor`,
`textBadColor`, `textAnnunciateColor`, `bgGoodColor`, `bgBadColor`,
`highlightGoodColor`, `highlightBadColor`, `outlineColor`.

```yaml
- type: value_text
  row: 0
  column: 0
  span: {rows: 10, columns: 40}
  options:
    dbkey: OILP1
    font_mask: "000"
```

> Use `number_format` for rounding / zero-padding the value. It applies no
> threshold coloring (the value just follows its quality flags); for warn/alarm
> bands use [`numeric_display`](Widgets-Engine-Gauges#numeric_display).

---

## `button`

A `button` is a stateful, interactive pushbutton. It is **not** the menu — it is
an instrument that can display data, change its color/text in response to FIX
data, and fire actions within pyEFIS. The classic use is a column of buttons
along each edge of the screen (reachable by the pilot and co-pilot), each one
showing the status of something and switching screens or toggling a setting. For
example, on the PFD an `EMS` button turns red when an engine item annunciates,
and pressing it jumps to the EMS screen; on the EMS screen the same button reads
`PFD` and takes you back.

![EMS button, normal](../images/ems-gray.png)
![EMS button, alert](../images/ems-red.png)

Because the background can be made transparent, buttons are often laid invisibly
**on top of** a gauge — e.g. trim-up / trim-down buttons over a
`horizontal_bar_gauge` showing trim position:

![Trim pitch buttons over a bar gauge](../images/trim-pitch.png)

**YAML `type:`** `button`

### Adding a button

A button is the one widget whose behavior lives in a **separate config file**.
The screen-builder entry is short; the `options: config:` key points at the
button's YAML file (relative to the config path). **`config:` is required** —
omitting it raises `button must specify options: config:`.

```yaml
- type: button
  row: 70
  column: 75
  span: {rows: 15, columns: 10}
  options:
    config: config/buttons/trim-up-invisible.yaml
```

| Option (on the screen entry) | Default | Meaning |
|--------|---------|---------|
| `config` | *(required)* | path to the button-config YAML file |
| `font_family` | **`DejaVu Sans Condensed`** | passed to the constructor |
| `font_mask` | none | sizing template for the button label |
| `encoder_order` | none | position in the encoder selection order (see [Encoder support](#encoder-support)) |

### The button-config file

Every button-config file must define at least `type:`, `text:` and `dbkey:`.

```yaml
type: simple
text: ""
dbkey: BTN6
```

| Config key | Default | Meaning |
|------------|---------|---------|
| `type` | *(required)* | `simple`, `toggle`, or `repeat` (see below) |
| `text` | *(required)* | initial label; usually overwritten by a `set text:` action |
| `dbkey` | *(required)* | a **boolean** FIX key tied to the button's pressed state; can also be driven by a physical button input. `{id}` in the key is replaced with the screen's `nodeID` so the same config serves multiple displays (e.g. `TSBTN{id}12` → `TSBTN112`) |
| `condition_keys` | `[]` | extra FIX keys this button watches in its conditions (see below) |
| `conditions` | `[]` | the list of `when` / `actions` rules (see below) |
| `bg_color` | `lightgray` | initial background color |
| `fg_color` | `black` | initial foreground (text) color |
| `transparent` | `false` | draw only a border, transparent fill (for overlays) |
| `hover_show` | `false` | on mouse-enter, set FIX key `HIDEBUTTON` false (un-hide a hidden button bar) |
| `repeat_interval` | `300` | (ms) auto-repeat interval — `repeat` type only |
| `repeat_delay` | `300` | (ms) delay before auto-repeat starts — `repeat` type only |

### Button types

`dbkey` must be a boolean and doubles as a physical-button input.

| `type:` | Behavior |
|---------|----------|
| **simple** | momentary pushbutton: fires its actions on press, then returns to the unpressed state. Does not repeat when held. Trigger it by touch/mouse, or by setting `dbkey` to `True`. |
| **toggle** | on/off latch: fires actions on both press and release. Set `dbkey` `True` for on, `False` for off; the button and the key stay in sync. |
| **repeat** | like `simple`, but **repeats** its actions while held down (rates set by `repeat_delay` / `repeat_interval`). |

### Condition keys

`condition_keys` lists the FIX keys (beyond `dbkey`) whose changes should
re-evaluate the button's conditions, and which you may reference as variables.
Conditions are re-evaluated whenever `dbkey` or any `condition_keys` value (or
its quality flags / aux values) changes.

```yaml
type: simple
text: ""
dbkey: BTN6
condition_keys:
  - CHT11
  - CHT12
  - EGT11
  - EGT12
```

### Conditions, `when`, `actions`, `continue`

`conditions:` is an ordered list of rules. Each rule has a `when:` expression;
when it evaluates true, the rule's `actions:` run. **By default, once a rule
matches, evaluation stops** — add `continue: true` to let the following rules be
evaluated as well.

```yaml
conditions:
  - when: "SCREEN eq 'EMS'"
    actions:
      - set text: PFD
      - set bg color: lightgray
    continue: true
  - when: "CHT11 gt 220 or CHT12 gt 220"
    actions:
      - set bg color: red
```

- `when:` is a **string** expression evaluated by the
  [`pycond`](https://github.com/axiros/pycond) library — `eq`, `ne`, `gt`,
  `lt`, `and`, `or` and `[ ]` grouping cover almost everything you need.
- `when:` may also be a **boolean** (`true` / `false`): the actions then run when
  the button's checked state matches that boolean (handy for toggle buttons).

### Variables available in conditions and `set text:`

Inside a `when:` expression — and inside `set text:` via `{NAME}` substitution —
you can reference:

- **`dbkey` and every `condition_keys` key** by name (its current value).
- For any of those keys, the quality flags and aux values:
  `KEY.old`, `KEY.bad`, `KEY.fail`, `KEY.annunciate`, and `KEY.aux.<name>`
  (e.g. `KEY.aux.min`, `KEY.aux.max`).
- Four built-ins:

| Variable | Meaning |
|----------|---------|
| `DBKEY` | the boolean value of this button's `dbkey` (the pressed/released state — most useful on toggle buttons) |
| `CLICKED` | `true` when the evaluation was triggered by a user press; `false` when triggered by a data change. Use it to distinguish user actions from data-driven ones |
| `SCREEN` | the name of the screen the button is on |
| `PREVIOUS_CONDITION` | the boolean result of the previous rule — lets you build an if/else across two rules |

### Actions

Each entry under `actions:` is a single-key map, `action: argument`. Two
families exist: **HMI actions** (system behavior) and **style actions**
(appearance, handled by the button itself). The available HMI actions are:

| Action | Argument | Effect |
|--------|----------|--------|
| `set airspeed mode` | mode | switch the airspeed box between IAS / GS / TAS |
| `set egt mode` | mode | drive the EGT bar gauges (normalize / peak / lean / reset) — see [Engine Gauges → EGT modes](Widgets-Engine-Gauges#egt-modes-engine-leaning) |
| `show screen` | screen name | switch to a named screen |
| `show next screen` | `true` | switch to the next screen |
| `show previous screen` | `true` | switch to the previous screen |
| `set value` | `KEY,value` | write `value` to FIX key `KEY` |
| `change value` | `KEY,delta` | add `delta` to FIX key `KEY` (e.g. `KEY,0.1`) |
| `change value wrap` | `KEY,delta` | add `delta` to FIX key `KEY`, **wrapping** within the key's `min`/`max` range instead of clamping — for circular or cyclic values. A heading bug stepping below 0 wraps to just under 360 (`HEADBUG,-1`); a selector cycles `0 → 1 → 2 → 0` (`NAVSRC,1`) |
| `sync value` | `DEST,SOURCE` | copy FIX key `SOURCE`'s current value into `DEST` — e.g. a push-to-sync that snaps the heading bug to the current heading (`HEADBUG,HEAD`) |
| `toggle bit` | `true` | toggle a boolean FIX value |
| `activate menu item` | index | activate a menu item by number |
| `activate menu` | menu name | open a named menu |
| `menu encoder` | value | drive the menu with an encoder step |
| `set menu focus` | — | move focus into the menu |
| `set instrument units` | — | trigger instrument unit switching |
| `exit` | `true` | exit pyEFIS |
| `evaluate` | expression | evaluate an expression (advanced/escape hatch) |

Style actions (applied to this button's own appearance):

| Action | Argument | Effect |
|--------|----------|--------|
| `set bg color` | `#hex` or a Qt color name | set the background color |
| `set fg color` | `#hex` or a Qt color name | set the text color |
| `set text` | string (with optional `{VAR}`) | set the label; `{NAME}` is substituted from the variables above, e.g. `set text: {CHT11}` |
| `button` | `disable` / `enable` / `checked` / `unchecked` | enable/disable the button, or force its checked state |

> **Anything not recognized as an HMI action falls through to the style
> handler.** That is how `set bg color` / `set text` / `button` work, and it is
> why a typo in an action name silently becomes a style no-op rather than an
> error.

**Avoiding loops.** Do not write an action on a button that changes that same
button's own `dbkey` — use `button: checked` / `button: unchecked` instead.
Avoid action chains where button A triggers button B which acts back on A.
Reordering rules and using `continue` sparingly is how you keep behavior
predictable. Note that **disabling a button does not stop it from evaluating
conditions and firing actions** — it only blocks user clicks; use the `CLICKED`
variable to gate user-initiated behavior.

> A complete, accurate `nodeID` / `{id}` discussion lives in
> [Screen Builder](Screen-Builder); buttons are the main consumer of that
> mechanism.

---

## `listbox`

A scrollable table that presents one or more **user-defined lists** — radio
frequencies, waypoints, anything — and, when the pilot selects a row, **writes
one or more FIX keys**. It also offers built-in rows to switch lists and to sort
(including by distance from the aircraft).

![Listbox](../images/listbox.png)

**YAML `type:`** `listbox`

**FIX keys:** reads `LAT` / `LONG` (for the nearest-location sort); writes
whatever keys each list item's `set:` block names.

### Defining the lists (screen entry)

The screen entry supplies `lists:` (and, for encoder use, `encoder_order:`).
Each entry has a `name` (the title shown at the top and in the list-picker) and a
`file` (the list-definition YAML, relative to the config path). The factory also
accepts the screen-builder `replace:` map, so `{radio_id}`-style placeholders in
the list files are substituted just like in includes.

```yaml
- type: listbox
  row: 0
  column: 101
  span: {rows: 40, columns: 54}
  options:
    encoder_order: 28
    lists:
      - name: Favorites
        file: lists/radio/favorites.yaml
      - name: Ohio
        file: lists/radio/ohio.yaml
```

| Option | Default | Meaning |
|--------|---------|---------|
| `lists` | *(required)* | list of `{name, file}` entries — the lists this box can show |
| `font_family` | **`DejaVu Sans Condensed`** | passed to the constructor |
| `encoder_order` | none | position in the encoder selection order |

When more than one list is defined, the box automatically adds a **Load List**
row so the pilot can switch between them.

### The list-definition file

A list file has two top-level sections: `display` (columns and behavior) and
`list` (the rows).

```yaml
display:
  location: true        # offer a "Sort by: Nearest" row (needs valid LAT/LONG)
  columns:
    - name: Name
      sort: true        # offer a "Sort by: Name" row
    - name: Identifier
      sort: true
    - name: Frequency
      sort: false       # false is the default
list:
  - Name: Knox County
    Identifier: K4I3
    Frequency: 122.800 Mhz
    set:
      COMACTFREQSET{radio_id}: 122800
      COMACTNAMESET{radio_id}: "{Name}"
```

- **`display.columns`** — each column has a single-word `name` (used both as the
  column header and as the key for each row's value) and an optional `sort:`
  flag. The column names you define here are the keys you must supply on every
  row. (`size:` and `show_headers:` appear in older examples but are not
  required.)
- **`display.location: true`** — adds a *Sort by: Nearest* row that sorts the
  list by great-circle distance from the aircraft's current `LAT`/`LONG`. This
  row only appears when the position is valid (not old/bad/fail).
- **`list`** — one map per row. Each must carry a value for every column `name`.

### Sorting

The listbox builds its sort options from the columns: every column with
`sort: true` produces a **Sort by: `<column>`** row at the top of the table, and
`display.location: true` adds **Sort by: Nearest**. Selecting a sort row
re-sorts the list in place (the listbox keeps encoder control — see below).
Text columns sort alphabetically; *Nearest* sorts by geodesic distance, placing
rows without `lat`/`long` last.

### Set-on-select

When a data row is selected, every key in its **`set:`** block is written to the
FIX database (and output). Values may embed `{Column}` placeholders, which are
replaced with that row's displayed cell text:

```yaml
  - Name: John Glenn Int. Tower
    Identifier: KCMH
    Frequency: 132.700 Mhz
    lat: 39.9969467
    long: -82.8921592
    set:
      COMACTFREQSET{radio_id}: 132700
      COMACTNAMESET{radio_id}: "{Name}"
```

- **`lat` / `long`** on a row supply the position for the *Nearest* sort, and can
  also be fed into `set:` (e.g. to send a waypoint to an autopilot).
- You may add **arbitrary keys** to a row that are not columns (so they are not
  displayed) and reference them in `set:`. For example a row with `type: Airport`
  and `set: { WPNAME: "{type} {Name}" }` writes `WPNAME` = `Airport <Name>`.

---

## Encoder support

Both `button` and `listbox` are **encoder-selectable**, so a panel with one
rotary encoder + button can drive them without a touchscreen (see
[Concepts §6](Concepts#6-encoder-interaction)).

- Set **`encoder_order`** on each selectable widget to control the order the
  orange selection highlight visits them. The shipped configs reserve ranges per
  include (e.g. 11–20 for side buttons, 21–30 for radio components).
- A **button** simply fires when selected and pressed; a disabled button is
  skipped (it cannot be selected).
- A **listbox** is unusual: pressing the button hands encoder *control* to the
  box, after which rotating moves the selected row and pressing performs that
  row's action. The listbox **keeps** control while you use its sort / load-list
  rows and only releases it when you select a data item.

Full setup — including the per-screen `encoder` / `encoder_button` keys — is in
[Screen Builder](Screen-Builder#encoder-control).
