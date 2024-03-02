# Screen Builder

The screen builder allows you to make the entire layout of your screens using just the configuration yaml.

## Module name
To use the screen builder you need to set the module to `module: pyefis.screens.screenbuilder`
```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
```

## Screen Layout
The next thing you need to do is define a layout grid for your screen.

To specify the grud you need to define the `columns:` and `rows:` that make up your grid.
The first column and row is 0

For a Six Pack using `rows: 2` and `columns: 3` makes sense.
If you are doing more complex layouts you can make the number of grids really high.
For example if your screen is 640 x 480, you could set `columns: 640` and `rows: 480`, now you can place gauges by the pixel.
Also consider that if you want to share your screen with others they might need a different resolution. Selecting a grid size that is easy to calculate might make more sense such as 600x400, the center if the screen would be `column: 300` and `row:200` sightly easier to calaulate than `320/220`
```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 300
      rows: 200
```

## Drawing a Grid on the Screen
While building your screen it might be helpful to have a grid overlayed on the screen so you could preview what it looks like and use the grid to help determine what row/column is needed to place an instrument where you want it.
To do this you can add the option `draw_grid: true` under layout:
```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 300
      rows: 200
      draw_grid: true
```
![Grid Image](/docs/images/draw_grid.png)

## Margins
Maybe you do not want instruments showing up behind the menu or some other customization you have made. Setting a margin will exclude that region from your grid so no gauges will be placed in that area.

Margins are defined under `layout:` using the key `margin:`

In this example we will exclude the top 10% and left 10% of the screen:

```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 300
      rows: 200
      margin:
        top: 10
        left: 10
```
![Margin Image](/docs/images/margin.png)

Margins are specified in percentage, not grid or pixels, to hopefully allow screens to work well for others that might have a different resolution.
You can specify margins for `top`, `bottom`, `left` and `right`

## Instruments / Gauges
The next section is `instruments:` where you define exactly what you want on the screen.
`instruments:` is a list, and rendered from top to bottom allowing you to place instruments on top of other instruments by simply changing the order
At a minimum an instruments must have `type:`, `row:` and `column:`

`type:` defines the type of instrument you want to use<br>
`row:` Specifies what row on the grid will be the top left corner of the instrument<br>
`column:` Specifies what column will be the top left corner of the instrument

Example placing the airspeed dial at the top left:
```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 300
      rows: 200
    instruments:
      - type: airspeed_dial
        row: 0
        column: 0
```
### Span
The next most useful option is `span:` which allows the instrument to span columns to the right and rows down.
Back to the example grid of 300 x 200. 

If you want the six gauges evenly places with three on top and two rows high:<br>

set the height to:<br>
`200 / 2 = 100`<br>
and the columns to<br>
`300 / 3 = 100`<br>

You can drop any decimals from your calculations. It is OK that the rows and columns do not match, the gauge will be as large as possible to fit in that area but will not be distorted. The default is to center vertically and horizontally.

```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 640
      rows: 480
      margin:
        bottom: 10
    instruments:
      - type: airspeed_dial
        row: 0
        column: 0
        span:
          rows: 100
          columns: 100
```
In the screen I highlighted 100x100 with blue, you can see the gauge is centered in that 100x100 area:
![Span Image](/docs/images/span.png)

### Move
The next option is `move:` that provides two options `shrink:` and `justify:`

Shrink allows you to shrink an item by percentage and justify allows you to shift it to the top, bottom, right or left. By default if you shrink without justify it will be centered.


```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 300
      rows: 200
    instruments:
      - type: airspeed_dial
        row: 0
        column: 0
        span:
          rows: 100
          columns: 100
        move:
          shrink: 50
```
The ASI is 50% smaller and centered in the 100x100 span specified:

![Span Image](/docs/images/shrink.png)

A more useful example for shrink would be to place a `horizontal_situation_indicator` over an `attitude_indicator`, placing both in the same row/column and span will be them centered to one another, then you can shrink the `horizontal_situation_indicator` to the size you desire.

