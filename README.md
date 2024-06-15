# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/makerplane/pyEfis/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                    |    Stmts |     Miss |   Cover |   Missing |
|-------------------------------------------------------- | -------: | -------: | ------: | --------: |
| src/pyefis/\_\_init\_\_.py                              |        1 |        0 |    100% |           |
| src/pyefis/cfg.py                                       |       79 |        0 |    100% |           |
| src/pyefis/common/\_\_init\_\_.py                       |       10 |        0 |    100% |           |
| src/pyefis/gui.py                                       |      189 |      189 |      0% |    17-282 |
| src/pyefis/hmi/\_\_init\_\_.py                          |       13 |        0 |    100% |           |
| src/pyefis/hmi/actionclass.py                           |       30 |        0 |    100% |           |
| src/pyefis/hmi/data.py                                  |       77 |       62 |     19% |38-66, 70-90, 94-110, 114-118, 122-128 |
| src/pyefis/hmi/functions.py                             |       15 |        0 |    100% |           |
| src/pyefis/hmi/keys.py                                  |       50 |       37 |     26% |30-49, 52-53, 57-59, 63-65, 69-82 |
| src/pyefis/hmi/menu.py                                  |      176 |      141 |     20% |36-84, 87-88, 91-119, 121-125, 128-130, 133, 136-148, 151-157, 160-174, 177-182, 186-200, 203, 206, 209, 212, 215, 218, 221, 226-227, 230-231, 234, 237-240, 243 |
| src/pyefis/hooks.py                                     |       14 |       14 |      0% |     17-37 |
| src/pyefis/instruments/NumericalDisplay/\_\_init\_\_.py |      202 |        1 |     99% |       291 |
| src/pyefis/instruments/\_\_init\_\_.py                  |        0 |        0 |    100% |           |
| src/pyefis/instruments/ai/VirtualVfr.py                 |      816 |      816 |      0% |   17-1075 |
| src/pyefis/instruments/ai/\_\_init\_\_.py               |      397 |      397 |      0% |    17-548 |
| src/pyefis/instruments/airspeed/\_\_init\_\_.py         |      346 |        1 |     99% |       295 |
| src/pyefis/instruments/altimeter/\_\_init\_\_.py        |      259 |      259 |      0% |    17-372 |
| src/pyefis/instruments/button/\_\_init\_\_.py           |      257 |      257 |      0% |    20-371 |
| src/pyefis/instruments/gauges/\_\_init\_\_.py           |        5 |        0 |    100% |           |
| src/pyefis/instruments/gauges/abstract.py               |      451 |      211 |     53% |136, 149, 167-179, 182, 219, 224, 259-260, 277-278, 282-290, 326, 330, 332, 334, 336, 341-342, 345-350, 353-354, 357-358, 366-370, 373-388, 393, 398-418, 422-440, 444-480, 483-531, 548-558, 562-608, 612-624, 627-672, 676-682 |
| src/pyefis/instruments/gauges/arc.py                    |      224 |        2 |     99% |     56-57 |
| src/pyefis/instruments/gauges/egt.py                    |       70 |       60 |     14% |28-52, 55-84, 89-96 |
| src/pyefis/instruments/gauges/horizontalBar.py          |      131 |        0 |    100% |           |
| src/pyefis/instruments/gauges/numeric.py                |       60 |        0 |    100% |           |
| src/pyefis/instruments/gauges/verticalBar.py            |      245 |        0 |    100% |           |
| src/pyefis/instruments/helpers/\_\_init\_\_.py          |       49 |       11 |     78% |22-24, 35-38, 48-51 |
| src/pyefis/instruments/hsi/\_\_init\_\_.py              |      461 |      461 |      0% |    17-632 |
| src/pyefis/instruments/listbox/\_\_init\_\_.py          |      211 |      211 |      0% |     5-313 |
| src/pyefis/instruments/misc/\_\_init\_\_.py             |      167 |        0 |    100% |           |
| src/pyefis/instruments/pa/\_\_init\_\_.py               |       70 |       70 |      0% |    17-104 |
| src/pyefis/instruments/tc/\_\_init\_\_.py               |      220 |      220 |      0% |    18-324 |
| src/pyefis/instruments/vsi/\_\_init\_\_.py              |      382 |      382 |      0% |    17-537 |
| src/pyefis/instruments/weston/\_\_init\_\_.py           |       41 |       41 |      0% |      1-48 |
| src/pyefis/main.py                                      |      158 |      158 |      0% |    18-254 |
| src/pyefis/screens/\_\_init\_\_.py                      |        0 |        0 |    100% |           |
| src/pyefis/screens/ems\_sm.py                           |       99 |       99 |      0% |    17-341 |
| src/pyefis/screens/epfd.py                              |      104 |      104 |      0% |    17-151 |
| src/pyefis/screens/pfd.py                               |      123 |      123 |      0% |    17-224 |
| src/pyefis/screens/pfd\_sm.py                           |      108 |      108 |      0% |    17-169 |
| src/pyefis/screens/r582\_sm.py                          |       98 |       98 |      0% |    17-210 |
| src/pyefis/screens/screenbuilder.py                     |      700 |      700 |      0% |    17-956 |
| src/pyefis/screens/sixpack.py                           |       53 |       53 |      0% |     17-88 |
| src/pyefis/screens/test.py                              |       21 |       21 |      0% |     17-48 |
| src/pyefis/user/\_\_init\_\_.py                         |        0 |        0 |    100% |           |
| src/pyefis/user/hooks/\_\_init\_\_.py                   |        0 |        0 |    100% |           |
| src/pyefis/user/hooks/composite.py                      |      103 |      103 |      0% |    22-165 |
| src/pyefis/user/hooks/keys.py                           |       19 |       19 |      0% |     20-53 |
| src/pyefis/user/screens/\_\_init\_\_.py                 |        0 |        0 |    100% |           |
| src/pyefis/version.py                                   |        2 |        0 |    100% |           |
|                                               **TOTAL** | **7306** | **5429** | **26%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/makerplane/pyEfis/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/makerplane/pyEfis/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/makerplane/pyEfis/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/makerplane/pyEfis/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fmakerplane%2FpyEfis%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/makerplane/pyEfis/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.