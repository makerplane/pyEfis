"""Headless render tests for the Data Status instrument.

Uses the Qt 'offscreen' platform so paintEvent runs with no display. The
key guarantees: the instrument constructs and paints from a good status
file, and a missing/malformed file is handled silently (construct-never-
raises) rather than crashing the EFIS at boot."""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from pyefis.instruments import data_status


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


SAMPLE = {
    "ok": True, "generated": "2026-06-14T00:00:00Z", "worst": "amber",
    "any_attention": True,
    "packs": [
        {"id": "airports-conus", "name": "Airports & Runways", "kind": "navdata",
         "status": "current", "severity": "none", "cycle": "2606",
         "expires": "2026-07-09", "days": 25, "detail": "2606"},
        {"id": "obstacles-conus", "name": "Obstacles", "kind": "obstacles",
         "status": "EXPIRED", "severity": "amber", "cycle": "260500",
         "expires": "2026-06-11", "days": -3, "detail": "260500 expired 2026-06-11"},
    ],
}


def _write(tmp_path, doc):
    p = tmp_path / "status.json"
    p.write_text(json.dumps(doc))
    return p


def test_constructs_and_paints(app, tmp_path):
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w.resize(800, 480)
    assert w.status["ok"] is True and len(w.status["packs"]) == 2
    pm = w.grab()                       # forces paintEvent offscreen
    assert not pm.isNull() and pm.width() == 800


def test_missing_file_is_safe(app, tmp_path):
    w = data_status.DataStatus(status_path=str(tmp_path / "nope.json"))
    w.resize(400, 300)
    assert w.status is None             # never raised
    assert not w.grab().isNull()        # paints the "unavailable" message


def test_malformed_file_is_safe(app, tmp_path):
    p = tmp_path / "status.json"
    p.write_text("{ not valid json ][")
    w = data_status.DataStatus(status_path=str(p))
    w.resize(400, 300)
    assert w.status is None
    assert not w.grab().isNull()


def test_reload_picks_up_changes(app, tmp_path):
    p = _write(tmp_path, {"ok": True, "packs": []})
    w = data_status.DataStatus(status_path=str(p))
    assert w.status["packs"] == []
    p.write_text(json.dumps(SAMPLE))
    w.reload()
    assert len(w.status["packs"]) == 2


def test_severity_color_keys(app):
    assert set(data_status.SEVERITY_COLORS) == {"amber", "white", "none"}


def test_continue_without_hmi_does_not_raise(app, tmp_path):
    # _on_continue must be safe even when hmi.actions isn't initialised.
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w._on_continue()                    # no exception


def test_update_command_is_expanduser(app, tmp_path, monkeypatch):
    # The updater must launch an absolute/~-expanded path (systemd PATH excludes
    # ~/.local/bin), not a bare name. The Update button now starts the flow with
    # a `sources` probe.
    from PyQt6.QtCore import QProcess
    captured = {}
    monkeypatch.setattr(QProcess, "start",
                        lambda self, prog, args: captured.update(prog=prog, args=args))
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)),
                               update_command="~/.local/bin/pyefis-data")
    w._on_update()
    assert captured["prog"] == os.path.expanduser("~/.local/bin/pyefis-data")
    assert captured["args"] == ["sources", "--json"]


# --- PackPicker + the Update -> sources -> catalog -> install flow ---

CATALOG = {
    "ok": True, "generated": "2026-06-15T00:00:00Z",
    "storage": {"root": "/data/makerplane-data",
                "free_bytes": 350_000_000_000, "total_bytes": 460_000_000_000},
    "packs": [
        {"id": "airports-conus", "name": "Airports & Runways", "kind": "navdata",
         "status": "current", "severity": "none", "bytes": 6_000_000,
         "regions": ["conus"], "tracked": True, "installed": True},
        {"id": "terrain-us-west", "name": "Terrain", "kind": "terrain",
         "status": "MISSING", "severity": "white", "bytes": 9_984_793_161,
         "regions": ["us-west"], "tracked": False, "installed": False},
        {"id": "water-na", "name": "Water", "kind": "water",
         "status": "MISSING", "severity": "white", "bytes": 2_460_000_000,
         "regions": ["conus", "us-west"], "tracked": False, "installed": False},
    ],
}


