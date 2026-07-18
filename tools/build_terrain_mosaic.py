#!/usr/bin/env python3
"""Stitch the per-degree mip tiles into one memory-mappable coarse MOSAIC per
level (prototype for docs/map_wide_range_perf_plan.md).

The wide-range bottleneck (measured by tools/bench_map_terrain.py) is COLD I/O:
_sample opens hundreds-to-thousands of tiny .mip/<L>/ files per render. A mosaic
replaces that with ONE file per level: the renderer memory-maps it and slices the
window in a single vectorized bilinear -- no per-file opens, no per-tile loop.

Output (beside the pyramid the renderer already reads):
    <tile_root>/.mip/mosaic/L<level>.hgt    raw big-endian int16, shape rows x cols
    <tile_root>/.mip/mosaic/L<level>.json   {level, rows, cols, spd, lat_n, lon_w}

Row r -> lat = lat_n - r/spd ; col c -> lon = lon_w + c/spd. Voids are stored as
the water sentinel so coastal bilinear matches load_tile. Run on a workstation.

    python tools/build_terrain_mosaic.py <tile_root> [--levels 4 5 6]
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np

SRTM3_VOID = -32768
_WATER_SENTINEL = -9999          # matches ai/svs.py load_tile (float -9999.0)
_NAME = re.compile(r"([NS])(\d+)([EW])(\d+)")


def _coord(stem: str):
    m = _NAME.match(stem.upper())
    la = int(m.group(2)) * (1 if m.group(1) == "N" else -1)
    lo = int(m.group(4)) * (1 if m.group(3) == "E" else -1)
    return la, lo


def build_level(root: Path, level: int):
    mip_dir = root / ".mip" / str(level)
    tiles = sorted(mip_dir.glob("[NS]*/*.hgt"))
    if not tiles:
        print(f"  L{level}: no tiles under {mip_dir}")
        return None
    coords = [_coord(p.stem) for p in tiles]
    lat_s = min(c[0] for c in coords)
    lat_n = max(c[0] for c in coords) + 1        # north edge lat of row 0
    lon_w = min(c[1] for c in coords)            # west edge lon of col 0
    lon_e = max(c[1] for c in coords) + 1
    raw0 = np.fromfile(tiles[0], dtype=">i2")
    nn = int(round(raw0.size ** 0.5))
    spd = nn - 1                                 # samples per degree (shared edge)
    rows = (lat_n - lat_s) * spd + 1
    cols = (lon_e - lon_w) * spd + 1
    mos = np.full((rows, cols), SRTM3_VOID, dtype=">i2")
    for p, (la, lo) in zip(tiles, coords):
        raw = np.fromfile(p, dtype=">i2")
        if raw.size != nn * nn:
            continue
        t = raw.reshape(nn, nn)
        r0 = (lat_n - (la + 1)) * spd
        c0 = (lo - lon_w) * spd
        mos[r0:r0 + nn, c0:c0 + nn] = t          # shared edges overwrite identically
    mos[mos == SRTM3_VOID] = _WATER_SENTINEL
    out_dir = root / ".mip" / "mosaic"
    out_dir.mkdir(parents=True, exist_ok=True)
    mos.tofile(out_dir / f"L{level}.hgt")
    meta = {"level": level, "rows": rows, "cols": cols, "spd": spd,
            "lat_n": lat_n, "lon_w": lon_w}
    (out_dir / f"L{level}.json").write_text(json.dumps(meta))
    print(f"  L{level}: {rows}x{cols} ({mos.nbytes/1e6:.0f} MB)  "
          f"lat {lat_s}..{lat_n} lon {lon_w}..{lon_e}  spd={spd}")
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build coarse terrain mosaics.")
    ap.add_argument("tile_root")
    ap.add_argument("--levels", type=int, nargs="*", default=[4, 5, 6])
    args = ap.parse_args(argv)
    root = Path(args.tile_root)
    print(f"root={root}  levels={args.levels}")
    for lv in args.levels:
        build_level(root, lv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
