# System & Status Widgets

These widgets do **not** display flight or engine data. They surface the health
of the unit's *data* and integrate external software into the panel:

- **`data_status`** and **`data_annunciation`** report the currency of the
  installed navigation data (the navdata / data-pack updater system), and let
  the user run an over-the-air update.
- **`weston`** embeds the Weston Wayland compositor (running waydroid) inside a
  pyEFIS screen so an **Android** app can be shown in a panel region.

Unlike the gauges, none of these read a **FIX key**, share the
[color-state model](Concepts#2-the-color-state-model-gauges), or participate in
the [encoder selection](Concepts#6-encoder-interaction) loop. They follow the
[layout / span rules](Concepts#5-layout-grid-span-move-ganging) like any other
widget, and `font_family` is resolved from [preferences](Preferences-and-Styling)
and passed to the constructor (see [Concepts §8](Concepts#8-how-options-reach-a-widget)).
They are placed on screens the same way — see [Screens Overview](Screens-Overview)
and [Screen Builder](Screen-Builder).

| `type:` | Class | Role |
|---------|-------|------|
| `data_status` | `data_status.DataStatus` | Full-screen navigation-data status & updater (boot screen) |
| `data_annunciation` | `data_status.DataAnnunciation` | Small persistent "DATA" currency flag for the flight view |
| `weston` | `weston.Weston` | Embeds a Weston/waydroid compositor to show an Android app |

---

## The navigation-data status file

`data_status` and `data_annunciation` are two views of the **same** status
file. That file is written by the **`pyefis-data`** updater (makerplane-data
"Phase F"): the tool that downloads and installs the signed data packs
(navigation data, obstacles, terrain, water, roads, charts, …) onto the unit.
pyEFIS only **reads and reflects** this file; it never writes it. Both widgets
read it through the shared `load_status()` helper, which is **defensive by
design** — a missing or malformed file yields a quiet "unavailable" state and
**never raises**, so the status display can never be the thing that stops the
aircraft from booting.

The default path is `~/.makerplane/pyefis/status.json` (constant
`DEFAULT_STATUS_PATH`), overridable per widget via `status_path`.

The status JSON is expected to contain:

- `ok` — whether the file is usable; when false/absent both widgets treat the
  data as "unavailable".
- `generated` — the catalog timestamp (shown as `catalog YYYY-MM-DD`).
- `packs` — a list of installed packs, each with (at least) `id`, `name`,
  `severity`, `status`, and `detail`.

Each pack carries a **severity**, which drives the (deliberately subtle) color:

| `severity` | Meaning | Color |
|------------|---------|-------|
| `amber` | expired / out of window | amber `rgb(255,176,0)` |
| `white` | expiring soon, or missing | off-white `rgb(235,235,235)` |
| `none` | current / healthy | calm green `rgb(120,190,120)` |

Severity ranks `none < white < amber`; the **worst** pack severity decides what
the annunciation shows.

---

## `data_status`

A full-screen, touch-oriented **Data Status** screen, intended to run at boot.
It lists every installed pack with its currency, plus two buttons:

- **Continue** — *always available* (the EFIS informs, it never restricts). It
  triggers the HMI `show screen` action to the `continue_screen` (default
  `PFD`).
- **Update** — runs the `pyefis-data` updater to fetch/install packs
  over-the-air or from a USB drive.

The Update flow is a multi-step wizard driven by sub-commands of the updater:
it first probes `sources --json` (Internet and/or USB), reads the available
packs with `catalog --json`, then presents a touch **pack picker**
(`PackPicker`) grouped by kind — Navigation Data, Water, Roads, Terrain, Charts.
The user can change the install location (`drives --json` → a drive chooser),
then **Install selected** runs `update --only <ids> --progress`, streaming a
per-pack progress bar; the install is cancelable. On success the screen reloads
the (rewritten) status file.

The screen also **auto-refreshes every 60 s** (and on show), so a USB stick
imported by the updater's udev hook, or a background update, appears without any
interaction.

### YAML `type:`

```yaml
type: data_status
```

### Options

These are the factory options forwarded by `build_data_status`
(`screens/screenbuilder_factory.py`); each maps to a `DataStatus.__init__`
argument. `font_family` comes from [preferences](Preferences-and-Styling), not
from `options:`.

| Option | Default | Meaning |
|--------|---------|---------|
| `status_path` | `~/.makerplane/pyefis/status.json` | path to the updater's status JSON to read (`~` is expanded) |
| `continue_screen` | `PFD` | screen name the **Continue** button navigates to (via the HMI `show screen` action) |
| `update_command` | `pyefis-data` | the updater CLI to run for the Update flow. Use an **absolute** or `~`-prefixed path — pyEFIS runs as a systemd service whose minimal `PATH` excludes `~/.local/bin`, so a bare name would fail to start |
| `font_family` | `DejaVu Sans Condensed` | from preferences (not `options:`) |

### Example

From the shipped `datastatus.yaml` screen (condensed). The screen fills the
whole layout; to show it at boot, add it to your screen set and set
`defaultScreen: DataStatus` in the main config.

```yaml
DataStatus:
  module: pyefis.screens.screenbuilder
  title: Data Status
  layout:
    rows: 100
    columns: 100
  instruments:
    - type: data_status
      row: 0
      column: 0
      span:
        rows: 100
        columns: 100
      options:
        continue_screen: PFD
        update_command: ~/.local/bin/pyefis-data
        # status_path defaults to ~/.makerplane/pyefis/status.json
```

### Notes

- **Touch-first.** The pack picker uses full-width row touch targets and a
  tap-vs-scroll heuristic (tap toggles on release if the finger hasn't moved;
  two-finger drag scrolls without toggling) tuned for the eglfs touchscreen.
- **Never fatal.** If the file is missing/unreadable it shows
  "Data status unavailable — run an update to populate it." If the updater
  binary can't even start, it shows "Updater unavailable on this device." and
  returns to the status view — it never blocks.
- **Cancel-safe install.** Canceling a download SIGTERMs the updater (with a
  hard-kill fallback); the previously installed data is left untouched
  (verify-then-atomic-swap), and the picker selection is preserved.
- This widget is **not encoder-selectable**; its buttons and rows are operated
  by touch (mouse).

---

## `data_annunciation`

A small, persistent **"DATA"** flag for the flight (PFD) view. It draws a
rounded box labeled `DATA` in the worst pack's severity color, and — by design —
shows **nothing at all** when everything is current (or when there is no updater
/ status file), so a healthy display is never cluttered. Tapping it triggers the
HMI `show screen` action to jump to the Data Status screen.

Like `data_status`, it reloads the status file on show and **every 60 s**.

### YAML `type:`

```yaml
type: data_annunciation
```

### Options

Forwarded by `build_data_annunciation`:

| Option | Default | Meaning |
|--------|---------|---------|
| `status_path` | `~/.makerplane/pyefis/status.json` | path to the updater's status JSON to read (`~` is expanded) |
| `target_screen` | `DataStatus` | screen name a **tap** navigates to (via the HMI `show screen` action) |
| `font_family` | `DejaVu Sans Condensed` | from preferences (not `options:`) |

### Example

From `pfd_ai_only.yaml` (also used the same way in `pfd.yaml`):

```yaml
- type: data_annunciation
  row: 2
  column: 2
  span:
    rows: 5
    columns: 18
  options:
    target_screen: DataStatus
```

### Notes

- It is **hidden** (paints nothing) at severity `none` — that is the healthy
  state. You will only see it when navdata is expired (amber) or expiring
  soon / missing (white).
- Pair `target_screen` here with the `continue_screen` on the matching
  `data_status` widget so tap-in / Continue-out land on the right screens.

---

## `weston`

`weston` embeds the **Weston Wayland compositor** as a child window inside a
pyEFIS screen region, so an **Android** application (run under **waydroid**) can
be shown in a panel — for example a moving-map or radio app alongside the EFIS
instruments. It launches the `weston` binary with the X11 backend
(`-Bx11-backend.so`), finds the resulting "Weston Compositor" X11 window, and
reparents it into a Qt window container that fills the widget's layout.

### YAML `type:`

```yaml
type: weston
```

### Options

`build_weston` reads these from `options:` and passes them to
`Weston.__init__`. The `ini` path is resolved relative to the screen's config
directory. `wide`/`high` are **computed** by the factory from the widget's
`span` (in grid cells), not set by hand.

| Option | Required | Meaning |
|--------|----------|---------|
| `socket` | yes | Wayland socket name for this compositor (passed as `weston -S<socket>`). Use a distinct name per `weston` widget |
| `ini` | yes | Weston config file, resolved relative to the screen's config directory (passed as `weston -c<ini>`) |
| `command` | yes (in YAML) | the program to display (e.g. `waydroid`). **See the caveat below** |
| `args` | yes (in YAML) | argument list for `command` (e.g. `[show-full-ui]`). **See the caveat below** |
| `wide` / `high` | computed | width/height in pixels, derived from the widget's `span` × the screen grid cell size; used to start Weston at the exact panel size in `--fullscreen` mode (this avoids waydroid mis-sizing artifacts). Do not set these in YAML |

> **Caveat — `command` / `args` are accepted but not used by the widget in the
> current source.** `build_weston` forwards `command` and `args` to
> `Weston.__init__`, and the constructor accepts them, but its body only starts
> the `weston` compositor (with `socket`, `ini`, and the computed
> `wide`/`high`). It does **not** itself launch `command`/`args`. The Android
> app named by `command:` (e.g. `waydroid show-full-ui`) must therefore be
> started by some other mechanism on the unit; the shipped screens still
> specify `command`/`args`, so treat them as required-by-config but verify how
> the app is actually launched on your device.

### Example

From the shipped `android.yaml`:

```yaml
- type: weston
  row: 0
  column: 0
  span:
    rows: 100
    columns: 155
  options:
    socket: pyefis-waydroid-1
    ini: weston.ini
    command: waydroid
    args:
      - show-full-ui
```

### Notes / constraints

- **Linux / Wayland / X11 only.** The widget relies on the `weston` binary, an
  X11 server (it uses `xwininfo` to locate the compositor window and the
  `python-xlib` `Xlib` package to reparent it), and waydroid. On platforms
  without these (e.g. Windows development machines) it cannot run — `Xlib` is
  imported defensively and is simply `None` when unavailable. The widget is
  intended for the on-target (Raspberry Pi / Linux) build.
- **Window discovery is best-effort.** After starting Weston it polls
  `xwininfo` up to ~15 times (~70 ms apart) for the "Weston Compositor" window.
  If the window never appears (compositor failed to start, wrong backend), the
  embed silently does not happen.
- **Clean shutdown.** Closing the widget terminates the Weston process
  gracefully (with a hard-kill fallback) so it does not leak a compositor.
- This widget reads no FIX key and is not encoder-selectable.
