#  Copyright (c) 2026 MakerPlane
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

"""Data Status instrument.

Reads the navigation-data status JSON written by the ``pyefis-data`` updater
(Phase F of makerplane-data) and presents a boot-time Data Status screen:
per-pack currency with a subtle amber/white/healthy colour, a Continue
button (always available — the EFIS informs, it never restricts), and an
Update button that runs the updater over-the-air (USB sticks are picked up
automatically by the updater's udev hook; this screen reflects them on its
next refresh).

The status file is read defensively: a missing or malformed file yields a
quiet "unavailable" state and never raises — the screen must never be the
thing that stops the aircraft from booting.
"""

import json
import logging
import os
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QRectF, QProcess, qRound
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (QWidget, QPushButton, QCheckBox, QScrollArea,
                             QVBoxLayout, QHBoxLayout, QLabel)

log = logging.getLogger(__name__)

# Fixed, well-known path the updater writes (mirrors pyefis_data.config).
DEFAULT_STATUS_PATH = "~/.makerplane/pyefis/status.json"

# Subtle by design. Expired/out-of-window is amber; soon-to-expire or missing
# is white; healthy is a calm green. Nothing here is alarming.
SEVERITY_COLORS = {
    "amber": QColor(255, 176, 0),
    "white": QColor(235, 235, 235),
    "none": QColor(120, 190, 120),
}
_TITLE_COLOR = QColor(235, 235, 235)
_DIM = QColor(150, 150, 150)

_BTN_STYLE = (
    "QPushButton { color: #EEEEEE; background-color: #202830;"
    " border: 1px solid #4A5A6A; border-radius: 6px; }"
    "QPushButton:pressed { background-color: #38444F; }"
    "QPushButton:disabled { color: #777777; border-color: #333333; }"
)

_SEV_RANK = {"none": 0, "white": 1, "amber": 2}


def load_status(status_path):
    """Read the updater's status JSON. Returns the parsed dict, or None on any
    problem (missing/malformed). Never raises — shared by the screen and the
    annunciation."""
    try:
        return json.loads(Path(os.path.expanduser(str(status_path))).read_text("utf-8"))
    except Exception:
        return None


def _parse_json(text):
    """Parse the last JSON object printed by a pyefis-data command. The updater
    may emit progress lines before the JSON, so scan from the first '{'. Returns
    None on any problem (the caller degrades gracefully)."""
    if not text:
        return None
    i = text.find("{")
    if i < 0:
        return None
    try:
        return json.loads(text[i:])
    except Exception:
        return None


def worst_severity(status):
    """The most-severe pack severity. 'none' when there is nothing to show
    (no status file, or every pack current) so the PFD annunciation can hide
    rather than clutter a healthy display."""
    if not status or not status.get("ok"):
        return "none"
    return max((p.get("severity", "white") for p in status.get("packs", [])),
               key=lambda s: _SEV_RANK.get(s, 1), default="none")


def fmt_bytes(n):
    """Human size for the picker (decimal-ish, GB/MB/KB)."""
    n = n or 0
    if n >= 1 << 30:
        return f"{n / (1 << 30):.1f} GB"
    if n >= 1 << 20:
        return f"{n / (1 << 20):.0f} MB"
    if n >= 1 << 10:
        return f"{n / (1 << 10):.0f} KB"
    return f"{n} B" if n else "-"


# Pack kinds collapsed into display groups for the picker, in display order.
_KIND_GROUP = {
    "navdata": "Navigation Data", "obstacles": "Navigation Data",
    "cifp": "Navigation Data", "airports": "Navigation Data",
    "water": "Water", "highways": "Roads",
    "terrain": "Terrain", "charts": "Charts",
}
_GROUP_ORDER = ["Navigation Data", "Water", "Roads", "Terrain", "Charts"]


def _row_label(p):
    """Per-row label: region for the region-split kinds (terrain), else the
    pack's friendly name."""
    if p.get("kind") == "terrain" and p.get("regions"):
        return p["regions"][0]
    return p.get("name") or p.get("id", "")


