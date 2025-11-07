# pip install PyQt6
from PyQt6 import QtGui, QtWidgets, QtCore
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QPainter, QPalette

def qrgba(r, g, b):  # clamp helper
    return QColor(int(r), int(g), int(b))

# --- Color sets ---
# "Original" = pure primaries (max contrast, more visual "vibration")
ORIG_RED    = qrgba(255,   0,   0)
ORIG_YELLOW = qrgba(255, 255,   0)
ORIG_GREEN  = qrgba(  0, 255,   0)

# "Adjusted" ~= luminance-balanced vivid colors (reduce apparent misalignment)
# You can tweak these toward your taste/monitor; these are a solid starting point.
ADJ_RED    = qrgba(255,  60,  40)   # brighten red by adding a little G
ADJ_YELLOW = qrgba(245, 220,  40)   # pull green down slightly
ADJ_GREEN  = qrgba(  0, 220,  80)   # reduce luminance, small R to warm it

# Optional: an HSL version with equal lightness (very stable visually)
def vivid_hsl(h_deg):  # same lightness for all hues
    return QColor.fromHsl(int(h_deg) % 360, 255, 130)  # S=255, L=130
HSL_RED, HSL_YELLOW, HSL_GREEN = vivid_hsl(0), vivid_hsl(55), vivid_hsl(120)

class Bars(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(800, 240)
        self.use_adjusted = True      # start with adjusted set
        self.use_hsl_equalL = False   # try this as an alternative
        self.use_separators = True    # 1px separators tame edge illusions

        # Dark background similar to your screenshots
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(36, 36, 36))
        self.setAutoFillBackground(True)
        self.setPalette(pal)

    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Space:
            self.use_adjusted = not self.use_adjusted
            self.update()
        elif e.key() == Qt.Key.Key_H:
            self.use_hsl_equalL = not self.use_hsl_equalL
            self.update()
        elif e.key() == Qt.Key.Key_S:
            self.use_separators = not self.use_separators
            self.update()
        else:
            super().keyPressEvent(e)

    def paintEvent(self, ev: QtGui.QPaintEvent) -> None:
        p = QPainter(self)
        # --- Pixel discipline ---
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # no AA for crisp edges
        p.setPen(Qt.PenStyle.NoPen)                               # we fill only
        p.setBrush(Qt.BrushStyle.SolidPattern)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)

        # Device Pixel Ratio awareness (helps on 125%/150% scaling displays)
        dpr = self.devicePixelRatioF()  # float
        # All geometry below uses ints so rasterization lands on whole pixels.
        W, H = self.width(), self.height()

        # Layout
        n = 6
        margin = 28
        gap = 22
        #bar_w = int((W - 2*margin - (n-1)*gap) / n)
        bar_w = 10

        # Band heights as integers
        # Top red, thin yellow, tall green, thin yellow, bottom red (like your bars)
        top_red_h    = int(H * 0.12)
        top_yel_h    = int(H * 0.05)
        green_h      = int(H * 0.46)
        bot_yel_h    = int(H * 0.05)
        bot_red_h    = int(H * 0.12)

        # Vertical centering
        total_h = top_red_h + top_yel_h + green_h + bot_yel_h + bot_red_h
        y0 = int((H - total_h) / 2)

        # Choose color set
        if self.use_hsl_equalL:
            RED, YEL, GRN = HSL_RED, HSL_YELLOW, HSL_GREEN
        elif self.use_adjusted:
            RED, YEL, GRN = ADJ_RED, ADJ_YELLOW, ADJ_GREEN
        else:
            RED, YEL, GRN = ORIG_RED, ORIG_YELLOW, ORIG_GREEN

        # Optional thin neutral separators to “lock” edges visually
        sep = 1 if self.use_separators else 0
        SEP_COLOR = QColor(52, 52, 52)  # near-bg dark gray

        # Draw bars
        x = margin
        for i in range(n):
            # compute integer rectangles (fillRect uses ints -> aligns to pixel grid)
            y = y0

            # top red
            p.setBrush(RED)
            p.fillRect(QRect(int(x), int(y), int(bar_w), int(top_red_h)), RED)
            y += top_red_h
            if sep:
                p.fillRect(QRect(int(x), int(y), int(bar_w), sep), SEP_COLOR)
                y += sep

            # top yellow
            p.setBrush(YEL)
            p.fillRect(QRect(int(x), int(y), int(bar_w), int(top_yel_h)), YEL)
            y += top_yel_h
            if sep:
                p.fillRect(QRect(int(x), int(y), int(bar_w), sep), SEP_COLOR)
                y += sep

            # green
            p.setBrush(GRN)
            p.fillRect(QRect(int(x), int(y), int(bar_w), int(green_h)), GRN)
            y += green_h
            if sep:
                p.fillRect(QRect(int(x), int(y), int(bar_w), sep), SEP_COLOR)
                y += sep

            # bottom yellow
            p.setBrush(YEL)
            p.fillRect(QRect(int(x), int(y), int(bar_w), int(bot_yel_h)), YEL)
            y += bot_yel_h
            if sep:
                p.fillRect(QRect(int(x), int(y), int(bar_w), sep), SEP_COLOR)
                y += sep

            # bottom red
            p.setBrush(RED)
            p.fillRect(QRect(int(x), int(y), int(bar_w), int(bot_red_h)), RED)

            x += bar_w + gap

        # Labels
        p.setPen(QColor(220, 220, 220))
        font = p.font()
        font.setPointSize(10)
        p.setFont(font)
        label = "Adjusted" if self.use_adjusted else "Original"
        if self.use_hsl_equalL: label += " (HSL equal L)"
        if self.use_separators: label += " + 1px separators"
        p.drawText(self.rect().adjusted(8, 8, -8, -8), Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignLeft, label)

def main():
    import sys
    app = QtWidgets.QApplication(sys.argv)
    # Optional: ensure crisp pixmaps on HiDPI
    # QtGui.QGuiApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    w = Bars()
    w.setWindowTitle("Garmin-style Bars (Space: toggle Original/Adjusted, H: toggle HSL equal L, S: separators)")
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
