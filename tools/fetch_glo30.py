#!/usr/bin/env python3
"""
Fetch Copernicus GLO-30 DEM tiles from the AWS Open Data bucket.

P6 of docs/svs_structural_plan.md: GLO-30 replaces SRTM3 as the terrain
source (global coverage — fixes the SRTM >60N hole over northern
Canada; 30 m resolution). This tool downloads the raw 1x1 degree
Cloud-Optimized GeoTIFFs; the HGT conversion step lives separately so
the (large, slow) download and the (fast, re-runnable) conversion can
be iterated independently.

No authentication required. Resumable: existing complete files are
skipped, so re-running after an interruption continues where it left
off. Partial downloads go to a .part file and are renamed on success.

Usage:
    python tools/fetch_glo30.py --dest D:/EarthData/glo30 \
        --min-lat 14 --max-lat 72 --min-lon -170 --max-lon -52
    python tools/fetch_glo30.py --dest ... --dry-run     # count + size only

The bucket's tileList.txt enumerates land tiles only — ocean cells have
no tile, which matches the renderer's missing-tile-is-water convention.
"""

import argparse
import concurrent.futures
import os
import re
import sys
import urllib.request

BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"
NAME_RE = re.compile(
    r"Copernicus_DSM_COG_10_([NS])(\d+)_00_([EW])(\d+)_00_DEM")


def tile_latlon(name):
    m = NAME_RE.fullmatch(name.strip())
    if not m:
        return None
    lat = int(m.group(2)) * (1 if m.group(1) == "N" else -1)
    lon = int(m.group(4)) * (1 if m.group(3) == "E" else -1)
    return lat, lon


def load_tile_list(dest):
    """Download (or reuse) the bucket's tile inventory."""
    cache = os.path.join(dest, "tileList.txt")
    if not os.path.exists(cache):
        print("fetching tile inventory ...")
        urllib.request.urlretrieve(f"{BUCKET}/tileList.txt", cache)
    with open(cache) as f:
        return [ln.strip() for ln in f if ln.strip()]


def fetch_one(name, dest):
    """Download one tile. Returns (name, bytes, skipped)."""
    out = os.path.join(dest, f"{name}.tif")
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return name, os.path.getsize(out), True
    url = f"{BUCKET}/{name}/{name}.tif"
    part = out + ".part"
    try:
        with urllib.request.urlopen(url, timeout=120) as r, \
                open(part, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        os.replace(part, out)
        return name, os.path.getsize(out), False
    except Exception:
        if os.path.exists(part):
            os.remove(part)
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--dest", required=True)
    ap.add_argument("--min-lat", type=int, default=14)
    ap.add_argument("--max-lat", type=int, default=72)
    ap.add_argument("--min-lon", type=int, default=-170)
    ap.add_argument("--max-lon", type=int, default=-52)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.dest, exist_ok=True)
    wanted = []
    for name in load_tile_list(args.dest):
        ll = tile_latlon(name)
        if ll is None:
            continue
        lat, lon = ll
        if (args.min_lat <= lat <= args.max_lat
                and args.min_lon <= lon <= args.max_lon):
            wanted.append(name)
    have = sum(1 for n in wanted
               if os.path.exists(os.path.join(args.dest, n + ".tif")))
    print(f"{len(wanted)} tiles in bbox "
          f"[{args.min_lat}..{args.max_lat}] x "
          f"[{args.min_lon}..{args.max_lon}]; {have} already present")
    if args.dry_run:
        return

    done = have
    failed = []
    todo = [n for n in wanted
            if not os.path.exists(os.path.join(args.dest, n + ".tif"))]
    total_bytes = 0
    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        futs = {pool.submit(fetch_one, n, args.dest): n for n in todo}
        for fut in concurrent.futures.as_completed(futs):
            name = futs[fut]
            try:
                _, size, _ = fut.result()
                total_bytes += size
                done += 1
                if done % 25 == 0:
                    print(f"  {done}/{len(wanted)} "
                          f"({total_bytes / 1e9:.1f} GB this run)",
                          flush=True)
            except Exception as e:
                failed.append(name)
                print(f"  FAILED {name}: {e}", flush=True)
    print(f"complete: {done}/{len(wanted)} tiles, "
          f"{total_bytes / 1e9:.1f} GB downloaded this run, "
          f"{len(failed)} failures")
    if failed:
        print("re-run to retry the failures (existing files are skipped)")
        sys.exit(1)


if __name__ == "__main__":
    main()