### Options
Some instruments have options, for example the HSI has the options `gsi_enabled` and `cdi_enabled` that can enable the glide slope indicator or the course deviation indicator
We will add those options to the HSI along with some shrink and justify to provide additional examples:
```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 300
      rows: 200
    instruments:
      - 
        type: horizontal_situation_indicator
        options:
          gsi_enabled: true
          cdi_enabled: true
        row: 100
        column: 100
        span:
          rows: 100
          columns: 100
        move:
          shrink: 10
          justify:
            - bottom
      -
        type: heading_display
        column: 100
        row: 100
        span:
          rows: 100
          columns: 100
        move:
          shrink: 80
          justify:
            - top
```
![Options Image](/docs/images/options_move.png)

#### FIX db keys
Some instruments, primarily gauges do not have default FIX db keys associated with them. In these cases you just specify the option `dbkey:`

Here is an example instrument for a tachometer:

```
      -
        type: arc_gauge
        row: 1
        column: 1
          options:
            name: RPM
            dbkey: TACH1
            decimalPlaces: 0
``` 

### Ganged Instruments
Ganged instruments are perfect for when you want to configure a column or row of instruments. To use them you simply prefix the instrument type with `ganged_`

For example `ganged_arc_gauge`

The default is to gang them vertically, if you want to gang horizontally you must specify the `gang_type:` key:

```
      -
        type: ganged_vertical_bar_gauge
        gang_type: horizontal

```

#### Groups
Each instrument in a gang must belong to a gang group. Each gang group will be slightly sperated on the screen to visually sperate each group from one another.


It is acceptable to only have a single group.
In our example the first group will be `Power`

It is not necessary to specify the `type` for each instrument in the gang, that is inhereted from the type of the gang such as `ganged_vertical_bar_gauge`

You can give the group a name, tho currently nothing is done with the name internally. Within the groups you speciy a list of `instruments:` where all you need to specify are the options unique to that instrument in the group.

```
      -
        type: ganged_vertical_bar_gauge
        gang_type: horizontal
        row: 8
        column: 1
        span:
          rows: 5
          columns: 27
        groups:
          - name: Power
            instruments:
              -
                options:
                  name: Volt
                  decimapPlaces: 1
                  showUnits: false
                  dbkey: VOLT
              -
                options:
                  name: Amp
                  showUnits: false
                  dbkey: CURRNT

```

#### Common Options #####

`common_options` can be specifed for each gang group and will be applied to all instruments defined in that group. If the same option is specified in `common_options:` and the instrument `options:`, the value defined for the instrument will be used for that instrument.

If you have a group of EGT instruments you should specify these common_options to enable the EGT mode switching for normalized/peak/lean etc.

```
          - name: EGT
            common_options:
              egt_mode_switching: true
              normalizeRange: 400
            instruments:

```

Following along with the example, here are the two groups for Power and EGT for a 4 cylinder engine:
```
      -
        type: ganged_vertical_bar_gauge
        gang_type: horizontal
        row: 8
        column: 1
        span:
          rows: 5
          columns: 27
        groups:
          - name: Power
            instruments:
              -
                options:
                  name: Volt
                  decimapPlaces: 1
                  showUnits: false
                  dbkey: VOLT
              -
                options:
                  name: Amp
                  showUnits: false
                  dbkey: CURRNT
          - name: EGT
            common_options:
              egt_mode_switching: true
              normalizeRange: 400
            instruments:
              -
                options:
                  name: "1"
                  decPlaces: 0
                  showUnits: false
                  dbkey: EGT11
              -
                options:
                  name: "2"
                  decPlaces: 0
                  showUnits: false
                  dbkey: EGT12
              -
                options:
                  name: "3"
                  decPlaces: 0
                  showUnits: false
                  dbkey: EGT13
              -
                options:
                  name: "4"
                  decPlaces: 0
                  showUnits: false
                  dbkey: EGT14

```

#### Instrument Includes ####
The configuration file can start to become quite large and you might want to reuse the same instrument configs on different screens. For this you can use the include option.<br>
This will include the file config/includes/side-buttons.yaml:
```
    instruments:
      - type: include,config/includes/side-buttons.yaml
```
If You wanted to use those same buttons on every screen just include them in every screen.

