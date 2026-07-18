# Avionics Reference — standards basis for pyEfis instruments

The curated distillation (Tier 2) of the FAA reference corpus: the normative rules
pyEfis instruments are held to, each traceable to its source. Per-instrument specs
(e.g. `hsi_widget_spec.md`) state their requirements and cite *this* document; this
document cites the primary sources.

## Framing: certifiable-quality without certification

MakerPlane is experimental/amateur-built, so none of the Part 23 / TSO material
below legally binds it. We adopt it anyway, deliberately, as the engineering target:
the goal is an EFIS that could be **positioned to certify — or to deliver documented
equivalent-or-better performance — if we ever chose to**, achieved by doing the work
properly now. Standards here are *design targets and a requirements basis*, not a
compliance obligation. Where we deviate, we document *why* (see the ILS-pointer colour
note in §4.3).

## How to use the corpus

- **Curated facts + citations:** this file. Read it first.
- **Full text (retrieval):** `MAOS/reference/faa_text/*.txt` — grep-able mirrors with
  `===== PAGE N =====` markers (N = the PDF page = the Read tool's `pages` number).
  Grep the text to find *where*; read that PDF page in `MAOS/FAA Documents/*.pdf` for
  the actual figure/table (diagrams don't survive text extraction).
- **Citation convention:** `<DOC> <section-or-figure> (p.<PDF-page>)`. Section numbers
  are preferred where the doc has them (stable); page numbers are the PDF/Read page.
- Regenerate the mirrors: `python MAOS/reference/extract_faa_text.py`.

## 1. Sources

| Doc | Corpus file | Role | Covers |
|-----|-------------|------|--------|
| **FAA-H-8083-15B** Instrument Flying Handbook (IFH) | `FAA-H-8083-15B.txt` | Behavioral | How instruments/EFIS behave; what the pilot reads; HSI/CDI/GS figures + flags |
| **FAA-H-8083-16B** Instrument Procedures Handbook | `FAA-H-8083-16B.txt` | Behavioral | Approach/nav procedures, sensitivities |
| **FAA-H-8083-25C** PHAK | `faa-h-8083-25c.txt` | Behavioral | Avionics/EFIS chapter, instrument fundamentals |
| **Chart User's Guide** | `cug-complete_20260122.txt` | Behavioral | Approach-plate + chart symbology |
| **AC 25-11B** Electronic Flight Displays | `AC_25-11B.txt` | **Normative (AMC)** | EFIS symbology, colour standard, failure/alerting, "no misleading info". Transport-category but the field's best-practice reference |
| **AC 23.1311-1C** Electronic Displays, Part 23 | `AC_23_1311-1C.txt` | **Normative (AMC)** | GA analog: §17 Symbology, §18 Annunciation, §22 Colour Standardization |
| **14 CFR Title 14 Vol 1** | `CFR-2025-title14-vol1.txt` | **Normative (rule)** | Part 23 airworthiness incl. §23.2600/.2605/.2615 (flightcrew interface) |
| Airplane Flying Handbook | `00_afh_full.txt` | Behavioral | Maneuvers; secondary for instruments |

**Pending (user is sourcing):** TSO-C113b (multipurpose displays), TSO-C6e (HSI/direction),
TSO-C36e (glideslope), TSO-C34e (localizer). These set minimum performance and invoke
paywalled industry standards (SAE **ARP 5289** nav-display symbology, SAE **ARP 4032A**
colour application, RTCA **DO-178C** software) that we treat the ACs as the proxy for.

## 2. Governing principle — do not display misleading information

The single rule everything else serves. A display must **monitor its data and, when a
value is invalid/lost/stale, annunciate that (flag, remove, or comparator-alert) rather
than present it as if valid.**

- **14 CFR §23.2600** — the flightcrew interface must let the crew *monitor and perform*
  their tasks and *minimize errors*. **§23.2605(b)** — a discernible means of providing
  operating parameters *including warnings, cautions, and normal indications*; **(c)** —
  unsafe-condition information must be *timely and clear*. **§23.2615** — present the
  information needed to *monitor parameters and determine trends* each phase of flight.
- **AC 25-11B §4.2 (p.21–22)** classifies display failures as either **detected** ("flagged
  or comparator alert", or easily crew-detectable) or **undetected/assumed-correct** — the
  latter is the hazardous *"misleading display of…"* case. The design intent is to move
  failures out of the misleading category by monitoring + annunciating. AC 25-11B (ch. 4)
  recommends the architecture *monitor primary flight information to reduce the probability
  of displaying misleading information.*
- **AC 23.1311-1C** — "clearly distinguishable indications of malfunction or misleading
  information" are the acceptable warning means; see §18 (Annunciation).

**pyEfis mapping.** Every widget already has the hooks: `fail` → remove + red flag (`XXX`);
`old` → grey (stale); `bad` → grey/flag (invalid); plus `secfail`. The standards-work is to
(a) wire *every* signal a widget consumes to these, and (b) render an explicit **flag** on
loss — not merely blank the element. (Silently hiding a needle is defensible for a needle
that parks; a *primary* signal loss generally warrants an annunciation, not just absence.)

## 3. Colour standard — AC 25-11B Table 5-1 (p.43)

"Recommended Colors for Certain Functions" — recommended for colour electronic displays:

| Function | Colour |
|----------|--------|
| Warnings | **Red** |
| Flight-envelope / system limits, exceedances | Red **or** Yellow/Amber (as appropriate) |
| Cautions, non-normal sources | **Yellow/Amber** |
| Scales, dials, tapes, associated info | **White** (green acceptable for tapes if it doesn't harm alerting) |
| Earth | Tan/Brown |
| Sky | Blue/Cyan |
| Engaged modes / normal conditions | **Green** |
| **ILS deviation pointer** | **Magenta** |
| Divisor lines, units, inactive soft-button labels | Light gray |

Design rule (**AC 25-11B §5.8**, p.42): where colour codes information, use **at least one
other distinctive parameter** too (size, shape, location) — never colour alone (aging eyes,
colour-vision deficiency). AC 23.1311-1C **§22** is the Part 23 colour-standardization analog.

## 4. HSI — source material

Requirements (with IDs) live in `hsi_widget_spec.md §"Flags, Alerts & Failure Annunciation"`
and cite the items here.

### 4.1 Required flags / annunciations

The IFH HSI figure (**IFH p.118**) labels three warning flags as standard HSI furniture,
plus the component set:

- **Compass (heading) warning flag** — heading/`HEAD` invalid.
- **NAV warning flag** (on the course-select pointer) — selected lateral nav invalid.
- **GS warning flag** — glideslope invalid/unreliable.

Component set from the same figure: compass card, course-select pointer, course-deviation
bar (CDI), TO/FROM indicator, symbolic aircraft, dual glideslope pointers + glideslope
deviation scale, heading bug.

Normative behaviour (**IFH p.283**): *"The localizer and GS warning flags disappear from view
on the indicator when sufficient voltage is received to actuate the needles. The flags show
when an unstable signal or receiver malfunction occurs."* → i.e. **flag = shown whenever the
signal is absent, unstable, or the receiver has failed; removed only when a valid signal
drives the needle.** VOR ambiguity uses an **ON/OFF flag** (**IFH p.259**).

**pyEfis gap (as of 2026-07):** the HSI renders *none* of the three warning flags. The recent
LOC-gated glideslope work (`GSV`) makes the GS diamond *hide* correctly, but hiding ≠ the
FAA-expected **flag**; and there is no compass/heading flag or NAV flag at all. This is the
core of the standards gap that motivated this effort.

### 4.2 Deviation scaling (full-scale)

The needle is normalized (±1.0); the **navigation source owns full-scale**, not the widget
(see `hsi_widget_spec.md §4.2`). Standard full-scale angular values (VOR ±10°; ILS localizer
≈ ±2.5°; glideslope ≈ ±0.7°; GPS by phase) are to be pinned to IFH/IPH pages in the HSI
requirements pass. The widget must not re-scale.

### 4.3 Source annunciation + colour (documented deviation)

**AC 25-11B Table 5-1 allocates Magenta to "ILS deviation pointer."** pyEfis instead colours
by *nav source* — magenta for GPS, green (`vloc_color`) for a VOR/LOC source — following the
modern GPS-navigator convention (Garmin et al.), where magenta = the active GPS/desired-track
and green/white = VLOC. **This is a deliberate, documented deviation from Table 5-1**, chosen
for source-identification clarity in a GPS-primary cockpit. Revisit if TSO/ARP review or user
testing argues for the Table 5-1 allocation. (Exactly the kind of "documented equivalent-or-
better" decision the framing calls for.)

### 4.4 Standalone heading displays (HeadingDisplay / DG_Tape)

Requirements + IDs live in `heading_widget_spec.md §4`. Distinct from the full HSI: the
boxed numeric heading readout (`HeadingDisplay`) and the moving heading tape (`DG_Tape`,
factory type `heading_tape`).

- **§8.2 (p.20)** — heading (direction) is **Primary Flight Information**, part of the
  basic-T; **14 CFR §91.205** requires a magnetic direction indicator (VFR) / gyro-stabilized
  heading (IFR).
- **§8.6 (p.23)** — *clear and unmistakable display of aircraft symbol and heading*; on the
  primary display the heading **scale should have a mode presenting at least 120° of arc**;
  the direction **source should be clearly indicated** (heading vs track, when track is a
  selectable option). *Loss of direction could reduce the pilot's capability* (§8.6.a) — so
  an invalid heading must be annunciated, not shown as live (governing §2).
- **§8.8 (p.24)** — magnetic-heading **accuracy** targets (gyro-stabilized ±4° ground / ±6°
  flight; non-stabilized ±10°). A *data-source* obligation on the AHRS/magnetometer, not a
  display property.

Colour (§22 / Table 5-1): heading scale/text white, cardinal points cyan; failure flag red,
degraded amber. pyEfis status: both standalone heading widgets now annunciate `HEAD`
`fail`/`old`/`bad` — `HeadingDisplay` (red `XXX` / blank amber) and `DG_Tape` (red `XXX`
mask on fail, grey wash + amber `HDG` on old/bad), closing HDG-ANN-001. No open heading
code gaps. The ≥120°-arc scale is provided by the HSI compass rose on shipped screens.

## 5. Attitude indicator (AI) — source material

Requirements (with IDs) live in `ai_widget_spec.md §4 "Flags, Alerts & Recovery
Annunciation"` and cite the items here.

### 5.1 Failure objectives

**AC 25-11B Table 4-1 (p.27)** — *loss of all attitude displays (incl. standby) is
**Catastrophic** / Extremely Improbable*. Attitude-fail annunciation and continued
function are therefore safety-critical: primary attitude must keep working through
unusual attitudes and rapid maneuvers (**§25.1301**; App. A §A.3).

### 5.2 Unusual-attitude recovery + envelope awareness (AC 25-11B App. A, p.70)

The AI must actively *aid recovery*, not merely display attitude:

- **§A.2.2** — quick-glance attitude for *all* unusual attitudes; the pilot must recognize
  and initiate recovery **within one second**. **Chevrons, pointers, and/or a permanent
  ground-sky horizon** are the recommended means.
- **§A.2.4** — a means to determine **margin to stall**; a **pitch-limit** indication is
  acceptable.
- **§A.2.5** — a means to identify an **excessive bank angle** before stall buffet.
- **§A.2.6** — **sideslip** clearly indicated (e.g. split trapezoid), with an **excessive
  sideslip** indication.
- **De-clutter (p.47)** — the AI may auto-de-clutter at an unusual attitude, removing
  non-essential information and retaining what is needed to recover.

### 5.3 pyEfis status

Present: attitude, pitch ladder, bank scale + standard-rate markers, slip/skid ball,
aircraft symbol + FPM, `fail_scene` ("XXX") on failure, `old`/`bad` grey, SVS UNAVAIL.
**Done:** excessive-bank (A.2.5) + excessive-sideslip (A.2.6) amber cautions;
**recovery chevrons (A.2.2)** — amber chevrons to the nearest horizon past the unusual
pitch thresholds; **de-clutter (p.47)** — removes non-essential overlays at an unusual
attitude, keeps the recovery cues. **Data-blocked (the only remaining gap):**
pitch-limit / stall-margin (A.2.4) needs an `AOA`/stall-margin key fix-gateway does not
publish yet.

## 6. Airspeed & altitude tapes — source material

Requirements (with IDs) live in `airspeed_widget_spec.md §4` (airspeed) and
`altimeter_widget_spec.md §4` (altitude), and cite the items here.
Scope is the **moving-scale (linear tape)** airspeed display and its low/high-speed
awareness cues; V-speed *values* come from the FIX database (IAS aux keys), so the cues
are a display-layer job over data the widget does not own (#64).

### 6.1 Moving-scale tape needs explicit awareness cues (AC 23.1311-1C §17.6–17.7, p.40)

**§17.6 (p.40)** — a moving-scale display with a digital read-out is acceptable, but
*"typically does not provide any inherent visual cue of the relationship of present value
to low or high airspeed limits,"* so **quick-glance awareness cues are needed**. **§17.7
(p.40)** — fixed-pointer/moving-scale airspeed displays *require more cues than
conventional round-dial indicators to compensate for their deficiencies*; green/white
arcs alone are **not** considered equivalent, so **low-speed awareness cues are necessary
for part 23 airplanes**. §17.7.b: incorporate *a red arc starting at VSO extending down
toward zero*, and *a red arc or red barber pole extending from VNE (or VMO) upward to the
end of the tape*. **Note (p.40):** the red arc below stall is **low-speed awareness only,
not a flight limit**.

### 6.2 VNE-airplane cues — the normative list (AC 23.1311-1C §17.7.1, Figure 2, p.40–41)

For a **VNE airplane** (the MakerPlane case), showing compliance with §§23.1311(a)(6) and
23.1545(a)–(d):

- **a. Red band from VSO to 0** (or the minimum displayed number). *During takeoff the
  low-speed red arc should not be displayed* (§17.7.a) — an optional inhibit.
- **b. Red band from VNE to the top of the airspeed tape.**
- **c. Yellow band VSO→VS1 is optional** and *discouraged* (clutter), especially for
  twins that already carry red/blue one-engine-inoperative lines.

Conventional arcs remain (§23.1545 markings): **white** flap-operating arc VS0→VFE,
**green** normal-operating arc VS1→VNO, **yellow** caution arc VNO→VNE, **red** VNE
radial. **§17.7.2 (p.42)** gives the VMO-airplane analog (red band VMO→top) — out of
scope here (no `VMO` key; MakerPlane is a VNE airplane).

### 6.3 Colour (AC 23.1311-1C §22.2 Table 4, p.45)

Red = **warnings + flight-envelope/system limits** (so both the low-speed and high-speed
red bands are correctly red); Amber/Yellow = **cautions** (the VNO→VNE caution arc);
White = **scales/tapes**; Green = **normal/engaged**. Consistent with AC 25-11B Table 5-1
(§3 above). Colour is never the sole cue (§22.6) — band **position** carries the meaning
too.

### 6.5 Altitude tape (AC 23.1311-1C §17.8, p.43)

The linear-tape altimeter is a sibling moving-scale display; requirements + IDs live in
`altimeter_widget_spec.md §4`.

- **§17.8.a (p.43)** — a linear-tape altimeter should include **enhancements denoting
  standard 500- and 1,000-foot increments**, convey **unambiguously, at a glance, the
  present altitude**, and carry enough scale length + markings for (i) the resolution to
  track altitude precisely in level flight and (ii) **look-ahead room to predict and
  accomplish level-off**. An **altitude reference bug is recommended** to provide
  acceptable cues.
- **§17.8.b (p.43)** — **display a trend indicator** *unless a VSI is located adjacent and
  to the right of the altimeter*. A **six-second** altitude-trend indicator is typical
  (other values may suit the airplane's performance / tape scaling).

Colour (§22.2 Table 4): scales/ticks **white**; the trend cue is **cyan** (matching the
airspeed tape). Unlike airspeed, the altitude tape carries **no envelope-limit band** —
there is no red/amber altitude band; altitude limits (if any) are advisory, not a tape
marking. Governing "glance-readable, no misleading info" per §2.

**pyEfis status.** `Altimeter_Tape` ships the moving-scale tape + fixed pointer + quality-
aware digital read-out (the §17.8 format). **Done:** distinct **500/1,000-ft** tick tiers
(AL-MARK-001) and the **6-second altitude trend** (AL-TREND-001, cyan; ALT-default so the
shared VS tape stays quiet). **Data-blocked (the only remaining gap):** the **altitude
reference bug** (AL-BUG-001) waits on a selected-altitude key from fix-gateway, like the
AI's AOA-blocked pitch-limit (§5.2 A.2.4).

### 6.4 pyEfis status

`instruments/airspeed/__init__.py` — `Airspeed` (round dial), **`Airspeed_Tape`** (the
moving-scale tape; the verification target), `Airspeed_Box`. The tape draws the green /
white / yellow arcs + a thin **red VNE line**, a fixed pointer, a digital IAS readout
(fail→`XXX`, old/bad→blank via `NumericalDisplay`), a TAS box, and a trend vector.
**Gaps (§17.7.1):** no **low-speed red band VSO→0** (AS-LSA-001) and no **high-speed red
band VNE→top** — only a hairline VNE radial, not the required band (AS-HSA-001).

## 7. Vertical speed indicator (VSI) — source material

Requirements + IDs live in `vsi_widget_spec.md §4`.

- **AC 23.1311-1C §8.11 (p.24)** — *"If provided, present the vertical speed indicator to
  the right or directly below the altitude indicator with a scale appropriate to the
  performance of the aircraft."* → placement (right of / below the altimeter) + a
  performance-appropriate range.
- **AC 25-11B §A.6 (p.74)** — *the display range of vertical speed (rate of climb) should
  be consistent with the climb/descent performance capabilities of the airplane*; if a TCAS
  RA is integrated, the range must be sufficient to show the red/green RA bands.
- **AC 25-11B §4.2 Table 4-6 (p.32)** — safety objectives for "other parameters":
  **loss of all vertical-speed displays = Major**, and **display of misleading
  vertical-speed information = Major**. So VS-invalid must be annunciated, not shown as a
  live value (governing principle §2). (Major, not Catastrophic like attitude — but still a
  flag/remove, not silent freeze.)
- Placement of the primary VSI *to the right of the primary altitude* is echoed in
  AC 25-11B (barometric setting / primary VSI to the right of the altitude indication).

Colour (§22 / Table 5-1): the failure flag is **red**; a degraded (`old`/`bad`) indication
greys. pyEfis status: all three VSI variants annunciate `fail`/`old`/`bad` — `VSI_Dial`
and `Alt_Trend_Tape` already did, and `VSI_PFD` now flags fail (red X, no dot) + greys
old/bad, closing the Major "misleading VS" gap (VSI-ANN-001).

## 8. Turn coordinator / slip-skid — source material

Requirements + IDs live in `tc_widget_spec.md §4`.

- **14 CFR §91.205(d)** — IFR minimum equipment includes a *gyroscopic rate-of-turn
  indicator combined with an integral slip-skid indicator (turn-and-bank indicator)*;
  **§91.205(d)(4)** makes the **slip-skid** mandatory. So both the rate-of-turn and the
  slip-skid ball are required-instrument functions.
- **AC 23.1311-1C §8.9 (p.26)** — rate-of-turn instrument; place near the heading
  indicator if required (a second independent attitude indicator may substitute).
- **AC 23.1311-1C §8.10 (p.26)** — the slip-skid is required by §91.205(d)(4); locate it
  directly below or near the rate-of-turn, or within the primary attitude display.
- **AC 25-11B §A.2.6 (p.70)** — sideslip should be clearly indicated, **with an excessive
  sideslip indication** (the same cue the AI slip/skid carries — `AI-SLIP-002`). The turn
  coordinator's ball is the dedicated slip-skid instrument, so it should carry the same
  excessive-slip salience.

The rate-of-turn shows the airplane symbol against **standard-rate** marks (3°/s = a
2-minute 360). Both the TC ball and the AI slip/skid consume `ALAT` and must agree. pyEfis
status: `TurnCoordinator` shows rate-of-turn + standard-rate marks + an integral slip-skid
ball and annunciates `ROT`/`ALAT` `fail`/`old`/`bad`; the **excessive-slip amber cue**
(TC-SLIP-002) is now implemented — the ball turns amber past `excessiveSlipFraction` of
full-scale, matching the AI slip/skid. No open TC code gaps.

## 9. Requirement IDs and traceability

The chain, grep-able end-to-end:

```
FAA citation      →  requirement (spec)  →  test case (catalog)  →  pytest         →  gap issue
AC 25-11B p.43       HSI-COLOR-001          HSI-TC-###             test_hsi_...       #NN
```

- **Requirement IDs** live in the per-instrument spec: `HSI-<CLASS>-<NNN>` where CLASS ∈
  {`ANN` annunciation/flags, `COLOR`, `DEV` deviation, `SRC` source, `GEOM` geometry, …}.
- **Test-case IDs** `HSI-TC-<NNN>` live in the test-case catalog and are cited by the pytest
  that executes them; each test case names the requirement it verifies.
- The **repo is the system of record** (requirements + catalog + IDs). Issue trackers hold the
  *work* (implement a gap, write a case), not the requirements.

## 10. Open items / to-mine

- [ ] Deep-read **AC 25-11B** ch. 4–5 and **AC 23.1311-1C §17/§18/§22** for the full alerting +
      symbology + colour requirement set; pin pages.
- [ ] Extract the four **TSOs** into the corpus when available; reconcile with the ACs.
- [ ] Pin IFH/IPH pages for deviation full-scale values (§4.2).
- [ ] Extend this file per instrument as verification rolls out beyond the HSI.
