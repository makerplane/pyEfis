# Terrain mip pyramid — specification

Status: SPEC (2026-07-08). Development not started. Cross-repo: the **pyEfis**
renderer (`get_mip`) and the **makerplane-data** terrain pack (pre-built coarse
levels). Driven by the moving-map high-range perf benchmark (§2). Companion specs:
`moving_map_spec.md`, `svs_rendering.md`, makerplane-data `docs/terrain.md`.

## 1. The problem

The moving map is unusable at wide (national) range. Benchmarked on the Pi 5:
**300 NM ≈ 38 s**, **160 NM ≈ 21 s** to render terrain. Bill wants to support
zooming out to the national level; that is impossible with the current tile path.

Root cause (measured, §2): the renderer loads and converts **entire native 3601²
tiles** to pull a sparse sample from each. At 300 NM a 1° tile lands on ~54×54
screen pixels, so **~0.02 %** of every tile's 13 M points is used — the other
~97 % of the work is thrown away. Cost is ~half disk, ~half per-tile CPU, and it
scales with area (~range²).

**Fix:** a **pre-built mip pyramid** shipped in the terrain pack — coarse,
downsampled tiles stored beside the native ones, so a wide view reads a handful of
tiny tiles instead of hundreds of 26 MB tiles. Terrain is bulk/static, built once
per edition on a workstation (makerplane-data `docs/terrain.md`), which is exactly
where the pyramid should be generated.

## 2. Evidence — the benchmark

Read-only, decomposed, cold, fresh regions (Pi 5, M.2, `/data/.../terrain/tiles`):

| phase | 160 NM | 300 NM |
|---|---:|---:|
| total | 21.3 s | 38.1 s |
| `fromfile` (disk) | 11.5 s (54 %) | 20.9 s (55 %) |
| `.astype(float32)` — byteswap + cast (CPU) | 7.2 s (34 %) | 12.7 s (33 %) |
| void-mask (CPU) | 2.0 s (9 %) | 3.6 s (9 %) |
| **actual render** (sample + palette + hillshade + image) | 0.6 s (3 %) | **0.9 s (2 %)** |
| tiles / disk read | 193 / 5.0 GB | 357 / 9.3 GB |

- The M.2 runs at ~440 MB/s — Gen2 ×1 **saturated, not slow** — but that is only
  ~55 % of the time. The other ~43 % is `load_tile` converting each full tile
  (`.astype(float32)` byteswaps + casts 13 M elements; then a void-mask sweeps
  13 M more). Neither half is a "faster disk" problem.
- The actual drawing is **0.9 s**. Everything else is loading/converting data that
  is immediately discarded.
- Scales ~range². True national (~1000 NM) ≈ **~4000 tiles / ~100 GB / ~7 min** —
  infeasible by construction, not a tuning problem.

(Benchmark scripts were `map_terrain_bench*.py`, run on the Pi; the numbers above
are the record.)

## 3. Why pre-built (not on-the-fly)

A pyramid can be built two ways:

- **On-the-fly** — `get_mip` downsamples on first load and caches the coarse array.
  Simple, but the *first* wide zoom still reads and converts one full 26 MB tile
  per tile in view (still ~38 s at 300 NM); only re-renders are fast.
- **Pre-built (this spec)** — coarse levels are generated once per edition and
  shipped in the pack. The Pi **never touches a 26 MB tile for a wide view** — it
  reads the small coarse file directly, so even the first zoom is fast. This is the
  proper fix for the bulk/static data shape.

## 4. Key enabler — the tile path is already resolution-agnostic

`load_tile` (svs.py) **infers the grid side from the file size** ("any square side
is accepted"), and `_sample` keys off `nn = t.shape[0]`. So a downsampled tile is
just a **smaller square big-endian `>i2` `.hgt`** that the *existing* read + sample
path handles with no changes. The pyramid needs **no new tile format** — only
smaller files and a lookup by level. This is why the flat top-down map is far
simpler than the abandoned SVS 3D clipmap (Track-1c): a per-level tile pick, no
morphing, no swim.

## 5. On-disk layout (pack and Pi)

Native tiles stay where they are (level 0). Coarse levels go in a parallel tree:

```
  terrain/tiles/<NSdir>/<name>.hgt              # native, 3601^2 (level 0)
  terrain/tiles/.mip/<L>/<NSdir>/<name>.hgt     # coarse level L (proposal)
```

Each level's side must keep clean grid registration so tiles still abut (GLO-30 is
pixel-is-point with shared edges: 3601 = 3600 intervals + 1). Decimating by a
factor `f` that **divides 3600** yields `3600/f + 1` points with corners preserved.
A candidate ladder (exact divisors of 3600):

| level | decimation `f` | side | pitch | bytes/tile |
|---|---:|---:|---:|---:|
| 0 (native) | 1 | 3601 | ~30 m | 26 MB |
| 1 | 4 | 901 | ~123 m | 1.6 MB |
| 2 | 16 | 226 | ~490 m | 102 KB |
| 3 | 48 | 76 | ~1.5 km | 11 KB |
| 4 | 144 | 26 | ~4.4 km | 1.4 KB |

