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
# version 0.10, 17 May 2007
#
# Version History:
# vers     date      Notes
# 0.10   17 May 07   Initial version.
# #############################################################################
#
# To Do:  1. Done.
#
#
# Done    1. Find way to generalize the criteria, to allow coverage of a wider
#            range of cases.

# #############################################################################

# def get_input_with_default(prompt, type, error_string, check_list =[], default = '', **kwds):
#     """
#     Return user input after validating it, offering the user a default value.
#     """
#
#     try:
#         prompt = 'CAS = [' + str(data_items['cas']) + '] '
#         value = VI.get_input(prompt, 'float+_or_blank',
#                        'ERROR - CAS must be a positive number.')
#         if value != '':
#             data_items['cas'] = value
#     except KeyError:
#         prompt = 'CAS = '
#         data_items['cas'] = VI.get_input(prompt, 'float+_or_blank',
#                        'ERROR - CAS must be a positive number.')
#
#     return data_items['cas']

"""
Validate user input against arbitrary criteria.  Used in the interactive interface in other modules.
"""


def get_input(
    prompt,
    type,
    error_string,
    check_list=[],
    default='',
    **kwds
    ):
    """
    Return user input after validating it.
    """

    input_validated = False

    if type == 'float':
        while not input_validated:
            input_data = eval(input(prompt))
            try:
                input_data = float(input_data)
                input_validated = True
            except ValueError:
                print(error_string)

    if type == 'float+':

        # data is a positive float

        input_data = eval(input(prompt))
        try:
            input_data = float(input_data)
            if input_data < 0:
                print(error_string)
            else:
                input_validated = True
        except ValueError:
            print(error_string)
    elif type == 'float_or_blank':

        # data is a float or blank

        while not input_validated:
            input_data = eval(input(prompt))
            if input_data == '':
                input_data = default
                input_validated = True
            else:
                try:
                    input_data = float(input_data)
                    input_validated = True
                except ValueError:
                    print(error_string)
    elif type == 'float_str_or_blank':

        # data is a float, a string in kwds['str_list'] or blank

        while not input_validated:
            input_data = eval(input(prompt))
            if input_data == '':
                input_data = default
                input_validated = True
            elif input_data in kwds['str_list']:
                input_validated = True
            else:
                try:
                    input_data = float(input_data)
                    input_validated = True
                except ValueError:
                    print(error_string)
    elif type == 'float+_or_blank':

        # data is a float, >= 0, or blank

        while not input_validated:
            input_data = eval(input(prompt))
            if input_data == '':
                input_data = default
                input_validated = True
                return input_data
            try:
                input_data = float(input_data)
                if input_data < 0:
                    print(error_string)
                else:
                    input_validated = True
            except ValueError:
                print(error_string)

    if type == 'int':
        while 1:
            input_data = eval(input(prompt))
            try:
                input_data = int(input_data)
                break
            except ValueError:
                print(error_string)

    if type == 'int_or_str':

        # data is an int or a string in kwds['str_list']

        while 1:
            input_data = eval(input(prompt))
            if input_data in kwds['str_list']:
                break
            try:
                input_data = int(input_data)
                try:
                    if input_data < kwds['min']:
                        print('You must enter an integer no less than', \
                            kwds['min'])
                except KeyError:
                    pass
                try:
                    if input_data > kwds['max']:
                        print('You must enter an integer less than', \
                            kwds['max'])
                except KeyError:
                    break
            except ValueError:
                print('You must enter an integer')
    elif type == 'list':

        while not input_validated:
            input_data = eval(input(prompt))
            if input_data == '':
                input_data = default
                input_validated = True
                return default
            if input_data in check_list:
                input_validated = True
            else:
                print(error_string)

    return input_data


def get_input2(
    prompt,
    conditions_any=[],
    conditions_all=[],
    debug=False,
    ):
    """Return user input, after validating it against arbitrary criteria.

    The user input must satisfy all conditions in conditions_all, and one or
    more of the conditions in conditions_any.  Conditions_any is a list, with
    the first item the error string to display if none of the conditions are
    met.  Conditions_all is a list of tuples, with each tuple having one
    condition + the associated error string to display to the user if the
    condition is not met.

    The conditions will be inserted in 'if' statements, and must be written
    so that the 'if' statement will be true if the data is valid.  E.g.

    if a 'Q' is needed:
    'X == \"Q\"'

    Note 1: all data input by the user is seen as a string, even if numbers are
    entered.  If the test is looking for an integer, write it as:
    'int(X)'

    Note 2: All tests are run inside 'try' statements, so exceptions will not
    cause problems.  Any test that raises an exception is treated as a failed
    test.

    Note 3: One idiosyncrasy of 'if' statements is that any statement that
    returns a \"0\" is treated as a False.  Tests must be crafted so a pass
    does not return a '0'.  E.g., if the test is intended to check that the
    data is a float, and a zero would be valid data, do not write the test as:
    'float(X)', as 'if float(\"0\"):' will not pass.

    """

    input_validated = False

    while not input_validated:
        X = eval(input(prompt))
        validated_any = False
        validated_all = True

        # does input meet one of conditions in conditions_any?

        if len(conditions_any) > 0:
            error_string = conditions_any[0]
            for condition in conditions_any[1:]:
                if debug:
                    print(('Testing condition', condition))
                try:
                    if eval(condition):
                        validated_any = True
                        if debug:
                            print('Test of ', condition, 'passed')
                    else:
                        if debug:
                            print('Test of ', condition, 'failed')
                except:
                    if debug:
                        print('Exception during test')
                    pass

        # does input meet all conditions in conditions_all?

        if len(conditions_all) > 0:
            for condition in conditions_all:
                if debug:
                    print('Testing condition', condition[0])
                try:
                    if eval(condition[0]):
                        if debug:
                            print('Test of ', condition[0], 'passed')
                        pass
                    else:
                        if debug:
                            print('Test of ', condition[0], 'failed')
                        validated_all = False
                        print(condition[1])
                except:
                    if debug:
                        print('Exception during test')
                    validated_all = False
                    print(condition[1])

        if not validated_any:
            print(error_string, '\n')
        elif validated_all:
            input_validated = True
    return X


