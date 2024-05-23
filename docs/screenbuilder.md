# Screen Builder

The screen builder allows you to make the entire layout of your screens using just the configuration yaml.

## main section ##
The `main` section of the configuration file contains an option `nodeID` that is used to identify the specific node this config belongs to. This is useful if you have more than one display allowing you to assign a unique id to each display.<br>
Within screen configurations you can create values with `{id}` where `{id}` will be replaced with the value in set for `nodeID`<br>
The most obvious place where this is useful is for touchscreen buttons. Such buttons can be associated with physical buttons too so we need a way to identify if the pilot pressed the button or if the co-pilot pressed the button. The example configuration file `buttons/screen-ems-pfd.yaml` is a button that changes the screen between PFD and EMS. We don't want both displays to change when a button is pressed, only the display that the button belongs to.<br>
Looking at the configuration we see how each screen, with a unique `nodeID` would have a unique db key for the button:
```
type: simple
text: ""
dbkey: TSBTN{id}12
```
In this example `nodeID: 1` would use key `TSBTN112` where `nodeID: 2` would use `TSBTN212`

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
Also consider that if you want to share your screen with others they might need a different resolution. Selecting a grid size that is easy to calculate might make more sense such as 600x400, the center if the screen would be `column: 300` and `row:200` sightly easier to calaulate than `320/220`<br>
To make sharing and exchanging screens with other users all screens and includes distributed with pyEFIS are defined with `columns: 200` and `rows: 110` This is close to 16:9 ratio matching the majority of screens on the market today. Typically any screen will work, un-modified, at any resoltion but somtimes it is necessary to specify `font_mask` option to ensure text will be sized to always fit the amount of text in the mask. 
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

A more useful example for shrink would be to place a `horizontal_situation_indicator` over an `attitude_indicator`, placing both in the same row/column and span so they are centered to one another, then you can shrink the `horizontal_situation_indicator` to the size you desire.

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
            decimal_places: 0
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
                  decimal_places: 1
                  show_units: false
                  dbkey: VOLT
              -
                options:
                  name: Amp
                  show_units: false
                  dbkey: CURRNT

```

#### Common Options #####

`common_options` can be specifed for each gang group and will be applied to all instruments defined in that group. If the same option is specified in `common_options:` and the instrument `options:`, the value defined for the instrument will be used for that instrument.

If you have a group of EGT instruments you should specify these common_options to enable the EGT mode switching for normalized/peak/lean etc.

```
          - name: EGT
            common_options:
              egt_mode_switching: true
              normalize_range: 400
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
                  decimal_places: 1
                  show_units: false
                  dbkey: VOLT
              -
                options:
                  name: Amp
                  show_units: false
                  dbkey: CURRNT
          - name: EGT
            common_options:
              egt_mode_switching: true
              normalize_range: 400
            instruments:
              -
                options:
                  name: "1"
                  decPlaces: 0
                  show_units: false
                  dbkey: EGT11
              -
                options:
                  name: "2"
                  decPlaces: 0
                  show_units: false
                  dbkey: EGT12
              -
                options:
                  name: "3"
                  decPlaces: 0
                  show_units: false
                  dbkey: EGT13
              -
                options:
                  name: "4"
                  decPlaces: 0
                  show_units: false
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

All of the instruments are defined the same as in the default.yaml<br>
You can use an include inside of another include. Just be sure to not create recursive includes!<br>
An example of this in `default.yaml` that includes `config/includes/mgl/v16/radio-display.yaml` that includes `config/includes/mgl/v16/active-display.yaml`, `config/includes/mgl/v16/standby-display.yaml` and `config/includes/mgl/v16/volumes.yaml` On another screen in `default.yaml` `config/includes/mgl/v16/active-display.yaml` is included too.

##### Include replacements #####
Somtimes it might be useful to reuse an include for multiple devices. For example, maybe you have two com radios. You can create a single set of includes that make up the radio, but use the replacement feature to control what instance belongs to what radio. <br>

This example we include the radio active display and define a replacement for radio_id:
```
      - type: include,includes/mgl/v16/active-display.yaml
        row: 70
        column: 156
        span:
          rows: 40
          columns: 45
        display_state: 2
        replace:
          radio_id: 1
```

Inside active-display.yaml, any value with `{radio_id}` will be replaced with `1` The active-display.yaml defines some dbkeys using `{radio_id}`:
```
      dbkey: COMACTFREQ{radio_id}
```
That would make the actual dbkey used to be `COMACTFREQ1`


