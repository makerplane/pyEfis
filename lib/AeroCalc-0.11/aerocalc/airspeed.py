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
# version 0.27, 16 May 2007
#
# Version History:
# vers     date      Notes
# 0.21   10 June 06  Started to add interactive mode
# 0.22   10 July 06  Error correction in some default units
# 0.23   07 Jan 07   Added several more interactive functions
# 0.24   05 May 07   Reworked to use default units from default_units module.
# 0.25   06 May 07   Added several more interactive functions
# 0.26   12 May 07   Reworked the interactive mode to move common idioms to
#                    functions
# 0.27   16 May 07   Reworked to respect default units, to stay open after
#                    running, and to save results between functions.
# #############################################################################
#
# To Do:  1. Add functions:
#
#         2. Extend the following functions to work at M > 1 and CAS > 661.48:
#             dp_over_p2mach
#             dp2eas
#             dp2tas
#             eas2dp
#             tas2dp
#
#         3. Test the following functions:
#             cas2eas
#             eas2cas
#             cas_mach2alt
#             cas_alt2mach
#             mach_alt2cas
#             mach2tas # errors?
#             tas2mach # errors?
#
#         4. Add examples to all functions.
#
#         5. Add tests for all functions.
#
#         6. Check superconic versions of cas to mach and mach to cas equations
#            from TPS notes
#
#         7. Done.
#
#         8. Done.
#
#
# Done    7. Rework the interactive functions to respect the default units.
#
#         8. Rework interactive functions to share data between runs.

# #############################################################################
# % coverage.py -r -m ../airspeed.py
# Name          Stmts   Exec  Cover   Missing
# -------------------------------------------
# ../airspeed     422     52    12%   98-109, 112, 115-117, 122-127, 156-198, 207, 217, 221, 223, 226, 231-278, 310, 315-316, 346-365, 370-404, 435-436, 440-444, 479-521, 530-600, 603-634, 660-664, 674-704, 707-722, 750-889, 891-892, 903-904, 931, 945-989, 998-1050, 1053-1209, 1231-1299, 1360-1362, 1368-1389, 1395, 1398, 1400-1401, 1411-1503, 1513-1530, 1562-1604
"""
Perform various air speed conversions.

Convert between Indicated Air Speed (IAS), Calibrated Air Speed (CAS),
Equivalent Air Speed (EAS), True Air Speed (TAS) and mach number.

Convert between pitot static system pressures and air speed.

Provide interactive airspeed conversions when script is run directly, e.g.
'python airspeed.py'.

"""

import math as M
from . import std_atm as SA

try:
    from default_units import *
except ImportError:
    default_area_units = 'ft**2'
    default_power_units = 'hp'
    default_speed_units = 'kt'
    default_temp_units = 'C'
    default_weight_units = 'lb'
    default_press_units = 'in HG'
    default_density_units = 'lb/ft**3'
    default_length_units = 'ft'
    default_alt_units = default_length_units
    default_avgas_units = 'lb'

from . import unit_conversion as U
from . import val_input as VI

Rho0 = SA.Rho0  # Density at sea level, kg/m**3
P0 = 101325.0  # Pressure at sea level, pa

# speed of sound from http://www.edwards.af.mil/sharing/tech_pubs/Handbook-10%20March02.pdf

A0 = 340.2941  # speed of sound at sea level, std day, m/s

# F calculated by manipulating NASA RP 1046 pg 17
# F is used in some of the supersonic solution equations.

F = (1.25 ** 2.5 * (2.4 ** 2.) ** 2.5) * 1.2

# #############################################################################
#
# delta pressure to speed
#
#    delta pressure to CAS
#
#    delta pressure and altitude to EAS
#
#    delta pressure, altitude and temperature to TAS
#
# #############################################################################


def _dp2speed(
    dp,
    Pref,
    Rhoref,
    press_units=default_press_units,
    speed_units=default_speed_units,
    ):

    dp = U.press_conv(dp, from_units=press_units, to_units='pa')
    speed = M.sqrt(((7. * Pref) * (1. / Rhoref)) * ((dp / Pref + 1.)
                    ** (2. / 7.) - 1.))

    # check to confirm the speed is less than 661.48 kt

    speed_kt = U.speed_conv(speed, from_units='m/s', to_units='kt')
    if speed_kt > 661.48:
        raise ValueError(
        'The function _dp2speed only works if the speed is less than or equal to 661.48 kt')
    speed = U.speed_conv(speed, from_units='m/s', to_units=speed_units)

    return speed


def dp2cas(dp, press_units=default_press_units,
           speed_units=default_speed_units):
    """
    Return the CAS for a given differential pressure (the difference
    between the pitot and static pressures).

    The pressure units may be in inches of HG, mm of HG, psi, lb/ft^2,
    hpa and mb.  The units are specified as: 'in HG', 'mm HG', 'psi',
    'lb/in**2', 'psf', 'lb/ft**2 'hpa', 'mb' or 'pa'.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    If the units are not specified, the units in default_units.py are used.

    Examples:

    Determine the CAS in kt that is equivalent to a differential pressure
    of 15 in HG:
    >>> dp2cas(15)
    518.96637566127652

    Determine the CAS in mph that is equivalent to a differential pressure
    of 0.2 psi:
    >>> dp2cas(.2, press_units = 'psi', speed_units = 'mph')
    105.88275188221526
    """

    try:

        # subsonic case

        cas = _dp2speed(dp, P0, Rho0, press_units, speed_units)
        return cas
    except ValueError:

        # supersonic case - need to iterate a solution.  Set upper and lower
        # guesses, and iterate until we zero in on a cas that produces the
        # desired differential pressure.

        dp_seek = U.press_conv(dp, from_units=press_units, to_units='pa'
                               )

        low = 340  # initial lower guess, m/s

        # This function works up to approximately 6,600 kt CAS.  The upper
        # limit can be extended by increasing the value of the initial upper
        # guess ("high").

        high = 3400  # initial upper guess, m/s

        # confirm initial low and high are OK:

        dp_low = _super_cas2dp(low)
        if dp_low > dp_seek:
            raise ValueError('Initial lower cas guess is too high.')

        dp_high = _super_cas2dp(high)
        if dp_high < dp_seek:
            raise ValueError('Initial upper cas guess is too low.')

        guess = (low + high) / 2.
        dp_guess = _super_cas2dp(guess)

        # keep iterating until dp is within 0.001% of desired value

        while M.fabs(dp_guess - dp_seek) / dp_seek > 1e-5:
            if dp_guess > dp_seek:
                high = guess
            else:
                low = guess

            guess = (low + high) / 2.
            dp_guess = _super_cas2dp(guess)

    # the supersonic solution is in m/s, so we need to convert to the
    # desired units.

    cas = U.speed_conv(guess, from_units='m/s', to_units=speed_units)

    # Supersonic case.  The subsonic case is returned way up at the top,
    # inside the try statement.

    return cas


