# Airspeed Tape Widget Specification

Standards-grounded spec for the **moving-scale (linear tape) airspeed display**, focused
on **markings, low/high-speed awareness cues, colour, and failure annunciation**.
Companion to [`avionics_reference.md`](avionics_reference.md) (the standards basis, §6)
and the sibling instrument specs ([`hsi_widget_spec.md`](hsi_widget_spec.md),
[`ai_widget_spec.md`](ai_widget_spec.md)). Scope is the **`Airspeed_Tape`** class in
`instruments/airspeed/__init__.py`; the round-dial `Airspeed` and the `Airspeed_Box` are
secondary and share the V-speed data contract below.

## 1. Purpose

Airspeed is primary flight information. On a **moving-scale** tape the present value sits
under a fixed pointer, so — unlike a round dial — the display gives *no inherent sense of
where the present speed sits relative to the low- and high-speed limits* (AC 23.1311-1C
§17.6). The standard therefore **requires** explicit low-speed and high-speed awareness
cues on part 23 tapes (§17.7): a red band from VSO down to zero, and a red band from VNE
up to the top of the tape. Loss-of-airspeed-awareness stalls remain a top-five fatal
accident cause for part 23 airplanes (§17.7.3.a), so these cues are the point of the
instrument, not decoration. This spec holds the tape to that bar and tracks the gaps.

## 2. Current state (implemented)

`Airspeed_Tape` (a `QGraphicsView`; the scale is a tall `QGraphicsScene` scrolled under a
fixed pointer). Already present:

- **Moving-scale tape** with major/minor tick marks + numeric labels, a **fixed pointer**
  (index triangle) and a **digital IAS read-out** (`NumericalDisplay`) — the §17.6 format.
- **Conventional arcs** (§23.1545 markings): **green** VS0→VNO, **white** flap arc
  VS0→VFE, **yellow** caution arc VNO→VNE, and a thin **red VNE line**.
- **V-speeds** from the `IAS` FIX item aux values (`Vs`, `Vs0`, `Vno`, `Vne`, `Vfe`), with
  safe defaults when unset (notably `Vne` defaults to 200; tape top `max = Vne * 1.25`).
- **Failure annunciation** on the read-out: `fail` → `XXX`, `old`/`bad` → blank
  (`NumericalDisplay` colour/text), driven by the standard FIX signals.
- **TAS box** and a **trend vector** (speed-trend look-ahead), both quality-aware.

## 3. Data contract

| Key / aux | Use | Source | Notes |
|-----------|-----|--------|-------|
| `IAS` (value) | present indicated airspeed → pointer + read-out | ADC | primary |
| `IAS` aux `Vs0` | **VSO** — stall, landing config; bottom of the low-speed red band | AFM / config | |
| `IAS` aux `Vs` | **VS1** — stall, clean; green-arc bottom, optional-yellow top | AFM / config | |
| `IAS` aux `Vno` | **VNO** — max structural cruise; green→yellow boundary | AFM / config | |
| `IAS` aux `Vne` | **VNE** — never-exceed; caution→red, top red band bottom | AFM / config | |
| `IAS` aux `Vfe` | **VFE** — max flap-extended; white arc top | AFM / config | |
| `TAS` | true-airspeed box | ADC | quality-aware |
| **`Vmo`** | **VMO variant (§17.7.2)** — not published; out of scope | ADC (future) | no aux key |