##### Include relative #####
When defining includes you can assume that each instrument starts at 0.
Then within the main config you can define a row and column and the instruments in the include will be rendered starting at the defined row and column.  This allows you to define something complex such as AHRS with heading and such then reuse that definition on various screens and different locations on the screen.

##### Include scaling #####
If you want to use use an include but want it to be a different size simply specify `span` with the row and columns you want the include to occupy.
```
    instruments:
      - type: include,includes/virtual_vfr.yaml
        row: 0
        column: 0
        span:
          rows: 55
          columns: 77.5
```

# Encoder control
pyEFIS can be controlled using a single rotary encoder with button. When the encoder is rotated an item on the screen will turn orange to indicate the selected item. While an item is selected if you rotate the encoder the selection will move to the next item. Pressing the button will either perform the action that is selected, such as a touchscreen button, or pass control over the encoder to the selected item such as a listbox. Once control is passed over to an item the behavior will depend on the specific item. after a period of time thetimeout will cause the screen to revert its default state with nothing selected<br>

## listbox control
To select the listbox rotate the encoder until the title of the listbox is orange. Then press the button.  Now when you rotate the encoder the selected row in the listbox will change, pressing the button will perform the action of the selected row in the listbox. The listbox is unique in that it only relenquishes control of the encoder when selecting an item from this list. It will retain control when using sort or list loading features.

## arc_gauge, horizontal_bar_gauge, vertical_bar_gauge and numeric_display
All four of these items behave the same, once you select an item by highlighting it and pressing the button the item will take control over the encoder. Rotating the encoder will change the value of the dbkey defined. Once you have the desired setting press the button and the value will be saved and the screen will revert to its default tate of nothing selected. If you decide to not change the value, do not press the button, let the timeout expire. When it times out the value will be reverted to its previous value and the screen will return to its default state.

## button
The buttons are simple, if you press the button while a on-screen button is highlighted, the action associated with that button will be performed. Since buttons can b disabled based on various conditions it is not possible to select disabled button.

## Controlling the order.
To control the order of slections you ned to specify an `encoder_order` for each instrument you want selectable. The recommended approach is to assign a range to each include config that has selectable items. The default configs included with pyEFIS use 11-20 for the touchscreen buttons, 21-30 for the radio components and 31-40 for the EGT mode buttons.<br>

here is an example of the buttons on the side of the screen being enabled for this feature and defining the order.<br>
pyefis/config/includes/side-buttons.yaml:
```
instruments:
  - type: ganged_button
    gang_type: vertical
    row: 0
    column: 0
    span:
      rows: 70
      columns: 14.5
    groups:
      - name: Side Buttons
        gap: 6
        common_options:
            font_mask: "ANDROID"
        instruments:
          -
            options:
              config: buttons/screen-ems-pfd.yaml
              encoder_order: 11
          -
            options:
              config: buttons/screen-ems2-pfd.yaml
              encoder_order: 12
          -
            options:
              config: buttons/screen-android-pfd.yaml
              encoder_order: 13
          -
            options:
              config: buttons/screen-radio-pfd.yaml
```

## Defining what encoder and button to use
Each screen needs to have the values `encoder` and `encoder_button` defined to enable this feature on the screen. These should be set to the dbkey for the encoder and button you want to use for controlling the screen.

Example from default.yaml file:
```
screens:
  SIXPACK:
    module: pyefis.screens.screenbuilder
    title: Standard Instrument Panel New
    encoder: ENC9
    encoder_button: BTN9
```


# Instrument List #
Below is a list of the instrument types, defaults and options. This is a WIP and is mostly incomplete. Basically an option is any properly of the instrument that is defined in its source. 


## airspeed_dial
An analog airspeed dial.

![Airspeed Dial](/docs/images/airspeed_dial.png)

Options:
  * bg_color - default black, example '#00000000'
  * font_family - default 'DejaVu Sans Condensed'
  * font_percent - default 0.07

## airspeed_box
A box that displays airspeed value, it can be switched between IAS, GS and TAS. Will change colors based on limits and status

Options:
  * font_family - default 'DejaVu Sans Condensed'


## airspeed_tape
Vertical airspeed tape with highlighted sections to indicate Vs, Vs0, Vno Vne and Vfe

![Airspeed Tape](/docs/images/airspeed_tape.png)

Options:
  * font_percent - default None
  * font_family - default 'DejaVu Sans Condensed'
  * font_mask - default '000'

## airspeed_trend_tape

