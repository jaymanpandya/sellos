#!/usr/bin/env bash
# install-bench.sh: install a SellOS bench on a fresh server (SOS-P0-06).
#
#   deploy/install-bench.sh [--dry-run] [--bench-dir DIR] [--repo URL] [--python PYTHON]
#
# Installs a bench pinned to one Frappe 16 version, turns on DNS multitenancy (one site per host
# name, so each company's subdomain serves its own site), installs SellOS from its 1.0 branch and
# generates the nginx configuration. It creates no site: tenant sites are made by the provisioner.
#
# --dry-run prints every command, each on a line that starts with "+ ", and runs none.
#
# It refuses, before any command runs, a folder that already holds a bench (the folder has
# sites/apps.txt, apps/frappe or sites/common_site_config.json), and it always refuses ~/iespl-bench,
# the shared development bench (SOS-SETUP-20). Exit 2 for a refusal or a bad option.
# Running it on staging and production is SOS-P0-06D (AMP Labs), never the build loop's.
set -euo pipefail

# The one place the Frappe version is pinned. scripts/check_ci_parity.py and the test of this script
# keep it equal to the --frappe-branch in .github/workflows/ci.yml.
FRAPPE_BRANCH="version-16"
SELLOS_BRANCH="1.0"

DRY_RUN=0
BENCH_DIR="${SELLOS_BENCH_DIR:-$HOME/sellos-bench}"
REPO_URL="https://github.com/jaymanpandya/sellos.git"
PYTHON_BIN="python3.14"

usage() {
  echo "usage: deploy/install-bench.sh [--dry-run] [--bench-dir DIR] [--repo URL] [--python PYTHON]" >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --bench-dir) [ "$#" -ge 2 ] || usage; BENCH_DIR="$2"; shift 2 ;;
    --repo) [ "$#" -ge 2 ] || usage; REPO_URL="$2"; shift 2 ;;
    --python) [ "$#" -ge 2 ] || usage; PYTHON_BIN="$2"; shift 2 ;;
    *) usage ;;
  esac
done

# Remove "." and ".." components by text, so a folder that does not exist yet still resolves.
normalize() {
  local part out=() IFS=/
  for part in $1; do
    case "$part" in
      "" | ".") ;;
      "..") [ "${#out[@]}" -gt 0 ] && unset 'out[${#out[@]}-1]' ;;
      *) out+=("$part") ;;
    esac
  done
  echo "/${out[*]-}"
}

# The real path (symbolic links followed) of the nearest existing parent, plus the rest.
resolve() {
  local p tail=""
  p="$(normalize "$1")"
  while [ ! -e "$p" ] && [ "$p" != "/" ]; do
    tail="/$(basename "$p")$tail"
    p="$(dirname "$p")"
  done
  echo "$(cd "$p" && pwd -P)$tail"
}

case "$BENCH_DIR" in
  "~") BENCH_DIR="$HOME" ;;
  "~/"*) BENCH_DIR="$HOME/${BENCH_DIR#"~/"}" ;;
esac
case "$BENCH_DIR" in
  /*) ;;
  *) BENCH_DIR="$PWD/$BENCH_DIR" ;;
esac
BENCH_DIR="$(resolve "$BENCH_DIR")"

# Refusals come first: nothing below runs until they pass.
if [ "$BENCH_DIR" = "$(resolve "$HOME/iespl-bench")" ]; then
  echo "Refusing $BENCH_DIR: it is the shared development bench, never installed over." >&2
  exit 2
fi
if [ -e "$BENCH_DIR/sites/apps.txt" ] || [ -e "$BENCH_DIR/apps/frappe" ] ||
  [ -e "$BENCH_DIR/sites/common_site_config.json" ]; then
  echo "Refusing $BENCH_DIR: it already holds a bench. Use an empty folder." >&2
  exit 2
fi

step() {
  if [ "$DRY_RUN" = 1 ]; then
    echo "+ $*"
  else
    echo "+ $*"
    "$@"
  fi
}

[ "$DRY_RUN" = 1 ] && echo "Dry run: every command is printed and none is run."
echo "Frappe branch: $FRAPPE_BRANCH. SellOS branch: $SELLOS_BRANCH. Bench folder: $BENCH_DIR."

step bench init --frappe-branch "$FRAPPE_BRANCH" --python "$PYTHON_BIN" "$BENCH_DIR"

# The bench commands below run inside the new bench.
if [ "$DRY_RUN" = 1 ]; then
  echo "+ cd $BENCH_DIR"
else
  echo "+ cd $BENCH_DIR"
  cd "$BENCH_DIR"
fi

step bench config dns_multitenant on
step bench get-app sellos "$REPO_URL" --branch "$SELLOS_BRANCH"
step bench setup nginx --yes
step sudo ln -sf "$BENCH_DIR/config/nginx.conf" /etc/nginx/conf.d/sellos.conf
step sudo nginx -t
step sudo systemctl reload nginx
echo "Done. Create company sites with the provisioner, not with this script."
