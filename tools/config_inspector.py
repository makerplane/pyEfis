#!/usr/bin/env python3

"""
Config Inspector: Standalone Qt app to explore pyEfis configuration

Features:
- Loads preferences.yaml (+ preferences.yaml.custom overrides) and default.yaml
- Resolves includes according to preferences['includes'] mapping
- Presents a consolidated tree view of the final configuration
- Marks values resolved from preferences (e.g., enabled.AUTO_START)
- Marks preference keys overridden by .custom with an [override] tag
- Shows expandable nodes for each include with the concrete file used
- If an include file is used >1 time, annotate nodes and provide a summary

This viewer is read-only and does not modify config files.
"""

from __future__ import annotations

import argparse
import os
import sys
import yaml
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Optional, Set

from PyQt6.QtCore import Qt, QPoint, QRegularExpression
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTreeView,
    QWidget,
    QVBoxLayout,
    QLabel,
    QSplitter,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QComboBox,
    QPlainTextEdit,
    QDialog,
    QDialogButtonBox,
)
from PyQt6.QtCore import QSortFilterProxyModel


# ---------- Utilities for preferences loading and merge tracking ----------

Path = Tuple[str, ...]


def deep_merge_with_overrides(base: Any, override: Any, path: Optional[Path] = None, overridden: Optional[set] = None) -> Any:
    """Deep merge override into base. Track paths where override changes/defines values.

    Returns the merged value. Collects overridden key paths (as tuples) in the 'overridden' set.
    """
    if overridden is None:
        overridden = set()
    if path is None:
        path = tuple()

    # If either side is not a dict, override completely
    if not isinstance(base, dict) or not isinstance(override, dict):
        if override is not None:
            overridden.add(path)
            return override
        return base

    out = dict(base)
    for k, v in override.items():
        p = path + (k,)
        if k in base:
            out[k] = deep_merge_with_overrides(base[k], v, p, overridden)
            # If the merged subtree equals base[k] but we've passed through override, still record if value differs
            if isinstance(base[k], dict) and isinstance(v, dict):
                # changes recorded at leaf nodes already
                pass
            else:
                if base[k] != out[k]:
                    overridden.add(p)
        else:
            out[k] = v
            overridden.add(p)
    return out


def load_preferences(config_dir: str) -> Tuple[Dict[str, Any], Set[Path]]:
    """Load preferences.yaml and merge preferences.yaml.custom if present, tracking overridden paths."""
    pref_path = os.path.join(config_dir, "preferences.yaml")
    with open(pref_path, "r", encoding="utf-8") as f:
        base = yaml.safe_load(f) or {}
    cust_path = pref_path + ".custom"
    overridden: Set[Path] = set()
    if os.path.exists(cust_path):
        with open(cust_path, "r", encoding="utf-8") as f:
            custom = yaml.safe_load(f) or {}
        merged = deep_merge_with_overrides(base, custom, overridden=overridden)
        return merged, overridden
    return base, overridden


# ---------- Include resolution and traversal with tracking ----------

@dataclass
class IncludeRecord:
    logical: str
    file_path: str
    contexts: List[str] = field(default_factory=list)


