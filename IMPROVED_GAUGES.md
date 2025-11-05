# Simplified Bar Gauges - Clean Single-Color Design

## The Simple Approach

I've created **truly simplified versions** of the vertical and horizontal bar gauges that eliminate ALL alignment issues by using a **single-color approach**.

### 🎯 How It Works

Instead of drawing multiple color bands (green/yellow/red zones), the **entire bar changes color** based on the current value:

- **🟢 Green bar** = Value is in the safe range
- **🟡 Yellow bar** = Value is in warning range (high or low)
- **🔴 Red bar** = Value is in alarm range (high or low)

This is like a modern "traffic light" gauge - the whole bar tells you the status at a glance.

### ✅ Benefits

1. **Zero alignment issues** - No color bands to align!
2. **Cleaner appearance** - Modern, minimalist design
3. **Easier to read** - Color indicates status instantly
4. **Simpler code** - No complex segment or threshold calculations
5. **Better performance** - Fewer drawing operations

## Files Created & Modified

### New Gauge Classes:
1. **`src/pyefis/instruments/gauges/verticalBarSimple.py`** ✅
   - Simplified vertical bar with single-color approach
   - 182 lines, complete implementation
   
2. **`src/pyefis/instruments/gauges/horizontalBarSimple.py`** ✅
   - Simplified horizontal bar with single-color approach
   - 171 lines, complete implementation

### Updated Files:
3. **`src/pyefis/instruments/gauges/__init__.py`** ✅
   - Added imports for `HorizontalBarSimple` and `VerticalBarSimple`

4. **`src/pyefis/screens/screenbuilder.py`** ✅
   - Added support for `vertical_bar_gauge_simple` type
   - Added support for `horizontal_bar_gauge_simple` type

5. **`config/preferences.yaml.custom`** ✅
   - All 12 EGT/CHT bars (BAR11-22) configured to use `vertical_bar_gauge_simple`

## Visual Comparison

### Old Multi-Band Approach:
```
EGT Bar:
┌───┐
│RED│ ← High alarm zone (>650°C)
├───┤
│YEL│ ← High warn zone (620-650°C)
├───┤
│GRN│ ← Safe zone
│███│ ← Current value (filled)
│GRN│
├───┤
│YEL│ ← Low warn zone
├───┤
│RED│ ← Low alarm zone
└───┘

Problem: Color bands can misalign between bars
```

### New Single-Color Approach:
```
EGT at 550°C (safe):    EGT at 630°C (warn):    EGT at 660°C (alarm):
┌───┐                   ┌───┐                   ┌───┐
│   │                   │   │                   │   │
│   │                   │   │                   │   │
│   │                   │YEL│                   │RED│
│GRN│ ← Filled          │YEL│ ← Filled          │RED│ ← Filled
│GRN│                   │YEL│                   │RED│
└───┘                   └───┘                   └───┘

Benefit: Entire bar changes color - no alignment issues!
```

## Configuration

Your `config/preferences.yaml.custom` is **already configured** with the simple gauges:

```yaml
gauges:
  # EGT for cylinders 1-4
  BAR11:
    type: vertical_bar_gauge_simple
  BAR12:
    type: vertical_bar_gauge_simple
  BAR13:
    type: vertical_bar_gauge_simple
  BAR14:
    type: vertical_bar_gauge_simple
  
  # CHT for cylinders 1-4
  BAR15:
    type: vertical_bar_gauge_simple
  BAR16:
    type: vertical_bar_gauge_simple
  BAR17:
    type: vertical_bar_gauge_simple
  BAR18:
    type: vertical_bar_gauge_simple
  
  # EGT for cylinders 5-6
  BAR19:
    type: vertical_bar_gauge_simple
    # ... cylinder 5 settings
  BAR20:
    type: vertical_bar_gauge_simple
    # ... cylinder 6 settings
  
  # CHT for cylinders 5-6
  BAR21:
    type: vertical_bar_gauge_simple
    # ... cylinder 5 settings
  BAR22:
    type: vertical_bar_gauge_simple
    # ... cylinder 6 settings
```

