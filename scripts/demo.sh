#!/usr/bin/env bash
# demo.sh: the SellOS demo environment (SOS-DEMO-1). A control site and two company sites with data, to look at
# in a browser. No gate touches them. Sign ins and URLs: docs/DEMO.md.
#
#   scripts/demo.sh seed     make what is missing (sites, users, data) and start the server. Safe to repeat
#   scripts/demo.sh reset    drop the demo sites and their databases, then seed from nothing
#   scripts/demo.sh status   which sites exist, whether the server answers for each, the LaunchAgent
#   scripts/demo.sh start    install and start the LaunchAgent com.sellos.demo (seed does this)
#   scripts/demo.sh stop     stop the server and unload the LaunchAgent. The sites and their data stay
#
# The sites are sellos_tenant_demo<id>.localhost, made through the tenant provisioning path (the control
# site's worker, the MariaDB provisioner account). The server is scripts/lib/demo_server.py on 127.0.0.1:8006,
# routing by Host header, with no reloader. Nothing here touches 8000, 8002 or 8004, or any other site.
# SELLOS_DEMO_WRITE_ONLY=1 writes the plist and touches neither launchd nor the port (the tests).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
BASELINE_DIR="${SELLOS_BASELINE_DIR:-$HOME/iespl-baseline}"
AGENTS="${SELLOS_LAUNCH_AGENTS_DIR:-$HOME/Library/LaunchAgents}"
PY="${SELLOS_TENANT_PYTHON:-$BENCH_DIR/env/bin/python}"
PORT=8006
LABEL="com.sellos.demo"
PLIST="$AGENTS/$LABEL.plist"
DOMAIN="gui/$(id -u)"
WRITE_ONLY="${SELLOS_DEMO_WRITE_ONLY:-0}"

usage() { echo "usage: scripts/demo.sh seed | reset | status | start | stop" >&2; exit 2; }
[ "$#" -eq 1 ] || usage

# Run sellos.testing.demo with the bench's Python, from the bench's sites folder.
demo() {
  [ -x "$PY" ] || { echo "The bench Python is missing at $PY. Set SELLOS_BENCH_DIR." >&2; exit 3; }
  (cd "$BENCH_DIR/sites" && SELLOS_BENCH_DIR="$BENCH_DIR" "$PY" -m sellos.testing.demo "$@")
}

write_plist() {
  mkdir -p "$AGENTS" "$BASELINE_DIR"
  local new
  new="$(mktemp)"
  cat >"$new" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$REPO_DIR/scripts/lib/demo_server.py</string>
    <string>--port</string>
    <string>$PORT</string>
  </array>
  <key>WorkingDirectory</key><string>$BENCH_DIR/sites</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$BASELINE_DIR/sellos-demo.log</string>
  <key>StandardErrorPath</key><string>$BASELINE_DIR/sellos-demo.log</string>
</dict>
</plist>
PLIST_EOF
  if [ -f "$PLIST" ] && cmp -s "$new" "$PLIST"; then rm -f "$new"; return 1; fi
  mv "$new" "$PLIST"
  return 0
}

loaded() { launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; }

start_server() {
  local changed=0
  write_plist && changed=1
  [ "$WRITE_ONLY" = "1" ] && { echo "Wrote $PLIST (write only: launchd and port $PORT untouched)."; return 0; }
  command -v plutil >/dev/null 2>&1 && plutil -lint "$PLIST" >/dev/null
  # Only a changed plist, or an agent that is not loaded, restarts the server, so seeding again does not
  # drop the browser's connection.
  if [ "$changed" = 1 ] && loaded; then launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true; fi
  loaded || launchctl bootstrap "$DOMAIN" "$PLIST"
  local i
  for i in $(seq 1 30); do
    if curl -s -o /dev/null --max-time 3 -H "Host: sellos_tenant_democontrol.localhost:$PORT" "http://127.0.0.1:$PORT/api/method/ping"; then
      echo "The demo server answers on port $PORT."
      return 0
    fi
    sleep 1
  done
  echo "The demo server did not answer on port $PORT in 30 seconds. See $BASELINE_DIR/sellos-demo.log." >&2
  return 1
}

# A running server keeps the roles and permissions it cached before the seed changed them (found 20 Nov 2026:
# a Company Admin got "You do not have permission to do this" under Assigned agent, from a server started
# 18 Nov, while the same calls passed in a fresh process). Seeding runs in another process, so restart the
# server after it, so what the browser sees is what the seed wrote.
restart_if_running() {
  [ "$WRITE_ONLY" = "1" ] && return 0
  if loaded; then launchctl kickstart -k "$DOMAIN/$LABEL" >/dev/null 2>&1 || true; fi
}

case "$1" in
  seed)
    demo seed
    restart_if_running
    start_server
    echo "Sign ins: docs/DEMO.md"
    ;;
  reset)
    demo reset
    restart_if_running
    start_server
    echo "Sign ins: docs/DEMO.md"
    ;;
  status)
    demo status
    if [ "$WRITE_ONLY" = "1" ]; then exit 0; fi
    if loaded; then echo "LaunchAgent $LABEL: loaded"; else echo "LaunchAgent $LABEL: not loaded"; fi
    ;;
  start) start_server ;;
  stop)
    if [ "$WRITE_ONLY" = "1" ]; then echo "Write only: nothing stopped."; exit 0; fi
    launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
    echo "The demo server is stopped. The demo sites and their data are kept. Start it again with: scripts/demo.sh start"
    ;;
  *) usage ;;
esac
