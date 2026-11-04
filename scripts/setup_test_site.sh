#!/usr/bin/env bash
# Run once. Creates the dedicated test site that the gate uses. It does not touch other sites.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH="${SELLOS_BENCH:-$(cd "$REPO/../.." && pwd)}"
SITE="${SELLOS_TEST_SITE:-sellos_test.localhost}"

case "$SITE" in
sellos.localhost | *buildos* | *pamaa* | *awh* | *dev_site* | test_site)
	echo "Refusing to create or use site $SITE." >&2
	exit 2
	;;
esac

if [ -d "$BENCH/sites/$SITE" ]; then
	echo "Test site $SITE already exists."
	exit 0
fi

echo "bench will ask for the MariaDB root password."
(cd "$BENCH" && bench new-site "$SITE" --admin-password "${SELLOS_TEST_ADMIN_PASSWORD:-admin}" --install-app sellos)
(cd "$BENCH" && bench --site "$SITE" set-config allow_tests true)
echo "Test site $SITE is ready."
