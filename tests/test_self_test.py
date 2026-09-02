"""`app.py --self-test` is what CI runs on the frozen Windows build: no camera,
no window, and it must find the two products on the bundled demo mat."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_self_test_finds_the_demo_products(tmp_path):
    env = {**os.environ, "AI_CASHIER_DATA": str(tmp_path)}
    r = subprocess.run([sys.executable, str(ROOT / "app.py"), "--self-test"],
                       cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "self-test ok" in r.stdout and "2 item(s)" in r.stdout, r.stdout