Options:
  * font_family - default 'DejaVu Sans Condensed'

## altimeter_dial
Analog altimeter dial

![Altimeter Dial](/docs/images/altimeter_dial.png)

Options:
  * altitude
  * font_family - default 'DejaVu Sans Condensed'
  * bg_color - default black

## altimeter_tape
Vertical airspeed tape

![Airspeed Tape](/docs/images/altimeter_tape.png)

Options:
  * font_percent - default None
  * altitude
  * font_family - default 'DejaVu Sans Condensed'
  * font_mask - default 00000
  * dbkey - default 'ALT'
  * maxalt - default 50000

## altimeter_trend_tape

![Altimeter Trend Tape](/docs/images/altimeter_trend_tape.png)

Options
  * font_family - default 'DejaVu Sans Condensed'


## atitude_indicator
Digital atitude indicator

![Atitude Indicator](/docs/images/atitude_indicator.png)

Options:
  * font_percent - default None
  * font_family - default 'DejaVu Sans Condensed'

## arc_gauge
Digital arc gauge
Supports encoder selection and modification

![Arc Gauge](/docs/images/arc_gauge.png)
![Arc Gauge](/docs/images/arc_gauge_segmented.png)

Options:
  * segments - default 0 options: any integer, defines the number of segments to create
  * segment_gap_percent - default 0.01, defines size of gaps in segments
  * segment_alpha - default 180, 0-255, higher is darker
  * name_location - default 'top', options 'top', 'right'
  * decimal_places - How may decimals to display
  * name
  * dbkey
  * temperature - Defines value as temperature for unit switching
  * show_units - default False
  * font_family - default 'DejaVu Sans Condensed'
  * font_mask
  * units_font_mask
  * name_font_mask
  * font_ghost_mask
  * units_font_ghost_mask
  * name_font_ghost_mask
  * min_size - default True
  * bg_good_color - default black
  * safe_good_color - default green
  * warn_good_color - default yellow
  * alarm_good_color - default red
  * text_good_color - default white
  * pen_good_color - default white
  * highlight_good_color - default magenta
  * bg_bad_color - default black
  * safe_bad_color - default dark gray
  * warn_bad_color - default dark yellow
  * alarm_bad_color - default dark red
  * text_bad_color - default gray
  * pen_bad_colo - default gray
  * highlight_bad_color - default dark magenta

## button
Supports encoder selection and modification

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

Options:
  * config
  * font_mask
  * font_family

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

In addition to those variables the variables `DBKEY`, `CLICKED`, `SCREEN` and `PREVIOUS_CONDITION` are also provided.
DBKEY provides the boolean value of the button dbkey, mostly useful in toggle buttons where you might want to know if the state is pressed (true) or released (false).
SCREEN will contain the value of the screen name
CLICKED will be true if the user has clicked the button to trigger evaluation of the conditions and false if the evaluation was triggered from just data changes.
PREVIOUS_CONDITION is a boolean that contains the results of the previous condition evaluation. Can be used to implemented a sort of if/else between two conditions.

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
Analog heading display

![Heading Display](/docs/images/heading_display.png)

Options:
  * font_family - default 'DejaVu Sans Condensed'
  * bg_color - default black
  * fg_color - default gray

## heading_tape
Horizontal Heading Tape

Options:
  * font_family - default 'DejaVu Sans Condensed'


![Heading Tape](/docs/images/heading_tape.png)

## horizontal_bar_gauge
Digital horizontal bar gauge
Supports encoder selection and modification

![Horizontal Bar Gauge](/docs/images/horizontal_bar_gauge.png)
![Horizontal Bar Gauge Segmented](/docs/images/horizontal_bar_gauge_segmented.png)

Options:
  * segments - default 0 options: any integer, defines the number of segments to create
  * segment_gap_percent - default 0.01, defines size of gaps in segments
  * segment_alpha - default 180, 0-255, higher is darker
  * bar_divisor - default 4.5, changes how tall the bar is
  * show_value
  * show_units
  * show_name
  * font_family - default 'DejaVu Sans Condensed'
  * font_mask
  * units_font_mask
  * name_font_mask
  * font_ghost_mask
  * units_font_ghost_mask
  * name_font_ghost_mask
  * min_size - default True
  * bg_good_color - default black
  * safe_good_color - default green
  * warn_good_color - default yellow
  * alarm_good_color - default red
  * text_good_color - default white
  * pen_good_color - default white
  * highlight_good_color - default magenta
  * bg_bad_color - default black
  * safe_bad_color - default dark gray
  * warn_bad_color - default dark yellow
  * alarm_bad_color - default dark red
  * text_bad_color - default gray
  * pen_bad_colo - default gray
  * highlight_bad_color - default dark magenta


