#  SPDX-License-Identifier: GPL-2.0-or-later
"""Rose bake cache (#94): heading changes reuse the baked rose; a scene
rebuild (resize) invalidates it. Companion to the tape strip cache
tests (#93) -- same scene-identity keying."""


def _hsi(qtbot, size=320):
    from pyefis.instruments import hsi
    h = hsi.HSI(font_percent=0.05, cdi_enabled=True, gsi_enabled=True)
    qtbot.addWidget(h)
    h.resize(size, size)
    h.show()
    qtbot.waitExposed(h)
    return h


def test_rose_cache_reused_across_headings(fix, qtbot):
    h = _hsi(qtbot)
    h.setHeading(10.0)
    h.grab()
    rose1 = h._rose_cache[2]
    h.setHeading(200.0)
    h.grab()
    assert h._rose_cache[2] is rose1


def test_rose_cache_invalidated_on_scene_rebuild(fix, qtbot):
    h = _hsi(qtbot)
    h.setHeading(10.0)
    h.grab()
    rose1 = h._rose_cache[2]
    h.resize(280, 280)          # resizeEvent replaces the scene
    h.grab()
    assert h._rose_cache[2] is not rose1


def test_rose_bake_excludes_then_restores_dynamic_items(fix, qtbot):
    h = _hsi(qtbot)
    h.grab()
    # the bake must leave the dynamic card items visible afterwards
    if h.track_item is not None:
        assert h.track_item.isVisible() == h._track_visible()
