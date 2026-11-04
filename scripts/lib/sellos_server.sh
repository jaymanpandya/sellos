# sellos_server.sh: which port the SellOS server is on, and proof that it really is SellOS.
# Sourced by scripts/run-tests.sh and scripts/prepare-regression.sh. Tested by
# sellos/tests/test_sellos_server_port.py.
#
# The port rule (Jayman, always): BuildOS runs on 8000, Pamaa on 8002, SellOS on 8004. SellOS never
# uses 8000 or 8002, and never starts, stops or touches the servers on them. Each server is pinned
# to one site. The SellOS server is always started as:
#   cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004
# A plain "bench serve --port 8004" without --site falls back to default_site and serves BuildOS's
# site for every host name, and that server answered /api/method/ping all the same.
#
# CI is not affected: it runs on its own machine, with its own bench start on port 8000
# (.github/workflows/ci.yml), and never runs these scripts. Do not change CI to match this file.

SELLOS_PORT=8004
SELLOS_SERVE_CMD="cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004"

# Exit with an environment status (2 or 3), and record it in $SELLOS_ENV_EXIT_FILE when that is set.
# scripts/run-tests.sh trusts a 2 or 3 only when it was recorded here, because under set -e a failing
# command exits with its own status, which can be 2 or 3 too (SOS-SETUP-14).
#   sellos_env_exit <status>
sellos_env_exit() {
  if [ -n "${SELLOS_ENV_EXIT_FILE:-}" ]; then echo "$1" >"$SELLOS_ENV_EXIT_FILE"; fi
  exit "$1"
}

# Print the webserver_port Frappe uses for a site: sites/<site>/site_config.json first, then
# sites/common_site_config.json, the order frappe.get_conf(site) uses. run-ui-tests builds Cypress's
# base URL from it. Prints nothing when neither file sets it.
#   sellos_site_port <bench dir> <site>
sellos_site_port() {
  python3 - "$1" "$2" <<'PY'
import json
import sys
from pathlib import Path

sites = Path(sys.argv[1]) / "sites"
for path in (sites / sys.argv[2] / "site_config.json", sites / "common_site_config.json"):
    try:
        conf = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        continue
    if "webserver_port" in conf:
        print(conf["webserver_port"])
        break
PY
}

# Set PORT to the site's port, or exit 2 if it is not 8004.
#   sellos_require_port <bench dir> <site>
sellos_require_port() {
  PORT="$(sellos_site_port "$1" "$2" || true)"
  if [ "$PORT" != "$SELLOS_PORT" ]; then
    echo "The webserver_port for $2 is '${PORT:-unset}', not $SELLOS_PORT. SellOS runs only on port $SELLOS_PORT." >&2
    echo "Run: bench --site $2 set-config -p webserver_port $SELLOS_PORT" >&2
    sellos_env_exit 2
  fi
}

# Exit 3 unless the server at <host>:<port> answers ping AND is SellOS. Anything answers ping, so
# a guest GET of /sellos must answer 301 or 302: only SellOS's page renderer redirects a guest.
#   sellos_preflight <host> <port>
sellos_preflight() {
  local host="$1" port="$2" code
  if ! curl -sf -o /dev/null --max-time 10 "http://$host:$port/api/method/ping"; then
    echo "Nothing answers http://$host:$port/api/method/ping. Start the SellOS server with: $SELLOS_SERVE_CMD" >&2
    echo "Cypress needs the site at its own address. Create it once with scripts/make-baseline.sh --create." >&2
    sellos_env_exit 3
  fi
  code="$(curl -s -o /dev/null --max-time 20 -w '%{http_code}' "http://$host:$port/sellos" || true)"
  case "$code" in
    301 | 302) ;;
    *)
      echo "A guest GET of http://$host:$port/sellos answered '$code', not 301 or 302." >&2
      echo "The server on port $port is not serving SellOS. Start it with: $SELLOS_SERVE_CMD" >&2
      sellos_env_exit 3
      ;;
  esac
}
