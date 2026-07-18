# Project Template & Lessons

A transferable playbook for spinning up a new project in a different
domain, distilled from what worked (and what bit us) in the pyEfis /
aerocommons fork.

This is not domain-specific. References to pyEfis are evidence, not scope.

---

## 1. Repository skeleton

What's earned its place:

```
project-root/
├── src/<package>/                # actual code
│   ├── <subsystem>/              # one dir per major subsystem
│   └── config/                   # default user-facing config
│       ├── includes/             # reusable config fragments
│       └── preferences.yaml      # documented defaults; never edited live
├── tests/
│   ├── conftest.py               # shared fixtures, mocks of external deps
│   ├── mock_<external>/          # in-memory stand-ins for external services
│   ├── <subsystem>/test_*.py     # pytest unit tests
│   └── visual_<feature>_test.py  # standalone exploration harnesses (NOT pytest)
├── tools/                        # one-off CLI scripts (downloaders, importers)
├── docs/
│   ├── requirements.md           # stable-ID requirements (see §2)
│   ├── <feature>.md              # per-feature reference docs
│   └── planning/                 # incremental design decisions (see §2)
├── pyproject.toml
├── Makefile or task runner
└── README
```

The `visual_*_test.py` distinction matters: those are **not** unit tests.
They're standalone Python entry points that bring up a window or other
visual output for human-in-the-loop iteration. Naming them `test_*` makes
pytest pick them up; naming them `visual_*` keeps them under `tests/` for
proximity but out of CI.

---

## 2. Documentation rituals that paid off

### `docs/requirements.md` with stable IDs

Format like `<PROJECT>-<AREA>-<NNN>`, e.g. `EFIS-WIND-001`. Every PR,
issue, and commit message can cite specific IDs. Requirements never get
deleted — they get superseded; old IDs stay valid in git history.

This sounds bureaucratic until the third time you reference
"EFIS-WIND-009" in a PR description and everyone immediately knows what
you're talking about.

### Planning docs as versioned decisions

When a non-trivial decision comes up (architecture, hardware, scope split),
write it down in a dated planning doc. Examples from pyEfis:

- `docs/svs_planning.md` — captures projection-mismatch analysis,
  hardware budget thinking, and a scoped issue plan in one place.
- `docs/svs_hardware_options.md` — distills research into a buy-decision.

Future-you (and any AI assistants you work with) read these when context
gets reloaded. They're cheaper than rebuilding the reasoning from scratch
each session.

### Per-feature reference docs

`docs/<feature>.md` with the user-facing config example, the FIX-database
keys it consumes, and the visual states. Think "what does the user need
to plug this into a screen YAML." Not exhaustive API docs — just enough
that a fresh contributor can adopt the feature without reading source.

---

## 3. Branch and PR hygiene

Patterns that worked:

- **One feature per branch.** `wind-display`, `svs-renderer`, `altsel`.
  Don't mix scope. The pull is real when an adjacent fix is "right
  there"; resist it. (We slipped once with the Xlib weston guard in the
  wind PR — small enough to ship together, big enough to be visible in
  the diff.)
