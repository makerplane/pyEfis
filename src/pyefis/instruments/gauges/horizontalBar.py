#  Copyright (c) 2013 Phil Birkelbach
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *


from .abstract import AbstractGauge
from pyefis.instruments import helpers

class HorizontalBar(AbstractGauge):
    def __init__(self, parent=None, min_size=True, font_family="DejaVu Sans Condensed"):
        super(HorizontalBar, self).__init__(parent)
        self.font_family = font_family
        if min_size:
            self.setMinimumSize(100, 50)
        self.show_value = True
        self.show_units = True
        self.show_name = True
        self.segments = 0 
        self.segment_gap_percent = 0.01
        self.segment_alpha = 180
        self.bar_divisor = 4.5
        # Optional font scaling percents (similar to vertical bars); if set, override legacy sizing
        self.small_font_percent = None  # fraction of widget height
        self.big_font_percent = None    # fraction of widget height
        # New options: place value/dbkey text on the left side of the bar
        self.value_on_bar_left = False
        self.value_on_bar_left_width_percent = 0.25  # portion of width reserved for left label
        self.show_dbkey_text = False  # when true, show dbkey text instead of numeric value on left label
        # Internals computed on resize
        self._bar_left = 0
        self._bar_width = 0
        self.barValueRect = QRectF()
        # Cache for top-row combined text (name/dbkey + units)
        self._top_text_cache = {
            'text': None,
            'w': 0,
            'h': 0,
            'font': None,
            'name_w': 0,
        }
    def getRatio(self):
        # Return X for 1:x specifying the ratio for this instrument
        return 2

    def resizeEvent(self, event):
        self.bigFont = QFont(self.font_family)
        self.section_size = self.height() / 12
        # Big font sizing: prefer percent if provided, else legacy section-size based
        if self.big_font_percent is not None:
            self.bigFont.setPixelSize(qRound(self.height() * float(self.big_font_percent)))
        else:
            self.bigFont.setPixelSize(qRound(self.section_size * 4))
        if self.font_mask:
            # Fit to width/height constraints if a mask exists
            self.bigFont.setPointSizeF(helpers.fit_to_mask(self.width()-5, self.bigFont.pixelSize() or (self.section_size * 4), self.font_mask, self.font_family))

        self.smallFont = QFont(self.font_family)
        if self.small_font_percent is not None:
            self.smallFont.setPixelSize(qRound(self.height() * float(self.small_font_percent)))
        else:
            self.smallFont.setPixelSize(qRound(self.section_size * 2))
        if self.name_font_mask:
            self.smallFont.setPointSizeF(helpers.fit_to_mask(self.width(), self.smallFont.pixelSize() or (self.section_size * 2.4), self.name_font_mask, self.font_family))

        self.unitsFont = QFont(self.font_family)
        if self.small_font_percent is not None:
            self.unitsFont.setPixelSize(qRound(self.height() * float(self.small_font_percent)))
        else:
            self.unitsFont.setPixelSize(qRound(self.section_size * 2))
        if self.units_font_mask:
            self.unitsFont.setPointSizeF(helpers.fit_to_mask(self.width(), self.unitsFont.pixelSize() or (self.section_size * 2.4), self.name_font_mask, self.font_family))

        self.barHeight = self.section_size * self.bar_divisor
        self.barTop = self.section_size * 2.7
        self.nameTextRect = QRectF(1, 0, self.width(), self.section_size * 2.4)
        self.valueTextRect = QRectF(1, self.section_size * 8, self.width()-5, self.section_size * 4)
        # Geometry is recalculated in paintEvent as well to reflect dynamic late-applied flags
        self._recompute_geometry()

    def _recompute_geometry(self):
        """Recalculate geometry based on current flags.
        Called in resizeEvent and paintEvent to handle preferences applied after initial resize."""
        self._bar_left = 0
        self._bar_width = self.width()
        if self.value_on_bar_left:
            pct = max(0.05, min(0.5, float(getattr(self, 'value_on_bar_left_width_percent', 0.25) or 0.25)))
            left_w = int(self.width() * pct)
            gap = 4
            self.barValueRect = QRectF(2, self.barTop, max(0, left_w - gap), self.barHeight)
            self._bar_left = left_w
            self._bar_width = max(0, self.width() - self._bar_left)
        else:
            self.barValueRect = QRectF()

    def _font_fit(self, base_font: QFont, text: str, rect: QRectF, min_px: int = 6) -> QFont:
        """Return a copy of base_font scaled so 'text' fits within rect (no clipping).
        Prefers pixelSize; falls back to pointSizeF if pixelSize is 0."""
        f = QFont(base_font)
        # Establish a starting pixel size based on height
        start_px = f.pixelSize() if f.pixelSize() > 0 else int(f.pointSizeF())
        if start_px <= 0:
            # default to a reasonable size proportional to rect height
            start_px = int(rect.height() * 0.8) if rect.height() > 0 else 12
        # Constrain by height first
        max_by_height = int(rect.height() * 0.9) if rect.height() > 0 else start_px
        size = max(min(start_px, max_by_height), min_px)
        # Quick proportional down-scale for width
        f.setPixelSize(size)
        fm = QFontMetrics(f)
        # Account for small padding
        avail_w = max(0, int(rect.width()) - 2)
        avail_h = max(0, int(rect.height()) - 2)
        if avail_w > 0:
            text_w = fm.horizontalAdvance(text)
            if text_w > 0 and text_w > avail_w:
                scale = avail_w / text_w
                size = max(min_px, int(size * scale))
                f.setPixelSize(size)
                fm = QFontMetrics(f)
        # Ensure height fits too
        if avail_h > 0:
            text_h = fm.height()
            if text_h > avail_h:
                scale = avail_h / text_h
                size = max(min_px, int(size * scale))
                f.setPixelSize(size)
        # Final safety loop to avoid off-by-one overflow
        fm = QFontMetrics(f)
        while (fm.horizontalAdvance(text) > avail_w or fm.height() > avail_h) and size > min_px:
            size -= 1
            f.setPixelSize(size)
            fm = QFontMetrics(f)
        return f

    def _get_top_layout(self):
        """Return fitted font and name width for top row (name/dbkey + units), using a small cache."""
        top_rect = self.nameTextRect
        name_text = (self.dbkey if self.show_dbkey_text else self.name) if self.show_name else ""
        units_text = self.units if self.show_units else ""
        spacer = " " if name_text and units_text else ""
        combined_text = f"{name_text}{spacer}{units_text}"
        key_changed = (
            combined_text != self._top_text_cache['text'] or
            top_rect.width() != self._top_text_cache['w'] or
            top_rect.height() != self._top_text_cache['h']
        )
        if key_changed:
            fitted_font = self._font_fit(self.smallFont, combined_text, top_rect)
            fm = QFontMetrics(fitted_font)
            name_w = fm.horizontalAdvance(name_text + spacer) if name_text else 0
            self._top_text_cache.update({
                'text': combined_text,
                'w': top_rect.width(),
                'h': top_rect.height(),
                'font': fitted_font,
                'name_w': name_w,
            })
        return self._top_text_cache['font'] or self.smallFont, (name_text, units_text, spacer, self._top_text_cache['name_w'])

    def get_bar_geometry(self):
        """Return (left, top, width, height) for the drawable bar region, respecting left label space."""
        return (int(self._bar_left), int(self.barTop), int(self._bar_width), int(self.barHeight))

    def paintEvent(self, event):
        # Ensure geometry reflects any preference attributes set after construction
        from time import perf_counter_ns
        from pyefis.diagnostics.overlay import GaugeDiagnostics
        _t0 = perf_counter_ns()
        self._recompute_geometry()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        #pen.setColor(self.textColor)
        #p.setPen(pen)
        # Top row: name/dbkey followed immediately by units (cached layout)
        top_rect = QRectF(self.nameTextRect)
        fitted_font, (name_text, units_text, spacer, name_w) = self._get_top_layout()
        p.setFont(fitted_font)
        # Optional ghost masks: draw individually at computed positions
        pen.setColor(self.textColor)
        p.setPen(pen)
        # Draw name/dbkey left
        if name_text:
            opt_left = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if self.name_font_ghost_mask:
                alpha = self.textColor.alpha()
                self.textColor.setAlpha(self.font_ghost_alpha)
                pen.setColor(self.textColor)
                p.setPen(pen)
                p.drawText(top_rect, self.name_font_ghost_mask, opt_left)
                self.textColor.setAlpha(alpha)
                pen.setColor(self.textColor)
                p.setPen(pen)
            p.drawText(top_rect, name_text, opt_left)
            if units_text:
                units_rect = QRectF(top_rect.left() + name_w, top_rect.top(), max(0, top_rect.width() - name_w), top_rect.height())
                if self.units_font_ghost_mask:
                    alpha = self.textColor.alpha()
                    self.textColor.setAlpha(self.font_ghost_alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                    p.drawText(units_rect, self.units_font_ghost_mask, opt_left)
                    self.textColor.setAlpha(alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                p.drawText(units_rect, units_text, opt_left)
        else:
            # No name; draw units starting at left
            if units_text:
                opt_left = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if self.units_font_ghost_mask:
                    alpha = self.textColor.alpha()
                    self.textColor.setAlpha(self.font_ghost_alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                    p.drawText(top_rect, self.units_font_ghost_mask, opt_left)
                    self.textColor.setAlpha(alpha)
                    pen.setColor(self.textColor)
                    p.setPen(pen)
                p.drawText(top_rect, units_text, opt_left)

        # Main Value (standard position) unless moved to left of bar
        if not self.value_on_bar_left:
            p.setFont(self.bigFont)
            opt = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
            if self.show_value: 
                if self.font_ghost_mask:
                    alpha = self.valueColor.alpha()
                    self.valueColor.setAlpha(self.font_ghost_alpha)
                    pen.setColor(self.valueColor)
                    p.setPen(pen)
                    p.drawText(self.valueTextRect, self.font_ghost_mask, opt)
                    self.valueColor.setAlpha(alpha)
                pen.setColor(self.valueColor)
                p.setPen(pen)
                p.drawText(self.valueTextRect, self.valueText, opt)
        else:
            # Draw numeric value as a label area to the left of the bar (always value here)
            label_text = self.valueText
            left_font = self._font_fit(self.bigFont, label_text or "", self.barValueRect)
            p.setFont(left_font)
            pen.setColor(self.valueColor)
            p.setPen(pen)
            opt_left = QTextOption(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            p.drawText(self.barValueRect, label_text, opt_left)

        # Draws the bar (clip so nothing bleeds under left label when reserved)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        bar_left, bar_top, bar_width, bar_height = self.get_bar_geometry()
        p.save()
        p.setClipRect(QRectF(bar_left, bar_top, bar_width, bar_height))
        pen.setColor(self.safeColor)
        brush = self.safeColor
        p.setPen(pen)
        p.setBrush(brush)
        p.drawRect(QRectF(bar_left, bar_top, bar_width, bar_height))
        # Warn regions
        pen.setColor(self.warnColor)
        brush = self.warnColor
        p.setPen(pen)
        p.setBrush(brush)
        if self.lowWarn:
            p.drawRect(QRectF(bar_left, bar_top,
                              self.interpolate(self.lowWarn, bar_width),
                              bar_height))
        if self.highWarn:
            x = bar_left + self.interpolate(self.highWarn, bar_width)
            p.drawRect(QRectF(x, bar_top,
                              (bar_left + bar_width) - x, bar_height))
        # Alarm regions
        pen.setColor(self.alarmColor)
        brush = self.alarmColor
        p.setPen(pen)
        p.setBrush(brush)
        if self.lowAlarm:
            p.drawRect(QRectF(bar_left, bar_top,
                              self.interpolate(self.lowAlarm, bar_width),
                              bar_height))
        if self.highAlarm:
            x = bar_left + self.interpolate(self.highAlarm, bar_width)
            p.drawRect(QRectF(x, bar_top,
                              (bar_left + bar_width) - x, bar_height))


        # Draw black bars to create segments
        if self.segments > 0:
            segment_gap = bar_width * self.segment_gap_percent
            segment_size = (bar_width - (segment_gap * (self.segments - 1)))/self.segments
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            pen.setColor(Qt.GlobalColor.black)
            p.setPen(pen)
            p.setBrush(Qt.GlobalColor.black)
            for segment in range(self.segments - 1):
                seg_left = bar_left + (((segment + 1) * segment_size) + (segment * segment_gap))
                p.drawRect(QRectF(seg_left, bar_top, segment_gap, bar_height))

        # Indicator Line
        pen.setColor(QColor(Qt.GlobalColor.darkGray))
        brush = QBrush(self.penColor)
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(brush)
        x = bar_left + self.interpolate(self._value, bar_width)
        if x < 0: x = 0
        if x > (bar_left + bar_width): x = (bar_left + bar_width)
        if not self.segments > 0:
            p.drawRect(QRectF(x-2, bar_top-4, 4, bar_height+8))
        else:
            # IF segmented, darken the top part of the bars from the line up
            pen.setColor(QColor(0, 0, 0, self.segment_alpha))
            p.setPen(pen)
            p.setBrush(QColor(0, 0, 0, self.segment_alpha))
            p.drawRect(QRectF(x, bar_top, (bar_left + bar_width) - x, bar_height))
        p.restore()
        # record diagnostics
        _t1 = perf_counter_ns()
        try:
            GaugeDiagnostics.get().record(self.__class__.__name__, _t1 - _t0)
        except Exception:
            pass