def dp2eas(
    dp,
    altitude,
    press_units=default_press_units,
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    ):
    """
    Return the EAS for a given differential pressure (the difference
    between the pitot and static pressures) and altitude.

    The pressure units may be in inches of HG, mm of HG, psi, lb/ft^2,
    hpa and mb.  The units are specified as: 'in HG', 'mm HG', 'psi',
    'lb/in**2', 'psf', 'lb/ft**2 'hpa', 'mb' or 'pa'.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    If the units are not specified, the units in default_units.py are used.

    This first version only works for EAS < 661.48 kt.
    """

    P = SA.alt2press(altitude, alt_units, press_units='pa')

    eas = _dp2speed(dp, P, Rho0, press_units, speed_units)
    return eas


def dp2tas(
    dp,
    altitude,
    temp,
    press_units=default_press_units,
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    temp_units=default_temp_units,
    ):
    """
    Return the TAS for a given differential pressure (the difference
    between the pitot and static pressures) and altitude.

    The pressure units may be in inches of HG, mm of HG, psi, lb/ft^2,
    hpa and mb.  The units are specified as: 'in HG', 'mm HG', 'psi',
    'lb/in**2', 'psf', 'lb/ft**2 'hpa', 'mb' or 'pa'.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    The temperature may be in deg C, F, K or R.

    If the units are not specified, the units in default_units.py are used.

    This first version only works for TAS < 661.48 kt.
    """

    P = SA.alt2press(altitude, alt_units, press_units='pa')

    press_ratio = SA.alt2press_ratio(altitude, alt_units)
    temp_ratio = U.temp_conv(temp, from_units=temp_units, to_units='K')\
         / 288.15
    density_ratio = press_ratio / temp_ratio
    Rho = Rho0 * density_ratio

    tas = _dp2speed(dp, P, Rho, press_units, speed_units)
    return tas


# #############################################################################
#
# speed to delta pressure
#
#    CAS to delta pressure
#
#    EAS and altitude to delta pressure
#
#    TAS, altitude and temperature to delta pressure
#
# #############################################################################


def _speed2dp(
    speed,
    Pref,
    Rhoref,
    press_units=default_press_units,
    speed_units=default_speed_units,
    ):
    """ Return a delta pressure (the difference between the pitot and
    static pressures) for a given speed.  Subsonic equation.
    """

    speed = U.speed_conv(speed, from_units=speed_units, to_units='m/s')
    dp = Pref * (((Rhoref * speed ** 2.) / (7. * Pref) + 1.) ** 3.5
                  - 1.)
    dp = U.press_conv(dp, from_units='pa', to_units=press_units)

    return dp


def _super_cas2dp(mcas):
    """Return the  differential pressure (difference between pitot and static
    pressures) for a given CAS.

    This function only works for speed in m/s, and pressure in pa.

    This function is only intended for CAS > 661.48 kt.
    """

    dp_over_P0 = (F * (mcas / A0) ** 7.) / (7. * (mcas / A0) ** 2. - 1.)\
         ** 2.5 - 1.
    dp = dp_over_P0 * P0

    return dp


def cas2dp(cas, speed_units=default_speed_units,
           press_units=default_press_units):
    """
    Return the differential pressure (difference between pitot and static
    pressures) for a given CAS.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The pressure units may be in inches of HG, mm of HG, psi, lb/ft^2,
    hpa and mb.  The units are specified as: 'in HG', 'mm HG', 'psi',
    'lb/in**2', 'psf', 'lb/ft**2 'hpa', 'mb' or 'pa'.

    If the units are not specified, the units in default_units.py are used.
    """

    # check to confirm the speed is less than 661.48 kt
#   kcas = U.speed_conv(cas, from_units = speed_units, to_units = 'kt')

    mcas = U.speed_conv(cas, from_units=speed_units, to_units='m/s')

#   if kcas > 661.48:

    if mcas > A0:

        # supersonic case

        dp = _super_cas2dp(mcas)
        dp = U.press_conv(dp, from_units='pa', to_units=press_units)
    else:

        # subsonic case

        dp = _speed2dp(cas, P0, Rho0, press_units=press_units,
                       speed_units=speed_units)
    return dp


def eas2dp(
    eas,
    altitude,
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    press_units=default_press_units,
    ):
    """
    Return the differential pressure (difference between pitot and static
    pressures) for a given EAS.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The pressure units may be in inches of HG, mm of HG, psi, lb/ft^2,
    hpa and mb.  The units are specified as: 'in HG', 'mm HG', 'psi',
    'lb/in**2', 'psf', 'lb/ft**2 'hpa', 'mb' or 'pa'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    If the units are not specified, the units in default_units.py are used.

    This first version only works for CAS < 661.48 kt.

    """

    # check to confirm the speed is less than 661.48 kt

    keas = U.speed_conv(eas, from_units=speed_units, to_units='kt')
    if keas > 661.48:
        raise ValueError(
            'The function eas2dp only works if the eas is less than or equal to 661.48 kt')

    P = SA.alt2press(altitude, alt_units=alt_units, press_units='pa')
    dp = _speed2dp(eas, P, Rho0, press_units=press_units,
                   speed_units=speed_units)

    return dp


