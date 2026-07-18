# Preferences & Styling

The shipped screens are deliberately parameterised so you can adapt them to your
aircraft **without editing the screen configs**. One place — your
`preferences.yaml.custom` — controls visual styles, which gauge shows what,
which features are on, and which include files fill named slots.

The goal: spend your time *flying* pyEFIS, not *tinkering* with it.

> See also [Screen Builder](Screen-Builder) for layout and
> [Widget Reference](Widget-Reference) for per-widget options.

---

## `preferences.yaml` and `preferences.yaml.custom`

`preferences.yaml` ships the defaults. **Do not edit it** — put your changes in
`preferences.yaml.custom`. The effective preferences are the two **merged**,
with your `.custom` overriding any conflicts. Upgrades replace
`preferences.yaml` but leave your `.custom` intact.

The file has four sections: `style`/`styles`, `gauges`, `enabled`, and
`includes`.

---

## `style` and `styles`

`style` selects which named visual theme(s) are active; you can stack several:

```yaml
style:
  - basic
  - segmented
```

`styles` defines those themes, **per gauge family**. The family names match the
gauge types with the trailing number stripped — the built-ins are `ARC`, `BAR`,
and `TEXT` (you can invent your own):

```yaml
styles:
  ARC:
    basic:
      # settings applied to all ARC gauges under the "basic" style
    segmented:
      segments: 10
  BAR:
    segmented:
      segments: 14
```

So selecting the `segmented` style turns every arc/bar gauge into its segmented
look in one move. The settings inside a style are ordinary widget options (see
[Widget Reference](Widget-Reference)).

---

## `gauges`

The `gauges` section does two jobs.

**1. Bind a logical gauge slot to a key/name/options.** The shipped screens
reference slots like `ARC1`, `BAR15` rather than hard-coding keys, so you
re-purpose a gauge in one place. Default:

```yaml
gauges:
  ARC1:
    name: RPM
    dbkey: TACH1
    decimal_places: 0
    temperature: false
    show_units: false
```

Override it in your `.custom` to make `ARC1` show, say, max EGT instead:

```yaml
gauges:
  ARC1:
    name: MAX EGT
    dbkey: EGTMAX1
    temperature: true
    show_units: true
```

**2. Per-gauge style overrides.** A single slot can tweak a style — e.g. the
radio aux-volume bar uses more segments than the family default:

```yaml
gauges:
  BAR32:
    styles:
      segmented:
        segments: 22
```

---

## `enabled`

Feature toggles. A screen-builder instrument may set `disabled:` to a **string**
rather than a boolean; that string is looked up in `enabled` to get the real
on/off value. `not FLAG` inverts (handy to turn one thing on and another off
from a single flag).

Example — the CHT/EGT includes gate each cylinder on a `CYLINDER_n` flag:

```yaml
# in includes/bars/vertical/4_CHT.yaml
        instruments:
          - preferences: BAR15
            options:
              disabled: CYLINDER_1
```

So a two-cylinder engine just sets:

```yaml
enabled:
  CYLINDER_1: true
  CYLINDER_2: true
  CYLINDER_3: false
  CYLINDER_4: false
```

…and the EGT/CHT strips show two cylinders. The same pattern gates optional
clusters like trim controls:

```yaml
enabled:
  TRIM_CONTROLS: true
  PITCH_TRIM: true
  YAW_TRIM: false
  ROLL_TRIM: false
```

Toggles also gate **opt-in widgets** — e.g. `wind_display` is skipped entirely
unless `WIND_DISPLAY: true`, so no error occurs if `HWIND`/`XWIND` aren't in the
FIX database.

---

## `includes`

The `includes` section maps a **named slot** to an actual include file, so a
cluster used across many screens can be swapped in one place instead of editing
each screen. This is also how the top-level config resolves its big sections.

```yaml
includes:
  BUTTON_GROUP1: includes/buttons/vertical/screen_changing_PFD-EMS-EMS2-ANDROID-RADIO-SIXPACK-Units.yaml
  SCREENS_CONFIG: screens/default_list.yaml
  MAIN_CONFIG:    main/default.yaml
```

When a config says `include: SCREENS_CONFIG` (as `default.yaml` does for its
`screens:` section), the loader (`screenbuilder_config.load_include_config`)
first tries the literal path, then falls back to this `includes` map. That means
you can change the **whole set of loaded screens** by pointing `SCREENS_CONFIG`
at a different list file, or swap every screen's side button-bar by repointing
`BUTTON_GROUP1` — without touching a screen config.

To change which screens load and the default screen, see
[Screens Overview](Screens-Overview).

---

## Putting it together

A typical `preferences.yaml.custom` for a real aircraft might:

1. Pick a `style` (e.g. `segmented`).
2. Re-bind a few `gauges` slots to the keys your fix-gateway actually publishes.
3. Set `enabled` flags for your cylinder count, trim axes, and optional widgets.
4. Repoint an `includes` slot if you want a different button bar or screen set.

Everything else — the screen layouts themselves — you leave alone.
