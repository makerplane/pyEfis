#!/usr/bin/python
# -*- coding: utf-8 -*-

""" Test cases for airspeed module.
Run this script directly to do all the tests.
"""

import unittest
import sys

# sys.path.append('/Users/kwh/python/')

sys.path.append('../')
import airspeed as A

# These tests assume that default_units.py contains the following defaults:
# default_area_units = 'ft**2'
# default_power_units = 'hp'
# default_speed_units = 'kt'
# default_temp_units = 'C'
# default_weight_units = 'lb'
# default_press_units = 'in HG'
# default_density_units = 'lb/ft**3'
# default_length_units = 'ft'
# default_alt_units = default_length_units
# default_avgas_units = 'lb'


def RE(value, truth):
    """ Return the absolute value of the relative error.
...."""

    return abs((value - truth) / truth)


class Test_cas2dp(unittest.TestCase):

    def test_01(self):

        # 100 kt to lb/ft**3
        # truth value from NASA RP 1046

        Value = A.cas2dp(100, press_units='psf')
        Truth = 34.0493
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):

        # 600 kt to lb/ft**3
        # truth value from NASA RP 1046

        Value = A.cas2dp(700, press_units='psf', speed_units='mph')
        Truth = 1540.37
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):

        # 300 mph to in HG
        # truth value from NASA RP 1046

        Value = A.cas2dp(300, press_units='in HG', speed_units='mph')
        Truth = 3.38145
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_04(self):

        # 300 mph to in HG
        # truth value from NASA RP 1046

        Value = A.cas2dp(55, press_units='in HG', speed_units='kt')
        Truth = .145052
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_05(self):

        # 300 km/h to mm HG
        # truth value from NASA RP 1046

        Value = A.cas2dp(300, press_units='mm HG', speed_units='km/h')
        Truth = 32.385
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_06(self):

        # 299 km/h to pa
        # truth value from NASA RP 1046

        Value = A.cas2dp(299, press_units='pa', speed_units='km/h')
        Truth = 4288.5
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_07(self):

        # 280 kt to mm HG
        # truth value from NASA RP 1046

        Value = A.cas2dp(280, press_units='mm HG')
        Truth = 99.671
        self.failUnless(RE(Value, Truth) <= 2e-5)

    def test_08(self):

        # 244 kt to pa
        # truth value from NASA RP 1046

        Value = A.cas2dp(244, press_units='pa')
        Truth = 9983.7
        self.failUnless(RE(Value, Truth) <= 2e-5)

    def test_09(self):

        # 1000 mph to in HG
        # truth value from NASA RP 1046

        Value = A.cas2dp(1000, press_units='in HG', speed_units='mph')
        Truth = 52.5970
        self.failUnless(RE(Value, Truth) <= 2e-5)

    def test_10(self):

        # 1000 mph to psf
        # truth value from NASA RP 1046

        Value = A.cas2dp(1000, press_units='psf', speed_units='mph')
        Truth = 3719.98
        self.failUnless(RE(Value, Truth) <= 2e-5)

    def test_11(self):

        # 1000 kt to in HG
        # truth value from NASA RP 1046

        Value = A.cas2dp(1000, press_units='in HG')
        Truth = 73.5454
        self.failUnless(RE(Value, Truth) <= 2e-5)

    def test_12(self):

        # 1000 kt to psf
        # truth value from NASA RP 1046

        Value = A.cas2dp(1000, press_units='psf')
        Truth = 5201.59
        self.failUnless(RE(Value, Truth) <= 2e-5)

    def test_13(self):

        # 1700 km/h to mm HG
        # truth value from NASA RP 1046

        Value = A.cas2dp(1700, press_units='mm HG', speed_units='km/h')
        Truth = 1524.86
        self.failUnless(RE(Value, Truth) <= 2e-5)

    def test_14(self):

        # 1700 km/h to pa
        # truth value from NASA RP 1046

        Value = A.cas2dp(1700, press_units='pa', speed_units='km/h')
        Truth = 203298
        self.failUnless(RE(Value, Truth) <= 2e-5)

    def test_15(self):

        # 1000 kt to mm HG
        # truth value from NASA RP 1046

        Value = A.cas2dp(1000, press_units='mm HG')
        Truth = 1868.05
        self.failUnless(RE(Value, Truth) <= 2e-5)

    def test_16(self):

        # 1000 kt to pa
        # truth value from NASA RP 1046

        Value = A.cas2dp(1000, press_units='pa')
        Truth = 249053
        self.failUnless(RE(Value, Truth) <= 2e-5)


