"""SOS-SETUP-36: a baseline restore resets every table, and the gate checks the test site is clean.

On 13 November 2026 the backend suite failed 13 times on rows no test had made. The 4 November
baseline lacked seven tables (DocTypes added since), a dump drops and recreates only the tables it
holds, so the gate's restore never cleared them: an active Support Grant and Consent Records an agent
had seeded by hand carried into the backend suite. And nothing reset the site between the changed
specs and the backend suite, so a row a spec's after hook missed carried over too.

Each test here makes its own tenant site (the only sites besides sellos_test.localhost the restore
accepts), works on that, and drops it, even when the test fails. sellos_test.localhost is never
touched, so these run safely inside the gate's own backend suite.
"""

import os
import re
import secrets
import subprocess
import tempfile
from pathlib import Path

from frappe.tests import IntegrationTestCase, UnitTestCase

from sellos.provisioning import tenant_sites

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "scripts" / "lib"
RESTORE = LIB / "restore_baseline.sh"
CHECK = LIB / "check_clean_site.sh"
RUN_TESTS = REPO_ROOT / "scripts" / "run-tests.sh"
PREPARE_REGRESSION = REPO_ROOT / "scripts" / "prepare-regression.sh"
BUILD_LOOP = REPO_ROOT / "scripts" / "build-loop.sh"
SELLOS_CLI = REPO_ROOT / "scripts" / "sellos"

# The tables the 4 November baseline lacked.
MISSING_FROM_BASELINE = (
	"Consent Record",
	"Pipeline Stage",
	"Plan",
	"Provisioning Job",
	"Support Access Log",
	"Support Grant",
	"Tenant",
)
# The tables check_clean_site.sh counts.
CHECKED = ("Consent Record", "Provisioning Job", "Support Access Log", "Support Grant", "Tenant")


def bench(site, *args, stdin=None):
	return subprocess.run(
		["bench", "--site", site, *args],
		cwd=tenant_sites.bench_dir(),
		input=stdin,
		capture_output=True,
		text=True,
		check=False,
	)


def sql(site, statement):
	result = bench(site, "mariadb", "-N", "-e", statement)
	if result.returncode != 0:
		raise AssertionError(f"SQL on {site} failed: {statement}\n{result.stdout}{result.stderr}")
	return result.stdout.strip()


def make_table(site, doctype, rows=0):
	sql(site, f"CREATE TABLE `tab{doctype}` (name varchar(140) PRIMARY KEY, note text)")
	for n in range(rows):
		sql(site, f"INSERT INTO `tab{doctype}` (name, note) VALUES ('left-{n}', 'left behind')")


def table_exists(site, doctype):
	count = sql(
		site,
		"SELECT COUNT(*) FROM information_schema.tables "
		f"WHERE table_schema = DATABASE() AND table_name = 'tab{doctype}'",
	)
	return count == "1"


def rows_in(site, doctype):
	return int(sql(site, f"SELECT COUNT(*) FROM `tab{doctype}`"))


def save_baseline(site):
	"""Dump the site the way scripts/make-baseline.sh does (bench backup) and return the .sql.gz."""
	result = bench(site, "backup")
	if result.returncode != 0:
		raise AssertionError(f"bench backup of {site} failed:\n{result.stdout}{result.stderr}")
	backups = tenant_sites.bench_dir() / "sites" / site / "private" / "backups"
	return max(backups.glob("*-database.sql.gz"), key=lambda p: p.stat().st_mtime)


def run_script(script, *args):
	return subprocess.run(
		["bash", str(script), *args],
		cwd=tenant_sites.bench_dir(),
		capture_output=True,
		text=True,
		check=False,
	)


class TenantSiteTestCase(IntegrationTestCase):
	def make_site(self):
		"""A tenant site of this test's own, dropped when the test ends, pass or fail."""
		tenant_id = "rb" + secrets.token_hex(4)
		site, _ = tenant_sites.names(tenant_id)
		self.addCleanup(self._drop, tenant_id)
		tenant_sites.create(tenant_id)
		return site

	def _drop(self, tenant_id):
		site, _ = tenant_sites.names(tenant_id)
		if site in tenant_sites.list_sites():
			tenant_sites.drop(tenant_id)