class ConfigWalker:
    def __init__(self, base_config_dir: str, preferences: Dict[str, Any]):
        self.base_config_dir = base_config_dir
        self.preferences = preferences or {}
        self.includes_used: Dict[str, IncludeRecord] = {}  # key: resolved file path
        self.include_nodes: List[Tuple[str, QStandardItem]] = []  # (file_path, item)

    def _resolve_include_file(self, current_file_dir: str, logical_or_path: str) -> Tuple[str, str]:
        """Resolve include using resolution order: current dir -> base dir -> preferences.includes mapping.
        Returns (logical_name, resolved_path).
        """
        # If it's a direct path that exists relative to current
        candidate = os.path.join(current_file_dir, logical_or_path)
        if os.path.exists(candidate):
            return logical_or_path, os.path.normpath(candidate)

        # Try base dir
        candidate = os.path.join(self.base_config_dir, logical_or_path)
        if os.path.exists(candidate):
            return logical_or_path, os.path.normpath(candidate)

        # Try preferences includes mapping
        logical = logical_or_path
        includes_map = (self.preferences or {}).get("includes", {})
        mapped = includes_map.get(logical)
        if mapped:
            # mapped can be relative to current or base
            cand2 = os.path.join(current_file_dir, mapped)
            if os.path.exists(cand2):
                return logical, os.path.normpath(cand2)
            cand2 = os.path.join(self.base_config_dir, mapped)
            if os.path.exists(cand2):
                return logical, os.path.normpath(cand2)
        raise FileNotFoundError(f"Cannot resolve include '{logical_or_path}' (base: {self.base_config_dir})")

    def _record_include(self, logical: str, resolved_path: str, context: str) -> None:
        rec = self.includes_used.get(resolved_path)
        if not rec:
            rec = IncludeRecord(logical=logical, file_path=resolved_path, contexts=[])
            self.includes_used[resolved_path] = rec
        rec.contexts.append(context)

    # ---------- Tree model population ----------
    def build_model(self, root_config_file: str) -> QStandardItemModel:
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Key", "Value", "Source/Notes"])  # 3 columns

        # – Preferences root
        prefs_root = QStandardItem("Preferences (merged)")
        prefs_root.setEditable(False)
        model.appendRow([prefs_root, QStandardItem("") , QStandardItem("")])
        self._populate_preferences_tree(prefs_root)

        # – Config root
        config_root = QStandardItem("Config (consolidated)")
        config_root.setEditable(False)
        model.appendRow([config_root, QStandardItem("") , QStandardItem(os.path.relpath(root_config_file, self.base_config_dir))])

        # Walk the main config
        file_dir = os.path.dirname(root_config_file)
        with open(root_config_file, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

        # Build tree from cfg
        self._walk_mapping(cfg, parent=config_root, current_file=root_config_file, breadcrumb=("<root>",))

        # – Includes summary root
        summary_root = QStandardItem("Includes summary")
        summary_root.setEditable(False)
        model.appendRow([summary_root, QStandardItem("") , QStandardItem("")])
        for path, rec in sorted(self.includes_used.items(), key=lambda kv: kv[0]):
            label = f"{os.path.relpath(path, self.base_config_dir)}"
            used_n = len(rec.contexts)
            notes = f"used {used_n} time(s); logical: {rec.logical}; contexts: " + " | ".join(rec.contexts)
            item = QStandardItem(label)
            item.setEditable(False)
            summary_root.appendRow([item, QStandardItem("") , QStandardItem(notes)])

        # After building, annotate include nodes to compact multiple [include] markers
        # Replace any number of leading "[include] " with a single "[{n}x] " when a file is used multiple times
        # and remove any trailing "(used nx)" legacy suffixes.
        counts: Dict[str, int] = {k: len(v.contexts) for k, v in self.includes_used.items()}
        for fpath, item in self.include_nodes:
            cnt = counts.get(fpath, 1)
            text = item.text()

            # Remove any trailing legacy suffix like " (used 6x)"
            if " (used " in text:
                text = text[: text.rfind(" (used ")]

            # Strip all leading "[include] " prefixes
            prefix = "[include] "
            while text.startswith(prefix):
                text = text[len(prefix) :]

            # Re-apply compact prefix
            if cnt > 1:
                item.setText(f"[{cnt}x] {text}")
            else:
                item.setText(f"[include] {text}")
        return model

    def _populate_preferences_tree(self, parent: QStandardItem) -> None:
        # Show merged preferences; mark overridden paths
        overridden_paths = getattr(self, "_overridden_paths", set())

        def add_node(key: str, val: Any, p: QStandardItem, path: Path) -> None:
            key_item = QStandardItem(str(key))
            key_item.setEditable(False)
            val_item = QStandardItem("")
            src_item = QStandardItem("")

            if isinstance(val, dict):
                p.appendRow([key_item, val_item, src_item])
                for k, v in val.items():
                    add_node(k, v, key_item, path + (k,))
            elif isinstance(val, list):
                p.appendRow([key_item, QStandardItem(f"[{len(val)} items]"), src_item])
                for i, v in enumerate(val):
                    add_node(f"[{i}]", v, key_item, path + (str(i),))
            else:
                # scalar
                vtext = self._scalar_to_text(val)
                val_item.setText(vtext)
                # mark override
                if path in overridden_paths:
                    src_item.setText("[override]")
                p.appendRow([key_item, val_item, src_item])

        add_node("root", self.preferences, parent, tuple())

    def set_overridden_paths(self, overridden_paths: Set[Path]) -> None:
        self._overridden_paths = overridden_paths

    def _scalar_to_text(self, v: Any) -> str:
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, bool):
            return "true" if v else "false"
        if v is None:
            return "null"
        return str(v)

    # -------------- YAML traversal and model building --------------
    def _walk_mapping(self, mapping: Dict[str, Any], parent: QStandardItem, current_file: str, breadcrumb: Path) -> None:
        cur_dir = os.path.dirname(current_file)
        for key, val in (mapping or {}).items():
            if key == "include":
                # This can be a string or list of strings
                files: List[str]
                if isinstance(val, str):
                    files = [val]
                elif isinstance(val, list):
                    files = val
                else:
                    raise SyntaxError(f"include in {current_file} must be a string or list")

                for f in files:
                    logical, resolved = self._resolve_include_file(cur_dir, f)
                    # include node
                    short = os.path.relpath(resolved, self.base_config_dir)
                    include_item = QStandardItem(f"{logical} -> {short}")
                    include_item.setEditable(False)
                    # Second column empty (it's a container)
                    src_item = QStandardItem("[include]")
                    parent.appendRow([QStandardItem("[include]"), QStandardItem("") , QStandardItem(f"{logical} -> {short}")])
                    # The visual tree should put children under the include descriptor; use the last inserted row's first item as parent
                    include_parent: QStandardItem = parent.child(parent.rowCount() - 1, 0)
                    include_parent.setText(f"[include] {logical} -> {short}")
                    self.include_nodes.append((resolved, include_parent))

                    # Record usage
                    self._record_include(logical, resolved, context="/".join(breadcrumb))

                    # Load included YAML and traverse it
                    with open(resolved, "r", encoding="utf-8") as incf:
                        sub = yaml.safe_load(incf) or {}
                    if isinstance(sub, dict):
                        self._walk_mapping(sub, include_parent, current_file=resolved, breadcrumb=breadcrumb + (f"include:{logical}",))
                    else:
                        # If included file yields non-dict, just display scalar/list directly
                        self._walk_value(sub, include_parent, current_file=resolved, key_label="<items>", breadcrumb=breadcrumb + (f"include:{logical}",))
                continue

            # Normal key path
            key_item = QStandardItem(str(key))
            key_item.setEditable(False)
            if isinstance(val, dict):
                parent.appendRow([key_item, QStandardItem("") , QStandardItem("")])
                self._walk_mapping(val, key_item, current_file=current_file, breadcrumb=breadcrumb + (str(key),))
            elif isinstance(val, list):
                parent.appendRow([key_item, QStandardItem(f"[{len(val)} items]"), QStandardItem("")])
                self._walk_list(val, key_item, current_file=current_file, breadcrumb=breadcrumb + (str(key),))
            else:
                # scalar: resolve enabled.* if applicable
                display_text, notes = self._resolve_scalar_with_preferences(val)
                parent.appendRow([key_item, QStandardItem(display_text), QStandardItem(notes)])

    def _walk_list(self, arr: List[Any], parent: QStandardItem, current_file: str, breadcrumb: Path) -> None:
        cur_dir = os.path.dirname(current_file)
        for i, elem in enumerate(arr):
            # list-level include form: element is a dict with 'include'
            if isinstance(elem, dict) and "include" in elem:
                logical, resolved = self._resolve_include_file(cur_dir, elem["include"])
                short = os.path.relpath(resolved, self.base_config_dir)
                parent.appendRow([QStandardItem("[include]"), QStandardItem("") , QStandardItem(f"{logical} -> {short}")])
                include_parent: QStandardItem = parent.child(parent.rowCount() - 1, 0)
                include_parent.setText(f"[include] {logical} -> {short}")
                self.include_nodes.append((resolved, include_parent))
                self._record_include(logical, resolved, context="/".join(breadcrumb + (f"[{i}]",)))

                # load items
                with open(resolved, "r", encoding="utf-8") as incf:
                    sub = yaml.safe_load(incf) or {}
                if not isinstance(sub, dict) or "items" not in sub:
                    # Fallback: show whatever is in the file under this include
                    self._walk_value(sub, include_parent, current_file=resolved, key_label="<items>", breadcrumb=breadcrumb + (f"include:{logical}",))
                else:
                    items = sub.get("items")
                    if isinstance(items, list):
                        for j, a in enumerate(items):
                            self._walk_value(a, include_parent, current_file=resolved, key_label=f"[{j}]", breadcrumb=breadcrumb + (f"include:{logical}",))
                    elif isinstance(items, dict):
                        # edge: dict under items
                        for k, v in items.items():
                            self._walk_value({k: v}, include_parent, current_file=resolved, key_label=str(k), breadcrumb=breadcrumb + (f"include:{logical}",))
                continue

            # normal element
            self._walk_value(elem, parent, current_file=current_file, key_label=f"[{i}]", breadcrumb=breadcrumb + (f"[{i}]",))

    def _walk_value(self, val: Any, parent: QStandardItem, current_file: str, key_label: str, breadcrumb: Path) -> None:
        if isinstance(val, dict):
            key_item = QStandardItem(key_label)
            key_item.setEditable(False)
            parent.appendRow([key_item, QStandardItem("") , QStandardItem("")])
            self._walk_mapping(val, key_item, current_file=current_file, breadcrumb=breadcrumb + (key_label,))
        elif isinstance(val, list):
            key_item = QStandardItem(key_label)
            key_item.setEditable(False)
            parent.appendRow([key_item, QStandardItem(f"[{len(val)} items]"), QStandardItem("")])
            self._walk_list(val, key_item, current_file=current_file, breadcrumb=breadcrumb + (key_label,))
        else:
            display_text, notes = self._resolve_scalar_with_preferences(val)
            parent.appendRow([QStandardItem(key_label), QStandardItem(display_text), QStandardItem(notes)])

    def _resolve_scalar_with_preferences(self, val: Any) -> Tuple[str, str]:
        """If val is a string that matches preferences['enabled'] key, return final bool and marker.
        Otherwise return stringified val.
        """
        # Convert scalars
        if isinstance(val, str):
            enabled = (self.preferences or {}).get("enabled", {}) or {}
            if val in enabled:
                resolved = enabled[val]
                # annotate if overridden
                ov = getattr(self, "_overridden_paths", set())
                over_mark = " [override]" if (('enabled', val) in ov or ("enabled", val) in ov) else ""
                return ("true" if bool(resolved) else "false", f"resolved from enabled.{val}{over_mark}")
            # Not an enabled token
            return (val, "")
        # Non-string scalars
        if isinstance(val, bool):
            return ("true" if val else "false", "")
        if val is None:
            return ("null", "")
        return (str(val), "")


