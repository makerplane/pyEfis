from PyQt6.QtWidgets import *
from PyQt6.QtGui import *

def fit_to_mask(width,height,mask,font,units_mask=None, units_ratio=0.8, numeric=False):
    font_size = 100
    error = 100
    minerror = 100
    goal = 0.02
    count = 0
    while ( error > goal):
        count += 1
        text_font = QFont(font)
        text_font.setPointSizeF(font_size)
        fm = QFontMetricsF(text_font)
        text_width = fm.horizontalAdvance(mask)
        if numeric:
            text_height = fm.tightBoundingRect(mask).height()
        else:
            text_height = fm.boundingRect(mask).height()
        units_width = 0
        units_height = 0
        if units_mask:
            units_font = QFont(font)
            units_font.setPointSizeF(font_size * units_ratio)
            fmu = QFontMetricsF(units_font)
            units_width = fmu.horizontalAdvance(units_mask)
        hfactor = height / text_height
        wfactor = width / ( text_width + units_width)
        if hfactor < 1 and wfactor < 1:
            factor = min(hfactor, wfactor)
        elif hfactor > 1 and wfactor > 1:
            factor = max(hfactor,wfactor)
        elif hfactor < 1 and wfactor > 1:
            factor = hfactor
        else:
            factor = wfactor
        error = abs(factor - 1)
        if factor > 1:
            if error < minerror:
                minerror = error
            else:
                break
        font_size = font_size * factor
    return font_size * 0.98




#: strip-cache ceiling: an altimeter tape at 30k ft x typical pph runs
#: ~12 MB; anything past this falls back to per-frame scene rendering.
_EDGE_FADE_CACHE_BYTES = 32 * 1024 * 1024


def render_view_edge_faded(view, fade_percent):
    """Paint a QGraphicsView's visible scene into its viewport with an
    alpha fade over the top and bottom ``fade_percent`` of the height,
    so a scrolling tape melts in/out at its ends instead of clipping.

    Call INSTEAD of ``super().paintEvent(event)`` when the widget's
    ``edge_fade`` option is > 0; anchored overlays (pointer, readout
    boxes) are then painted by the caller on top, unfaded. The scene's
    alpha is multiplied by a vertical gradient
    (CompositionMode_DestinationIn) in an offscreen buffer, so whatever
    sits behind the tape -- SVS terrain included -- shows through the
    fade. (DestinationIn on the widget's own backing store would also
    erase what is painted behind the tape.)

    Perf (#93): the tape scenes are STATIC between rebuilds --
    resizeEvent replaces ``view.scene`` wholesale and values only
    scroll the view -- so the full strip is rendered ONCE into an image
    cached on the view (keyed on scene identity + geometry). Each frame
    then blits the visible slice (SmoothPixmapTransform keeps subpixel
    scrolling smooth) and fades only the two edge strips; the old
    full-viewport gradient fill was a no-op over the middle ~70%.
    Re-rendering the scene per frame was ~12% of all GIL time in the
    post-#89 flight profile. Falls back to the per-frame render when
    the view is scaled or the strip would exceed the cache ceiling.
    """
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import (QColor, QImage, QLinearGradient, QPainter)
    vp = view.viewport()
    w, h = vp.width(), vp.height()
    if w <= 0 or h <= 0:
        return
    f = max(0.0, min(45.0, float(fade_percent))) / 100.0

    scene = view.scene
    srect = scene.sceneRect()
    t = view.transform()
    plain = (abs(t.m11() - 1.0) < 1e-9 and abs(t.m22() - 1.0) < 1e-9
             and t.m12() == 0.0 and t.m21() == 0.0)
    sw = int(srect.width() + 0.5)
    sh = int(srect.height() + 0.5)

    strip = None
    if plain and 0 < sw * sh * 4 <= _EDGE_FADE_CACHE_BYTES:
        # The cache holds the scene OBJECT (not id()): a strong ref
        # keeps a replaced scene's identity from being recycled into a
        # false cache hit; the stale ref is dropped on the first paint
        # after a rebuild.
        key = (sw, sh, w, h,
               getattr(view, "foregroundOpacity", None),
               getattr(view, "backgroundOpacity", None))
        cached = getattr(view, "_edge_fade_strip", None)
        if (cached is not None and cached[0] is scene
                and cached[1] == key):
            strip = cached[2]
        else:
            strip = QImage(sw, sh, QImage.Format.Format_ARGB32_Premultiplied)
            strip.fill(0)
            sp = QPainter(strip)
            sp.setRenderHint(QPainter.RenderHint.Antialiasing)
            scene.render(sp, QRectF(0, 0, sw, sh), srect)
            sp.end()
            view._edge_fade_strip = (scene, key, strip)

    buf = getattr(view, "_edge_fade_buf", None)
    if buf is None or buf.width() != w or buf.height() != h:
        buf = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        view._edge_fade_buf = buf
    buf.fill(0)
    p = QPainter(buf)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    visible = view.mapToScene(vp.rect()).boundingRect()
    if strip is not None:
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(QRectF(0, 0, w, h), strip,
                    QRectF(visible.x() - srect.x(),
                           visible.y() - srect.y(),
                           visible.width(), visible.height()))
    else:
        scene.render(p, QRectF(0, 0, w, h), visible)
    if f > 0.0:
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad.setColorAt(f, QColor(0, 0, 0, 255))
        grad.setColorAt(1.0 - f, QColor(0, 0, 0, 255))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_DestinationIn)
        fh = int(f * h + 1.0)
        p.fillRect(0, 0, w, fh, grad)
        p.fillRect(0, h - fh, w, fh, grad)
    p.end()
    out = QPainter(vp)
    out.drawImage(0, 0, buf)
    out.end()
