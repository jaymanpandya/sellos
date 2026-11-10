# Secrets (SOS-P0-09)

Keys and passwords never go in a repository. They live in encrypted settings (a site's
`site_config.json` or a password field) or in environment variables.

## The scan

* gitleaks runs as a pre-commit hook (`.pre-commit-config.yaml`), so a commit that stages a key is
  refused on the developer's machine.
* The same hook runs in the `Linters` workflow (`pre-commit/action`) on every push to 1.0 and every
  pull request, so a key that got past a local hook turns the check red.
* `sellos/tests/test_secret_scan.py` stages a fake key in a scratch repository and confirms the hook
  blocks it, and that a clean file passes.

## If a real key is committed

Revoke it at the provider first, then remove it from the repository. Deleting it in a later commit is
not enough, because history keeps it.

## False positives

Never add a real key to an allowlist. Build fake test values in pieces, as the scan test does.
