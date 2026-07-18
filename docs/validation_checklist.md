# pyEFIS validation checklist

A bounded, ~30-minute pass to confirm a build works on **your** hardware, not
just the author's. Aimed at reviewers and pilots validating the large
SVS / moving-map / editor / instrument change set before it merges.

You do **not** need to read the code. Install, boot, look at a few screens,
confirm the "expected" matches what you see, and report anything that doesn't.

## How to report

For each item: PASS, FAIL, or N/A. For any FAIL, capture a screenshot and note
what you saw. Please fill in the environment block once at the top of your
report so results are comparable across testers:

```
Tester:
Device:          (e.g. Raspberry Pi 5 / 8GB, or Dell XPS laptop)
OS:              (e.g. Raspberry Pi OS Bookworm 64-bit, Ubuntu 24.04)
GPU/driver:      (e.g. Pi VideoCore, Intel iris, "none/software")
Install method:  snap (channel: edge/beta) | source checkout
Data present:    yes (makerplane-data updater) | no
fix-gateway src: X-Plane | Stratux | GNX | none
```

---

## Part A — Install and first boot

- [ ] **A1. Install succeeds.**
  - *Snap:* `sudo snap refresh pyefis --<channel>` (or install) completes with no
    error. *(Snap builds/publishing are handled by the maintainer; testers just
    install the published channel.)*
  - *Source:* per [running_from_source.md](running_from_source.md) — `make venv`,
    `pip install -e '.[qt,svs]'`, `python pyEfis.py`.
- [ ] **A2. pyEFIS boots to a screen** without a traceback, on a fresh config
  (no hand-created folders required). **Expected:** the default PFD appears; the
  attitude shows sky/ground.
- [ ] **A3. Config auto-created.** `~/makerplane/pyefis/config/` exists and was
  populated automatically (you did not create it).

## Part B — Core screens (should work everywhere, GPU or not)

Switch screens with the on-screen button / configured control.

- [ ] **B1. PFD** — airspeed tape, altimeter tape, attitude, heading all present
  and readable.
- [ ] **B2. Engine (EMS / EMS2)** — engine gauges (RPM, oil, CHT/EGT, fuel)
  render; gauge bands/colors present.
- [ ] **B3. Six-Pack** — the classic six instruments lay out without overlap.
- [ ] **B4. Data Status** — the nav-data status screen renders (it will show
  "no data" states if the makerplane-data packs aren't installed — that is a
  PASS, not a failure).
- [ ] **B5. No overlap / clipping** on your actual screen resolution. Note the
  resolution if anything is cut off.

## Part C — New / changed features

- [ ] **C1. HSI** — heading bug and course pointer track; with a nav source
  (X-Plane HSI, etc.) CDI/TO-FROM behave sensibly.
- [ ] **C2. Moving map** — if a map screen is configured, terrain/airports/
  navaids/airways layers render and pan; range/orientation controls respond.
  **Requires the fix-gateway map-control keys** (MAPRANGE/MAPORIENT/MAPTERRAIN)
  — without them the controls no-op (note this rather than failing C2).
- [ ] **C3. Synthetic Vision (SVS)** — **off by default.** To test: on a
  GPU-capable device with terrain data, set `enabled: true` in the `svs:` block
  of your `svs.yaml` and point the paths at your data root. **Expected:** terrain
  mesh with airport/runway and water/road overlays. To fetch terrain/nav data,
  run the makerplane-data updater (`pyefis-data update`) — on a Pi it's already
  installed. *(No GPU or no data? Skip this and rely on the degradation checks
  D1/D2 instead — "SVS UNAVAIL" is the expected, correct result.)*
- [ ] **C4. Instrument fixes** — altimeter and numeric/value_text readouts show
  correct formatting (decimals, units) with live or test data.

## Part D — Graceful degradation (this is where "works in my env" hides)

These MUST NOT crash. A clean fallback is a PASS.

- [ ] **D1. No GPU.** On software rendering, SVS annunciates **"SVS UNAVAIL"**
  and the attitude falls back to sky/ground. pyEFIS keeps running.
- [ ] **D2. No terrain/nav data.** With SVS enabled but `/data/...` paths empty
  or absent, pyEFIS still boots and runs; terrain simply doesn't draw. No
  traceback, no requirement to create folders by hand.
- [ ] **D3. No fix-gateway.** With no data source running, pyEFIS boots and shows
  screens; instruments read stale/invalid (grey / red "XXX") rather than crashing.
- [ ] **D4. fix-gateway reconnect.** Start fix-gateway after pyEFIS; values come
  alive without a pyEFIS restart.

## What to send back

- The filled environment block.
- The PASS/FAIL grid (A1..D4).
- Screenshots for any FAIL, plus the last ~30 lines of console output if it
  crashed (`python pyEfis.py --debug` for source installs).

## Coverage matrix (maintainers fill in as reports arrive)

The point of this table is to make the gaps visible — an empty cell is an
untested combination, not a passing one.

| Device / GPU | Install | PFD | Engine | Map | SVS | Degrade (D1-D4) |
|---|---|---|---|---|---|---|
| Pi 5 / VideoCore | snap | | | | | |
| Pi 4 / VideoCore | snap | | | | | |
| Desktop / discrete GPU | source | | | | | |
| Laptop / integrated | source | | | | | |
| Laptop / software (no GPU) | source | | | | | |
