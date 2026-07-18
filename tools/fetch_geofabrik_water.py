#!/usr/bin/env python3
"""
Download Geofabrik per-state OSM shapefile extracts and build the SVS
water sqlite database from the inland-water layer (gis_osm_water_a_free_1).

Each Geofabrik state extract is a single zip containing every OSM layer
for the state. We only need ``gis_osm_water_a_free_1.shp`` (polygon
inland water — lakes, reservoirs, ponds, wide rivers) so the script
extracts just that layer and deletes the zip afterwards to keep disk
usage bounded (each state zip is 50 MB–1.5 GB).

The ocean coastline layer is sourced separately from the existing
``water-polygons-split-4326`` extract that ships with this checkout.

Usage:
    # Single state — fast path for verifying the pipeline
    python tools/fetch_geofabrik_water.py --states texas

    # Full lower-48 CONUS coverage (multi-hour download)
    python tools/fetch_geofabrik_water.py --states conus

    # Custom subset
    python tools/fetch_geofabrik_water.py \\
        --states oklahoma,arkansas,louisiana,texas
"""

import argparse
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path


CONUS_STATES = [
    "alabama", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "district-of-columbia", "florida",
    "georgia", "idaho", "illinois", "indiana", "iowa", "kansas",
    "kentucky", "louisiana", "maine", "maryland", "massachusetts",
    "michigan", "minnesota", "mississippi", "missouri", "montana",
    "nebraska", "nevada", "new-hampshire", "new-jersey", "new-mexico",
    "new-york", "north-carolina", "north-dakota", "ohio", "oklahoma",
    "oregon", "pennsylvania", "rhode-island", "south-carolina",
    "south-dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west-virginia", "wisconsin", "wyoming",
]

BASE_URL = "https://download.geofabrik.de/north-america/us"

# Files we keep from the per-state zip. gis_osm_water_a is polygons
# (lakes/reservoirs/ponds/wide rivers); the linestring waterways layer
# is dropped because the SVS renderer only paints polygons.
WATER_LAYER_FILES = (
    "gis_osm_water_a_free_1.shp",
    "gis_osm_water_a_free_1.shx",
    "gis_osm_water_a_free_1.dbf",
    "gis_osm_water_a_free_1.prj",
    "gis_osm_water_a_free_1.cpg",
)

OCEAN_SHP_DEFAULT = (
    "openstreetmapsdata/water-polygons-split-4326/water_polygons.shp"
)


def _fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def download_state(state, cache_dir):
    """Download a single state's shp.zip from Geofabrik. Idempotent:
    if the file already exists with non-zero size, skip the download."""
    url = f"{BASE_URL}/{state}-latest-free.shp.zip"
    out = cache_dir / f"{state}-latest-free.shp.zip"
    if out.exists() and out.stat().st_size > 0:
        print(f"  [cached] {out.name} ({_fmt_bytes(out.stat().st_size)})")
        return out
    print(f"  downloading {url}")
    t0 = time.time()
    tmp = out.with_suffix(".zip.partial")
    with urllib.request.urlopen(url) as resp, open(tmp, "wb") as fh:
        total = int(resp.headers.get("Content-Length", 0))
        copied = 0
        chunk = 1 << 20  # 1 MB
        while True:
            data = resp.read(chunk)
            if not data:
                break
            fh.write(data)
            copied += len(data)
            if total:
                pct = 100.0 * copied / total
                print(f"    {pct:5.1f}%  ({_fmt_bytes(copied)} / "
                      f"{_fmt_bytes(total)})", end="\r")
        print()
    tmp.rename(out)
    print(f"    done in {time.time() - t0:.1f}s "
          f"({_fmt_bytes(out.stat().st_size)})")
    return out


def extract_water_layer(zip_path, dest_dir):
    """Extract just the water polygon layer from a state zip. Returns
    the path to the extracted .shp, or None if the zip doesn't contain
    the expected layer."""
    state = zip_path.name.replace("-latest-free.shp.zip", "")
    out_dir = dest_dir / state
    out_dir.mkdir(parents=True, exist_ok=True)
    shp_out = out_dir / WATER_LAYER_FILES[0]
    if shp_out.exists() and shp_out.stat().st_size > 0:
        return shp_out
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        want = []
        for layer in WATER_LAYER_FILES:
            for n in names:
                if n.endswith(layer):
                    want.append((n, layer))
                    break
        if not any(layer == WATER_LAYER_FILES[0]
                   for _, layer in want):
            print(f"  WARNING: {zip_path.name} has no water_a layer")
            return None
        for src, dest in want:
            with zf.open(src) as fh_in, \
                    open(out_dir / dest, "wb") as fh_out:
                shutil.copyfileobj(fh_in, fh_out)
    return shp_out