class _PackRow(QWidget):
    """A full-width touch target for one pack: a tap anywhere on the row toggles
    its checkbox. The checkbox (and labels) are made mouse-transparent so every
    tap lands on the row, not the tiny 26px indicator — a precise tap on the box
    is unreliable on the eglfs touchscreen.

    Tap vs. scroll: toggle on *release*, and only when the pointer hasn't moved
    more than ``_TAP_SLOP`` px since press. Two-finger scrolling drags the
    synthesized pointer across the row (and scrolls the content under it), so it
    exceeds the slop and does NOT toggle; a clean tap stays put and selects.
    (The old code toggled on *press*, which fired before the gesture could be
    recognised as a scroll — so scrolling kept flipping whatever row a finger
    first landed on.)"""

    _TAP_SLOP = 12          # px of pointer movement still counted as a tap

    def __init__(self, checkbox, parent=None):
        super().__init__(parent)
        self._cb = checkbox
        self._press_pos = None

    def _moved(self, event):
        if self._press_pos is None:
            return None
        d = event.position() - self._press_pos
        return abs(d.x()) + abs(d.y())          # manhattan distance

    def mousePressEvent(self, event):
        self._press_pos = event.position()
        event.accept()

    def mouseMoveEvent(self, event):
        # Once the pointer wanders past the slop it's a scroll/drag, not a tap;
        # drop the press so the upcoming release won't toggle.
        moved = self._moved(event)
        if moved is not None and moved > self._TAP_SLOP:
            self._press_pos = None
        event.accept()

    def mouseReleaseEvent(self, event):
        moved = self._moved(event)
        if moved is not None and moved <= self._TAP_SLOP:
            self._cb.toggle()
        self._press_pos = None
        event.accept()


