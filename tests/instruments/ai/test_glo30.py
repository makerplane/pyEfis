"""P6 tests: GLO-30 conversion math and mixed-resolution tile support."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[3] / "tools"))
from convert_glo30 import resample_columns, build_hgt_array  # noqa: E402

from pyefis.instruments.ai.svs import SVSRenderer, load_tile  # noqa: E402


def _write_hgt(root: Path, lat, lon, n, value):
    ns_dir = root / f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"
    ns_dir.mkdir(parents=True, exist_ok=True)
    name = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}" \
           f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}.hgt"
    np.full((n, n), value, dtype=">i2").tofile(ns_dir / name)


class TestConverterMath:
    def test_resample_columns_identity_at_3600(self):
        a = np.arange(2 * 3600, dtype=np.float32).reshape(2, 3600)
        assert resample_columns(a) is a

    def test_resample_columns_1800_to_3600(self):
        # High-latitude band: 1800 cols over the same 1-degree span.
        row = np.linspace(0.0, 100.0, 1800).astype(np.float32)
        out = resample_columns(np.stack([row, row]))
        assert out.shape == (2, 3600)
        # A linear ramp must stay a ramp with the same endpoints.
        assert out[0, 0] == pytest.approx(0.0)
        assert out[0, -1] == pytest.approx(100.0, rel=1e-3)
        diffs = np.diff(out[0].astype(np.float64))
        assert diffs.min() >= -1e-4   # monotonic

    def test_build_hgt_borrows_neighbours(self):
        c = np.full((3600, 3600), 10.0, dtype=np.float32)
        east = np.full(3600, 20.0, dtype=np.float32)
        south = np.full(3600, 30.0, dtype=np.float32)
        out = build_hgt_array(c, east, south, se_corner=40.0)
        assert out.shape == (3601, 3601)
        assert out[0, 0] == 10.0
        assert out[100, 3600] == 20.0    # east edge from neighbour
        assert out[3600, 100] == 30.0    # south edge from neighbour
        assert out[3600, 3600] == 40.0   # SE corner

    def test_build_hgt_duplicates_when_no_neighbours(self):
        c = np.arange(3600 * 3600, dtype=np.float32).reshape(3600, 3600)
        out = build_hgt_array(c)
        assert out[0, 3600] == c[0, -1]
        assert out[3600, 0] == c[-1, 0]
        assert out[3600, 3600] == c[-1, -1]


class TestDynamicTileResolution:
    def test_load_tile_3601(self, tmp_path):
        _write_hgt(tmp_path, 60, -136, 3601, 1500)
        t = load_tile(tmp_path, 60, -136)
        assert t.shape == (3601, 3601)
        assert t[0, 0] == 1500.0

    def test_load_tile_1201_still_works(self, tmp_path):
        _write_hgt(tmp_path, 32, -97, 1201, 200)
        t = load_tile(tmp_path, 32, -97)
        assert t.shape == (1201, 1201)

    def test_load_tile_rejects_non_square(self, tmp_path):
        ns = tmp_path / "N32"
        ns.mkdir()
        np.zeros(1000, dtype=">i2").tofile(ns / "N32W097.hgt")
        assert load_tile(tmp_path, 32, -97) is None

    def test_sample_elevations_mixed_resolution(self, tmp_path):
        _write_hgt(tmp_path, 32, -98, 1201, 100)   # SRTM3-res tile
        _write_hgt(tmp_path, 32, -97, 3601, 900)   # GLO-30-res tile
        r = SVSRenderer({"enabled": True, "tile_path": str(tmp_path)})
        elev, water = r._sample_elevations(
            np.array([[32.5, 32.5]]), np.array([[-97.5, -96.5]]))
        assert elev[0, 0] == pytest.approx(100.0)
        assert elev[0, 1] == pytest.approx(900.0)
        assert not water.any()


class TestMixedResolutionPatch:
    def test_build_patch_upsamples_and_caps(self, tmp_path):
        # NE tile fine (3601), the rest coarse (1201): patch assembles
        # at 3601/tile then decimates to the configured cap.
        for la, lo, n, v in ((32, -98, 1201, 100), (32, -97, 3601, 200),
                             (33, -98, 1201, 300), (33, -97, 1201, 400)):
            _write_hgt(tmp_path, la, lo, n, v)
        from pyefis.instruments.ai.svs_gl import SVSGLRenderer
        r = SVSRenderer({"enabled": True, "tile_path": str(tmp_path),
                         "heightmap_max_px": 4096})
        glr = SVSGLRenderer(r)
        patch = glr._build_patch(32, -98)
        # native 2x3601 = 7202 -> decimated x2 -> 3601, under the cap
        assert patch.shape == (3601, 3601)
        # SW corner of patch = south-west tile (row 0 = south edge)
        assert patch[0, 0] == pytest.approx(100.0)
        assert patch[0, -1] == pytest.approx(200.0)    # SE = fine tile
        assert patch[-1, 0] == pytest.approx(300.0)    # NW
        assert patch[-1, -1] == pytest.approx(400.0)   # NE

    def test_build_patch_all_srtm3_unchanged(self, tmp_path):
        for la, lo in ((32, -98), (32, -97), (33, -98), (33, -97)):
            _write_hgt(tmp_path, la, lo, 1201, 50)
        from pyefis.instruments.ai.svs_gl import SVSGLRenderer
        r = SVSRenderer({"enabled": True, "tile_path": str(tmp_path)})
        glr = SVSGLRenderer(r)
        patch = glr._build_patch(32, -98)
        # 2*(N-1)+1: shared tile edges are no longer duplicated, so the
        # patch is edge-inclusive with samples on the global native grid
        # (keeps decimation phase-anchored across patch rebuilds).
        assert patch.shape == (2401, 2401)
