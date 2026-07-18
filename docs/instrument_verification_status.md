# Instrument Verification — Status

Index + running status for the **standards-grounded instrument verification** workstream.
Each instrument is held to FAA Part 23 / AC / TSO material as an **engineering target**
(certifiable-quality *without* certification — deviations documented), verified against the
FAA corpus, and closed with an executable test catalog. See
[`avionics_reference.md`](avionics_reference.md) for the standards basis and the framing.

Branch: **`display-changes`** (billmallard/pyEfis fork). Last updated: 2026-07-01.

## The template (repeated per instrument)

FAA standards → per-instrument spec `<name>_widget_spec.md §4` with stable
`<WIDGET>-<CLASS>-NNN` requirement IDs (each cited to doc + PDF page) → test catalog in
`tests/instruments/<w>/` (passing tests verify shipped behaviour; **`xfail(strict)` tests
are the self-closing gap tracker** — each flips the run red when its feature lands) →
implement → visual-verify offscreen → **deploy to the Pi** (scp/patch, LF-normalized;
`diff --strip-trailing-cr` to see the real delta) → mark DONE.

Run one widget's suite:
`cd pyEfis; PYTHONPATH="C:/pylib;src" python -m pytest tests/instruments/<w>/ --no-cov -q -p no:cacheprovider`

## Status by instrument

All seven areas below are **verified + deployed to the Pi**. "Code gaps" counts
*implementable* gaps still open; data-blocked items are tracked separately.

| Instrument | Spec | Suite | Open code gaps | Data-blocked (tracked) |
|------------|------|-------|----------------|------------------------|
| **HSI** | [hsi_widget_spec.md](hsi_widget_spec.md) | 25 pass | none (3 warning flags done) | — |
| **Attitude (AI)** | [ai_widget_spec.md](ai_widget_spec.md) | 22 pass / 1 xfail | none | **AI-LIM-001** pitch-limit → AOA |
| **Airspeed tape** | [airspeed_widget_spec.md](airspeed_widget_spec.md) | 12 pass | none | — |
| **Altimeter tape** | [altimeter_widget_spec.md](altimeter_widget_spec.md) | 13 pass / 1 xfail | none | **AL-BUG-001** alt reference bug → ALT_SEL |
| **VSI** | [vsi_widget_spec.md](vsi_widget_spec.md) | 11 pass | none | — |
| **Turn coordinator / slip-skid** | [tc_widget_spec.md](tc_widget_spec.md) | 9 pass | none | — |
| **Heading / compass** | [heading_widget_spec.md](heading_widget_spec.md) | (in HSI suite) 29 pass | none | — |

**Net: no implementable code gaps remain across the verified instruments.** The two open
items are both data-blocked on a fix-gateway key (below).

## What shipped (highlights)

- **HSI** — three warning flags (HDG/NAV/GS) + LOC-gated glideslope.
- **AI** — excessive-bank + excessive-sideslip amber cautions; unusual-attitude **recovery
  chevrons** (A.2.2); **de-clutter** at unusual attitude (p.47).
- **Airspeed** — low-speed **red band VSO→0** + high-speed **red band VNE→top** (§17.7.1).
- **Altimeter** — 500/1,000-ft **tick tiers** (§17.8.a) + 6-second **altitude trend**
  (§17.8.b, ALT-default so the shared VS tape stays quiet).
- **VSI** — `VSI_PFD` invalid-VS annunciation (Table 4-6 Major "misleading VS").
- **Turn coordinator** — excessive-slip **amber ball** (A.2.6), matching the AI slip/skid.
- **Heading** — `DG_Tape` invalid-heading annunciation (§8.6.a; resolved the in-code TODO).

**Fleet consistency thread:** every moving/scrolling display (VSI_PFD, DG_Tape) and every
slip-skid (AI, TC) now annunciates invalid data (red `XXX`/flag on fail, grey on old/bad)
and excessive-slip the same way, off the same FIX keys.

## Data-blocked gaps (need a fix-gateway key)

Both are specified, contracted, and carry `xfail(strict)` gap-tracker tests; they will
auto-close (flip the run red) the moment the key is published.

| pyEfis gap | Needs | fix-gateway tracking |
|------------|-------|----------------------|
| **AI-LIM-001** — pitch-limit / stall-margin on the AI (A.2.4) | an **AOA / stall-margin** key | **[billmallard/fix-gateway#13](https://github.com/billmallard/fix-gateway/issues/13)** (EFIS-AOA-001) |
| **AL-BUG-001** — altimeter **reference bug** at selected altitude (§17.8.a) | an **`ALT_SEL`** key | **billmallard/fix-gateway [#7](https://github.com/billmallard/fix-gateway/issues/7)/#6/#8/#9** (EFIS-ALTSEL-*) |

## Open enhancements (non-blocking, tracked in the specs)

- **Airspeed:** takeoff inhibit of the low-speed red band (§17.7.a — needs a WoW/phase
  signal); green-arc bottom is VS0 where §23.1545 wants VS1.
- **Altimeter:** configurable range; the `screenbuilder_factory.py` `show_trend`/
  `trend_lookahead` forwarding is committed locally but **not yet deployed to the Pi** (the
  Pi's factory is a few commits behind — the trend still works via the dbkey default).
- **VSI:** configurable range per §A.6.
- **TC:** `TurnCoordinator_Tape` is unregistered/unwired legacy — would need TC-ANN-001 if
  ever wired.
- **Heading:** heading-vs-track **source indication** (§8.6.b) — no track selection in the
  stack yet.
- **HSI (deferred follow-ups):** `_showCDI`-on-fail, TO/FROM styling, NAVSRC persistence
  ([#84](https://github.com/billmallard/pyEfis/issues/84)).

## Corpus + reference

- Curated, page-cited standards basis: [`avionics_reference.md`](avionics_reference.md)
  (§2 no-misleading, §3 colour, §4 HSI + §4.4 heading, §5 AI, §6 airspeed/altitude tapes,
  §7 VSI, §8 turn coordinator).
- Full FAA text (grep-able, `===== PAGE N =====` markers): `MAOS/reference/faa_text/*.txt`
  (not committed). Key docs: **AC 25-11B**, **AC 23.1311-1C**, **14 CFR part 23**.
- This corpus + the per-instrument catalogs are also the grounding substrate for the
  Auspex test-oracle effort.
