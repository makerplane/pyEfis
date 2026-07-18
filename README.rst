|Coverage Badge| |Website snapcraft.io| |candidate| |beta| |edge|

.. |Coverage Badge| image:: https://raw.githubusercontent.com/makerplane/pyEfis/python-coverage-comment-action-data/badge.svg
   :target: https://htmlpreview.github.io/?https://github.com/makerplane/pyEfis/blob/python-coverage-comment-action-data/htmlcov/index.html

.. |Website snapcraft.io| image:: https://snapcraft.io/pyefis/badge.svg
   :target: https://snapcraft.io/pyefis

.. |candidate| image:: https://img.shields.io/snapcraft/v/pyefis/latest/candidate?label=candidate&color=d5d90d
   :target: https://snapcraft.io/pyefis

.. |beta| image:: https://img.shields.io/snapcraft/v/pyefis/latest/beta?label=beta&color=d9870d
   :target: https://snapcraft.io/pyefis

.. |edge| image:: https://img.shields.io/snapcraft/v/pyefis/latest/edge?label=edge&color=d90d0d
   :target: https://snapcraft.io/pyefis


pyEfis
==================

Getting Started
---------------

We have recently started distributing pyEFIS and FiX Gateway as snaps on snapcraft.io.
If you are only interested in installing and using pyEFIS follow the installation guide here: https://github.com/makerplane/pyEfis/blob/master/INSTALLING.md
If you are interested in modifying pyEFIS see below.
For more detailed documentation see: https://github.com/makerplane/Documentation

It is recommende that you work in a virtual environment. To use the global interpreter, skip the below step.

::

    $ make venv
    $ source venv/bin/activate

The second command, the activation of the virtual environment, needs to be performed every time you start a new console session.

Next, install the dependencies. ``make init`` installs the development tooling
(pytest, flake8, black, ...); the runtime GUI and 3D dependencies live in
optional extras, so install those too:

::

    $ make init
    $ pip install -e '.[qt,svs]'

The ``qt`` extra (PyQt6) is **required** -- pyEfis will not start without it. The
``svs`` extra (numpy, PyOpenGL) is optional and only needed to render Synthetic
Vision terrain; without it pyEfis runs normally and the attitude view shows
``SVS UNAVAIL``. See `docs/running_from_source.md <docs/running_from_source.md>`_
for the full walkthrough.

Install `FIX-Gateway <https://github.com/makerplane/FIX-Gateway>`_  as documented in its readme.

Now, you can run pyEfis:

::

    $ python pyEfis.py

Controls
--------

This is an Electronic Flight Information System written in Python.

It was created for use in the MakerPlane Open Source Aircraft Project.

It does not have any method of reading flight information directly from the
hardware but instead uses FIX Gateway as it's source of information.  FIX
Gateway is a plugin based program that allows different types of flight
information systems to communicate to one another.  pyEfis contains a client
to FIX Gateway and so has access to all the flight data that FIX Gateway
is configured for.

Controls

'[' and ']' Keys changes the Altimeter Setting

'm' Changes Airspeed mode from IAS , TAS, and GS

'a' and 's' select the different screens.

Virtual VFR
-----------------------------

In order to take advantage of virtual
VFR chart object rendering, download the latest FAA CIFP file from here:
https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/cifp/download/

Extract the FAACIFP18 file into the pyEfis/CIFP directory. Make note of the FAA
disclaimers also in the zip file.

Create an index file:
'''
./MakeCIFPIndex.py CIFP/FAACIFP18
'''

This creates an index.bin file in CIFP directory

Update the config file [Screen.PFD] section dbpath and indexpath
with the path names of the FAACIFP18 and index.bin files respectively.

Synthetic Vision (SVS)
-----------------------------

The attitude / Virtual-VFR widget can render a GL-accelerated **Synthetic
Vision** view: a perspective terrain picture with water, major roads,
obstacles, and airports/runways drawn in 3D over the live attitude.

* **Terrain** — elevation-shaded relief from SRTM / Copernicus GLO-30 tiles,
  drawn as a forward polar fan with distance-based level of detail.
* **Water** — coastlines, lakes, and reservoirs (OpenStreetMap, ODbL).
* **Obstacles** — FAA DOF towers and antennas as vertical poles, colour-coded
  by lighting and conflict with the aircraft altitude.
* **Airports & runways** — runway quads with FAA surface markings (threshold
  bars, centreline, designators, aiming point, TDZ) and identifier flags.
