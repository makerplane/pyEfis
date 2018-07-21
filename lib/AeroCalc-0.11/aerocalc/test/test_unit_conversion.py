#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Test cases for unit_conversion module.
Run this script directly to do all the tests.
"""

import unittest
import sys
sys.path[0] = '../'
import unit_conversion as U


def RE(value, truth):
    """ Return the absolute value of the relative error.
    """

    if truth == 0:
        return abs(value - truth)
    else:
        return abs((value - truth) / truth)


class Test_area_conv(unittest.TestCase):

    """Given that the conversion function works by converting units to or from
     a base unit, a complete check requires one calculation that converts too 
     and from each unit."""

    def test_01(self):
        Value = U.area_conv(10, from_units='ft**2', to_units='in**2')
        Truth = 1440
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):
        Value = U.area_conv(144, from_units='in**2', to_units='m**2')
        Truth = 0.3048 ** 2
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):
        Value = U.area_conv(1000, from_units='m**2', to_units='km**2')
        Truth = 0.001
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_04(self):
        Value = U.area_conv(1, from_units='km**2', to_units='sm**2')
        Truth = ((1000 / 0.3048) / 5280) ** 2
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_05(self):
        Value = U.area_conv(1, from_units='sm**2', to_units='nm**2')
        Truth = (5280 / (1852. / 0.3048)) ** 2
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_06(self):
        Value = U.area_conv(1, from_units='nm**2', to_units='ft**2')
        Truth = (1852. / 0.3048) ** 2
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_density_conv(unittest.TestCase):

    def test_01(self):
        Value = U.density_conv(1, from_units='kg/m**3',
                               to_units='slug/ft**3')
        Truth = (3.6127292e-5 * 12 ** 3) / 32.174
        print(Value, Truth)
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):
        Value = U.density_conv(1, from_units='slug/ft**3',
                               to_units='lb/ft**3')
        Truth = 32.174
        print(Value, Truth)
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_force_conv(unittest.TestCase):

    def test_01(self):
        Value = U.force_conv(100, from_units='lb', to_units='N')
        Truth = 444.822
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):
        Value = U.force_conv(444.822, from_units='N', to_units='lb')
        Truth = 100
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_len_conv(unittest.TestCase):

    def test_01(self):
        Value = U.len_conv(120, from_units='in', to_units='ft')
        Truth = 10
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):
        Value = U.len_conv(10, from_units='ft', to_units='in')
        Truth = 120
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):
        Value = U.len_conv(10000, from_units='m', to_units='km')
        Truth = 10
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_04(self):
        Value = U.len_conv(10, from_units='km', to_units='m')
        Truth = 10000
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_05(self):
        Value = U.len_conv(1, from_units='sm', to_units='nm')
        Truth = 0.86897624
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_06(self):
        Value = U.len_conv(0.86897624, from_units='nm', to_units='sm')
        Truth = 1
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_power_conv(unittest.TestCase):

    def test_01(self):
        Value = U.power_conv(1, from_units='hp', to_units='ft-lb/mn')
        Truth = 33000
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):
        Value = U.power_conv(33000, from_units='ft-lb/mn', to_units='hp'
                             )
        Truth = 1
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):
        Value = U.power_conv(550, from_units='ft-lb/s', to_units='kW')
        Truth = 0.74569987
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_04(self):
        Value = U.power_conv(0.74569987, from_units='kW',
                             to_units='ft-lb/s')
        Truth = 550
        self.failUnless(RE(Value, Truth) <= 1e-5)


    # def test_05(self):
    #     Value = U.power_conv(0.017584264, from_units='kW', to_units='BTU/hr')
    #     Truth = 60
    #     print(Value, Truth)
    #     self.failUnless(RE(Value, Truth) <= 1e-5)
    #
    # def test_06(self):
    #     Value = U.power_conv(60, from_units='BTU/hr', to_units='W')
    #     Truth = 17.584264
    #     self.failUnless(RE(Value, Truth) <= 1e-5)
    #
    # def test_07(self):
    #     Value = U.power_conv(0.017584264, from_units='kW', to_units='BTU/mn')
    #     Truth = 1
    #     self.failUnless(RE(Value, Truth) <= 1e-5)
    #
    # def test_08(self):
    #     Value = U.power_conv(1, from_units='BTU/mn', to_units='W')
    #     Truth = 17.584264
    #     self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_press_conv(unittest.TestCase):

    def test_01(self):
        Value = U.press_conv(1, from_units='in HG', to_units='mm HG')
        Truth = 25.4
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):
        Value = U.press_conv(1, from_units='mm HG', to_units='psi')
        Truth = 0.01934543333
        self.failUnless(RE(Value, Truth) <= 5e-4)

    def test_03(self):
        Value = U.press_conv(1, from_units='psi', to_units='lb/ft**2')
        Truth = 144
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_04(self):
        Value = U.press_conv(1, from_units='lb/ft**2', to_units='mb')
        Truth = 0.4788
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_speed_conv(unittest.TestCase):

    def test_01(self):
        Value = U.speed_conv(1, from_units='kt', to_units='mph')
        Truth = (1852. / 0.3048) / 5280
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):
        Value = U.speed_conv(1, from_units='mph', to_units='km/h')
        Truth = (5280 * 0.3048) / 1000
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):
        Value = U.speed_conv(1, from_units='km/h', to_units='m/s')
        Truth = 1000 / 3600.
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_04(self):
        Value = U.speed_conv(1, from_units='m/s', to_units='ft/s')
        Truth = 1 / 0.3048
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_05(self):
        Value = U.speed_conv(1, from_units='ft/s', to_units='kt')
        Truth = 3600. / (1852. / 0.3048)
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_temp_conv(unittest.TestCase):

    def test_01(self):
        Value = U.temp_conv(0, from_units='C', to_units='F')
        Truth = 32
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):
        Value = U.temp_conv(100, from_units='C', to_units='F')
        Truth = 212
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):
        Value = U.temp_conv(32, from_units='F', to_units='C')
        Truth = 0
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_04(self):
        Value = U.temp_conv(212, from_units='F', to_units='C')
        Truth = 100
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_05(self):
        Value = U.temp_conv(473.15, from_units='K', to_units='C')
        Truth = 200.
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_06(self):
        Value = U.temp_conv(-100, from_units='C', to_units='K')
        Truth = 173.15
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_07(self):
        Value = U.temp_conv(100, from_units='K', to_units='R')
        Truth = 180
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_08(self):
        Value = U.temp_conv(180, from_units='R', to_units='K')
        Truth = 100
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_09(self):
        Value = U.temp_conv(32, from_units='F', to_units='R')
        Truth = 491.67
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_10(self):
        Value = U.temp_conv(671.67, from_units='R', to_units='F')
        Truth = 212
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_11(self):
        Value = U.temp_conv(671.67, from_units='R', to_units='C')
        Truth = 100
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_12(self):
        Value = U.temp_conv(-100, from_units='C', to_units='R')
        Truth = 311.67
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_13(self):
        Value = U.temp_conv(373.15, from_units='K', to_units='F')
        Truth = 212
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_14(self):
        Value = U.temp_conv(-148, from_units='F', to_units='K')
        Truth = 173.15
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_vol_conv(unittest.TestCase):

    def test_01(self):
        Value = U.vol_conv(1, from_units='ft**3', to_units='in**3')
        Truth = 12 ** 3
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):
        Value = U.vol_conv(1, to_units='m**3', from_units='in**3')
        Truth = (0.3048 / 12) ** 3
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):
        Value = U.vol_conv(1, from_units='m**3', to_units='km**3')
        Truth = 0.001 ** 3
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_04(self):
        Value = U.vol_conv(1, to_units='sm**3', from_units='km**3')
        Truth = ((1000 / 0.3048) / 5280) ** 3
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_05(self):
        Value = U.vol_conv(1, from_units='sm**3', to_units='nm**3')
        Truth = (5280 / (1852. / 0.3048)) ** 3
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_06(self):
        Value = U.vol_conv(1, to_units='USG', from_units='nm**3')
        Truth = 7.4805195 * (1852. / 0.3048) ** 3
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_07(self):
        Value = U.vol_conv(1, from_units='USG', to_units='ImpGal')
        Truth = 0.83267418
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_08(self):
        Value = U.vol_conv(1, to_units='l', from_units='ImpGal')
        Truth = 4.54609
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_09(self):
        Value = U.vol_conv(1, from_units='l', to_units='ft**3')
        Truth = (0.1 / 0.3048) ** 3
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_wt_conv(unittest.TestCase):

    def test_01(self):
        Value = U.avgas_conv(100, from_units='lb', to_units='kg')
        Truth = 45.359
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_02(self):
        Value = U.avgas_conv(45.359, from_units='kg', to_units='lb')
        Truth = 100
        self.failUnless(RE(Value, Truth) <= 1e-5)

    def test_03(self):
        Value = U.avgas_conv(100, from_units='lb', to_units='lb')
        Truth = 100
        self.failUnless(RE(Value, Truth) <= 1e-5)


class Test_avgas_conv(unittest.TestCase):

    def test_01(self):

        # 10 USG of nominal fuel at nominal temperature to lbs
        # truth value from Canada Flight Supplement

        Value = U.avgas_conv(10, from_units='USG', to_units='lb')
        Truth = 60.1
        self.failUnless(RE(Value, Truth) <= 5e-4)

    def test_02(self):

        # 200 lb of nominal fuel at -40 deg C to USG
        # truth value from Canada Flight Supplement

        Value = U.avgas_conv(200., from_units='lb', to_units='USG',
                             temp=-40)
        Truth = 200. / 6.41
        self.failUnless(RE(Value, Truth) <= 5e-4)

    def test_03(self):

        # 200 lb of 100LL grade fuel at 15 deg C to Imperial Gallons
        # truth value from Air BP Handbook of Products - 715 kg/m**3

        Value = U.avgas_conv(200., from_units='lb', to_units='ImpGal',
                             grade='100LL')
        Truth = (((200. / 2.204622622) / 715) * 1000) / 4.54609
        self.failUnless(RE(Value, Truth) <= 5e-4)

    def test_04(self):

        # 200 kg of 100 grade fuel at 30 deg C to l
        # truth value from Air BP Handbook of Products - 695 kg/m**3 at 15 deg C

        Value = U.avgas_conv(200., from_units='kg', to_units='l',
                             grade='100', temp=30)
        Truth = (200. / 695) * 1000

        # correct for temperature, using ratio given in Canada Flight Supplement

        Truth *= 6.01 / 5.9
        self.failUnless(RE(Value, Truth) <= 5e-4)

    def test_05(self):

        # 200 l of 80 grade fuel at -40 deg C to kg
        # truth value from Air BP Handbook of Products - 690 kg/m**3 at 15 deg C

        Value = U.avgas_conv(200., from_units='l', to_units='kg',
                             grade='80', temp=-40)
        Truth = (200. / 1000) * 690

        # correct for temperature, using ratio given in Canada Flight Supplement

        Truth *= 6.41 / 6.01
        self.failUnless(RE(Value, Truth) <= 5e-4)


# create test suites

main_suite = unittest.TestSuite()
suite1 = unittest.makeSuite(Test_area_conv)
suite2 = unittest.makeSuite(Test_density_conv)
suite3 = unittest.makeSuite(Test_force_conv)
suite4 = unittest.makeSuite(Test_len_conv)
suite5 = unittest.makeSuite(Test_power_conv)
suite6 = unittest.makeSuite(Test_press_conv)
suite7 = unittest.makeSuite(Test_speed_conv)
suite8 = unittest.makeSuite(Test_temp_conv)
suite9 = unittest.makeSuite(Test_vol_conv)
suite10 = unittest.makeSuite(Test_wt_conv)
suite11 = unittest.makeSuite(Test_avgas_conv)

# add test suites to main test suite, so all test results are in one block

main_suite.addTest(suite1)
main_suite.addTest(suite2)
main_suite.addTest(suite3)
main_suite.addTest(suite4)
main_suite.addTest(suite5)
main_suite.addTest(suite6)
main_suite.addTest(suite7)
main_suite.addTest(suite8)
main_suite.addTest(suite9)
main_suite.addTest(suite10)
main_suite.addTest(suite11)

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=5).run(main_suite)