def tas2dp(
    tas,
    altitude,
    temp,
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    temp_units=default_temp_units,
    press_units=default_press_units,
    ):
    """
    Return the differential pressure (difference between pitot and static
    pressures) for a given TAS.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The pressure units may be in inches of HG, mm of HG, psi, lb/ft^2,
    hpa and mb.  The units are specified as: 'in HG', 'mm HG', 'psi',
    'lb/in**2', 'psf', 'lb/ft**2 'hpa', 'mb' or 'pa'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    The temperature may be in deg C, F, K or R.

    If the units are not specified, the units in default_units.py are used.

    This first version only works for CAS < 661.48 kt.

    """

    # check to confirm the speed is less than 661.48 kt

    ktas = U.speed_conv(tas, from_units=speed_units, to_units='kt')
    if ktas > 661.48:
        raise ValueError(
            'The function tas2dp only works if the tas is less than or equal to 661.48 kt')

    P = SA.alt2press(altitude, alt_units=alt_units, press_units='pa')

    press_ratio = SA.alt2press_ratio(altitude, alt_units)
    temp_ratio = U.temp_conv(temp, from_units=temp_units, to_units='K')\
         / 288.15
    density_ratio = press_ratio / temp_ratio
    Rho = Rho0 * density_ratio
    dp = _speed2dp(tas, P, Rho, press_units=press_units,
                   speed_units=speed_units)

    return dp


def cas2eas(
    cas,
    altitude,
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    ):
    """
    Return the EAS for a given CAS, pressure altitude and temperature.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    If the units are not specified, the units in default_units.py are used.
    """

    dp = cas2dp(cas, speed_units)
    eas = dp2eas(dp, altitude, alt_units=alt_units,
                 speed_units=speed_units)

    return eas


def i_cas2eas(data_items):
    """
    Return the EAS for a given CAS, pressure altitude and temp, with
    interactive input from the user.
    """

    # version that goes interactive, if required

    data_items['cas'] = _get_CAS(data_items)
    cas = data_items['cas']

    data_items['speed_units'] = _get_speed_units(data_items)
    speed_units = data_items['speed_units']

    data_items['altitude'] = _get_alt(data_items)
    altitude = data_items['altitude']

    data_items['alt_units'] = _get_alt_units(data_items)
    alt_units = data_items['alt_units']

    print()
    print('CAS = ', cas, speed_units)
    print('Altitude = ', altitude, alt_units)
    print()

    eas = cas2eas(cas, altitude, speed_units, alt_units)
    data_items['eas'] = eas
    return_string = 'EAS = ' + str(eas) + ' ' + speed_units
    print(return_string)


def cas2tas(
    cas,
    altitude,
    temp='std',
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    temp_units=default_temp_units,
    ):
    """
    Return the TAS for a given CAS, pressure altitude and temperature.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    The temperature may be in deg C, F, K or R. The temperature defaults to std
    temperature if it is not input.

    If the units are not specified, the units in default_units.py are used.

    """

    if temp == 'std':
        temp = SA.alt2temp(altitude, temp_units=temp_units,
                           alt_units=alt_units)

    dp = cas2dp(cas, speed_units)
    tas = dp2tas(
        dp,
        altitude,
        temp,
        speed_units=speed_units,
        alt_units=alt_units,
        temp_units=temp_units,
        )

    return tas


def i_cas2tas(data_items):
    """
    Return the TAS for a given CAS, pressure altitude and temp, with
    interactive input from the user.
    """

    # version that goes interactive, if required

    data_items['cas'] = _get_CAS(data_items)
    cas = data_items['cas']

    data_items['speed_units'] = _get_speed_units(data_items)
    speed_units = data_items['speed_units']

    data_items['altitude'] = _get_alt(data_items)
    altitude = data_items['altitude']

    data_items['alt_units'] = _get_alt_units(data_items)
    alt_units = data_items['alt_units']

    data_items['temp_units'] = _get_temp_units(data_items)
    temp_units = data_items['temp_units']

    data_items['temp'] = _get_temp(data_items)
    temp = data_items['temp']

    print()
    print('CAS = ', cas, speed_units)
    print('Altitude = ', altitude, alt_units)
    print('Temperature = ', temp, 'deg', temp_units)
    print()

    tas = cas2tas(
        cas,
        altitude,
        temp,
        speed_units,
        alt_units,
        temp_units,
        )
    data_items['tas'] = tas
    return_string = 'TAS = ' + str(tas) + ' ' + speed_units
    print(return_string)


def eas2tas(
    eas,
    altitude,
    temp='std',
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    temp_units=default_temp_units,
    ):
    """
    Return the TAS for a given EAS, pressure altitude and temperature.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    The temperature may be in deg C, F, K or R. The temperature defaults to std
    temperature if it is not input.

    If the units are not specified, the units in default_units.py are used.

    """

    if temp == 'std':
        temp = SA.alt2temp(altitude, temp_units=temp_units,
                           alt_units=alt_units)

    dp = eas2dp(eas, altitude, speed_units, alt_units)
    tas = dp2tas(
        dp,
        altitude,
        temp,
        speed_units=speed_units,
        alt_units=alt_units,
        temp_units=temp_units,
        )

    return tas


def i_eas2tas(data_items):
    """
    Return the TAS for a given EAS, pressure altitude and temp, with
    interactive input from the user.
    """

    # version that goes interactive, if required

    data_items['eas'] = _get_EAS(data_items)
    eas = data_items['eas']

    data_items['speed_units'] = _get_speed_units(data_items)
    speed_units = data_items['speed_units']

    data_items['altitude'] = _get_alt(data_items)
    altitude = data_items['altitude']

    data_items['alt_units'] = _get_alt_units(data_items)
    alt_units = data_items['alt_units']

    data_items['temp_units'] = _get_temp_units(data_items)
    temp_units = data_items['temp_units']

    data_items['temp'] = _get_temp(data_items)
    temp = data_items['temp']

    print()
    print('EAS = ', eas, speed_units)
    print('Altitude = ', altitude, alt_units)
    print('Temperature = ', temp, 'deg', temp_units)
    print()

    tas = eas2tas(
        eas,
        altitude,
        temp,
        speed_units,
        alt_units,
        temp_units,
        )
    data_items['tas'] = tas
    return_string = 'TAS = ' + str(tas) + ' ' + speed_units
    print(return_string)


