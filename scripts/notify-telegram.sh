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
set -euo pipefail

MESSAGE="${1:?Usage: notify-telegram.sh \"<message>\"}"

: "${SELLOS_TELEGRAM_BOT_TOKEN:?Set SELLOS_TELEGRAM_BOT_TOKEN in your environment}"
: "${SELLOS_TELEGRAM_CHAT_ID:?Set SELLOS_TELEGRAM_CHAT_ID in your environment}"

curl -sS -X POST \
  "https://api.telegram.org/bot${SELLOS_TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${SELLOS_TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=${MESSAGE}" \
  -d "parse_mode=HTML" \
  > /dev/null