class Test_dp2cas(unittest.TestCase):

    def test_01(self):

        # 100 kt in lb/ft**3
        # truth value from NASA RP 1046

        Value = A.dp2cas(34.0493, press_units='psf')
        Truth = 100
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):

        # 700 mph in lb/ft**3
        # truth value from NASA RP 1046

        Value = A.dp2cas(1540.37, press_units='psf', speed_units='mph')
        Truth = 700
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):

        # 300 mph in in HG
        # truth value from NASA RP 1046

        Value = A.dp2cas(3.38145, press_units='in HG', speed_units='mph'
                         )
        Truth = 300
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_04(self):

        # 55 kt in in HG
        # truth value from NASA RP 1046

        Value = A.dp2cas(.145052, press_units='in HG', speed_units='kt')
        Truth = 55
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_05(self):

        # 300 km/h in mm HG
        # truth value from NASA RP 1046

        Value = A.dp2cas(32.385, press_units='mm HG', speed_units='km/h'
                         )
        Truth = 300
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_06(self):

        # 299 km/h in pa
        # truth value from NASA RP 1046

        Value = A.dp2cas(4288.5, press_units='pa', speed_units='km/h')
        Truth = 299
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_07(self):

        # 280 kt in mm HG
        # truth value from NASA RP 1046

        Value = A.dp2cas(99.671, press_units='mm HG')
        Truth = 280
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_08(self):

        # 244 kt in pa
        # truth value from NASA RP 1046

        Value = A.dp2cas(9983.7, press_units='pa')
        Truth = 244
        self.failUnless(RE(Value, Truth) <= 1e-5)

# ....def test_09(self):
# ........# check out of range on airspeed too high
# ........# truth value from NASA RP 1046
# ........self.assertRaises(ValueError, A.dp2cas, 1889.51, speed_units = 'mph', press_units = 'psf')

    def test_09(self):

        # 1000 kt in lb/ft**3
        # truth value from NASA RP 1046

        Value = A.dp2cas(5201.59, press_units='psf')
        Truth = 1000
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_10(self):

        # 1100 mph in lb/ft**3
        # truth value from NASA RP 1046

        Value = A.dp2cas(4676.47, press_units='psf', speed_units='mph')
        Truth = 1100
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_11(self):

        # 1100 mph in in HG
        # truth value from NASA RP 1046

        Value = A.dp2cas(66.1208, press_units='in HG', speed_units='mph'
                         )
        Truth = 1100
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_12(self):

        # 1000 kt in in HG
        # truth value from NASA RP 1046

        Value = A.dp2cas(73.5454, press_units='in HG', speed_units='kt')
        Truth = 1000
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_13(self):

        # 1700 km/h in mm HG
        # truth value from NASA RP 1046

        Value = A.dp2cas(1524.86, press_units='mm HG',
                         speed_units='km/h')
        Truth = 1700
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_14(self):

        # 1700 km/h in pa
        # truth value from NASA RP 1046

        Value = A.dp2cas(203298, press_units='pa', speed_units='km/h')
        Truth = 1700
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_15(self):

        # 1000 kt in mm HG
        # truth value from NASA RP 1046

        Value = A.dp2cas(1868.05, press_units='mm HG')
        Truth = 1000
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_16(self):

        # 1000 kt in pa
        # truth value from NASA RP 1046

        Value = A.dp2cas(249053, press_units='pa')
        Truth = 1000
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_cas2tas(unittest.TestCase):

    def test_01(self):

        # 400 kt at 30000, std temp
        # truth value from NASA RP 1046

        Value = A.cas2tas(400, 30000)
        Truth = 602.6
        self.failUnless(RE(Value, Truth) <= 3e-5)

    def test_02(self):

        # 400 kt at 30000, temp -70 deg F
        # truth value from NASA RP 1046 + correction for non-standard temp

        Value = A.cas2tas(400, 30000, -70, temp_units='F')
        Truth = 586.266
        self.failUnless(RE(Value, Truth) <= 3e-5)


class Test_tas2cas(unittest.TestCase):

    def test_01(self):

        # 400 kt at 30000, std temp
        # truth value from NASA RP 1046

        Value = A.tas2cas(602.6, 30000)
        Truth = 400
        self.failUnless(RE(Value, Truth) <= 3e-5)

    def test_02(self):

        # 400 kt at 30000, temp -70 deg F
        # truth value from NASA RP 1046 + correction for non-standard temp

        Value = A.tas2cas(586.266, 30000, -70, temp_units='F')
        Truth = 400
        self.failUnless(RE(Value, Truth) <= 3e-5)


class Test_mach2dp_over_p(unittest.TestCase):

    def test_01(self):

        # M0.8

        Value = A.mach2dp_over_p(.8)

        # truth value from NASA RP 1046

        Truth = .52434
        self.failUnless(RE(Value, Truth) <= 1e-5)

