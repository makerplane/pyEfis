# SVS Water Database

The SVS water-polygon overlay reads from a sqlite file produced by
`tools/build_water_db.py` out of vector shapefiles. This doc captures
the data sources, the current build/deploy workflow, the perf
constraints we hit on the first deploy, and the shape of the
download-and-update tool we still need to build.

## Data sources (verified working)

### OSM coastline-derived water polygons (oceans + seas)

- **Source**: https://osmdata.openstreetmap.de/data/water-polygons.html
- **File**: `water-polygons-split-4326.zip`
- **Direct download**:
  <https://osmdata.openstreetmap.de/download/water-polygons-split-4326.zip>
- **Projection**: EPSG:4326 (WGS-84) — required (pyEfis works in
  geographic coordinates)
- **Format**: shapefile (.shp + sidecars), pre-cut into manageable
  chunks
- **Size**: ~620 MB compressed, ~3.4 GB uncompressed (.shp 1.2 GB)
- **Count**: 53,326 shapes, fragmented into 876,554 rings
- **Refresh cadence**: weekly upstream; for our purposes monthly /
  on-demand is fine — coastlines don't move
- **Pi dest dir**: `~/pyEfis/water/`

### Natural Earth 10m physical lakes

- **Source**: https://www.naturalearthdata.com/downloads/10m-physical-vectors/
- **Direct download**:
  <https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_lakes.zip>
- **Size**: ~5 MB zipped, 2.6 MB .shp
- **Count**: 1,355 shapes / 1,597 rings worldwide
- **Coverage**: every major lake on the planet; no inland rivers,
  no farm ponds. Good enough for SVS baseline.
- **Refresh cadence**: Natural Earth releases roughly annually;
  we don't really need to track it

### NOT YET INGESTED — future candidates

- **OSM inland water (lakes / rivers / reservoirs at full OSM
  detail)**: would catch every lake and wider river worldwide.
  Comes from running a full OSM .pbf extract through osmium /
  imposm with the right tag filters. ~10 GB+ world; ~1 GB CONUS.
  Worth doing once we have a proper download/build pipeline.
- **NOAA GSHHG hierarchical shorelines**: alternate ocean polygon
  set with built-in LOD (full / high / intermediate / low / crude
  resolutions). Could replace OSM for ocean if we want
  pre-decimated tiers without re-running our own decimation.

## Build workflow today

```bash
PYTHONPATH="C:/pylib;src" python tools/build_water_db.py \
    /path/to/water.sqlite \
    --ocean /path/to/water-polygons-split-4326/water_polygons.shp \
    --lake  /path/to/ne_10m_lakes/ne_10m_lakes.shp \
    --max-vertices 32
```

- `--max-vertices N` (default 32) stride-decimates each polygon at
  ingest time. Per-polygon BLOB shrinks from ~50–100 KB (raw OSM
  detail) to ~512 bytes. Critical for runtime perf — see "perf
  notes" below.
- `--ocean` / `--lake` / `--river` / `--osm-water` flags set the
  `kind` field per source; pyEfis uses `kind == 'ocean'` to skip
  the SRTM lookup since ocean = sea level by definition.
- `--text input.txt` is a documented hand-rollable format useful
  for tiny test datasets without pulling pyshp into the runtime
  environment.

The build is currently driven by hand from the Windows dev box
because the shapefiles are downloaded manually. Resulting sqlite
file is scp'd to the Pi at `/home/wpballard/pyEfis/water/`.

## Pi-side wiring

`virtual_vfr.yaml` in the screen YAML carries:

```yaml
svs:
    enabled: true
    ...
    water_db_path: /home/wpballard/pyEfis/water/water_capped.sqlite
    water_max_vertices: 32          # optional, defaults to 32
    svs_perf_log: true              # optional, default false
```

WaterDB construction is "missing file means disabled" — there is no
fatal failure if the path is wrong, just no water overlay.

