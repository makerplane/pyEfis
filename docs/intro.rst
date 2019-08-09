============
Introduction
============

This is an Electronic Flight Information System written in Python.

It was created for use in the MakerPlane Open Source Aircraft Project.

pyEfis uses PyQt as the primary windowing environment.

It does not have any method of reading flight information directly from the
hardware but instead uses FIX Gateway as it's source of information.  FIX
Gateway is a plugin based program that allows various types of flight
information systems to communicate to one another.  pyEfis contains a client
to FIX Gateway and so has access to all the flight data that FIX Gateway
is configured for.