Include files are made just like the default.yaml file except the top level is `instruments:`
```
instruments:
  - type: button
    row: 2
    column: 376
    span:
      rows: 15
      columns: 24
    options:
      config: config/buttons/screen-ems-pfd.yaml
```
All of the instruments are defined the same as in the default.yaml
Currently you cannot use includes inside of includes.

##### Include relative #####
When defining includes you can assume that each instrument starts at 0.
Then within the main config you can define `relative: true` along with row and column and the instruments in the include will be rendered starting at the defined row and column.  This allows you to define something complex such as AHRS with heading and such then reuse that definition on various screens and different locations on the screen.

##### Include scaling #####
If you want to use use an include but want it to be a different size simply specify `span` with the row and columns you want the include to occupy.
```
    instruments:
      - type: include,includes/virtual_vfr.yaml
        relative: true
        row: 0
        column: 0
        span:
          rows: 55
          columns: 77.5
```

# Instrument List #
Below is a list of the instrument types, defaults and options. This is a WIP and is mostly incomplete. Basically an option is any properly of the instrument that is defined in its source. Currenlty not many options have common names, one instrument might use font_size where another is fontsize or fontSize. Hopefully the community can decide on some common naming and update the code to make maintaining the list here much easier.

To add a button you need to spcify the option `config:` that points to the yaml file with the configuration for the button:
```
      - type: button
        row: 70
        column: 75
        span:
          rows: 15
          columns: 10
        options:
          config: config/buttons/trim-up-invisible.yaml
```


## airspeed_dial

![Airspeed Dial](/docs/images/airspeed_dial.png)

## airspeed_box

## airspeed_tape

![Airspeed Tape](/docs/images/airspeed_tape.png)

## airspeed_trend_tape

## altimeter_dial

![Altimeter Dial](/docs/images/altimeter_dial.png)

## altimeter_tape

![Airspeed Tape](/docs/images/altimeter_tape.png)

## altimeter_trend_tape

![Altimeter Trend Tape](/docs/images/altimeter_trend_tape.png)

## atitude_indicator

![Atitude Indicator](/docs/images/atitude_indicator.png)

## arc_gauge

![Arc Gauge](/docs/images/arc_gauge.png)

## button

Buttons should not be confused with the menu tho one could replace the menu with buttons if desired. The idea behind buttons is to provide an interactive instrument that can display data, change state such as color in response to data and perform actions within the system. The motivation to create this was because I wanted to place some physical buttons along each side of the screen so the pilot and co-pilot would have easy access to the buttons. Next to each physical button on the screen would be a button that shows the status of some option. For example, while viewing the Primary Flight Display screen if an engine item annunciates the button labeled EMS will turn red to indicate an alert condition. Pressing the button will take you to the EMS screen.  While viewing the EMS screen the button text changed to PFD, pressing it will take you back to the PFD screen.
<br>
Example buttons:<br>
![EMS Gray](/docs/images/ems-gray.png)<br>
![EMS Red](/docs/images/ems-red.png)

### Adding a button
To add a button you need to spcify the option `config:` that points to the yaml file with the configuration for the button:
```
      - type: button
        row: 70
        column: 75
        span:
          rows: 15
          columns: 10
        options:
          config: config/buttons/trim-up-invisible.yaml
```

### Button configuration
Every button needs to have `type:` `text:` and `dbkey:` defined.i
```
type: simple
text: ""
dbkey: BTN6
```

### dbkey and physical buttons
dbkey must be a boolean and can be used for a physical button input too.
Three types of buttons:
simple: <br>
A simple button is like a momentary pushbutton. It will perform some action when pressed then go back to the non-pressed state. It does not repeat actions if held down.
You could trigger a press by pressing the button with touchscreen or mouse or by setting dbkey to True
toggle:<br>
A toggle button is either on or off, it will perform actions when pressed or released.
You could trigger on by setting dbkey to True and off by setting dbkey to False
repeat:<br>
A repeat button is the same as a simple button however it will repeat actions if it is held down.
<br>
Example buttons with invisible background color overlayed on top of a vertical bar gauge to control and show position of a trim tab:<br>
![Trim Pitch](/docs/images/trim-pitch.png)


