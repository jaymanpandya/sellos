#!/usr/bin/env bash
# Run once per clone. Points git at the hooks in .githooks.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
chmod +x "$REPO"/.githooks/* "$REPO"/scripts/*.sh "$REPO"/scripts/*.py
git -C "$REPO" config core.hooksPath .githooks
echo "Git hooks installed. Every commit now runs scripts/test_all.sh, and every push checks the gate ran."
