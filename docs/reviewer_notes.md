# Reviewer notes: what changed vs. master, and where it's been exercised

Companion to the pyEFIS landing PR and the
[validation checklist](validation_checklist.md). This is the "where to poke"
map for a reviewer: the behavioral deltas from `master`, the risk areas, and an
honest account of what hardware/data combinations have actually been run (empty
cells are untested, not implied-passing).

## Behavioral changes vs. master

Grouped by subsystem. "Existing users" = someone already running a standard
PFD/EMS panel who updates to this build.

| Subsystem | Change | Effect on existing users |
|---|---|---|
| **Synthetic Vision (SVS)** | New GL terrain renderer + nav-data backends | **None** — ships `enabled: false`, GL-required; annunciates "SVS UNAVAIL" without a GPU. Opt-in. |
| **Moving map** | New layered map screen + range/orientation/terrain controls | **None** unless a map screen is configured. Controls need the fix-gateway map keys (FIX-Gateway #204). |
| **Attitude (AI)** | 30 Hz frame clock decoupled from FIX bursts; interpolated/dead-reckoned pose | Same data, smoother motion. No config change. |
| **HSI / nav-source** | Heading-bug + course-pointer + nav-source select | **Behavioral:** the nav-source `select()` now **flags the needle failed when the selected source is absent/invalid** instead of showing the previously-selected source's stale value. Honest "no source" vs. a silently wrong indication. (Pairs with FIX-Gateway #203.) |
| **Editor / schema exporter** | `editor/schema.py`, `resolver.py`, `groups.py` | None at runtime — offscreen tooling. |
| **Data Status screen** | New nav-data currency screen | New optional screen; shows "no data" states gracefully when packs are absent. |
| **Instrument fixes** | altimeter, numeric/value_text formatting | Bug fixes (decimals/units render correctly); low risk. |
| **Config default** | `includes/ahrs/svs.yaml` now ships SVS `enabled: false` | A stock config that previously auto-enabled SVS on the AI-only screen now needs an explicit `enabled: true`. Managed (configurator-provisioned) devices are unaffected — the updater injects the svs block. |
| **Dependencies** | `numpy`/`PyOpenGL` moved to an optional `svs` extra; PyQt6 in `qt` extra | Base install unchanged. Source installs need `pip install -e '.[qt,svs]'` (see [running_from_source.md](running_from_source.md)). |

## Risk areas worth poking

1. **SVS/GL on your specific GPU/driver** — the renderer targets Pi VideoCore via
   EGL; desktop GPUs and drivers vary. Most likely place for surprises.
2. **Moving-map performance / pan** on lower-power devices.
3. **Screen layout at non-standard resolutions** — clipping/overlap.
4. **Instrument formatting** (decimals, units) with real vs. test data.
5. **Graceful degradation** — no GPU, no terrain data, no fix-gateway. These MUST
   NOT crash (they are the checklist's Part D).

## Where it's been exercised (seeded — maintainer to complete)

Honest coverage map. A blank cell is an untested combination — the point of this
table is to make the gaps visible, not to imply coverage. `~` = partial /
informal. Please fill in before/at review.

| Environment | Boots | Core screens (PFD/EMS) | Moving map | SVS terrain | Degradation (no GPU / data / gw) |
|---|---|---|---|---|---|
| Pi 5 (test bench) | yes | yes | ~ | ~ | ~ |
| Pi 4 | | | | | |
| Desktop Linux + discrete GPU | | | | | |
| Laptop + integrated GPU | | | | | |
| Laptop, software render (no GPU) | | | | | (expect "SVS UNAVAIL") |
| Field aircraft (real panel, in flight) | | | | | |

Data sources exercised (fill in): X-Plane `~`, Stratux `~`, Garmin GNX `~`, live CAN-FIX ___.

> Maintainer: replace `~`/blanks with yes/no from actual runs. The blanks are
> the honest answer to "does it work in environments other than mine?" —
> and the reason the [validation checklist](validation_checklist.md) exists.