class PackPicker(QWidget):
    """Touch list of every available pack, grouped by kind, pre-checked from
    the device's current selection. Emits the chosen ids to install. Built from
    a ``catalog --json`` doc; no network of its own.

    Callbacks: ``on_install(ids)``, ``on_cancel()``, ``on_switch()`` (swap
    source when both Internet and USB are available)."""

    def __init__(self, parent=None, *, doc=None, source_label="Internet",
                 alt_source_label=None, font_family="DejaVu Sans Condensed",
                 on_install=None, on_cancel=None, on_switch=None,
                 on_change_storage=None):
        super().__init__(parent)
        self.font_family = font_family
        self._on_install = on_install or (lambda ids: None)
        self._on_cancel = on_cancel or (lambda: None)
        self._on_switch = on_switch or (lambda: None)
        self._on_change_storage = on_change_storage      # None -> no Change button
        doc = doc or {}
        self.packs = doc.get("packs", []) or []
        self.storage = doc.get("storage", {}) or {}
        self.chosen_root = None                            # set if user picks a drive
        self.checks = {}                                  # id -> QCheckBox
        self.rows = {}                                     # id -> _PackRow
        self._chooser = None                               # drive-chooser overlay
        self.bytes_by_id = {p["id"]: p.get("bytes", 0) for p in self.packs}
        # Opaque overlay: the picker is raised over the live data-status screen,
        # so its background must fully block what's behind it. A plain QWidget
        # ignores a stylesheet background unless WA_StyledBackground is set —
        # without it the screen underneath (e.g. the storage/drive text) bled
        # through the title and footer margins around the scroll list.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background:#0B1015;")
        self._build(source_label, alt_source_label)

    def _f(self, px, bold=False):
        f = QFont(self.font_family)
        f.setPixelSize(px)
        f.setBold(bold)
        return f

    def _build(self, source_label, alt_source_label):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("Select data to install")
        title.setStyleSheet("color:#EEEEEE;")
        title.setFont(self._f(19, bold=True))
        head.addWidget(title)
        hint = QLabel("Tap a row to select  ·  use two fingers to scroll")
        hint.setStyleSheet("color:#6E828F;")
        hint.setFont(self._f(13))                          # same small font as source
        head.addSpacing(14)
        head.addWidget(hint)
        head.addStretch(1)
        src = QLabel(f"Source: {source_label}")
        src.setStyleSheet("color:#9FBBC9;")
        src.setFont(self._f(14))
        head.addWidget(src)
        if alt_source_label:
            sw = QPushButton(f"Use {alt_source_label}")
            sw.setStyleSheet(_BTN_STYLE)
            sw.setFont(self._f(13))
            sw.setMinimumHeight(34)
            sw.clicked.connect(lambda: self._on_switch())
            head.addWidget(sw)
        outer.addLayout(head)

        srow = QHBoxLayout()
        self.storage_label = QLabel(self._storage_text())
        self.storage_label.setStyleSheet("color:#8FA0AB;")
        self.storage_label.setFont(self._f(13))
        srow.addWidget(self.storage_label)
        srow.addStretch(1)
        if self._on_change_storage is not None:
            chg = QPushButton("Change…")
            chg.setStyleSheet(_BTN_STYLE + "QPushButton{padding:5px 18px;}")
            chg.setFont(self._f(13))
            chg.setMinimumHeight(34)
            chg.setCursor(Qt.CursorShape.PointingHandCursor)
            chg.clicked.connect(lambda: self._on_change_storage())
            srow.addWidget(chg)
        outer.addLayout(srow)
        self.warn_label = QLabel("")
        self.warn_label.setStyleSheet("color:#FFB000;")
        self.warn_label.setFont(self._f(12))
        self.warn_label.setWordWrap(True)
        self.warn_label.setVisible(False)
        outer.addWidget(self.warn_label)

        area = QScrollArea(self)
        area.setWidgetResizable(True)
        area.setStyleSheet("QScrollArea{border:1px solid #2B3742;border-radius:8px;"
                           "background:#0E141A;}")
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(10, 6, 10, 8)
        col.setSpacing(2)
        groups = {}
        for p in self.packs:
            groups.setdefault(_KIND_GROUP.get(p.get("kind"), "Other"), []).append(p)
        for g in _GROUP_ORDER + [g for g in groups if g not in _GROUP_ORDER]:
            items = groups.get(g)
            if not items:
                continue
            hdr = QLabel(g)
            hdr.setStyleSheet("color:#79C7A0; padding-top:8px;")
            hdr.setFont(self._f(14, bold=True))
            col.addWidget(hdr)
            for p in sorted(items, key=lambda x: x.get("id", "")):
                col.addWidget(self._row(p))
        col.addStretch(1)
        area.setWidget(content)
        outer.addWidget(area, 1)

        foot = QHBoxLayout()
        self.summary = QLabel("")
        self.summary.setFont(self._f(14))
        foot.addWidget(self.summary)
        foot.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(lambda: self._on_cancel())
        self.btn_install = QPushButton("Install selected")
        self.btn_install.clicked.connect(self._do_install)
        # Extra horizontal padding around the label and a wider gap between the
        # two buttons (touch comfort / breathing room).
        padded = _BTN_STYLE + "QPushButton{padding:7px 30px;}"
        for b in (cancel, self.btn_install):
            b.setStyleSheet(padded)
            b.setFont(self._f(15))
            b.setMinimumHeight(44)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        foot.addWidget(cancel)
        foot.addSpacing(20)
        foot.addWidget(self.btn_install)
        outer.addLayout(foot)
        self._update_summary()

    def _row(self, p):
        cb = QCheckBox()
        cb.setChecked(bool(p.get("tracked")))
        # Fully style the indicator: the native check glyph doesn't render under
        # the running EFIS's Qt style (a size-only indicator drew nothing on the
        # device), so paint our own -- outlined box when unchecked, filled green
        # when checked. Style-independent so it always shows on eglfs.
        cb.setStyleSheet(
            "QCheckBox::indicator{width:26px;height:26px;border:2px solid #8FA3B3;"
            "border-radius:5px;background:#0E141A;}"
            "QCheckBox::indicator:checked{background:#3FB36B;border:2px solid #79C7A0;}")
        cb.stateChanged.connect(self._update_summary)
        self.checks[p["id"]] = cb
        name = QLabel(_row_label(p))
        name.setStyleSheet("color:#EAEAEA;")
        name.setFont(self._f(15))
        sev = p.get("severity", "white")
        col = {"amber": "#FFB000", "white": "#DDDDDD", "none": "#78BE78"}.get(sev, "#DDDDDD")
        meta = QLabel(f"{fmt_bytes(p.get('bytes', 0))}    {p.get('status', '')}")
        meta.setStyleSheet(f"color:{col};")
        meta.setFont(self._f(13))
        # The whole row is the touch target; children must not intercept taps.
        for child in (cb, name, meta):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        row = _PackRow(cb)
        row.setMinimumHeight(48)                          # generous touch target
        row.setStyleSheet("_PackRow:hover{background:#141C24;}")
        h = QHBoxLayout(row)
        h.setContentsMargins(4, 6, 4, 6)
        h.setSpacing(10)
        h.addWidget(cb)
        h.addWidget(name, 1)
        h.addWidget(meta)
        self.rows[p["id"]] = row
        return row

    def selected_ids(self):
        return [pid for pid, cb in self.checks.items() if cb.isChecked()]

    def _selected_bytes(self):
        return sum(self.bytes_by_id.get(pid, 0) for pid in self.selected_ids())

    def _update_summary(self, *_):
        ids = self.selected_ids()
        total = self._selected_bytes()
        free = self.storage.get("free_bytes")
        over = free is not None and total > free
        msg = f"{len(ids)} selected  -  {fmt_bytes(total)}"
        if over:
            msg += f"   needs more than the {fmt_bytes(free)} free"
        self.summary.setText(msg)
        self.summary.setStyleSheet("color:#FFB000;" if over else "color:#CCCCCC;")
        self.btn_install.setEnabled(bool(ids) and not over)

    def _do_install(self):
        self.btn_install.setEnabled(False)
        self._on_install(self.selected_ids())

    # --- storage chooser ---
    def _storage_text(self):
        st = self.storage
        if st.get("free_bytes") is not None:
            return (f"Installing to {st.get('root')}  -  "
                    f"{fmt_bytes(st['free_bytes'])} free of {fmt_bytes(st.get('total_bytes'))}")
        return f"Installing to {st.get('root', '(default location)')}"

    def open_drive_chooser(self, drives):
        """Overlay a list of candidate storage drives (from `drives --json`).
        Tapping one sets it as the install target (and warns if removable)."""
        self._close_chooser()
        self._chooser = QWidget(self)
        # Same opaque-overlay requirement as the picker itself (see __init__).
        self._chooser.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._chooser.setStyleSheet("background:#0B1015;")
        v = QVBoxLayout(self._chooser)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)
        title = QLabel("Choose where data is stored")
        title.setStyleSheet("color:#EEEEEE;")
        title.setFont(self._f(18, bold=True))
        v.addWidget(title)
        hint = QLabel("Pick a drive with room for what you're installing. An "
                      "internal drive is recommended for the permanent store.")
        hint.setStyleSheet("color:#8FA0AB;")
        hint.setFont(self._f(13))
        hint.setWordWrap(True)
        v.addWidget(hint)
        area = QScrollArea(self._chooser)
        area.setWidgetResizable(True)
        area.setStyleSheet("QScrollArea{border:1px solid #2B3742;border-radius:8px;"
                           "background:#0E141A;}")
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(8, 6, 8, 8)
        col.setSpacing(4)
        if not drives:
            none = QLabel("No writable drives found.")
            none.setStyleSheet("color:#DDDDDD;")
            none.setFont(self._f(14))
            col.addWidget(none)
        for d in drives:
            col.addWidget(self._drive_row(d))
        col.addStretch(1)
        area.setWidget(content)
        v.addWidget(area, 1)
        back = QPushButton("Back")
        back.setStyleSheet(_BTN_STYLE + "QPushButton{padding:7px 30px;}")
        back.setFont(self._f(15))
        back.setMinimumHeight(44)
        back.clicked.connect(self._close_chooser)
        brow = QHBoxLayout()
        brow.addStretch(1)
        brow.addWidget(back)
        v.addLayout(brow)
        self._chooser.setGeometry(0, 0, self.width(), self.height())
        self._chooser.show()
        self._chooser.raise_()

    def _drive_row(self, d):
        tag = "USB / removable" if d.get("removable") else "internal"
        btn = QPushButton(f"  {d['mount']}      [{tag}]      "
                          f"{fmt_bytes(d.get('free_bytes', 0))} free of "
                          f"{fmt_bytes(d.get('total_bytes', 0))}")
        btn.setStyleSheet(_BTN_STYLE + "QPushButton{text-align:left;padding:12px 16px;}")
        btn.setFont(self._f(14))
        btn.setMinimumHeight(54)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self._apply_storage(d))
        return btn

    def _apply_storage(self, d):
        root = d["mount"].rstrip("/") + "/makerplane-data"
        self.chosen_root = root
        self.storage = {"root": root, "free_bytes": d.get("free_bytes"),
                        "total_bytes": d.get("total_bytes")}
        self.storage_label.setText(self._storage_text())
        if d.get("removable"):
            self.warn_label.setText(
                "Removable drive selected. It may not be mounted on the next "
                "boot - terrain and other data could be unavailable until it is. "
                "An internal drive is recommended for the permanent store.")
            self.warn_label.setVisible(True)
        else:
            self.warn_label.setVisible(False)
        self._close_chooser()
        self._update_summary()

    def _close_chooser(self):
        if self._chooser is not None:
            self._chooser.hide()
            self._chooser.deleteLater()
            self._chooser = None