DRIVES = {"drives": [
    {"mount": "/data", "device": "/dev/mmcblk0p1", "fstype": "ext4",
     "free_bytes": 360_000_000_000, "total_bytes": 460_000_000_000, "removable": False},
    {"mount": "/media/wpballard/SSD", "device": "/dev/sda1", "fstype": "exfat",
     "free_bytes": 900_000_000_000, "total_bytes": 1_000_000_000_000, "removable": True},
]}


def test_parse_json_skips_leading_lines():
    out = "  fetch http://x\n  build ...\n" + json.dumps({"ok": True})
    assert data_status._parse_json(out) == {"ok": True}
    assert data_status._parse_json("no json here") is None


def test_picker_prechecks_tracked_and_renders(app):
    pk = data_status.PackPicker(doc=CATALOG)
    pk.resize(800, 480)
    assert pk.selected_ids() == ["airports-conus"]      # only the tracked pack
    assert not pk.grab().isNull()                        # paints offscreen


def test_picker_row_tap_toggles_checkbox(app):
    # On the touchscreen the whole row must toggle (tapping the tiny indicator
    # is unreliable); children are mouse-transparent and the row toggles on tap.
    # A tap is press+release on (nearly) the same spot — the row toggles on
    # release within a small slop so that two-finger scroll drags don't select.
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtCore import QEvent, QPointF, Qt

    def tap(row, x=5, y=5):
        for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            ev = QMouseEvent(kind, QPointF(x, y),
                             Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier.NoModifier)
            (row.mousePressEvent if kind == QEvent.Type.MouseButtonPress
             else row.mouseReleaseEvent)(ev)

    pk = data_status.PackPicker(doc=CATALOG)
    pk.resize(800, 480)
    assert "water-na" not in pk.selected_ids()
    assert pk.checks["water-na"].testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    tap(pk.rows["water-na"])
    assert "water-na" in pk.selected_ids()               # tap selected it
    tap(pk.rows["water-na"])
    assert "water-na" not in pk.selected_ids()           # tap again deselects


def test_picker_install_emits_selection(app):
    got = {}
    pk = data_status.PackPicker(doc=CATALOG, on_install=lambda ids: got.update(ids=ids))
    pk.resize(800, 480)
    pk.checks["water-na"].setChecked(True)
    pk._do_install()
    assert set(got["ids"]) == {"airports-conus", "water-na"}


def test_picker_free_space_guard_disables_install(app):
    tight = {**CATALOG, "storage": {"root": "/x",
             "free_bytes": 1_000_000_000, "total_bytes": 2_000_000_000}}
    pk = data_status.PackPicker(doc=tight)
    pk.resize(800, 480)
    pk.checks["terrain-us-west"].setChecked(True)        # 9.9 GB > 1 GB free
    assert pk.btn_install.isEnabled() is False


def _stub_run(w):
    """Replace DataStatus._run with a capture that records (args, on_finish)."""
    calls = []
    w._run = lambda args, on_finish, on_line=None: calls.append((list(args), on_finish))
    return calls


def test_update_flow_sources_catalog_picker(app, tmp_path):
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w.resize(800, 480)
    calls = _stub_run(w)
    w._on_update()
    assert calls[0][0] == ["sources", "--json"]
    calls[0][1](0, json.dumps({"network": True, "usb": []}))   # sources result
    assert calls[1][0] == ["catalog", "--json"]                # default: Internet
    calls[1][1](0, json.dumps(CATALOG))                        # catalog result
    assert w.mode == "picker" and w.picker is not None
    assert w.picker.selected_ids() == ["airports-conus"]


def test_update_flow_no_sources_is_clean(app, tmp_path):
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w.resize(800, 480)
    calls = _stub_run(w)
    w._on_update()
    calls[0][1](0, json.dumps({"network": False, "usb": []}))
    assert w.mode == "status"
    assert "No internet" in w.message and w.btn_update.isEnabled()


def test_update_flow_usb_only_uses_source(app, tmp_path):
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w.resize(800, 480)
    calls = _stub_run(w)
    w._on_update()
    calls[0][1](0, json.dumps({"network": False, "usb": ["/media/u/stick/makerplane-data"]}))
    assert calls[1][0] == ["catalog", "--json", "--source",
                           "/media/u/stick/makerplane-data"]


