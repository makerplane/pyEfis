# Pilot's Guide

This guide is for **operating** a pyEFIS display in the cockpit — what the
screens show, what the colors mean, and how to work the controls. It assumes a
build using the shipped screens; your installer may have customized it (see
[Screens Overview](Screens-Overview)).

> **Advisory use.** pyEFIS is an experimental/advisory display. Use it alongside
> your aircraft's required instruments, not in place of them. It shows what
> fix-gateway feeds it; if a sensor is lost, pyEFIS flags it (see
> [Indications & alerts](#indications--alerts)) but cannot invent data.

---

## The screens at a glance

pyEFIS presents several full-screen layouts you move between with on-screen
buttons. The shipped set:

| Screen | What it's for |
|--------|---------------|
| **Data Status** | Navdata currency / updates (the boot screen) |
| **PFD** | Primary flight display: attitude/synthetic vision + flight tapes + a slim engine column |
| **AI-only PFD** | Full-width attitude/synthetic vision, no engine strip |
| **EMS** | Engine monitoring: flight bundle + full engine instruments |
| **EMS2** | Engine-only monitoring (no attitude) |
| **Six-Pack** | The traditional round-gauge six instruments |
| **Radio** | Com radio control |
| **Android** | An embedded Android app panel (if enabled) |

Full contents of each are in [Screens Overview](Screens-Overview).

---

## Reading the PFD

The PFD combines the classic "T" with synthetic vision:

- **Attitude / Synthetic Vision** fills the center — pitch ladder and bank
  pointer over either a two-tone sky/ground or, when enabled and supported,
  **terrain, water, runways, and obstacles** drawn from the aircraft's position
  (see [Attitude & SVS](Widgets-Attitude-and-SVS)). A **flight-path marker** (if
  fed) shows where the aircraft is actually going.
- **Airspeed tape** (left) — your indicated airspeed, with colored bands for the
  V-speeds (white flap arc, green normal, yellow caution, red Vne) taken from
  the aircraft's configured speeds. A TAS readout and a short **trend arrow**
  (projected speed a few seconds ahead) may appear.
- **Altimeter tape** (right) — indicated altitude, with the **barometric
  setting** shown nearby (see [Setting the altimeter](#setting-the-altimeter-baro)).
- **VSI** — vertical speed, as a tape/pointer beside the altimeter.
- **Heading** — a heading tape or card across the top/bottom.
- **HSI** — course pointer with **CDI** (course deviation) and, on an approach,
  the **glideslope** diamond.
- **Slip/skid** — the inclinometer "ball" (also the standalone turn coordinator
  on the Six-Pack).
- **Wind** — a compact headwind/crosswind readout (if enabled): `HW`/`TW` for
  head/tailwind, `RX`/`LX` for crosswind from the right/left.

---

## Indications & alerts

pyEFIS uses a consistent visual language across every gauge and readout.

**Operating-range bands** (engine gauges, airspeed): **green** = normal,
**yellow** = caution, **red** = exceedance. These thresholds come from each
value's limits, set in fix-gateway — not from the display.

**Data quality** — every value can independently signal its health:

| You see… | It means | What to do |
|----------|----------|------------|
| Normal bright value | Live, trusted | — |
| **Dimmed / grayed** value | The value is **stale (old)** or flagged **bad** | Treat as suspect; cross-check |
| **`X` / `XXX`** in place of digits, or value drops to zero | The source has **failed** | Don't trust it; use backup instruments |
| **Red** number/text | **Annunciation** — attention requested for that item | Investigate the item |
| Wind shows an amber **`X`** or dim **`---`** | Wind components are bad / not available | Disregard wind |

**Screen-change buttons annunciate too:** while you're on the PFD, the **EMS**
button turns **red** if an engine parameter (EGT/CHT, etc.) goes into alert —
your cue to jump to the engine screen.

**The DATA flag:** a small **DATA** annunciator appears only when your navdata
(terrain/airport/obstacle packs) is out of date or missing. Tap it to open the
[Data Status](#data-currency--updates) screen. When everything is current, the
flag is hidden.

---

## Moving between screens

Each screen carries a **bar of buttons** (along a side or edge) that jump to the
other screens — PFD, EMS, EMS2, Six-Pack, Radio, (Android), and Units. The
button for the screen you're on flips to take you back to the PFD, so it's
always one press home.

These can be **touchscreen** buttons, **physical** buttons wired to the same FIX
keys, or driven by a **rotary encoder**:

- **Encoder (if equipped):** rotate to move an **orange** highlight to a button
  or instrument; press to activate it (or to start editing a selected value);
  press again to confirm; stop touching it and it times out back to normal.

### Hiding the buttons

The **Units / Show Menu** button doubles as a menu toggle. When the buttons are
hidden (for an uncluttered view), this button reads **"Show Menu"**; press it to
bring the bar back. (Under the hood it toggles the `HIDEBUTTON` key.)

---

## Common in-flight adjustments

### Setting the altimeter (baro)

The altimeter has **+ / −** buttons (often invisible regions near the baro
setting) that step the barometric setting `BARO` by 0.01 inHg. They **repeat**
if held.

### Display brightness (dimmer)

**+ / −** dimmer buttons step the display brightness (`DIM`) and repeat when
held — for day/night and changing light.

### Units

The **Units** button toggles units for temperature (**°C ⇄ °F**), pressure
(**inHg ⇄ hPa**), and altitude (**ft ⇄ m**) on the instruments configured for
switching (e.g. OAT, oil temperature). One press flips all of them together.

### Airspeed source

The airspeed **box** can switch what speed it shows — **IAS / GS / TAS** —
so you can read groundspeed or true airspeed without leaving the PFD.

---

## Engine monitoring & leaning

The **EMS** (and **EMS2**) screens show the full engine picture: RPM, manifold
pressure, oil temperature/pressure, fuel, electrical, and the per-cylinder
**EGT** and **CHT** strips (vertical bars). The hottest cylinder is highlighted.

For fuel-injected/leaning work, the EGT strip has **mode buttons**:

| Button | What it does |
|--------|--------------|
| **Normal** | Absolute EGT against the gauge range (default) |
| **Peak** | Tracks each cylinder's peak; once a cylinder falls past peak it shows **how far below peak** it is — find peak and set rich/lean of it |
| **Normalize** | Re-centers all cylinders to a common reference so you can compare them directly |
| **Lean** | Shortcut: reset peak + normalize + peak together, the usual leaning view |
| **Reset Peak** | Clears the stored peaks to start a new lean |

These are mutually-managed — selecting one clears the others — and the active
button highlights green. (Engineering detail:
[Engine & Data Gauges → EGT modes](Widgets-Engine-Gauges#egt-modes-engine-leaning).)

---

## Trim (if equipped)

If your installer enabled trim controls, the PFD shows **trim position** (pitch,
and optionally roll/yaw) with **+/−** buttons to drive it. These are off by
default and only appear when configured for your aircraft's trim axes.

---

## Data currency & updates

The **Data Status** screen (shown at boot) lists your installed navigation-data
packs — terrain, airports, obstacles, water — and their currency, color-coded.
From here:

- **Continue** proceeds to the flight display.
- **Update** runs the data updater (downloads/installs newer packs, with a
  progress bar) — typically done on the ground with connectivity.

In flight, the small **DATA** flag (above) is your reminder if anything is out
of date.

---

## If something looks wrong

- **A value is gray/dim or shows `X`** — that source is stale or failed; it is
  *not* a display fault. Check the sensor/feed (fix-gateway).
- **Terrain/airports look off or missing** — the synthetic-vision picture
  depends on current data packs (see Data Status) and only draws a forward arc;
  features behind or beside you aren't shown. SVS is advisory terrain awareness,
  **not** a terrain-clearance instrument.
- **Buttons disappeared** — press the **Show Menu** button to bring them back.