class DataStatus(QWidget):
    def __init__(self, parent=None, font_family="DejaVu Sans Condensed",
                 status_path=DEFAULT_STATUS_PATH, continue_screen="PFD",
                 update_command="pyefis-data"):
        super().__init__(parent)
        self.font_family = font_family
        self.status_path = Path(os.path.expanduser(status_path))
        self.continue_screen = continue_screen
        self.update_command = update_command
        self.status = None            # parsed dict, or None when unavailable
        self.message = ""             # transient line (e.g. "Updating…")
        self._proc = None
        self.row_h = 24
        # picker flow: "status" (default), "picker" (choose packs), "busy"
        # (installing). `_sources` is the last `sources` probe; `_source` is the
        # chosen source (None = Internet, else a USB dir path).
        self.mode = "status"
        self.picker = None
        self._sources = None
        self._source = None
        self._prog = None             # install progress: {index,total,name,pct}
        self._canceling = False       # True between Cancel tap and process exit

        self.btn_continue = QPushButton("Continue", self)
        self.btn_update = QPushButton("Update", self)
        # Cancel button for the install/progress (busy) screen, so a long
        # transfer never traps the user. Hidden except in busy mode.
        self.btn_cancel_dl = QPushButton("Cancel", self)
        self.btn_cancel_dl.clicked.connect(self._cancel_download)
        self.btn_cancel_dl.setVisible(False)
        for b in (self.btn_continue, self.btn_update, self.btn_cancel_dl):
            b.setStyleSheet(_BTN_STYLE)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_continue.clicked.connect(self._on_continue)
        self.btn_update.clicked.connect(self._on_update)

        # Refresh periodically so a USB import (handled by the updater's udev
        # hook) or a background timer update shows up without interaction.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.reload)
        self._timer.start(60_000)
        self.reload()

    # --- data ---
    def reload(self):
        self.status = load_status(self.status_path)   # construct-never-raises
        self.update()

    def showEvent(self, event):
        self.reload()
        super().showEvent(event)

    # --- actions ---
    def _on_continue(self):
        from pyefis import hmi       # lazy: avoids import-time app dependency
        if getattr(hmi, "actions", None) is not None:
            try:
                hmi.actions.trigger("show screen", self.continue_screen)
                return
            except Exception as e:
                log.warning("Continue action failed: %s", e)
        log.info("Continue pressed (no HMI action available)")

    # --- subprocess plumbing ---
    def _run(self, args, on_finish, on_line=None):
        """Run ``pyefis-data <args>`` asynchronously and call
        ``on_finish(code, stdout_text)`` exactly once. If ``on_line`` is given,
        it's called with each complete stdout line as it arrives (used to stream
        install-progress events). A failure to even start the updater routes to
        ``_fail`` (never blocks the screen)."""
        if self._proc is not None:
            return
        proc = QProcess(self)
        self._proc = proc
        state = {"done": False, "out": "", "buf": ""}

        def read_ready():
            chunk = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
            state["out"] += chunk
            if on_line:
                state["buf"] += chunk
                while "\n" in state["buf"]:
                    line, state["buf"] = state["buf"].split("\n", 1)
                    on_line(line)

        def finish(code, _status):
            if state["done"]:
                return
            state["done"] = True
            read_ready()                       # drain anything buffered
            self._proc = None
            on_finish(code, state["out"])

        def errored(_e):
            if state["done"]:
                return
            state["done"] = True
            self._proc = None
            # A user cancel terminates the process, which Qt may report as a
            # crash. Route it to the normal finish handler (cancel branch)
            # rather than the start-failure message.
            if self._canceling:
                on_finish(-1, state["out"])
            else:
                self._fail("Updater unavailable on this device.")

        proc.readyReadStandardOutput.connect(read_ready)
        proc.finished.connect(finish)
        proc.errorOccurred.connect(errored)
        # Expand ~ so a config can use ~/.local/bin/pyefis-data. An absolute
        # path is required when pyEfis runs as a systemd service, whose minimal
        # PATH excludes ~/.local/bin (a bare name would fail to start).
        proc.start(os.path.expanduser(self.update_command), args)

    def _fail(self, message):
        self._close_picker()
        self.mode = "status"
        self.message = message
        self.btn_update.setEnabled(True)
        self._sync_visibility()
        self.update()

    # --- Update flow: sources -> catalog -> picker -> install ---
    def _on_update(self):
        """Tapping Update no longer blindly runs an OTA update; it first asks
        what sources are available, then shows the pack picker."""
        if self._proc is not None or self.mode != "status":
            return
        self.message = "Checking for updates…"
        self.btn_update.setEnabled(False)
        self.update()
        self._run(["sources", "--json"], self._after_sources)

    def _after_sources(self, code, out):
        info = _parse_json(out) or {}
        net = bool(info.get("network"))
        usb = list(info.get("usb") or [])
        self._sources = {"network": net, "usb": usb}
        if not net and not usb:
            self._fail("No internet connection and no USB drive found. "
                       "Your current data is unchanged.")
            return
        # Default source: USB if it's the only one, else Internet (freshest).
        self._source = (usb[0] if (usb and not net) else None)
        self._load_catalog()

    def _load_catalog(self):
        self.message = "Loading available data…"
        self.update()
        args = ["catalog", "--json"]
        if self._source:
            args += ["--source", self._source]
        self._run(args, self._after_catalog)

    def _after_catalog(self, code, out):
        doc = _parse_json(out)
        if not doc or not doc.get("ok"):
            self._fail("Couldn't read the data catalog from that source.")
            return
        self._show_picker(doc)

    def _source_labels(self):
        """(current label, the-other-available label or None)."""
        net = self._sources.get("network")
        usb = self._sources.get("usb") or []
        on_usb = self._source is not None
        cur = "USB drive" if on_usb else "Internet"
        alt = None
        if on_usb and net:
            alt = "Internet"
        elif (not on_usb) and usb:
            alt = "USB drive"
        return cur, alt

    def _show_picker(self, doc):
        self._close_picker()
        cur, alt = self._source_labels()
        self.picker = PackPicker(
            self, doc=doc, source_label=cur, alt_source_label=alt,
            font_family=self.font_family,
            on_install=self._install_selected,
            on_cancel=self._cancel_picker,
            on_switch=self._switch_source,
            on_change_storage=self._choose_storage)
        self.mode = "picker"
        self.message = ""
        self._sync_visibility()
        self.picker.setGeometry(0, 0, self.width(), self.height())
        self.picker.show()
        self.picker.raise_()

    def _switch_source(self):
        usb = self._sources.get("usb") or []
        # toggle Internet <-> first USB
        self._source = (usb[0] if self._source is None and usb else None)
        self._load_catalog()

    def _cancel_picker(self):
        self._fail("")                # back to status, no message

    def _choose_storage(self):
        """Picker 'Change…' -> enumerate drives, then show the chooser overlay."""
        if self._proc is not None or self.picker is None:
            return
        self._run(["drives", "--json"], self._after_drives)

    def _after_drives(self, code, out):
        if self.picker is None:
            return
        doc = _parse_json(out) or {}
        self.picker.open_drive_chooser(doc.get("drives", []))

    def _install_selected(self, ids):
        if not ids:
            return
        chosen_root = getattr(self.picker, "chosen_root", None) if self.picker else None
        self.mode = "busy"
        self._prog = None
        self.message = "Installing… large packs can take several minutes."
        self._sync_visibility()
        self.update()
        args = ["update", "--only", ",".join(ids), "--progress"]
        if self._source:
            args += ["--source", self._source]
        if chosen_root:                          # picker storage chooser changed it
            args += ["--root", chosen_root]
        self._run(args, self._after_install, on_line=self._on_progress_line)

    def _on_progress_line(self, line):
        """Parse one JSON progress event from `update --progress` and refresh
        the busy screen's bar. Non-JSON lines (plain logs) are ignored."""
        line = line.strip()
        if not line.startswith("{"):
            return
        try:
            ev = json.loads(line)
        except Exception:
            return
        kind = ev.get("event")
        if kind == "begin":
            self._prog = {"total": ev.get("total", 0), "index": 0, "name": "", "pct": None}
        elif kind == "pack":
            self._prog = {"total": ev.get("total", 0), "index": ev.get("index", 0),
                          "name": ev.get("name", ""), "pct": None}
        elif kind == "progress":
            if self._prog is None:
                self._prog = {"total": 0, "index": 0, "name": ""}
            self._prog["pct"] = ev.get("pct")
        else:
            return
        if self.mode == "busy":
            self.update()

    def _cancel_download(self):
        """Tapping Cancel on the progress screen: ask the updater to stop. It
        gets a SIGTERM, unwinds the (possibly mid-) download, and leaves the
        installed data untouched (verify-then-atomic-swap). We then return to
        the pack picker with the selection preserved."""
        if self._proc is None or self._canceling:
            return
        self._canceling = True
        self.btn_cancel_dl.setEnabled(False)
        self.message = "Canceling…"
        self.update()
        self._proc.terminate()                    # SIGTERM -> graceful unwind
        # Safety net: if the updater ignores SIGTERM, hard-kill it so the user
        # is never stuck on a spinner.
        QTimer.singleShot(5000, self._force_kill_proc)

    def _force_kill_proc(self):
        if self._proc is not None and self._canceling:
            self._proc.kill()

    def _after_install(self, code, out):
        if self._canceling:
            self._canceling = False
            self.btn_cancel_dl.setEnabled(True)
            # code == 0 means the install actually finished in the race before
            # SIGTERM landed — treat it as success and fall through.
            if code != 0:
                self._prog = None
                self.message = ""
                if self.picker is not None:
                    # Back to the picker (the previous screen); their selection
                    # is intact so they can adjust or retry, or Cancel to status.
                    self.mode = "picker"
                    self.picker._update_summary()     # re-enable Install button
                    self._sync_visibility()
                    self.picker.show()
                    self.picker.raise_()
                    self.update()
                else:
                    self._fail("Update canceled — your data is unchanged.")
                return
        self._close_picker()
        self.mode = "status"
        self._prog = None
        self.btn_update.setEnabled(True)
        self.message = ("Update complete." if code == 0 else
                        "Update finished with problems — your previous data is "
                        "still in place. See the rows above.")
        self._sync_visibility()
        self.reload()                 # the updater also rewrote status.json

    def _close_picker(self):
        if self.picker is not None:
            self.picker.hide()
            self.picker.deleteLater()
            self.picker = None

    # --- layout ---
    def _sync_visibility(self):
        """Show the status buttons only in status mode; the picker covers the
        whole widget in picker mode."""
        status_mode = self.mode == "status"
        self.btn_continue.setVisible(status_mode)
        self.btn_update.setVisible(status_mode)
        self.btn_cancel_dl.setVisible(self.mode == "busy")
        if self.mode == "busy":
            self.btn_cancel_dl.raise_()
        if self.picker is not None:
            self.picker.setVisible(self.mode == "picker")
            if self.mode == "picker":
                self.picker.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event):
        w, h = self.width(), self.height()
        self.row_h = max(16, qRound(h * 0.055))
        self.font = QFont(self.font_family)
        self.font.setPixelSize(qRound(self.row_h * 0.62))
        self.title_font = QFont(self.font_family)
        self.title_font.setPixelSize(qRound(self.row_h * 0.85))
        self.font.setPixelSize(qRound(self.row_h * 0.62))

        bw, bh = qRound(w * 0.22), qRound(h * 0.10)
        by = h - bh - qRound(h * 0.05)
        self.btn_continue.setGeometry(qRound(w * 0.10), by, bw, bh)
        self.btn_update.setGeometry(qRound(w * 0.68), by, bw, bh)
        f = QFont(self.font_family)
        f.setPixelSize(qRound(bh * 0.4))
        self.btn_continue.setFont(f)
        self.btn_update.setFont(f)
        # Cancel sits centred below the progress bar in the busy screen.
        self.btn_cancel_dl.setGeometry((w - bw) // 2, qRound(h * 0.62), bw, bh)
        self.btn_cancel_dl.setFont(f)
        if self.picker is not None:
            self.picker.setGeometry(0, 0, w, h)

    # --- paint ---
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if self.mode == "busy":
            # Installing: a calm centred panel with a per-pack progress bar.
            p.fillRect(self.rect(), QColor(11, 16, 21))
            hc = int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            p.setFont(self.title_font)
            p.setPen(_TITLE_COLOR)
            p.drawText(QRectF(0, h * 0.30, w, self.row_h * 1.4), hc,
                       "Canceling…" if self._canceling
                       else "Installing navigation data")
            prog = self._prog
            p.setFont(self.font)
            if prog and prog.get("total"):
                name = prog.get("name") or "…"
                sub = f"{name}    ({prog.get('index', 0)} of {prog.get('total', 0)})"
                p.setPen(SEVERITY_COLORS["white"])
                p.drawText(QRectF(0, h * 0.30 + self.row_h * 1.7, w, self.row_h), hc, sub)
                bw = int(w * 0.6)
                bx = (w - bw) // 2
                by = qRound(h * 0.30 + self.row_h * 3.1)
                bh = max(10, qRound(self.row_h * 0.5))
                pct = prog.get("pct")
                p.setPen(QColor(70, 84, 96))
                p.setBrush(QColor(20, 28, 36))
                p.drawRoundedRect(QRectF(bx, by, bw, bh), 4, 4)
                if pct is not None:
                    fillw = int(bw * max(0, min(100, pct)) / 100)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QColor(63, 179, 107))
                    if fillw > 0:
                        p.drawRoundedRect(QRectF(bx, by, fillw, bh), 4, 4)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(SEVERITY_COLORS["white"])
                p.drawText(QRectF(0, by + bh + 6, w, self.row_h),
                           int(Qt.AlignmentFlag.AlignHCenter),
                           f"{pct}%" if pct is not None else "working…")
            else:
                p.setPen(SEVERITY_COLORS["white"])
                p.drawText(QRectF(0, h * 0.30 + self.row_h * 1.7, w, self.row_h),
                           hc, self.message or "Installing…")
            return

        # Single-line so a long detail string clips at its column instead of
        # wrapping down into the next pack's row.
        flags = int(Qt.TextFlag.TextSingleLine | Qt.AlignmentFlag.AlignLeft
                    | Qt.AlignmentFlag.AlignVCenter)
        x = qRound(w * 0.10)
        col_status = qRound(w * 0.42)
        col_detail = qRound(w * 0.58)
        y = qRound(h * 0.10)

        p.setFont(self.title_font)
        p.setPen(_TITLE_COLOR)
        p.drawText(QRectF(x, y, w * 0.8, self.row_h), flags, "NAVIGATION DATA")
        gen = (self.status or {}).get("generated")
        if gen:
            p.setFont(self.font)
            p.setPen(_DIM)
            p.drawText(QRectF(col_detail, y, w - col_detail - x, self.row_h), flags,
                       f"catalog {gen[:10]}")
        y += qRound(self.row_h * 1.8)

        p.setFont(self.font)
        if not self.status or not self.status.get("ok"):
            p.setPen(SEVERITY_COLORS["white"])
            p.drawText(QRectF(x, y, w - 2 * x, self.row_h), flags,
                       "Data status unavailable — run an update to populate it.")
        else:
            for pk in self.status.get("packs", []):
                color = SEVERITY_COLORS.get(pk.get("severity", "white"),
                                            SEVERITY_COLORS["white"])
                p.setPen(color)
                p.drawText(QRectF(x, y, col_status - x, self.row_h), flags,
                           str(pk.get("name", pk.get("id", ""))))
                p.drawText(QRectF(col_status, y, col_detail - col_status, self.row_h), flags,
                           str(pk.get("status", "")))
                p.drawText(QRectF(col_detail, y, w - col_detail - x, self.row_h), flags,
                           str(pk.get("detail", "")))
                y += self.row_h

        if self.message:
            p.setFont(self.font)
            p.setPen(SEVERITY_COLORS["white"])
            p.drawText(QRectF(x, h * 0.74, w - 2 * x, self.row_h), flags, self.message)