def test_update_flow_install_then_back_to_status(app, tmp_path):
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w.resize(800, 480)
    calls = _stub_run(w)
    w._on_update()
    calls[0][1](0, json.dumps({"network": True, "usb": []}))
    calls[1][1](0, json.dumps(CATALOG))
    w.picker.checks["water-na"].setChecked(True)
    w._install_selected(w.picker.selected_ids())
    assert w.mode == "busy"
    assert calls[2][0] == ["update", "--only", "airports-conus,water-na", "--progress"]
    calls[2][1](0, "  airports-conus  installed 2606\n")        # success
    assert w.mode == "status" and "complete" in w.message.lower()
    assert w.picker is None


def test_picker_storage_chooser_removable_warns(app):
    pk = data_status.PackPicker(doc=CATALOG, on_change_storage=lambda: None)
    pk.resize(900, 560)
    assert pk.chosen_root is None
    pk.open_drive_chooser(DRIVES["drives"])
    assert pk._chooser is not None and not pk.grab().isNull()
    pk._apply_storage(DRIVES["drives"][1])               # the removable SSD
    assert pk.chosen_root == "/media/wpballard/SSD/makerplane-data"
    assert pk._chooser is None                            # overlay closed
    assert not pk.warn_label.isHidden()                   # removable warning shown
    assert "/media/wpballard/SSD/makerplane-data" in pk.storage_label.text()


def test_picker_storage_internal_no_warning(app):
    pk = data_status.PackPicker(doc=CATALOG, on_change_storage=lambda: None)
    pk.resize(900, 560)
    pk._apply_storage(DRIVES["drives"][0])                # internal /data
    assert pk.chosen_root == "/data/makerplane-data"
    assert pk.warn_label.isHidden() is True


def test_update_flow_storage_chooser_passes_root(app, tmp_path):
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w.resize(900, 560)
    calls = _stub_run(w)
    w._on_update()
    calls[0][1](0, json.dumps({"network": True, "usb": []}))   # sources
    calls[1][1](0, json.dumps(CATALOG))                        # catalog
    w._choose_storage()
    assert calls[2][0] == ["drives", "--json"]
    calls[2][1](0, json.dumps(DRIVES))                         # drives
    assert w.picker._chooser is not None
    w.picker._apply_storage(DRIVES["drives"][0])               # pick /data
    w._install_selected(w.picker.selected_ids())
    assert "--root" in calls[3][0]
    assert calls[3][0][calls[3][0].index("--root") + 1] == "/data/makerplane-data"


def test_progress_line_parsing_updates_bar(app, tmp_path):
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w.resize(900, 560)
    w.mode = "busy"
    w._on_progress_line(json.dumps({"event": "begin", "total": 3}))
    assert w._prog["total"] == 3 and w._prog["pct"] is None
    w._on_progress_line(json.dumps({"event": "pack", "index": 2, "total": 3,
                                    "id": "terrain-us-west", "name": "Terrain"}))
    assert w._prog["index"] == 2 and w._prog["name"] == "Terrain"
    w._on_progress_line(json.dumps({"event": "progress", "id": "terrain-us-west",
                                    "done": 5, "total": 10, "pct": 50}))
    assert w._prog["pct"] == 50
    w._on_progress_line("  some plain log line, not json")    # ignored, no raise
    assert w._prog["pct"] == 50
    assert not w.grab().isNull()                                # busy bar renders


def test_install_passes_progress_flag_and_streams(app, tmp_path):
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w.resize(900, 560)
    captured = {}
    w._run = lambda args, on_finish, on_line=None: captured.update(
        args=args, on_finish=on_finish, on_line=on_line)
    w.picker = None
    w._install_selected(["airports-conus", "water-na"])
    assert "--progress" in captured["args"]
    assert captured["on_line"] == w._on_progress_line       # progress is streamed
    # a progress event flowing through the streamed callback updates the bar
    captured["on_line"](json.dumps({"event": "begin", "total": 2}))
    assert w._prog["total"] == 2


def test_update_flow_cancel_returns_to_status(app, tmp_path):
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w.resize(800, 480)
    calls = _stub_run(w)
    w._on_update()
    calls[0][1](0, json.dumps({"network": True, "usb": []}))
    calls[1][1](0, json.dumps(CATALOG))
    assert w.mode == "picker"
    w._cancel_picker()
    assert w.mode == "status" and w.picker is None


