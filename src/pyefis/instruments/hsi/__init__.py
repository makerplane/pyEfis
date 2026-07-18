#  Copyright (c) 2013 Neil Domalik; 2018-2019 Garrett Herschleb
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

import math
import time

from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *


from pyefis import common
import pyavtools.fix as fix
from pyefis import common
from pyefis.instruments import helpers

# TODO: Add CDI and Glide Slope indicators and tick marks but make them
#       configurable.


class HSI(QGraphicsView):
    def __init__(self, parent=None, font_size=15, font_percent=None, fg_color=Qt.GlobalColor.white, bg_color=Qt.GlobalColor.black, gsi_enabled=False, cdi_enabled=False, font_family="DejaVu Sans Condensed"):
        super(HSI, self).__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0%); border: 0px")
        self.font_family = font_family
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.font_percent = None
        if font_percent:
            self.font_percent = font_percent
            font_size = qRound(self.font_percent * self.width())
        self.fontSize = font_size
        self.tickSize = self.fontSize * 0.7
        self.fg_color = fg_color
        self.bg_color = bg_color
        # Compass-disc fill opacity, percent: 100 = solid face (default), 0 =
        # transparent so the SVS/PFD behind shows through the circle. This fills
        # the round compass disc, not the rectangular widget box.
        self.bg_opacity = 100
        # Selected-course pointer colour (the triangle driven by COURSE). With
        # source_auto_color on (default), this magenta is used for a GPS source
        # and vloc_color (green) for a VOR/LOC source, selected by NAVSRC
        # (2=GPS, 0/1=NAV). Off -> the pointer is always course_color.
        self.course_color = "#ff00ff"
        self.source_auto_color = True
        self.vloc_color = "#00ff00"
        # Nav-source annunciation: a small "GPS" / "VLOC1" / "VLOC2" label on the
        # rose face, coloured to match the source. Refined to VOR/LOC when NAVTYPE
        # is published. On by default.
        self.source_label_enabled = True
        # CDI/GSI deviation-needle colour + width.
        self.needle_color = "#ffff00"
        self.needle_width = 3
        # Garmin-style heading bug (cyan): a marker that scrolls to the selected
        # heading from the HEADBUG FIX key. Off by default -- not every panel
        # publishes a selected heading (a MAVLink trim/cruise autopilot has
        # none), so enable it in the editor once a source exists.
        self.heading_bug_enabled = False
        self.heading_bug_color = "#00ffff"
        # GPS ground-track diamond (magenta): a marker on the rose at the current
        # magnetic GPS ground track (TRACKM). Garmin shows it whenever there is a
        # valid track. Gated on ground speed (GPS track is meaningless near zero
        # groundspeed) -- shown only at or above track_min_speed kt. On by
        # default; it self-hides when TRACKM/GS are absent, stale, or below the
        # speed gate, so it is safe on panels without a GPS track source.
        self.track_indicator_enabled = True
        self.track_color = "#ff00ff"
        self.track_min_speed = 5.0
        self.gsi_enabled = gsi_enabled
        self.cdi_enabled = cdi_enabled
        # List for tick mark visibility, Top, Bottom, Right, Left
        self.visiblePointers = [True, True, True, True]

        self._CdiOld = True
        self._CdiBad = True
        self._CdiFail = True

        self._GsiOld = True
        self._GsiBad = True
        self._GsiFail = True

        self._CourseOld = True
        self._CourseBad = True
        self._CourseFail = True

        self._HeadOld = True
        self._HeadBad = True
        self._HeadFail = True

        self._courseDeviation = 0
        self._glideSlopeIndicator = 0
        self.labels = list()

        self.item = fix.db.get_item("COURSE")
        self._courseSelect = self.item.value
        self.item.valueChanged[float].connect(self.setCoursePointer)
        self.item.oldChanged[bool].connect(self.setCourseOld)
        self.item.badChanged[bool].connect(self.setCourseBad)
        self.item.failChanged[bool].connect(self.setCourseFail)
        self.setCourseOld(self.item.old)
        self.setCourseBad(self.item.bad)
        self.setCourseFail(self.item.fail)

        if self.cdi_enabled:
            self.cdidb = fix.db.get_item("CDI")
            self._courseDeviation = self.cdidb.value
            self.cdidb.valueChanged[float].connect(self.setCdi)
            self.cdidb.oldChanged[bool].connect(self.setCdiOld)
            self.cdidb.badChanged[bool].connect(self.setCdiBad)
            self.cdidb.failChanged[bool].connect(self.setCdiFail)
            self.setCdiOld(self.cdidb.old)
            self.setCdiBad(self.cdidb.bad)
            self.setCdiFail(self.cdidb.fail)
        else:
            self._CdiOld = False
            self._CdiBad = False
            self._CdiFail = False
        if self.gsi_enabled:
            self.gsidb = fix.db.get_item("GSI")
            self._glideSlopeIndicator = self.gsidb.value
            self.gsidb.valueChanged[float].connect(self.setGsi)
            self.gsidb.oldChanged[bool].connect(self.setGsiOld)
            self.gsidb.badChanged[bool].connect(self.setGsiBad)
            self.gsidb.failChanged[bool].connect(self.setGsiFail)
            self.setGsiOld(self.gsidb.old)
            self.setGsiBad(self.gsidb.bad)
            self.setGsiFail(self.gsidb.fail)
        else:
            self._GsiOld = False
            self._GsiBad = False
            self._GsiFail = False

        self.head = fix.db.get_item("HEAD")
        self._heading = self.head.value
        self.head.valueChanged[float].connect(self.setHeading)
        self.head.oldChanged[bool].connect(self.setHeadOld)
        self.head.badChanged[bool].connect(self.setHeadBad)
        self.head.failChanged[bool].connect(self.setHeadFail)
        self.setHeadFail(self.head.fail)
        self.setHeadOld(self.head.old)
        self.setHeadBad(self.head.bad)
        self.setHeadFail(self.head.fail)

        # Heading-bug source (HEADBUG). Subscribe always (like CDI/GSI); the
        # marker is only drawn when heading_bug_enabled. Guarded so a database
        # without the key can't break construction.
        self._hdgBug = 0.0
        self.hdg_bug_item = None
        try:
            self.hdgbugdb = fix.db.get_item("HEADBUG")
            self._hdgBug = self.hdgbugdb.value or 0.0
            self.hdgbugdb.valueChanged[float].connect(self.setHdgBug)
        except Exception:
            self.hdgbugdb = None

        # GPS ground track (TRACK) + ground speed (GS) for the track diamond.
        # Subscribe always (the marker is drawn only when enabled); guarded so a
        # database without these keys can't break construction -- the diamond
        # then simply never shows. GS gates the marker by speed; if there is no
        # GS source the gate is skipped (track shown whenever valid).
        self._track = 0.0
        self._gs = 0.0
        self._TrackOld = True
        self._TrackBad = True
        self._TrackFail = True
        self.track_item = None
        try:
            self.trackdb = fix.db.get_item("TRACKM")
            self._track = self.trackdb.value or 0.0
            self.trackdb.valueChanged[float].connect(self.setTrack)
            self.trackdb.oldChanged[bool].connect(self.setTrackOld)
            self.trackdb.badChanged[bool].connect(self.setTrackBad)
            self.trackdb.failChanged[bool].connect(self.setTrackFail)
            self._TrackOld = self.trackdb.old
            self._TrackBad = self.trackdb.bad
            self._TrackFail = self.trackdb.fail
        except Exception:
            self.trackdb = None
        try:
            self.gsdb = fix.db.get_item("GS")
            self._gs = self.gsdb.value or 0.0
            self.gsdb.valueChanged[float].connect(self.setGs)
        except Exception:
            self.gsdb = None

        # Selected nav source (NAVSRC: 0=NAV1, 1=NAV2, 2=GPS) for source-based
        # colouring of the course pointer + CDI (magenta GPS / green VLOC).
        # Subscribed defensively; absent source -> _navsrc stays None and the
        # static colours are used.
        self._navsrc = None
        try:
            self.navsrcdb = fix.db.get_item("NAVSRC")
            self._navsrc = self.navsrcdb.value
            self.navsrcdb.valueChanged[float].connect(self.setNavsrc)
        except Exception:
            self.navsrcdb = None
        # Active source kind (NAVTYPE: 0=GPS, 1=VOR, 2=LOC, 3=LOC-BC) refines the
        # source label (VOR1/LOC1 vs the NAVSRC-only VLOC1). Defensive; absent ->
        # the label falls back to GPS/VLOCn from NAVSRC alone.
        self._navtype = None
        try:
            self.navtypedb = fix.db.get_item("NAVTYPE")
            self._navtype = self.navtypedb.value
            self.navtypedb.valueChanged[float].connect(self.setNavtype)
        except Exception:
            self.navtypedb = None
        # Glideslope/glidepath validity for the selected source (GSV: 1 = GS
        # present, 0 = none). A VOR has no glideslope, so GSV=0 hides the GS
        # needle while the lateral CDI stays. Defensive; absent -> the GS shows
        # on its own quality, preserving behaviour where GSV is not published.
        self._gsv = None
        try:
            self.gsvdb = fix.db.get_item("GSV")
            self._gsv = self.gsvdb.value
            self.gsvdb.valueChanged[float].connect(self.setGsv)
        except Exception:
            self.gsvdb = None
        # VOR TO/FROM for the selected source (TOFROM: 0=off/flag, 1=TO, 2=FROM).
        # Drawn as a triangle on the course line; hidden when 0 (LOC/GPS or no
        # signal). Defensive; absent -> not shown.
        self._tofrom = 0
        try:
            self.tofromdb = fix.db.get_item("TOFROM")
            self._tofrom = self.tofromdb.value or 0
            self.tofromdb.valueChanged[float].connect(self.setTofrom)
        except Exception:
            self.tofromdb = None

        self._showCDI = not self.isOld()
        self._showGSI = not self.isOld()
        self._showHdgFlag = False
        self._showNavFlag = False
        self._showGsFlag = False
        self.cardinal = ["N", "E", "S", "W"]
        self.course_pointer = None
        self.myparent = parent
        self.update_period = None

    def getRatio(self):
        # Return X for 1:x specifying the ratio for this instrument
        return 1

    def resizeEvent(self, event):
        if self.font_percent:
            self.fontSize = qRound(self.font_percent * self.width())
        self.tickSize = self.fontSize * 0.7
        self.scene = QGraphicsScene(0, 0, self.width(), self.height())
        self.cx = self.width() / 2.0
        self.cy = self.height() / 2.0
        self.r = self.height() / 2.0 - 5.0
        self.cdippw = self.r * 0.5
        self.gsipph = self.r * 0.5

        # Compass-disc background fill, behind the rose (z=-1), honouring
        # bg_opacity: a solid face by default (1.0), or transparent (0.0) so the
        # SVS/PFD behind the round instrument shows through. Drawn as a scene
        # item (not drawBackground) so it is rendered fresh and isn't subject to
        # the view's background caching.
        _op = max(0.0, min(1.0, float(getattr(self, "bg_opacity", 100)) / 100.0))
        if _op > 0.0:
            _disc = QColor(self.bg_color)
            _disc.setAlphaF(_op)
            _bgitem = self.scene.addEllipse(
                self.cx - self.r, self.cy - self.r, self.r * 2.0, self.r * 2.0,
                QPen(Qt.PenStyle.NoPen), QBrush(_disc))
            _bgitem.setZValue(-1)

        # Setup Pens
        compassPen = QPen(QColor(self.fg_color), self.fontSize * 0.02)
        textBrush = QBrush(QColor(self.fg_color))
        nobrush = QBrush()

        _cp = self._course_pointer_color()
        headingPen = QPen(_cp)
        headingBrush = QBrush(_cp)
        headingPen.setWidth(1)


        f = QFont(self.font_family)
        f.setPixelSize(self.fontSize)

        for count in range(0, 360, 5):
            angle = (count) * math.pi / 180.0
            cosa = math.cos(angle)
            sina = math.sin(angle)
            iy1 = -self.r
            iy2 = -self.r + self.tickSize
            if count % 10 != 0:
                iy2 -= self.tickSize/2
            x1 = (-iy1*sina) + self.cx # (ix*cosa - iy*sina) ix factor removed Since x is 0
            y1 = iy1*cosa + self.cy # (iy*cosa + ix*sina)
            x2 = (-iy2*sina) + self.cx
            y2 = iy2*cosa + self.cy
            self.scene.addLine(x1, y1, x2, y2, compassPen)
            if count % 90 == 0:
                t = self.scene.addSimpleText(self.cardinal[int(count / 90)], f)
                br = t.sceneBoundingRect()
                t.setRotation(count)
                t.setPen(compassPen)
                t.setBrush(textBrush)
                iy3 = -self.r + self.tickSize*1.1
                ix3 = -br.width()/2
                x3 = (ix3*cosa - iy3*sina) + self.cx
                y3 = (iy3*cosa + ix3*sina) + self.cy
                t.setPos(x3, y3)
                self.labels.append(t)
            elif count % 30 == 0:
                text = str(int(count / 10))
                t = self.scene.addSimpleText(text, f)
                br = t.sceneBoundingRect()
                t.setRotation(count)
                t.setPen(compassPen)
                t.setBrush(textBrush)
                iy3 = -self.r + self.tickSize*1.1
                ix3 = -br.width()/2
                x3 = (ix3*cosa - iy3*sina) + self.cx
                y3 = (iy3*cosa + ix3*sina) + self.cy
                t.setPos(x3, y3)
                self.labels.append(t)

        # Course pointer (driven by COURSE): the selected-course triangle,
        # coloured by source (magenta GPS / green VLOC) when source_auto_color is
        # on, else course_color.
        triangle = self.course_pointer_polygon()
        self.course_pointer = self.scene.addPolygon(triangle, headingPen, headingBrush)
        # The visible course pointer + CDI are drawn in paintEvent, rotated to the
        # course on the heading-up card (HSI style); hide the scene triangle so the
        # head is not doubled. The item is kept for course/state bookkeeping.
        self.course_pointer.setVisible(False)

        # Garmin-style heading bug (cyan): scrolls to the HEADBUG selected
        # heading on the inside of the ring. Drawn only when enabled.
        self.hdg_bug_item = None
        if getattr(self, "heading_bug_enabled", False):
            _hbc = QColor(self.heading_bug_color)
            self.hdg_bug_item = self.scene.addPolygon(
                self._hdg_bug_polygon(), QPen(_hbc), QBrush(_hbc))

        # GPS ground-track diamond (magenta). Created when enabled; its
        # visibility is gated on speed/quality by _update_track().
        self.track_item = None
        if getattr(self, "track_indicator_enabled", False):
            _tc = QColor(self.track_color)
            self.track_item = self.scene.addPolygon(
                self._track_diamond_polygon(), QPen(_tc), QBrush(_tc))
            self._update_track()

        self.setScene(self.scene)
        # Clear any prior view rotation before re-applying. resizeEvent can fire
        # repeatedly (initial layout settling, any geometry change), and the
        # rotation is a view transform that persists across the scene rebuild --
        # without this reset each call stacked another -heading rotation, baking
        # in a permanent offset (the card showed heading+offset, e.g. 290 when
        # actually 052). setHeading then tracks incrementally from this baseline.
        self.resetTransform()
        self.rotate(-self._heading)

        # Draws the static overlay stuff to a pixmap
        self.map = QPixmap(self.width(), self.height())
        self.map.fill(Qt.GlobalColor.transparent)
        p = QPainter(self.map)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # set the width and height for conveinience
        # w = self.width()
        # h = self.height()

        p.setPen(QPen(QColor(self.fg_color),self.fontSize * 0.07))
        p.setBrush(QColor(Qt.GlobalColor.transparent))
        # Outer ring
        p.drawEllipse(QRectF(self.cx-self.r, self.cy-self.r, self.r*2.0, self.r*2.0))
        # Draw the pointer marks
        p.setPen(QPen(QColor(Qt.GlobalColor.yellow), 3))
        if self.visiblePointers[0]:
            # Top Pointer
            p.drawLine(QLineF(self.cx, self.cy - self.r - 5,
                              self.cx, self.cy - self.r + self.fontSize*2))
        if self.visiblePointers[1]:
            # Bottom Pointer
            p.drawLine(QLineF(self.cx, self.cy + self.r + 5,
                              self.cx, self.cy + self.r - self.fontSize*2))
        if self.visiblePointers[2]:
            # Right Pointer
            p.drawLine(QLineF(self.cx + self.r + 5, self.cy,
                              self.cx + self.r - self.fontSize*2, self.cy))
        if self.visiblePointers[3]:
            # Left Pointer
            p.drawLine(QLineF(self.cx - self.r - 5, self.cy,
                              self.cx - self.r + self.fontSize*2, self.cy))

        self.overlay = self.map.toImage()



    def course_pointer_polygon(self):
        inc = int(self.tickSize)
        iyb = -self.r
        points = [ (inc, -self.r),
                  (-inc, -self.r),
                  (0, -self.r + inc)]
        angle = (self._courseSelect) * math.pi / 180
        cosa = math.cos(angle)
        sina = math.sin(angle)

        points = [((ix*cosa - iy*sina), (iy*cosa + ix*sina)) for ix,iy in points]
        points = [QPointF((ix + self.cx), (iy + self.cy)) for ix,iy in points]
        triangle = QPolygonF(points)
        return triangle

    def _hdg_bug_polygon(self):
        # Classic notched heading-bug shape on the inside of the ring, rotated
        # to the selected heading (_hdgBug).
        inc = int(self.tickSize)
        w = inc
        h = inc * 1.3
        yo = -self.r            # outer edge (at the ring)
        yi = -self.r + h        # inner base
        yn = -self.r + h * 0.5  # notch depth
        points = [(-w, yi), (-w, yo), (-w * 0.35, yo), (-w * 0.35, yn),
                  (w * 0.35, yn), (w * 0.35, yo), (w, yo), (w, yi)]
        angle = (self._hdgBug) * math.pi / 180.0
        cosa = math.cos(angle)
        sina = math.sin(angle)
        points = [((ix * cosa - iy * sina), (iy * cosa + ix * sina))
                  for ix, iy in points]
        points = [QPointF((ix + self.cx), (iy + self.cy)) for ix, iy in points]
        return QPolygonF(points)

    def setHdgBug(self, value):
        if value != self._hdgBug:
            self._hdgBug = common.bounds(0, 360, value)
            if self.hdg_bug_item is not None:
                self.hdg_bug_item.setPolygon(self._hdg_bug_polygon())

    def _track_diamond_polygon(self):
        # Small diamond on the rose face near the outer edge, rotated to the GPS
        # ground track (_track). Scene-space like the other markers, so the view
        # rotation places it at (track - heading) from the lubber line.
        s = self.tickSize * 0.55
        yc = -self.r + self.tickSize * 1.3
        points = [(0, yc - s), (s, yc), (0, yc + s), (-s, yc)]
        angle = self._track * math.pi / 180.0
        cosa = math.cos(angle)
        sina = math.sin(angle)
        points = [((ix * cosa - iy * sina), (iy * cosa + ix * sina))
                  for ix, iy in points]
        points = [QPointF((ix + self.cx), (iy + self.cy)) for ix, iy in points]
        return QPolygonF(points)

    def _track_visible(self):
        # Only with a valid track and, when a GS source exists, at or above the
        # speed gate (GPS track is noise near zero groundspeed).
        if not getattr(self, "track_indicator_enabled", False):
            return False
        if self._TrackOld or self._TrackBad or self._TrackFail:
            return False
        if self.gsdb is not None and self._gs < self.track_min_speed:
            return False
        return True

    def _update_track(self):
        if self.track_item is None:
            return
        vis = self._track_visible()
        self.track_item.setVisible(vis)
        if vis:
            self.track_item.setPolygon(self._track_diamond_polygon())

    def setTrack(self, value):
        v = common.bounds(0, 360, value)
        if v != self._track:
            self._track = v
            self._update_track()

    def setGs(self, value):
        if value != self._gs:
            self._gs = value
            self._update_track()

    def setTrackOld(self, old):
        self._TrackOld = old
        self._update_track()

    def setTrackBad(self, bad):
        self._TrackBad = bad
        self._update_track()

    def setTrackFail(self, fail):
        self._TrackFail = fail
        self._update_track()

    def _rose_image(self):
        """The static rose (disc, ticks, cardinal/numeral labels) baked
        UNROTATED at 2x supersample -- once per scene build (#94). The
        heading rotation is applied at blit time in paintEvent; the
        dynamic card items (heading bug, track diamond) are hidden
        during the bake and drawn directly under the same rotation.
        The cache holds the scene OBJECT (resizeEvent replaces the
        scene wholesale; id() could be recycled -- same hazard as the
        tape strip cache, #93)."""
        scene = self.scene
        w, hgt = self.width(), self.height()
        key = (w, hgt, float(self.fontSize))
        cached = getattr(self, "_rose_cache", None)
        if (cached is not None and cached[0] is scene
                and cached[1] == key):
            return cached[2]
        ss = 2
        img = QImage(w * ss, hgt * ss,
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        dyn = [i for i in (self.hdg_bug_item, self.track_item)
               if i is not None]
        vis = [i.isVisible() for i in dyn]
        for i in dyn:
            i.setVisible(False)
        try:
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.scene.render(p, QRectF(0, 0, w * ss, hgt * ss),
                              QRectF(0, 0, w, hgt))
            p.end()
        finally:
            for i, v in zip(dyn, vis):
                i.setVisible(v)
        self._rose_cache = (scene, key, img)
        return img

    def paintEvent(self, event):
        # The rose is static art on a rotating card: blit the cached
        # unrotated bake through the heading rotation instead of having
        # QGraphicsView re-render ~84 items per frame (#94 -- the HSI
        # was ~24% of all GIL time in flight). The heading bug and
        # track diamond are the only dynamic card items; they are drawn
        # here under the same rotation, in scene coordinates, exactly
        # as their scene polygons are computed. setHeading still
        # rotates the (now unpainted) view so scene-item updates keep
        # scheduling repaints.
        c = QPainter(self.viewport())
        c.setRenderHint(QPainter.RenderHint.Antialiasing)
        c.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        c.save()
        c.translate(self.cx, self.cy)
        c.rotate(-self._heading)
        c.drawImage(QRectF(-self.cx, -self.cy,
                           self.width(), self.height()),
                    self._rose_image())
        c.translate(-self.cx, -self.cy)
        if self.hdg_bug_item is not None:
            _hbc = QColor(self.heading_bug_color)
            c.setPen(QPen(_hbc))
            c.setBrush(QBrush(_hbc))
            c.drawPolygon(self._hdg_bug_polygon())
        if self.track_item is not None and self.track_item.isVisible():
            _tc = QColor(self.track_color)
            c.setPen(QPen(_tc))
            c.setBrush(QBrush(_tc))
            c.drawPolygon(self._track_diamond_polygon())
        c.restore()

        # Put the static overlay image on the view
        c.drawImage(self.rect(), self.overlay)


        compassPen = QPen(QColor(self.fg_color))
        cdiPen = QPen(self._source_color() or QColor(self.needle_color))
        cdiPen.setWidth(int(getattr(self, "needle_width", 3)))
        c.setRenderHint(QPainter.RenderHint.Antialiasing)


        # Course pointer + lateral deviation (CDI) + TO/FROM as one assembly,
        # rotated to the selected course on the heading-up card (on-screen course
        # angle = COURSE - HEADING) so it turns with the rose like a real HSI.
        if self.cdi_enabled or self.gsi_enabled:
            ang = (self._courseSelect - self._heading) * math.pi / 180.0
            ca = math.cos(ang); sa = math.sin(ang)

            def _p(lx, ly):   # local (lateral, along; -along = toward course head)
                return QPointF(self.cx + lx*ca - ly*sa, self.cy + ly*ca + lx*sa)

            ext = self.r - self.fontSize * 2.0
            bar = self.cdippw
            self._showCDI = self.cdi_enabled and not (self._CdiOld or self._CdiBad)
            self._showGSI = self.gsi_enabled and (self._gsv is None or self._gsv >= 0.5) \
                and not (self._GsiOld or self._GsiBad or self._GsiFail)

            if self.cdi_enabled:
                # Lateral deviation scale dots (white) along the lateral axis.
                c.setPen(QPen(QColor(self.fg_color)))
                c.setBrush(QBrush(QColor(self.fg_color)))
                dotr = max(1.5, self.tickSize * 0.16)
                for dev in (-1.0, -2.0/3.0, -1.0/3.0, 1.0/3.0, 2.0/3.0, 1.0):
                    c.drawEllipse(_p(dev * bar, 0.0), dotr, dotr)
                # Course pointer (source colour): head + tail through centre with
                # an arrowhead; the CDI bar (middle) carries the lateral deviation.
                cpc = self._course_pointer_color()
                cw = max(2, int(getattr(self, "needle_width", 3)))
                c.setPen(QPen(cpc, cw)); c.setBrush(QBrush(cpc))
                arr = self.tickSize
                c.drawLine(_p(0.0, bar), _p(0.0, ext))                     # tail
                c.drawLine(_p(0.0, -bar), _p(0.0, -ext + arr))             # head
                c.drawPolygon(QPolygonF([_p(0.0, -ext), _p(arr * 0.55, -ext + arr),
                                         _p(-arr * 0.55, -ext + arr)]))    # arrowhead
                if self._showCDI:
                    off = self._courseDeviation * bar
                    c.drawLine(_p(off, -bar), _p(off, bar))                # CDI bar
                # TO/FROM triangle: apex toward the head (TO) or tail (FROM).
                tf = int(round(self._tofrom)) if self._tofrom else 0
                if self._showCDI and tf in (1, 2):
                    rr = self.r * 0.42
                    s = self.tickSize * 0.6
                    length = self.tickSize * 1.1
                    if tf == 1:
                        pts = [(0.0, -(rr + length)), (s, -rr), (-s, -rr)]
                    else:
                        pts = [(0.0, -(rr - length)), (s, -rr), (-s, -rr)]
                    c.drawPolygon(QPolygonF([_p(lx, ly) for lx, ly in pts]))

            if self.gsi_enabled and (self._gsv is None or self._gsv >= 0.5):
                # Glideslope/glidepath: a vertical deviation scale on the RIGHT of
                # the rose (HSI convention) with a source-coloured diamond pointer.
                # Centre = on path; two dots each side. Hidden when there is no
                # glideslope (e.g. a VOR).
                gx = self.cx + self.r * 0.72
                grange = self.gsipph
                c.setPen(QPen(QColor(self.fg_color)))
                c.setBrush(QBrush(QColor(self.fg_color)))
                gdot = max(1.5, self.tickSize * 0.16)
                c.drawLine(qRound(gx - self.tickSize*0.55), qRound(self.cy),
                           qRound(gx + self.tickSize*0.55), qRound(self.cy))
                for dev in (-1.0, -0.5, 0.5, 1.0):
                    c.drawEllipse(QPointF(gx, self.cy - dev*grange), gdot, gdot)
                if self._showGSI:
                    gsc = self._source_color() or QColor(self.needle_color)
                    c.setPen(QPen(gsc)); c.setBrush(QBrush(gsc))
                    gy = self.cy - self._glideSlopeIndicator * grange
                    ds = self.tickSize * 0.6
                    c.drawPolygon(QPolygonF([QPointF(gx, gy - ds), QPointF(gx + ds, gy),
                                             QPointF(gx, gy + ds), QPointF(gx - ds, gy)]))

        # Nav-source annunciation (top-left), coloured to match the active source.
        # Its bounding box is stored as a tap target -- tapping it cycles NAVSRC
        # (see mousePressEvent).
        self._source_label_rect = None
        if getattr(self, "source_label_enabled", True):
            label = self._source_label()
            if label:
                c.setPen(QPen(self._source_color() or QColor(self.course_color)))
                lf = QFont(self.font_family)
                lf.setPixelSize(int(self.fontSize))
                c.setFont(lf)
                lx = qRound(self.width() * 0.03)
                ly = qRound(self.fontSize * 1.2)
                c.drawText(lx, ly, label)
                fm = c.fontMetrics()
                pad = int(self.fontSize * 0.5)
                self._source_label_rect = (lx - pad, ly - fm.ascent() - pad,
                                           fm.horizontalAdvance(label) + 2*pad,
                                           fm.height() + 2*pad)

        # Warning flags (AC 25-11B: warnings red). A flag positively annunciates
        # an invalid signal, distinct from merely hiding an element -- see
        # hsi_widget_spec.md sec 7.1. Heading (compass) flag: HEAD invalid.
        self._showHdgFlag = self._HeadFail or self._HeadBad
        if self._showHdgFlag:
            self._draw_flag(c, "HDG", self.cx, self.fontSize * 1.1)
        # NAV (lateral) flag: selected lateral source invalid. The CDI bar is
        # already removed by _showCDI; the flag positively annunciates the loss.
        self._showNavFlag = self._CdiFail or self._CdiBad
        if self._showNavFlag:
            self._draw_flag(c, "NAV", self.cx - self.r * 0.4, self.cy)
        # GS flag: glideslope expected (present per GSV) but its signal is
        # unreliable (bad/failed). The diamond (_showGSI) already excludes bad/fail,
        # so the diamond and this flag are mutually exclusive. Distinct from 'no GS
        # present' (GSV<0.5), where the scale is simply absent -- no flag.
        self._showGsFlag = (self.gsi_enabled
                            and self._gsv is not None and self._gsv >= 0.5
                            and (self._GsiFail or self._GsiBad))
        if self._showGsFlag:
            self._draw_flag(c, "GS", self.cx + self.r * 0.72, self.cy)

    def _draw_flag(self, c, text, x, y):
        """Draw a red boxed warning flag centred at (x, y) (AC 25-11B: warnings
        red). Black fill keeps it legible over the compass card."""
        red = QColor(255, 0, 0)
        f = QFont(self.font_family)
        f.setBold(True)
        f.setPixelSize(int(self.fontSize))
        c.setFont(f)
        fm = c.fontMetrics()
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        pad = int(self.fontSize * 0.3)
        box = QRectF(x - tw / 2.0 - pad, y - th / 2.0 - pad,
                     tw + 2 * pad, th + 2 * pad)
        c.setBrush(QBrush(QColor(0, 0, 0)))
        c.setPen(QPen(red, max(2, int(self.fontSize * 0.12))))
        c.drawRect(box)
        c.setPen(QPen(red))
        c.drawText(box, int(Qt.AlignmentFlag.AlignCenter), text)

    def getHeading(self):
        return self._heading

    def setHeading(self, heading):
        if heading != self._heading:
            now = time.time()
            newheading = common.bounds(0, 360, heading)
            diff = newheading - self._heading
            if diff > 180:
                diff -= 360
            elif diff < -180:
                diff += 360
            self._heading = newheading
            self.rotate(-diff)
            self.last_update_time = now

    def setHeadOld(self,old):
        self._HeadOld = old

    def setHeadBad(self,bad):
        self._HeadBad = bad

    def setHeadFail(self,fail):
        if fail != self._HeadFail:
            self._HeadFail = fail
            self.changeFail()
 
    heading = property(getHeading, setHeading)

    def isOld(self):
        return self._GsiOld    or self._GsiBad\
            or self._CdiOld    or self._CdiBad\
            or self._HeadOld   or self._HeadBad\
            or self._CourseOld or self._CourseBad

    def isFail(self):
        return self._GsiFail\
            or self._CdiFail\
            or self._HeadBad\
            or self._CourseBad

    def changeFail(self):
        if self.isFail():
            for l in self.labels:
                l.setOpacity(0)
        else:
            for l in self.labels:
                l.setOpacity(1)

    def getCoursePointer(self):
        return self._courseSelect

    def setCoursePointer(self, course):
        if course != self._courseSelect:
            self._courseSelect = common.bounds(0, 360, course)
            if self.course_pointer is not None:
                self.course_pointer.setPolygon(self.course_pointer_polygon())
            if self.isVisible():
                self.update()

    coursePointer = property(getCoursePointer, setCoursePointer)

    def _source_color(self):
        """Active-source colour for the course pointer and CDI/GSI when
        source_auto_color is on: course_color (magenta) for a GPS source,
        vloc_color (green) for a VOR/LOC source. Returns None when auto-colouring
        is off or NAVSRC is unavailable, so callers fall back to the static
        per-element colour."""
        if not getattr(self, "source_auto_color", False):
            return None
        if self._navsrc is None:
            return None
        # NAVSRC 2 = GPS (magenta); 0/1 = NAV1/NAV2 (green).
        if int(round(self._navsrc)) == 2:
            return QColor(self.course_color)
        return QColor(self.vloc_color)

    def _course_pointer_color(self):
        return self._source_color() or QColor(self.course_color)

    def setNavsrc(self, value):
        if value != self._navsrc:
            self._navsrc = value
            # Recolour the course pointer now; the CDI/GSI recolour on next paint.
            if getattr(self, "course_pointer", None) is not None:
                _cp = self._course_pointer_color()
                self.course_pointer.setPen(QPen(_cp))
                self.course_pointer.setBrush(QBrush(_cp))
            if self.isVisible():
                self.update()

    def setNavtype(self, value):
        if value != self._navtype:
            self._navtype = value
            if self.isVisible():
                self.update()

    def setGsv(self, value):
        if value != self._gsv:
            self._gsv = value
            if self.isVisible():
                self.update()

    def setTofrom(self, value):
        if value != self._tofrom:
            self._tofrom = value
            if self.isVisible():
                self.update()

    def mousePressEvent(self, event):
        # Tapping the nav-source annunciation cycles the source: GPS -> NAV1 ->
        # NAV2 -> GPS (NAVSRC 2/0/1). Anywhere else, default handling.
        r = getattr(self, "_source_label_rect", None)
        if r is not None and getattr(self, "navsrcdb", None) is not None:
            px, py = event.pos().x(), event.pos().y()
            if r[0] <= px <= r[0] + r[2] and r[1] <= py <= r[1] + r[3]:
                cur = int(round(self._navsrc)) if self._navsrc is not None else 2
                fix.db.set_value("NAVSRC", float((cur + 1) % 3))
                event.accept()
                return
        super(HSI, self).mousePressEvent(event)

    def _source_label(self):
        """Nav-source annunciation text: "GPS" for a GPS source, "VOR{n}" /
        "LOC{n}" when NAVTYPE identifies the NAV radio, else "VLOC{n}" from NAVSRC
        alone. Empty when no source is available."""
        if self._navsrc is None:
            return ""
        src = int(round(self._navsrc))
        if src == 2:
            return "GPS"
        slot = src + 1                          # NAVSRC 0->NAV1, 1->NAV2
        nt = None if self._navtype is None else int(round(self._navtype))
        if nt == 1:
            return f"VOR{slot}"
        if nt in (2, 3):
            return f"LOC{slot}"
        return f"VLOC{slot}"

    def setCourseOld(self,old):
        self._CourseOld = old

    def setCourseBad(self,bad):
        self._CourseBad = bad

    def setCourseFail(self,fail):
        if fail != self._CourseFail:
            self._CourseFail = fail
            self.changeFail()

    def getCdi(self):
        return self._courseDeviation

    def setCdi(self, cdi):
        if cdi != self._courseDeviation:
            self._courseDeviation = cdi
            if self.isVisible(): 
                self.update()

    def setCdiOld(self, old):
        if self.cdi_enabled:
            self._CdiOld = old
            if self.isVisible():
                self.update()

    def setCdiBad(self, bad):
        if self.cdi_enabled:
            self._CdiBad = bad
            if self.isVisible():
                self.update()

    def setCdiFail(self, fail):
        if self.cdi_enabled:
            if fail != self._CdiFail:
                self._CdiFail = fail
                self.changeFail()


    cdi = property(getCdi, setCdi)

    def getGsi(self):
        return self._glideSlopeIndicator

    def setGsi(self, gsi):
        if gsi != self._glideSlopeIndicator:
            self._glideSlopeIndicator = gsi
            if self.isVisible(): self.update()

    gsi = property(getGsi, setGsi)

    def setGsiOld(self, old):
        if self.gsi_enabled:
            self._GsiOld = old
            if self.isVisible():
                self.update()

    def setGsiBad(self, bad):
        if self.gsi_enabled:
            self._GsiBad = bad
            if self.isVisible():
                self.update()

    def setGsiFail(self, fail):
        if self.gsi_enabled:
            if fail != self._GsiFail:
                self._GsiFail = fail
                self.changeFail()


    # We don't want this responding to keystrokes
    def keyPressEvent(self, event):
        pass

    # Don't want it acting with the mouse scroll wheel either
    def wheelEvent(self, event):
        pass

    def showEvent(self, event):
        self.update()


class HeadingDisplay(QWidget):
    def __init__(self, parent=None, fg_color="#aaaaaa", bg_color="#000000", bg_opacity=100, font_family="DejaVu Sans Condensed" ):
        super(HeadingDisplay, self).__init__(parent)
        self.font_family = font_family
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.fg_color = fg_color
        self.bg_color = bg_color
        # Background-fill opacity, percent: 100 = solid box (default), 0 = fully
        # transparent so whatever is behind the box (e.g. the SVS/PFD) shows
        # through. The widget area itself is made transparent so the paintEvent
        # fill alpha is what controls the look.
        self.bg_opacity = bg_opacity
        self.setStyleSheet("background: transparent")

        self._Old = True
        self._Bad = True
        self._Fail = True

        self.item = fix.db.get_item("HEAD")
        self.item.valueChanged[float].connect(self.setHeading)
        self.item.failChanged[bool].connect(self.setFail)
        self.item.badChanged[bool].connect(self.setBad)
        self.item.oldChanged[bool].connect(self.setOld)
        self.setOld(self.item.old)
        self.setBad(self.item.bad)
        self.setFail(self.item.fail)

        self._heading = self.item.value

        self.font = QFont(self.font_family)
        self.font.setBold(True)
        # Include the degree sign so the font is sized to the actual content
        # ("030°"), not three bare digits — otherwise the trailing ° pushes the
        # centred text tight against the box edges.
        self.font_mask = "999°"
        self.font_percent = 0.80
        self.font_size = helpers.fit_to_mask(self.width()*self.font_percent ,self.height()*self.font_percent,self.font_mask,self.font_family)
        self.font.setPointSizeF(self.font_size)

    def resizeEvent(self, event):
        self.font_size = helpers.fit_to_mask(self.width()*self.font_percent ,self.height()*self.font_percent,self.font_mask,self.font_family)
        self.font.setPointSizeF(self.font_size)

    def paintEvent(self, event):
        self.font.setPointSizeF(self.font_size)
        c = QPainter(self)
        compassPen = QPen(QColor(self.fg_color))
        bg = QColor(self.bg_color)
        try:
            bg.setAlphaF(max(0.0, min(1.0, float(self.bg_opacity) / 100.0)))
        except (TypeError, ValueError):
            pass
        compassBrush = QBrush(bg)
        c.setPen(compassPen)
        c.setBrush(compassBrush)
        c.setFont(self.font)
        tr = QRectF(0, 0, self.width()-1, self.height()-1)
        c.drawRect(tr)
        if self._Fail:
            heading_text = "XXX"
            c.setBrush(QBrush(QColor(Qt.GlobalColor.red)))
            c.setPen(QPen(QColor(Qt.GlobalColor.red)))
        elif self._Bad:
            heading_text = ""
            c.setBrush(QBrush(QColor(255, 150, 0)))
            c.setPen(QPen(QColor(255, 150, 0)))
        elif self._Old:
            heading_text = ""
            c.setBrush(QBrush(QColor(255, 150, 0)))
            c.setPen(QPen(QColor(255, 150, 0)))
        else:
            heading_text = self._fmt_heading(self._heading)

        c.drawText(tr, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, heading_text)

    @staticmethod
    def _fmt_heading(value):
        """Heading as three zero-padded digits with a trailing degree sign:
        3 -> "003°", 30 -> "030°", 360/0 -> "000°"."""
        return f"{int(value) % 360:03d}°"

    def getHeading(self):
        return self._heading

    def setHeading(self, heading):
        if heading != self._heading:
            self._heading = common.bounds(0, 360, heading)
            if self.isVisible(): self.update()

    heading = property(getHeading, setHeading)

    def setFail(self, fail):
        self._Fail = fail
        self.repaint()

    def setOld(self, old):
        self._Old = old
        self.repaint()

    def setBad(self, bad):
        self._Bad = bad
        self.repaint()

    def showEvent(self, event):
        self.update()

class DG_Tape(QGraphicsView):
    def __init__(self, parent=None, font_family="DejaVu Sans Condensed"):
        super(DG_Tape, self).__init__(parent)
        self.setStyleSheet("border: 0px")
        self.font_family = font_family
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.fontsize = 20
        self._heading = 1
        self._headingSelect = 1
        self._courseSelect = 1
        self._courseDevation = 1
        self.cardinal = ["N", "E", "S", "W", "N"]

        self.item = fix.db.get_item("HEAD", True)
        self.item.valueChanged[float].connect(self.setHeading)
        self._heading = self.item.value

        # Heading-invalid annunciation (AC 23.1311-1C sec 8.6.a): a lost/stale
        # heading must be flagged, not scrolled as a frozen tape (loss of
        # direction reduces the pilot's capability; governing "no misleading
        # info" principle).
        self._fail = self.item.fail
        self._old = self.item.old
        self._bad = self.item.bad
        self.item.failChanged[bool].connect(self.setFail)
        self.item.oldChanged[bool].connect(self.setOld)
        self.item.badChanged[bool].connect(self.setBad)

        self.dpp = 10
    def resizeEvent(self, event):
        w = self.width()
        h = self.height()

        compassPen = QPen(QColor(Qt.GlobalColor.white))
        compassPen.setWidth(2)

        headingPen = QPen(QColor(Qt.GlobalColor.red))
        headingPen.setWidth(8)

        f = QFont(self.font_family)
        f.setPixelSize(self.fontsize)

        self.scene = QGraphicsScene(0, 0, 5000, h)
        self.scene.addRect(0, 0, 5000, h,
                           QPen(QColor(Qt.GlobalColor.black)), QBrush(QColor(Qt.GlobalColor.black)))

        self.setScene(self.scene)

        for i in range(-50, 410, 5):
            if i % 10 == 0:
                self.scene.addLine((i * 10) + w / 2, 0, (i * 10) + w / 2, h / 2,
                                   compassPen)
                if i > 360:
                    t = self.scene.addText(str(i - 360))
                    t.setFont(f)
                    self.scene.setFont(f)
                    t.setDefaultTextColor(QColor(Qt.GlobalColor.white))
                    t.setX(((i * 10) + w / 2) - t.boundingRect().width() / 2)
                    t.setY(h - t.boundingRect().height())
                elif i < 1:
                    t = self.scene.addText(str(i + 360))
                    t.setFont(f)
                    self.scene.setFont(f)
                    t.setDefaultTextColor(QColor(Qt.GlobalColor.white))
                    t.setX(((i * 10) + w / 2) - t.boundingRect().width() / 2)
                    t.setY(h - t.boundingRect().height())
                else:
                    if i % 90 == 0:
                        t = self.scene.addText(self.cardinal[int(i / 90)])
                        t.setFont(f)
                        self.scene.setFont(f)
                        t.setDefaultTextColor(QColor(Qt.GlobalColor.cyan))
                        t.setX(((i * 10) + w / 2) - t.boundingRect().width() / 2)
                        t.setY(h - t.boundingRect().height())
                    else:
                        t = self.scene.addText(str(i))
                        t.setFont(f)
                        self.scene.setFont(f)
                        t.setDefaultTextColor(QColor(Qt.GlobalColor.white))
                        t.setX(((i * 10) + w / 2) - t.boundingRect().width() / 2)
                        t.setY(h - t.boundingRect().height())
            else:
                self.scene.addLine((i * 10) + w / 2, 0,
                                   (i * 10) + w / 2, h / 2 - 20,
                                    compassPen)

    def redraw(self):
        self.resetTransform()
        self.centerOn(self._heading * self.dpp + self.width() / 2,
                      self.height() / 2)

    def getHeading(self):
        return self._heading

    def setHeading(self, heading):
        if heading != self._heading:
            self._heading = heading
            self.redraw()

    heading = property(getHeading, setHeading)

    def setFail(self, fail):
        self._fail = fail
        self.viewport().update()

    def setOld(self, old):
        self._old = old
        self.viewport().update()

    def setBad(self, bad):
        self._bad = bad
        self.viewport().update()

    def paintEvent(self, event):
        super(DG_Tape, self).paintEvent(event)
        # Annunciate an invalid heading over the centre read window. fail -> red
        # XXX masking the reading (a frozen tape must not read as valid); old/bad
        # -> grey wash + amber HDG flag (degraded). Same convention as the boxed
        # HeadingDisplay and the other tapes.
        if not (self._fail or self._old or self._bad):
            return
        w = self.width()
        h = self.height()
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._fail:
            color = QColor(Qt.GlobalColor.red)
            text = "XXX"
        else:                                   # old / bad -> degraded
            p.fillRect(self.viewport().rect(), QColor(128, 128, 128, 120))
            color = QColor(255, 150, 0)
            text = "HDG"
        bw = w * 0.34
        bh = h * 0.72
        rect = QRectF(w / 2 - bw / 2, h / 2 - bh / 2, bw, bh)
        if self._fail:
            p.fillRect(rect, QColor(Qt.GlobalColor.black))
        pen = QPen(color)
        pen.setWidth(max(2, qRound(h * 0.03)))
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rect)
        f = QFont(self.font_family)
        f.setBold(True)
        f.setPixelSize(max(10, qRound(h * 0.4)))
        p.setFont(f)
        p.setPen(QPen(color))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def showEvent(self, event):
        self.redraw()

    # We don't want this responding to keystrokes
    def keyPressEvent(self, event):
        pass

    # Don't want it acting with the mouse scroll wheel either
    def wheelEvent(self, event):
        pass

