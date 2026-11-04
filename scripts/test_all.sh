#!/usr/bin/env bash
# The SellOS gate. It runs the backend and frontend tests and the HTTP smoke checks.
# The git hooks in .githooks run it before every commit. You can also run it by hand:
#   scripts/test_all.sh          full gate
#   scripts/test_all.sh fast     lint, test presence check and frontend unit tests only
# It never touches the main bench processes. It uses its own test site and its own port.
set -euo pipefail

MODE="${1:-full}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH="${SELLOS_BENCH:-$(cd "$REPO/../.." && pwd)}"
SITE="${SELLOS_TEST_SITE:-sellos_test.localhost}"
PORT="${SELLOS_TEST_PORT:-8004}"
LOGS="${TMPDIR:-/tmp}/sellos_gate"
mkdir -p "$LOGS"

# Refuse to run against anything that is not the dedicated test site and port.
case "$SITE" in
sellos.localhost | *buildos* | *pamaa* | *awh* | *dev_site* | test_site)
	echo "Refusing to use site $SITE. Use a dedicated test site such as sellos_test.localhost." >&2
	exit 2
	;;
esac
case "$PORT" in
8000 | 8003 | 9000 | 11000 | 13000)
	echo "Refusing to use port $PORT. It belongs to a running bench or dev server." >&2
	exit 2
	;;
esac

# A commit that only changes Markdown needs the lint step, not the whole suite.
STAGED="$(git -C "$REPO" diff --cached --name-only 2>/dev/null || true)"
if [ -n "$STAGED" ] && ! echo "$STAGED" | grep -qv '\.md$'; then
	MODE="docs"
fi

STEP_NO=0
FAILED=""
SERVER_PID=""
START_ALL=$(date +%s)

stop_server() {
	pkill -f "serve --port $PORT" 2>/dev/null || true
	if command -v lsof >/dev/null 2>&1; then
		lsof -ti "tcp:$PORT" 2>/dev/null | xargs kill 2>/dev/null || true
	fi
}

cleanup() {
	if [ -n "$SERVER_PID" ]; then
		stop_server
	fi
}
trap cleanup EXIT

run() {
	local name="$1"
	shift
	STEP_NO=$((STEP_NO + 1))
	local log="$LOGS/step_${STEP_NO}.log"
	local t0
	t0=$(date +%s)
	printf '%-44s ' "[$STEP_NO] $name"
	if "$@" >"$log" 2>&1; then
		echo "PASS ($(($(date +%s) - t0))s)"
	else
		echo "FAIL"
		echo "----- last 40 lines of $log -----"
		tail -n 40 "$log"
		FAILED="$name"
		exit 1
	fi
}

in_frontend() { (cd "$REPO/frontend" && "$@"); }
in_bench() { (cd "$BENCH" && "$@"); }

wait_for_server() {
	for _ in $(seq 1 60); do
		if curl -s -o /dev/null "http://localhost:$PORT/api/method/ping"; then
			return 0
		fi
		sleep 1
	done
	echo "The test server did not start on port $PORT" >&2
	tail -n 30 "$LOGS/server.log" >&2 || true
	return 1
}

# Not under set -e: this function runs inside an if, so every status is checked by hand.
smoke_http() {
	local status=0 users=""
	if curl -s -o /dev/null "http://localhost:$PORT/api/method/ping"; then
		echo "Something is already listening on port $PORT, so the smoke check would test the wrong server." >&2
		echo "Stop it, or set SELLOS_TEST_PORT to a free port." >&2
		return 1
	fi
	in_bench bench --site "$SITE" serve --port "$PORT" >"$LOGS/server.log" 2>&1 &
	SERVER_PID=$!

	wait_for_server || status=1
	if [ "$status" -eq 0 ]; then
		users="$(in_bench bench --site "$SITE" execute sellos.testing.users.users_for_smoke | tail -n 1)" || status=1
	fi
	if [ "$status" -eq 0 ]; then
		SELLOS_SMOKE_BASE="http://localhost:$PORT" SELLOS_SMOKE_USERS="$users" \
			python3 "$REPO/scripts/smoke_http.py" || status=1
	fi

	stop_server
	SERVER_PID=""
	return "$status"
}

echo "SellOS gate ($MODE). Repo: $REPO"

run "tests accompany code changes" python3 "$REPO/scripts/check_tests_changed.py"
run "lint (pre-commit hooks)" bash -c "cd '$REPO' && pre-commit run --all-files"

if [ "$MODE" != "docs" ]; then
	run "frontend install (frozen lockfile)" in_frontend yarn install --frozen-lockfile
	run "frontend unit tests" in_frontend yarn test
fi

if [ "$MODE" = "full" ]; then
	run "frontend build" in_frontend yarn build
	if [ ! -d "$BENCH/sites/$SITE" ]; then
		echo "The test site $SITE does not exist. Create it once with: scripts/setup_test_site.sh" >&2
		exit 1
	fi
	run "site migrate" in_bench bench --site "$SITE" migrate
	run "test users created and read back" in_bench bench --site "$SITE" execute sellos.testing.users.ensure_test_users
	run "backend tests (bench run-tests)" in_bench bench --site "$SITE" run-tests --app sellos
	run "HTTP smoke: login and /sellos as real users" smoke_http
fi

TREE="$(git -C "$REPO" write-tree 2>/dev/null || true)"
if [ -n "$TREE" ]; then
	echo "$TREE $(date +%s) $MODE" >>"$REPO/.git/sellos_gate_log"
fi
echo "GATE PASSED ($MODE) in $(($(date +%s) - START_ALL))s. Tree: ${TREE:-unknown}"