# ---------- Main Window ----------

class ConfigInspectorWindow(QMainWindow):
    def __init__(self, model: QStandardItemModel, base_dir: str, root_file: str):
        super().__init__()
        self.setWindowTitle("pyEfis Config Inspector")
        self.resize(1100, 800)

        # Main widget
        main = QWidget(self)
        layout = QVBoxLayout(main)
        main.setLayout(layout)

        info = QLabel(f"Base config dir: {base_dir}\nRoot config: {os.path.relpath(root_file, base_dir)}")
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        # Filters row
        filters_row = QWidget(self)
        filters_layout = QHBoxLayout(filters_row)
        filters_row.setLayout(filters_layout)
        self.key_filter_edit = QLineEdit(self)
        self.key_filter_edit.setPlaceholderText("Filter by key (case-sensitive substring)")
        self.value_filter_edit = QLineEdit(self)
        self.value_filter_edit.setPlaceholderText("Filter by value (case-sensitive substring)")
        filters_layout.addWidget(QLabel("Key filter:"))
        filters_layout.addWidget(self.key_filter_edit, 1)
        filters_layout.addWidget(QLabel("Value filter:"))
        filters_layout.addWidget(self.value_filter_edit, 1)

        # Proxy model for filtering
        self.proxy = TreeFilterProxy()
        self.proxy.setSourceModel(model)
        self.proxy.setRecursiveFilteringEnabled(True)

        # Tree view
        self.tree = QTreeView(self)
        self.tree.setModel(self.proxy)
        # Enable non-uniform rows so wrapped text can expand height if needed
        self.tree.setUniformRowHeights(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(False)
        self.tree.expandToDepth(1)
        self.tree.header().setStretchLastSection(True)
        self.tree.header().setDefaultSectionSize(380)
        # Allow wrapping in cells when text has line breaks
        self.tree.setWordWrap(True)
        # Context menu for expand/collapse subtree
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)

        # Wire up filters
        self.key_filter_edit.textChanged.connect(self._on_filters_changed)
        self.value_filter_edit.textChanged.connect(self._on_filters_changed)

        # AND/OR operator selector for filters
        op_row = QWidget(self)
        op_layout = QHBoxLayout(op_row)
        op_row.setLayout(op_layout)
        op_layout.addWidget(QLabel("Filter logic:"))
        self.logic_combo = QComboBox(self)
        self.logic_combo.addItems(["AND", "OR"])  # default AND
        self.logic_combo.currentTextChanged.connect(self._on_filters_changed)
        op_layout.addWidget(self.logic_combo)

        layout.addWidget(info)
        layout.addWidget(filters_row)
        layout.addWidget(op_row)
        layout.addWidget(self.tree)

        self.setCentralWidget(main)

    def _on_filters_changed(self, *_):
        key_text = self.key_filter_edit.text().strip()
        val_text = self.value_filter_edit.text().strip()
        self.proxy.set_key_filter(key_text)
        self.proxy.set_value_filter(val_text)
        self.proxy.set_op_mode(self.logic_combo.currentText() or "AND")

        # Optionally expand nodes that remain to show matches context (leave as-is)

    def _on_context_menu(self, pos: QPoint):
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        menu = QMenu(self)
        act_expand = menu.addAction("All expand")
        act_collapse = menu.addAction("All collapse")
        act_view = menu.addAction("View full text…")
        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action == act_expand:
            self._expand_subtree(index)
        elif action == act_collapse:
            self._collapse_subtree(index)
        elif action == act_view:
            self._open_view_dialog(index)

    def _expand_subtree(self, proxy_index):
        # Expand this node and all descendants
        stack = [proxy_index]
        while stack:
            idx = stack.pop()
            if not idx.isValid():
                continue
            self.tree.expand(idx)
            for r in range(self.proxy.rowCount(idx)):
                child = self.proxy.index(r, 0, idx)
                stack.append(child)

    def _collapse_subtree(self, proxy_index):
        # Collapse descendants then the node
        stack = [proxy_index]
        order = []
        while stack:
            idx = stack.pop()
            if not idx.isValid():
                continue
            order.append(idx)
            for r in range(self.proxy.rowCount(idx)):
                child = self.proxy.index(r, 0, idx)
                stack.append(child)
        # collapse in reverse so children first
        for idx in reversed(order):
            self.tree.collapse(idx)

    def _open_view_dialog(self, proxy_index):
        if not proxy_index.isValid():
            return
        # Gather row data
        def col_text(c):
            return self.proxy.data(self.proxy.index(proxy_index.row(), c, proxy_index.parent()), Qt.ItemDataRole.DisplayRole) or ""
        key = col_text(0)
        val = col_text(1)
        notes = col_text(2)
        dlg = QDialog(self)
        dlg.setWindowTitle("Full text")
        dlg.resize(700, 500)
        v = QVBoxLayout(dlg)
        t = QPlainTextEdit(dlg)
        t.setReadOnly(True)
        t.setPlainText(f"Key:\n{key}\n\nValue:\n{val}\n\nNotes:\n{notes}")
        v.addWidget(t)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=dlg)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        v.addWidget(buttons)
        dlg.exec()


