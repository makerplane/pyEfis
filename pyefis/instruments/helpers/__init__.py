from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

def fit_to_mask(width,height,mask,font,units_mask=None, units_ratio=0.8):

    font_size = height
    text_font = QFont(font, int(font_size))
    units_font = QFont(font, int(font_size * units_ratio))
    t = QGraphicsSimpleTextItem(mask)
    t.setFont(text_font)
    text_width = t.boundingRect().width()
    text_height = t.boundingRect().height()
    units_width = 0
    units_height = 0
    if units_mask:
        u = QGraphicsSimpleTextItem(units_mask)
        u.setFont(units_font)
        units_width = u.boundingRect().width()
        units_height = u.boundingRect().height()

    # IF needed, shrink until it fits
    while (text_width + units_width >= width) and font_size > 0.5:
        font_size -= 0.1
        text_font.setPointSizeF(font_size)
        t.setFont(text_font)
        text_width = t.boundingRect().width()
        text_height = t.boundingRect().height()
        if units_mask:
            units_font.setPointSizeF(font_size * units_ratio)
            u.setFont(units_font)
            units_width = u.boundingRect().width()
            units_height = u.boundingRect().height()

    # If needed, grow until it fills
    while text_width + units_width <= width:
        font_size += 0.1
        text_font.setPointSizeF(font_size)
        t.setFont(text_font)
        text_width = t.boundingRect().width()
        text_height = t.boundingRect().height()
        if units_mask:
            units_font.setPointSizeF(font_size * units_ratio)
            u.setFont(units_font)
            units_width = u.boundingRect().width()
            units_height = u.boundingRect().height()

    # The above took care of the width, this addresses the height:
    while (text_height >= height) and font_size > 0.5:
        font_size -= 0.1
        text_font.setPointSizeF(font_size)
        t.setFont(text_font)
        text_width = t.boundingRect().width()
        text_height = t.boundingRect().height()

    return(font_size)


