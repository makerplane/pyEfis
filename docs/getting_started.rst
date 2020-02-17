===============
Getting Started
===============

pyEfis is an Electronic Flight Information System written in Python.

It was created for use in the MakerPlane Open Source Aircraft Project.

It does not have any method of reading flight information directly from the
hardware but instead uses FIX Gateway as it's source of information.  FIX
Gateway is a plugin based program that allows different types of flight
information systems to communicate to one another.  pyEfis contains a client
to FIX Gateway and so has access to all the flight data that FIX Gateway
is configured for.

-------------------
Installation
-------------------

Right now the only supported operating system for pyEfis is Linux.  This is
to keep the maintenance effor to a minimum during these early stages of
development.

pyEfis runs on Python versions 3.x so be sure and install the 3.x versions of
all of these dependencies.

pyEfis has several dependencies.  The primary one is PyQt.  Installation
instructions can be found here...

https://www.riverbankcomputing.com/static/Docs/PyQt5/installation.html

On Deban based distributions apt should work.

``$ sudo apt install python3-pyqt5``

You will need pip3 to be installed for the rest of these dependencies.  See
https://packaging.python.org/tutorials/installing-packages/ for information on
installing pip and it's associated tools.  On Debian based distributions you
should be able to simply run...

``$ sudo apt install python3-pip``

FIX-Gateway is the backend data gathering application.  Currently the best
way to install FIX-Gateway is to download the current archive from the
GitHub repository.

``$ wget https://github.com/makerplane/FIX-Gateway/archive/master.zip -O fixgw.zip``

``$ unzip fixgw.zip``


This will create a directory on your machine called 'FIX-Gateway-master'

You can also clone the repository if you have git installed and would like to
have the git repository installed locally.

``$ git clone https://github.com/makerplane/FIX-Gateway.git``

This will create a directory on your machine called 'FIX-Gateway'

Next you'll change into the directory that was created by whichever method that you chose
and run the setup utility to install the software.


``$ cd FIX-Gateway-master``
``$ sudo python3 setup.py install```

Now you can run FIX-Gateway with the following command.

``$ fixgw``

It may complain about some missing modules but it should still start up.  To verify
that it is running correctly you can use the installed client program.

``$ fixgwc``

At the FIX> prompt type `status` and it should show information about the state
of the FIX-Gateway service.  You can use the client to read and write data in
the data base to change what pyEfis is displaying.  See the FIX-Gateway
documentation on the GitHub repository for detailed information on how to use
FIX-Gateway.

https://github.com/makerplane/FIX-Gateway

Next we need to install pyAvTools.  This is a Python package which contains
aviation related tools and libraries.

The installation is similar to FIX-Gateway and can be done by downloading an
archive of the repository of cloning the repository.  We'll just show the
archive method.


``$ wget https://github.com/makerplane/pyAvTools/archive/master.zip -O pyavtools.zip``

``$ unzip pyavtools.zip``

``$ cd pyAvTools-master``

``$ sudo python3 setup.py install``

Now we can finally install pyEfis itself.

``$ wget https://github.com/makerplane/pyEfis/archive/master.zip -O pyefis.zip``

``$ unzip pyefis.zip``

``$ cd pyEfis-master``

.. Once pyEfis has a proper setup system we need to change this
   $ sudo python3 setup.py install

To run pyEfis simply execute the Python script...

``$ ./pyEfis.py``

If all has worked you should get an EFIS displayed on your desktop.