def eas2cas(
    eas,
    altitude,
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    ):
    """
    Return the CAS for a given EAS, pressure altitude and temperature.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    If the units are not specified, the default units in default_units.py are used.

    Examples:

    Determine equivalent Air Speed for 250 kt CAS at 10,000 ft:
    >>> cas2eas(250, 10000)
    248.09577137102258

    Determine equivalent Air Speed for 250 mph CAS at 10,000 ft:
    >>> cas2eas(250, 10000, speed_units = 'mph')
    248.54048288757579
    """

    dp = eas2dp(eas, altitude, speed_units, alt_units)
    cas = dp2cas(dp, speed_units=speed_units)

    return cas


def i_eas2cas(data_items):
    """
    Return the CAS for a given EAS, pressure altitude, with
    interactive input from the user.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    If the units are not specified, the units in default_units.py are used.

    """

    data_items['eas'] = _get_EAS(data_items)
    eas = data_items['eas']

    data_items['speed_units'] = _get_speed_units(data_items)
    speed_units = data_items['speed_units']

    data_items['altitude'] = _get_alt(data_items)
    altitude = data_items['altitude']

    data_items['alt_units'] = _get_alt_units(data_items)
    alt_units = data_items['alt_units']

    print()
    print('EAS = ', eas, speed_units)
    print('Altitude = ', altitude, alt_units)
    print()

    cas = eas2cas(eas, altitude, speed_units, alt_units)
    data_items['cas'] = cas
    return_string = 'CAS = ' + str(cas) + ' ' + speed_units
    print(return_string)


def tas2cas(
    tas,
    altitude,
    temp='std',
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    temp_units=default_temp_units,
    ):
    """
    Return the CAS for a given TAS, pressure altitude and temperature.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    The temperature may be in deg C, F, K or R. The temperature defaults to std
    temperature if it is not input.

    If the units are not specified, the units in default_units.py are used.

    Examples:

    Determine the true Air Speed for 250 kt CAS at 10,000 ft with standard
    temperature:
    >>> cas2tas(250, 10000)
    288.70227231079861

    Determine the true Air Speed for 250 mph CAS at 10,000 ft with standard
    temperature:
    >>> cas2tas(250, 10000, speed_units = 'mph')
    289.21977095514148

    Determine the true Air Speed for 250 mph CAS at 10,000 ft with
    temperature of 0 deg C:
    >>> cas2tas(250, 10000, 0, speed_units = 'mph')
    291.80148048806217

    Determine the true Air Speed for 250 mph CAS at 10,000 ft with
    temperature of 0 deg F:
    >>> cas2tas(250, 10000, 0, speed_units = 'mph', temp_units = 'F')
    282.14588227473797
    """

    if temp == 'std':
        temp = SA.alt2temp(altitude, temp_units=temp_units,
                           alt_units=alt_units)

    dp = tas2dp(
        tas,
        altitude,
        temp,
        speed_units,
        alt_units=alt_units,
        temp_units=temp_units,
        )
    cas = dp2cas(dp, speed_units=speed_units)

    return cas


def i_tas2cas(data_items):
    """
    Return the CAS for a given TAS, pressure altitude and temp, with
    interactive input from the user.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    The temperature may be in deg C, F, K or R. The temperature defaults to std
    temperature if it is not input.

    If the units are not specified, the units in default_units.py are used.

    """

    data_items['tas'] = _get_TAS(data_items)
    tas = data_items['tas']

    data_items['speed_units'] = _get_speed_units(data_items)
    speed_units = data_items['speed_units']

    data_items['altitude'] = _get_alt(data_items)
    altitude = data_items['altitude']

    data_items['alt_units'] = _get_alt_units(data_items)
    alt_units = data_items['alt_units']

    data_items['temp_units'] = _get_temp_units(data_items)
    temp_units = data_items['temp_units']

    data_items['temp'] = _get_temp(data_items)
    temp = data_items['temp']

    print()
    print('TAS = ', tas, speed_units)
    print('Altitude = ', altitude, alt_units)
    print('Temperature = ', temp, 'deg', temp_units)
    print()

    cas = tas2cas(
        tas,
        altitude,
        temp,
        speed_units,
        alt_units,
        temp_units,
        )
    data_items['cas'] = cas
    return_string = 'CAS = ' + str(cas) + ' ' + speed_units
    print(return_string)


def tas2eas(
    tas,
    altitude,
    temp='std',
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    temp_units=default_temp_units,
    ):
    """
    Return the EAS for a given TAS, pressure altitude and temperature.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    The temperature may be in deg C, F, K or R. The temperature defaults to std
    temperature if it is not input.

    If the units are not specified, the units in default_units.py are used.

    """

    if temp == 'std':
        temp = SA.alt2temp(altitude, temp_units=temp_units,
                           alt_units=alt_units)

    dp = tas2dp(
        tas,
        altitude,
        temp,
        speed_units,
        alt_units=alt_units,
        temp_units=temp_units,
        )
    eas = dp2eas(dp, altitude, alt_units=alt_units,
                 speed_units=speed_units)

    return eas


def i_tas2eas(data_items):
    """
    Return the EAS for a given TAS, pressure altitude and temp, with
    interactive input from the user.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    The temperature may be in deg C, F, K or R. The temperature defaults to std
    temperature if it is not input.

    If the units are not specified, the units in default_units.py are used.

    """

    data_items['tas'] = _get_TAS(data_items)
    tas = data_items['tas']

    data_items['speed_units'] = _get_speed_units(data_items)
    speed_units = data_items['speed_units']

    data_items['altitude'] = _get_alt(data_items)
    altitude = data_items['altitude']

    data_items['alt_units'] = _get_alt_units(data_items)
    alt_units = data_items['alt_units']

    data_items['temp_units'] = _get_temp_units(data_items)
    temp_units = data_items['temp_units']

    data_items['temp'] = _get_temp(data_items)
    temp = data_items['temp']

    print()
    print('TAS = ', tas, speed_units)
    print('Altitude = ', altitude, alt_units)
    print('Temperature = ', temp, 'deg', temp_units)
    print()

    eas = tas2eas(
        tas,
        altitude,
        temp,
        speed_units,
        alt_units,
        temp_units,
        )
    data_items['eas'] = eas
    return_string = 'EAS = ' + str(eas) + ' ' + speed_units
    print(return_string)


# #############################################################################
#
# delta p over p to Mach
#
#     and
#
# Mach to delta p over p
#
# #############################################################################


def dp_over_p2mach(dp_over_p):
    """
    Return the mach number for a given delta p over p.

    Mach must be less than or equal to 10.
    """

