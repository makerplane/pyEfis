# FIX Database Keys

pyEFIS draws **FIX keys** — named values in the in-memory FIX database fed by
fix-gateway. This page is a glossary of the keys the shipped widgets consume.
See [Concepts §1](Concepts#1-the-fix-database-the-data-bus) for how keys,
quality flags, and aux values work.

> **Canonical source:** the master registry of keys, their types, and their
> CAN-FIX parameter IDs lives in **fix-gateway / CAN-FIX**, not in pyEFIS.
> pyEFIS only *reads* keys. Keys, ranges, and units below reflect how the
> shipped pyEFIS configs and the test mock database define them; your
> fix-gateway may add more.

## Air data

| Key | Units | Meaning | Read by |
|-----|-------|---------|---------|
| `IAS` | knots | Indicated airspeed (carries V-speed aux values) | airspeed widgets |
| `TAS` | knots | True airspeed | `airspeed_box`, `airspeed_tape` (TAS box), AI |
| `GS` | knots | Ground speed | `airspeed_box` |
| `ALT` | ft | Indicated/baro altitude | altimeter widgets |
| `VS` | ft/min | Vertical speed | `vsi_*`, `altimeter_trend_tape` |
| `BARO` | inHg | Altimeter setting (Kollsman) | altimeter, baro buttons |
| `OAT` / `CAT` | °C | Outside / calibrated air temp | EMS gauges |

**`IAS` aux values** (V-speeds, drive the airspeed-tape color bands):
`Vs`, `Vs0`, `Vno`, `Vne`, `Vfe`, `Va`, `Vx`, `Vy`, `Vmc`, `V1`, `V2`.

## Attitude & inertial

| Key | Units | Meaning | Read by |
|-----|-------|---------|---------|
| `PITCH` | deg | Pitch angle | AI, `virtual_vfr` |
| `ROLL` | deg | Roll/bank angle | AI, `virtual_vfr` |
| `ALAT` | g | Lateral acceleration (slip/skid ball) | AI, `turn_coordinator` |
| `ROT` | deg/s | Rate of turn | `turn_coordinator` |

## Navigation & position

| Key | Units | Meaning | Read by |
|-----|-------|---------|---------|
| `HEAD` | deg | Magnetic heading | `heading_display`, `heading_tape`, HSI |
| `HEADBUG` | deg | Selected heading bug | HSI heading bug, `value_text` |
| `TRACK` | deg | GPS ground track | AI flight-path marker |
| `COURSE` | deg | Selected course (of the selected nav source) | HSI, `virtual_vfr` heading source |
| `CDI` | −1..1 | Course deviation (of the selected nav source) | HSI |
| `GSI` | −1..1 | Glideslope deviation (of the selected nav source) | HSI |
| `NAVSRC` | — | Selected nav source: `0`=GPS, `1`=NAV1, `2`=NAV2 | source-select button (writes it); HSI reads `COURSE`/`CDI`/`GSI` |
| `LAT` / `LONG` | deg | Position | `virtual_vfr` / SVS |
| `HWIND` | knots | Headwind component (− = tailwind) | `wind_display` |
| `XWIND` | knots | Crosswind component (+ = from right) | `wind_display` |

> **Nav-source selection.** `COURSE` / `CDI` / `GSI` are *canonical* keys that
> always carry whichever source the pilot has selected with `NAVSRC`. The
> per-source values (GPS vs NAV1 vs NAV2 course/deviation) live in **fix-gateway**
> (keys like `GPSCRS`, `NAV1CDI`, …); its `compute` plugin's `select` function
> routes the chosen one into `COURSE`/`CDI`/`GSI`. pyEFIS only reads the canonical
> keys — bind the HSI to those, and a `value_text` to `NAVSRC` (or a button that
> cycles it) for the source annunciation. A button using
> [`change value wrap`](Widgets-Text-and-Interactive#actions) on `NAVSRC` cycles
> the source.

## Engine / EMS (representative)

These are bound to gauges through [Preferences](Preferences-and-Styling)
(`gauges:` slots like `ARC1`, `BAR15`) and the EMS includes. Exact names/IDs
come from fix-gateway/CAN-FIX; the shipped example configs use:

| Key | Meaning |
|-----|---------|
| `TACH1` | Engine RPM |
| `OILP1` / `OILT1` | Oil pressure / temperature |
| `EGT11`–`EGT14` | Exhaust gas temp per cylinder; `EGTMAX1` = hottest |
| `CHT11`–`CHT14` | Cylinder head temp per cylinder; `CHTMAX1` = hottest |
| `FUELP1` / `FUELF1` | Fuel pressure / flow |
| `FUELQT` / `FUELQ1`–`FUELQ3` | Fuel quantity (total / tanks) |
| `VOLT` / `CURRNT` | Bus voltage / current |
| `HTOT1` | (engine health/aux, per config) |

Each engine key supplies its green/yellow/red bands via its **aux values**
(`Min`/`Max`/`lowWarn`/`lowAlarm`/`highWarn`/`highAlarm`) — see
[Concepts §2](Concepts#2-the-color-state-model-gauges).

## System / UI

| Key | Type | Meaning |
|-----|------|---------|
| `TSBTN<node><n>` | bool | Touchscreen button (node-scoped, e.g. `TSBTN112`) |
| `BTN<n>` / `ENC<n>` | bool / int | Physical button / rotary encoder inputs |
| `HIDEBUTTON` | bool | Hide/show on-screen buttons (menu timeout) |
| `MAVREQADJ`, `MAVADJ`, `MAVSTATE`, `MAVMODE` | mixed | MAVLink/autopilot request & state keys (trim/AP) |

## A note on quality flags

Every key carries `old` / `bad` / `fail` / `annunciate` flags independent of its
value (see [Concepts §3](Concepts#3-data-quality--states)). Buttons can read any
of these in conditions as `KEY.old`, `KEY.bad`, `KEY.fail`, `KEY.annunciate`,
and aux values as `KEY.aux.<name>` — see
[Widgets-Text-and-Interactive](Widgets-Text-and-Interactive).
