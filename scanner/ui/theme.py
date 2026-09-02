"""One stylesheet for the whole till.

v2 set styles inline on nearly every widget, which is how the scanner ended up
with teal buttons next to orange buttons and white scrollbars on a dark
background.  Every colour and size now lives here.
"""

# Slate base, one accent.  Green and red are reserved for state, never decoration.
BG        = "#0E1116"
SURFACE   = "#161B22"
SURFACE_2 = "#1D242D"
LINE      = "#2A333F"
TEXT      = "#E8EDF2"
MUTED     = "#8A98A8"
ACCENT    = "#FF7A18"
ACCENT_D  = "#D96208"
OK        = "#2ECC71"
BAD       = "#E5484D"
INFO      = "#4C9AFF"

FONT = '"SF Pro Display", "Helvetica Neue", "Segoe UI", "Noto Sans Thai", sans-serif'

QSS = f"""
* {{ font-family: {FONT}; }}
QMainWindow {{ background: {BG}; color: {TEXT}; }}
QWidget {{ color: {TEXT}; }}
/* labels must not paint their own box, or every caption becomes a dark slab */
QLabel {{ background: transparent; }}
QFrame {{ background: transparent; }}

#topBar, QFrame#topBar {{ background: {SURFACE}; border-bottom: 1px solid {LINE}; }}
#brandMark {{ color: {ACCENT}; font-size: 26px; font-weight: 800; letter-spacing: 1px; }}
#brandSub  {{ color: {MUTED}; font-size: 13px; }}
#clock     {{ color: {TEXT};  font-size: 20px; font-weight: 600; }}

#pill        {{ border-radius: 15px; padding: 6px 16px; font-size: 13px; font-weight: 600; }}
#pill[state="on"]  {{ background: rgba(46,204,113,0.14); color: {OK};  border: 1px solid rgba(46,204,113,0.35); }}
#pill[state="off"] {{ background: rgba(229,72,77,0.14);  color: {BAD}; border: 1px solid rgba(229,72,77,0.35); }}

/* cards sit above the page, not flush with it */
#card, QFrame#card {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: 18px; }}
#cardTitle {{ color: {MUTED}; font-size: 12px; font-weight: 700; letter-spacing: 1.6px; }}

QLabel#viewfinder {{ background: #05070A; border: 1px solid {LINE}; border-radius: 14px; }}

#chip, QFrame#chip {{ background: {SURFACE_2}; border: 1px solid {LINE}; border-radius: 12px; }}
/* an item the till could not name must look different from one it could, or the
   customer scrolls past it and gets charged for whatever staff guessed */
#chip[state="unknown"] {{ background: rgba(255,122,24,0.10); border-color: {ACCENT}; }}
#chip[state="ambiguous"] {{ background: rgba(76,154,255,0.10); border-color: {INFO}; }}
#chipName  {{ font-size: 15px; font-weight: 600; color: {TEXT}; }}
#chipMeta  {{ font-size: 12px; color: {MUTED}; }}
#chipPrice {{ font-size: 17px; font-weight: 700; color: {ACCENT}; }}
#emptyNote {{ color: {MUTED}; font-size: 15px; }}

#rowName  {{ font-size: 17px; font-weight: 600; color: {TEXT}; }}
#rowMeta  {{ font-size: 12px; color: {MUTED}; }}
#rowTotal {{ font-size: 17px; font-weight: 700; color: {TEXT}; }}
#rowLine  {{ background: {LINE}; }}

#sumLabel {{ font-size: 15px; color: {MUTED}; }}
#sumValue {{ font-size: 15px; color: {TEXT}; font-weight: 600; }}
#totLabel {{ font-size: 15px; color: {MUTED}; font-weight: 700; letter-spacing: 1.4px; }}
#totValue {{ font-size: 44px; color: {TEXT}; font-weight: 800; }}

/* touch targets: nothing a finger has to hit is under 56px */
QPushButton {{
    background: {SURFACE_2}; color: {TEXT}; border: 1px solid {LINE};
    border-radius: 14px; padding: 16px 22px; font-size: 16px; font-weight: 600;
    min-height: 56px;
}}
QPushButton:hover   {{ background: #242D38; border-color: #3A4654; }}
QPushButton:pressed {{ background: #131920; }}
QPushButton:disabled {{ color: #4E5967; background: #141920; border-color: #202833; }}

QPushButton#primary {{
    background: {ACCENT}; color: #150A02; border: none;
    font-size: 21px; font-weight: 800; letter-spacing: 0.6px; min-height: 84px;
}}
QPushButton#primary:hover   {{ background: #FF8C36; }}
QPushButton#primary:pressed {{ background: {ACCENT_D}; }}
QPushButton#primary:disabled {{ background: #241C14; color: #6B5B48; }}

QPushButton#pay {{
    background: {OK}; color: #05200F; border: none;
    font-size: 21px; font-weight: 800; min-height: 76px;
}}
QPushButton#pay:hover   {{ background: #43D982; }}
QPushButton#pay:disabled {{ background: #182029; color: #55616F; }}

QPushButton#ghostDanger {{ color: {BAD}; border-color: rgba(229,72,77,0.4); }}
QPushButton#ghostDanger:hover {{ background: rgba(229,72,77,0.12); }}
QPushButton#ghostDanger:disabled {{ color: #55616F; border-color: {LINE}; }}

QPushButton#step {{ min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px;
                    padding: 0; font-size: 20px; font-weight: 700; border-radius: 12px; }}

/* v2's scrollbars rendered as white blocks on the dark UI */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: #333F4D; border-radius: 5px; min-height: 40px; }}
QScrollBar::handle:vertical:hover {{ background: #435264; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    height: 0; width: 0; background: none; border: none;
}}
QScrollBar:horizontal {{ height: 0px; }}

#statusBar, QFrame#statusBar {{ background: {SURFACE}; border-top: 1px solid {LINE}; color: {MUTED}; font-size: 13px; }}

QDialog {{ background: {SURFACE}; }}

/* form controls. Without these Qt paints its native light widgets straight
   onto the dark till - white boxes in the middle of the panel. */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {BG}; color: {TEXT};
    border: 1px solid {LINE}; border-radius: 12px;
    padding: 10px 14px; font-size: 16px; selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QLineEdit::placeholder {{ color: {MUTED}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; color: {TEXT};
    border: 1px solid {LINE}; selection-background-color: {ACCENT};
    selection-color: #150A02; outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {SURFACE_2}; border: none; width: 22px;
}}
QMessageBox QLabel {{ color: {TEXT}; font-size: 15px; }}
"""
