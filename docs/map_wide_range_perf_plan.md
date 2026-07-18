# Moving map — wide-range render performance plan

Status: PLAN (2026-07-10). Follow-on to the mip pyramid
(`docs/terrain_mip_pyramid.md`), which took wide-range terrain from *tile-bound*
to *render-bound* (300 NM 38 s → 0.38 s, ~99×) — 550 NM now renders faster than
300 NM did before. Goal: push wide / national range as far as is reasonable.
Grounded in `src/pyefis/instruments/map/layers/terrain.py` and `ai/svs.py`
(`TileCache`).

## Results (2026-07-10 — measured, then prototyped)

`tools/bench_map_terrain.py` (offscreen, local pyramid) decomposed the cold
wide-range render and **settled the GPU question with numbers**: the palette /
pixel math is a flat **~0.04 s** at every range, while `_sample` was **14–20 s
cold** and scaled with tile *count* (520 tiles @ 550 NM → 2552 @ 1200 NM), almost
entirely cold file I/O (warm < 0.8 s). So the cost is opening hundreds-to-
thousands of tiny `.mip` files — **GPU shaders would accelerate the 0.04 s and
miss the 15 s.** Ruled out by measurement.

**Fix built + proven: the memory-mapped coarse mosaic** (`tools/
build_terrain_mosaic.py` + `TileCache.get_mosaic` + `TerrainLayer._sample_mosaic`,
all guarded — no mosaic ⇒ old per-tile path). One mmap per level (L4 711 MB,
L5 176 MB, L6 44 MB, stitched from the existing pyramid) sliced in a single
vectorized bilinear. Local bench, centre 39/-106:

| range | tiles | per-tile cold | mosaic cold |
|---|---:|---:|---:|
| 550 NM | 520 | 14.6 s | **0.20 s** |
| 1200 NM | 2552 | 20.4 s | **0.19 s** |
| 2000 NM | 6956 | ~60 s | **0.20 s** |
| 2500 NM | 10856 | ~100 s | **0.19 s** |

Render is now **flat ~0.19 s at any range** — constant-time nationwide zoom.
Verified vs the per-tile path: 0.3–0.9 m mean elevation delta, ~100% water-mask
match (boundary outliers are the mosaic interpolating *across* tile edges where
per-tile edge-clamps — the mosaic is the more-correct one). Moving-map tests: 9
passed, no regression (guarded fallback). **Remaining:** productionize (fold the
mosaic build into `build_terrain_mips` / `make-terrain` so mosaics ship in the
packs) and validate on the Pi. The Tier-1 render tweaks below are now minor
(`rest` ≈ 0.09 s dominates the 0.19 s), kept for reference.

## 1. Where the time actually goes now (read from the code)

The worker `_render` (terrain.py:196) builds a **fixed ~1024² north-up image** —
`n = min(1024, hypot(w,h)·1.25·_RES)`, which does **not** grow with range. So
`_palette`, the `np.gradient` hillshade, and the `QImage` build are **~constant**
cost at any range. Two things are **not** constant:

1. **`_sample` loops over every 1° tile in view** (terrain.py:277,
   `for la in unique(tl): for lo in unique(tn):`) → **O(range²) tiles**: ~256
   blocks at 550 NM (mip 6), more further out. The pyramid made each `get_mip`
   tiny, but each block now covers only ~`1024²/N_tiles` pixels, so the loop is
   **overhead-bound** — per-tile lock + dict + `floor`/`clip` setup + an `np.ix_`
   fancy-index assignment — not compute-bound. **This is the wide-range
   bottleneck.**
2. **`_render` loads a full ~26 MB *native* centre tile every build**
   (terrain.py:211-213) purely to read `tile.shape[0]` (=3601) for the mip-level
   formula. On every tile-boundary crossing that's a 26 MB read + float32 cast for
   a constant — the known "last full-tile read".

The math (n≈1024 constant; ~256 tiny-tile Python iterations at 550 NM) points
squarely at **tile COUNT**, not tile size or the pixel math. §2 confirms before we
touch anything.

## 2. Kill the two-day iteration loop FIRST

The real cost last cycle wasn't the code — it was profile → guess → build →
deploy → observe on the Pi across two days. Two accelerators collapse that:

