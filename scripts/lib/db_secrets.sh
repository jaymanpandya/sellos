# db_secrets.sh: the MariaDB provisioner account the agent gets, and nothing else (SOS-SETUP-18).
# Sourced by scripts/build-loop.sh, scripts/run-tests.sh and scripts/notify-telegram.sh. Tested by
# sellos/tests/test_db_secrets.py.
#
# Tenant sites are created and dropped with a narrow MariaDB account, never with root (Jayman,
# 4 November 2026). Since SOS-SETUP-22 the agent never gets the password in its environment: code reads
# it with sellos.provisioning.credentials.get_provisioner_password() (the variable, else the macOS
# Keychain item sellos_provisioner) and hands it to bench only through a child process's environment.
# The loop and the gate load it into their own environment (sellos_load_provisioner_password) so the
# redaction filter and the leak check know the value; sellos_agent_env strips it again. It has CREATE USER, RELOAD and SHOW DATABASES globally, and ALL PRIVILEGES WITH
# GRANT OPTION on `sellos\_tenant\_%`.* and `sellos_tenant_%`.* only (Frappe's new-site needs the plain one). Its name and password come from the environment the
# loop is started in:
#   SELLOS_DB_PROVISIONER_USER      default sellos_provisioner
#   SELLOS_DB_PROVISIONER_PASSWORD  no default
# Their values are never printed, logged, put on a command line here, or sent in a notification.
# Everything the loop writes goes through sellos_redact, and the gate fails a run whose logs,
# repository or tenant sites hold the password (scripts/check_no_secret_leak.py).

export SELLOS_DB_PROVISIONER_USER="${SELLOS_DB_PROVISIONER_USER:-sellos_provisioner}"

# Exported names that look like a credential. The agent gets none of them, except the two above and
# the ones claude itself needs to sign in. That covers any MariaDB root password variable, the
# Telegram token, GitHub tokens and the other apps' secrets on this machine.
SELLOS_SECRET_NAME_RE='PASSWORD|PASSWD|SECRET|TOKEN|CREDENTIAL|API_KEY|ACCESS_KEY|PRIVATE_KEY|^MYSQL_PWD$|^MARIADB_|^MYSQL_ROOT|^SELLOS_DB_|^SELLOS_TELEGRAM_'
SELLOS_AGENT_KEEP=" SELLOS_DB_PROVISIONER_USER ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN "

# Run a command (claude -p) with every credential variable removed from its environment except the
# provisioner's user name and what claude needs to sign in. The provisioner password is removed too
# (SOS-SETUP-22): the agent's code reads it from the Keychain through get_provisioner_password().
#   sellos_agent_env <command> [args...]
sellos_agent_env() {
  local name drop=()
  while IFS= read -r name; do
    [[ "$SELLOS_AGENT_KEEP" == *" $name "* ]] && continue
    if [[ "$name" =~ $SELLOS_SECRET_NAME_RE ]]; then drop+=(-u "$name"); fi
  done < <(compgen -e)
  env ${drop[@]+"${drop[@]}"} "$@"
}

# The Keychain item that holds the provisioner password (SOS-SETUP-22).
SELLOS_KEYCHAIN_SERVICE=sellos_provisioner
SELLOS_STORE_COMMAND='security add-generic-password -a "$USER" -s sellos_provisioner -w'

# Is the password available, without reading it? 0 when SELLOS_DB_PROVISIONER_PASSWORD is set or the
# Keychain item exists (security find-generic-password without -w prints no secret).
sellos_provisioner_available() {
  [ -n "${SELLOS_DB_PROVISIONER_PASSWORD:-}" ] && return 0
  command -v security >/dev/null 2>&1 || return 1
  security find-generic-password -s "$SELLOS_KEYCHAIN_SERVICE" >/dev/null 2>&1
}

# Put the password in this shell's environment, never on screen, so sellos_redact and the leak check
# can find it. Called by the loop and the gate before their output filter starts. The agent never
# gets it (sellos_agent_env). Returns 1, and sets nothing, when it is not available.
sellos_load_provisioner_password() {
  [ -n "${SELLOS_DB_PROVISIONER_PASSWORD:-}" ] && return 0
  sellos_provisioner_available || return 1
  local value
  value="$(security find-generic-password -s "$SELLOS_KEYCHAIN_SERVICE" -w 2>/dev/null)" || return 1
  [ -n "$value" ] || return 1
  export SELLOS_DB_PROVISIONER_PASSWORD="$value"
}

# Copy stdin to stdout with the provisioner's user name and password replaced. The values are read
# from the environment inside Python, so they are never on a command line. Line buffered, so it can
# sit in a pipe in front of tee.
#   some command | sellos_redact
sellos_redact() {
  python3 -u -c '
import os
import sys

pairs = [
    (os.environ.get("SELLOS_DB_PROVISIONER_PASSWORD", ""), b"[provisioner password]"),
    (os.environ.get("SELLOS_DB_PROVISIONER_USER", ""), b"[provisioner user]"),
]
pairs = [(v.encode(), r) for v, r in pairs if v]
src, out = sys.stdin.buffer, sys.stdout.buffer
for line in iter(src.readline, b""):
    for value, replacement in pairs:
        line = line.replace(value, replacement)
    out.write(line)
    out.flush()
'
}

# Print a string redacted.
#   sellos_redact_text "<text>"
sellos_redact_text() {
  printf '%s\n' "$1" | sellos_redact
}
