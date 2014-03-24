#!/usr/bin/python
# -*- coding: utf-8 -*-

# #############################################################################
#
# Distribution Notes
#
# HTML docs are created with epydoc, via
# "cd /Users/kwh/sw_projects/hg/python/AeroCalc_Package"
# "epydoc --no-private -n AeroCalc -u 'http://www.kilohotel.com/python/aerocalc/' aerocalc"
#
# Generate distribution - "python setup.py sdist"
#
# #############################################################################

from distutils.core import setup

setup(
    name='AeroCalc',
    version='0.11',
    description='Aeronautical Engineering Calculations',
    long_description='''
AeroCalc is a pure python package that performs various aeronautical 
engineering calculations.  Currently it provides airspeed conversions, 
standard atmosphere calculations, static source error correction calculations 
and unit conversions.''',
    author='Kevin Horton',
    author_email='kevin01@kilohotel.com',
	url='http://www.kilohotel.com/python/aerocalc',
    packages=['aerocalc'],
    license='BSD',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: Atmospheric Science',
        ],
    
    )
