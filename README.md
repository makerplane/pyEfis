# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/makerplane/pyEfis/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                    |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|-------------------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/pyefis/\_\_init\_\_.py                              |        1 |        0 |        0 |        0 |    100% |           |
| src/pyefis/cfg.py                                       |       79 |        0 |       70 |        0 |    100% |           |
| src/pyefis/common/\_\_init\_\_.py                       |       10 |        0 |        4 |        0 |    100% |           |
| src/pyefis/gui.py                                       |      187 |        0 |       60 |        0 |    100% |           |
| src/pyefis/hmi/\_\_init\_\_.py                          |       13 |        0 |        2 |        0 |    100% |           |
| src/pyefis/hmi/actionclass.py                           |       29 |        0 |        4 |        0 |    100% |           |
| src/pyefis/hmi/data.py                                  |       75 |       62 |       34 |        0 |     12% |36-64, 68-88, 92-108, 112-116, 120-126 |
| src/pyefis/hmi/functions.py                             |       15 |        0 |        0 |        0 |    100% |           |
| src/pyefis/hmi/keys.py                                  |       50 |       37 |       24 |        0 |     18% |30-49, 52-53, 57-59, 63-65, 69-82 |
| src/pyefis/hmi/menu.py                                  |      176 |      141 |       50 |        0 |     15% |36-84, 87-88, 91-119, 121-125, 128-130, 133, 136-148, 151-157, 160-174, 177-182, 186-200, 203, 206, 209, 212, 215, 218, 221, 226-227, 230-231, 234, 237-240, 243 |
| src/pyefis/hooks.py                                     |       14 |       14 |        4 |        0 |      0% |     17-37 |
| src/pyefis/instruments/NumericalDisplay/\_\_init\_\_.py |      202 |        0 |       42 |        0 |    100% |           |
| src/pyefis/instruments/\_\_init\_\_.py                  |        0 |        0 |        0 |        0 |    100% |           |
| src/pyefis/instruments/ai/VirtualVfr.py                 |      805 |      499 |      244 |       22 |     33% |134-157, 187-\>exit, 191-216, 219-231, 235-436, 440-466, 470-490, 493-497, 500-524, 527-533, 536-542, 545-551, 554-559, 562-\>exit, 572-585, 588, 591, 594, 597, 605-618, 621, 624, 627, 630, 637-656, 659, 662, 665, 668, 674-682, 715, 725-728, 731-735, 738, 750-\>752, 763, 768, 770-\>772, 815, 821-\>819, 835-859, 861, 863, 868-869, 884, 886, 899-905, 914-918, 926-929, 937-947, 956, 958, 966-984, 987-991, 994-998, 1005-1017, 1022-1058 |
| src/pyefis/instruments/ai/\_\_init\_\_.py               |      398 |        0 |       72 |        0 |    100% |           |
| src/pyefis/instruments/airspeed/\_\_init\_\_.py         |      346 |        0 |       72 |        0 |    100% |           |
| src/pyefis/instruments/altimeter/\_\_init\_\_.py        |      260 |        0 |       38 |        0 |    100% |           |
| src/pyefis/instruments/button/\_\_init\_\_.py           |      245 |        0 |      104 |        0 |    100% |           |
| src/pyefis/instruments/gauges/\_\_init\_\_.py           |        5 |        0 |        0 |        0 |    100% |           |
| src/pyefis/instruments/gauges/abstract.py               |      456 |        0 |      168 |        0 |    100% |           |
| src/pyefis/instruments/gauges/arc.py                    |      223 |        0 |       66 |        0 |    100% |           |
| src/pyefis/instruments/gauges/egt.py                    |       70 |       60 |       30 |        0 |     10% |28-52, 55-84, 89-96 |
| src/pyefis/instruments/gauges/horizontalBar.py          |      131 |        0 |       34 |        0 |    100% |           |
| src/pyefis/instruments/gauges/numeric.py                |       60 |        0 |       10 |        0 |    100% |           |
| src/pyefis/instruments/gauges/verticalBar.py            |      245 |        0 |       72 |        0 |    100% |           |
| src/pyefis/instruments/helpers/\_\_init\_\_.py          |       40 |        0 |       16 |        0 |    100% |           |
| src/pyefis/instruments/hsi/\_\_init\_\_.py              |      461 |        0 |      102 |        0 |    100% |           |
| src/pyefis/instruments/listbox/\_\_init\_\_.py          |      213 |        0 |       58 |        0 |    100% |           |
| src/pyefis/instruments/misc/\_\_init\_\_.py             |      167 |        0 |       20 |        0 |    100% |           |
| src/pyefis/instruments/pa/\_\_init\_\_.py               |       70 |       29 |       10 |        1 |     52% |60-72, 75, 79-95, 98 |
| src/pyefis/instruments/tc/\_\_init\_\_.py               |      220 |        0 |       40 |        0 |    100% |           |
| src/pyefis/instruments/vsi/\_\_init\_\_.py              |      382 |        0 |       68 |        0 |    100% |           |
| src/pyefis/instruments/weston/\_\_init\_\_.py           |       57 |       46 |       14 |        0 |     15% |13-61, 65-76 |
| src/pyefis/instruments/wind/\_\_init\_\_.py             |      109 |        8 |       14 |        4 |     90% |43-45, 92-93, 117-118, 148, 154-\>170, 162 |
| src/pyefis/main.py                                      |      149 |      149 |       62 |        0 |      0% |    18-248 |
| src/pyefis/screens/\_\_init\_\_.py                      |        0 |        0 |        0 |        0 |    100% |           |
| src/pyefis/screens/screenbuilder.py                     |      199 |        0 |       68 |        0 |    100% |           |
| src/pyefis/screens/screenbuilder\_config.py             |      135 |        0 |       78 |        0 |    100% |           |
| src/pyefis/screens/screenbuilder\_display.py            |       31 |        0 |       14 |        0 |    100% |           |
| src/pyefis/screens/screenbuilder\_encoder.py            |       89 |        0 |       46 |        0 |    100% |           |
| src/pyefis/screens/screenbuilder\_factory.py            |       48 |        0 |        8 |        0 |    100% |           |
| src/pyefis/screens/screenbuilder\_layout.py             |      129 |        0 |       70 |        0 |    100% |           |
| src/pyefis/screens/screenbuilder\_options.py            |       41 |        0 |       20 |        0 |    100% |           |
| src/pyefis/screens/screenbuilder\_overlay.py            |       46 |        0 |       10 |        0 |    100% |           |
| src/pyefis/screens/screenbuilder\_preferences.py        |       31 |        0 |       28 |        0 |    100% |           |
| src/pyefis/user/\_\_init\_\_.py                         |        0 |        0 |        0 |        0 |    100% |           |
| src/pyefis/user/hooks/\_\_init\_\_.py                   |        0 |        0 |        0 |        0 |    100% |           |
| src/pyefis/user/hooks/composite.py                      |      103 |      103 |       26 |        0 |      0% |    22-165 |
| src/pyefis/user/hooks/keys.py                           |       19 |       19 |        4 |        0 |      0% |     20-53 |
| src/pyefis/user/screens/\_\_init\_\_.py                 |        0 |        0 |        0 |        0 |    100% |           |
| src/pyefis/version.py                                   |        2 |        0 |        0 |        0 |    100% |           |
| **TOTAL**                                               | **6836** | **1167** | **1980** |   **27** | **82%** |           |


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