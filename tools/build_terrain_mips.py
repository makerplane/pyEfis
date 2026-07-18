#!/usr/bin/env python3
"""Build a terrain mip pyramid (docs/terrain_mip_pyramid.md).

For every native HGT tile under a tile tree, write anti-aliased downsampled
copies at levels 1..N into the parallel ``.mip/<L>/<NSdir>/<name>.hgt`` tree the
moving-map / SVS ``TileCache.get_mip()`` reads. Dense 2x-per-level pyramid
(level k -> factor ``2**k``, ~``30*2**k`` m pitch), matching ``terrain.py``'s mip
selection. Output is the same big-endian int16 HGT the loader already reads (the
side is inferred from file size), so no new format. Run on a workstation that
holds the tiles -- never the EFIS device.

Downsample: a **node-centred box average** -- each coarse grid node is the mean
of a ~factor-wide box of native samples centred on it. So the coarse corners stay
registered to the native corners (tiles keep abutting), and the result is
anti-aliased (no strided-subsample moire). Voids (``SRTM3_VOID``) are excluded
from each average; GLO-30 has none, so this is a safety net for SRTM3.

Each tile is independent, so the build parallelises across CPU cores (``--jobs``,
default = all cores). Workers receive the void marker from the parent and never
import the pyEfis GUI stack, so spawning is cheap on Windows. A 16-core box cuts
the all-NA build from hours to tens of minutes -- handy for a cloud runner.

Usage::

    python tools/build_terrain_mips.py <tile_root> [--levels 6] [--force]
                                        [--jobs 0] [--only N35W098 N36W099 ...]
"""
import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

MAX_LEVEL = 6           # matches the terrain.py mip clamp (min(6, ...))
DEFAULT_VOID = -32768   # SRTM3/GLO-30 void marker; overridden by the authoritative
                        # pyefis.instruments.ai.svs.SRTM3_VOID when it is importable.

# Void marker used by :func:`downsample`. Set once in the parent (``_resolve_void``)
# and re-established in each worker by the pool initializer, so workers do not need
# to import ``pyefis.instruments.ai`` (and PyQt6) just for a constant.
_VOID = DEFAULT_VOID


def _resolve_void() -> int:
    """The authoritative void marker from pyEfis if importable, else the literal.
    Called once in the parent; the value is handed to workers so none of them
    import the GUI stack (which makes ``multiprocessing`` spawn cheap)."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        from pyefis.instruments.ai.svs import SRTM3_VOID
        return int(SRTM3_VOID)
    except Exception:
        return DEFAULT_VOID


def downsample(native: np.ndarray, factor: int, void: int | None = None) -> np.ndarray:
    """Anti-aliased node-centred box downsample of a square ``(n, n)`` int16
    tile by ``factor``. Returns an ``(m, m)`` big-endian int16 array with
    ``m = round((n-1)/factor) + 1``, corners registered to the native corners.
    Voids (== ``void``, default the module marker) are excluded per box; an
    all-void box stays void."""
    void = _VOID if void is None else void
    n = native.shape[0]
    m = int(round((n - 1) / factor)) + 1
    data = native.astype(np.float64)
    valid = (native != void).astype(np.float64)
    dv = data * valid
    # coarse node positions, corner-exact (first = 0, last = n-1)
    idx = np.rint(np.linspace(0, n - 1, m)).astype(np.int64)
    half = max(1, factor // 2)
    lo = np.clip(idx - half, 0, n)
    hi = np.clip(idx + half + 1, 0, n)      # exclusive

    def boxsum(a):
        """Node-centred box sums along axis 0: (K, X) -> (m, X)."""
        cs = np.zeros((a.shape[0] + 1, a.shape[1]), np.float64)
        np.cumsum(a, axis=0, out=cs[1:])
        return cs[hi] - cs[lo]

    # separable: box the rows, then box the columns (via transpose)
    ds = boxsum(boxsum(dv).T)               # (m_col, m_row)
    ws = boxsum(boxsum(valid).T)            # (m_col, m_row)
    with np.errstate(invalid="ignore", divide="ignore"):
        coarse = (ds / ws).T                # (m_row, m_col)
    coarse = np.where(ws.T > 0, coarse, float(void))
    return np.ascontiguousarray(np.rint(coarse)).astype(">i2")


def _iter_native(root: Path, only):
    for p in sorted(root.glob("[NS]*/*.hgt")):
        stem = p.stem.upper()
        if only and stem not in only:
            continue
        yield stem, p


def build_tile(root: Path, stem: str, path: Path, levels: int, force: bool) -> int:
    raw = np.fromfile(path, dtype=">i2")
    n = int(round(raw.size ** 0.5))
    if n * n != raw.size:
        print(f"  skip {stem}: not square ({raw.size} samples)")
        return 0
    native = raw.reshape(n, n)
    ns = path.parent.name                    # <NSdir>
    written = 0
    for level in range(1, levels + 1):
        out = root / ".mip" / str(level) / ns / f"{stem}.hgt"
        if out.exists() and not force:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        downsample(native, 1 << level).tofile(out)
        written += 1
    return written


def _init_worker(void: int):
    """Pool initializer: pin this worker's void marker (no pyEfis import)."""
    global _VOID
    _VOID = void