class DataAnnunciation(QWidget):
    """A small, persistent 'DATA' flag for the flight (PFD) view.

    Subtle by design: amber when any installed navdata is expired, white when
    expiring soon or missing, and **hidden** when everything is current (or no
    updater is present) so a healthy display is never cluttered. Tapping it
    jumps to the Data Status screen.
    """

    def __init__(self, parent=None, font_family="DejaVu Sans Condensed",
                 status_path=DEFAULT_STATUS_PATH, target_screen="DataStatus"):
        super().__init__(parent)
        self.font_family = font_family
        self.status_path = os.path.expanduser(status_path)
        self.target_screen = target_screen
        self.status = None
        self.font = QFont(font_family)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.reload)
        self._timer.start(60_000)
        self.reload()

    def reload(self):
        self.status = load_status(self.status_path)
        self.update()

    def showEvent(self, event):
        self.reload()
        super().showEvent(event)

    def mousePressEvent(self, event):
        from pyefis import hmi
        if getattr(hmi, "actions", None) is not None:
            try:
                hmi.actions.trigger("show screen", self.target_screen)
            except Exception as e:
                log.warning("DATA annunciation tap failed: %s", e)

    def resizeEvent(self, event):
        self.font = QFont(self.font_family)
        self.font.setPixelSize(max(8, qRound(self.height() * 0.7)))

    def paintEvent(self, event):
        sev = worst_severity(self.status)
        if sev == "none":
            return                      # healthy / no updater -> show nothing
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = SEVERITY_COLORS.get(sev, SEVERITY_COLORS["white"])
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        pen = p.pen()
        pen.setColor(color)
        p.setPen(pen)
        p.drawRoundedRect(rect, 3, 3)
        p.setFont(self.font)
        p.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "DATA")