* **Major roads** — OSM motorway / trunk overlays.

Terrain and the chart databases are supplied by the companion
`makerplane-data <https://github.com/makerplane/makerplane-data>`_
navigation-data system — an over-the-air / USB updater that keeps signed
terrain, airport, obstacle, water, and road packs current — or by
user-supplied local files. A boot-time **Data Status** screen and a subtle
**DATA** annunciator on the PFD report navigation-data currency, powered by the
same updater.

SVS is **off by default**. Enable it by adding a nested ``svs:`` block with
``enabled: true`` to the ``virtual_vfr`` instrument options, pointing at the
terrain tile directory and the sqlite databases. See the commented example in
``src/pyefis/config/includes/ahrs/virtual_vfr.yaml``.

Hardware
-----------------------------

pyEfis runs on a Raspberry Pi or on standard desktop Linux. The reference
flight unit is a **Raspberry Pi 5 (8 GB)** running Raspberry Pi OS
(Debian 13 "trixie"), Python 3.13.

Minimum (EFIS without SVS)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* A Raspberry Pi 4/5 — or any x86-64 Linux box — that can run Python 3.10+
  and Qt 6.
* The core instruments (PFD, gauges, HSI, …) are drawn on the CPU with
  QPainter, so an accelerated GPU is **not** required when Synthetic Vision is
  disabled.
* A microSD card large enough for the OS (32 GB+).

Suggested (full SVS unit)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Raspberry Pi 5, 8 GB** — headroom for the GL terrain renderer and the
  navigation-data store.
* **A supported GPU is required for Synthetic Vision.** SVS is GL-rendered
  (OpenGL ES 3.0+ / desktop GL 3.0); on the Pi 5 the built-in VideoCore VII
  (Mesa V3D driver, ``eglfs``) provides this out of the box. The recent
  draw-path optimisations lowered the per-frame cost but did **not** remove the
  GL requirement — so a capable GPU matters only when SVS is enabled. If SVS is
  enabled on a machine with no usable GPU/driver, it disables itself after the
  GL renderer fails to initialise and the attitude display reverts to the
  normal sky/ground view with an ``SVS UNAVAIL`` annunciation — the EFIS keeps
  running, just without synthetic vision. (A system with only *software* GL will
  render SVS correctly but slowly.)
* **Storage — an M.2 HAT + NVMe SSD is strongly preferred.** The
  navigation-data packs are large: terrain regions run tens of GB and a full
  North-America terrain set is ~90 GB. Either use a large, high-quality
  (A2-rated) microSD card, or — better — add an **M.2 HAT with an NVMe SSD**
  for the data store and keep the OS on the microSD. The reference unit boots
  from a 64 GB microSD and stores data on a ~500 GB NVMe SSD mounted at
  ``/data`` (the ``makerplane-data`` default data root).

Testing
------------
To run all of the automated tests and code covreage.

::

    $ make test


Distribution
------------

To create a Python wheel for distribution, there is a make target. The wheel will be created in the ``dist/`` directory.

::

    $ make wheel

After installing the wheel via pip, the user can run pyEfis from the command line. Please mind that the FIX-Gateway server needs to be up and running.

::

    $ pyefis

All CLI options work as defined.

::
    
    $ pyefis -h
    usage: pyefis [-h] [-m {test,normal}] [--debug] [--verbose] [--config-file CONFIG_FILE] [--log-config LOG_CONFIG]

    pyEfis

    optional arguments:
      -h, --help            show this help message and exit
      -m {test,normal}, --mode {test,normal}
                              Run pyEFIS in specific mode
      --debug               Run in debug mode
      --verbose, -v         Run in verbose mode
      --config-file CONFIG_FILE
                              Alternate configuration file
      --log-config LOG_CONFIG
                              Alternate logger configuration file


Cleanup
------------

To cleanup all of the test files, virtual environemnt and other changes made by the makefile. This is a destructive command, you may want to review what it does before running it.

::

    $ make clean


Licensing & Patents (this fork)
-------------------------------

pyEfis is GPL-2.0-or-later (Phil Birkelbach and contributors); all work on
this fork's branches (SVS, moving map, instrument registry/editor) is
contributed under the same license, which carries the GPL's implied patent
license and, at v3, an express patent grant. The extended architecture
around pyEfis (configurator, data currency, provider model) is publicly
disclosed as prior art in the makerplane-data repository
(docs/AC-DP-001-architecture-disclosure.md); the intent is that all of it
remain permanently free to implement.
