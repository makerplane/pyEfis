#!/usr/bin/python
# -*- coding: utf-8 -*-

# version 0.15, 29 Apr 07

""" Test cases for ssec module.
Run this script directly to do all the tests.
"""

import unittest
import sys

# It is assumed that ssec.py is in the directory directly above

sys.path.append('../')
import ssec as SS



def RE(value, truth):
    """ Returns the absolute value of the relative error.
    """

    return abs((value - truth) / truth)


class Test_gps2tas(unittest.TestCase):

    def test_01(self):

        # three legs, returning TAS only

        Value = SS.gps2tas([178, 185, 188], [178, 82, 355])
        Truth = 183.05
        self.failUnless(RE(Value, Truth) <= 1e-4)

    def test_02(self):

        # three legs, returning TAS, wind speed and direction

        (TAS, (WS, Dir)) = SS.gps2tas([178, 185, 188], [178, 82, 355], 1)
        TAS_Truth = 183.05
        WS_Truth = 5.26
        Dir_Truth = 194.5
        self.failUnless(RE(TAS, TAS_Truth) <= 1e-4)
        self.failUnless(RE(WS, WS_Truth) <= 1e-3)
        self.failUnless(RE(Dir, Dir_Truth) <= 1e-4)


        # four legs, returning TAS only

        Value = SS.gps2tas([178, 185, 188, 184], [178, 82, 355, 265])
        Truth = 183.73
        self.failUnless(RE(Value, Truth) <= 1e-4)

    def test_03(self):

        # three legs, returning TAS, wind speed and direction and heading for each leg

        (TAS, (WS, Dir), (H0, H1, H2)) = SS.gps2tas([178, 185, 188], [178, 82, 355], 2)
        TAS_Truth = 183.05
        WS_Truth = 5.26
        Dir_Truth = 194.5
        H0_T = 178.46
        H1_T = 83.52
        H2_T = 354.45
        self.failUnless(RE(TAS, TAS_Truth) <= 1e-4)
        self.failUnless(RE(WS, WS_Truth) <= 1e-3)
        self.failUnless(RE(Dir, Dir_Truth) <= 1e-4)
        self.failUnless(RE(H0, H0_T) <= 1e-4)
        self.failUnless(RE(H1, H1_T) <= 1e-4)
        self.failUnless(RE(H2, H2_T) <= 1e-4)

    def test_04(self):

        # four legs, returning TAS only

        Value = SS.gps2tas([178, 185, 188, 184], [178, 82, 355, 265])
        Truth = 183.73
        self.failUnless(RE(Value, Truth) <= 1e-4)

    def test_05(self):

        # four legs, returning TAS and standard deviation

        (TAS, SD) =SS.gps2tas([178, 185, 188, 184], [178, 82, 355, 265], 1)
        TAS_Truth = 183.73
        SD_Truth = 0.827
        self.failUnless(RE(TAS, TAS_Truth) <= 1e-4)
        self.failUnless(RE(SD, SD_Truth) <= 1e-3)

    def test_06(self):

        # four legs, returning TAS, standard deviation and four calculated winds

        (TAS, SD, ((W0, D0), (W1, D1), (W2, D2), (W3, D3))) = SS.gps2tas([178, 185, 188, 184], [178, 82, 355, 265], 2)
        TAS_Truth = 183.73
        SD_Truth = 0.827
        W0_T, D0_T = 5.26, 194.52
        W1_T, D1_T = 3.58, 181.52
        W2_T, D2_T = 5.15, 162.7
        W3_T, D3_T = 6.44, 177.95
        self.failUnless(RE(TAS, TAS_Truth) <= 1e-4)
        self.failUnless(RE(SD, SD_Truth) <= 1e-3)
        self.failUnless(RE(D0, D0_T) <= 1e-4)
        self.failUnless(RE(D1, D1_T) <= 1e-4)
        self.failUnless(RE(D2, D2_T) <= 1e-4)
        self.failUnless(RE(D3, D3_T) <= 1e-4)
        self.failUnless(RE(W0, W0_T) <= 1e-3)
        self.failUnless(RE(W1, W1_T) <= 1e-3)
        self.failUnless(RE(W2, W2_T) <= 1e-3)
        self.failUnless(RE(W3, W3_T) <= 1e-3)


# create test suites

main_suite = unittest.TestSuite()
suite1 = unittest.makeSuite(Test_gps2tas)
# suite2 = unittest.makeSuite(Test_alt2temp_ratio)
# suite3 = unittest.makeSuite(Test_alt2press_ratio)
# suite4 = unittest.makeSuite(Test_alt2press)
# suite5 = unittest.makeSuite(Test_alt2density_ratio)
# suite6 = unittest.makeSuite(Test_alt2density)
# suite7 = unittest.makeSuite(Test_press2alt)
# suite8 = unittest.makeSuite(Test_press_ratio2alt)
# suite9 = unittest.makeSuite(Test_density2alt)
# suite10 = unittest.makeSuite(Test_density_ratio2alt)
# suite11 = unittest.makeSuite(Test_density_alt)
# suite12 = unittest.makeSuite(Test_temp2speed_of_sound)
# suite13 = unittest.makeSuite(Test_temp2isa)
# suite14 = unittest.makeSuite(Test_isa2temp)
# suite15 = unittest.makeSuite(Test_pressure_alt)
# suite16 = unittest.makeSuite(Test_sat_press)
# suite17 = unittest.makeSuite(Test_density_alt2temp)

# add test suites to main test suite, so all test results are in one block

main_suite.addTest(suite1)
# main_suite.addTest(suite2)
# main_suite.addTest(suite3)
# main_suite.addTest(suite4)
# main_suite.addTest(suite5)
# main_suite.addTest(suite6)
# main_suite.addTest(suite7)
# main_suite.addTest(suite8)
# main_suite.addTest(suite9)
# main_suite.addTest(suite10)
# main_suite.addTest(suite11)
# main_suite.addTest(suite12)
# main_suite.addTest(suite13)
# main_suite.addTest(suite14)
# main_suite.addTest(suite15)
# main_suite.addTest(suite16)
# main_suite.addTest(suite17)

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(main_suite)

