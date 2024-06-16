from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

def fit_to_mask(iwidth,iheight,mask,font,units_mask=None, units_ratio=0.8):

    # Could not get font metrics to work perfectly
    # Seems like text it rendered starting slightly to the right
    # rsulting in the right side of the text getting cut off
    # Fitting to a slightly smaller width and height
    # seems to resolve the issue.
    width = iwidth * 0.95
    height = iheight * 0.96
    font_size = height
    text_font = QFont(font, int(font_size))
    units_font = QFont(font, int(font_size * units_ratio))
    fm = QFontMetrics(text_font)
    text_width = fm.tightBoundingRect(mask).width()
    text_height = fm.tightBoundingRect(mask).height()
    units_width = 0
    units_height = 0
    if units_mask:
        fmu = QFontMetrics(units_font)
        units_width = fmu.tightBoundingRect(units_mask).width()
        units_height = fmu.tightBoundingRect(units_mask).height()

    # IF needed, shrink until it fits
    while ( (text_width + units_width > width) or text_height > height ) and font_size > 0.5:
        font_size -= 0.2
        text_font.setPointSizeF(font_size)
        fm = QFontMetrics(text_font)
        text_width = fm.tightBoundingRect(mask).width()
        text_height = fm.tightBoundingRect(mask).height()
        if units_mask:
            units_font.setPointSizeF(font_size * units_ratio)
            fmu = QFontMetrics(units_font)
            units_width = fmu.tightBoundingRect(units_mask).width()
            units_height = fmu.tightBoundingRect(units_mask).height()
    # If needed, grow until it fills
    while (text_width + units_width < width) and text_height < height:
        font_size += 0.2
        text_font.setPointSizeF(font_size)
        fm = QFontMetrics(text_font)
        text_width = fm.tightBoundingRect(mask).width()
        text_height = fm.tightBoundingRect(mask).height()
        if units_mask:
            units_font.setPointSizeF(font_size * units_ratio)
            fmu = QFontMetrics(units_font)
            units_width = fmu.tightBoundingRect(units_mask).width()
            units_height = fmu.tightBoundingRect(units_mask).height()

    font_size -= 0.2

    # The above took care of the width, this addresses the height:
    while (text_height >= height) and font_size > 0.5:
        font_size -= 0.2
        text_font.setPointSizeF(font_size)
        fm = QFontMetrics(text_font)
        text_width = fm.tightBoundingRect(mask).width()

    return(font_size)


