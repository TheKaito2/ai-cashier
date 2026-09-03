# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows build (also runs on macOS as a rehearsal).

    pyinstaller --noconfirm build/windows/AICashier.spec

One-folder, windowed.  onnxruntime, cv2 and uvicorn are collected whole: all
three load pieces of themselves by name at run time and PyInstaller's static
analysis misses them.  Everything the till reads sits in the bundle (see
paths.py: RESOURCES); everything it writes goes to the user's data folder.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parents[1]

datas = [
    (str(ROOT / "models" / "mobilenet_v3_small.onnx"), "models"),
    (str(ROOT / "models" / "mobilenet_v3_small.onnx.data"), "models"),
    (str(ROOT / "config" / "settings.json"), "config"),
    (str(ROOT / "data" / "products.json"), "data"),
    (str(ROOT / "docs" / "assets" / "demo_frame.jpg"), "docs/assets"),
    (str(ROOT / "docs" / "assets" / "demo_mat.png"), "docs/assets"),
    (str(ROOT / "server" / "static"), "server/static"),
    (str(ROOT / "assets" / "fonts"), "assets/fonts"),
    (str(ROOT / "VERSION"), "."),
]
binaries, hiddenimports = [], []
for package in ("onnxruntime", "cv2", "uvicorn"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # the till imports QtCore/QtGui/QtWidgets only; keep the rest of Qt out
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
              "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.Qt3DCore",
              "PySide6.QtCharts", "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtDataVisualization",
              "PySide6.QtLocation", "PySide6.QtPositioning", "PySide6.QtBluetooth",
              "torch", "torchvision", "ultralytics", "matplotlib", "tkinter", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

icon = ROOT / "build" / "windows" / "icon.ico"
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="AI Cashier",
    console=False,                       # windowed: app.py sends stdout/stderr to the log
    icon=str(icon) if icon.exists() else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="AICashier")
