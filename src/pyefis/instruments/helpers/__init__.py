from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

def fit_to_mask(width,height,mask,font,units_mask=None, units_ratio=0.8):
    # This works well for text, but renderes numbers undersized
    font_size = height
    text_font = QFont(font)
    text_font.setPointSizeF(font_size)
    units_font = QFont(font)
    units_font.setPointSizeF(font_size * units_ratio)
    fm = QFontMetrics(text_font)
    text_width = fm.boundingRect(mask).width()
    text_height = fm.boundingRect(mask).height() - fm.leading()
    units_width = 0
    units_height = 0
    if units_mask:
        fmu = QFontMetrics(units_font)
        units_width = fmu.boundingRect(units_mask).width()
        units_height = fmu.boundingRect(units_mask).height() 

    # IF needed, shrink until it fits
    while ( (text_width + units_width > width) or text_height > height ) and font_size > 0.5:
        font_size -= 0.2
        text_font.setPointSizeF(font_size)
        fm = QFontMetrics(text_font)
        text_width = fm.boundingRect(mask).width()
        text_height = fm.boundingRect(mask).height() 
        if units_mask:
            units_font.setPointSizeF(font_size * units_ratio)
            fmu = QFontMetrics(units_font)
            units_width = fmu.boundingRect(units_mask).width()
            units_height = fmu.boundingRect(units_mask).height() 
    # If needed, grow until it fills
    while (text_width + units_width < width) and text_height < height:
        font_size += 0.2
        text_font.setPointSizeF(font_size)
        fm = QFontMetrics(text_font)
        text_width = fm.boundingRect(mask).width()
        text_height = fm.boundingRect(mask).height() 
        if units_mask:
            units_font.setPointSizeF(font_size * units_ratio)
            fmu = QFontMetrics(units_font)
            units_width = fmu.boundingRect(units_mask).width()
            units_height = fmu.boundingRect(units_mask).height() 

    font_size -= 0.2

    # The above took care of the width, this addresses the height:
    while (text_height >= height) and font_size > 0.5:
        font_size -= 0.2
        text_font.setPointSizeF(font_size)
        fm = QFontMetrics(text_font)
        text_height = fm.boundingRect(mask).height() 
    if font_size <= 0:
        raise "Error"
    return(font_size)


