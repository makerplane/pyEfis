#!/usr/bin/python
# -*- coding: utf-8 -*-
# #############################################################################
# Copyright (c) 2008, Kevin Horton
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# *
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * The name of Kevin Horton may not be used to endorse or promote products
#       derived from this software without specific prior written permission.
# *
# THIS SOFTWARE IS PROVIDED BY KEVIN HORTON ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
# EVENT SHALL KEVIN HORTON BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# #############################################################################
#
# version 0.11, 25 Apr 2008
#
# Version History:
# vers     date      Notes
# 0.10   17 Mar 08   Initial version.
#
# 0.11   25 Apr 08   Added ssec module (mostly empty yet)
# #############################################################################
#
# Distribution Notes
#
# HTML docs are created with epydoc, via
# "epydoc --no-private -n AeroCalc -u 'http://www.kilohotel.com/python/aerocalc/' aerocalc"
#
# Generate distribution - "python setup.py sdist"
#
# #############################################################################

"""Various aeronautical engineering calculations

This package contains the following modules:

airspeed  -       airspeed conversions and calculations.  Provides interactive
                  mode when run directly, e.g. 'python airspeed.py'
default_units -   defines default units to be used by all modules.  May be 
                  overridden by a user units file.
ssec -            static source error correction calculations
std_atm -         standard atmosphere parametres and calculations
unit_conversion - convert various aeronautical parametres between commonly
                  used units
val_input -       validates user input when in interactive mode

Author: Kevin Horton
E-mail: kevin01 -at- kilohotel.com
"""

VERSION = '0.11'