#   mach = (5*( (dp_over_p + 1)**(2/7.) -1) )**0.5

    mach = M.sqrt(5. * ((dp_over_p + 1.) ** (2. / 7.) - 1.))

    if mach <= 1.:
        return mach
    else:

        # supersonic case - need to iterate a solution.  Set upper and lower
        # guesses, and iterate until we zero in on a mach that produces the
        # desired result.

        dp_over_p_seek = dp_over_p

        low = 1.  # initial lower guess for mach

        # This function works up to Mach 10  The upper limit can be
        # extended by increasing the value of the initial upper guess
        # ("high").

        high = 10  # initial upper guess for mach

        # confirm initial low and high are OK:

        dp_over_p_low = mach2dp_over_p(low)
        if dp_over_p_low > dp_over_p_seek:
            raise ValueError('Initial lower mach guess is too high.')

        dp_over_p_high = mach2dp_over_p(high)
        if dp_over_p_high < dp_over_p_seek:
            raise ValueError('Initial upper mach guess is too low.')

        guess = (low + high) / 2.
        dp_over_p_guess = mach2dp_over_p(guess)

        # keep iterating until dp is within 0.001% of desired value

        while M.fabs(dp_over_p_guess - dp_over_p_seek) / dp_over_p_seek\
             > 1e-5:
            if dp_over_p_guess > dp_over_p_seek:
                high = guess
            else:
                low = guess

            guess = (low + high) / 2.
            dp_over_p_guess = mach2dp_over_p(guess)

    return guess


def mach2dp_over_p(M):
    """
    Return the delta p over p for a given mach number.
    The result is equal to:
    (pitot pressure - static pressure) / static pressure

    Example - determine the delta p over p at mach 0.4:

    >>> mach2dp_over_p(.4)
    0.11655196580975336
    """

    if M <= 1.:
        dp_over_p = (M ** 2. / 5. + 1.) ** 3.5 - 1.
    else:
        dp_over_p = (F * M ** 7.) / (7. * M ** 2. - 1.) ** 2.5 - 1.

    return dp_over_p


# #############################################################################
#
# conversions between cas, mach and altitude
#
# pick any two values, and find the third
#
# #############################################################################


def cas_mach2alt(
    cas,
    mach,
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    ):
    """
    Return the altitude that corresponds to a given CAS and mach.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    If the units are not specified, the units in default_units.py are used.

    """

    dp = cas2dp(cas, speed_units=speed_units, press_units='pa')
    dp_over_p = mach2dp_over_p(mach)
    p = dp / dp_over_p
    altitude = SA.press2alt(p, press_units='pa', alt_units=alt_units)

    return altitude


def i_cas_mach2alt(data_items):
    """
    Return the altitude that corresponds to a given CAS and mach, with an
    interactive interface.
    """

    data_items['cas'] = _get_CAS(data_items)
    cas = data_items['cas']

    data_items['speed_units'] = _get_speed_units(data_items)
    speed_units = data_items['speed_units']

    data_items['mach'] = _get_mach(data_items)
    mach = data_items['mach']

    data_items['alt_units'] = _get_alt_units(data_items)
    alt_units = data_items['alt_units']

    print()
    print('CAS = ', cas, speed_units)
    print('Mach = ', mach)
    print()
#   print 'Desired altitude units are: ', alt_units

    print()

    print(return_string)
    data_items['altitude'] = alt

    return_string = 'Altitude = ' + str(alt) + ' ' + alt_units
    print(return_string)


def cas_alt2mach(
    cas,
    altitude,
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    ):
    """
    Return the mach that corresponds to a given CAS and altitude.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    If the units are not specified, the units in default_units.py are used.

    """

    dp = cas2dp(cas, speed_units=speed_units, press_units='pa')
    p = SA.alt2press(altitude, alt_units=alt_units, press_units='pa')
    dp_over_p = dp / p
    mach = dp_over_p2mach(dp_over_p)

    return mach


def i_cas_alt2mach(data_items):
    """
    Return the mach that corresponds to a given CAS and altitude, using an
    interactive interface.
    """

    data_items['cas'] = _get_CAS(data_items)
    cas = data_items['cas']

    data_items['speed_units'] = _get_speed_units(data_items)
    speed_units = data_items['speed_units']

    data_items['altitude'] = _get_alt(data_items)
    altitude = data_items['altitude']

    data_items['alt_units'] = _get_alt_units(data_items)
    alt_units = data_items['alt_units']

    print()
    print('CAS = ', cas, speed_units)
    print('Altitude = ', altitude, alt_units)
    print('Mach = ', mach)

    mach = cas_alt2mach(cas, altitude, speed_units, alt_units)
    data_items['mach'] = mach
    print('Mach = ', mach)


def _cas_alt2mach2(
    cas,
    altitude,
    speed_units=default_speed_units,
    alt_units=default_alt_units,
    ):
    """
    Alternative, trial variant of cas_alt2mach, using the equations from
    USAF TPS notes.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    If the units are not specified, the units in default_units.py are used.

    """

    PR = SA.alt2press_ratio(altitude, alt_units)
    cas = U.speed_conv(cas, from_units=speed_units, to_units='m/s')

    if cas <= A0:

        # <= 661.48 kt

        mach = M.sqrt(5. * (((1. / PR) * ((1. + 0.2 * (cas / A0) ** 2.)
                       ** 3.5 - 1.) + 1.) ** (2. / 7.) - 1.))
    else:
        raise ValueError('CAS too high.')

    return mach


def mach_alt2cas(
    mach,
    altitude,
    alt_units=default_alt_units,
    speed_units=default_speed_units,
    ):
    """
    Return the calibrated Air Speed that corresponds to a given mach and
    altitude.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    If the units are not specified, the units in default_units.py are used.

    """

    p = SA.alt2press(altitude, alt_units=alt_units, press_units='pa')
    dp_over_p = mach2dp_over_p(mach)
    dp = dp_over_p * p
    cas = dp2cas(dp, press_units='pa', speed_units=speed_units)

    return cas


