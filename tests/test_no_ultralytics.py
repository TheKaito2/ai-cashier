"""The till and the server must run without ultralytics or torch.

Ultralytics is AGPL-3.0: anything that imports it and is distributed must be
AGPL too, which would make the Apache-2.0 licence on this repository false.
It also drags a training framework onto a Raspberry Pi that never trains.
Both packages are blocked here at import time; if any module on the till path
reaches for them, this test fails.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BLOCKED = r"""
import sys, os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
class Block:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in {"ultralytics", "torch", "torchvision"}:
            raise ImportError(f"{name} is not allowed on the till")
        return None
sys.meta_path.insert(0, Block())
sys.path.insert(0, %r)
import recognition.pipeline, recognition.embedder, recognition.proposer
import server.main
from PySide6.QtWidgets import QApplication
QApplication([])
import scanner.ui.main_window, scanner.ui.enrol_dialog
print("ok")
""" % str(ROOT)


def test_till_and_server_import_without_ultralytics_or_torch():
    r = subprocess.run([sys.executable, "-c", BLOCKED], capture_output=True, text=True,
                       cwd=ROOT, timeout=120)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-2000:]