- **Local offscreen render benchmark (minutes, not days).** The terrain layer is
  pure numpy + `QImage` — **no OpenGL** — so unlike the SVS it renders offscreen
  on Windows. Build `tools/bench_map_terrain.py`: take a real pose (grab one via
  netfix from the Pi), call `TerrainLayer._render` against the local pyramid
  (`D:\EarthData\glo30hgt\.mip`) at 300 / 550 / 800 / 1200 NM, and time each stage
  (sample / palette / gradient / QImage / water). Iterate render-side changes in a
  tight loop; deploy to the Pi only for final on-glass validation.
- **Cheap pyramid rebuilds.** Build-side changes (mosaic tier, RGB overview) now
  rebuild+publish via the container pipeline (`packtools/cloud`) in ~an hour on the
  NAS, not a hand cycle.
- **py-spy `--gil` on the Pi** (the tool that nailed #89) to cross-check the local
  decomposition on real hardware, once per candidate.

**Phase 0 deliverable:** a decomposition table (stage × range) that ranks the real
hotspots. Everything below is a hypothesis until that table exists.

## 3. Candidates, ranked by impact ÷ effort

### Tier 1 — render-side only (no rebuild; iterate locally in minutes)
1. **Drop the per-render native centre-tile load** (terrain.py:211-213). Cache the
   native side after first use (or `os.path.getsize` a tile, or infer from any
   cached mip tile's decimation). Removes a 26 MB read + cast on every crossing.
   Trivial, pure win.
2. **Replace the O(range²) tile loop with one vectorized gather** (`_sample`). At a
   given mip level every in-view tile shares one side `nn`, so assemble the needed
   coarse tiles into a single contiguous **mosaic array** once, then do ONE global
   bilinear sample over the whole 1024² grid — killing the Python double-loop and
   the per-block `np.ix_`. Fetch the tiles under a single lock while you're there.
   **Expected the biggest render-side win.**
3. **int16-direct sampling.** `load_tile` casts every tile to float32
   (svs.py:213); instead sample the `>i2` directly and cast only the 1024² output.
   Removes the cast across all in-view tiles.

### Tier 2 — build-side (rebuild pyramid; validate on Pi)
4. **Coarse mosaic / super-tile tier.** Pre-stitch the deepest levels into
   multi-degree tiles (e.g. 4°–8° blocks, or per-region continental mosaics) so a
   national view touches a handful of files, not hundreds. Attacks tile COUNT at
   the source and makes candidate 2 nearly free. A natural extension of
   `build_terrain_mips.py`.
5. **Precomputed RGB overview (the endgame).** Hillshade is fixed NW-light and the
   palette is fixed, so bake palette + hillshade into coarse **RGB** overview tiles
   at build time. Wide-range render then becomes a *blit* — no sample/palette/
   gradient at all — i.e. **O(1) regardless of range**, like a web-map basemap.
   Biggest win, biggest change; do it if Tier 1 + #4 still fall short. Renderer
   picks the RGB overview above a range threshold, elevation tiles below.

### Tier 3 — paint path (only if it profiles hot)
6. **Quantized-angle rotated-blit cache.** `paint` rotates + blits the 1024² image
   every frame (terrain.py:143-147); on the Pi's software raster that can cost.
   Cache the rotated result at quantized headings. Lower priority — the image is
   already worker-cached and paint is once-per-frame.

## 4. Sequencing

P0 instrument (local bench + py-spy) → P1 candidate 1 → re-measure → P2 candidate 2
→ re-measure → P3 candidate 3 → if wide range still short: P4 mosaic tier → P5 RGB
overview. Ship render-side changes to `display-changes`; validate each build-side
change on the Pi with the §2 recipe.

## 5. Guardrails
- **Caution mode needs live elevation** (TAWS tint, terrain.py:218-225), so an RGB
  overview (#5) is relief-mode-only — keep the elevation path for caution + close
  range.
- Keep refactors **bit-comparable** where possible (the pyramid work showed
  byte-identical checks catch regressions instantly).
- `_mip_max = 512` already holds a national working set; revisit if #4 changes tile
  counts.
- The water overlay (`_draw_water`) is already worker-side / zero per-frame — any
  mosaic or RGB change must preserve that property.