## horizontal_situation_indicator
Analog or digital situation indicator

![Horizontal Situation Indicator](/docs/images/horizontal_situation_indicator.png)

Options:
  * gsi_enabled: default False
  * cdi_enabled: default False
  * font_percent: - default None 
  * font_family - default 'DejaVu Sans Condensed'
  * fg_color - default white
  * bg_color - default black


## listbox
Displays and loads user-defined lists. Supports various sort options and can set values when items are selected. Useful for frequently needed items like radio frquencies or waypoints.
Supports encoder selection and modification

![Listbox](/docs/images/listbox.png)

Options:
  * font_family - default 'DejaVu Sans Condensed'
  * lists

### Create a list ###
When defining a listbox you need to specify the options `encoder_order`, if you are using an encoder and `lists`. Each item under list needs a `name` that will be displayed as the title of the list and a `file` that contains the actual list. Here is an example with two lists defined:

```
  - type: listbox
    row: 0
    column: 101
    span:
      rows: 40
      columns: 54
    options:
      encoder_order: 28
      lists:
        - name: Favorites
          file: lists/radio/favorites.yaml
        - name: Ohio
          file: lists/radio/ohio.yaml
```

The list box will provide an option to load a list so you can switch between all of the lists defined.<br>

The actual list file will define what options are presented to the user and what data is displayed.

The first section of a list is `display`, this defines the list of columns that will be displayed and what columns can be used to sort. When `sort` is set to true an option to sort by that column will be provided in the listbox. You can have 1 or more columns, only limited by your imagination.

This example defines three columns named `Name`, `Identifier` and `Frequency` where only `Name` and `Identifier` are sortable. 
```
display:
  columns:
    - name: Name
      sort: true
    - name: Identifier
      sort: true
    - name: Frequency
      sort: false #False is the default
```

The next section is the actual list of items to display in the listbox. Each item in the list should define keys using the exact values from the columns you created. Using our example above you should have a key named `Name`, `Identifier` and `Frequency`

```
list:
  - Name: Knox County
    Identifier: K4I3
    Frequency: 122.800 Mhz
```

The next thing you need to do is define what should happen when this item is selected. You can set one or more dbkeys to a value. That value can also contain the values from the columns. For example, if you wanted to set a dbkey to the `Name` of this selection simply specify `{Name}` in the set value.
```
  - Name: Knox County
    Identifier: K4I3
    Frequency: 122.800 Mhz
    set:
      COMACTFREQSET{radio_id}: 122800
      COMACTNAMESET{radio_id}: "{Name}"
```

Assuming the replace `radio_id` is set to 1, if the above row is selected then `COMACTFREQSET1` will be set to `122800` and `COMACTNAMESET1` will be set to `Knox County`

The last feature is the ability to associate a location with the item. Simply add the keys `lat` and `long` for example:
```
  - Name: John Glenn Int. Tower
    Identifier: KCMH
    Frequency:  132.700 Mhz
    lat: 39.9969467
    long: -82.8921592
    set:
      COMACTFREQSET{radio_id}: 132700
      COMACTNAMESET{radio_id}: "{Name}"
```

You could simply use `lat` and `long` in your dbkey set section, maybe useful if you were making a list of waypoints and want to send the location to the auto pilot. But you can also enable the list to sort by location where the list is sorted by the distance from your current location.
To enable this sort option add the key `location` with value `true` to the display section:
```
display:
  location: true
  columns:
    - name: Name
      sort: true
    - name: Identifier
      sort: true
    - name: Frequency
      sort: false
```

One last thing that might be useful, just like you can set a value using the data from each list item, such as `{Name}` or `{lat}` you can add arbitrary keys and use those in the set value section. The arbitrary keys would not be displayed in the interface.

The next two configurations would both set `EXAMPLEKEY` to `Just a test` to demonstrate how this might be used:
```
list:
  - Name: test
    arbitrary: Just
    set:
      EXAMPLEKEY: {arbitrary} a {Name}
```

```
list:
  - Name: Test
    set:
      EXAMPLEKEY: Just a test 
```

A more useful example of this feature:
```
list:
  - Name: Marion Municipal
    type: Airport
    set:
      WPNAME: {type} {Name}
  - Name: Giant Basket
    type: POI
    set:
      WPNAME: {type} {Name}
```

