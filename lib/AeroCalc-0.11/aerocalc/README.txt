AeroCalc is a pure python package with modules that perform various aeronautical 
engineering related calculations.

This package contains the following modules:

airspeed         airspeed conversions and calculations.  Provides interactive
                 mode when run directly, e.g. 'python airspeed.py'.

default_units    defines default units to be used by all modules.  May be 
                 overridden by a user units file.

ssec             Currently contains functions to calculate true airspeed given 
                 GPS ground speed and track data from multiple runs on various 
                 tracks.  Will eventually also contain various calculations 
                 related to static source error correction.

std_atm          standard atmosphere parametres and calculations.

unit_conversion  convert various aeronautical parametres between commonly
                 used units.

val_input        validates user input when in interactive mode.