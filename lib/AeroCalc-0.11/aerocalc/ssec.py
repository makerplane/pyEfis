#!/usr/bin/env python
# encoding: utf-8

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
# version 0.10, 25 Apr 2008
#
# Version History:
# vers     date     Notes
# 0.10   25 Apr 08  First public release. 
# #############################################################################

"""
Various functions related to static source error correction.
"""

import airspeed as A
import math as M
import std_atm as SA
import unit_conversion as U

##############################################################################
#
# TAS from GPS data.
#
##############################################################################
def gps2tas(GS, TK, verbose = 0):
    """
    Returns true airspeed, given GPS groundspeed and track on at least
    three legs (four legs preferred).  Uses the method developed by Doug
    Gray - http://www.kilohotel.com/rv8/rvlinks/doug_gray/TAS_FNL4.pdf
    
    GS and TK are lists of ground speed and track data.
    
    Three legs:
        If verbose = 0, then only TAS is returned.
        If verbose = 1, then TAS, wind speed and direction are returned.
        If verbose = 2, then TAS, wind speed and direction and the heading
        for each leg are returned.  The wind speed and direction is 
        returned as a tuple, and the headings are returned as a tuple

        
    Four legs:
        Data from only three legs is sufficient to calculate TAS.  If data
        four legs is entered, four different calculations are conducted,
        using a different mix of three data points for each calculation.
        If the data quality is high, the TAS and wind for all four 
        calculations will be similar.  The standard deviation on the TAS is
        calculated - good quality data will have a standard deviation of
        less than 1 kt.
        
        If verbose = 0, then only TAS is returned.
        If verbose = 1, then TAS and its standard deviation are returned.
        If verbose = 2, then TAS, its standard deviation and the four wind
        speeds and directions are returned (the winds are returned as a list
        of four tuples)
    
    Validated against sample data in four leg tab of NTPS GPS PEC spreadsheet:
    http://www.ntps.edu/Files/GPS%20PEC.XLS
    
    Examples:
        
        Data for all examples:
            >>> gs = [178, 185, 188, 184]
            >>> tk = [178, 82, 355, 265]
            
            Determine the TAS, given the above data from four runs:
            >>> gps2tas(gs, tk)
            183.72669557114619
            
            Determine the TAS and standard deviation from the four calculations:
            >>> gps2tas(gs, tk, verbose = 1)
            (183.72669557114619, 0.82709634705928436)
            
            Determine the TAS, standard deviation, and wind speed and direction
            for each calculation:
            >>> gps2tas(gs, tk, verbose = 2)
            (183.72669557114619, 0.82709634705928436, ((5.2608369270843056, 194.51673740323213), (3.5823966532035927, 181.52174627838372), (5.1495218164839995, 162.69803415599802), (6.4436728241320145, 177.94783081049718)))

    """
    # confirm GS and TK are valid lengths:
    if 2 < len(GS) < 5:
        pass
    else:
        raise ValueError('GS must be a list of three or four items')
        
    if 2 < len(TK) < 5:
        pass
    else:
        raise ValueError('TK must be a list of three or four items')
    
    if len(GS) != len(TK):
        raise ValueError('The ground speed and track arrays must have the same number of elements.')
        
    if len(GS) == 3:
        result = gps2tas3(GS, TK, verbose)
        return result
    else:
        gs_data_sets, tk_data_sets, results = [], [], []
        
        gs_data_sets.append([GS[0], GS[1], GS[2]])
        gs_data_sets.append([GS[1], GS[2], GS[3]])
        gs_data_sets.append([GS[2], GS[3], GS[0]])      
        gs_data_sets.append([GS[3], GS[0], GS[1]])

        tk_data_sets.append([TK[0], TK[1], TK[2]])
        tk_data_sets.append([TK[1], TK[2], TK[3]])
        tk_data_sets.append([TK[2], TK[3], TK[0]])      
        tk_data_sets.append([TK[3], TK[0], TK[1]])
        
        for (gs, tk) in zip (gs_data_sets, tk_data_sets):
            results.append(gps2tas3(gs, tk, 2))
        
        ave_TAS = 0
        ave_wind_x = 0
        ave_wind_y = 0
        sum2_TAS = 0
        
        for item in results:
            ave_TAS +=item[0]
            sum2_TAS += item[0] ** 2
            ave_wind_x += item[1][0] * M.sin(M.pi * item[1][1] / 180.)
            ave_wind_y += item[1][0] * M.cos(M.pi * item[1][1] / 180.)

        ave_TAS /= 4.
        std_dev_TAS = M.sqrt((sum2_TAS - 4 * ave_TAS ** 2) / 3)
        ave_wind_x /= 4
        ave_wind_y /= 4.
        ave_wind_speed = M.sqrt(ave_wind_x ** 2 + ave_wind_y ** 2)
        ave_wind_dir = (720. - (180. / M.pi * M.atan2(ave_wind_x, ave_wind_y))) % 360
        # return results
        
        if verbose == 0:
            return ave_TAS
        elif verbose == 1:
            return ave_TAS, std_dev_TAS
        elif verbose == 2:
            return ave_TAS, std_dev_TAS, ((results[0][1][0], results[0][1][1]),(results[1][1][0], results[1][1][1]),(results[2][1][0], results[2][1][1]),(results[3][1][0], results[3][1][1]))
        else:
            raise ValueError('The value of verbose must be equal to 0, 1 or 2')


