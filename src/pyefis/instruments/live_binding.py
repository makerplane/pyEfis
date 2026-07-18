#  Copyright (c) 2026 Bill Mallard
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

"""Runtime control bindings -- derive a widget setting from a FIX key's value.

The read side of the control-bindings layer (makerplane-data
docs/control_bindings.md). A control (button / knob) writes a FIX key; a widget
mixes in :class:`LiveBindingMixin` and lists its :class:`LiveBind` descriptors, so
each ``<prop>_key`` option, when set, subscribes to that key and drives the
setting -- converting the key value per the binding's semantics.

Shared here (not re-implemented per widget) so the ~43 widgets that will gain
bindable settings do not each re-do the subscribe / convert / repaint / startup
dance. The startup-ordering policy lives in one place too (see ``_seed``).
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import pyavtools.fix as fix

logger = logging.getLogger(__name__)


@dataclass
class LiveBind:
    """One runtime binding on a widget.

    ``attr``        the widget attribute the setting lives on (e.g. ``range_nm``).
    ``semantics``   bool | index_ladder | enum | scalar (see instrument_spec).
    ``key_option``  the option that names the FIX key (e.g. ``range_key``).
    ``ladder_option`` (index_ladder) the comma-list option the index steps through.
    ``enum``        (enum) the ordered options the index selects.
    ``apply``       optional ``fn(widget, value)`` that applies the converted value
                    instead of ``setattr`` -- used when a setter has side effects
                    (e.g. a map layer toggle rebuilds the live layer object).
    """

    attr: str
    semantics: str
    key_option: str
    ladder_option: str = ""
    enum: Sequence = field(default_factory=tuple)
    apply: Optional[Callable] = None


class LiveBindingMixin:
    """Mix into a QWidget to give its settings live FIX-key bindings.

    Call :meth:`init_live_bindings` once, AFTER the screenbuilder has applied the
    widget's options (e.g. from the first ``paintEvent``, alongside other lazy
    setup), passing the widget's :class:`LiveBind` list.
    """

    def init_live_bindings(self, binds, node_id=0):
        if getattr(self, "_live_binds_ready", False):
            return
        self._live_binds_ready = True
        self._live_binds = []
        for b in binds:
            key = getattr(self, b.key_option, None)
            if not key:
                continue                       # unbound -> stays a static option
            key = str(key).replace("{id}", str(node_id))
            try:
                item = fix.db.get_item(key)
            except Exception:                  # noqa: BLE001 -- construct-never-raises
                logger.warning("live binding: FIX key %r unavailable", key)
                continue
            # Seed the key from the config default BEFORE connecting our slot, so
            # seeding does not fire our OWN applier. That matters for a setter
            # binding (a map layer): applying mid-init would call set_layer and,
            # on the device, re-enter the terrain system and abort. Seeding first
            # still puts the value on the bus for other listeners; the widget is
            # already at its config default, so there is nothing to re-apply.
            self._seed(b, item)
            slot = self._live_slot(b, item)
            for typ in (float, int, bool):
                try:
                    item.valueChanged[typ].connect(slot)
                except Exception:              # overload may not exist; harmless
                    pass
            self._live_binds.append((b, item, slot))

    # --- internals ---------------------------------------------------------
    def _live_slot(self, b, item):
        def slot(*_ignored):
            self._apply_bind(b, item.value)
        return slot

    def _apply_bind(self, b, raw):
        value = self._convert(b, raw)
        if value is None:
            return
        # CRITICAL: FIX valueChanged callbacks arrive on a NON-GUI thread. Touch
        # only plain Python attributes here -- do NOT call Qt (update(), a layer
        # toggle, ...) directly, or Qt aborts (SIGABRT) on the cross-thread
        # access. The widget repaints from its own GUI-thread loop; the map's
        # frame timer already polls the bound attrs (range_nm/orientation) and
        # repaints on change, exactly like its LAT/LONG handlers. A setter
        # `apply` must itself be GUI-thread-safe (none are wired yet).
        if b.apply is not None:
            b.apply(self, value)
        else:
            setattr(self, b.attr, value)

    def _bind_options(self, b):
        if b.semantics == "enum":
            return list(b.enum)
        raw = getattr(self, b.ladder_option, "") or ""     # index_ladder
        out = []
        for tok in str(raw).split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                out.append(float(tok))
            except ValueError:
                pass
        return out

    def _convert(self, b, raw):
        """FIX key value -> the setting's value, per semantics. None = ignore."""
        try:
            if b.semantics == "bool":
                return bool(raw)
            if b.semantics == "scalar":
                return float(raw)
            options = self._bind_options(b)     # index_ladder | enum
            if not options:
                return None
            idx = int(round(float(raw)))
            idx = max(0, min(len(options) - 1, idx))
            return options[idx]
        except (TypeError, ValueError):
            return None

    def _current_index(self, b):
        """The key value that represents the widget's CURRENT setting -- used to
        seed the key from the config default at startup."""
        cur = getattr(self, b.attr, None)
        if b.semantics == "bool":
            return 1 if cur else 0
        if b.semantics == "scalar":
            try:
                return float(cur)
            except (TypeError, ValueError):
                return None
        options = self._bind_options(b)
        if not options:
            return None
        if b.semantics == "enum":
            try:
                return options.index(cur)
            except ValueError:
                return 0
        try:                                    # index_ladder: nearest step
            return min(range(len(options)),
                       key=lambda i: abs(options[i] - float(cur)))
        except (TypeError, ValueError):
            return 0

    def _seed(self, b, item):
        """Startup policy (control_bindings.md 11.3, Phase 1): with no persistence
        yet, the CONFIG DEFAULT wins -- seed the key so annunciators/other readers
        see the right state immediately, then the key drives the setting. Phase 3
        will instead let a persisted key value win on connect."""
        idx = self._current_index(b)
        if idx is None:
            return
        try:
            item.value = idx
            item.output_value()
        except Exception:                       # noqa: BLE001
            logger.debug("live binding: could not seed %s", b.key_option)