# ....def test_02(self):
# ........# check out of range on mach too high
# ........self.assertRaises(ValueError, A.mach2dp_over_p, 1.0001)

    def test_02(self):

        # M 1

        Value = A.mach2dp_over_p(1)

        # truth value from NASA RP 1046

        Truth = .89293
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):

        # M 1.001

        Value = A.mach2dp_over_p(1.001)

        # truth value from NASA RP 1046

        Truth = .89514
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_04(self):

        # M 5

        Value = A.mach2dp_over_p(5)

        # truth value from NASA RP 1046

        Truth = 31.65347
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_dp_over_p2mach(unittest.TestCase):

    def test_01(self):

        # M0.8

        Value = A.dp_over_p2mach(.52434)

        # truth value from NASA RP 1046

        Truth = .8
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):

        # M0.999

        Value = A.dp_over_p2mach(.89072)

        # truth value from NASA RP 1046

        Truth = .999
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):

        # M1.0

        Value = A.dp_over_p2mach(.89293)

        # truth value from NASA RP 1046

        Truth = 1
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_04(self):

        # M1.001

        Value = A.dp_over_p2mach(.89514)

        # truth value from NASA RP 1046

        Truth = 1.001
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_05(self):

        # M5

        Value = A.dp_over_p2mach(31.65347)

        # truth value from NASA RP 1046

        Truth = 5
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_tas2mach(unittest.TestCase):

    def test_01(self):

        # Mach 1

        Value = A.tas2mach(661.48, 15)

        # truth value from NASA RP 1046

        Truth = 1
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):

        # Mach .5, mph, deg F

        Value = A.tas2mach(761.22 / 2, 59, speed_units='mph',
                           temp_units='F')

        # truth value from NASA RP 1046

        Truth = .5
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):

        # Mach 1, mph, 10,000 ft

        Value = A.tas2mach(734.58, speed_units='mph', altitude=10000)

        # truth value from NASA RP 1046

        Truth = 1
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_04(self):

        # Mach 1, km/h, 10,000 m

        Value = A.tas2mach(1078.07, speed_units='km/h', altitude=10000,
                           alt_units='m')

        # truth value from NASA RP 1046

        Truth = 1
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_mach2tas(unittest.TestCase):

    def test_01(self):

        # Mach 1

        Value = A.mach2tas(1, 15)

        # truth value from NASA RP 1046

        Truth = 661.48
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):

        # Mach .5

        Value = A.mach2tas(.5, 59, speed_units='mph', temp_units='F')

        # truth value from NASA RP 1046

        Truth = 761.22 / 2
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):

        # Mach 1, mph, 10,000 ft

        Value = A.mach2tas(1, speed_units='mph', altitude=10000)

        # truth value from NASA RP 1046

        Truth = 734.58
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_mach2temp(unittest.TestCase):

    def test_01(self):

        # Mach 0.5, 15 deg C, K = 0.5

        Value = A.mach2temp(.5, 15, .5)
        Truth = 7.97195121951
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):

        # Mach 0.7, 59 deg F, K = 0.8

        Value = A.mach2temp(.7, 59, .8, temp_units='F')
        Truth = 21.29253709199
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_tas2temp(unittest.TestCase):

    def test_01(self):

        # 300 KTAS, 15 deg C, K = 0

        Value = A.tas2temp(300, 15, 0)
        Truth = 15
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):

        # 300 mph TAS, 59 deg F, K = 0.8

        Value = A.tas2temp(300, 59, .8, temp_units='F', speed_units = 'mph')
        Truth = 46.11
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):

        # 1000 km/h TAS, 59 deg F, K = 0.95

        Value = A.tas2temp(1000, 59, .95, temp_units='F', speed_units = 'km/h')
        Truth = -6.664535
        # print Value, Truth
        self.failUnless(RE(Value, Truth) <= 1e-5)

# create test suites

main_suite = unittest.TestSuite()
suite1 = unittest.makeSuite(Test_cas2dp)
suite2 = unittest.makeSuite(Test_dp2cas)

# suite3 = unittest.makeSuite(Test_asi_inst_error_corr)
# suite4 = unittest.makeSuite(Test_mach2dp_over_p)

suite5 = unittest.makeSuite(Test_cas2tas)
suite6 = unittest.makeSuite(Test_tas2cas)
suite7 = unittest.makeSuite(Test_mach2dp_over_p)
suite8 = unittest.makeSuite(Test_dp_over_p2mach)
suite9 = unittest.makeSuite(Test_tas2mach)
suite10 = unittest.makeSuite(Test_mach2tas)
suite11 = unittest.makeSuite(Test_mach2temp)
suite12 = unittest.makeSuite(Test_tas2temp)

# add test suites to main test suite, so all test results are in one block

main_suite.addTest(suite1)
main_suite.addTest(suite2)

# main_suite.addTest(suite3)
# main_suite.addTest(suite4)

main_suite.addTest(suite5)
main_suite.addTest(suite6)
main_suite.addTest(suite7)
main_suite.addTest(suite8)
main_suite.addTest(suite9)
main_suite.addTest(suite10)
main_suite.addTest(suite11)
main_suite.addTest(suite12)

# run main test suite
# if we run the main test suite, we get a line for each test, plus any
# tracebacks from failures.

unittest.TextTestRunner(verbosity=5).run(main_suite)

# if we run unittest.main(), we get just a single line of output, plus any
# tracebacks from failures.
# if __name__ == '__main__':
#     unittest.main()

