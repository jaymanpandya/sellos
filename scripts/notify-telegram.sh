#!/usr/bin/env bash
# notify-telegram.sh — post one message to the SellOS build loop's Telegram chat.
#
# Usage: notify-telegram.sh "<message text>"
#
# Requires two environment variables, deliberately not hardcoded here:
#   SELLOS_TELEGRAM_BOT_TOKEN
#   SELLOS_TELEGRAM_CHAT_ID
# Set these in your shell profile, or export them before launching
# build-loop.sh, so the token never lands in this file or in git.
#
# SOS-SETUP-17: every message is also printed, so it is in the loop's log whether or not Telegram is
# set up. A missing token or a failed send is reported and never fails the caller: build-loop.sh
# calls this after a task completes, and an exit 1 here used to stop the loop after every task.
set -uo pipefail

MESSAGE="${1:?Usage: notify-telegram.sh \"<message>\"}"

# SOS-SETUP-18: the MariaDB provisioner account's user name and password never reach a notification
# or the loop log. Without the redaction library nothing is printed or sent.
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/db_secrets.sh"
if [ ! -f "$LIB" ]; then
  echo "NOTIFY: withheld, $LIB is missing, so the message cannot be redacted." >&2
  exit 0
fi
# shellcheck source=lib/db_secrets.sh
source "$LIB"
MESSAGE="$(sellos_redact_text "$MESSAGE")"

printf 'NOTIFY: %s\n' "$MESSAGE"

if [ -z "${SELLOS_TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${SELLOS_TELEGRAM_CHAT_ID:-}" ]; then
  echo "NOTIFY: not sent to Telegram, SELLOS_TELEGRAM_BOT_TOKEN or SELLOS_TELEGRAM_CHAT_ID is not set." >&2
  exit 0
fi

if ! curl -sS --max-time 20 -X POST \
  "https://api.telegram.org/bot${SELLOS_TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${SELLOS_TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=${MESSAGE}" \
  -d "parse_mode=HTML" \
  > /dev/null 2>&1; then
  echo "NOTIFY: the Telegram send failed. The message is above." >&2
fi
exit 0
