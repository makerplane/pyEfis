# pyEFIS Manual

pyEFIS is the open-source **Python EFIS** (Electronic Flight Instrument System)
for the [MakerPlane](https://makerplane.org) open-source aircraft project. It is
a PyQt6 cockpit display that renders configurable **screens** built from
**widgets** (instruments), driven by live flight/engine data from a companion
**fix-gateway** process.

This manual has two halves:

- **Engineering reference** — what every widget is, all its options, the data
  it consumes, and how screens/preferences are assembled. For builders,
  integrators, and contributors.
- **Pilot's guide** — what the shipped screens show and how to operate the
  display in the cockpit. For end users.

> This manual is generated and maintained from the pyEFIS source tree under
> `docs/wiki/` and mirrored to this wiki. See
> [Contributing to these docs](#maintaining-this-manual).

---

## How pyEFIS fits together

```
   sensors / GPS / engine            fix-gateway              pyEFIS
   ──────────────────────  →   ┌──────────────────┐   →   ┌─────────────────┐
   ADAHRS, EMS, GPS, radios    │  FIX database    │  TCP  │  screens of     │
   (CAN-FIX, NMEA, X-Plane…)   │  (keys: IAS,ALT, │       │  widgets draw   │
                               │   TACH1, COURSE…)│       │  the FIX keys   │
                               └──────────────────┘       └─────────────────┘
```

pyEFIS **only displays** — it reads named values ("FIX keys") and paints them.
The mapping of sensors→keys is fix-gateway's job. Understand the
[FIX database](Concepts#1-the-fix-database-the-data-bus) and the rest follows.

---

## Start here

| If you want to… | Read |
|-----------------|------|
| Understand the shared vocabulary (FIX keys, colors, fonts, layout) | **[Concepts](Concepts)** |
| Run pyEFIS from a source checkout (developers) | **[Running from Source](Running-from-Source)** |
| Lay out or edit a screen in YAML | **[Screen Builder](Screen-Builder)** |
| Look up a specific widget and its options | **[Widget Reference](Widget-Reference)** |
| Customize the shipped screens without rewriting them | **[Preferences & Styling](Preferences-and-Styling)** |
| Operate the display as a pilot | **[Pilot's Guide](Pilots-Guide)** |

## Widget reference

All ~27 widget types, grouped by role. Every page documents the YAML `type:`,
the FIX keys consumed, and a source-extracted option table.

- **[Flight instruments](Widgets-Flight-Instruments)** — airspeed, altimeter,
  VSI, heading, HSI, turn coordinator, wind.
- **[Attitude & Synthetic Vision](Widgets-Attitude-and-SVS)** — the attitude
  indicator (AI) and Virtual VFR / SVS terrain.
- **[Engine & data gauges](Widgets-Engine-Gauges)** — arc, vertical/horizontal
  bar, numeric display (and their `ganged_` strips).
- **[Text & interactive](Widgets-Text-and-Interactive)** — static text, value
  text, buttons, listbox.
- **[System & status](Widgets-System)** — data status, data annunciation,
  weston (Android).
- **[FIX database keys](FIX-Database-Keys)** — the glossary of keys each widget
  reads/writes.

## Screens & configurations

- **[Screens Overview](Screens-Overview)** — the shipped layouts (PFD, EMS,
  EMS2, Six-Pack, Radio, Android, AI-only, Data-Status) and how the active set
  is chosen.

---

## Maintaining this manual

The canonical source lives in the code repo at **`docs/wiki/`** (one `.md` per
wiki page, GitHub-wiki naming). Images live in `docs/images/`. To publish
changes to the GitHub wiki, run the mirror tool described in
[`docs/wiki-publishing.md`](https://github.com/billmallard/pyEfis/blob/gpu-required/docs/wiki-publishing.md)
and push the wiki clone. Do not edit wiki pages directly in the GitHub UI —
they will be overwritten on the next mirror.