class TestRestoreResetsEveryTable(TenantSiteTestCase):
	"""SOS-SETUP-36: a row in a table the baseline does not hold is gone after the restore."""

	def test_a_row_in_each_of_the_seven_tables_is_gone_after_the_restore(self):
		site = self.make_site()
		baseline = save_baseline(site)
		users_in_baseline = rows_in(site, "User")
		# The tables are made after the baseline was saved, as the seven DocTypes were, with a row each.
		for doctype in MISSING_FROM_BASELINE:
			make_table(site, doctype, rows=1)
			self.assertEqual(rows_in(site, doctype), 1)

		result = run_script(RESTORE, site, str(baseline))
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
		self.assertIn(f"Dropped every table of {site}", result.stdout)
		for doctype in MISSING_FROM_BASELINE:
			with self.subTest(doctype=doctype):
				self.assertFalse(table_exists(site, doctype), f"tab{doctype} survived the restore")
		# The baseline itself is back.
		self.assertEqual(rows_in(site, "User"), users_in_baseline)


class TestCleanSiteCheck(TenantSiteTestCase):
	"""SOS-SETUP-36: the clean check exits 3 on a dirty site and names the table and its row count."""

	def test_the_check_passes_on_a_clean_site_and_exits_3_on_a_dirty_one(self):
		site = self.make_site()
		for doctype in CHECKED:
			make_table(site, doctype)
		clean = run_script(CHECK, site)
		self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
		self.assertIn(f"Test site {site} is clean: no rows in 5 checked tables.", clean.stdout)

		sql(site, "INSERT INTO `tabSupport Grant` (name) VALUES ('SUP-1'), ('SUP-2')")
		sql(site, "INSERT INTO `tabConsent Record` (name) VALUES ('CR-1')")
		dirty = run_script(CHECK, site)
		self.assertEqual(dirty.returncode, 3, dirty.stdout + dirty.stderr)
		self.assertIn(f"TEST SITE NOT CLEAN: tabSupport Grant on {site} holds 2 rows", dirty.stderr)
		self.assertIn(f"TEST SITE NOT CLEAN: tabConsent Record on {site} holds 1 rows", dirty.stderr)
		self.assertNotIn("tabTenant on", dirty.stderr)
		self.assertIn("environment problem", dirty.stderr)

	def test_the_check_exits_3_when_a_table_cannot_be_read(self):
		site = self.make_site()
		result = run_script(CHECK, site)  # the tables were never made
		self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
		self.assertIn("could not count the rows", result.stderr)


def gate_block(start, end):
	"""The text of scripts/run-tests.sh from the line holding start up to the line holding end."""
	text = RUN_TESTS.read_text(encoding="utf-8")
	begin = text.index(start)
	return text[begin : text.index(end, begin)]


class TestResetBeforeTheBackendSuite(TenantSiteTestCase):
	"""SOS-SETUP-36: a row a spec left behind is gone before the backend suite starts.

	The gate's own code runs here: its sellos_reset_test_site function and the block between the
	changed tests and the backend suite, cut from scripts/run-tests.sh. The changed spec is a stand in
	that leaves a Support Grant behind, the backend suite a stand in that counts them, and
	prepare_test_site.sh a no-op (a tenant site has no SellOS app to prepare).
	"""

	def run_gate_segment(self, site, baseline, targets):
		root = Path(self.enterContext(tempfile.TemporaryDirectory()))
		(root / "scripts" / "lib").mkdir(parents=True)
		for script in (RESTORE, CHECK):
			(root / "scripts" / "lib" / script.name).symlink_to(script)
		(root / "scripts" / "lib" / "prepare_test_site.sh").write_text(
			'echo "prepared $1"\n', encoding="utf-8"
		)
		(root / "targets.tsv").write_text(targets, encoding="utf-8")
		reset_fn = gate_block("sellos_reset_test_site() {", 'sellos_reset_test_site "before the tests"')
		between = gate_block('sellos_flake_gate "$FLAKE_TARGETS" || exit 1', 'echo "--- Backend unit tests')
		driver = f"""set -euo pipefail
sellos_env_exit() {{ echo "ENV EXIT $1"; exit "$1"; }}
REPO_DIR="{root}"
SITE="{site}"
APP=sellos
BASELINE="{baseline}"
FLAKE_TARGETS="{root}/targets.tsv"
sellos_flake_gate() {{
  bench --site "$SITE" mariadb -e "INSERT INTO \\`tabSupport Grant\\` (name, note) VALUES ('SUP-SPEC', 'left by a spec')"
}}
{reset_fn}
{between}
echo "BACKEND SUITE SEES $(bench --site "$SITE" mariadb -N -e 'SELECT COUNT(*) FROM `tabSupport Grant`') SUPPORT GRANTS"
"""
		return subprocess.run(
			["bash", "-c", driver],
			cwd=tenant_sites.bench_dir(),
			capture_output=True,
			text=True,
			check=False,
		)

	def test_a_row_left_by_a_spec_is_gone_before_the_backend_suite(self):
		site = self.make_site()
		for doctype in CHECKED:
			make_table(site, doctype)
		baseline = save_baseline(site)

		result = self.run_gate_segment(site, baseline, "spec\tcrm/x.cy.js\t/tmp/x\n")
		out = result.stdout + result.stderr
		self.assertEqual(result.returncode, 0, out)
		self.assertIn("after the changed specs, before the backend suite", out)
		self.assertIn(f"Test site {site} is clean", out)
		self.assertIn("BACKEND SUITE SEES 0 SUPPORT GRANTS", out)

	def test_without_a_changed_spec_the_site_is_not_reset_again(self):
		site = self.make_site()
		for doctype in CHECKED:
			make_table(site, doctype)
		baseline = save_baseline(site)

		result = self.run_gate_segment(site, baseline, "backend\tsellos.x.test_x\t/tmp/x\n")
		out = result.stdout + result.stderr
		self.assertEqual(result.returncode, 0, out)
		self.assertNotIn("Restoring the clean test site baseline", out)
		self.assertIn("BACKEND SUITE SEES 1 SUPPORT GRANTS", out)


