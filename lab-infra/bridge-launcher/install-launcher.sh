#!/usr/bin/env bash
#
# Install the O4AA bridge Launcher API onto a bridge VM (run as root, on the bridge).
# Bake this into the golden image so a fresh bridge boots with the launcher idle-listening.
#
# Usage:
#   sudo ./install-launcher.sh --secret <FLEET_SECRET>     # fleet-wide secret (recommended)
#   sudo ./install-launcher.sh                             # generates a random secret and prints it
#   sudo ./install-launcher.sh --port 9090 --secret <s>
#
set -euo pipefail

PORT=9090
SECRET=""
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST=/opt/bridge/launcher

while [[ $# -gt 0 ]]; do
  case "$1" in
    --secret) SECRET="$2"; shift 2 ;;
    --port)   PORT="$2";   shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ $EUID -eq 0 ]] || { echo "must run as root"; exit 1; }
command -v python3 >/dev/null || { echo "python3 not found"; exit 1; }
command -v docker  >/dev/null || { echo "docker not found";  exit 1; }

if [[ -z "$SECRET" ]]; then
  SECRET="$(head -c 24 /dev/urandom | base64 | tr -d '/+=' | head -c 32)"
  GENERATED=1
fi

echo "==> Installing launcher to $DEST (port $PORT)"
install -d -m 755 "$DEST"
install -m 755 "$SRC_DIR/bridge-launcher.py" "$DEST/bridge-launcher.py"
printf '%s' "$SECRET" > "$DEST/secret"
chmod 600 "$DEST/secret"; chown root:root "$DEST/secret"

echo "==> Installing systemd unit"
sed "s/BRIDGE_LAUNCHER_PORT=9090/BRIDGE_LAUNCHER_PORT=${PORT}/" \
    "$SRC_DIR/bridge-launcher.service" > /etc/systemd/system/bridge-launcher.service
systemctl daemon-reload
systemctl enable --now bridge-launcher.service

echo "==> Verifying"
sleep 2
if curl -fsS "http://127.0.0.1:${PORT}/healthz" >/dev/null; then
  echo "    OK: launcher responding on :${PORT}/healthz"
else
  echo "    WARN: /healthz not responding yet - check: journalctl -u bridge-launcher -n 50"
fi

echo
echo "Launcher installed and enabled (starts on boot; bridge stack stays down until /launch)."
if [[ "${GENERATED:-0}" == "1" ]]; then
  echo "GENERATED SECRET (record this for the VDI bootstrap / platform placeholder):"
  echo "    $SECRET"
fi
echo "Remember: expose port ${PORT} only to the paired VDI (pod-internal), same as 8000/3001."
