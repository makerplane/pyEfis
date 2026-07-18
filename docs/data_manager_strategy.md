# MakerPlane Data Manager — strategy

How end users keep a pyEfis Pi 5 deployment's data current, with the
Garmin data-manager experience as the benchmark: subscribe once, plug
in (or connect), and the box tells you when something is stale.

Companion to [svs_structural_plan.md](svs_structural_plan.md) — this
document defines the **production and distribution** side of the data
story; plan P8 (scenery packs) is the **on-device consumption** side,
and its pack format should be designed jointly with this.

## What data a deployment actually needs

| Data | Source | Cycle | Prepared size | Built by (today) |
|---|---|---|---|---|
| Terrain | Copernicus GLO-30 | ~yearly editions | ~26 MB / 1° tile (87 GB NA) | fetch_glo30 + convert_glo30 |
| Airports/runways | FAA NASR | 28 days | ~50 MB CONUS | build_airport_db.py |
| Obstacles | FAA DOF | 56 days | ~30 MB CONUS | build_obstacle_db.py |
| Procedures/waypoints | FAA CIFP | 28 days (AIRAC) | ~20 MB | faa-cifp-data repo (snap) |
| Water polygons | OSM Geofabrik + Natural Earth | quarterly is plenty | ~0.1–1 GB / region | build_water_db / fetch_geofabrik_water |
| Charts (P10, future) | FAA VFR raster | 56 days | tens of GB / continent | build_chart_pack (planned) |
| Mag variation | WMM coefficients | 5 years | KB | (future) |

Two very different shapes hide in that table:

- **Bulk-static** (terrain, satellite imagery): huge, almost never
  changes. Download once, sneakernet-friendly, hosting cost dominated
  by storage+egress.
- **Cyclical** (NASR/CIFP/DOF/charts/water): small, *currency is the
  whole point*. This is where the Garmin experience matters — the
  pilot needs to know "my data expires June 26" without thinking.

Licensing is favourable: FAA products are public domain, Copernicus
GLO-30 permits redistribution, OSM is ODbL (derived water DBs must
carry attribution — bake it into the pack metadata). The one hard
exclusion stands: Canadian VNC charts are NavCanada-licensed and stay
user-supplied forever; the pipeline must treat "user-supplied pack
slots" as first-class.

## Architecture: three components

```
[FAA / Copernicus / OSM]
        |  (daily cron checks)
        v
(1) PACK BUILDER  — GitHub Actions, runs the existing tools/ scripts,
        |           emits versioned signed packs + a catalog manifest
        v
(2) DISTRIBUTION  — Cloudflare R2 (zero egress fees) + static website
        |           on Cloudflare Pages reading the manifest
        v
(3) ON-PI UPDATER — pyefis-data CLI/daemon: WiFi pull at the hangar,
                    or USB-stick import; verifies, swaps atomically,
                    feeds the in-EFIS DATA status flag
```

### (1) Pack builder — automated pipeline

A new repo (suggest `makerplane/makerplane-data` — the existing
`faa-cifp-data` snap repo is the proven prototype and either grows into
this or gets absorbed by it). GitHub Actions on a daily schedule:

- Check each upstream for a new edition (FAA publishes effective dates
  in advance; like faa-cifp-data already does, fetch both *current*
  and *next* cycle so devices can stage data before it becomes
  effective).
- When new: run the existing build tools (they move from `pyEfis/tools/`
  into a shared package so both repos use one implementation), emit a
  pack, upload to R2, regenerate the catalog manifest.
- Terrain is a one-time manual pipeline run per continent/edition (too
  big for routine CI); cyclical packs are minutes of CI time.

**Pack format** (this IS the P8 design — settle it once): one file per
pack (sqlite or zip), plus catalog entry:

```json
{ "id": "navdata-conus", "kind": "navdata", "cycle": "2606",
  "effective": "2026-06-12", "expires": "2026-07-10",
  "sha256": "...", "bytes": 104857600,
  "url": "https://data.makerplane.org/packs/navdata-conus-2606.pack",
  "min_pyefis": "2.1", "attribution": "FAA NASR/CIFP/DOF" }
```

Manifest signed with a project ed25519 key (minisign); the updater
verifies signature + sha256 before installing. For terrain, packs are
regional groups (e.g. 10°×10° blocks or named regions "US-Southwest",
"Canada-West") so SD-card users can hold just their flying area while
NVMe users take a continent.

### (2) Distribution — website + storage