def i_mach_alt2cas(data_items):
    """
    Return the calibrated Air Speed that corresponds to a given mach and
    altitude, using an interactive interface.
    """

    data_items['mach'] = _get_mach(data_items)
    mach = data_items['mach']

    data_items['altitude'] = _get_alt(data_items)
    altitude = data_items['altitude']

    data_items['alt_units'] = _get_alt_units(data_items)
    alt_units = data_items['alt_units']

    data_items['speed_units'] = _get_speed_units(data_items)
    speed_units = data_items['speed_units']

    print()
    print('Altitude = ', altitude, alt_units)
    print('Mach = ', mach)
    print()
    print(return_string)
    cas = mach_alt2cas(mach, altitude, alt_units, speed_units)
    data_items['cas'] = cas
    return_string = 'CAS = ' + str(cas) + ' ' + speed_units
    print(return_string)


# #############################################################################
#
# Mach and temperature to TAS
#
#     and
#
# TAS and temperature to Mach
#
# #############################################################################


def mach2tas(
    mach,
    temp='std',
    altitude='blank',
    temp_units=default_temp_units,
    alt_units=default_alt_units,
    speed_units=default_speed_units,
    ):
    """
    Return the TAS for a given mach number.  The temperature or altitude
    must also be specified.  If the altitude is specified, the temperature
    is assumed to be standard.  If both the altitude and temperature are
    specified, the altitude input is ignored.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    The temperature may be in deg C, F, K or R. The temperature defaults to std
    temperature if it is not input.

    If the units are not specified, the units in default_units.py are used.

    Examples:

    Determine the TAS in kt at 0.8 mach at a temperature of
    -15 deg C:
    >>> mach2tas(0.8, -15)
    500.87884108468597

    Determine the TAS in kt at 0.8 mach at 30,000 ft, assuming
    standard temperature:
    >>> mach2tas(0.8, altitude = 30000)
    471.45798523415107

    Determine the TAS in mph at 0.8 mach at 5000 m, assuming
    standard temperature:
    >>> mach2tas(0.8, altitude = 5000, alt_units = 'm', speed_units = 'mph')
    573.60326790383715

    Determine the TAS in km/h at 0.4 mach at a temperature of
    300 deg K:
    >>> mach2tas(0.4, 300, temp_units = 'K', speed_units = 'km/h')
    499.99796329569176
    """

    if temp == 'std':
        if altitude != 'blank':
            temp = SA.alt2temp(altitude, temp_units=temp_units,
                               alt_units=alt_units)
        else:
            raise ValueError(
                'At least one of the temperature or altitude must be specified.')

    tas = mach * SA.temp2speed_of_sound(temp, temp_units, speed_units)

    return tas


def i_mach2tas(data_items):
    """
    Return the TAS that corresponds to a given Mach, altitude, and temperature
    using an interactive interface.
    """

    data_items['mach'] = _get_mach(data_items)
    mach = data_items['mach']

    data_items['altitude'] = _get_alt(data_items)
    altitude = data_items['altitude']

    data_items['alt_units'] = _get_alt_units(data_items)
    alt_units = data_items['alt_units']

    data_items['temp_units'] = _get_temp_units(data_items)
    temp_units = data_items['temp_units']

    data_items['temp'] = _get_temp(data_items)
    temp = data_items['temp']

    data_items['speed_units'] = _get_speed_units(data_items)
    speed_units = data_items['speed_units']

    print()
    print('Mach = ', mach)
    print('Altitude = ', altitude, alt_units)
    print('Temperature =', temp, temp_units)
    print()

    tas = mach2tas(
        mach,
        temp,
        altitude,
        temp_units,
        alt_units,
        speed_units,
        )
    data_items['tas'] = tas
    print('TAS = ', tas, speed_units)


def tas2mach(
    tas,
    temp='std',
    altitude='blank',
    temp_units=default_temp_units,
    alt_units=default_alt_units,
    speed_units=default_speed_units,
    ):
    """
    Return the mach number for a given TAS.  The temperature or altitude
    must also be specified.  If the altitude is specified, the temperature
    is assumed to be standard.  If both the altitude and temperature are
    specified, the altitude input is ignored.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The altitude may be in feet ('ft'), metres ('m'), kilometres ('km'),
    statute miles, ('sm') or nautical miles ('nm').

    The temperature may be in deg C, F, K or R. The temperature defaults to std
    temperature if it is not input.

    If the units are not specified, the units in default_units.py are used.

    Examples:

    Determine the mach number for a TAS of 500 kt at a temperature of
    -15 deg C:
    >>> tas2mach(500, -15)
    0.79859632148519943

    Determine the mach number for a TAS of 500 kt at a temperature of
    0 deg F:
    >>> tas2mach(500, 0, temp_units = 'F')
    0.80292788758764277

    Determine the mach number for a TAS of 500 kt at an altitude of
    10,000 ft, assuming standard temperature:
    >>> tas2mach(500, altitude = 10000)
    0.78328945665870209

    Determine the mach number for a TAS of 400 mph at an altitude of
    5000 m, assuming standard temperature:
    >>> tas2mach(400, altitude = 5000, speed_units = 'mph', alt_units = 'm')
    0.55787687746166581
    """

    if temp == 'std':
        if altitude != 'blank':
            temp = SA.alt2temp(altitude, temp_units=temp_units,
                               alt_units=alt_units)
        else:
            raise ValueError('At least one of the temperature or altitude must be specified.')

    mach = tas / SA.temp2speed_of_sound(temp, temp_units, speed_units)

    return mach


def i_tas2mach(data_items):
    """
    Return the mach that corresponds to a given TAS, altitude, and temperature
    using an interactive interface.
    """

    data_items['tas'] = _get_TAS(data_items)
    tas = data_items['tas']

    data_items['speed_units'] = _get_speed_units(data_items)
    speed_units = data_items['speed_units']

    data_items['altitude'] = _get_alt(data_items)
    altitude = data_items['altitude']

    data_items['alt_units'] = _get_alt_units(data_items)
    alt_units = data_items['alt_units']

    data_items['temp_units'] = _get_temp_units(data_items)
    temp_units = data_items['temp_units']

    data_items['temp'] = _get_temp(data_items)
    temp = data_items['temp']

    print()
    print('TAS = ', tas, speed_units)
    print('Altitude = ', altitude, alt_units)
    print('Temperature =', temp, temp_units)
    print()

    mach = tas2mach(
        tas,
        temp,
        altitude,
        temp_units,
        alt_units,
        speed_units,
        )
    data_items['mach'] = mach
    print('Mach = ', mach)


