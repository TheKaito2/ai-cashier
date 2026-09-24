#!/usr/bin/env bash
# Put the till on a Raspberry Pi and make it start with the desktop.
#
#   git clone <repo> && cd AI-Cashier-v4 && ./deploy/install.sh
#
# Default is --scale none, because the defence build has no load cell
# (docs/HARDWARE.md, decision of 23 September 2026).  Pass a flag to change it:
#
#   ./deploy/install.sh --scale hx711 --lan
#
# Start at boot is XDG autostart, NOT a systemd user unit.  A user unit wants
# graphical-session.target, which GNOME and KDE activate and labwc - what Pi OS
# Trixie actually runs - does not.  The unit then sits enabled and never starts,
# with no log to say why.  Autostart also runs inside the real desktop session,
# so Qt picks its own platform plugin instead of the installer guessing over SSH
# where WAYLAND_DISPLAY is never set.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLAGS="${*:---scale none --fullscreen}"

command -v apt-get >/dev/null || { echo "This is for Raspberry Pi OS / Debian."; exit 1; }

echo "==> system packages"
sudo apt-get update -qq
sudo apt-get install -y python3-venv libxcb-cursor0

# PySide6 alone is about 100 MB and opencv-contrib another 40.  Over the Pi's
# wifi this step is ten to thirty minutes, so it must not be quiet: a silent
# half-hour is indistinguishable from a hang, and someone will kill it.
echo "==> virtualenv - this is the slow part, expect 10-30 minutes"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install --upgrade pip
"$ROOT/.venv/bin/pip" install --progress-bar on -r "$ROOT/requirements.txt"

[ -f "$ROOT/models/mobilenet_v3_small.onnx" ] || \
  "$ROOT/.venv/bin/python" "$ROOT/tools/export_embedder.py"

# An earlier version of this script installed a systemd user unit that could
# never fire.  Take it away rather than leave it enabled and confusing.
if [ -f ~/.config/systemd/user/ai-cashier.service ]; then
  echo "==> removing the old systemd unit, which never started"
  systemctl --user disable --now ai-cashier 2>/dev/null || true
  rm -f ~/.config/systemd/user/ai-cashier.service
  systemctl --user daemon-reload 2>/dev/null || true
fi

echo "==> autostart (${FLAGS})"
mkdir -p ~/.config/autostart ~/.local/share/applications
ENTRY="[Desktop Entry]
Type=Application
Name=AI Cashier
Comment=The till
Exec=${ROOT}/.venv/bin/python ${ROOT}/app.py ${FLAGS}
Path=${ROOT}
Terminal=false
Categories=Office;"
printf '%s\n' "$ENTRY" > ~/.config/autostart/ai-cashier.desktop      # at login
printf '%s\n' "$ENTRY" > ~/.local/share/applications/ai-cashier.desktop  # in the menu

# Only a real desktop session can prove the till opens a window.  Over SSH there
# is no display, and a failure there would say nothing about the Pi's screen -
# so say what is true instead of running a check that cannot mean anything.
if [ -z "${WAYLAND_DISPLAY:-}${DISPLAY:-}" ]; then
  echo
  echo "==> installed.  No display in this session, so nothing was started."
  echo "    Reboot the Pi, or log in on its own screen.  The till comes up with"
  echo "    the desktop.  If it does not, run this on the Pi itself to see why:"
  echo
  echo "      ${ROOT}/.venv/bin/python ${ROOT}/app.py ${FLAGS}"
  exit 0
fi

echo "==> starting it now to check it actually opens"
"$ROOT/.venv/bin/python" "$ROOT/app.py" $FLAGS &
PID=$!
sleep 8
if kill -0 "$PID" 2>/dev/null; then
  echo "==> running (pid $PID).  It will start with the desktop from now on."
else
  wait "$PID" 2>/dev/null || true
  echo "==> FAILED - it exited within 8 seconds.  Run it by hand to see the error:"
  echo "      ${ROOT}/.venv/bin/python ${ROOT}/app.py ${FLAGS}"
  exit 1
fi