**V-speeds are FIX-database values, not layout options (#64)** — the tape is a
display-layer consumer; the cues are drawn from whatever the aux values say. Quality
(`old`/`bad`/`fail`) is tracked on the `IAS`/`TAS` items per the widget convention.

## 4. Markings, awareness cues, and annunciation (requirements)

Standards basis: AC 23.1311-1C **§17.6–17.7** (moving-scale awareness cues, p.40),
**§17.7.1 / Figure 2** (VNE-airplane cues, p.40–41), **§22.2 Table 4** (colour, p.45),
referencing **§§23.1311(a)(6), 23.1545**; consolidated in `avionics_reference.md` §6.

**Governing rule.** A moving-scale airspeed tape must give **quick-glance low- and
high-speed awareness** — the pilot must see the present speed's relationship to the stall
and never-exceed limits without reading the number. Green/white arcs alone are *not*
equivalent on a tape (§17.7.a). IDs (`AS-<CLASS>-<NNN>`) are stable and anchor the test
catalog (§5). **Status** is the widget as of this writing.

| ID | Requirement | Trigger | Required response | Cite | Status |
|----|-------------|---------|-------------------|------|--------|
| **AS-DISP-001** | Moving-scale tape: scrolling scale, fixed pointer, digital read-out | always | Present-value read-out + fixed index over a moving scale | §17.6 p.40 | **DONE** |
| **AS-MARK-001** | Conventional V-speed arcs | always | White VS0→VFE, green VS0/VS1→VNO, yellow VNO→VNE arcs | §23.1545; §22.2 Table 4 | **DONE** |
| **AS-ANN-001** | Airspeed-invalid annunciation | `IAS` fail / old / bad | Read-out `XXX` on fail; blank (not a stale number) on old/bad | §18; §2 governing principle | **DONE** |
| **AS-LSA-001** | **Low-speed red band VSO→0** | always (optional takeoff inhibit) | Red band from VSO down to zero — low-speed awareness (not a limit) | §17.7.1.a p.40–41 (Fig 2) | **DONE** — `low_speed_band` |
| **AS-HSA-001** | **High-speed red band VNE→top** | always | Red band (or barber pole) from VNE up to the top of the tape — not merely a hairline radial | §17.7.1.b p.40–41 (Fig 2) | **DONE** — `high_speed_band` |
| **AS-LSA-002** | *(optional)* yellow band VSO→VS1 | always | Yellow low-speed band | §17.7.1.c p.41 | **OPTIONAL — not planned** (discouraged as clutter) |
| **AS-VMO-001** | VMO-airplane red band VMO→top | always | Red band from VMO up | §17.7.2 p.42 | **N/A — out of scope** (no `Vmo` key; MakerPlane is a VNE airplane) |

**Contract for the gap cues.** After `resizeEvent`, `Airspeed_Tape` shall expose the two
awareness bands as scene items so they are drawable *and* verifiable:

- `self.low_speed_band` — a red-filled `QGraphicsRectItem` spanning scene-y from `VSO` to
  `0` (i.e. `y(Vs0) … y(0)`), or `None` when V-speeds are unavailable / the takeoff
  inhibit is active. (AS-LSA-001)
- `self.high_speed_band` — a red-filled `QGraphicsRectItem` spanning scene-y from `VNE` to
  the tape top (`y(Vne) … 0`), or `None` when unavailable. (AS-HSA-001)

Scene-y mapping is the tape's own `y(v) = -v * pph + tape_start`,
`tape_start = max * pph + h/2`. Bands sit *behind* the tick labels/pointer (painter
order / low z) so the numbers stay legible (§22.6 — colour is not the sole cue; the band
**position** carries the meaning). The bands are **awareness cues, not limits** (§17.7
Note): they change no behaviour, they only inform.

## 5. Test cases

The executable catalog is in
[`tests/instruments/airspeed/test_airspeed.py`](../tests/instruments/airspeed/test_airspeed.py),
keyed to the §4 IDs. Passing tests verify shipped behaviour; the `xfail(strict)` tests are
the **gap tracker** — each flips the run red when its cue is implemented, forcing the
marker's removal.

| AS-TC | Requirement | Test (`test_as_cat_…`) | Status |
|-------|-------------|------------------------|--------|
| 001 | AS-DISP-001 | `moving_scale_tape_format` | pass |
| 002 | AS-MARK-001 | `conventional_vspeed_arcs` | pass |
| 003 | AS-ANN-001 | `airspeed_invalid_annunciation` | pass |
| 101 | **AS-LSA-001** | `low_speed_red_band` | pass |
| 102 | **AS-HSA-001** | `high_speed_red_band` | pass |

## 6. Conventions and standards basis

Symbology is industry convention grounded in open references: **AC 23.1311-1C** (Electronic
Displays for Part 23) §17 symbology, §18 annunciation, §22 colour; **§§23.1311(a)(6),
23.1545** (airspeed limitation markings); cross-checked against **AC 25-11B** Table 5-1
colour. Consolidated + page-cited in [`avionics_reference.md`](avionics_reference.md) §6.
Match the *conventions* (unprotected, a safety benefit); never copy a vendor's *expression*.

## 7. Open items

- **Takeoff inhibit (§17.7.a):** the low-speed red arc *should not* display during takeoff.
  Deferred — needs a phase-of-flight signal (weight-on-wheels / a takeoff mode) the stack
  does not publish yet; record as a follow-up so the band can be suppressed on the ground.
- **Green-arc bottom:** the tape currently draws the green arc from **VS0**; §23.1545 puts
  the green (normal-operating) arc bottom at **VS1** (`Vs`). Minor deviation — confirm and
  align when the bands land (the white flap arc already runs VS0→VFE).
- V-speed values are FIX-DB (#64); they belong to fix-gateway/config, not the editor schema.