class TreeFilterProxy(QSortFilterProxyModel):
    """Filter by key (column 0) and value (column 1) independently.
    Both filters are AND-ed: a row matches if it matches the key filter AND the value filter.
    Recursive filtering is enabled so parents remain if any child matches.
    """
    def __init__(self):
        super().__init__()
        self._key_re: Optional[QRegularExpression] = None
        self._val_re: Optional[QRegularExpression] = None
        # Case-sensitive by default per request
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        self._op_mode: str = "AND"  # or "OR"

    def set_key_filter(self, text: str):
        self._key_re = self._make_re(text)
        self.invalidateFilter()

    def set_value_filter(self, text: str):
        self._val_re = self._make_re(text)
        self.invalidateFilter()

    def _make_re(self, text: str) -> Optional[QRegularExpression]:
        if not text:
            return None
        # escape and wrap as contains
        pattern = QRegularExpression.escape(text)
        return QRegularExpression(f".*{pattern}.*")

    def set_op_mode(self, mode: str):
        mode = (mode or "AND").upper()
        if mode not in ("AND", "OR"):
            mode = "AND"
        if mode != self._op_mode:
            self._op_mode = mode
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        model = self.sourceModel()
        idx_key = model.index(source_row, 0, source_parent)
        idx_val = model.index(source_row, 1, source_parent)

        def text(index):
            return model.data(index, Qt.ItemDataRole.DisplayRole) or ""

        # Check self match
        key_ok = True
        val_ok = True
        if self._key_re is not None:
            key_ok = self._key_re.match(str(text(idx_key))).hasMatch()
        if self._val_re is not None:
            val_ok = self._val_re.match(str(text(idx_val))).hasMatch()

        if self._op_mode == "AND":
            # AND: all non-empty filters must match
            if self._key_re is not None and not key_ok:
                self_match = False
            elif self._val_re is not None and not val_ok:
                self_match = False
            else:
                self_match = True
        else:  # OR
            active = []
            if self._key_re is not None:
                active.append(key_ok)
            if self._val_re is not None:
                active.append(val_ok)
            if not active:  # no filters active -> match everything
                self_match = True
            else:
                self_match = any(active)

        if self_match:
            return True

        # Otherwise, accept if any child matches recursively
        for r in range(model.rowCount(idx_key)):
            if self.filterAcceptsRow(r, idx_key):
                return True

        return False