- **PR description format**: Summary (3-5 bullets), Test plan (checklist),
  Notes (anything reviewer needs to know — "please use merge commit, not
  squash" lives here).
- **PR scope discipline**: a PR's job is to be reviewable. The Xlib fix
  needs ten lines of context to evaluate; the wind feature needs hundreds.
  Splitting into commits within the PR is a cheap halfway measure.
- **Don't merge to your fork's main early.** Wait for the upstream PR to
  merge, then sync. Otherwise you end up ahead of upstream and have to
  manually rebase later.
- **Note the merge style** in PR description if your platform has a
  squash-merge defect or org policy. "Please use a regular merge commit,
  not squash" surfaces it before the maintainer hits the wrong button.

---

## 4. Test architecture

Three layers, each doing different work:

### Unit tests (pytest)

Cheap, fast, mocked. Use `conftest.py` to provide a shared mock of any
external service. In pyEfis the mock is the FIX database (`tests/mock_db/`);
in your project it might be a network API, a hardware bus, a database.

The test should never need the real external service running.

### Visual / interactive harnesses

Standalone Python scripts under `tests/visual_*_test.py`. Bring up a
window, accept inputs via env vars, exit on close. Not collected by
pytest. Used for design iteration, screenshots, and "does this look
right" judgement calls.

`tests/visual_svs_test.py` was the difference between "we'll guess at
camera positions" and "we'll iterate on dozens of viewpoints in an
afternoon." Worth building early.

### Integration / e2e

Where applicable. In pyEfis we never wrote these because the visual
harnesses + unit coverage were enough. In a network-heavy project they're
not optional.

---

## 5. Configuration philosophy

Two-layer, opt-in, traceable:

- **`preferences.yaml`** — defaults shipped with the package. Never edited
  by users. Every option is documented inline.
- **`preferences.yaml.custom`** — user override file. Only sections users
  want to change. Merged on top of defaults at runtime.

### Feature toggles via preference keys

Rather than hardcoding `enabled: true/false`, gate features on a named
preference key. Then the same screen YAML works whether the user wants
the feature or not — they flip one preference rather than editing the
screen layout.

### The polarity gotcha (real footgun, learned the hard way)

If you adopt a `disabled: KEY` pattern matched against
`preferences.enabled[KEY]`, decide once whether the polarity is **active
when KEY is true** (positive form) or **active when KEY is false**
(inverse). pyEfis supports both via `disabled: KEY` vs `disabled: not
KEY` and it bit us during this work — `disabled: not WIND_DISPLAY`
silently disabled the widget when we wanted it on.

Better: pick one form and stick to it project-wide, even if your config
parser supports both.

### Symptom: "my edits aren't taking effect"

If a project copies defaults to a user dir on first run and only updates
unedited files, the "is this file user-edited?" check is fragile (e.g.,
mtime equality on Windows). Document the workaround (manual `cp` from
source). Better: use a content hash, not a timestamp.

---

## 6. Cross-platform development

The project will be developed on at least two platforms (Linux primary,
Windows / macOS dev boxes). Lessons:

- **Guard platform-specific imports.** Linux-only modules (`Xlib`, `dbus`,
  `evdev`, etc.) need `try/except ImportError`, not bare `import`. Other
  platforms shouldn't crash at module load.
- **Document the dev environment.** Where do dependencies live? In pyEfis
  on Windows they're at `C:\pylib`; without that note, someone fresh
  spends an hour. A `docs/dev_environment.md` or matching memory entry
  saves the next person.
- **Default to UTF-8 line endings**, configure `core.autocrlf` explicitly.
  Save the .gitattributes file.
- **Don't assume a graceful fallback** when an external service isn't
  running. pyEfis blocks indefinitely waiting for FIX-Gateway because
  initialization is synchronous on the network call. If your app does
  this, document the symptom and add an error message that says so.

---

## 7. Performance discipline

Resist guessing. The SVS performance targets in the original commit were
educated guesses, not measurements; eight months later we're still asking
"is this actually fast enough on a Pi?"

Order of operations:

1. **Add timing instrumentation early.** A `--profile` flag that prints
   per-stage frame times costs a few hours and pays for itself the first
   time someone asks "is this fast enough."
2. **Measure on the actual target hardware.** x86 throttled to "Pi-ish"
   is unreliable — different ISA, memory bandwidth, GPU.
3. **Don't buy hardware speculatively.** Profile, then buy the exact tier
   the data says you need. The $170 → $500 → $1500 ladder is steep and
   the cheap end is often enough.
4. **Decoration vs geometry.** When something looks expensive, check
   whether it's actually expensive. Curated icons and text labels look
   polished but cost nothing; rasterizing 36k quads costs a lot. Don't
   conflate visual fidelity with computational cost.

---

## 8. Cross-session continuity (especially with AI assistants)

When you're working with an assistant across many sessions, context loss
is the silent killer. Patterns that worked:

- **Memory entries for stable facts** — user role, project context,
  environment paths, persistent preferences. The assistant should
  initialise its understanding from these, not rebuild from scratch.
- **Memory updates when state changes** — branch was merged, hardware was
  bought, decision was made. Stale memory is worse than no memory.
- **Handoff docs at session breakpoints** — `HANDOFF.md` at the project
  root, listing branch state, uncommitted work, open questions, and the
  recommended next step. Delete it once committed; recreate at the next
  break.
- **Don't trust assistant memory alone for critical state.** It can drift
  or silently lose entries. Codify load-bearing facts in committed docs
  too: `docs/svs_planning.md` is more reliable than a memory entry that
  says "we decided X."
- **Cite line numbers and IDs.** "EFIS-WIND-007 says X, see svs.py:471"
  is verifiable; "we decided to use the deadband approach" is not.

---

## 9. Specific footguns to memorise

Concrete things that bit us in this project:

| Footgun | What happened | Mitigation |
|---|---|---|
| `disabled: not KEY` polarity | Inverted feature toggle, widget didn't render | Pick one polarity project-wide |
| Windows mtime precision | Source YAML edits didn't propagate to user dir | Content hash, not timestamp |
| Unguarded `Xlib` import | pyEfis crashed at module load on Windows | `try/except ImportError` for all platform-specific deps |
| Untracked file follows branch switch | `HANDOFF.md` left on wrong branch | `git status` before every checkout |
| Squash-merge GitHub defect | Risk of mangled commit history | Note "please use merge commit" in PR description |
| Demo plugin doesn't publish wind keys | Live UI showed fail state, looked broken | Add a sim/cycle path for unattended demos |
| FIX-Gateway connection blocks GUI | "pyEfis won't start" with confusing logs | Mock the data layer in tests; document the symptom |
| `git add` refused tracked file under gitignore'd dir | `config/` is gitignored, files are tracked | Use `git add -u` for already-tracked changes |
| PR scope creep | Adjacent fixes tempting | Commit splits within PR if shipping together |
| Stale memory entries | Wrong branch / merged PR confusion | Update memory when state changes |

---

## 10. Recommended starting moves for a new project

If you're standing up a fresh repo in a new domain, in order:

1. **Pick a project ID prefix** (3-5 letters) for requirements stable IDs.
2. **Create `docs/requirements.md`** with the first half-dozen
   requirements, even if vague. They'll sharpen as you build.
3. **Create the repo skeleton** from §1. Empty dirs are fine.
4. **Write the first `tests/conftest.py`** with a mock for the most
   important external dependency. Even if the mock is trivial, the
   pattern is established.
5. **Write the first visual harness**, even if it just opens a blank
   window. The cost of adding one later is high; the cost of starting
   with one is nothing.
6. **Add a `Makefile` (or task runner)** with `init`, `test`, `clean`
   targets. Document the commands in the README.
7. **First PR** should be the skeleton + first feature, kept small. Get
   the PR rhythm established before the codebase gets opinions.
8. **Document the dev environment** (`docs/dev_environment.md` or
   equivalent). Where dependencies live, how to launch the app, common
   pitfalls. Update as you discover things.

Don't over-engineer at step 1. The point of §1-§9 is the patterns are
known so you can adopt them as scope demands, not all at once on day one.