class _FakeProc:
    """Stand-in for the install QProcess so the cancel path is testable without
    a real subprocess: it just records that terminate()/kill() were called."""
    def __init__(self):
        self.terminated = False
        self.killed = False

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def _drive_to_busy(w, calls):
    w._on_update()
    calls[0][1](0, json.dumps({"network": True, "usb": []}))
    calls[1][1](0, json.dumps(CATALOG))
    w.picker.checks["water-na"].setChecked(True)
    w._install_selected(w.picker.selected_ids())
    assert w.mode == "busy"


def test_cancel_download_returns_to_picker(app, tmp_path):
    """Cancel on the progress screen terminates the updater and drops back to
    the pack picker with the selection intact (the 'don't feel trapped' path)."""
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w.resize(800, 480)
    calls = _stub_run(w)
    _drive_to_busy(w, calls)
    w._proc = _FakeProc()                          # the running updater process
    w._cancel_download()
    assert w._canceling is True
    assert w._proc.terminated is True              # SIGTERM delivered
    assert "cancel" in w.message.lower()
    assert not w.grab().isNull()                   # "Canceling…" screen renders
    # the terminated process now exits non-zero -> back to the picker
    w._proc = None
    calls[2][1](-1, "")
    assert w.mode == "picker"
    assert w._canceling is False
    assert "water-na" in w.picker.selected_ids()   # selection preserved
    assert w.picker.btn_install.isEnabled()        # install re-enabled for retry
    assert w.btn_cancel_dl.isHidden()              # cancel hidden off the busy screen


def test_cancel_race_completion_counts_as_success(app, tmp_path):
    """If the install actually finishes in the race before SIGTERM lands (exit
    0), it's treated as a completed update, not a cancel."""
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w.resize(800, 480)
    calls = _stub_run(w)
    _drive_to_busy(w, calls)
    w._proc = _FakeProc()
    w._cancel_download()
    w._proc = None
    calls[2][1](0, "  water-na  installed 2026q2r4\n")     # finished cleanly
    assert w.mode == "status" and "complete" in w.message.lower()
    assert w._canceling is False


def test_cancel_button_only_visible_when_busy(app, tmp_path):
    w = data_status.DataStatus(status_path=str(_write(tmp_path, SAMPLE)))
    w.resize(800, 480)
    assert w.btn_cancel_dl.isHidden()              # status mode: hidden
    w.mode = "busy"
    w._sync_visibility()
    assert not w.btn_cancel_dl.isHidden()          # busy mode: shown


# --- DataAnnunciation (persistent PFD flag) ---

def test_worst_severity():
    assert data_status.worst_severity(None) == "none"
    assert data_status.worst_severity({"ok": False}) == "none"
    assert data_status.worst_severity(SAMPLE) == "amber"   # has an expired pack
    all_current = {"ok": True, "packs": [{"severity": "none"}, {"severity": "none"}]}
    assert data_status.worst_severity(all_current) == "none"
    soon = {"ok": True, "packs": [{"severity": "none"}, {"severity": "white"}]}
    assert data_status.worst_severity(soon) == "white"


def test_annunciation_hidden_when_current(app, tmp_path):
    doc = {"ok": True, "packs": [{"name": "Airports", "severity": "none"}]}
    a = data_status.DataAnnunciation(status_path=str(_write(tmp_path, doc)))
    a.resize(120, 40)
    assert data_status.worst_severity(a.status) == "none"
    assert not a.grab().isNull()        # paints nothing, but does not crash


def test_annunciation_shows_when_expired(app, tmp_path):
    a = data_status.DataAnnunciation(status_path=str(_write(tmp_path, SAMPLE)))
    a.resize(120, 40)
    assert data_status.worst_severity(a.status) == "amber"
    assert not a.grab().isNull()


def test_annunciation_unavailable_is_hidden(app, tmp_path):
    a = data_status.DataAnnunciation(status_path=str(tmp_path / "nope.json"))
    a.resize(120, 40)
    assert a.status is None
    assert data_status.worst_severity(a.status) == "none"   # no updater -> no flag


def test_annunciation_tap_without_hmi_is_safe(app, tmp_path):
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtCore import QEvent, QPointF, Qt
    a = data_status.DataAnnunciation(status_path=str(_write(tmp_path, SAMPLE)))
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(1, 1),
                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier)
    a.mousePressEvent(ev)               # no exception
