# HSI Widget Specification

**Status:** Draft v0.5 (working specification; P0 + P1a + track-diamond fix shipped)
**Widget type:** `horizontal_situation_indicator`
**Source:** [`src/pyefis/instruments/hsi/__init__.py`](../src/pyefis/instruments/hsi/__init__.py)
**Registry:** [`src/pyefis/screens/screenbuilder_factory.py`](../src/pyefis/screens/screenbuilder_factory.py) (`type="horizontal_situation_indicator"`)

This is the first of the per-instrument specifications (see issue: "Per-widget
specifications + documentation"). It is meant to be the **template** for the
others: each widget is a small application, and this document captures its
purpose, its data contract, its appearance options, its behaviors, and a phased
plan to bring it to parity with market-leading HSIs.

---

## 1. Purpose

A Horizontal Situation Indicator combines a **directional gyro / compass** with a
**course deviation indicator (CDI)** in one instrument: a rotating compass card
under a fixed aircraft symbol, a selected-course pointer, a lateral deviation
bar, a glideslope/glidepath scale, and a set of selectable markers (heading bug,
bearing pointers, ground-track diamond). It answers, at a glance: *which way am I
pointing, which way is my course, and how far off it am I.*

## 2. Design principles

1. **A display first, with a thin, honest control surface.** The HSI's main job
   is to render navigation state published on the FIX bus. It *may* also write
   back a small, well-defined set of **pilot selections made at the instrument** —
   the **selected course** (OBS/CRS) and the **active nav source** (`NAVSRC`, via
   the tappable source label / a `CDI SRC` button) — because those are choices a
   pilot makes *on the HSI*. What it must **not** do is own navigation *logic*:
   source **routing** (the `select` compute), deviation scaling, and waypoint
   sequencing live upstream (fix-gateway / the navigator). Rule of thumb: the
   widget may publish *what the pilot picked*, never *compute what the needles
   mean*. (Note the distinction: the widget writes the source **selection**
   `NAVSRC`; fix-gateway does the source **routing**. Persistence of that
   selection and its publication as a true CAN-FiX bus parameter are fix-gateway
   concerns — see §4.3, §11.4, and issue #84.)
2. **One canonical key per concept, fed by a selector.** The HSI reads
   `COURSE` / `CDI` / `GSI`; fix-gateway's `compute` `select` routes the active
   source (`NAVSRC`) into those canonical keys. The widget never has to know
   which radio is active to draw the needle — but it *does* need a published
   *source descriptor* to color and annotate correctly (see §4).
3. **Layout-vs-FIX boundary (issue #64).** Appearance and feature toggles are
   **editor options** (written into the screen YAML). Live navigation quantities
   and their scaling are **FIX-database values** (published by fix-gateway). This
   spec labels every field as one or the other. V-speed-style "which is which"
   mistakes are the main thing this boundary prevents.
4. **Conventions, not clones (see §9).** The HSI follows long-established
   symbology conventions so a pilot reads it without retraining. Those
   conventions come from open standards and decades of practice, cited in §9 —
   not from any one vendor's copyrighted material.
5. **Two repos move together.** New behavior that needs new data is a
   **canfix-spec / fix-gateway** change first (the data contract), then a pyEfis
   widget change. Build the data before the pixels.

## 3. Current state (implemented)

**FIX keys read** (`dbkeys=["COURSE","CDI","GSI","HEAD"]` plus internal
subscriptions):

| Key | Role | Notes |
|---|---|---|
| `HEAD` | rotates the compass card | magnetic heading |
| `COURSE` | selected-course pointer (magenta) | canonical, fed by `select` from `NAVSRC` |
| `CDI` | lateral deviation bar | canonical; `cdi_enabled` |
| `GSI` | glideslope/glidepath needle | canonical; `gsi_enabled` |
| `HEADBUG` | selected-heading bug (cyan) | `heading_bug_enabled` |
| `TRACK` + `GS` | GPS ground-track diamond (magenta) | `track_indicator_enabled`, gated by `track_min_speed` |

**Editor options (category 1, today):** `cdi_enabled`, `gsi_enabled`,
`fg_color`, `bg_color`, `bg_opacity`, `needle_color`, `needle_width`,
`course_color`, `heading_bug_enabled`, `heading_bug_color`,
`track_indicator_enabled`, `track_color`, `track_min_speed`.

**Source-selection chain (fix-gateway, config-driven — already built):**
`NAVSRC` (`0=GPS, 1=NAV1, 2=NAV2`, `max=3` so a button cycles 0→1→2→0) →
`compute` `select` routes `{GPS,NAV1,NAV2}{CRS,CDI,GSI}` into `COURSE`/`CDI`/`GSI`
→ `compute` `remap` produces `XPHSISRC` for X-Plane HSI feedback. The on-screen
"control" is a **generic `button`** instrument configured to cycle `NAVSRC`;
there is no dedicated nav-source widget.

**Resolved (P0):** the `COURSE` value was handled by a method named
`setHeadingBug` (stored as `_headingSelect`), confusable with the real heading
bug (`setHdgBug`). Renamed to `setCoursePointer` / `_courseSelect` /
`course_pointer`, and a dead `_courseSelect = 1` was dropped. No behaviour change.

## 4. Data contract — existing and proposed

The HSI's competitiveness is mostly a **data** problem: the renderer is
straightforward once the values exist. Keys below marked **PROPOSED** do not yet
exist and must be added to the CAN-FiX schema (the master spreadsheet
`src/CAN-FIX.ods` in [canfix-spec](https://billmallard.github.io/canfix-spec/) —
*do not hand-edit the generated json/xml*) and published by fix-gateway before
the widget can use them. Map to existing CAN-FiX navigation parameters where one
already fits; only add where there is a genuine gap.

### 4.1 Existing (in fix-gateway `ahrs.yaml`)
`HEAD`, `HEADBUG`, `TRACK`, `TRACKM`, `GS`, `COURSE`, `CDI`, `GSI`, `NAVSRC`,
`GPSCRS/GPSCDI/GPSGSI`, `NAV1CRS/NAV1CDI/NAV1GSI`, `NAV2CRS/NAV2CDI/NAV2GSI`,
`XPHSISRC`.

### 4.2 Audit: mapping HSI needs to existing CAN-FiX parameters

A parameter audit (against `canfix.json` v0.7) confirms the working assumption:
**almost everything a competitive HSI needs already exists in the CAN-FiX spec.**
The richest single parameter is **OBI Flags (id 450)** — a WORD that already
bundles TO/FROM, the active nav input, the glideslope flag, and the LOC-vs-VOR
type:

```
id 450  OBI Flags:  b0    = To/From (To = 1)
                    b1:b2 = Input (00=NAV1, 01=NAV2, 10=GPS1, 11=GPS2)
                    b3    = GS (glideslope present)
                    b4    = LOC/NAV (localizer vs VOR)
```

So `NAVTYPE` and `TOFROM` are **not new parameters** — they are bit fields of an
existing one.

| HSI need | CAN-FiX parameter (id) | Status |
|---|---|---|
| TO/FROM | OBI Flags (450) b0 | EXISTS (bit) |
| Active source / input | OBI Flags (450) b1:b2 | EXISTS (bit) |
| LOC vs VOR (`NAVTYPE`) | OBI Flags (450) b4 | EXISTS (bit) |
| Glideslope present | OBI Flags (450) b3 | EXISTS (bit) |
| Lateral deviation (`CDI`) | VOR/LOC Deviation (448); Cross Track Error (456, nm) | EXISTS |
| Glideslope deviation (`GSI`) | Glideslope Deviation (449) | EXISTS |
| Selected course (`COURSE`) | Selected Course (457) | EXISTS |
| Desired track (`DTK`) | Selected Course (457) is the active-leg DTK; Track Error Angle (1179) | EXISTS |
| Distance (`DME/DIS`) | Waypoint, Distance To (1164, nm) | EXISTS |
| ETE | Next Waypoint ETE (1157); Waypoint ETE (1163); Destination ETE (1178) | EXISTS |
| Active waypoint id (`WPID`) | Next Waypoint Identifier (1152); Waypoint Identifier (1158) | EXISTS |
| Station ident | VOR/ILS Identifier (1224) | EXISTS |
| VOR radial (bearing) | Actual VOR Radial (1228); Selected VOR Radial (1232) | EXISTS |
| Selected glidepath | Selected Glidepath Angle (458) | EXISTS |
| Ground track (diamond) | True / Magnetic Ground Track (454 / 455) | EXISTS |

**Genuine gaps (small — all GPS-navigator mode state):**

| HSI need | Status | Cheapest fill |
|---|---|---|
| OBS mode active | GAP | spare bit of OBI Flags (b5) — minimal `.ods` touch |
| SUSP (sequencing suspended) | GAP | spare bit of OBI Flags (b6) |
| Flight-phase annunciation (ENR/TERM/APR) | GAP (optional) | new nav param, or omit |
| Bearing TO active GPS waypoint | PARTIAL | compute in fix-gateway from aircraft (451/452) + waypoint (1153/1154) lat/lon — no schema change |

**Source-numbering reconciliation.** Three encodings of the active nav input are
in play (OBI Flags vs `NAVSRC` vs `XPHSISRC`); **§4.3** reconciles them and
recommends aligning `NAVSRC` to the bus-native ordering.

**Where the work lands.** The **CAN-FiX schema barely changes** (only the optional
OBS/SUSP bits). The real work is in the **fix-gateway key layer** — expose
`TOFROM`/`NAVTYPE` (decode OBI Flags on real hardware, or set from X-Plane) and
add keys for DME/ETE/WPID/radials that map to the existing CAN-FiX parameters —
plus the **widget** that reads them. This is exactly the layering this spec
assumed: build the data (mostly already there), then the pixels.

> **Decision (CDI scaling).** `CDI`/`GSI` stay **strictly normalized** (−1..+1 =
> full-scale deflection / the standard dots). Full-scale is owned by the
> **navigation source**, per FAA needle-deflection standards — VOR ±10° (≈2° per
> dot), LOC ±2.5° (much more sensitive), GPS 2.0 nm enroute / 1.0 nm terminal /
> angular on approach (FAA-H-8083-15B; AIM; AC 20-138 / TSO-C146). The widget
> renders the dots it is given and **never computes scaling** — this also keeps
> existing consumers (the autopilot) unaffected. No `CDISCALE` key is added; the
> normalized convention already present in the widget is correct.

### 4.3 Source-numbering reconciliation (recommendation)

> **Status: implemented** in fix-gateway (`xplane-data-driven`, commit `e0e26aa`)
> — `ahrs.yaml` `NAVSRC` + `compute.yaml` `select`/`remap` migrated to the
> NAV-first ordering below; verified locally, pending an X-Plane bench test.

Three encodings of "which nav input is active" are in play:

| Input | OBI Flags 450 b1:b2 (CAN-FiX) | `NAVSRC` today | `NAVSRC` proposed | X-Plane `XPHSISRC` |
|---|---|---|---|---|
| NAV1 | 0 (`00`) | 1 | 0 | 0 |
| NAV2 | 1 (`01`) | 2 | 1 | 1 |
| GPS (1) | 2 (`10`) | 0 | 2 | 2 |
| GPS2 | 3 (`11`) | — | 3 | (2) |

`NAVSRC` today is the **only outlier** (GPS-first). That single difference is why
fix-gateway needs the `[2, 0, 1]` remap to X-Plane today — and would need a second
table to decode OBI Flags from real hardware.

**Recommendation: migrate `NAVSRC` to the bus-native NAV-first ordering**
(`0=NAV1, 1=NAV2, 2=GPS`, extensible `3=GPS2`). This collapses all three schemes
into one:

1. **Bus-native.** `NAVSRC` then equals OBI Flags b1:b2 directly — a real CAN-FiX
   nav/GPS source's OBI Flags decodes into `NAVSRC` with no table.
2. **X-Plane alignment.** X-Plane's HSI source is already NAV-first
   (`0=NAV1, 1=NAV2, 2=GPS`), so `XPHSISRC` becomes **identity** with `NAVSRC` and
   the `[2, 0, 1]` remap disappears.
3. **Dual GPS.** The 2-bit OBI space distinguishes GPS1/GPS2; the 3-value `NAVSRC`
   cannot. NAV-first ordering leaves room (`3=GPS2`).

**Concrete fix-gateway changes (single-GPS panels):**
- `ahrs.yaml`: `NAVSRC` description → `0=NAV1, 1=NAV2, 2=GPS`; `max` stays 3.
- `compute.yaml`: reorder the three `select` input lists from
  `[NAVSRC, GPS*, NAV1*, NAV2*]` to `[NAVSRC, NAV1*, NAV2*, GPS*]`; the `XPHSISRC`
  `remap` becomes identity (`table: [0, 1, 2]`) or is dropped (write `NAVSRC`
  straight to `XPHSISRC`).
- The nav-source **button**: its cycle is now NAV1→NAV2→GPS. If GPS-primary
  cycling is preferred, set the button's start value or a custom cycle — that is a
  UX choice independent of the encoding.
- Migration is contained: the button writes `NAVSRC` dynamically (no hard-coded
  value in saved panels), so few or no configs change meaning. It is a live
  behavior change to fix-gateway, so it should be made deliberately and verified
  on the bench (X-Plane HSI source still follows after the change).

**Command vs. status (forward-looking).** `NAVSRC` is a *selection command*; OBI
Flags b1:b2 is the *active-input status*. They coincide today, but Garmin-style
**auto-switching** (GPS → LOC on an ILS before the FAF) makes the active input
differ from the manual selection. So the widget should colour/annunciate from the
**active source** (OBI Flags / a status key), not the raw `NAVSRC` command. For
now fix-gateway can publish them as the same value; keeping them conceptually
separate lets auto-switching drop in later without a redesign.

## 5. Appearance options (category 1 — editor)

### 5.1 Existing
See §3. Keep all.

### 5.2 Proposed

| Option | Kind | Purpose |
|---|---|---|
| `source_auto_color` | boolean | color course pointer + CDI by `NAVTYPE` (magenta GPS / green VOR-LOC) instead of the static `course_color`. Default **on**. |
| `vloc_color` | color | the "green" used when the source is VOR/LOC (default `#00ff00`). |
| `orientation` | enum | `north_up` (full 360 rose, today) / `heading_up` / `track_up` / `arc` (120° expanded HSI). |
| `bearing1_enabled` / `bearing2_enabled` | boolean | show bearing pointer 1 / 2. |
| `bearing_color` | color | bearing-pointer color (default cyan `#00ffff`). |
| `tofrom_enabled` | boolean | show the TO/FROM indicator. |
| `data_fields` | enum/multi | which corner data fields to show (CRS, HDG, DIS, DTK, GS, ETE, source). |
| `aircraft_symbol` | enum | reference-symbol style. |
| `rose_labels` | enum | cardinal letters vs numerals; tick density. |

The `visiblePointers` array (top/bottom/right/left tick visibility) already
exists internally — expose it if useful.

## 6. Behaviors and modes

Each item: what it does, the input(s), the convention.

1. **Compass card** — rotates so current `HEAD` is under the lubber line
   (north-up today; §5.2 adds heading-/track-up and arc).
2. **Course pointer** — arrow to `COURSE`. Convention: **single-line for source
   1, double-line for source 2**; colored magenta for GPS, green for VOR/LOC
   (gated by `source_auto_color` + `NAVTYPE`).
3. **CDI (lateral deviation)** — bar offset from the course pointer along the
   standard dotted scale, drawn from the **normalized** `CDI` value. Full-scale is
   defined by the **navigation source** (VOR ±10°, LOC ±2.5°, GPS 2.0/1.0 nm by
   phase — FAA-H-8083-15B), not by the widget: the display renders the dots it is
   given and never scales. Hidden/flagged when the signal is invalid (see 11). An
   optional `NAVPHASE` annunciation (ENR/TERM/APR) is display-only text from the
   navigator.
4. **TO/FROM** — for VOR sources; hidden for LOC and (typically) GPS.
5. **Glideslope / glidepath (VDI)** — vertical deviation scale + diamond from
   `GSI`; shown on ILS/LPV/approach. **An ILS glideslope requires a valid
   localizer**: the diamond appears only when a glideslope is received *and* the
   localizer is captured, so it hides when off the localizer — turned off the
   approach, or crossing a false glideslope lobe while climbing out. A GPS/LPV
   glidepath has no separate localizer and shows on its own vertical-guidance
   flag. Enforced in fix-gateway as `GSV = min(NAV#DH, not nav#_flag_glideslope)`
   (localizer-displayed AND glideslope-received); see 11.
6. **Heading bug** — cyan marker at `HEADBUG`.
7. **Ground-track diamond** — magenta diamond at the **magnetic** ground track
   `TRACKM`, gated by `GS ≥ track_min_speed`. (Implemented.) *Originally read
   `TRACK` (true), which sat off by the local magnetic variation on the magnetic
   rose; fixed to `TRACKM`, derived in fix-gateway as `(TRACK + MAGVAR) mod 360`
   via the new `wrap360` compute function.*
8. **Bearing pointers 1 & 2** — cyan needles pointing to `BRG1`/`BRG2`;
   single-line (1) / double-line (2); **hidden when heading is invalid**; they
   never override and are visually separated from the deviation bar. Each has a
   selectable source label.
9. **OBS mode** — when an OBS control sets the course, `COURSE` becomes
   pilot-settable; with a GPS source, asserting `OBSMODE` suspends waypoint
   sequencing and holds the active-to waypoint; annunciate **"OBS"**. **"SUSP"**
   annunciated from `SUSP`.
10. **Data fields** — corner readouts: selected course (CRS), selected heading
    (HDG), distance (DIS/DME), desired track (DTK), ground speed (GS), ETE,
    active waypoint, and the **navigation-source annunciation** (e.g. "GPS",
    "VOR1", "LOC1") colored to match the pointer.
11. **Signal-driven visibility (failure handling)** — the display shows what it
    **receives**, not what is selected. A needle (CDI, GSI, bearing pointer)
    appears only when a valid signal for it is present; with no signal it **hides**
    — the digital equivalent of a mechanical needle parking in the bezel —
    regardless of which source is selected (e.g. selecting LOC with no localizer
    received shows no needle). The **glideslope is additionally coupled to the
    localizer**: an ILS GS diamond shows only with a captured localizer, never on
    its own — a real HSI does not present vertical guidance without lateral. This
    is enforced upstream in fix-gateway (`GSV = min(NAV#DH, not
    nav#_flag_glideslope)`), so the widget just reads `GSV`. Follow the widget
    convention: `fail` → remove / red flag; `old`/`bad` → grey. Never show stale
    or sourceless guidance.

## 7. Flags, alerts, and failure annunciation (requirements)

Standards basis: [`avionics_reference.md`](avionics_reference.md) §2–§4 — 14 CFR
§23.2600/.2605/.2615; AC 25-11B §4.2 and Table 5-1; AC 23.1311-1C §18/§22; IFH
(FAA-H-8083-15B) p.118, p.259, p.283.

**Governing rule.** The HSI must *monitor every signal it consumes and annunciate
loss or invalidity* — a positive **flag** for a primary signal, removal for a needle
that parks — and must never present stale or sourceless guidance as if it were valid
("do not display misleading information", `avionics_reference.md` §2). Requirement IDs
(`HSI-<CLASS>-<NNN>`) are stable and are the anchor for the test-case catalog (§10) and
any gap issues. **Status** reflects the widget as of this writing.

### 7.1 Warning flags (HSI-ANN)

The IFH HSI figure (IFH p.118) shows three standard warning flags; p.283 gives the
behavior — *a flag appears whenever its signal is absent, unstable, or the receiver has
failed, and is removed only when a valid signal drives the needle.*

| ID | Flag | Trigger | Required response | Cite | Status |
|----|------|---------|-------------------|------|--------|
| **HSI-ANN-001** | Heading (compass) flag | `HEAD` fail/bad or absent | Red **HDG** flag; compass card and every heading-referenced element (course pointer, CDI geometry, bearing pointers, track diamond) must stop presenting misleading heading | IFH p.118; AC 25-11B §4.2; 14 CFR §23.2605(b) | **DONE** — red HDG flag |
| **HSI-ANN-002** | NAV (lateral) flag | Selected lateral source (`CDI`) fail/bad/absent | **NAV** flag by the course pointer; remove the CDI bar | IFH p.118, p.283 | **DONE** — red NAV flag; CDI removed |
| **HSI-ANN-003** | GS (glideslope) flag | Glideslope *expected* (ILS tuned, LOC valid) but the GS signal is invalid/unstable/failed | **GS** flag on the glideslope scale — distinct from "no GS present" (scale simply absent) | IFH p.283; AC 25-11B §4.2 | **DONE** — red GS flag; diamond suppressed |

The HSI-ANN-003 distinction matters: **no glideslope tuned/expected → no GS scale**
(handled by `GSV`); **glideslope expected but signal lost → GS *flag*** (still a gap).

### 7.2 Per-signal failure response (HSI-FAIL)

**HSI-FAIL-001.** Every FIX signal the widget consumes is wired to the widget failure
convention, and no element is left showing its last-good value after loss:

| Signal | valid | old (stale) | bad (invalid) | fail | absent |
|--------|-------|-------------|---------------|------|--------|
| `HEAD` | normal | grey card | grey + HDG flag (ANN-001) | HDG flag, freeze/blank card | HDG flag |
| `COURSE` | normal | grey pointer | grey pointer | remove pointer | pointer removed |
| `CDI` | normal | hide bar | hide + NAV flag (ANN-002) | remove + NAV flag | no bar |
| `GSI`/`GSV` | normal | hide diamond | hide diamond | hide/flag (ANN-003) | no scale |
| `HEADBUG` | normal | grey bug | grey bug | remove bug | no bug |
| `TRACKM`/`GS` | normal | hide diamond | hide diamond | hide diamond | no diamond |
| `TOFROM` | normal | hide | hide | hide | hide |
| `BRG1`/`BRG2` | normal | hide needle | hide needle | hide needle | no needle |

The widget now renders all three flags (ANN-001..003), and `_showGSI` hides on `fail`
too. Open items: gating `_showCDI` on `fail` (currently old/bad only — the NAV flag
covers annunciation, but a pure-fail CDI is not yet removed) and confirming
`HEAD`/`COURSE`/`HEADBUG` each fully honor the convention.

### 7.3 Colour (HSI-COLOR)

| ID | Requirement | Cite |
|----|-------------|------|
| **HSI-COLOR-001** | Nav-source colour: **magenta = GPS**; **green = VOR/LOC (VLOC) and ADF bearing needles**. Established market convention (Garmin and others); a *documented, intentional* deviation from AC 25-11B Table 5-1's "ILS deviation pointer = magenta", chosen for source-identification clarity in a GPS-primary cockpit | `avionics_reference.md` §4.3 |
| **HSI-COLOR-002** | Warnings **red**; cautions **amber/yellow**; engaged/normal **green**; scales/tapes/text **white**; selected/bug markers **cyan**. Colour is never the sole code — pair with shape, size, or location | AC 25-11B Table 5-1, §5.8 |

### 7.4 Source annunciation (HSI-SRC)

**HSI-SRC-001.** The active nav source is annunciated on the face at all times (e.g.
"GPS", "VOR1", "LOC1"), coloured per HSI-COLOR-001, so the crew always knows what drives
lateral/vertical guidance (14 CFR §23.2605(b); `avionics_reference.md` §4.1).
*Status: implemented — the tappable source label.*

### 7.5 Deviation scaling (HSI-DEV)

**HSI-DEV-001.** The CDI and GS needles are strictly normalized (±1.0); the navigation
source owns full-scale (§4.2, by phase / receiver type). The widget renders the
deviation it is given and never re-scales. Cite: §4.2; FAA-H-8083-15B; AIM 1-1.

## 8. Phased implementation plan

Ordered by impact-per-effort; each phase is shippable and testable on its own.

- **P0 — cleanup + foundation (pyEfis only). [DONE]** Renamed the course-pointer
  code (see §3); added the `source_auto_color` / `vloc_color` options. No new data.
- **P1a — source colouring by NAVSRC. [DONE]** The course pointer + CDI/GSI are
  coloured magenta for a GPS source, `vloc_color` (green) for a NAV source, read
  from `NAVSRC` (no new data). Widget + registry + schema/R2 + editor twin shipped.
- **P1b — NAVTYPE refinement + source label.** Decode OBI Flags b4 (LOC vs VOR)
  into a `NAVTYPE` key for the green-only-on-VLOC nuance and the single/double-line
  pointer, plus the on-face source annunciation ("GPS" / "VOR1" / "LOC1").
- **P2 — TO/FROM + phase annunciation.** Add `TOFROM` and the optional `NAVPHASE`
  label; draw the TO/FROM arrow. `CDI` stays normalized (no `CDISCALE`; the source
  owns full-scale — see §4.2).
- **P3 — data fields.** Add `DME/DIS`, `DTK`, `ETE`, `WPID`; render the
  configurable corner readouts (CRS/HDG/GS already available).
- **P4 — bearing pointers.** Add `BRG1/BRG2` (+ source + valid); render the two
  cyan needles with source labels and the heading-invalid hide rule.
- **P5 — OBS control + mode.** Add an OBS/CRS control (encoder or button writing
  `COURSE`; `OBSMODE`/`SUSP` flags) and the OBS/SUSP annunciations.
- **P6 — orientation modes.** Heading-up / track-up / arc (120°) expanded HSI.

Each phase: implement widget + factory `Prop`s, regenerate `schema.json` →
R2, update the `editor.html` twin to match (fidelity rule), add unit tests and a
visual test case.

## 9. Conventions and standards basis (and sourcing note)

The symbology in this spec is **industry convention**, grounded in open
references — not proprietary to any vendor. The consolidated, page-cited standards
basis is [`avionics_reference.md`](avionics_reference.md); the flag/alert/colour
*requirements* derived from it are in §7. Primary references:

- **FAA Instrument Flying Handbook, FAA-H-8083-15B** — HSI, CDI, RMI/bearing
  pointers, OBS, TO/FROM.
- **FAA AIM** (1-1, GPS/RNAV) — CDI full-scale by phase (2.0 nm enroute, 1.0 nm
  terminal, angular approach), mode behavior.
- **AC 20-138 / TSO-C146** (GPS/WAAS) — RNAV CDI scaling and flight-phase modes.
- **AC 25-11B** (Electronic Flight Displays) — colour standard (Table 5-1),
  failure/alerting philosophy (§4.2), and the "do not display misleading
  information" rule; the primary source for flags/alerts.
- **AC 23.1311-1C** (Electronic Displays, Part 23) — the GA analog: §17 symbology,
  §18 annunciation, §22 colour standardization.
- **14 CFR §23.2600 / .2605 / .2615** — flightcrew-interface rule: information must
  be monitorable, with discernible warnings/cautions/normal indications, and not
  misleading.
- **[CAN-FiX specification](https://billmallard.github.io/canfix-spec/)** — the
  data contract these keys live in.

**Sourcing note (for next developers):** vendor pilot's guides (e.g. the Garmin
GI 275 guide kept in `docs/` for reference) were read only to *confirm* these
conventions and the expected pilot workflow. This document is written
independently and cites the open standards above; no vendor text, diagrams, or
trade dress are reproduced. Match the *conventions* (which are unprotected and a
safety benefit); never copy a competitor's *expression*. See the project README
for the broader open-source posture.

## 10. Test cases

The executable catalog lives in
[`tests/instruments/hsi/test_hsi.py`](../tests/instruments/hsi/test_hsi.py), keyed to the
§7 requirement IDs. Passing tests verify shipped behaviour; the three `xfail(strict)`
tests are the **gap tracker** for the unimplemented warning flags — they fail today and
will flip the run red the moment a flag is implemented, forcing removal of the marker.
(Suite: 25 passed, 0 xfailed.)

| HSI-TC | Requirement | Test (`test_hsi_cat_…`) | Status |
|--------|-------------|-------------------------|--------|
| 001 | HSI-FAIL-001 (happy) | `all_valid_shows_both_needles` | pass |
| 021 | HSI-FAIL-001 (CDI) | `cdi_hidden_when_old_or_bad` | pass |
| 031 | HSI-FAIL-001 (GSI) | `gsi_hidden_when_old_or_bad` | pass |
| 032 | HSI-ANN-003 (no-GS) | `gs_absent_when_gsv_zero` | pass |
| 041 | HSI-COLOR-001 + SRC-001 | `source_switch_tracks_colour_and_label` | pass |
| 060 | HSI-DEV-001 (CDI edge) | `cdi_full_scale_boundary` | pass |
| 062 | HSI-DEV-001 (GS edge) | `gsi_full_scale_boundary` | pass |
| 101 | **HSI-ANN-001** (HDG flag) | `hdg_flag_on_head_fail` | pass |
| 102 | **HSI-ANN-002** (NAV flag) | `nav_flag_on_cdi_invalid` | pass |
| 103 | **HSI-ANN-003** (GS flag) | `gs_flag_on_gs_lost` | pass |

Existing tests also map in: HSI-FAIL-001 → `cdi_gsi_old_tracks_oldchanged_not_failchanged`,
`quality_flags_hide_and_restore_labels`; HSI-ANN-003 (no-GS) → `gsi_hidden_when_no_glideslope`;
HSI-COLOR-001 → `source_auto_color`; HSI-SRC-001 → `source_label`, `source_label_tap_cycles_navsrc`.

Visual / on-target cases the unit suite can't cover (label `test-case`; record heading,
source, expected appearance):

- Source switch GPS→NAV1→NAV2: pointer color/line-style and on-face label change.
- CDI valid/invalid: needle hides + flag on invalid.
- Track diamond above/below `track_min_speed`.
- Bearing pointers with heading invalid → hidden.
- OBS mode: course settable, "OBS"/"SUSP" annunciated, no auto-sequence.
- TO/FROM for a VOR; absent for LOC and GPS.
- Failure/stale: `fail` red, `old`/`bad` grey.

## 11. Resolved questions and remaining work

1. **Signal-driven visibility (resolved).** The display reflects the *received*
   signal, not the selection: needles hide when no valid signal is present,
   regardless of the source selected (§6.11). The active source's **type** (for
   the magenta/green colouring) is published *with* the signal by the producing
   source/plugin; for X-Plane, fix-gateway derives it. The ILS **glideslope is
   gated on localizer validity** (`GSV = min(NAV#DH, not nav#_flag_glideslope)`),
   so it hides off the localizer — implemented and flight-verified against
   X-Plane. Remaining work: ensure the active source publishes `NAVTYPE` and
   per-needle validity.
2. **CDI normalization (resolved).** `CDI`/`GSI` stay strictly normalized; the
   navigation source owns full-scale per FAA standards (§4.2 decision,
   FAA-H-8083-15B). `CDISCALE` dropped — the existing normalized convention is
   correct.
3. **Map to existing CAN-FiX parameters (done — see §4.2).** Audit complete:
   almost everything already exists (OBI Flags 450 alone covers TO/FROM, source,
   GS, LOC/NAV). Only OBS/SUSP mode bits are genuine gaps, fillable as spare bits
   of OBI Flags via the careful `.ods` process; the GPS bearing pointer is
   fix-gateway-computable from existing lat/lon. Source-numbering schemes need
   reconciling.
4. **Control and interaction (scoped — see §12).** Both physical knob controllers
   and on-screen touch-select are needed; this is a panel-wide interaction model,
   not an HSI-only concern.

## 12. Control and interaction (OBS and beyond)

Setting values on the HSI (and other widgets) — selected course (OBS/CRS),
heading bug, nav source, baro — needs **two complementary input paths**. They are
not either/or; both are wanted:

**A. Physical knob / button controllers.** Hardware the pilot reaches for without
looking. In the test environment the **Octavi IFR-1**
(<https://www.octavi.net/ifr-1>) and **Knobster**
(<https://siminnovations.com/knobster/>) drive X-Plane today over USB HID. The
clean integration point is the **FIX bus**, giving three routes:
- *Sim path (works today):* controller → X-Plane → fix-gateway (reads datarefs) →
  pyEfis. Fine for bench testing.
- *Real-aircraft USB path:* a small **fix-gateway source plugin** reads the USB
  HID controller and writes FIX keys (`COURSE`, `HEADBUG`, `NAVSRC`, baro).
  Mirrors the existing plugin pattern; no sim required.
- *Native CAN-FiX path:* a purpose-built **CAN-FiX knob node** (Arduino +
  `can-fix-arduinolib`) publishes `COURSE`/`HEADBUG` straight onto the bus — the
  most "native" option and the one the protocol intends.

**B. On-screen touch-select + adjust.** Touch a value field (CRS, HDG, baro) to
make it the active edit target, then adjust it (encoder, on-screen +/−, or a
second knob), with a clear highlight and an edit timeout. pyEfis already has an
**encoder/HMI edit mechanism** (`AbstractGauge` encoder-edit state,
`hmi/menu.py`) — this is an *extension* of it with a touch-to-select layer, not a
new subsystem. Should be **web-UI toggleable** (enable/disable touch editing per
panel).

**C. Dedicated controller surface (optional).** A second Pi with a 5" touch
display as a control head. Because fix-gateway is **networked (TCP)**, a second
pyEfis instance can run a "controller screen" (buttons + encoder UI) that writes
FIX keys over the network — reusing the whole stack instead of building anew.

**Open-source prior art to evaluate** (survey — candidates, not yet vetted):
- **MobiFlight** — open-source framework binding hardware (encoders, buttons,
  displays) to flight-sim variables; primarily MSFS with X-Plane support. A
  reference for the hardware-binding model.
- **XCSoar / OpenVario** — open-source soaring computer + open touch hardware
  (7" Pi-class). Its **InfoBox** pattern (touch a field → adjust) is a proven
  open-source touch-select interaction worth studying directly.
- **TouchPi** — Raspberry Pi + touchscreen handheld project; evaluate as a
  reference design for the dedicated-controller hardware (C).
- **AvareX / Avare** — open-source touch EFB (Android); touch interaction model.
- **FlightGear Canvas** — open-source instrument-UI toolkit; interaction ideas.
- **`can-fix-arduinolib`** — already in the MakerPlane org; the basis for a native
  CAN-FiX knob node.
- *(Commercial benchmark, not OSS):* **Air Manager / Air Player** (Sim
  Innovations, makers of Knobster) — the de-facto touch-panel-plus-knob UX to
  match.

This control work is broader than the HSI — it is a **panel-wide interaction
model**. The HSI's OBS/CRS control is its first concrete consumer; spec the
interaction model once and the heading bug, baro, and nav-source controls reuse
it. Track it as its own issue.
