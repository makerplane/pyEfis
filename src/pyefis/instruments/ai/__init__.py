#  Copyright (c) 2013 Phil Birkelbach; 2018-2019 Garrett Herschleb
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

import math
import time
import logging

import pyavtools.fix as fix
from pyefis import common
from pyefis.instruments.ai.svs import SVSRenderer, make_svs_item
from pyefis.instruments.ai.pose import PoseSource

log = logging.getLogger(__name__)

# TODO:
#   Check TAS quality and revert to turn rate indication
#   Fix quality indications
#   Add quality flags to indicate the actual failures
#   Remove internal assignments of database items.  Should be a normal
#      Qt widget and these things done externally.
#   Add configuration for bank angle tick sizes

class AI(QGraphicsView):
    # Below this groundspeed the flight-path marker has no usable solution:
    # GPS track (the FPM's lateral position) is undefined when stationary and
    # noisy while taxiing, so the marker darts around the screen (issue #70).
    # Hide it until the aircraft is actually moving -- standard HUD/SVS
    # behavior, and correct with real sensors too (not just X-Plane).
    _FPM_MIN_GS_KT = 30.0

    def __init__(self, parent=None, font_percent=None, font_family="DejaVu Sans Condensed", show_fpm=True):
        super(AI, self).__init__(parent)
        self.myparent = parent
        self.font_family = font_family
        self.show_fpm = show_fpm
        # The following information is meant to be configurable from the screen
        # definition file
        self.font_percent = font_percent
        if self.font_percent:
            self.fontSize = qRound(self.width() * self.font_percent)
        else:
            self.fontSize = 30
        # Number of degrees shown from top to bottom. This sets
        # pixelsPerDeg = widget_height / pitchDegreesShown, which is
        # the SAME scale applied to the horizontal axis, so the AI's
        # effective horizontal FOV = widget_width * pitchDegreesShown
        # / widget_height. At the original 60 deg on a 5" 800x480
        # panel the HFOV came out to ~100 deg — about 2x the angular
        # spread of a typical avionics PFD's synthetic-vision view
        # (Garmin GI-275: ~50 deg; G1000 PFD: ~50-60 deg; X-Plane
        # cockpit view: 60-70 deg). Terrain and runways appeared
        # roughly half their natural size as a result.
        #
        # 30 puts HFOV at 50 deg on a 5:3 panel (800x480 -> 50 deg,
        # 1024x600 -> 51.2 deg) — matches the Garmin GI-275 SVS and
        # most G1000-class PFD synthetic-vision views. The pitch
        # ladder spreads out by 60/30 = 2x relative to the original,
        # which gives more screen-space per degree of pitch (more
        # readable, and matches the visible pitch range real PFDs
        # use).
        self.pitchDegreesShown = 30
        # Pitch tick mark configurations
        self.minorDiv = 1   # Degrees between minor divisions
        self.majorDiv = 5  # Degrees between major divisions
        self.numberedDiv = 10 # Degrees between numbered divisions
        # Line widths of the pitch tick marks
        self.minorDivWidth = 10
        self.majorDivWidth = 40
        self.numberedDivWidth = 50
        # When True (default) the tick widths + bank-mark size scale with the
        # font on resize; set False to honour the explicit pixel sizes above
        # (so they can be exposed as independent editor options).
        self.tick_autoscale = True
        self.visiblePitchAngle = 15 # Amount of visible pitch angle marks
        self.pitchOpacity = 0.6
        # Bank angle tick indicators
        self.bankMarkSize = 10
        # Standard rate turn bank angle indicators.
        self.drawBankMarkers = True
        self.bankAngleRadius = None # Radius of the bank angle markings
        self.bankAngleMaximum = 25  # Largest bank angle that will be indicated
        # Envelope-awareness caution thresholds (AC 25-11B App A A.2.5 / A.2.6):
        # amber annunciation past excessive bank / sideslip. Configurable.
        self.excessiveBankDeg = 45
        self.excessiveSlip = 0.25
        self._excessive_bank = False
        self._excessive_slip = False
        # Unusual-attitude recovery chevrons (AC 25-11B App A A.2.2): past
        # these pitch thresholds large chevrons point to the nearest horizon
        # so the pilot recognises + initiates recovery within one second.
        # Asymmetric per common EFIS/Part 25 convention (spec sec 4);
        # configurable.
        self.unusualPitchHighDeg = 30
        self.unusualPitchLowDeg = -20
        self._show_recovery_chevrons = False
        # De-clutter (AC 25-11B p.47, App A): at an unusual attitude remove
        # non-essential overlays (FPM, standard-rate turn diamonds, horizon
        # heading scale), keeping only recovery-critical symbology. Engages on
        # the unusual-pitch condition above or a steep bank past this threshold.
        # (65 deg, past the excessive-bank caution, is the unusual-attitude
        # regime -- not a normal steep turn.) Configurable.
        self.unusualBankDeg = 65
        self._decluttered = False
        # Fixed aircraft reference symbol (the "wings" the horizon moves
        # behind). style: "classic" (split wing bars + center dot),
        # "garmin"/"gi275" (GI-275-style stepped wing bars + center
        # chevron), or "none" (no symbol -- SVS-as-background mode). Set
        # from the screen YAML options (aircraft_symbol, symbol_color);
        # applied by the screenbuilder factory.
        self.aircraft_symbol = "classic"
        self.symbol_color = "yellow"
        # Proportional size multiplier for the reference symbol (1 =
        # standard). Scales each style's own dimensions around the
        # horizon anchor, so wingspan and proportions grow together.
        self.symbol_scale = 1.0
        # Bank-angle cluster placement: the arc centre sits at
        # bank_position percent of widget height measured UP from the
        # bottom (50 = centred, the classic look -- same convention as
        # horizon_position), with radius bank_radius percent of height
        # (33.3 = the classic height/3). The whole cluster -- arc,
        # roll pointer, datum triangle, standard-rate diamonds and
        # slip/skid ball -- moves and scales together. An explicit
        # bankAngleRadius (px) in the YAML still wins over bank_radius.
        # G1000-style declutter (checkbox): stop drawing pitch-ladder
        # rows whose SCREEN position rises above a line just below the
        # bank arc, so ladder dashes/numbers never render through it.
        self.pitch_ladder_avoid_bank = False
        self.bank_position = 50
        self.bank_radius = 100.0 / 3.0   # percent; == the classic height/3
        # Overlay opacities (0 = invisible .. 1 = solid), the same dial
        # pitchOpacity gives the ladder. bankOpacity fades the whole
        # bank-angle cluster (bank scale + roll pointer + standard-rate
        # diamonds + slip/skid ball); horizonOpacity fades the white
        # zero-pitch reference line. With aircraft_symbol "none",
        # pitchOpacity 0, bankOpacity 0, horizonOpacity 0 and show_fpm
        # off, the widget renders the bare SVS environment.
        self.bankOpacity = 1.0
        self.horizonOpacity = 1.0
        # Vertical position of the pitch=0 horizon, as a percent of widget
        # height measured UP from the bottom. 50 = centred (the default; the
        # plain AI never changes this). The SVS widget can raise it (e.g. ~67 =
        # two-thirds up) to expand the ground area; the WHOLE attitude reference
        # -- horizon, pitch ladder, aircraft symbol and SVS terrain -- shifts
        # together so level flight still shows the wings on the horizon.
        self.horizon_position = 50

        # Compass heading scale on the white horizon line (off by default):
        # short vertical ticks every `interval` degrees with an upright numeric
        # label every `label_interval` degrees. Driven by magnetic HEAD, so it
        # scrolls as the aircraft turns and tilts with the horizon.
        self.horizon_heading_marks = False
        self.horizon_heading_interval = 10
        self.horizon_heading_label_interval = 20
        self.horizon_heading_tick_length = 5
        self.horizon_heading_color = "#ffffff"

        # Clean-terrain capture mode (for the configurator's static SVS preview):
        # when True the widget renders ONLY the environment -- SVS terrain + sky
        # / ground -- and suppresses every symbology layer (horizon line, pitch
        # ladder, aircraft symbol, bank scale, slip ball, FPM, heading marks,
        # chevrons). Used by the visual harness (SVS_TERRAIN_ONLY) to grab a
        # symbology-free terrain frame that the configurator twin draws over.
        self.terrain_only = False

        self.setStyleSheet("border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # ------------------------------------------------------------------
        # Frame clock (plan P4). FIX value slots only STORE state; this
        # timer samples the interpolated pose at the display rate and
        # triggers the repaint. Decouples render cadence from gateway
        # burst patterns and bounds the main-thread CPU. Flag changes
        # (old/bad/fail) still repaint immediately — they are alerts.
        # ------------------------------------------------------------------
        self._pose = PoseSource()
        self._frame_dirty = True
        self._frame_last_pose = None
        self._frame_timer = QTimer(self)
        # Coarse timers (the default) have 5% slack on top of the
        # 15.6 ms Windows tick — at 33 ms intervals that reads as
        # ~47 ms frames. Precise typing keeps the cadence honest.
        self._frame_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._frame_timer.timeout.connect(self._frame_tick)
        self.set_frame_rate(30.0)

        # Assume True until told otherwise
        self._AIOld = dict()
        self._AIBad = dict()
        self._AIFail = dict()
        for p in ['PITCH', 'ROLL','ALAT','TAS']:
            self._AIOld[p] = True
            self._AIBad[p] = True
            self._AIFail[p] = True
        pitch = fix.db.get_item("PITCH")
        pitch.valueChanged[float].connect(self.setPitchAngle)
        pitch.oldChanged[bool].connect(self.setAIOldPitch)
        pitch.badChanged[bool].connect(self.setAIBadPitch)
        pitch.failChanged[bool].connect(self.setAIFailPitch)
        self._AIOld['PITCH'] = pitch.old
        self._AIBad['PITCH'] = pitch.bad
        self._AIFail['PITCH'] = pitch.fail
        self._pitchAngle = pitch.value
        roll = fix.db.get_item("ROLL")
        roll.valueChanged[float].connect(self.setRollAngle)
        roll.oldChanged[bool].connect(self.setAIOldRoll)
        roll.badChanged[bool].connect(self.setAIBadRoll)
        roll.failChanged[bool].connect(self.setAIFailRoll)
        self._rollAngle = roll.value
        self._AIOld['ROLL'] = roll.old
        self._AIBad['ROLL'] = roll.bad
        self._AIFail['ROLL'] = roll.fail
        alat = fix.db.get_item("ALAT")
        alat.valueChanged[float].connect(self.setLateralAcceleration)
        alat.oldChanged[bool].connect(self.setAIOldLAcc)
        alat.badChanged[bool].connect(self.setAIBadLAcc)
        alat.failChanged[bool].connect(self.setAIFailLAcc)
        self._AIOld['ALAT'] = alat.old
        self._AIBad['ALAT'] = alat.bad
        self._AIFail['ALAT'] = alat.fail
        self._latAccel = alat.value
        tas = fix.db.get_item("TAS")
        tas.valueChanged[float].connect(self.setTrueAirspeed)
        tas.oldChanged[bool].connect(self.setAIOldTAS)
        tas.badChanged[bool].connect(self.setAIBadTAS)
        tas.failChanged[bool].connect(self.setAIFailTAS)
        self._AIOld['TAS'] = tas.old
        self._AIBad['TAS'] = tas.bad
        self._AIFail['TAS'] = tas.fail

        self._tas = tas.value

        # Flight Path Marker (GPS method): VS, GS, TRACK, HEAD.
        # Keys default to fail=True so that if any are missing from the FIX
        # database (e.g. gateway doesn't publish TRACK), _drawFPM stays
        # silently disabled rather than crashing.
        # VPATH (vertical flight path angle, deg) is preferred when the
        # data source can produce it directly (X-Plane publishes it via
        # idx 18 slot 3 as the same value its own FPM symbol uses).
        # When VPATH isn't published we fall back to atan2(VS, GS),
        # which is correct in steady state but lags VPATH during
        # transient descents — the FIX key still wires up cleanly via
        # the missing-key guard below.
        self._fpm_fail = {k: True for k in ('VS', 'GS', 'TRACK', 'HEAD', 'VPATH')}
        self._fpm_bad  = {k: False for k in ('VS', 'GS', 'TRACK', 'HEAD', 'VPATH')}
        self._fpm_vs    = 0.0
        self._fpm_gs    = 0.0
        self._fpm_track = 0.0
        self._fpm_head  = 0.0
        self._fpm_vpath = 0.0
        for key in ('VS', 'GS', 'TRACK', 'HEAD', 'VPATH'):
            try:
                _item = fix.db.get_item(key)
            except KeyError:
                log.warning(
                    f"AI: FIX key '{key}' not defined — Flight Path Marker disabled")
                continue
            _item.valueChanged[float].connect(lambda v, k=key: self._fpmValueChanged(k, v))
            _item.failChanged[bool].connect(lambda f, k=key: self._fpmFailChanged(k, f))
            _item.badChanged[bool].connect(lambda b, k=key: self._fpmBadChanged(k, b))
            self._fpm_fail[key] = _item.fail
            self._fpm_bad[key]  = _item.bad
            setattr(self, f'_fpm_{key.lower()}', _item.value)
            self._pose.set_fail(key, _item.fail)

        # Seed the pose source from the initial FIX values — the
        # valueChanged signals for anything set before this widget
        # was constructed have already fired and will not repeat
        # until the value changes again.
        self._pose.set_dynamics(gs_kt=self._fpm_gs,
                                track_deg=self._fpm_track,
                                vs_fpm=self._fpm_vs)

        # SVS position inputs: LAT, LONG, ALT (disabled by default; renderer
        # set via set_svs_config). Missing keys leave the SVS position at 0
        # and the renderer's ready gate will skip drawing if no tiles match.
        self._svs_lat  = 0.0
        self._svs_lon  = 0.0
        self._svs_alt  = 0.0
        self.svs: SVSRenderer | None = None
        for key, attr in (("LAT", "_svs_lat"), ("LONG", "_svs_lon"), ("ALT", "_svs_alt")):
            try:
                _item = fix.db.get_item(key)
            except KeyError:
                log.warning(
                    f"AI: FIX key '{key}' not defined — SVS will use 0.0 for {attr}")
                continue
            _item.valueChanged[float].connect(
                lambda v, k=key: self._positionValueChanged(k, v))
            setattr(self, attr, _item.value)
        if self._svs_lat or self._svs_lon:
            self._pose.set_position(self._svs_lat, self._svs_lon)
        if self._svs_alt:
            self._pose.set_altitude(self._svs_alt)

        # Magnetic variation. SVS does its geographic projection in
        # true-north coordinates, so it needs TRUE heading. HEAD is by
        # convention magnetic (so the HSI rose reads naturally). The
        # AI widget converts HEAD to TRUE at SVS call time as
        # ``HEAD - MAGVAR``. Positive MAGVAR = west variation (FAA
        # "West is best": MAG = TRUE + W_VAR). When MAGVAR isn't
        # published the correction is zero and the SVS sits with a
        # constant rotational offset equal to local variation — small
        # error in low-variation regions, larger near the magnetic
        # poles.
        self._magvar = 0.0
        try:
            _item = fix.db.get_item("MAGVAR")
            _item.valueChanged[float].connect(
                lambda v: (setattr(self, "_magvar", v),
                           setattr(self, "_frame_dirty", True)))
            self._magvar = _item.value
        except KeyError:
            log.warning(
                "AI: FIX key 'MAGVAR' not defined — SVS heading "
                "will be treated as true heading (no mag-var correction)")

        # We store all the pitch tick marks and text in a list so that
        # we can adjust the opacity of the items.
        self.pitchItems = []

    def _draw_aircraft_symbol(self, p, w, h):
        """Draw the fixed aircraft reference symbol into the static
        overlay. Style + colour come from self.aircraft_symbol /
        self.symbol_color (screen YAML options)."""
        style = str(getattr(self, "aircraft_symbol", "classic")).lower()
        if style in ("none", "off", "hidden"):
            return   # SVS-as-background mode: no fixed reference symbol
        # The symbol rides the horizon, so it shifts up with horizon_position
        # (0 offset by default = centred).
        cx, cy = w / 2.0, h / 2.0 - self._horizon_offset_px()
        # symbol_scale multiplies every style's own dimensions around the
        # horizon anchor -- wingspan and proportions grow together.
        ss = max(0.3, min(3.0, float(getattr(self, "symbol_scale", 1.0))))
        col = QColor(self.symbol_color)
        if not col.isValid():
            col = QColor(Qt.GlobalColor.yellow)
        p.setPen(QPen(QColor(Qt.GlobalColor.black), 1))
        p.setBrush(QBrush(col))
        if style in ("garmin", "delta"):
            # Garmin G3X-style "bat wing": two slender ANHEDRAL triangles
            # sweeping down-outboard from a notched apex on the horizon
            # line. Each wing is split lengthwise into a lit upper face
            # (the symbol colour) and a shaded darker lower face -- the
            # bevelled 3D look of the real display -- with a matching
            # two-tone horizon-reference barb (rounded pill) riding the
            # horizon out toward each edge.
            span = w * 0.15 * ss        # wing length, apex -> outer edge
            drop = span * 0.30          # anhedral: outer edge below the apex
            thick = max(6.0, span * 0.16)  # outer-edge thickness (vertical)
            ext = span * 0.12           # base slant: bottom corner runs this
                                        # much further outboard than the top
            gap = max(3.0, w * 0.012 * ss)  # half-notch between the apexes
            dark = QColor(col).darker(165)
            for s in (-1, 1):
                xi = cx + s * gap                 # SHARP apex, on the horizon
                xo = cx + s * (gap + span)        # outer edge, top corner x
                xt = xo + s * ext                 # outer edge, bottom-tip x
                # slanted outer base: top corner -> lower, further-out tip,
                # so the wing end droops down-and-out like the G3X
                mx = (xo + xt) / 2.0              # tone split midpoint
                my = cy + drop + thick * 0.5
                p.setBrush(QBrush(col))           # lit upper face
                p.drawPolygon(QPolygonF([
                    QPointF(xi, cy),
                    QPointF(xo, cy + drop),
                    QPointF(mx, my)]))
                p.setBrush(QBrush(dark))          # shaded lower face
                p.drawPolygon(QPolygonF([
                    QPointF(xi, cy),
                    QPointF(mx, my),
                    QPointF(xt, cy + drop + thick)]))
            # Horizon reference barbs: two-tone pills centred ON the
            # horizon line, out near the roll-scale edges.
            bl = w * 0.062 * ss         # barb length
            bx = w * 0.35 * ss          # barb centre offset from centre
            bh = max(6.0, h * 0.024 * ss)   # barb thickness (total)
            for s in (-1, 1):
                x0 = cx + s * bx - bl / 2.0
                p.setBrush(QBrush(col))           # full pill, lit tone
                p.drawRoundedRect(QRectF(x0, cy - bh / 2.0, bl, bh),
                                  bh / 2.0, bh / 2.0)
                p.setBrush(QBrush(dark))          # lower half, shaded
                p.drawRoundedRect(QRectF(x0, cy, bl, bh / 2.0),
                                  bh / 4.0, bh / 4.0)
        elif style in ("g1000", "g3x"):
            # G1000/G3X style: two FLAT split wing bars with a small upward
            # triangle standing in the centre gap between them (distinct from the
            # garmin delta, whose wings taper off the delta base).
            bt = max(2.5, h * 0.017 * ss)   # wing bar half-thickness
            gap = w * 0.05 * ss         # half-gap from centre to the inboard bar
            wing = w * 0.15 * ss        # wing-bar length
            trih = max(6.0, h * 0.052 * ss)  # centre triangle height
            triw = gap * 0.72           # centre triangle half-base (fits the gap)
            p.drawRect(QRectF(cx - gap - wing, cy - bt, wing, 2 * bt))  # left bar
            p.drawRect(QRectF(cx + gap, cy - bt, wing, 2 * bt))         # right bar
            p.drawPolygon(QPolygonF([                 # centre up-triangle
                QPointF(cx, cy - trih),
                QPointF(cx + triw, cy),
                QPointF(cx - triw, cy)]))
        elif style in ("gi275", "gi-275", "boresight", "ring"):
            # Boresight style: two flat wing bars flanking an OPEN ring (the
            # aircraft "boresight"/waterline circle) at the centre.
            bt = max(2.5, h * 0.015 * ss)   # wing bar half-thickness
            gap = w * 0.055 * ss        # half-gap from centre to the inboard bar
            wing = w * 0.15 * ss        # wing-bar length
            rr = max(4.0, h * 0.030 * ss)   # boresight ring radius
            p.drawRect(QRectF(cx - gap - wing, cy - bt, wing, 2 * bt))  # left bar
            p.drawRect(QRectF(cx + gap, cy - bt, wing, 2 * bt))         # right bar
            ring = QPen(col)                       # open yellow ring (no fill)
            ring.setWidth(max(2, qRound(h * 0.012)))
            p.setPen(ring)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), rr, rr)
        elif style in ("brackets", "grt", "l", "l-bracket", "l_bracket"):
            # GRT-style L-brackets: a wing bar each side with an inboard
            # down-tick (forming an "L"), flanking a small centre dot.
            bt = max(3.0, h * 0.012 * ss)   # bar thickness
            inner = w * 0.07 * ss        # half-gap from centre to the inboard tip
            wing = w * 0.14 * ss         # wing-bar length
            tick = bt * 2.6              # inboard down-tick length
            p.drawRect(QRectF(cx - inner - wing, cy - bt / 2, wing, bt))  # left bar
            p.drawRect(QRectF(cx - inner - bt, cy - bt / 2, bt, tick))    # left tick
            p.drawRect(QRectF(cx + inner, cy - bt / 2, wing, bt))         # right bar
            p.drawRect(QRectF(cx + inner, cy - bt / 2, bt, tick))         # right tick
            p.drawEllipse(QPointF(cx, cy), bt * 0.7, bt * 0.7)            # centre dot
        else:
            # Classic: split wing bars + centre dot. Rewritten
            # centre-relative so the scale grows the bars around the
            # anchor: at ss=1 the inboard edge sits at w/12 from centre
            # and the bar is w/6 long -- exactly the historical
            # [w/4, w/4 + w/6] placement.
            inner = (w / 12.0) * ss
            wing = (w / 6.0) * ss
            bh2 = 3.0 * ss               # bar half-height
            p.drawRect(QRectF(cx - inner - wing, cy - bh2, wing, 2 * bh2))
            p.drawRect(QRectF(cx + inner, cy - bh2, wing, 2 * bh2))
            p.drawEllipse(QRectF(cx - 3 * ss, cy - 3 * ss, 9 * ss, 9 * ss))

    def resizeEvent(self, event):
        self.pitchItems = []
        # Detach the SVS item from the outgoing scene BEFORE we replace
        # it. QGraphicsScene deletes its items on destruction; if the
        # item rides the old scene down, the Python wrapper is left
        # pointing at a deleted C++ object and the next attach crashes.
        # Seen on eglfs (Pi), where fullscreen startup produces extra
        # resize events with the old scene destroyed in between.
        _svs_item = getattr(self, "_svs_item", None)
        if _svs_item is not None:
            try:
                _old_scene = _svs_item.scene()
                if _old_scene is not None:
                    _old_scene.removeItem(_svs_item)
            except RuntimeError:
                # C++ side already deleted — drop the dead wrapper;
                # _attach_svs_item_if_ready rebuilds it from self.svs.
                self._svs_item = None
        if self.font_percent:
            self.fontSize = qRound(self.width() * self.font_percent)
            if self.tick_autoscale:
                self.minorDivWidth = qRound(self.fontSize * 0.3)
                self.majorDivWidth = self.minorDivWidth * 4
                self.numberedDivWidth = self.minorDivWidth * 5
                self.bankMarkSize = qRound(self.fontSize * 0.3 )
        #Setup the scene that we use for the background of the AI
        sceneHeight = self.height() * 4.5
        sceneWidth = math.sqrt(self.width() * self.width() +
                               self.height() * self.height())
        self.pixelsPerDeg = self.height() / self.pitchDegreesShown
        self.scene = QGraphicsScene(0, 0, sceneWidth, sceneHeight)
        # Setup default values. bank_radius (percent of height, default
        # 33.3 = the classic height/3) sizes the bank arc; an explicit
        # bankAngleRadius px from the YAML still wins.
        if self.bankAngleRadius is None:
            self.bankAngleRadius = self.height() * max(
                5.0, min(80.0,
                         float(getattr(self, "bank_radius", 33.3)))) / 100.0
        # Get a failure scene ready in case it's needed
        self.fail_scene = QGraphicsScene(0, 0, sceneWidth, sceneHeight)
        self.fail_scene.addRect(0,0, sceneWidth, sceneHeight, QPen(QColor(Qt.GlobalColor.white)), QBrush(QColor(50,50,50)))
        font = QFont(self.font_family, 80, QFont.Weight.Bold)
        t = self.fail_scene.addSimpleText("XXX", font)
        t.setPen (QPen(QColor(Qt.GlobalColor.red)))
        t.setBrush (QBrush(QColor(Qt.GlobalColor.red)))
        r = t.boundingRect()
        t.setPos ((sceneWidth-r.width())/2, (sceneHeight-r.height())/2)

        #Draw the Blue and Brown rectangles
        gradientBlue = QLinearGradient(0, 0, 0, sceneHeight / 2)
        gradientBlue.setColorAt(0.7, QColor(0, 51, 102))
        gradientBlue.setColorAt(1.0, QColor(51, 153, 255))
        gradientBlue.setSpread(QGradient.Spread.PadSpread)
        self.blue_pen = QPen(QColor(Qt.GlobalColor.blue))
        self.gblue_brush = QBrush(gradientBlue)
        gradientLGray = QLinearGradient(0, 0, 0, sceneHeight / 2)
        gradientLGray.setColorAt(0.7, QColor(100, 100, 100))
        gradientLGray.setColorAt(1.0, QColor(153, 153, 153))
        gradientLGray.setSpread(QGradient.Spread.PadSpread)
        self.gray_sky = QBrush(gradientLGray)
        if self.getAIOld() or self.getAIBad():
            brush = self.gray_sky
        else:
            brush = self.gblue_brush
        self.sky_rect = self.scene.addRect(0, 0, sceneWidth, sceneHeight / 2, self.blue_pen, brush)
        self.setScene(self.scene)
        gradientBrown = QLinearGradient(0, sceneHeight / 2, 0, sceneHeight)
        gradientBrown.setColorAt(0.0, QColor(105, 46, 1))
        gradientBrown.setColorAt(0.3, QColor(244, 164, 96))
        gradientBrown.setSpread(QGradient.Spread.PadSpread)
        self.brown_pen = QPen(QColor(160, 82, 45))  # Brown Color
        self.gbrown_brush = QBrush(gradientBrown)
        gradientDGray = QLinearGradient(0, sceneHeight / 2, 0, sceneHeight)
        gradientDGray.setColorAt(0.0, QColor(20, 20, 20))
        gradientDGray.setColorAt(0.2, QColor(75, 75, 75))
        gradientDGray.setSpread(QGradient.Spread.PadSpread)
        self.gray_land = QBrush(gradientDGray)
        if self.getAIOld() or self.getAIBad():
            brush = self.gray_land
        else:
            brush = self.gbrown_brush
        self.land_rect = self.scene.addRect(0, sceneHeight / 2 + 1, sceneWidth, sceneHeight,
                           self.brown_pen, brush)

        self.setScene(self.scene)

        #Draw the main horizontal line
        pen = QPen(QColor(Qt.GlobalColor.white))
        pen.setWidth(qRound(self.fontSize * 0.05))
        # z=1 (with the pitch ladder) so the zero-pitch reference line
        # stays visible OVER the SVS terrain (z=0.5) — otherwise
        # mountains rising above the horizon hide it, removing the
        # attitude reference exactly when terrain fills the view.
        self._horizon_line = self.scene.addLine(
            0, sceneHeight / 2, sceneWidth, sceneHeight / 2, pen)
        self._horizon_line.setZValue(1)
        # horizonOpacity (0..1): fade/hide the zero-pitch reference line
        # (SVS-as-background mode). Applied here because the scene is
        # rebuilt on every resize.
        self._horizon_line.setOpacity(
            max(0.0, min(1.0, float(getattr(self, "horizonOpacity", 1.0)))))
        # draw the degree hash marks
        pen.setColor(Qt.GlobalColor.white)
        w = self.scene.width()
        h = self.scene.height()
        f = QFont(self.font_family)
        f.setPixelSize(self.fontSize)

        # Draw the tick mark lines on the scene
        for i in range(-90, 91):
            if i == 0:  # Don't draw a line at zero
                pass
            elif i % self.numberedDiv == 0:
                left = w / 2 - self.numberedDivWidth / 2
                right = w / 2 + self.numberedDivWidth / 2
                y = h / 2 - self.pixelsPerDeg * i

                l = self.scene.addLine(left, y, right, y, pen)
                l.setZValue(1)
                self.pitchItems.append((i, l))
                t = self.scene.addText(str(i))
                t.setFont(f)
                self.scene.setFont(f)
                t.setDefaultTextColor(Qt.GlobalColor.white)
                t.setX(right + 5)
                t.setY(y - t.boundingRect().height() / 2)
                t.setZValue(1)
                self.pitchItems.append((i, t))

                t = self.scene.addText(str(i))
                t.setFont(f)
                self.scene.setFont(f)
                t.setDefaultTextColor(Qt.GlobalColor.white)
                t.setX(left - (t.boundingRect().width() + 5))
                t.setY(y - t.boundingRect().height() / 2)
                t.setZValue(1)
                self.pitchItems.append((i, t))

            elif i % self.majorDiv == 0:
                left = w / 2 - self.majorDivWidth / 2
                right = w / 2 + self.majorDivWidth / 2
                y = h / 2 - self.pixelsPerDeg * i
                l = self.scene.addLine(left, y, right, y, pen)
                l.setZValue(1)
                self.pitchItems.append((i, l))

            elif i % self.minorDiv == 0:
                left = w / 2 - self.minorDivWidth / 2
                right = w / 2 + self.minorDivWidth / 2
                y = h / 2 - self.pixelsPerDeg * i
                l = self.scene.addLine(left, y, right, y, pen)
                l.setZValue(1)
                self.pitchItems.append((i, l))
        self.setPitchItems()

        # Draws the static overlay stuff to a pixmap
        self.map = QPixmap(self.width(), self.height())
        self.map.fill(Qt.GlobalColor.transparent)
        p = QPainter(self.map)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # change width and height to the view instead of the scene
        w = self.width()
        h = self.height()
        r = self.bankAngleRadius
        self._draw_aircraft_symbol(p, w, h)

        # Fixed bank-datum pointer at the top of the bank arc: part of the
        # bank-angle display, so it follows bankOpacity like the rotating
        # scale in paintEvent.
        _bank_op = max(0.0, min(1.0,
                                float(getattr(self, "bankOpacity", 1.0))))
        if _bank_op > 0.0:
            p.setOpacity(_bank_op)
            m = self.bankMarkSize
            p.setBrush(QColor(Qt.GlobalColor.white))
            p.translate(w / 2, self._bank_anchor_y(h) - r)
            triangle = QPolygonF([QPointF(m,  m*2),
                                 QPointF(-m, m*2),
                                 QPointF(0,  m/2)])
            p.drawPolygon(triangle)
            p.setOpacity(1.0)

        self.overlay = self.map.toImage()

        # resizeEvent builds a new self.scene; re-attach the SVS item so it
        # tracks the current scene rather than being orphaned on the old one.
        self._attach_svs_item_if_ready()

        self.redraw()

    def set_svs_config(self, config: dict):
        """Initialise the SVS renderer from a config dict (called by screenbuilder).

        SVS is added to the QGraphicsScene as a low-Z item so the pitch
        ladder and other scene items render on top of the terrain. Override
        the default with ``z_value`` in the SVS config block.

        The scene itself is built in ``resizeEvent``, so if this method runs
        before the first resize we defer the attachment — ``resizeEvent``
        re-runs ``_attach_svs_item_if_ready`` after rebuilding the scene.
        """
        # If we already had an SVS item, detach it from whatever scene held it
        # so we can swap in a fresh renderer cleanly.
        if getattr(self, "_svs_item", None) is not None:
            old_scene = self._svs_item.scene()
            if old_scene is not None:
                old_scene.removeItem(self._svs_item)
            self._svs_item = None

        self.svs = SVSRenderer(config)
        # Canonical renderer handle. The screenbuilder assigns YAML `options`
        # as raw attributes, so `self.svs` is frequently overwritten with the
        # `svs:` config DICT after this runs (see the note in paintEvent). Keep
        # a reference under a name that is NOT a YAML option key so code that
        # needs the live renderer (e.g. _svs_drawing) can always find it.
        self._svs_renderer = self.svs
        # Z-order layers inside the AI scene:
        #   z =  1.0  — pitch ladder lines, numerals  (setZValue(1) in resizeEvent)
        #   z =  0.5  — SVS terrain (this item, default)
        #   z =  0.0  — sky_rect, land_rect (the static artificial horizon)
        # So SVS covers the static blue/brown background but stays behind the
        # pitch ladder. Configurable via the `z_value` SVS config key.
        z = float(config.get("z_value", 0.5))
        # GL viewport (P5): the SVS renders directly into the view's
        # backing GL surface between begin/endNativePainting — no
        # offscreen FBO, no glReadPixels. The QPainter scene items
        # (pitch ladder, symbology) render through Qt's GL paint
        # engine on the same surface. FullViewportUpdate is required
        # for GL viewports (partial updates are not supported).
        from PyQt6.QtOpenGLWidgets import QOpenGLWidget
        if not isinstance(self.viewport(), QOpenGLWidget):
            glw = QOpenGLWidget()
            # MSAA (P7): antialiases the whole AI — terrain silhouettes
            # and QPainter symbology alike. The driver grants the
            # closest supported sample count (0 if unsupported), so
            # this degrades silently.
            # Default 2x: at panel sizes the visual difference from 4x is
            # marginal, but terrain fill cost roughly halves — measured
            # decisive for holding 30 Hz at metro worst-case poses.
            samples = int(config.get("msaa_samples", 2))
            if samples > 1:
                fmt = QSurfaceFormat()
                fmt.setSamples(samples)
                glw.setFormat(fmt)
            self.setViewport(glw)
            self.setViewportUpdateMode(
                QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        # Display frame rate (P4): the AI frame clock's tick rate.
        self.set_frame_rate(config.get("frame_rate", 30.0))
        self._svs_z = z
        self._svs_item = make_svs_item(self.svs, self)
        self._svs_item.setZValue(z)
        self._attach_svs_item_if_ready()

    def _attach_svs_item_if_ready(self):
        """Idempotently add the SVS scene item to the current scene.
        ``resizeEvent`` rebuilds ``self.scene`` on every resize, so the item
        has to be re-attached each time the scene changes. If the item's
        C++ object was deleted with a destroyed scene, rebuild the thin
        wrapper around the surviving SVSRenderer."""
        if getattr(self, "svs", None) is None:
            return
        # self.scene is the inherited QGraphicsView.scene method until
        # resizeEvent assigns the instance attribute — guard against that.
        scene = self.__dict__.get("scene")
        if scene is None:
            return
        item = getattr(self, "_svs_item", None)
        if item is not None:
            try:
                if item.scene() is scene:
                    return
                scene.addItem(item)
                return
            except RuntimeError:
                pass  # wrapper points at a deleted C++ object — rebuild
        self._svs_item = make_svs_item(self.svs, self)
        self._svs_item.setZValue(getattr(self, "_svs_z", 0.5))
        scene.addItem(self._svs_item)

    def _fpmValueChanged(self, key, value):
        setattr(self, f'_fpm_{key.lower()}', value)
        # Feed the dead-reckoning inputs; the frame clock repaints.
        if key == "GS":
            self._pose.set_dynamics(gs_kt=value)
        elif key == "TRACK":
            self._pose.set_dynamics(track_deg=value)
        elif key == "VS":
            self._pose.set_dynamics(vs_fpm=value)
        self._frame_dirty = True

    def _fpmFailChanged(self, key, fail):
        self._fpm_fail[key] = fail
        self._pose.set_fail(key, fail)
        if self.isVisible():
            self.update()

    def _fpmBadChanged(self, key, bad):
        self._fpm_bad[key] = bad
        if self.isVisible():
            self.update()

    def update(self):  # noqa: A003 — deliberate QWidget.update override
        """Route repaint requests to the viewport widget. With the P5
        QOpenGLWidget viewport, update() on the view widget itself
        does not invalidate the GL surface — only the initial expose
        would ever paint. viewport().update() is correct for both GL
        and raster viewports."""
        self.viewport().update()

    def _positionValueChanged(self, key, value):
        """GPS/baro position inputs: store raw and timestamp into the
        pose source. The frame clock samples the interpolated pose."""
        if key == "LAT":
            self._svs_lat = value
            self._pose.set_position(value, self._svs_lon)
        elif key == "LONG":
            self._svs_lon = value
            self._pose.set_position(self._svs_lat, value)
        elif key == "ALT":
            self._svs_alt = value
            self._pose.set_altitude(value)
        self._frame_dirty = True

    def set_frame_rate(self, fps):
        """(Re)start the display frame clock at *fps* (clamped 5-60)."""
        fps = max(5.0, min(60.0, float(fps)))
        self._frame_rate = fps
        self._frame_timer.start(int(round(1000.0 / fps)))

    def _frame_tick(self):
        """Display-rate tick: sample the interpolated pose, apply it,
        and repaint — but only when something actually changed, so a
        parked aircraft costs near-zero CPU."""
        if not self.isVisible() or self.__dict__.get("scene") is None:
            return
        sampled = self._pose.sample()
        if sampled is not None:
            lat, lon, alt = sampled
            self._svs_lat = lat
            self._svs_lon = lon
            if alt is not None:
                self._svs_alt = alt
        pose_key = (round(self._svs_lat, 8), round(self._svs_lon, 8),
                    round(self._svs_alt, 2), self._pitchAngle,
                    self._rollAngle, self._fpm_head, self._latAccel,
                    self._tas)
        if not self._frame_dirty and pose_key == self._frame_last_pose:
            return
        self._frame_last_pose = pose_key
        self._frame_dirty = False
        self._update_land_brush()
        self.redraw()
        self.update()

    def _live_svs(self):
        """The live ``SVSRenderer``, resolved clobber-safe — or None.

        Prefers ``_svs_renderer`` (stashed by set_svs_config under a non-YAML
        name), falls back to ``self.svs`` for the base-AI case, and never
        returns the YAML config DICT the screenbuilder commonly overwrites
        ``self.svs`` with. Every consumer that needs the renderer's live
        state (``enabled`` / ``gl_failed`` / ``drew_terrain``) must go through
        here, or it silently reads a dict and sees every flag as False."""
        s = getattr(self, "_svs_renderer", None)
        if s is None or isinstance(s, dict):
            s = getattr(self, "svs", None)   # base-AI case: self.svs is the renderer
        if s is None or isinstance(s, dict):
            return None
        return s

    def _svs_drawing(self):
        """True when the SVS is genuinely painting terrain — enabled, ready,
        not GL-failed, and it actually drew terrain on the last frame. Used to
        decide whether the artificial brown ground can be replaced by sky."""
        s = self._live_svs()
        if s is None:
            return False
        return (getattr(s, "enabled", False)
                and getattr(s, "ready", False)
                and not getattr(s, "gl_failed", False)
                and getattr(s, "drew_terrain", False))

    def _update_land_brush(self):
        """Set the below-horizon (land) fill. Degraded data stays grey; when
        the SVS is actively drawing terrain we paint the land area SKY so the
        synthetic terrain (and the haze that melts it into the sky) is all you
        see below the horizon — no brown sliver between terrain and horizon.
        Otherwise the normal brown attitude ground is the fail-safe. Only
        re-applies on change, so it never thrashes the scene per frame."""
        if not hasattr(self, "land_rect"):
            return
        if self.getAIOld() or self.getAIBad():
            want = self.gray_land
        elif self._svs_drawing():
            want = self.gblue_brush          # sky — SVS terrain is the ground
        else:
            want = self.gbrown_brush         # fail-safe brown attitude ground
        if want is not getattr(self, "_land_brush_cur", None):
            self.land_rect.setBrush(want)
            self._land_brush_cur = want

    def _fpm_solution_valid(self):
        """Whether the flight-path marker has a usable solution to draw.

        Needs the GPS inputs present (VPATH is optional -- real GPS sources
        won't publish it, so it must not gate the FPM) AND a groundspeed above
        ``_FPM_MIN_GS_KT``. Below that the track is undefined/noisy and the
        marker would dart around the screen (issue #70); the user's report was
        rapid horizontal movement while stationary at idle."""
        required = ('VS', 'GS', 'TRACK', 'HEAD')
        if any(self._fpm_fail[k] for k in required):
            return False
        if self._fpm_gs < self._FPM_MIN_GS_KT:
            return False
        return True

    def _drawFPM(self, p, w, h):
        """Draw GPS flight path marker if a valid solution exists and show_fpm
        is set."""
        if not self.show_fpm or not self._fpm_solution_valid():
            return
        required = ('VS', 'GS', 'TRACK', 'HEAD')
        fpm_bad = any(self._fpm_bad[k] for k in required)

        # Vertical flight path angle. Prefer the authoritative VPATH
        # FIX key when the source publishes it (X-Plane idx 18 slot 3
        # is the same value X-Plane's own primary-flight-display FPM
        # uses). Fall back to atan2(VS, GS), which is correct in
        # steady state but lags VPATH on transient descents.
        if not self._fpm_fail['VPATH']:
            fpa_deg = self._fpm_vpath
        else:
            gs_fpm = self._fpm_gs * 101.269  # knots → ft/min
            if gs_fpm > 10.0:
                fpa_deg = math.degrees(math.atan2(self._fpm_vs, gs_fpm))
            else:
                fpa_deg = 0.0
        # Drift angle: crab relative to heading, normalised ±180°.
        # TRACK (idx 18 slot 2 = hpath) is the TRUE ground track;
        # HEAD is magnetic. Subtract MAGVAR from HEAD so both legs of
        # the subtraction are in the true-north frame — otherwise the
        # FPM sits one local-mag-var off its real screen position
        # (same bug class as the pre-MAGVAR SVS projection).
        head_true = self._fpm_head - getattr(self, "_magvar", 0.0)
        drift_deg = ((self._fpm_track - head_true) + 180.0) % 360.0 - 180.0

        ppd = getattr(self, 'pixelsPerDeg', self.height() / self.pitchDegreesShown)
        sym_r = self.bankMarkSize * 0.65
        x_roll = drift_deg * ppd
        # The flight path is measured from the HORIZON, not the boresight. The
        # aircraft symbol sits `pitch` above the horizon, so the FPM belongs
        # (pitch - fpa) below the symbol -- i.e. fpa above the horizon. In
        # nose-high level flight (high AoA, fpa ~ 0) that drops the marker from
        # the boresight onto the horizon line, where it belongs.
        y_roll = (self._pitchAngle - fpa_deg) * ppd

        # Clamp to widget interior (in rolled frame, conservative)
        max_x = w / 2.0 - sym_r * 3.0
        max_y = h / 2.0 - sym_r * 3.0
        x_roll = max(-max_x, min(max_x, x_roll))
        y_roll = max(-max_y, min(max_y, y_roll))

        fpm_color = QColor(0, 200, 0) if not fpm_bad else QColor(255, 165, 0)
        pen = QPen(fpm_color)
        pen.setWidth(max(1, qRound(self.fontSize * 0.05)))

        p.save()
        p.resetTransform()
        # Raise the FPM base with the rest of the attitude reference so it
        # tracks the (possibly raised) horizon; 0 offset by default = centred.
        p.translate(w / 2.0, h / 2.0 - self._horizon_offset_px())
        p.rotate(self._rollAngle * -1.0)   # align with pitch ladder
        p.translate(x_roll, y_roll)         # move to flight-path position
        p.rotate(self._rollAngle)           # symbol stays upright in display space
        p.setPen(pen)
        p.setBrush(Qt.GlobalColor.transparent)
        p.drawEllipse(QPointF(0.0, 0.0), sym_r, sym_r)
        p.drawLine(QPointF(-sym_r * 2.4, 0.0), QPointF(-sym_r * 1.1, 0.0))
        p.drawLine(QPointF( sym_r * 1.1, 0.0), QPointF( sym_r * 2.4, 0.0))
        p.drawLine(QPointF(0.0, -sym_r * 1.1), QPointF(0.0, -sym_r * 2.0))
        p.restore()

    def _draw_recovery_chevrons(self, p, w, h):
        """AC 25-11B App A A.2.2: at an unusual pitch attitude, large chevrons
        point to the nearest horizon so the pilot can recognise the attitude and
        initiate recovery within one second. Drawn in the rolled attitude frame
        (like the pitch ladder / FPM) so they track the horizon at any bank; the
        stack marches toward the horizon and the apexes point at it -- down when
        nose-high (the horizon has fallen below the symbol), up when nose-low."""
        nose_high = self._pitchAngle > self.unusualPitchHighDeg
        d = 1.0 if nose_high else -1.0     # +y is down: +1 points/leads to ground
        half = w * 0.16                    # chevron half-width (shoulder to centre)
        depth = h * 0.09                   # how far the apex leads the shoulders
        step = h * 0.15                    # vertical spacing of the stack
        y0 = d * h * 0.13                  # first chevron, offset toward the horizon

        pen = QPen(QColor(255, 176, 0))    # amber -- caution, not a failure
        pen.setWidth(max(3, qRound(self.fontSize * 0.14)))
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        p.save()
        p.resetTransform()
        p.translate(w / 2.0, h / 2.0 - self._horizon_offset_px())
        p.rotate(self._rollAngle * -1.0)   # align with the pitch ladder
        p.setPen(pen)
        p.setBrush(Qt.GlobalColor.transparent)
        for i in range(3):
            yc = y0 + d * i * step
            p.drawPolyline(QPolygonF([
                QPointF(-half, yc),
                QPointF(0.0, yc + d * depth),
                QPointF(half, yc),
            ]))
        p.restore()

    # the pitchItems list contains a tuple that represents all of the tick marks
    # and text of the Pitch graducations.  The first item of the tuple is the angle
    # and the second is the item reference.  We use this to make the tick marks
    # disappear when they are a certain distance from the current pitch angle
    def setPitchItems(self):
        # Optional G1000-style declutter: the ladder may climb INTO the
        # arch of the bank arc (useful space), but stops just below the
        # slip/skid ball -- rows whose screen position rises above the
        # ball's bottom edge are hidden. The ball rides at
        # anchor - r + 3*markSize with radius 0.8*markSize (paintEvent),
        # so the cutoff is that bottom edge plus a half-mark of air.
        # Row-granular, evaluated in SCREEN space so it tracks roll,
        # pitch, horizon_position and the bank placement knobs.
        cut = None
        if getattr(self, "pitch_ladder_avoid_bank", False):
            h = self.height()
            r = self.bankAngleRadius if self.bankAngleRadius else h / 3
            m = self.bankMarkSize
            cut = self._bank_anchor_y(h) - r + m * 4.3
        for each in self.pitchItems:
            if abs(each[0] - self._pitchAngle) < self.visiblePitchAngle:
                if cut is not None:
                    pt = self.mapFromScene(
                        each[1].sceneBoundingRect().center())
                    if pt.y() < cut:
                        each[1].setOpacity(0)
                        continue
                each[1].setOpacity(self.pitchOpacity)
            else:
                each[1].setOpacity(0)

    def _draw_horizon_heading(self, p, w, h):
        # Compass heading scale on the white horizon line: short vertical ticks
        # every horizon_heading_interval degrees and an upright numeric label
        # every horizon_heading_label_interval degrees. Drawn in the rolled
        # frame (the FPM's transform) so the ticks sit on -- and tilt with --
        # the horizon and scroll as the aircraft turns. Magnetic HEAD drives the
        # positions; the marks and the aircraft heading are both magnetic, so
        # the relative offset equals the true-bearing offset and the ticks line
        # up with the SVS terrain (the magnetic variation cancels out).
        if not getattr(self, "horizon_heading_marks", False):
            return
        if self._fpm_bad.get("HEAD") or self._fpm_fail.get("HEAD"):
            return
        ppd = getattr(self, "pixelsPerDeg",
                      self.height() / self.pitchDegreesShown)
        head = self._fpm_head
        interval = max(1, int(getattr(self, "horizon_heading_interval", 10)))
        label_iv = max(interval,
                       int(getattr(self, "horizon_heading_label_interval", 20)))
        tick_len = float(getattr(self, "horizon_heading_tick_length", 5))
        col = QColor(getattr(self, "horizon_heading_color", "#ffffff"))
        if not col.isValid():
            col = QColor(Qt.GlobalColor.white)
        roll = self._rollAngle

        p.save()
        p.resetTransform()
        p.translate(w / 2.0, h / 2.0 - self._horizon_offset_px())
        p.rotate(-roll)
        horizon_y = self._pitchAngle * ppd   # the pitch=0 line in this frame

        pen = QPen(col)
        pen.setWidth(max(1, qRound(self.fontSize * 0.04)))
        p.setPen(pen)
        f = QFont(self.font_family)
        f.setPixelSize(max(8, qRound(self.fontSize * 0.55)))
        p.setFont(f)
        fm = p.fontMetrics()
        cull = w * 0.75

        for mk in range(0, 360, interval):
            d = ((mk - head + 180.0) % 360.0) - 180.0
            x = d * ppd
            if abs(x) > cull:
                continue
            p.drawLine(QPointF(x, horizon_y), QPointF(x, horizon_y - tick_len))
            if mk % label_iv == 0:
                lbl = self._heading_label(mk)
                p.save()
                p.translate(x, horizon_y - tick_len)
                p.rotate(roll)   # keep the number upright despite bank
                p.drawText(QPointF(-fm.horizontalAdvance(lbl) / 2.0, -3.0), lbl)
                p.restore()
        p.restore()

    @staticmethod
    def _heading_label(deg):
        # Magnetic heading label: cardinal letter at N/E/S/W, else the heading
        # in tens (060 -> "6", 340 -> "34"), matching the HSI compass rose.
        deg = int(round(deg)) % 360
        return {0: "N", 90: "E", 180: "S", 270: "W"}.get(deg, str(deg // 10))

    def _horizon_offset_px(self):
        # Pixels to shift the pitch=0 horizon UP from the viewport centre,
        # derived from horizon_position (percent up the screen; 50 = centred,
        # which yields 0). Positive = horizon higher on the screen.
        return (float(getattr(self, "horizon_position", 50)) / 100.0
                - 0.5) * self.height()

    def _bank_anchor_y(self, h):
        # Screen y of the bank-arc CENTRE, from bank_position (percent of
        # height measured UP from the bottom, like horizon_position;
        # 50 = the classic viewport centre). The whole bank cluster --
        # arc, roll pointer, datum triangle, diamonds, slip ball --
        # anchors here.
        pos = max(0.0, min(100.0,
                           float(getattr(self, "bank_position", 50))))
        return h * (1.0 - pos / 100.0)

    def _horizon_offset_deg(self):
        # The same shift expressed as a look-down angle (offset_px /
        # pixelsPerDeg, which reduces to height-independent form). The SVS
        # terrain projects pitch=0 to the viewport centre, so depressing its
        # camera by this angle raises the terrain horizon to match the AI's.
        return (float(getattr(self, "horizon_position", 50)) / 100.0
                - 0.5) * self.pitchDegreesShown

    def redraw(self):
        # self.scene is the inherited QGraphicsView.scene METHOD until
        # resizeEvent builds the instance attribute (see
        # _attach_svs_item_if_ready). showEvent can fire before the first
        # resizeEvent, so guard against drawing before the scene exists --
        # resizeEvent calls redraw() again once it's built.
        scene = self.__dict__.get("scene")
        if scene is None:
            return
        self.resetTransform()
        _avoid = getattr(self, "pitch_ladder_avoid_bank", False)
        # Raise the whole attitude reference per horizon_position. The view
        # rotates roll about the viewport CENTRE, so a plain vertical centre
        # offset would make the raised horizon swing around the centre (the
        # symbol would drift off the horizon at bank). Injecting the "up by
        # _off" shift rotated by the bank angle makes it a pure SCREEN-space
        # vertical shift after the -roll view rotation, so the horizon keeps
        # pivoting on the (raised) aircraft symbol at any bank. _off = 0 (the
        # default) leaves everything centred and unchanged.
        _off = self._horizon_offset_px()
        _rr = math.radians(self._rollAngle)
        self.centerOn(
            scene.width() / 2 + _off * math.sin(_rr),
            scene.height() / 2 + _off * math.cos(_rr)
            + self._pitchAngle * self.pixelsPerDeg * -1.0)
        self.rotate(self._rollAngle * -1.0)

# We use the paintEvent to draw on the viewport the parts that aren't moving.
        if _avoid:
            self.setPitchItems()

    def paintEvent(self, event):
        # Wall-clock-bound paintEvent timing for perf debugging. When
        # svs_perf_log is enabled on the SVS renderer we report the
        # full paintEvent duration AND the gap between consecutive
        # paintEvents alongside the SVS-internal timings, so we can
        # see how much of the per-frame budget is consumed inside vs
        # outside SVS. Cheap to leave compiled in — perf object is
        # held by the SVS renderer and only does work when its
        # ``enabled`` flag is set.
        import time as _time
        perf = getattr(getattr(self, "svs", None), "_perf", None)
        if perf is not None and perf.enabled:
            _pe_t0 = _time.perf_counter_ns()
            _pe_last = getattr(self, "_perf_last_paint_ns", 0)
            if _pe_last:
                perf.add_ns("frame.gap_between_paintEvent",
                            _pe_t0 - _pe_last)
            self._perf_last_paint_ns = _pe_t0
        else:
            _pe_t0 = 0

        # Choose the below-horizon fill (grey / sky-while-SVS-draws / brown)
        # BEFORE the scene renders, so it's correct this frame. paintEvent runs
        # on every repaint, however it was triggered (FIX callbacks, the frame
        # clock, runway updates) — unlike _frame_tick, which short-circuits when
        # the pose key is unchanged. Change-cached, so it only touches the brush
        # on an actual transition.
        self._update_land_brush()
        if self.terrain_only:
            # Clean SVS-environment frame: hide the z=1 symbology scene items
            # (horizon line + pitch ladder), render terrain + sky only, and skip
            # every paintEvent overlay (aircraft symbol, bank, slip, FPM, ...).
            hl = getattr(self, "_horizon_line", None)
            if hl is not None:
                hl.setOpacity(0.0)
            for _i, _item in self.pitchItems:
                _item.setOpacity(0.0)
            super(AI, self).paintEvent(event)
            return
        super(AI, self).paintEvent(event)
        w = self.width()
        h = self.height()
        r = self.bankAngleRadius
        m = self.bankMarkSize
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # SVS terrain is rendered as a QGraphicsItem inside super().paintEvent()
        # above, at a low z-value (default -10). The pitch ladder (z=1) and any
        # other scene items render on top. Overlay symbology below is painted
        # directly onto the viewport, so it always lands in front of SVS.

        # Put the static overlay image on the view
        p.drawImage(self.rect(), self.overlay)

        # SVS UNAVAIL annunciation. The SVS is GL-required; if the GL
        # renderer failed to initialise or draw (e.g. SVS enabled on a
        # machine with no usable GPU/driver), it disables itself and we
        # annunciate rather than silently showing the sky/ground two-tone
        # as if terrain awareness were available. Resolve the renderer
        # clobber-safe (self.svs is often the YAML config DICT, on which
        # every getattr returns False — which would suppress this warning).
        _svs = self._live_svs()
        if (_svs is not None
                and getattr(_svs, "enabled", False)
                and getattr(_svs, "gl_failed", False)):
            p.save()
            _af = QFont(self.font_family, -1, QFont.Weight.Bold)
            _af.setPixelSize(max(12, qRound(self.fontSize * 0.9)))
            p.setFont(_af)
            p.setPen(QPen(QColor(255, 176, 0)))
            p.drawText(QRectF(0, h * 0.18, w, h * 0.12),
                       Qt.AlignmentFlag.AlignCenter, "SVS UNAVAIL")
            p.restore()

        pen = QPen(Qt.GlobalColor.white)
        pen.setWidth(qRound(self.fontSize * 0.025))
        p.setPen(pen)
        p.setBrush(QColor(Qt.GlobalColor.white))
        marks = QPen(Qt.GlobalColor.white)

        # Bank-cluster anchor (bank_position; 50 = the classic centre).
        p.translate(w / 2, self._bank_anchor_y(h))

        # Unusual-attitude regime (AC 25-11B App A A.2.2 / p.47) -- drives both
        # the recovery chevrons and the de-clutter. Computed up front so the
        # non-essential overlays below can be suppressed this frame; the
        # chevrons themselves are drawn last (on top).
        self._show_recovery_chevrons = (
            self._pitchAngle > self.unusualPitchHighDeg
            or self._pitchAngle < self.unusualPitchLowDeg)
        self._decluttered = (self._show_recovery_chevrons
                             or abs(self._rollAngle) > self.unusualBankDeg)

        # Caution states are computed even when the bank cluster is drawn
        # transparent -- other logic (annunciations, tests) reads them.
        # Slip / Skid: amber past the excessive-sideslip threshold
        # (AC 25-11B App A A.2.6: caution). Excessive bank
        # (AC 25-11B App A A.2.5): amber scale + pointer past the
        # threshold, before stall buffet.
        self._excessive_slip = abs(self._latAccel) >= self.excessiveSlip
        self._excessive_bank = abs(self._rollAngle) > self.excessiveBankDeg

        # bankOpacity (0..1): the whole bank-angle cluster -- slip/skid
        # ball, bank scale + roll pointer, standard-rate diamonds -- fades
        # together, the same dial pitchOpacity gives the ladder. 0 skips
        # the drawing entirely (SVS-as-background mode).
        bank_op = max(0.0, min(1.0,
                               float(getattr(self, "bankOpacity", 1.0))))
        if bank_op > 0.0:
            if bank_op < 1.0:
                p.setOpacity(bank_op)
            p.setPen(QColor(Qt.GlobalColor.black))
            p.setBrush(QColor(255, 150, 0) if self._excessive_slip
                       else QColor(Qt.GlobalColor.white))
            p.drawEllipse(QPointF(self._latAccel * -m*12, -r + m*3),
                          m*0.8, m*0.8)

            _bank_col = (QColor(255, 150, 0) if self._excessive_bank
                         else QColor(Qt.GlobalColor.white))
            p.rotate(self._rollAngle * -1.0)
            # Add moving Bank Angle Markers
            marks.setColor(_bank_col)
            marks.setWidth(qRound(self.fontSize * 0.05))
            p.setPen(marks)
            p.setBrush(_bank_col)
            smallMarks = [10, 20, 45]
            largeMarks = [30, 60]
            shortLine = QLineF(0, -r, 0, -(r-m))
            longLine = QLineF(0, -(r+m), 0, -(r-m))
            for angle in smallMarks:
                p.rotate(angle)
                p.drawLine(shortLine)
                p.rotate(- 2 * angle)
                p.drawLine(shortLine)
                p.rotate(angle)
            for angle in largeMarks:
                p.rotate(angle)
                p.drawLine(longLine)
                p.rotate(- 2 * angle)
                p.drawLine(longLine)
                p.rotate(angle)
            triangle = QPolygonF([QPointF(m/2, -(r+m/2)),
                                 QPointF(-m/2, -(r+m/2)),
                                 QPointF(0, -(r - m/2))])
            p.drawPolygon(triangle)
            # Draw standard rate turn markers (non-essential -- de-cluttered
            # at an unusual attitude).
            if self.drawBankMarkers and not self._decluttered:
                a = math.degrees(math.atan(self._tas/364.0))
                if a > self.bankAngleMaximum:
                    a = self.bankAngleMaximum
                diamond = QPolygonF([QPointF(0, -r),
                                    QPointF(-m*0.8, -(r+m*0.8)),
                                    QPointF(-0, -r - m*1.6),
                                    QPointF(m*0.8, -(r+m*0.8))])
                p.setBrush(Qt.GlobalColor.transparent)
                p.rotate(a)
                p.drawPolygon(diamond)
                p.rotate(-2 * a)
                p.drawPolygon(diamond)
            if bank_op < 1.0:
                p.setOpacity(1.0)

        # FPM and the horizon heading scale are non-essential recovery clutter --
        # suppressed at an unusual attitude (de-clutter).
        if not self._decluttered:
            self._drawFPM(p, w, h)
            self._draw_horizon_heading(p, w, h)

        # Unusual-attitude recovery chevrons (AC 25-11B App A A.2.2). Past the
        # pitch thresholds, guide the recovery toward the nearest horizon. Drawn
        # last so they sit on top of the de-cluttered display.
        if self._show_recovery_chevrons:
            self._draw_recovery_chevrons(p, w, h)

        if _pe_t0:
            perf.add_ns("frame.ai_paintEvent_total",
                        _time.perf_counter_ns() - _pe_t0)

    # We don't want this responding to keystrokes
    def keyPressEvent(self, event):
        pass

    # Don't want it acting with the mouse scroll wheel either
    def wheelEvent(self, event):
        pass

    def showEvent(self, event):
        self.redraw()

    def setRollAngle(self, angle):
        if angle != self._rollAngle and not self.getAIFail():
            self._rollAngle = common.bounds(-180, 180, angle)
            self._frame_dirty = True

    def getRollAngle(self):
        return self._rollAngle

    rollAngle = property(getRollAngle, setRollAngle)

    def setLateralAcceleration(self, value):
        if value != self._latAccel:
            self._latAccel = common.bounds(-0.3, 0.3, value)
            self._frame_dirty = True

    def setTrueAirspeed(self, value):
        if value != self._tas:
            self._tas = value
            self._frame_dirty = True

    def getPitchAngle(self):
        return self._pitchAngle

    def setPitchAngle(self, angle):
        if angle != self._pitchAngle and not self.getAIFail():
            self._pitchAngle = common.bounds(-90, 90, angle)
            self.setPitchItems()
            self._frame_dirty = True

    pitchAngle = property(getPitchAngle, setPitchAngle)

    def getPitchAngle(self):
        return self._pitchAngle

    def getAIFail(self):
        return True in self._AIFail.values()

    def setAIFailRoll(self, fail):
        self.setFail(fail,'ROLL')

    def setAIFailPitch(self, fail):
        self.setFail(fail,'PITCH')

    def setAIFailLAcc(self, fail):
        self.setFail(fail,'ALAT')

    def setAIFailTAS(self, fail):
        self.setFail(fail,'TAS')

    def setFail(self, fail,item=None):
        if fail != self._AIFail[item]:
            self._AIFail[item] = fail
            if hasattr(self, 'fail_scene'):
                if self.getAIFail():
                    self.resetTransform()
                    self.setScene (self.fail_scene)
                else:
                    self.setScene (self.scene)
                    # Initially set to grey
                    # we may have old data while recovering
                    if hasattr(self, 'sky_rect'):
                        if self.getAIOld() or self.getAIBad():
                            self.sky_rect.setBrush (self.gray_sky)
                        else:
                            self.sky_rect.setBrush (self.gblue_brush)
                        self._update_land_brush()   # land: grey/sky/brown
                    self.redraw()

    def getAIOld(self):
        return True in self._AIOld.values()

    def setAIOldRoll(self, old):
        self.setOld(old,'ROLL')

    def setAIOldPitch(self, old):
        self.setOld(old,'PITCH')

    def setAIOldLAcc(self, old):
        self.setOld(old,'ALAT')

    def setAIOldTAS(self, old):
        self.setOld(old,'TAS')

    def setOld(self, old, item=None):
        log.debug("Set AI Old")
        if old != self._AIOld[item]:
            self._AIOld[item] = old
            if hasattr(self, 'sky_rect'):
                if self.getAIOld():
                    self.sky_rect.setBrush (self.gray_sky)
                    #self.old_text.show()
                else:
                    self.sky_rect.setBrush (self.gblue_brush)
                    #self.old_text.hide()
                self._update_land_brush()
                self.redraw()

    def getAIBad(self):
        return True in self._AIBad.values()

    def setAIBadRoll(self, bad):
        self.setBad(bad,'ROLL')

    def setAIBadPitch(self, bad):
        self.setBad(bad,'PITCH')

    def setAIBadLAcc(self, bad):
        self.setBad(bad,'ALAT')

    def setAIBadTAS(self, bad):
        self.setBad(bad,'TAS')

    def setBad(self, bad, item=None):
        log.debug("Set AI Bad")
        if bad != self._AIBad[item]:
            self._AIBad[item] = bad
            if hasattr(self, 'sky_rect'):
                if self.getAIBad():
                    self.sky_rect.setBrush (self.gray_sky)
                    #self.bad_text.show()
                else:
                    self.sky_rect.setBrush (self.gblue_brush)
                    #self.bad_text.hide()
                self._update_land_brush()
                self.redraw()




class FDTarget(QGraphicsView):
    def __init__(self, center, pixelsPerDeg, parent=None):
        super(FDTarget, self).__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0%); border: 0px")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.aicenter = center
        self.pixelsPerDeg = pixelsPerDeg

    def resizeEvent(self, event):
        self.w = self.width()
        self.h = self.height()
        polyheight = 8
        self.poly_points = [(-self.w/2,-polyheight/2)
                           ,( self.w/2,-polyheight/2)
                           ,( self.w/2, polyheight/2)
                           ,(-self.w/2, polyheight/2)]

        self.scene = QGraphicsScene(0, 0, self.w*2, self.w*2)
        pen = QPen(QColor(Qt.GlobalColor.black))
        brush = QBrush (QColor (Qt.GlobalColor.magenta))
        ps = [QPointF (x,y) for x,y in self.poly_points]
        fdpoly = QPolygonF (ps)
        self.poly = self.scene.addPolygon (fdpoly, pen, brush)
        self.poly.setX(self.w)
        self.poly.setY(self.w)

        self.setScene(self.scene)
        self.aicenter.setX (self.aicenter.x()-self.w/2)
        self.aicenter.setY (self.aicenter.y()-self.h/2)
        self.centerOn (self.w, self.w)

    def update(self, fdpitch, fdroll):
        self.move (qRound(self.aicenter.x()), qRound(self.aicenter.y() - fdpitch * self.pixelsPerDeg))
        roll = fdroll * math.pi / 180
        sinroll = math.sin(roll)
        cosroll = math.cos(roll)
        ps = [QPointF (cosroll*x - sinroll*y, sinroll*x + cosroll*y) for x,y in self.poly_points]
        fdpoly = QPolygonF (ps)
        self.poly.setPolygon (fdpoly)
