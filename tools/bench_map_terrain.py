#!/usr/bin/env python3
"""Offscreen benchmark + decomposition for the moving-map terrain layer.

The map terrain layer is pure numpy + QImage (no OpenGL), so its worker render
(``TerrainLayer._render``) runs offscreen on a workstation against the local mip
pyramid -- no Pi, no display. This times the render at several ranges, COLD
(tiles loaded from disk) and WARM (caches hot), and decomposes it into the tile
sampling loop vs the palette vs everything else, alongside the in-view tile count
and selected mip level. These are the numbers behind
``docs/map_wide_range_perf_plan.md`` -- run it before and after each render-side
change to see the effect in seconds instead of a two-day Pi deploy cycle.

Run (Windows, deps on C:/pylib):
    PYTHONPATH="C:/pylib;src" python tools/bench_map_terrain.py \
        --tiles D:/EarthData/glo30hgt --lat 39 --lon -106
"""
import argparse
import math
import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # no display needed
import numpy as np


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tiles", default="D:/EarthData/glo30hgt",
                    help="HGT tile tree (must hold the .mip pyramid)")
    ap.add_argument("--lat", type=float, default=39.0)
    ap.add_argument("--lon", type=float, default=-106.0)
    ap.add_argument("--ranges", type=float, nargs="*",
                    default=[160, 300, 550, 800, 1200],
                    help="range_nm values to benchmark")
    ap.add_argument("--w", type=int, default=1000, help="map widget width px")
    ap.add_argument("--h", type=int, default=700, help="map widget height px")
    ap.add_argument("--repeat", type=int, default=1,
                    help="render N times per cell, report the fastest")
    ap.add_argument("--water", default="",
                    help="water db path (enables the _draw_water overlay)")
    args = ap.parse_args(argv)

    from PyQt6.QtGui import QGuiApplication
    _app = QGuiApplication([])                 # QImage needs an app instance

    import pyefis.instruments.map.layers.terrain as tmod
    from pyefis.instruments.ai.camera import M_PER_DEG_LAT

    class Owner:
        tile_path = args.tiles
        terrain_mode = "relief"
        water_db_path = args.water              # "" skips the water overlay
        water_max_vertices = 512

    layer = tmod.TerrainLayer()
    layer.configure(Owner())
    layer._alt_ft = 0.0
    cy = args.h

    def plan(range_nm):
        """Replicate _render's sizing so we can report n / mpp / mip / tiles."""
        px_per_m = max(1.0, cy) / max(1.0, range_nm * 1852.0)
        half_diag_m = 0.5 * math.hypot(args.w, args.h) / px_per_m * 1.25
        n = int(min(1024, max(64, 2 * half_diag_m * px_per_m * layer._RES)))
        mpp = 2 * half_diag_m / n
        lat_cos = math.cos(math.radians(args.lat))
        idx = np.arange(n) - (n - 1) / 2.0
        lats = args.lat + (-idx * mpp) / M_PER_DEG_LAT
        lons = args.lon + (idx * mpp) / (M_PER_DEG_LAT * lat_cos)
        tiles = (len(np.unique(np.floor(lats).astype(int)))
                 * len(np.unique(np.floor(lons).astype(int))))
        native = M_PER_DEG_LAT / 3600.0
        mip = max(0, min(6, int(round(math.log2(max(1.0, mpp / native))))))
        return n, mpp, mip, tiles

    def timed_render(range_nm, cold):
        """One _render, with _sample and _palette wrapped to accumulate time."""
        if cold:
            c = layer._cache
            for d in (c._mip, c._cache):
                d.clear()
            c._mip_order.clear()
            c._order.clear()
            if hasattr(c, "_mosaic"):
                c._mosaic.clear()          # force re-mmap for a fair cold row
        acc = {"sample": 0.0, "palette": 0.0}
        orig_s = tmod.TerrainLayer._sample
        orig_p = tmod._palette

        def ts(self, *a, **k):
            t = time.perf_counter()
            r = orig_s(self, *a, **k)
            acc["sample"] += time.perf_counter() - t
            return r

        def tp(*a, **k):
            t = time.perf_counter()
            r = orig_p(*a, **k)
            acc["palette"] += time.perf_counter() - t
            return r

        tmod.TerrainLayer._sample = ts
        tmod._palette = tp
        try:
            job = (None, args.lat, args.lon, range_nm, args.w, args.h, cy)
            t0 = time.perf_counter()
            layer._render(job)
            total = time.perf_counter() - t0
        finally:
            tmod.TerrainLayer._sample = orig_s
            tmod._palette = orig_p
        return total, acc["sample"], acc["palette"]

    print(f"tiles={args.tiles}  centre=({args.lat},{args.lon})  "
          f"screen={args.w}x{args.h}\n")
    hdr = (f"{'range':>6} {'n':>5} {'mip':>3} {'tiles':>6} "
           f"{'cold_s':>8} {'warm_s':>8} {'sample_s':>9} {'palette_s':>9} {'rest_s':>7}")
    print(hdr)
    print("-" * len(hdr))
    for rng in args.ranges:
        n, mpp, mip, tiles = plan(rng)
        # cold once (first touch), then warm (fastest of --repeat)
        cold, cs, cp = timed_render(rng, cold=True)
        warm = min(timed_render(rng, cold=False)[0] for _ in range(args.repeat))
        rest = cold - cs - cp
        print(f"{rng:>6.0f} {n:>5} {mip:>3} {tiles:>6} "
              f"{cold:>8.3f} {warm:>8.3f} {cs:>9.3f} {cp:>9.3f} {rest:>7.3f}")
    print("\ncold = first render at this range (tiles read from disk); "
          "warm = caches hot.")
    print("sample = _sample tile loop | palette = _palette | "
          "rest = gradient + QImage + centre-tile read + overhead.")
    print("If cold >> warm and sample dominates -> tile I/O + Python-loop bound "
          "(GPU shaders would not help; mosaic/vectorize/precompute-RGB would).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
