"""One stylesheet for the whole till: the instrument half of docs/DESIGN.md.

v2 set styles inline on nearly every widget, which is how the scanner ended up
with teal buttons next to orange buttons and white scrollbars on a dark
background.  Every colour and size lives here, as one token table and one
stylesheet template.  Change the table in docs/DESIGN.md first, then this.
"""

from __future__ import annotations

import logging
from string import Template

logger = logging.getLogger(__name__)

#: docs/DESIGN.md, instrument column.  ok / warn / bad / info carry state; the
#: accent is the one decorative colour.  The receipt strip is paper on the panel,
#: so the paper column's values are here too.
TOKENS = {
    "bg": "#131110", "surface": "#1C1917", "surface2": "#262220", "line": "#3A342F",
    "ink": "#F2EDE4", "muted": "#A39B8F",
    "accent": "#FF7A18", "accent_ink": "#FFA45C", "on_accent": "#1A1714", "accent_down": "#D96208",
    "ok": "#3DD68C", "warn": "#F2B33D", "bad": "#F0575B", "info": "#6FA8FF",
    "viewfinder": "#0A0908",
    "paper": "#FBFAF7", "paper2": "#EAE7E0", "paper_line": "#D6D2C9",
    "paper_ink": "#1A1714", "paper_muted": "#6B655C",
    "sans": '"IBM Plex Sans Thai", "Noto Sans Thai", "Helvetica Neue", "Segoe UI", sans-serif',
    # Plex Mono has no Thai glyphs; Qt falls through the list per glyph
    "mono": '"IBM Plex Mono", "IBM Plex Sans Thai", "Menlo", "Consolas", monospace',
}

_loaded: list[str] | None = None


def load_fonts() -> list[str]:
    """Register the bundled Plex files with Qt.  Needs a QApplication; runs once.

    Returns the family names Qt reports, so a harness can assert the till is
    not silently rendering in a fallback face.
    """
    global _loaded
    if _loaded is not None:
        return _loaded
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication
    import paths

    families: list[str] = []
    for path in sorted(paths.FONTS.glob("*.ttf")):
        index = QFontDatabase.addApplicationFont(str(path))
        if index < 0:
            logger.warning("font not loaded: %s", path.name)
        else:
            families += [f for f in QFontDatabase.applicationFontFamilies(index) if f not in families]
    if not families:
        logger.warning("no bundled fonts under %s - the till is using system faces", paths.FONTS)
    app = QApplication.instance()
    if app is not None and families:
        app.setFont(QFont("IBM Plex Sans Thai", 11))
    _loaded = families
    return families