def gps2tas3(GS, TK, verbose=0):
    """
    Returns true airspeed, given GPS groundspeed and track on three legs.
    Uses the method developed by Doug Gray:
    http://www.kilohotel.com/rv8/rvlinks/doug_gray/TAS_FNL4.pdf
    
    GS and TK are arrays of ground speed and track data.
    
    If verbose = 0, then only TAS is returned.
    If verbose = 1, then TAS, wind speed and wind direction are returned.
    If verbose = 2, then TAS, wind speed and direction and the heading for
    each leg are returned.  The wind speed and direction is returned as a 
    tuple, and the headings are returned as a tuple

    Validated against sample in Doug Gray's paper.
    
    Examples:
    
    """
    x, y, b, m, hdg = [], [], [], [], []

    for (gs, tk) in zip(GS, TK):
        x.append(gs * M.sin(M.pi * (360. - tk) / 180.))
        y.append(gs * M.cos(M.pi * (360. - tk) / 180.))
    
    m.append(-1 * (x[1] - x[0]) / (y[1] - y[0]))
    m.append(-1 * (x[2] - x[0]) / (y[2] - y[0]))
    
    b.append((y[0] + y[1]) / 2 - m[0] * (x[0] + x[1]) / 2)
    b.append((y[0] + y[2]) / 2 - m[1] * (x[0] + x[2]) / 2)
    
    wind_x = (b[0] - b[1]) / (m[1] - m[0]) 
    wind_y = m[0] * wind_x + b[0]
    
    wind_speed = M.sqrt(wind_x ** 2 + wind_y ** 2)
    wind_dir = (540. - (180. / M.pi * M.atan2(wind_x, wind_y))) % 360.
    
    TAS = M.sqrt((x[0] - wind_x) ** 2 + (y[0] - wind_y) ** 2)
    
    if verbose >= 2:
        hdg.append((540. - (180. / M.pi * M.atan2(wind_x - x[0], wind_y - y[0]))) % 360.)
        hdg.append((540. - (180. / M.pi * M.atan2(wind_x - x[1], wind_y - y[1]))) % 360.)
        hdg.append((540. - (180. / M.pi * M.atan2(wind_x - x[2], wind_y - y[2]))) % 360.)
        
        return TAS, (wind_speed, wind_dir), (hdg[0], hdg[1], hdg[2])

    elif verbose == 1:
        return TAS, (wind_speed, wind_dir)
    elif verbose == 0:
        return TAS
    else:
        raise ValueError('The value of verbose must be equal to 0, 1 or 2')


def main():
	pass


if __name__ == '__main__':
	main()