class TestGateWiring(UnitTestCase):
	"""SOS-SETUP-36: the gate, prepare-regression.sh, the agent prompt and the loop start use the fixes."""

	def test_the_gate_restores_through_the_full_wipe_and_checks_the_site_clean(self):
		text = RUN_TESTS.read_text(encoding="utf-8")
		self.assertNotIn('gunzip -c "$BASELINE" | bench --site "$SITE" mariadb', text)
		reset_fn = gate_block("sellos_reset_test_site() {", 'sellos_reset_test_site "before the tests"')
		order = [
			reset_fn.index("lib/restore_baseline.sh"),
			reset_fn.index("lib/prepare_test_site.sh"),
			reset_fn.index("lib/check_clean_site.sh"),
		]
		self.assertEqual(order, sorted(order))
		self.assertIn('if [ "$clean_status" -eq 3 ]; then sellos_env_exit 3; fi', reset_fn)
		# The second reset sits between the changed tests and the backend suite.
		self.assertLess(
			text.index('sellos_flake_gate "$FLAKE_TARGETS" || exit 1'),
			text.index('sellos_reset_test_site "after'),
		)
		self.assertLess(text.index('sellos_reset_test_site "after'), text.index('run_backend "$LOG_DIR'))

	def test_prepare_regression_wipes_and_checks_before_it_seeds(self):
		text = PREPARE_REGRESSION.read_text(encoding="utf-8")
		self.assertNotIn('gunzip -c "$BASELINE" | bench --site "$SITE" mariadb', text)
		order = [
			text.index("lib/restore_baseline.sh"),
			text.index("ui_fixtures.prepare_clean_site"),
			text.index("lib/check_clean_site.sh"),
			text.index("ui_fixtures.seed_regression_data"),
		]
		self.assertEqual(order, sorted(order))

	def test_the_agent_is_told_never_to_seed_the_test_site(self):
		text = BUILD_LOOP.read_text(encoding="utf-8")
		rule = (
			"Never run seed_regression_data, any ui_fixtures.seed_* function or scripts/prepare-regression.sh"
		)
		# Both prompts: the task prompt and the repair prompt.
		self.assertEqual(text.count(rule), 2)

	def test_the_loop_starts_with_default_signals(self):
		text = SELLOS_CLI.read_text(encoding="utf-8")
		self.assertTrue(re.search(r'\(set -m; cd "\$REPO_DIR" && nohup "\$SCRIPT_DIR/build-loop.sh"', text))

	def test_the_restore_refuses_any_other_site_before_a_command_runs(self):
		for site in (
			"pamaa",
			"awh",
			"buildos_test.localhost",
			"sellos.localhost",
			"sellos_tenant_A.localhost",
		):
			with self.subTest(site=site):
				result = run_script(RESTORE, site, "/nonexistent.sql.gz")
				self.assertEqual(result.returncode, 2)
				self.assertIn("Refusing to wipe site", result.stderr)

	def test_the_new_scripts_are_executable(self):
		for script in (RESTORE, CHECK):
			self.assertTrue(os.access(script, os.X_OK), f"{script.name} is not executable")
