#!/usr/bin/env python3
"""
Convert Copernicus GLO-30 GeoTIFF tiles to 1-arc-second HGT tiles.

P6 of docs/svs_structural_plan.md. Output is the SRTM HGT layout the
pyEfis TileCache already reads — big-endian int16, square, row 0 at the
north edge — at 3601x3601 samples (1 arc-second), written into the
``<NS-dir>/<name>.hgt`` tree the tile loader searches.

GLO-30 wrinkles handled here:

- Tiles are NOT square above 50 deg latitude: column counts shrink as
  meridians converge (3600 / 2400 / 1800 / 1200 / 720 / 360 for the
  50/60/70/80/85 bands). Columns are linearly resampled to 3600 so the
  output grid is regular — this is what makes the >60N Canada coverage
  actually usable by the renderer.
- GLO grids span [edge, edge+1) — the eastern column and southern row
  that an edge-inclusive 3601-sample HGT needs belong to the neighbour
  tiles. The converter reads them when the neighbour GeoTIFF is present
  and duplicates the last row/column otherwise (a one-sample flat spot
  at the seam, invisible at SVS scales).
- Heights are float32 metres (EGM2008); rounded to int16 like SRTM.
  GLO-30 has no voids — ocean is real values (0.0) inside coastal
  tiles, and open-ocean tiles simply don't exist (which the renderer
  already treats as water).

Usage:
    python tools/convert_glo30.py --src D:/EarthData/glo30 \
        --dest D:/EarthData/glo30hgt [--workers 4] [--tiles N60W136 ...]
"""

import argparse
import concurrent.futures
import os
import re
import sys

import numpy as np

NAME_RE = re.compile(
    r"Copernicus_DSM_COG_10_([NS])(\d+)_00_([EW])(\d+)_00_DEM")
OUT_SAMPLES = 3601


def tile_name(lat, lon):
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}"


def glo_name(lat, lon):
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return (f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_"
            f"{ew}{abs(lon):03d}_00_DEM")


def resample_columns(arr, out_cols=3600):
    """Linearly resample each row to *out_cols* (high-latitude GLO
    tiles carry fewer columns over the same 1-degree span)."""
    rows, cols = arr.shape
    if cols == out_cols:
        return arr
    x_dst = np.arange(out_cols) * (cols / out_cols)
    x_src = np.arange(cols, dtype=np.float64)
    out = np.empty((rows, out_cols), dtype=arr.dtype)
    for i in range(rows):
        out[i] = np.interp(x_dst, x_src, arr[i])
    return out


def build_hgt_array(center, east_col=None, south_row=None,
                    se_corner=None):
    """Assemble the edge-inclusive 3601x3601 grid from the tile's own
    3600x3600 samples plus the neighbour-borrowed east column, south
    row, and SE corner (each already resampled; None duplicates)."""
    out = np.empty((OUT_SAMPLES, OUT_SAMPLES), dtype=np.float32)
    out[:3600, :3600] = center
    out[:3600, 3600] = east_col if east_col is not None \
        else center[:, -1]
    out[3600, :3600] = south_row if south_row is not None \
        else center[-1, :]
    if se_corner is not None:
        out[3600, 3600] = se_corner
    elif east_col is not None:
        out[3600, 3600] = east_col[-1]
    elif south_row is not None:
        out[3600, 3600] = south_row[-1]
    else:
        out[3600, 3600] = center[-1, -1]
    return out


def _read_glo(src, lat, lon):
    """Read one GLO tile as float32 rows-north-first, columns
    resampled to 3600. Returns None when absent (ocean)."""
    import rasterio
    path = os.path.join(src, glo_name(lat, lon) + ".tif")
    if not os.path.exists(path):
        return None
    with rasterio.open(path) as ds:
        arr = ds.read(1).astype(np.float32)
    return resample_columns(arr)


def convert_one(src, dest, lat, lon):
    name = tile_name(lat, lon)
    ns_dir = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"
    out_dir = os.path.join(dest, ns_dir)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, name + ".hgt")
    if os.path.exists(out_path):
        return name, "skip"

    center = _read_glo(src, lat, lon)
    if center is None:
        return name, "absent"
    east = _read_glo(src, lat, lon + 1)
    south = _read_glo(src, lat - 1, lon)
    east_col = east[:, 0] if east is not None else None
    south_row = south[0, :] if south is not None else None
    se = None
    if east is not None and south is not None:
        se_tile = _read_glo(src, lat - 1, lon + 1)
        if se_tile is not None:
            se = float(se_tile[0, 0])
    hgt = build_hgt_array(center, east_col, south_row, se)
    np.clip(np.rint(hgt), -32767, 32767).astype(">i2").tofile(
        out_path + ".part")
    os.replace(out_path + ".part", out_path)
    return name, "ok"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--src", required=True, help="raw GLO-30 .tif dir")
    ap.add_argument("--dest", required=True, help="HGT output root")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tiles", nargs="*",
                    help="specific tiles e.g. N60W136 (default: all "
                         "tiles present in --src)")
    args = ap.parse_args()

    if args.tiles:
        wanted = []
        for t in args.tiles:
            m = re.fullmatch(r"([NS])(\d+)([EW])(\d+)", t.upper())
            assert m, f"bad tile name {t}"
            wanted.append((int(m.group(2)) * (1 if m.group(1) == "N"
                                              else -1),
                           int(m.group(4)) * (1 if m.group(3) == "E"
                                              else -1)))
    else:
        wanted = []
        for fn in os.listdir(args.src):
            m = NAME_RE.match(fn)
            if m and fn.endswith(".tif"):
                wanted.append(
                    (int(m.group(2)) * (1 if m.group(1) == "N" else -1),
                     int(m.group(4)) * (1 if m.group(3) == "E" else -1)))

    print(f"{len(wanted)} tiles to convert")
    done = skip = 0
    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        futs = [pool.submit(convert_one, args.src, args.dest, la, lo)
                for la, lo in wanted]
        for fut in concurrent.futures.as_completed(futs):
            name, status = fut.result()
            if status == "ok":
                done += 1
                if done % 50 == 0:
                    print(f"  {done} converted", flush=True)
            elif status == "skip":
                skip += 1
    print(f"complete: {done} converted, {skip} already present")


if __name__ == "__main__":
    main()
