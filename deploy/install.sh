#!/usr/bin/env bash
# Put the till on a Raspberry Pi and make it start at boot.
#
#   git clone <repo> && cd AI-Cashier-v4 && ./deploy/install.sh
#
# Default is --scale none, because the defence build has no load cell
# (docs/HARDWARE.md, decision of 23 September 2026).  Pass a flag to change it:
#
#   ./deploy/install.sh --scale hx711 --lan
#
# Afterwards the till is a service:  systemctl --user {start,stop,restart} ai-cashier
# Logs:                              journalctl --user -u ai-cashier -f
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLAGS="${*:---scale none --fullscreen}"

command -v apt-get >/dev/null || { echo "This is for Raspberry Pi OS / Debian."; exit 1; }

echo "==> system packages"
sudo apt-get update -qq
sudo apt-get install -y python3-venv libxcb-cursor0

echo "==> virtualenv"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install --quiet --upgrade pip
"$ROOT/.venv/bin/pip" install --quiet -r "$ROOT/requirements.txt"

[ -f "$ROOT/models/mobilenet_v3_small.onnx" ] || \
  "$ROOT/.venv/bin/python" "$ROOT/tools/export_embedder.py"

# Qt picks the wrong platform plugin often enough to be worth pinning to what
# this desktop session actually is.
PLATFORM=$([ -n "${WAYLAND_DISPLAY:-}" ] && echo wayland || echo xcb)

echo "==> service (${FLAGS}, QT_QPA_PLATFORM=${PLATFORM})"
mkdir -p ~/.config/systemd/user ~/.local/share/applications
cat > ~/.config/systemd/user/ai-cashier.service <<UNIT
[Unit]
Description=AI Cashier till and dashboard
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
WorkingDirectory=${ROOT}
ExecStart=${ROOT}/.venv/bin/python app.py ${FLAGS}
Restart=on-failure
RestartSec=3
Environment=QT_QPA_PLATFORM=${PLATFORM}
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=graphical-session.target
UNIT

# so the shopkeeper can also start it by hand from the menu
cat > ~/.local/share/applications/ai-cashier.desktop <<DESKTOP
[Desktop Entry]
Type=Application
Name=AI Cashier
Comment=The till
Exec=${ROOT}/.venv/bin/python ${ROOT}/app.py ${FLAGS}
Path=${ROOT}
Terminal=false
Categories=Office;
DESKTOP

systemctl --user daemon-reload
systemctl --user enable --now ai-cashier
sudo loginctl enable-linger "$USER"        # start at boot without logging in

sleep 3
if systemctl --user is-active --quiet ai-cashier; then
  echo "==> running.  It will come back on every boot."
else
  echo "==> FAILED to start.  What went wrong:"
  journalctl --user -u ai-cashier -n 30 --no-pager
  exit 1
fi