# ---------- CLI / Entry Point ----------

def find_default_config() -> Tuple[str, str]:
    """Attempt to find default.yaml and return (base_config_dir, default_yaml_path)."""
    user_home = os.environ.get('SNAP_REAL_HOME', os.path.expanduser("~"))
    prefix_path = sys.prefix
    path_options = [
        '{USER}/makerplane/pyefis/config',
        '{PREFIX}/local/etc/pyefis',
        '{PREFIX}/etc/pyefis',
        '/etc/pyefis',
        '.',
    ]
    config_filename = 'default.yaml'
    for directory in path_options:
        d = directory.format(USER=user_home, PREFIX=prefix_path)
        cand = os.path.join(d, config_filename)
        if os.path.isfile(cand):
            return os.path.abspath(d), os.path.abspath(cand)
    # Fallback to repo-relative location
    here = os.path.dirname(os.path.abspath(__file__))
    repo_config = os.path.abspath(os.path.join(here, '..', 'config'))
    cand = os.path.join(repo_config, config_filename)
    return repo_config, cand


def main():
    parser = argparse.ArgumentParser(description="pyEfis Config Inspector")
    parser.add_argument("--config", dest="config_file", help="Path to config/default.yaml. Defaults to auto-detect.")
    parser.add_argument("--base", dest="base_dir", help="Base config directory. Defaults to directory of --config or auto-detected.")
    args = parser.parse_args()

    if args.config_file:
        config_file = os.path.abspath(args.config_file)
        base_dir = os.path.abspath(args.base_dir) if args.base_dir else os.path.dirname(config_file)
    else:
        base_dir, config_file = find_default_config()

    if not os.path.exists(config_file):
        print(f"Error: cannot find config file: {config_file}", file=sys.stderr)
        sys.exit(2)

    # Load preferences and overrides
    preferences, overridden = load_preferences(base_dir)

    # Build model
    app = QApplication(sys.argv)
    walker = ConfigWalker(base_dir, preferences)
    walker.set_overridden_paths(overridden)
    model = walker.build_model(config_file)

    w = ConfigInspectorWindow(model, base_dir, config_file)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