# #############################################################################
#
# Ram temperature rise calculations
#
#     Mach and indicated temperature to ambient temperature
#
#         and
#
#     TAS and indicated temperature to ambient temperature
#
# #############################################################################


def mach2temp(
    mach,
    indicated_temp,
    recovery_factor,
    temp_units=default_temp_units,
    ):
    """
    Return the ambient temp, given the mach number, indicated
    temperature and the temperature probe's recovery factor.

    The temperature may be in deg C, F, K or R.

    If the units are not specified, the units in default_units.py are used.


    Examples:

    Determine the ambient temperature with an indicated temperature of
    -20 deg C at mach 0.6 with a probe recovery factor of 0.8:

    >>> mach2temp(0.6, -20, 0.8)
    -33.787291981845698

    Determine the ambient temperature with an indicated temperature of
    75 deg F at mach 0.3 with a probe recovery factor of 0.9:

    >>> mach2temp(0.3, 75, 0.9, temp_units = 'F')
    66.476427868529839
    """

    indicated_temp = U.temp_conv(indicated_temp, from_units=temp_units,
                                 to_units='K')
    ambient_temp = indicated_temp / (1. + (0.2 * recovery_factor) * mach
             ** 2.)

    ambient_temp = U.temp_conv(ambient_temp, from_units='K',
                               to_units=temp_units)

    return ambient_temp


def tas2temp(
    tas,
    indicated_temp,
    recovery_factor,
    speed_units=default_speed_units,
    temp_units=default_temp_units,
    ):
    """
    Return the ambient temp, given the TAS, indicated temperature
    and the temperature probe's recovery factor.

    The speed units may be 'kt', 'mph', 'km/h', 'm/s' and 'ft/s'.

    The temperature may be in deg C, F, K or R. The temperature defaults to std
    temperature if it is not input.

    If the units are not specified, the units in default_units.py are used.

    """

    indicated_temp = U.temp_conv(indicated_temp, from_units=temp_units,
                                 to_units='K')
    tas = U.speed_conv(tas, from_units=speed_units, to_units='kt')

    # value 7592.4732909142658 was adjusted to make the result equal that
    # obtained using mach2temp

    ambient_temp = indicated_temp - (recovery_factor * tas ** 2.)\
         / 7592.4732909142658

    ambient_temp = U.temp_conv(ambient_temp, from_units='K',
                               to_units=temp_units)

    return ambient_temp


# #############################################################################
#
# Interactive mode
#
#     Private functions for interactive user interface
#
# #############################################################################


def _get_alt(data_items): #pragma: no cover
    try:
        prompt = 'Altitude = [' + str(data_items['altitude']) + '] '
        value = VI.get_input2(prompt,
                              conditions_any=['ERROR - Altitude must be a number.  Commas are not allowed.'
                              , 'type(float(X)) == float', 'X == ""'])
        if value != '':
            data_items['altitude'] = float(value)
    except KeyError:

        prompt = 'Altitude = '
        data_items['altitude'] = float(VI.get_input2('Altitude = ',
                conditions_any=['ERROR - Altitude must be a number.  Commas are not allowed.'
                , 'type(float(X)) == float', 'X == ""']))
    return data_items['altitude']


def _get_alt_units(data_items): #pragma: no cover

    if data_items['alt_units'] == 'ft':
        prompt = 'altitude units = [ft], m, km, sm, nm: '
    elif data_items['alt_units'] == 'm':
        prompt = 'altitude units = [m], ft, km, sm, nm: '
    elif data_items['alt_units'] == 'km':
        prompt = 'altitude units = [km], ft, m, sm, nm: '
    elif data_items['alt_units'] == 'sm':
        prompt = 'altitude units = [sm], ft, m, km, nm: '
    elif data_items['alt_units'] == 'nm':
        prompt = 'altitude units = [nm], ft, m, km, sm: '

    alt_units = VI.get_input2(prompt, conditions_any=[
        'ERROR - altitude units must be one of "ft", "m", "km", "sm" or "nm".'
            ,
        'X == "ft"',
        'X =="m"',
        'X == "km"',
        'X == "sm"',
        'X == "nm"',
        'X == ""',
        ])
    if alt_units != '':
        print('Alt units not blank')
        data_items['alt_units'] = alt_units
    return data_items['alt_units']


def _get_CAS(data_items): #pragma: no cover
    try:
        prompt = 'CAS = [' + str(data_items['cas']) + '] '
        value = VI.get_input2(prompt,
                              conditions_any=['ERROR - CAS must be a positive number.'
                              , 'float(X) >= 0', 'X == ""'])
        if value != '':
            data_items['cas'] = float(value)
    except KeyError:
        prompt = 'CAS = '
        data_items['cas'] = float(VI.get_input2(prompt,
                                  conditions_any=['ERROR - CAS must be a positive number.'
                                  , 'float(X) >= 0']))

    return data_items['cas']


def _get_EAS(data_items): #pragma: no cover
    try:
        prompt = 'EAS = [' + str(data_items['eas']) + '] '
        value = VI.get_input2(prompt,
                              conditions_any=['ERROR - EAS must be a positive number.'
                              , 'float(X) >= 0', 'X == ""'])
        if value != '':
            data_items['eas'] = float(value)
    except KeyError:
        prompt = 'EAS = '
        data_items['eas'] = float(VI.get_input2(prompt,
                                  conditions_any=['ERROR - EAS must be a positive number.'
                                  , 'float(X) >= 0']))

    return data_items['eas']


def _get_TAS(data_items): #pragma: no cover
    try:
        prompt = 'TAS = [' + str(data_items['tas']) + '] '
        value = VI.get_input2(prompt,
                              conditions_any=['ERROR - TAS must be a positive number.'
                              , 'float(X) >= 0', 'X == ""'])
        if value != '':
            data_items['tas'] = float(value)
    except KeyError:
        prompt = 'TAS = '
        data_items['tas'] = float(VI.get_input2(prompt,
                                  conditions_any=['ERROR - TAS must be a positive number.'
                                  , 'float(X) >= 0']))

    return data_items['tas']