## numeric_display
Displays numeric values, changes colors based on limits and status.
Supports encoder selection and modification

![Numeric Display](/docs/images/numeric_display.png)

![Numeric Display with segmented font and ghosting](/docs/images/numeric_display_segmented_ghosting.png)

Options:
  * decimal_places - How may decimals to display
  * font_mask  
  * font_family - default 'DejaVu Sans Condensed'
  * units_font_mask
  * dbkey
  * pressure - Defines value as pressure for unit switching
  * altitude - Defines value as altitude for unit switching
  * temperature - Defines value as temperature for unit switching
  * show_units - true/false 
  * bg_good_color - default black
  * safe_good_color - default green
  * warn_good_color - default yellow
  * alarm_good_color - default red
  * text_good_color - default white
  * pen_good_color - default white
  * highlight_good_color - default magenta
  * bg_bad_color - default black
  * safe_bad_color - default dark gray
  * warn_bad_color - default dark yellow
  * alarm_bad_color - default dark red
  * text_bad_color - default gray
  * pen_bad_colo - default gray
  * highlight_bad_color - default dark magenta

## static_text

![Static Text](/docs/images/static_text.png)

Options:
  * font_family - default 'DejaVu Sans Condensed'
  * font_percent
  * font_mask
  * font_ghost_mask
  * font_ghost_alpha
  * text
  * alignment

## turn_coordinator

![Turn Coordinator](/docs/images/turn_coordinator.png)

Options:
  * font_family - default 'DejaVu Sans Condensed'
  * dial - default True

## value_text

![Value Text](/docs/images/value_text.png)

Options:
  * font_family - default 'DejaVu Sans Condensed'
  * font_ghost_mask
  * font_mask
  * dbkey
  * font_percent

## vertical_bar_gauge
Supports encoder selection and modification

![Vertical Bar Gauge](/docs/images/vertical_bar_gauge.png)
![Vertical Bar Gauge](/docs/images/vertical_bar_gauge_segmented.png)

Options:
  * segments - default 0 options: any integer, defines the number of segments to create
  * segment_gap_percent - default 0.012, defines size of gaps in segments
  * segment_alpha - default 180, 0-255, higher is darker
  * temperature - Defines value as temperature for unit switching
  * highlight_key - If the displayed value matches thie value of this key then the gauge is highlighted. Useful to highlight the max value ie CHTMAX1 or EGTMAX1
  * decimal_places - How may decimals to display
  * show_units - default True
  * show_value - default True
  * show_name - default True
  * small_font_percent - default 0.08
  * big_font_percent - default 0.10
  * bar_width_percent - default 0.3
  * line_width_percent - dfault 0.5
  * text_gap - default 3
  * dbkey
  * name
  * egt_mode_switching
  * normalize_range - default 0
  * font_family - default 'DejaVu Sans Condensed'
  * font_mask
  * units_font_mask
  * name_font_mask
  * font_ghost_mask
  * units_font_ghost_mask
  * name_font_ghost_mask
  * bg_good_color - default black
  * safe_good_color - default green
  * warn_good_color - default yellow
  * alarm_good_color - default red
  * text_good_color - default white
  * pen_good_color - default white
  * highlight_good_color - default magenta
  * bg_bad_color - default black
  * safe_bad_color - default dark gray
  * warn_bad_color - default dark yellow
  * alarm_bad_color - default dark red
  * text_bad_color - default gray
  * pen_bad_colo - default gray
  * highlight_bad_color - default dark magenta

## virtual_vfr

![Virtual VFR](/docs/images/virtual_vfr.png)

Options:
  * font_percent
  * font_family - default 'DejaVu Sans Condensed'
  * gsi

## vsi_dial

![VSI Dial](/docs/images/vsi_dial.png)

Options:
  * font_family - default 'DejaVu Sans Condensed'

## vsi_pfd

![VSI PFD](/docs/images/vsi_pfd.png)

Options:
  * font_family - default 'DejaVu Sans Condensed'
  * font_percent

## weston
Runs weston compositor inside pyEFIS and starts waydroid to display within it

Options:
  * socket
  * ini
  * command
  * args



# Preferences #
Preferences is a way to define various styles or options that can be turned on or off from a single configuration file. Obviously not everyone will have the exact same hardware so our example screens are unlikely to work for anyone without making numerous changes. Additionally, if someone wants slightly different options for a large portion of the instruments they would not want to edit those settings in dozens of places.

