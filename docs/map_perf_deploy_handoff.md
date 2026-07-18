# Handoff: ship the wide-range map performance work to all users

Status: 2026-07-10. The wide-range moving-map performance work (terrain mosaic +
water range-cap + Great Lakes) is **proven and live on Bill's bench Pi only**.
This doc is what a fresh thread needs to get it to every user. Companion:
`map_wide_range_perf_plan.md` (the profiling + design), `terrain_mip_pyramid.md`,
makerplane-data `docs/terrain.md`.

> **UPDATE 2026-07-10 — §3.1 RESOLVED in the cloud, not on the device.** The
> mosaic now ships as a **national `terrain-mosaic` pack built by the cloud
> pipeline** (makerplane-data `packtools/cloud/entrypoint.sh`: mips → mosaic
> stitch → region packs → mosaic pack → verify), so **no on-device build step is
> needed** — this supersedes the Option A/B decision below. `make-terrain
> --mosaic` packages `.mip/mosaic/`, the updater auto-tracks it with any terrain
> region, and it unzips into `terrain/tiles/.mip/mosaic/` for `get_mosaic()` with
> zero renderer change. Region packs also now ship compressed. Landed on
> makerplane-data `dev`. **Remaining:** run the QNAP container to publish
> (§3.5 clean-device verify still applies), then §3.3 branch promotion + §3.4
> tests + §3.6 bench reconcile. §3.2 big-water is still optional/deferred.

## 1. What's done, and exactly where it lives

**Code — pushed to `billmallard/pyEfis` branch `dev`** (NOT master/release):

| commit | what |
|---|---|
| `f2a48c9` | `build_terrain_mips.py` parallelized (`--jobs`) |
| `44e8e59` | terrain **mosaic**: `tools/build_terrain_mosaic.py`, `TileCache.get_mosaic`, `TerrainLayer._sample_mosaic`, `tools/bench_map_terrain.py`, `docs/map_wide_range_perf_plan.md` |
| `2623de8` | water overlay hard range-cap (superseded by a652de1) |
| `a652de1` | `WaterDB.polygons_in_range(drop_ocean=)`; water tiered by range |
| `7fa3849` | range-scaled wide-range lake size floor (Great Lakes above 300 NM) |

**Data — on the bench Pi only, NOT in packs:**
- Terrain mosaics `/data/makerplane-data/terrain/tiles/.mip/mosaic/L{4,5,6}.{hgt,json}`
  built on-device with `build_terrain_mosaic.py` (CONUS extent; ~9/36/143 MB).
- No "big water" index exists yet (proposed, §3.2).

**Deployment reality:** the bench Pi runs a **patched** `~/pyEfis` (`git apply`,
base `bcc11a4`) with `.bak-pre-mosaic` backups, not a clean `dev` checkout. Other
devices have **none** of this.

## 2. The gap: what "deployed to all users" requires

Two independent things must reach a user's device:
1. **The render code** — needs to land on the branch users actually run
   (`master` / a release), then eventually the upstream pyEfis PR.
2. **The mosaic data** — a device must have `.mip/mosaic/` beside its `.mip` tree,
   or `get_mosaic` returns None and it stays slow. **This is the crux** and drives
   the main design decision below.

## 3. Work items

### 3.1 Get the mosaic onto every device — DONE (national pack, cloud-built)
The mosaic is a **whole-extent stitched file per level**, but terrain packs are
**per-region** and devices **union** whatever regions they opted into — so a
per-region mosaic piece can't be stitched back into one file on-device.

**Resolved: ship ONE national `terrain-mosaic` pack, built in the cloud.** A
single whole-extent mosaic is the only artifact that is both cloud-built *and*
correct for any region combination. Implemented (makerplane-data `dev`):
- **`build_terrain_mosaic.py`** runs in the cloud pipeline right after the mip
  build (`entrypoint.sh` step 2), stitching `.mip/mosaic/L{4,5,6}` from the full
  tree (seconds).
- **`packtool make-terrain --mosaic`** (`packtools/make_terrain.build_mosaic_pack`)
  packages `.mip/mosaic/*` into `terrain-mosaic-<edition>.pack`, tagged with the
  synthetic region `mosaic` (isolates tile provenance from the real region packs).
- **Updater auto-tracks it** whenever any terrain region is tracked
  (`core._tracked_ids`); it unzips into `terrain/tiles/.mip/mosaic/`, which
  `TileCache.get_mosaic()` reads with **zero renderer change** (absent ⇒ per-tile
  fallback).

This replaces the earlier on-device-build idea (which needed numpy in the updater
venv + a path to the pyEfis tool + a stale-aware hook — all avoided). Devices with
a us-west-only selection do download the national mosaic (~200–300 MB compressed),
which is exactly the data national zoom needs. **Next: run the QNAP container to
publish, then verify §3.5.**

