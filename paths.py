"""Where the till keeps things.

Two kinds of file, two places:

  * resources - the code, the ONNX model, the dashboard's static pages, the
    demo frame.  Read-only.  In a checkout they sit next to this file; in a
    PyInstaller bundle they sit in the bundle directory (`sys._MEIPASS`).
  * data - the database, the product gallery, the empty-mat photograph, the
    settings.  Written by the till.  In a checkout that is `data/` (and
    `config/settings.json`) so nothing changes for development, the tests or
    the Raspberry Pi.  Installed on Windows, Program Files is read-only, so
    data lives in the user's local app-data folder instead
    (docs/research/09, and the Phase 6 plan).  `AI_CASHIER_DATA` overrides
    either.

Everything that used to compute `Path(__file__).resolve().parents[N]` goes
through here.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "AI Cashier"
FROZEN = bool(getattr(sys, "frozen", False))
#: the checkout root in development, the bundle directory when frozen
RESOURCES = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def version() -> str:
    try:
        return (RESOURCES / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


def _user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "ai-cashier"


def data_dir() -> Path:
    override = os.environ.get("AI_CASHIER_DATA")
    if override:
        return Path(override).expanduser()
    if FROZEN:
        return _user_data_dir()
    return RESOURCES / "data"


def settings_path() -> Path:
    """The hardware/rig settings file.  Development reads the checked-in
    `config/settings.json`; a frozen build (or an override) reads its own copy
    in the data folder, seeded from the bundled one on first run."""
    if os.environ.get("AI_CASHIER_DATA") or FROZEN:
        return data_dir() / "settings.json"
    return RESOURCES / "config" / "settings.json"


def first_run_seed() -> list[Path]:
    """Copy the bundled defaults into the data folder if they are not there.
    Returns what was copied.  A no-op in development, where data/ is the
    source tree itself."""
    target = data_dir()
    if target == RESOURCES / "data":
        return []
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for src, name in ((RESOURCES / "config" / "settings.json", "settings.json"),
                      (RESOURCES / "data" / "products.json", "products.json")):
        dst = target / name
        if src.exists() and not dst.exists():
            shutil.copyfile(src, dst)
            copied.append(dst)
    return copied


# the things the till reads and writes, by name
def database_path() -> Path:
    return data_dir() / "checkout.sqlite3"


def legacy_products_json() -> Path:
    return data_dir() / "products.json"


def gallery_path() -> Path:
    return data_dir() / "gallery.npz"


def mat_path() -> Path:
    return data_dir() / "mat_background.png"


def log_dir() -> Path:
    return data_dir() / "logs"


EMBEDDER = RESOURCES / "models" / "mobilenet_v3_small.onnx"
STATIC = RESOURCES / "server" / "static"
FONTS = RESOURCES / "assets" / "fonts"          # IBM Plex Sans Thai + Plex Mono (OFL)
DEMO_FRAME = RESOURCES / "docs" / "assets" / "demo_frame.jpg"
DEMO_MAT = RESOURCES / "docs" / "assets" / "demo_mat.png"
