#!/usr/bin/env bash
# install-launch-agent.sh: run the SellOS server as a LaunchAgent (SOS-SETUP-33).
#
#   scripts/install-launch-agent.sh             install, or reinstall, and start it
#   scripts/install-launch-agent.sh --replace   also stop a SellOS server started by hand on 8004 first
#   scripts/install-launch-agent.sh --remove    stop it and remove both agents
#
# Two agents in ~/Library/LaunchAgents:
#   com.sellos.server         cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004
#                             (the only way the SellOS server is started), started at login and
#                             restarted whenever it exits (KeepAlive)
#   com.sellos.server-health  every 2 minutes, and after sleep, `scripts/sellos server-check`: when the
#                             server no longer serves sellos_test.localhost (a process that survives sleep
#                             but stops answering), it restarts com.sellos.server
# Logs: ~/iespl-baseline/sellos-server.log and sellos-server-health.log.
# It never touches the servers on 8000 (BuildOS) or 8002 (Pamaa). A server it did not start is
# stopped only with --replace, and only when its command line is the pinned SellOS one.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/iespl-bench}"
BASELINE_DIR="${SELLOS_BASELINE_DIR:-$HOME/iespl-baseline}"
AGENTS="${SELLOS_LAUNCH_AGENTS_DIR:-$HOME/Library/LaunchAgents}"
SITE="sellos_test.localhost"
PORT=8004
DOMAIN="gui/$(id -u)"
SERVER_LABEL="com.sellos.server"
HEALTH_LABEL="com.sellos.server-health"
SERVER_PLIST="$AGENTS/$SERVER_LABEL.plist"
HEALTH_PLIST="$AGENTS/$HEALTH_LABEL.plist"
MODE="${1:-install}"

unload() { launchctl bootout "$DOMAIN/$1" >/dev/null 2>&1 || true; }

if [ "$MODE" = "--remove" ]; then
  unload "$HEALTH_LABEL"
  unload "$SERVER_LABEL"
  rm -f "$SERVER_PLIST" "$HEALTH_PLIST"
  echo "Removed $SERVER_LABEL and $HEALTH_LABEL. Start the server by hand with: cd $BENCH_DIR && bench --site sellos_test.localhost serve --port 8004"
  exit 0
fi
if [ "$MODE" != "install" ] && [ "$MODE" != "--replace" ]; then
  echo "Usage: $0 [--replace | --remove]" >&2
  exit 2
fi

BENCH_BIN="$(command -v bench || true)"
if [ -z "$BENCH_BIN" ]; then
  echo "bench is not on PATH. Install it as for the rest of the bench, then run this again." >&2
  exit 3
fi

# A server already on 8004 that launchd did not start would hold the port, and the agent would
# restart forever. Stop it only with --replace, and only when it is the pinned SellOS server.
unload "$SERVER_LABEL"
for pid in $(lsof -nP -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true); do
  cmdline="$(ps -o command= -p "$pid" 2>/dev/null || true)"
  if [[ "$cmdline" != *"--site $SITE"* && "$cmdline" != *"--site=$SITE"* ]]; then
    # A worker of a pinned server shows no --site; its parent does.
    parent="$(ps -o ppid= -p "$pid" | tr -d ' ')"
    cmdline="$cmdline $(ps -o command= -p "$parent" 2>/dev/null || true)"
  fi
  if [[ "$cmdline" != *"$SITE"* ]]; then
    echo "Port $PORT is held by pid $pid, which is not the SellOS server:" >&2
    echo "  $cmdline" | cut -c1-200 >&2
    echo "Stop that process yourself; SellOS will not touch it." >&2
    exit 1
  fi
  if [ "$MODE" != "--replace" ]; then
    echo "A SellOS server started by hand runs on $PORT (pid $pid). Stop it, or run: $0 --replace" >&2
    exit 1
  fi
  echo "Stopping the SellOS server started by hand (pid $pid)."
  kill -TERM "$pid" 2>/dev/null || true
done
for _ in $(seq 1 20); do
  lsof -nP -t -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || break
  sleep 1
done

mkdir -p "$AGENTS" "$BASELINE_DIR"
PATH_FOR_AGENT="$(dirname "$BENCH_BIN"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cat >"$SERVER_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$SERVER_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-c</string>
    <string>cd "$BENCH_DIR" &amp;&amp; exec "$BENCH_BIN" --site sellos_test.localhost serve --port 8004</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$PATH_FOR_AGENT</string>
    <key>HOME</key><string>$HOME</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>ProcessType</key><string>Interactive</string>
  <key>StandardOutPath</key><string>$BASELINE_DIR/sellos-server.log</string>
  <key>StandardErrorPath</key><string>$BASELINE_DIR/sellos-server.log</string>
</dict>
</plist>
EOF

cat >"$HEALTH_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$HEALTH_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$REPO_DIR/scripts/sellos</string>
    <string>server-check</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>$PATH_FOR_AGENT</string>
    <key>HOME</key><string>$HOME</string>
  </dict>
  <key>StartInterval</key><integer>120</integer>
  <key>StandardOutPath</key><string>$BASELINE_DIR/sellos-server-health.log</string>
  <key>StandardErrorPath</key><string>$BASELINE_DIR/sellos-server-health.log</string>
</dict>
</plist>
EOF

plutil -lint "$SERVER_PLIST" "$HEALTH_PLIST" >/dev/null
unload "$HEALTH_LABEL"
launchctl bootstrap "$DOMAIN" "$SERVER_PLIST"
launchctl bootstrap "$DOMAIN" "$HEALTH_PLIST"

echo "Installed $SERVER_LABEL and $HEALTH_LABEL. Waiting for the server to serve $SITE on $PORT..."
for _ in $(seq 1 45); do
  code="$(curl -s -o /dev/null --max-time 5 -w '%{http_code}' "http://$SITE:$PORT/sellos" || true)"
  if [ "$code" = "301" ] || [ "$code" = "302" ]; then
    echo "The SellOS server is up (guest /sellos answers $code). Log: $BASELINE_DIR/sellos-server.log"
    exit 0
  fi
  sleep 2
done
echo "The server did not come up in 90 seconds. Read $BASELINE_DIR/sellos-server.log" >&2
exit 1