### 3.2 (Optional) big-water index — instant wide-range water
Wide-range water is currently query-bound (~2.3 s @ 2500 NM: SQLite scans a
2.15 M-polygon R-Tree over a huge bbox). To make it instant, build a **pre-filtered
side table** of only large bodies (`bbox diag >= ~0.5°`, ~46k rows) with its own
R-Tree; `WaterDB.polygons_in_range` queries it when `drop_ocean`/wide. Same
on-device-vs-pack decision as §3.1 — recommend building it on-device from
`water.sqlite` post-update (a one-time `CREATE TABLE … WHERE size>=? ` + rtree).
Deferred: current 0.35–2.5 s is smooth enough (Bill signed off); do this only if
wide-range water instantness is wanted.

### 3.3 Branch promotion
Render code is on `dev`. Promote `dev → qa → master` (forward-only, per
`makerplane-data/docs/environments.md`). **Caution:** master promotion was being
held to protect the open **upstream pyEfis PR #274** — check that's resolved
before promoting, or cherry-pick the map commits onto a clean branch for the
upstream PR. Final reach = an upstream PR to Phil Birkelbach's pyEfis.

### 3.4 Tests
Add unit coverage (only the offscreen bench guards this today):
- `get_mosaic` / `_sample_mosaic`: build a tiny 2-tile mosaic in a tmp tree,
  assert the mosaic sample matches the per-tile sample (the 0.3–0.9 m check we did
  by hand) and that absent-mosaic falls back.
- Water tiering: assert `drop_ocean` + range-scaled floor reduce the poly set
  above `_WATER_FULL_MAX_NM`.
Existing `tests/instruments/test_moving_map.py` is green (9) incl. the water fake
updated for the `drop_ocean` kwarg.

### 3.5 Clean-device end-to-end verification
The real proof for *other* users: on a **clean** device (not the patched bench),
`pyefis-data update` → confirm `.mip/mosaic/` gets built (§3.1) → pinch to
nationwide → verify ~0.2 s render (use `tools/bench_map_terrain.py --water <db>`
on-device; it must exercise water, that's how the 30 s hid originally).

### 3.6 Reconcile the bench Pi (housekeeping)
Once the code is on master, replace the bench Pi's patched `~/pyEfis` with a clean
checkout (backups `.bak-pre-mosaic` exist). Not urgent — it works as-is.

## 4. Reference (so the next thread has the keys)

- **Bench Pi:** `ssh wpballard@10.110.10.189` (alias `pyefis` resolves flakily —
  use the IP; `scp` is broken on the workstation, use `cat file | ssh … 'cat >…'`).
  pyEfis is a **user** service: `systemctl --user restart pyefis.service`
  (set `XDG_RUNTIME_DIR=/run/user/1000`; not sudo, not the system service). Deps in
  `~/pyEfis/.venv`; run tools with `.venv/bin/python … PYTHONPATH=src
  QT_QPA_PLATFORM=offscreen`. Tile tree `/data/makerplane-data/terrain/tiles`
  (CONUS only, lat24-49/lon-125..-66); water `/data/makerplane-data/water/current/water.sqlite`.
- **Workstation:** GLO-30 `.hgt` tree `D:\EarthData\glo30hgt` (+ full-NA mosaics
  under `.mip/mosaic`); deps on `C:\pylib` (`PYTHONPATH="C:/pylib;src"`).
- **Key constants** (`map/layers/terrain.py`): `_WATER_FULL_MAX_NM=300`,
  `_WATER_WIDE_DIAG_PER_NM=0.001`, `_WATER_WIDE_DIAG_MAX=3.0`; mip clamp `0..6`.
- **Water DB fact:** all rows `kind='water'`, `elev_ft=NULL` — size is the only
  discriminator (don't rely on the schema docstring's ocean/lake/river).
- **Bench:** `tools/bench_map_terrain.py --tiles <tree> --water <db> --lat --lon
  --ranges … --repeat 3` — offscreen render decomposition (sample/palette/rest),
  cold vs warm.

## 5. Recommended order
1. ~~§3.1 mosaic to every device~~ **DONE** — national `terrain-mosaic` pack in
   the cloud pipeline (makerplane-data `dev`). Run the QNAP container to publish,
   then verify §3.5 on a clean device.
2. §3.4 tests (mosaic-pack + auto-track tests landed; the `_sample_mosaic`
   vs per-tile equivalence + water-tiering unit tests are still open),
   §3.3 branch promotion (mind PR #274), upstream PR.
3. §3.2 big-water index only if wide-range water instantness is wanted.
4. §3.6 reconcile the bench Pi.