- **Storage**: Cloudflare R2. The decisive feature is **zero egress
  fees** — a popular terrain region being downloaded a thousand times
  costs nothing beyond ~$1.50/month per 100 GB stored. Total at NA
  scale (terrain + cycles + future charts): roughly 300–500 GB ≈
  **$5–8/month**. CI and Pages are free for public repos.
- **Website** (Cloudflare Pages, static + the manifest as its API):
  shows current/next cycle status with countdown, a region picker that
  produces either direct downloads or a `packlist.json` the on-Pi
  updater consumes, and a "prepare a USB stick" flow (download N files
  + the manifest to a stick — that's the whole sneakernet format).
- No accounts in v1. Nothing here needs identity; adding accounts later
  (saved regions, email expiry reminders) is additive.

### (3) On-Pi updater — `pyefis-data`

A small CLI + optional systemd timer on the Pi:

- `pyefis-data status` — installed packs vs catalog: current / update
  available / **expires in N days** / expired.
- `pyefis-data update` — pull what's stale for the configured regions
  over WiFi, verify signature+sha256, download to a staging dir, swap
  atomically (rename), then signal pyEfis (the 1 s DB caches mean most
  packs hot-load; terrain tiles are picked up on next cache miss).
- **USB import**: a udev/boot hook that detects a stick carrying
  `makerplane-data/` with a manifest, then runs the same
  verify-and-swap. This is the Garmin-card path for hangars without
  WiFi, and doubles as the recovery path.
- Region config lives in one place (`~/.makerplane/pyefis/data.yaml`):
  regions of interest, storage budget, auto-update on/off.

**In-EFIS integration** (the part pilots actually see): a `DATA` status
that pyEfis surfaces — amber when any installed cyclical pack is past
its expiry date, with the detail (which pack, expired when) on a
config/status screen. This is the plan P8 "out-of-cycle annunciation"
item; it belongs to this workstream now.

## Phasing (each independently shippable)

| Phase | Deliverable | Effort | Notes |
|---|---|---|---|
| A | Pack format + signed manifest schema; tools/ build scripts factored into a shared package | 2–3 d | Joint design with plan P8; unblocks everything |
| B | CI pipeline for cyclical packs (NASR/CIFP/DOF, then water) + R2 bucket | 2–3 d | Highest value: currency automation |
| C | `pyefis-data` CLI: status/update/verify/swap + USB import | 3–4 d | Pi-side; testable against B immediately |
| D | Terrain packs uploaded (one-time per edition) + region grouping | 1–2 d | Mostly upload logistics |
| E | Website: cycle dashboard, region picker, USB-stick flow | 3–5 d | Static; reads the manifest |
| F | In-EFIS DATA flag + status screen | 1–2 d | Folds into/replaces part of P8 |
| G | Later: chart packs (P10), email reminders, delta updates, Canadian airport coverage | — | See open questions |

Sensible order: A → B → C gives a working end-to-end loop (cron builds
a fresh NASR pack, your Pi pulls it at the hangar) before any website
exists. The website is presentation, not plumbing.

## Risks and design positions

- **Trust/safety**: signed manifest + checksums, staged atomic swaps,
  and the expiry annunciation. Standard experimental-avionics framing
  applies (MakerPlane's existing not-for-primary-navigation posture);
  the data manager must never silently serve stale data as fresh —
  absence of an update is annunciated, not hidden.
- **Bus factor / ownership**: pipeline and key belong in the MakerPlane
  GitHub org, not an individual account; R2/Pages on a MakerPlane
  Cloudflare account. Documented so any maintainer can rotate keys and
  re-run builds.
- **Bandwidth abuse**: R2 makes it a non-issue financially; rate limits
  via Cloudflare if ever needed.
- **Pi storage diversity**: region packs + a storage budget in
  `data.yaml` handle the SD-card case; NVMe users just select
  "North America".
- **Canadian airports gap**: NASR is US-only. Options to evaluate in
  Phase G: OurAirports open data (global, community-maintained,
  variable quality) as an optional supplementary pack, clearly labeled.

## Open questions for MakerPlane

1. Domain/branding: `data.makerplane.org`? Needs MakerPlane DNS + a
   Cloudflare account decision.
2. Does this live as a new repo or grow out of `faa-cifp-data`?
   (Recommendation: new repo, absorb faa-cifp-data's fetch logic.)
3. Who holds the signing key besides Bill?
4. Snap vs plain pip/systemd for `pyefis-data` on the Pi — the
   ecosystem has used snaps (fixgateway, faa-cifp-data); the Pi 5
   deployment here is bare venv. Pick one story for end users.
5. Appetite for serving non-US users in v1 (terrain+OSM water are
   global already; only navdata is US-bound).
