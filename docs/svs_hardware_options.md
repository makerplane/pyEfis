# SVS Hardware Options

Hardware research notes for SVS performance benchmarking and potential
aircraft installation. Companion to [`svs_planning.md`](svs_planning.md)
section 4.

Prices and exact SKUs shift; verify everything before ordering.

## Verdict (as of 2026-05): **Pi 5 is enough**

The OpenGL renderer tier (see [svs_rendering.md](svs_rendering.md)) was
shipped on 2026-05-28. Measured Pi 5 numbers at 800×600, range_nm=30:

- **opengl tier: 5.1 ms/frame mean, ~196 FPS, p95 within 0.2 ms of p50**
- polar CPU tier: 153 ms/frame (~6.5 FPS) on the same hardware

The V3D GPU sitting next to the A76 cores was the unused silicon
keeping us at 6-8 FPS. With it carrying the terrain rasteriser, the
Pi 5 has 5-10× the headroom needed for video-rate SVS *and* leaves
the CPU available for the runway / obstacle / marking overlays.

This kills the lab-box justification for buying x86 to run SVS. The
N100 / Compulab / Onlogic ladders below remain valid for builders who
want them for other reasons (Windows tooling, broader software stack,
sturdier industrial enclosure), but performance is no longer a
reason. Pi 5 + DC conditioner is the recommended SVS installation
target.

## Two distinct purposes

A **lab box** for benchmarking and a candidate **aircraft-installable** unit
have different priorities. Buy the lab box first; only escalate to
aircraft-rated hardware after profiling proves it's needed.

---

## Lab / desk experimentation — Intel N100 class

For benchmarking SVS framerates against Pi 4 / Pi 5. Any of these will run
pyEfis at full `cpu_dense` / `cpu_ultra` and exercise the OpenGL tier when
it ships. None are aircraft-rated.

| Model | Chip | Price (approx) | Notes |
|---|---|---|---|
| Beelink Mini S13 | N150 | ~$170 | Fanless, 12V barrel, common 16/500 config |
| Beelink EQ14 | N150 | ~$200 | More I/O than the S-series |
| MeLE Quieter 4C | N100 | ~$220 | Smaller than Beelink, 12V |
| Trigkey Speed S5 / Mini K | N100 | ~$160 | Often the cheapest path to "real x86 perf" |

**Recommendation for desk benchmarking**: Beelink Mini S13. Cheap, well-known,
plenty of reviews. Run the SVS visual harness alongside one on a Pi 5 to get
direct comparison numbers.

---

## Aircraft-installable — 12V / 24V, fanless, vibration-tolerant

Aircraft-electrical-system-friendly. Three tiers; cost climbs steeply.

### Tier 1: DIY — Pi 5 + aviation power conditioning (~$150 total) — RECOMMENDED

- **Raspberry Pi 5 8GB**, official active cooler (mandatory in an enclosed
  installation; passive cooling will throttle).
- DC step-down / conditioner:
  - **TracoPower TEN 8-2411WIN** — 9-36V → 5V, ~$30. Covers 12V and 24V
    aircraft systems with brownout tolerance during engine start.
  - **Mean Well DDR-15G-5** — 24-28V → 5V, DIN rail, ~$25.
- Add an EMI filter if alternator noise is rough.
- Cheapest and smallest. The ARM-vs-x86 gap stopped mattering once
  the SVS terrain rasteriser moved onto V3D — at 196 FPS the CPU
  side is no longer the bottleneck for anything in pyEfis. Power
  integration is the only DIY task left.

### Tier 2: Compulab Fitlet 3 / 4 (~$400-600)

- Fanless x86. Older **Fitlet 3** uses Atom/Celeron; newer **Fitlet 4**
  uses N100 / N305.
- **8-32V DC input** native — covers both 12V and 24V aircraft systems
  without external converter.
- Industrial temperature range. Conformal coating options.
- Israeli-made; reasonable track record in industrial / automotive use.

This is the sweet spot for experimental amateur-built aviation IMO. Not
overkill, not undersized.

### Tier 3: Onlogic (formerly Logic Supply) — ~$700-1500

- **HX310** / **CL210G** / **K430** — purpose-built fanless industrial PCs.
- Wide-input DC (typically 9-36V), rugged enclosure, certified vibration
  ratings.
- The closest to "aviation-grade" without going through TSO certification.
- Real spend; only justified if benchmarking proves x86 is required AND
  you've committed to a real installation.

---

## Other things to plan around when flying it

These are not covered by the box itself.

- **Vibration mounting** — Lord shock mounts on whatever box you pick. Even
  fanless designs have SSDs and connectors that hate vibration; modern NVMe
  is reasonably robust but isolation matters.
- **Display** — separate decision. Most experimental builders use a 7"-10"
  HDMI panel. Sunlight readability is the big one. Vendors: Faytech,
  Beetronics, PiHut, sometimes industrial OEMs.
- **Power sequencing / brownouts** — engine start can dip a 12V bus to
  ~7V momentarily. Make sure the supply has hold-up capacitance or "no
  brownout" rating. This bites people more than expected.
- **Heat** — fanless boxes need airflow. In a tightly-cowled installation
  with radiative-only cooling, an N100 can throttle on a hot day. Plan to
  temperature-log a hot-day flight test before committing.

---

## Recommended order of purchase

Updated after 2026-05 Pi 5 measurements (see Verdict above):

1. **Raspberry Pi 5 8GB + TracoPower TEN 8-2411WIN (~$150)** for the
   installation. SVS runs at ~196 FPS on this stack; the question
   "is the CPU/GPU enough?" is answered.
2. **Beelink Mini S13 (~$170)** as an *optional* desk benchmark box —
   useful if you also want a Windows / x86 dev environment or want to
   verify pyEfis behaviour on a different driver stack, but no longer
   required to ship.
3. **Compulab Fitlet 4** only if you want a hardened fanless x86
   installation for non-performance reasons (broader software stack,
   industrial enclosure, native 8-32V DC). Cost is no longer offset
   by a performance need.
4. **Onlogic** is for a TSO / PMA path or for unusually harsh
   installations. Performance is not the deciding factor.

---

## Open questions to resolve while researching

- **12V vs 24V aircraft system**: which one are you building for? Most
  small experimental aircraft are 12V; the answer narrows the power-supply
  choice.
- **Display already chosen?** Many of these mini-PCs come barebones —
  display is a separate ~$100-300 spend. Resolution and brightness drive
  the choice.
- **Performance ceiling target**: the `opengl` tier on Pi 5 runs
  at ~196 FPS, so this question is now resolved unless you're trying
  to drive a very large display (>1080p). Pi 5 is sufficient.
- **Certification path**: experimental amateur-built only? Or any
  expectation of a TSO / PMA path later? The latter changes hardware
  selection significantly (Onlogic territory).
