|Website snapcraft.io|

.. |Website snapcraft.io| image:: https://snapcraft.io/pyefis/badge.svg
   :target: ihttps://snapcraft.io/pyefis

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

Next, you install all dependencies.

::

    $ make init

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