def _worker(job):
    """Pool task: build one tile's pyramid. Returns ``(stem, written, error)``;
    a failure on one tile is captured, not raised, so the batch continues."""
    root, stem, path, levels, force = job
    try:
        return stem, build_tile(root, stem, path, levels, force), None
    except Exception as exc:                 # noqa: BLE001 -- one bad tile != abort
        return stem, 0, repr(exc)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a terrain mip pyramid.")
    ap.add_argument("tile_root", help="terrain tile tree (holds <NSdir>/*.hgt)")
    ap.add_argument("--levels", type=int, default=MAX_LEVEL,
                    help=f"deepest level to build (default {MAX_LEVEL})")
    ap.add_argument("--force", action="store_true",
                    help="rebuild levels that already exist")
    ap.add_argument("-j", "--jobs", type=int, default=0,
                    help="worker processes (0 = all CPUs, the default; 1 = sequential)")
    ap.add_argument("--only", nargs="*", default=None,
                    help="only these tiles (e.g. N35W098)")
    args = ap.parse_args(argv)

    root = Path(args.tile_root)
    only = {s.upper() for s in args.only} if args.only else None
    tiles = list(_iter_native(root, only))

    void = _resolve_void()
    global _VOID
    _VOID = void                             # for the sequential path (parent process)
    jobs = args.jobs if args.jobs > 0 else (os.cpu_count() or 1)
    jobs = max(1, min(jobs, len(tiles) or 1))

    print(f"root={root}  native tiles: {len(tiles)}  levels 1..{args.levels}  "
          f"jobs={jobs}  void={void}")
    t0 = time.perf_counter()
    files = 0
    errors = []
    jobargs = [(root, stem, path, args.levels, args.force) for stem, path in tiles]

    def _progress(i):
        if (i + 1) % 50 == 0 or (i + 1) == len(tiles):
            dt = time.perf_counter() - t0
            rate = (i + 1) / dt if dt > 0 else 0
            print(f"  {i + 1}/{len(tiles)} tiles... "
                  f"({files} files, {dt:.0f}s, {rate:.1f} tiles/s)")

    if jobs == 1:
        for i, ja in enumerate(jobargs):
            _, written, err = _worker(ja)
            files += written
            if err:
                errors.append((ja[1], err))
            _progress(i)
    else:
        import multiprocessing as mp
        with mp.Pool(jobs, initializer=_init_worker, initargs=(void,)) as pool:
            for i, (stem, written, err) in enumerate(
                    pool.imap_unordered(_worker, jobargs, chunksize=1)):
                files += written
                if err:
                    errors.append((stem, err))
                _progress(i)

    footprint = 0
    mip_root = root / ".mip"
    if mip_root.exists():
        footprint = sum(f.stat().st_size for f in mip_root.rglob("*.hgt"))
    dt = time.perf_counter() - t0
    print(f"done: {len(tiles)} tiles -> {files} mip files written, "
          f"pyramid {footprint / 1e9:.2f} GB, {dt:.1f}s"
          + (f" ({len(tiles) / dt:.1f} tiles/s)" if dt > 0 else ""))
    if errors:
        print(f"WARNING: {len(errors)} tile(s) errored:")
        for stem, err in errors[:20]:
            print(f"  {stem}: {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