def parse_states_arg(s):
    s = s.strip().lower()
    if s == "conus":
        return list(CONUS_STATES)
    states = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        # Accept both "new-york" and "new_york" / "newyork"
        part = part.replace(" ", "-").replace("_", "-")
        states.append(part)
    return states


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--states", default="conus",
                   help="comma-separated state slugs (geofabrik style: "
                        "'new-york', 'texas', ...) or 'conus' for the "
                        "lower 48")
    p.add_argument("--cache-dir", default="openstreetmapsdata/geofabrik",
                   help="where state zips and extracted shapefiles "
                        "are kept (idempotent — reusing this dir lets "
                        "you re-run the build without re-downloading)")
    p.add_argument("--output", default="water/water_rtree.sqlite",
                   help="output sqlite path (overwrites)")
    p.add_argument("--ocean-shp", default=OCEAN_SHP_DEFAULT,
                   help="OSM coastline polygons shapefile (kept "
                        "alongside inland water). Pass '' to skip.")
    p.add_argument("--ne-lakes",
                   default="openstreetmapsdata/ne_10m_lakes/ne_10m_lakes.shp",
                   help="Natural Earth 10m lakes shapefile, for "
                        "non-US coverage outside the state list. "
                        "Pass '' to skip.")
    p.add_argument("--keep-zips", action="store_true",
                   help="don't delete state zips after extraction "
                        "(useful for re-running with different "
                        "filters)")
    p.add_argument("--max-vertices", type=int, default=32,
                   help="per-polygon vertex cap (build_water_db.py "
                        "default)")
    p.add_argument("--build-only", action="store_true",
                   help="skip download/extract; only run the build "
                        "step using whatever shapefiles are already "
                        "in the cache dir")
    args = p.parse_args()

    cache_dir = Path(args.cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir = cache_dir / "extracted"
    extracted_dir.mkdir(exist_ok=True)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    states = parse_states_arg(args.states)
    print(f"Plan: {len(states)} state(s): {', '.join(states[:5])}"
          f"{'...' if len(states) > 5 else ''}")
    print(f"Cache: {cache_dir}")
    print(f"Output: {output}")
    print()

    shp_paths = []
    if not args.build_only:
        for i, state in enumerate(states, 1):
            print(f"[{i}/{len(states)}] {state}")
            try:
                zip_path = download_state(state, cache_dir)
            except Exception as e:
                print(f"  ERROR: download failed: {e}")
                continue
            shp = extract_water_layer(zip_path, extracted_dir)
            if shp:
                shp_paths.append(shp)
                if not args.keep_zips:
                    zip_path.unlink()
                    print(f"  removed {zip_path.name} "
                          "(--keep-zips to retain)")
    else:
        for sub in sorted(extracted_dir.iterdir()):
            shp = sub / WATER_LAYER_FILES[0]
            if shp.exists():
                shp_paths.append(shp)

    if not shp_paths:
        print("ERROR: no water shapefiles to build from", file=sys.stderr)
        sys.exit(1)

    print(f"\nBuilding {output} from {len(shp_paths)} water shapefile(s)")
    cmd = [
        sys.executable,
        str(Path(__file__).parent / "build_water_db.py"),
        str(output),
        "--max-vertices", str(args.max_vertices),
    ]
    if args.ocean_shp:
        cmd += ["--ocean", args.ocean_shp]
    if args.ne_lakes:
        cmd += ["--lake", args.ne_lakes]
    for shp in shp_paths:
        cmd += ["--osm-water", str(shp)]
    print(" ".join(cmd[:6]) + f" ... ({len(shp_paths)} --osm-water args)")
    subprocess.check_call(cmd)
    sz = output.stat().st_size
    print(f"\nDone. Output: {output} ({_fmt_bytes(sz)})")


if __name__ == "__main__":
    main()
