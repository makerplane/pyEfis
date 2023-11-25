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
![Grid Image](/docs/images/grid_grid.png)

## Margins
Maybe you do not want instruments showing up behind the menu or some other customization you have made. Setting a margin will exclude that region from your grid so no gauges will be placed in that area.

Margins are defined under `layout:` using the key `margin:`

In this example we will exclude the bottom 10% of the screen:

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
```
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
      columns: 640
      rows: 480
      margin:
        bottom: 10
    instruments:
      - type: airspeed_dial
        row: 1
        column: 1
```
### Span
The next most useful option is `span:` which allows the instrument to span columns to the right and rows down.
Back to the example grid of 640 x 480 that matches the resolution, `rows:` and `columns:` specify how many pixels tall and wide the instrument will be. 

If you want the six gauges evenly places with three on top and two rows high:<br>

set the height to:<br>
`480 / 2 = 240`<br>
and the columns to<br>
`640 / 3 = 213.33`<br>

You can drop the decimals. It is OK that that rows and columns do not match, the gauge will be as large as possible to fit in that area but will not be distorted. The default is to center vertically and horizontally.

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
        db_items: IAS
        row: 1
        column: 1
        span:
          rows: 240
          columns: 213
```

### Move
The next option is `move:` that provides two options `shrink:` and `justify:`

Shrink allows you to shrink and item by percentage, this is useful in cases where you might want to keep the layout simple but need to fit a couple of instruments in the same area.

Imagine our example six pack, it would be much easier to have just three columns and two rows because you do not need any math to figure out the span:
```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 3
      rows: 2
    instruments:
      - type: airspeed_dial
        db_items: IAS
        row: 1
        column: 1
```

For the HSI you want to display a small heading box above it. First you place the HSI:
```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 3
      rows: 2
    instruments:
      - 
        type: horizontal_situation_indicator
        row: 2
        column: 2
```
Now you shrink it a little and move it down to make room for the heading box:
```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 3
      rows: 2
    instruments:
      - 
        type: horizontal_situation_indicator
        row: 2
        column: 2
        move:
          shrink: 21
          justify:
            - bottom
```
Then you can place the heading box which also needs to shrink and justify to the top:
```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 3
      rows: 2
    instruments:
      - 
        type: horizontal_situation_indicator
        row: 2
        column: 2
        move:
          shrink: 21
          justify:
            - bottom
      -
        type: heading_display
        db_items: HEAD
        column: 2
        row: 2
        move:
          shrink: 80
          justify:
            - top
```

### Options
Some instruments have options, for example the HSI has the options `gsi_enabled` and `cdi_enabled` that can enable the glide slope indicator or the course deviation indicator
We will add those options to the HSI
```
screens:
  SixPackNew:
    module: pyefis.screens.screenbuilder
    title: Six Pack
    layout:
      columns: 3
      rows: 2
    instruments:
      - 
        type: horizontal_situation_indicator
        options:
          gsi_enabled: true
          cdi_enabled: true
        row: 2
        column: 2
        move:
          shrink: 21
          justify:
            - bottom
      -
        type: heading_display
        column: 2
        row: 2
        move:
          shrink: 80
          justify:
            - top
```

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

### Ganged Instruments ###
Ganged instruments are perfect for when you want to configure a column or row of instruments. To use them you simply prefix the instrument type with `ganged_`

For example `ganged_arc_gauge`

The default is to gang them vertically, if you want to gang horizontally you must specify the `gang_type:` key:

```
      -
        type: ganged_vertical_bar_gauge
        gang_type: horizontal

```

#### Groups ####
Each instrument in a gang must belong to a gang group. Each gang group will be slightly sperated on the screen to visuallt sperate each group from one another.


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

##### Common Options #####

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


# Instrument List #
Below is a list of the instrument types, defaults and options. This is a WIP and is mostly incomplete. Basically an option is any properly of the instrument that is defined in its source. Currenlty not many options have common names, one instrument might use font_size where another is fontsize or fontSize. Hopefully the community can decide on some common naming and update the code to make maintaining the list here much easier.


airspeed_dial
altimeter_dial
atitude_indicator
heading_display
horizontal_situation_indicator
turn_coordinator
vsi_dial