def _get_speed_units(data_items): #pragma: no cover
    if data_items['speed_units'] == 'kt':
        prompt = 'speed units = [kt], mph, km/h, m/s, ft/s: '
    elif data_items['speed_units'] == 'mph':
        prompt = 'speed units = [mph], kt, km/h, m/s, ft/s: '
    elif data_items['speed_units'] == 'km/h':
        prompt = 'speed units = [km/h], kt, mph, m/s, ft/s: '
    elif data_items['speed_units'] == 'm/s':
        prompt = 'speed units = [m/s], kt, mph, km/h, ft/s: '
    elif data_items['speed_units'] == 'mph':
        prompt = 'speed units = [ft/s], kt, mph, km/h, m/s: '

    spd_units = VI.get_input2(prompt, conditions_any=[
        'ERROR - speed units must be one of "kt", "mph", "km/h", "m/s" or "ft/s".'
            ,
        'X == "kt"',
        'X =="mph"',
        'X == "km/h"',
        'X == "m/s"',
        'X == "ft/s"',
        'X == ""',
        ])
    if spd_units != '':
        data_items['speed_units'] = spd_units
    return data_items['speed_units']


def _get_mach(data_items): #pragma: no cover
    try:
        prompt = 'Mach = [' + str(data_items['mach']) + '] '
        value = VI.get_input2(prompt,
                              conditions_any=['ERROR - Mach must be a positive number.'
                              , 'float(X) >= 0', 'X == ""'])
        if value != '':
            data_items['mach'] = float(value)
    except KeyError:
        prompt = 'Mach = '
        data_items['mach'] = float(VI.get_input2(prompt,
                                   conditions_any=['ERROR - Mach must be a positive number.'
                                   , 'float(X) >= 0']))

    return data_items['mach']


def _get_temp(data_items): #pragma: no cover
    try:
        prompt = 'Temperature = [' + str(data_items['temp']) + '] '
        value = VI.get_input2(prompt,
                              conditions_any=['ERROR - Temperature must be a number, or S for std temperature.'
                              , 'X =="S"', 'X == "s"', 'X == ""',
                              'type(float(X)) == float'])
        if value.upper() == 'S':
            data_items['temp'] = SA.alt2temp(data_items['altitude'],
                    alt_units=data_items['alt_units'],
                    temp_units=data_items['temp_units'])
        elif value != '':
            data_items['temp'] = value
    except KeyError:
        prompt = 'Temperature = [std] '
        value = VI.get_input2(prompt,
                              conditions_any=['ERROR - Temperature must be a number, or S for std temperature.'
                              , 'X =="S"', 'X == "s"', 'X == ""',
                              'type(float(X)) == float'])
        if value == 'S' or value == 's' or value == '':
            data_items['temp'] = SA.alt2temp(data_items['altitude'],
                    alt_units=data_items['alt_units'],
                    temp_units=data_items['temp_units'])
        else:
            data_items['temp'] = value

    return float(data_items['temp'])


def _get_temp_units(data_items): #pragma: no cover
    if data_items['temp_units'] == 'C':
        prompt = 'Temperature units = [C], F, K, R: '
    elif data_items['temp_units'] == 'F':
        prompt = 'Temperature units = [F], C, K, R: '
    elif data_items['temp_units'] == 'K':
        prompt = 'Temperature units = [K], C, F, R: '
    elif data_items['temp_units'] == 'R':
        prompt = 'Temperature units = [R], C, F, K: '

    temp_units = VI.get_input2(prompt, conditions_any=[
        'ERROR - temperature units must be one of "C", "F", "K", or "R".'
            ,
        'X.upper() == "C"',
        'X.upper() == "F"',
        'X.upper() == "K"',
        'X.upper() == "R"',
        'X == ""',
        ]).upper()
    if temp_units != '':
        data_items['temp_units'] = temp_units
    return data_items['temp_units']


def _interactive_mode(): #pragma: no cover
    """
    Provide interactive interface for selected functions.
    """

    data_items = {}
    data_items['speed_units'] = default_speed_units
    data_items['alt_units'] = default_alt_units
    data_items['temp_units'] = default_temp_units

    _interactive_interface(data_items)


def _interactive_interface(data_items): #pragma: no cover
    """Provide interactive interface to screen.
    """

    func_list = [
        ['i_cas2eas(data_items)', 'CAS to EAS'],
        ['i_cas2tas(data_items)', 'CAS to TAS'],
        ['i_eas2cas(data_items)', 'EAS to CAS'],
        ['i_eas2tas(data_items)', 'EAS to TAS'],
        ['i_tas2cas(data_items)', 'TAS to CAS'],
        ['i_tas2eas(data_items)', 'TAS to EAS'],
        ['i_cas_alt2mach(data_items)', 'CAS and Altitude to Mach'],
        ['i_cas_mach2alt(data_items)', 'CAS and Mach to Altitude'],
        ['i_mach_alt2cas(data_items)', 'Mach and Altitude to CAS'],
        ['i_tas2mach(data_items)',
         'TAS, Altitude and Temperature to Mach'],
        ['i_mach2tas(data_items)',
         'Mach, Altitude and Temperature to TAS'],
        ]

    count = 1
    print('The following functions are available:')
    for func in func_list:
        if count < 10:
            print(' ', count, '-', func[1])
        else:
            print('', count, '-', func[1])
        count += 1
    print('  Q - Quit')


    item = VI.get_input2('Select a function to run by number: ',
                         conditions_any=['You must enter an integer between 1 and '
                          + str(len(func_list)) + ', or "Q"',
                         '0 < int(X) <= ' + str(len(func_list)),
                         'X == "Q"', 'X == "q"'])
    if item.upper() == 'Q':
        return
    else:
        item = int(item)
    print()
    func_list_num = item - 1
    eval(func_list[func_list_num][0])
    prompt = '\nDo another calculation [Y/n]'
    input_data = raw_input(prompt)
    if input_data == '' or input_data == 'Y' or input_data == 'y':
        print('\n')
        _interactive_interface(data_items)
    else:
        sys.exit()


if __name__ == '__main__':  #pragma: no cover

    # run doctest to check the validity of the examples in the doc strings.

    import doctest
    import sys
    doctest.testmod(sys.modules[__name__])

    # run the interactive interface

    _interactive_mode()