## Perf notes (KSBA flight test, 2026-06-02)

Profiler (svs_perf_log: true) at KSBA looking out over the Pacific
on the GL renderer tier with the FULL un-decimated 1.45 GB OSM DB:

| segment | per-frame | % budget |
|---|---|---|
| **water.query** | **53 ms** | **70%** |
| runways | 6.5 ms | 9% |
| gl_terrain | 3.7 ms | 5% |
| obstacles | 3.2 ms | 4% |
| water.project | 0.04 ms × N | 0.3% |
| water.drawPolygon | 0.06 ms × N | 0.2% |

Diagnosis:

- The vector projection / drawing was trivially fast even with
  100+ polygons in range.
- `water.query` (sqlite SELECT + BLOB decode) was 70% of the
  frame budget.
- Rebuilding with `--max-vertices 32` cut DB from 1.45 GB to
  354 MB but `water.query` stayed at ~53 ms. So the cost wasn't
  reading 50 KB BLOBs — it was the index scan itself.
- The default `idx_bbox` is `(min_lat, max_lat, min_lon, max_lon)`
  — sqlite can only use one inequality predicate efficiently, so
  the planner is essentially scanning all rows with
  `min_lat < lat_upper` and matching the rest in Python.

The proper fix is sqlite's **R-Tree** virtual-table extension —
that's purpose-built for bbox queries and runs sub-millisecond on
this dataset size. Filed as a separate todo; not in the
build_water_db.py first version.

There's also a separate, larger perf mystery: total SVS work
adds up to ~65 ms / frame but pyEfis was running at 2 FPS
(~500 ms / frame). The other 435 ms is happening *outside* the
SVS draw path. Could be the GL FBO blit, Qt's repaint loop on the
new SVS widget, or other instrument paint events being amplified
by something. Needs investigation with a wider-scope profiler.

## What the download-and-update tool needs to do

The tool we still need to build. Open requirements:

1. **Fetch sources** — download OSM water-polygons-split-4326.zip
   and ne_10m_lakes.zip from their canonical URLs. Verify size /
   checksum where the upstream provides one.
2. **Cache locally** — re-running shouldn't re-download if the
   upstream file is unchanged (HEAD request + Last-Modified or
   ETag check).
3. **Extract** — unzip into a working directory.
4. **Build** — invoke `build_water_db.py` with appropriate flags,
   default `--max-vertices 32`.
5. **Validate** — confirm the resulting sqlite has the expected
   table shape, polygon count is plausible, and a sample query
   in a known bbox returns results.
6. **Install** — atomic move into place at the configured
   `water_db_path` so an in-flight pyEfis doesn't see a half-built
   file.
7. **Optional region builds** — CONUS-only build to keep DB small
   (~10–20 MB instead of 354 MB), useful for embedded targets
   with limited storage. Would clip both shapefiles to a bbox at
   ingest.
8. **Future inland-water build** — when we add OSM inland data,
   the tool should also run an OSM extract via osmium/imposm and
   merge into the same DB with `kind=lake` / `kind=river`.
9. **Cron/systemd hook** — schedule a monthly rebuild so the data
   stays current without manual steps.

Probably belongs as `tools/refresh_water_data.py` or a small
script set under `tools/water/`. Pattern can mirror what
`tools/build_airport_db.py` / `tools/build_obstacle_db.py` do for
their FAA NASR / DOF refresh.

## Filed work (followups)

- **R-Tree index for water_polygons** — replace the
  `idx_bbox(min_lat, max_lat, min_lon, max_lon)` B-tree with a
  proper rtree virtual table. Expected to drop `water.query` from
  ~53 ms to <1 ms.
- **Refresh tool** as above.
- **Inland OSM water** ingest pipeline.
- **CONUS-only / region-only** sub-build option.
- **Investigate the missing ~430 ms/frame** outside SVS at KSBA
  with water enabled.