_QSS = """
* { font-family: $sans; }
QMainWindow { background: $bg; color: $ink; }
QWidget { color: $ink; }
/* labels must not paint their own box, or every caption becomes a dark slab */
QLabel { background: transparent; }
QFrame { background: transparent; }

#topBar, QFrame#topBar { background: $bg; border-bottom: 1px solid $line; }
#brandMark { color: $accent; font-family: $mono; font-size: 22px; font-weight: 700; letter-spacing: 3px; }
#brandSub  { color: $muted; font-size: 13px; }
#clock     { color: $ink; font-family: $mono; font-size: 20px; font-weight: 500; }

#pill { font-family: $mono; font-size: 12px; letter-spacing: 1px; border-radius: 4px; padding: 6px 12px; }
#pill[state="on"]  { color: $ok;  border: 1px solid rgba(61,214,140,0.45); }
#pill[state="off"] { color: $bad; border: 1px solid rgba(240,87,91,0.45); }

/* cards sit above the page, not flush with it */
#card, QFrame#card { background: $surface; border: 1px solid $line; border-radius: 6px; }
#cardTitle { color: $muted; font-family: $mono; font-size: 12px; font-weight: 600; letter-spacing: 2px; }

/* the viewfinder is the hero; its border is the till's state */
QLabel#viewfinder { background: $viewfinder; border: 2px solid $line; border-radius: 6px; }
QLabel#viewfinder[state="scanning"]  { border-color: $accent; }
QLabel#viewfinder[state="unknown"]   { border-color: $accent; }
QLabel#viewfinder[state="ambiguous"] { border-color: $info; }
QLabel#viewfinder[state="ready"]     { border-color: $ok; }

/* instrument readouts */
#readout { color: $muted; font-family: $mono; font-size: 13px; letter-spacing: 0.5px; }
#readout[state="ok"]  { color: $muted; }
#readout[state="bad"] { color: $bad; }

#chip, QFrame#chip { background: $surface2; border: 1px solid $line; border-left: 4px solid $ok; border-radius: 4px; }
/* an item the till could not name must look different from one it could, or the
   customer scrolls past it and gets charged for whatever staff guessed */
#chip[state="unknown"]   { border-left-color: $accent; background: rgba(255,122,24,0.08); }
#chip[state="ambiguous"] { border-left-color: $info;   background: rgba(111,168,255,0.08); }
#chipName  { font-size: 16px; font-weight: 600; color: $ink; }
#chipMeta  { font-family: $mono; font-size: 12px; color: $muted; }
#chipPrice { font-family: $mono; font-size: 18px; font-weight: 600; color: $accent_ink; }
#emptyNote { color: $muted; font-size: 15px; }
#rowMeta   { font-family: $mono; font-size: 12px; color: $muted; }
#totValue  { font-family: $mono; font-size: 44px; color: $ink; font-weight: 600; }

/* the receipt: paper on the panel, set the way the printer sets it */
#receiptBody, QFrame#receiptBody { background: $paper; border-top-left-radius: 4px; border-top-right-radius: 4px; }
#rcp      { font-family: $mono; font-size: 14px; color: $paper_ink; }
#rcpMuted { font-family: $mono; font-size: 12px; color: $paper_muted; }
#rcpTotal { font-family: $mono; font-size: 34px; font-weight: 600; color: $paper_ink; }
#rcpRule  { background: $paper_line; }
QPushButton#rcpStep {
    background: $paper2; color: $paper_ink; border: 1px solid $paper_line; border-radius: 4px;
    min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px; padding: 0;
    font-family: $mono; font-size: 18px; font-weight: 600;
}
QPushButton#rcpStep:hover   { background: $paper_line; }
QPushButton#rcpStep:pressed { background: $paper_muted; color: $paper; }

/* touch targets: nothing a finger has to hit is under 56px */
QPushButton {
    background: $surface2; color: $ink; border: 1px solid $line;
    border-radius: 6px; padding: 14px 20px; font-size: 16px; font-weight: 600;
    min-height: 56px;
}
QPushButton:hover    { background: #2F2A25; border-color: #4A433C; }
QPushButton:pressed  { background: $bg; }
QPushButton:disabled { color: #5E564D; background: #1A1715; border-color: #2A2622; }

QPushButton#primary {
    background: $accent; color: $on_accent; border: none;
    font-family: $mono; font-size: 20px; font-weight: 700; letter-spacing: 2px; min-height: 84px;
}
QPushButton#primary:hover    { background: $accent_ink; }
QPushButton#primary:pressed  { background: $accent_down; }
QPushButton#primary:disabled { background: #2C2118; color: #6B5B48; }

QPushButton#pay {
    background: $ok; color: $on_accent; border: none;
    font-family: $mono; font-size: 20px; font-weight: 700; letter-spacing: 2px; min-height: 76px;
}
QPushButton#pay:hover    { background: #5AE0A0; }
QPushButton#pay:disabled { background: #1E2A24; color: #4F6B5C; }

QPushButton#ghostDanger { color: $bad; border-color: rgba(240,87,91,0.4); background: transparent; }
QPushButton#ghostDanger:hover    { background: rgba(240,87,91,0.10); }
QPushButton#ghostDanger:disabled { color: #5E564D; border-color: $line; }

QPushButton#step { min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px;
                   padding: 0; font-size: 20px; font-weight: 700; border-radius: 6px; }

/* v2's scrollbars rendered as white blocks on the dark UI */
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: $paper_line; border-radius: 4px; min-height: 40px; }
QScrollBar::handle:vertical:hover { background: $paper_muted; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {
    height: 0; width: 0; background: none; border: none;
}
QScrollBar:horizontal { height: 0px; }

#statusBar, QFrame#statusBar { background: $bg; border-top: 1px solid $line; color: $muted; font-size: 13px; }

QDialog { background: $surface; }

/* form controls. Without these Qt paints its native light widgets straight
   onto the dark till - white boxes in the middle of the panel. */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: $bg; color: $ink;
    border: 1px solid $line; border-radius: 6px;
    padding: 10px 14px; font-size: 16px; selection-background-color: $accent;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: $accent; }
QLineEdit::placeholder { color: $muted; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView {
    background: $surface2; color: $ink;
    border: 1px solid $line; selection-background-color: $accent;
    selection-color: $on_accent; outline: none;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { background: $surface2; border: none; width: 22px; }
QMessageBox QLabel { color: $ink; font-size: 15px; }
"""

QSS = Template(_QSS).substitute(TOKENS)
