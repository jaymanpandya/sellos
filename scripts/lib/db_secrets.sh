# db_secrets.sh: the MariaDB provisioner account the agent gets, and nothing else (SOS-SETUP-18).
# Sourced by scripts/build-loop.sh, scripts/run-tests.sh and scripts/notify-telegram.sh. Tested by
# sellos/tests/test_db_secrets.py.
#
# Tenant sites are created and dropped with a narrow MariaDB account, never with root (Jayman,
# 4 November 2026). It has CREATE USER, RELOAD and SHOW DATABASES globally, and ALL PRIVILEGES WITH
# GRANT OPTION on `sellos\_tenant\_%`.* only. Its name and password come from the environment the
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
SELLOS_AGENT_KEEP=" SELLOS_DB_PROVISIONER_USER SELLOS_DB_PROVISIONER_PASSWORD ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN "

# Run a command (claude -p) with every credential variable removed from its environment except the
# provisioner's two. The password is inherited through the environment, never put on argv.
#   sellos_agent_env <command> [args...]
sellos_agent_env() {
  local name drop=()
  while IFS= read -r name; do
    [[ "$SELLOS_AGENT_KEEP" == *" $name "* ]] && continue
    if [[ "$name" =~ $SELLOS_SECRET_NAME_RE ]]; then drop+=(-u "$name"); fi
  done < <(compgen -e)
  env ${drop[@]+"${drop[@]}"} "$@"
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
