# Running pyEfis from source (laptop / developer)

This is for developers who want to run pyEfis from a git checkout on a normal
desktop or laptop (Linux, internet-connected). If you just want to *use* pyEfis
on a Raspberry Pi, use the snap install in [INSTALLING.md](../INSTALLING.md)
instead.

## Prerequisites

- Python **3.8+** (`requires-python = ">=3.8, <4"`).
- `git`, `make`, and a working **display** (pyEfis is a Qt GUI; it can't render
  headless).
- On Linux you may also need the usual Qt runtime system libraries (e.g.
  `libegl1`) if the PyQt6 wheel doesn't pull everything in.

## 1. Clone

```bash
git clone https://github.com/makerplane/pyEfis.git   # or your fork
cd pyEfis
git checkout <branch>                                 # the branch you want to run
```

## 2. Virtual environment

Recommended (skip only if you deliberately want the global interpreter):

```bash
make venv
source venv/bin/activate     # re-run this in every new shell
```

## 3. Install dependencies  (the step that trips people up)

`make init` installs the **development tooling only** (pytest, flake8, black,
…). It does **not** install the runtime GUI/3D dependencies, which live in
optional extras in `pyproject.toml`. You must install those explicitly:

```bash
make init                    # dev tooling (optional if you're not testing)
pip install -e '.[qt,svs]'   # <-- the app's actual runtime dependencies
```

What the extras are, and why they're split:

| Extra | Pulls in | Needed for |
|---|---|---|
| `qt`  | `PyQt6` | **Required.** pyEfis will not start without it (`import PyQt6` fails). |
| `svs` | `numpy`, `PyOpenGL` | **Optional.** Only needed to render Synthetic Vision (terrain). Without it, pyEfis runs normally and the attitude view annunciates `SVS UNAVAIL`. |

If you only want to run the standard PFD/MFD and don't care about terrain,
`pip install -e '.[qt]'` is enough. Use `'.[qt,svs]'` to enable SVS.

> If you `make init` and then `python pyEfis.py` and it dies immediately on
> `ModuleNotFoundError: No module named 'PyQt6'`, you skipped this step. Install
> the `qt` extra.

## 4. FIX-Gateway (the data source)

pyEfis is only the **display** — it reads flight data over TCP from
[FIX-Gateway](https://github.com/makerplane/FIX-Gateway), which must be running
separately. Install and start it per its own README (its `xplane` plugin is an
easy laptop data source for testing). pyEfis will start without it but shows no
live data.

## 5. Run

```bash
python pyEfis.py
```

Useful flags: `--debug` (verbose logging), `--config-file <path>` (use a
specific config instead of the default).

## First-run behavior and file locations

On first launch pyEfis **auto-creates** `~/makerplane/pyefis/config/` and copies
in default config files (it never overwrites files you've already customized).
You do not need to create that directory yourself. Key locations:

- pyEfis config: `~/makerplane/pyefis/config`
- default config file loaded: `~/makerplane/pyefis/config/default.yaml`
- flight-data-recorder logs: `~/makerplane/pyefis/fdr`

## Synthetic Vision (SVS) data paths

The SVS include ([src/pyefis/config/includes/ahrs/svs.yaml](../src/pyefis/config/includes/ahrs/svs.yaml))
ships with SVS enabled and its data paths pointing at the makerplane-data
updater's **standard Pi data root**, `/data/makerplane-data/…` (terrain tiles,
airports/obstacles/water/highways sqlite DBs). On a Pi that path is populated
automatically; on a laptop it does not exist, and `/data` is not writable
without root.

You do **not** need that data to run pyEfis. Your options:

1. **Ignore it** — without the `svs` extra or a GPU, SVS annunciates
   `SVS UNAVAIL` and the rest of the EFIS runs normally.
2. **Point the paths at your own data root** — edit the `svs:` block in your
   `~/makerplane/pyefis/config` copy of `svs.yaml` and change `tile_path`,
   `nasr_db_path`, etc. to a directory you control (e.g. under
   `~/makerplane/pyefis/data/…`).
3. **Turn SVS off** — set `enabled: false` in that `svs:` block.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: No module named 'PyQt6'` | The `qt` extra isn't installed. `pip install -e '.[qt]'`. |
| Runs, but attitude view says `SVS UNAVAIL` | Expected without a usable GPU or the `svs` extra. Not an error. |
| SVS/terrain errors about `/data/makerplane-data/...` | That data root doesn't exist on a laptop — see the SVS section above (point the paths elsewhere or set `enabled: false`). |
| No instruments show live values | FIX-Gateway isn't running, or pyEfis isn't pointed at it. Start FIX-Gateway (step 4). |