That set adds ~**1.7 MB per native tile (~+6 %)** — NA ≈ +5–6 GB (R2 storage is
cheap, zero egress). A denser pyramid (add `f=2` @ 1801², `f=8` @ 451²) gives
smoother LOD for the 40–160 NM band at ~+33 % (~+30 GB). Level set is a decision
(§10.1). At 300 NM the renderer would pick level 2–3 (~490 m–1.5 km) — the whole
national window then totals a few MB instead of ~100 GB.

## 6. Renderer changes (pyEfis)

- **`TileCache.get_mip(lat, lon, level)`** — level 0 → the existing native `get`;
  level ≥ 1 → `load_tile` from `.mip/<L>/…`, cached. If the level file is absent
  (an old edition with no pyramid), **fall back to native** (or an on-the-fly
  downsample) so old packs still work — just slow at range. `terrain.py` already
  calls `get_mip` behind `hasattr(self._cache, "get_mip")`.
- **Level clamp** — `terrain.py` currently `mip = max(0, min(4, log2(mpp/native)))`.
  Raise the ceiling to the deepest built level; keep the same selection formula.
- **Cache sizing** — coarse tiles are tiny, so a right-sized (or separate) coarse
  cache holds a whole national window resident → pans and re-renders are instant.
  (Today `TileCache(max_tiles=9)` thrashes at hundreds of tiles.)
- **Optional, complementary:** sample the `>i2` tile directly and cast only the
  output grid, dropping the per-tile `.astype(float32)` (~33 % of native cost) even
  before the pyramid — a cheap interim win (§9 P4).

## 7. Pack builder changes (makerplane-data)

- **`make_terrain` / `build_region_pack`** — for each native tile, generate levels
  1..N and write them into the region zip under `.mip/<L>/…` next to the native
  tile. Native tiles remain byte-identical.
- **Downsample** — block-mean over each `f×f` block (anti-aliased), **void-aware**
  (exclude/propagate `SRTM3_VOID` so coarse cells over data voids don't average
  garbage), output big-endian `>i2`, preserving corner registration (the
  `3600/f + 1` sizing of §5).
- **Manifest / pack_meta** — record the pyramid (`mip_levels: [...]` or a flag) so
  the updater and renderer know it is present. This is new pack *content*, same
  pack *kind* (`terrain`); if it changes the manifest **schema**, follow the
  makerplane-data rule (merge the schema/updater change to `main` before the first
  R2 publish). A path convention (`.mip/<L>/`) with no manifest change avoids that
  gate entirely — a decision (§10.4).
- Build a pyramid-enabled edition; publish region-by-region as today.

## 8. Delivery (Pi)

`pyefis-data update` unzips the `.mip/` tree alongside the native tiles (regions
union as today). Extra footprint is the §5 level-set overhead (~+6 % or ~+33 %).
**Backward compatible:** a Pi on an old edition keeps working via the native
fallback (§6) — it just stays slow at range until it pulls the pyramid edition.

## 9. Phases

- **P1 — Renderer.** `get_mip` + coarse cache + raised clamp, reading a
  **locally-built** pyramid; prove the win on the Pi by re-running the §2
  benchmark (target: 300 NM well under 1 s). No pack/manifest changes yet.
- **P2 — Builder.** Pyramid generation in `make_terrain` (downsample + `.mip/`
  layout + manifest note); build and publish a pyramid-enabled terrain edition.
- **P3 — Deploy + verify.** Pi pulls the pyramid edition; verify national zoom
  on-glass; tune the level set and cache size against real use.
- **P4 — (optional) interim + adjacencies.** The `>i2`-direct sampling win (§6);
  raise the vector-layer range caps / add the high-altitude enroute tier (major
  airports + VORs) so wide views show nav data, not just terrain — *separate*
  layer work, tracked apart from this pyramid.

## 10. Decisions (Bill, 2026-07-08)

1. **Level set — DENSE.** Full 2×-per-level pyramid, levels 1–6 (`f = 2^k`,
   ~+33 %, ~+30 GB all-NA). R2 is zero-egress (~pennies/mo), and dense buys smooth
   zoom **easing** (a planned cool-factor touch): smaller detail "pops" at level
   changes, less mid-animation blur, and it keeps the door open for LOD cross-fade
   (trilinear blend between adjacent levels) later. The coarse ladder was only the
   minimum to unblock national; dense is the low-regret pick.
2. **Layout — parallel `.mip/<L>/` tree.** `<tile_root>/.mip/<L>/<NSdir>/<name>.hgt`.
   Already what `get_mip` reads; unions across regions like native; `load_tile`
   reuses with a different root; dot-prefix stays out of the way.
3. **Downsample — anti-aliased.** Node-centred box average (corner-registered,
   void-aware), not plain subsampling.
4. **Manifest — pure path convention.** No manifest/pack_meta schema field; the
   `.mip/` files just ride in the region zip and the renderer discovers them by
   trying to read (native fallback if absent). No merge-before-publish gate.
5. **Cache — grow as needed.** The coarse cache holds a national working set
   (`_mip_max = 512` small tiles); grow further if a use case needs it.
6. **Interim `>i2`-direct sampling** — optional, deferred (P4); the pyramid already
   removes the per-tile cast for wide views.

## 11. Non-goals

- **Not** the SVS 3D clipmap (Track-1c, abandoned for swim/perf). This is the flat
  top-down map: a per-level tile pick, no morphing.
- **Not** a new tile format — coarse levels are ordinary square `>i2` HGT files.
- **Not** the high-altitude enroute vector tier — wanted, but separate layer work
  (§9 P4).