### Condition keys
The next option that might be useful is `condition_keys:`
This optional option allows you to define what FIX db items this button needs to use within conditions to make decisions on what action to perform. This is an array of one or more FIX db keys
```
type: simple
text: ""
dbkey: BTN6
condition_keys:
  - CHT11
  - CHT12
  - CHT13
  - CHT14
  - EGT11
  - EGT12
  - EGT13
  - EGT14
```

### Conditions

The `conditions:` key is an array of conditions, then when true, will execute the actions defined. 
```
conditions:
  - when: "SCREEN eq 'EMS'"
    actions:
      - set text: PFD
      - set bg color: lightgray
    continue: true
```
In the example above `when:` is the condition where we are checking if the SCREEN the button is on is the screen named EMS. This condition will be evaluated whenever dbkey or any of the confition_keys changes. If `when:` evaluates to true the actions specified will be executed. By default once a condition evaluates to true no other conditions will be evaluated. But in this example the option `continue: true` is included which allows the following conditions to also be evaluated.<br>

All of the conditions are evaluated using the library `pycond`, you can read its documentation if you need help making conditions but normally `eq`, `ne`, `and`, `or` and the breackets `[]` are suffecient to make condition statements.

### Variables

the dbkey and condition_keys are avaliable to use in the conditions. If you included `CHT11` as a dbkey or condition_key you can use CHT11 as a variable in the condition statement. For all FIX db items variables or `old`, `bad` etc and aux values are also avaliable.
```
KEY.old
KEY.bad
KEY.fail
KEY.annunciate
KEY.aux.min
KEY.aux.max
etc etc
```

In addition to those variables the variables `CLICKED` and `SCREEN` are also provided.
SCREEN will contain the value of the screen name
CLICKED will be true if the user has clicked the button to trigger evaluation of the conditions and false if the evaluation was triggered from just data changes.

Here is a list of all the actions:

  * set airspeed mode: 
  * set egt mode: 
  * show next screen: true
  * show previous screen: true
  * set value: KEY,value
  * change value:  KEY,0.1
  * toggle value:  true
  * activate menu item: 1
  * activate menu: MENU_NAME
  * menu encoder: <VALUE>
  * set menu focus:
  * set instrument units:
  * exit: true
  * set bg color: #hex or predefined qt color name
  * set fg color: #hex or predefined qt color name
  * set text: See Below
  * button: (disable|enable|checked|unchecked)

### Button Text
When using the action `set text:` setting static text is always an option such as `set text: EMS` resulting in the button saying `EMS` You can also use any of the variables used in conditions by simply putting curly brackets around the variable name such as `set text: {CHT11}`

While attempts were made to prevent loops it is still possible to trigger them. To avoid them do not create an action in a button that changes its own dbkey. Instead use `button:checked` or `button:unchecked`
Avoid taking actions on button 'A' that cause button 'B' to take actions on button 'A'
The order of conditions and actions does matter. Avoiding loops and unexpected behaviour can be accomplished with re-ording and limited use of continue.
disabeling a button does not prevent it from evaluating conditions and performing actions. It only prevent a user from clicking a button. Using the variable `CLICKED` in your conditions can be very useful to distinguise between user initiated actions and FIX db values initiating actions.


## heading_display

![Heading Display](/docs/images/heading_display.png)

## heading_tape

![Heading Tape](/docs/images/heading_tape.png)

## horizontal_bar_gauge

![Horizontal Bar Gauge](/docs/images/horizontal_bar_gauge.png)

## horizontal_situation_indicator

![Horizontal Situation Indicator](/docs/images/horizontal_situation_indicator.png)

## numeric_display

## static_text

## turn_coordinator

![Turn Coordinator](/docs/images/turn_coordinator.png)

## value_display

## vertical_bar_gauge

![Vertical Bar Gauge](/docs/images/vertical_bar_gauge.png)

## virtual_vfr

![Virtual VFR](/docs/images/virtual_vfr.png)

## vsi_dial

![VSI Dial](/docs/images/vsi_dial.png)

## vsi_pfd

![VSI PFD](/docs/images/vsi_pfd.png)

