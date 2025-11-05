# Improved Bar Gauges - Migration Guide

## What's Been Improved

I've created **improved versions** of the vertical and horizontal bar gauges that fix the color band alignment issue you were experiencing. The key improvements:

### 1. **Consistent Pixel Calculation**
- All threshold positions (low alarm, low warn, high warn, high alarm) are calculated using a single `_calculateThresholdPixel()` method
- Uses `round()` consistently for all positions to avoid accumulating floating-point errors
- Color bands are drawn from absolute pixel positions, not relative offsets

### 2. **Cleaner Drawing Logic**
- Color bands are drawn in sequential sections (top-to-bottom for vertical, left-to-right for horizontal)
- Each section knows its exact start and end position
- No more cumulative rounding errors between bands

### 3. **Simplified Segment Rendering**
- Segments only draw when `segments > 1` (no gap lines for `segments: 1`)
- Gap calculation is cleaner and more predictable
- Filled bar effect (darkening) is applied separately and cleanly

## Files Created

1. **`src/pyefis/instruments/gauges/verticalBarImproved.py`**
   - Improved vertical bar gauge class
   - Inherits from original `VerticalBar` to preserve all functionality
   
2. **`src/pyefis/instruments/gauges/horizontalBarImproved.py`**
   - Improved horizontal bar gauge class
   - Inherits from original `HorizontalBar` to preserve all functionality

3. **Updated `src/pyefis/instruments/gauges/__init__.py`**
   - Exported both new gauge types

4. **Updated `src/pyefis/screens/screenbuilder.py`**
   - Added support for new gauge types: `vertical_bar_gauge_improved` and `horizontal_bar_gauge_improved`

## How to Use

You have **two options**:

### Option 1: Override in preferences.yaml.custom (Recommended - Easy to Revert)

Since your EGT/CHT bars are defined using ganged instruments that reference BAR11-14, BAR19-22, you can simply add the `type:` override to each bar in `config/preferences.yaml.custom`:

```yaml
gauges:
  # EGT bars
  BAR11:
    type: vertical_bar_gauge_improved
  BAR12:
    type: vertical_bar_gauge_improved
  BAR13:
    type: vertical_bar_gauge_improved
  BAR14:
    type: vertical_bar_gauge_improved
  BAR19:
    type: vertical_bar_gauge_improved
  BAR20:
    type: vertical_bar_gauge_improved
  
  # CHT bars
  BAR15:
    type: vertical_bar_gauge_improved
  BAR16:
    type: vertical_bar_gauge_improved
  BAR17:
    type: vertical_bar_gauge_improved
  BAR18:
    type: vertical_bar_gauge_improved
  BAR21:
    type: vertical_bar_gauge_improved
  BAR22:
    type: vertical_bar_gauge_improved
```

This approach:
- ✅ Doesn't modify any include files
- ✅ Easy to test and revert
- ✅ Works with ganged bar layouts
- ✅ Can be version controlled separately

### Option 2: Modify Include Files (Permanent Change)

If you want to make the change permanent, you can modify the include files directly. However, note that ganged instruments work differently - they reference individual BAR preferences, not direct type specifications.

**For standalone bars** (not ganged), you would change:
```yaml
instruments:
  - type: vertical_bar_gauge_improved
    # ... other settings
```

But since you're using ganged layouts (`ganged_vertical_bar_gauge`), **Option 1 is the better approach**.

## Testing

1. **Backup your current config** (already done in preferences.yaml.custom)

2. **Choose your approach** (Option 1 or Option 2 above)

3. **Restart pyEfis**:
   ```bash
   cd ~/makerplane/pyefis
   python pyEfis.py
   ```

4. **Look for alignment improvements**:
   - Color bands (green/yellow/red) should align perfectly between bars
   - No more "shifted" appearance
   - Transitions between colors should be at exactly the same pixel height

## What to Expect

With the improved gauges and your current settings:
- **`segments: 1`** - Gives you solid thermometer-style bars with no visible segment gaps
- **`segment_alpha: 250`** - Strong darkening effect for the unfilled portion
- **Aligned color bands** - All bars will show color transitions at identical pixel positions

## Reverting

If you want to go back to the original gauges:
- Simply change `vertical_bar_gauge_improved` back to `vertical_bar_gauge`
- Or remove the `type:` override from preferences.yaml.custom

## Technical Details

The original implementation calculated each color band's height relative to the previous band, which could accumulate rounding errors:
```python
# Old way (simplified)
green_height = threshold2 - threshold1  # Might be 100.3 pixels
yellow_height = threshold3 - threshold2  # Might be 50.7 pixels
# After rounding, you get 100 + 51 = 151, but should be 150
```

The improved implementation calculates from absolute positions:
```python
# New way (simplified)
green_top = round(calculate_pixel(threshold1))     # 50
green_bottom = round(calculate_pixel(threshold2))  # 150
yellow_bottom = round(calculate_pixel(threshold3)) # 200
# Each band knows its exact position, no accumulation
```

## Need More Help?

If the alignment still looks off after trying the improved gauges, we can:
1. Check if the pixel rounding algorithm needs adjustment
2. Verify the threshold values in FIX Gateway are correct
3. Look at the bar layout calculations in screenbuilder

Let me know how it works!