## How to Test

**Restart pyEfis to see the new single-color bars:**

```bash
cd ~/makerplane/pyefis
python pyEfis.py
```

## What to Expect

With the simple gauges, you'll see:
- ✅ **Entire bar is one solid color** - Green, yellow, or red
- ✅ **Bar fills from bottom to top** showing current value
- ✅ **Color indicates status** - No need to look at which zone the value is in
- ✅ **Zero alignment issues** - No color bands to align!
- ✅ **Clean, modern appearance** - Minimalist design
- ✅ **All functionality preserved** - Highlights, peak mode, normalize mode still work
- ✅ **Magenta circles still work** - Highlighting the hottest cylinder (EGTMAX1/CHTMAX1)

### Color Logic:
The bar color is determined by the **current value** vs thresholds:

1. **🔴 Red (Alarm)**: 
   - EGT ≥ 650°C (highAlarm) 
   - CHT ≥ 232°C (highAlarm)
   - Or values below lowAlarm

2. **🟡 Yellow (Warning)**:
   - EGT ≥ 620°C (highWarn) but < 650°C
   - CHT ≥ 204°C (highWarn) but < 232°C
   - Or values below lowWarn but above lowAlarm

3. **🟢 Green (Safe)**:
   - All other values (between lowWarn and highWarn)

## Alternative Gauge Options

You have three gauge types available:

### 1. **Simple (Currently Active)** - Recommended ✅
```yaml
type: vertical_bar_gauge_simple
```
- Entire bar changes color based on value
- Clean, modern look
- No alignment issues

### 2. **Improved** - Multi-band with fixed alignment
```yaml
type: vertical_bar_gauge_improved
```
- Traditional color bands (green/yellow/red zones)
- Better pixel alignment than original
- Use if you prefer the traditional multi-band look

### 3. **Original** - Default multi-band
```yaml
type: vertical_bar_gauge
```
- Original implementation
- Has the alignment issue you reported
- Available for comparison

## Technical Implementation

### Simple Gauge Approach

The simple gauge uses a single `_getBarColor()` method that checks the current value against thresholds:

```python
def _getBarColor(self):
    """Determine bar color based on current value and thresholds."""
    value = self._value
    
    # Check high alarm first (highest priority)
    if self.highAlarm is not None and value >= self.highAlarm:
        return self.alarmColor  # Red
    
    # Check high warning
    if self.highWarn is not None and value >= self.highWarn:
        return self.warnColor   # Yellow
    
    # Check low alarm
    if self.lowAlarm is not None and value <= self.lowAlarm:
        return self.alarmColor  # Red
    
    # Check low warning
    if self.lowWarn is not None and value <= self.lowWarn:
        return self.warnColor   # Yellow
    
    # Default to safe
    return self.safeColor       # Green
```

### Drawing Process

1. Draw dark gray background (empty portion)
2. Calculate value pixel position
3. Get bar color based on `_getBarColor()`
4. Draw filled portion from bottom to value position in that color
5. Draw highlight ball if this is the hottest cylinder
6. Draw peak line if in peak mode

This approach is:
- ✅ **Simpler** - One color calculation instead of multiple band calculations
- ✅ **Faster** - Fewer draw operations
- ✅ **More reliable** - No pixel rounding or alignment issues
- ✅ **Easier to understand** - Color = status, instantly readable
- ✅ **Inherits from original** - All features (normalize, peak, temperature conversion) preserved

## Summary

All files are created and your configuration is ready:

| File | Status | Lines |
|------|--------|-------|
| `verticalBarSimple.py` | ✅ Created | 182 |
| `horizontalBarSimple.py` | ✅ Created | 171 |
| `gauges/__init__.py` | ✅ Updated | Imports added |
| `screenbuilder.py` | ✅ Updated | Types registered |
| `preferences.yaml.custom` | ✅ Updated | All bars configured |

**Ready to run!** Just restart pyEfis and you'll see the new clean single-color bars. 🚀