The goal with this is to hopefully develop example screens and preferences that meet most users needed so they can focus on using pyEFIS rather than tinkering with it.

## preferences.yaml & preferences.yaml.custom ##
This file contains the preferences and options avaliable by default. You should not edit this file, if you want to make changes edit the `preferences.yaml.custom` file.  The resulting preferences will be the combination of both files with the `preferences.yaml.custom` file overriding any conflicting settings in the two files.

### style ###
The style section is where you pick what style(s) you want applied.
Example selecting basic and segmented styles:
```
style:
- basic
- segmented
```

### styles ###
The styles section defines the various styles avaliable The schema is:
```
styles:
  TYPE_OF_GAUGE1:
    STYLE_NAME1:
      Settings needed to apply the style fo TYPE_OF_GAUGE1
    STYLE_NAME2:
      Settings needed to apply the style fo TYPE_OF_GAUGE1
  TYPE_OF_GAUGE2:
    STYLE_NAME1:
      Settings needed to apply the style fo TYPE_OF_GAUGE2
    STYLE_NAME2:
      Settings needed to apply the style fo TYPE_OF_GAUGE2
```
TYPE_OF_GAUGE should match the gauge names, without the numbers, that are listed in the `gauges` sction

For example if in gauges you have:  
```
gauges:
  ARC1:
    name: RPM
    dbkey: TACH1
    decimal_places: 0
    temperature: false
    show_units: false
  ARC2:
    name: Oil Press
    dbkey: OILP1
    decimal_places: 0
    temperature: false
    show_units: false
```

syles that apply to all `ARC` gauges would be defined with:
```
styles:
  ARC:
    STYLE_NAME:
      settings needed for style
```

You can use the default names of `ARC`, `BAR` and `TEXT` or create your own if needed


### gauges ###
The gauges sections serves two purposes. Maybe you do not want the ARC1 gauges to be a tachometer, instead you want it to be the Maximum EGT. You could copy the ARC1 section from `preferences.yaml` to `preferences.yaml.custom` then edit it.
preferences.yaml:
```
gauges:
  ARC1:
    name: RPM
    dbkey: TACH1
    decimal_places: 0
    temperature: false
    show_units: false
```

In your preferences.yaml.custom file:
```
gauges:
  ARC1:
    name: MAX EGT
    dbkey: EGTMAX1
    temperature: True
    show_units: True
```

The second purpose of the gauges sections is to apply specific style settings for individual gauges.  As an example, the `segmented` style for BAR32 uses a different number of segments than what is defined in the `styles` section. So the segments setting is modified for BAR32:
```
  BAR32:
    # Radio Aux Vol
    styles:
      segmented:
        segments: 22
```

### enabled ###
The enabled section is where you can turn various things on or off. Within screen builder configs when an instrument has the option `disabled` defined and it is a string rather than a boolean, the actually boolean value will be set to the value of that string as defined in the enabled section.

Example, in the config file `includes/bars/vertical/4_CHT.yaml` an instrument has the option `disabled` set to the string `CYLINDER_``:
```
        instruments:
            -
              preferences: BAR15
              options:
                disabled: CYLINDER_1
```
The actual value used for disabled will be looked up in the enabled section and set to the value defined:
```
enabled:
  CYLINDER_1: true
```

This allows you to customize the default screens by simply setting options to true or false. Maybe you only have a two cylinder engine, not four. in your `preferences.yaml.custom` you could define:
```
enabled:
  CYLINDER_1: true
  CYLINDER_2: true
  CYLINDER_3: false
  CYLINDER_4: false

```
Now the EGT and CHT displays will only show two cylinders.

Another example, the trim controls are not shown by default because `TRIM_CONTROLS` is set to `false` in preferences.yaml. You only have a pitch trim, not roll and yaw. In the `preferneces.yaml.custom` you would define:
```
enabled:
  PITCH_TRIM: true
  YAW_TRIM: false
  ROLL_TRIM: false
  TRIM_CONTROLS: true
```

### includes ###
The includes section is used to change what screen builder config file is used for a specific include. An example of using this is to replace the set of buttons on the right side of the screen.  That include is used within many screen builder configs, instead of editing each of the config files we can simply define the include with a key name, then in the includes section define that key and the name of the actual file you want to load. 
```
includes:
  BUTTON_GROUP1: includes/buttons/vertical/screen_changing_PFD-EMS-EMS2-ANDROID-RADIO-SIXPACK-Units.yaml
```