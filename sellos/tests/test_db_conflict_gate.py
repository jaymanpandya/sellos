"""SOS-SETUP-25: the gate treats a MariaDB 1020 or deadlock as a retryable infrastructure error.

On 10 November 2026 SOS-P1-06A was Blocked by a 1020 ("Record has changed since last read in table
tabcontact") from a timing race with the shared bench worker. The gate handed it to the agent as a
code failure and spent the repair runs. scripts/lib/db_conflict.sh's run_backend, which
scripts/run-tests.sh runs the backend tests through, now reruns only the failing module once, alone,
and exits 3 with "database conflict (1020), not a code failure" if the rerun hits one again.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "scripts" / "lib"
DB_CONFLICT = LIB / "db_conflict.py"

# What Frappe's runner printed in the gate run that Blocked SOS-P1-06A (run-20261110-225325.log), cut down.
CONFLICT_RUN = """\
Running 11 integration tests for sellos

sellos.tests.test_crm_fresh_site.TestFixtures
   \x1b[31m ✖ \x1b[0m test_remove_seeded_leads_removes_everything_the_seeds_made_and_says_so
   \x1b[32m ✔ \x1b[0m test_seed_agent_leads_gives_the_agent_one_lead_and_hides_the_others

======================================================================
 ERROR  test_remove_seeded_leads_removes_everything_the_seeds_made_and_says_so (sellos.tests.test_crm_fresh_site.TestFixtures.test_remove_seeded_leads_removes_everything_the_seeds_made_and_says_so)
Traceback (most recent call last):
MySQLdb.OperationalError: (1020, "Record has changed since last read in table 'tabcontact'; try restarting transaction")
frappe.exceptions.QueryDeadlockError: (1020, "Record has changed since last read in table 'tabcontact'; try restarting transaction")
----------------------------------------------------------------------
Ran 11 tests in 9.120s

FAILED (errors=1)
"""

DEADLOCK_IN_SETUP_CLASS = """\
 ERROR  setUpClass (sellos.crm.test_crm.TestCrm)
pymysql.err.OperationalError: (1213, 'Deadlock found when trying to get lock; try restarting transaction')
FAILED (errors=1)
"""

CODE_FAILURE = """\
 FAIL  test_list_leads (sellos.crm.test_crm.TestCrm.test_list_leads)
AssertionError: 2 != 3
FAILED (failures=1)
"""

PASSED = """\
Ran 11 tests in 8.000s

OK
"""

DRIVER = """\
set -euo pipefail
sellos_env_exit() {{ echo "$1" >"$SELLOS_ENV_EXIT_FILE"; exit "$1"; }}
REPORT_TEST_EXIT="{dir}/fake_runner.sh"
SITE=sellos_test.localhost
APP=sellos
DB_CONFLICT="{db_conflict}"
DB_CONFLICT_LOG="{dir}/conflicts.log"
SELLOS_ENV_EXIT_FILE="{dir}/env-exit"
source "{lib}/db_conflict.sh"
status=0
run_backend "{dir}/backend.log" "$@" || status=$?
echo "RUN_BACKEND_STATUS=$status"
"""

FAKE_RUNNER = """\
#!/usr/bin/env bash
n=$(( $(cat "{dir}/count" 2>/dev/null || echo 0) + 1 ))
echo "$n" >"{dir}/count"
echo "$*" >>"{dir}/calls"
cat "{dir}/out-$n.txt"
exit "$(cat "{dir}/code-$n")"
"""


class DbConflictLog(unittest.TestCase):
	def parse(self, command, text):
		with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as f:
			f.write(text)
		try:
			return subprocess.run(
				["python3", str(DB_CONFLICT), command, f.name], capture_output=True, text=True, check=False
			)
		finally:
			Path(f.name).unlink()

	def test_1020_and_1213_are_database_conflicts(self):
		self.assertEqual(self.parse("is-conflict", CONFLICT_RUN).returncode, 0)
		self.assertEqual(self.parse("is-conflict", DEADLOCK_IN_SETUP_CLASS).returncode, 0)

	def test_an_assertion_is_not_a_database_conflict(self):
		self.assertEqual(self.parse("is-conflict", CODE_FAILURE).returncode, 1)
		self.assertEqual(self.parse("is-conflict", PASSED).returncode, 1)

	def test_the_failing_module_is_named_once_including_a_setup_class_error(self):
		self.assertEqual(
			self.parse("failing-modules", CONFLICT_RUN + CONFLICT_RUN).stdout.split(),
			["sellos.tests.test_crm_fresh_site"],
		)
		self.assertEqual(
			self.parse("failing-modules", DEADLOCK_IN_SETUP_CLASS).stdout.split(), ["sellos.crm.test_crm"]
		)


class RunBackend(unittest.TestCase):
	def setUp(self):
		self.dir = Path(tempfile.mkdtemp(prefix="sellos-dbconflict-"))

	def tearDown(self):
		for p in self.dir.iterdir():
			p.unlink()
		self.dir.rmdir()

	def run_gate(self, *runs, args=()):
		"""Run run_backend over a fake test runner whose nth call prints runs[n-1] and exits with its code."""
		for n, (output, code) in enumerate(runs, start=1):
			(self.dir / f"out-{n}.txt").write_text(output, encoding="utf-8")
			(self.dir / f"code-{n}").write_text(str(code), encoding="utf-8")
		runner = self.dir / "fake_runner.sh"
		runner.write_text(FAKE_RUNNER.format(dir=self.dir), encoding="utf-8")
		runner.chmod(0o755)
		driver = self.dir / "driver.sh"
		driver.write_text(DRIVER.format(dir=self.dir, lib=LIB, db_conflict=DB_CONFLICT), encoding="utf-8")
		result = subprocess.run(
			["bash", str(driver), *args], capture_output=True, text=True, check=False, cwd=self.dir
		)
		calls = (self.dir / "calls").read_text(encoding="utf-8").splitlines()
		return result, calls

	def test_a_conflict_that_passes_on_rerun_passes_and_reruns_only_the_failing_module(self):
		result, calls = self.run_gate((CONFLICT_RUN, 1), (PASSED, 0))
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("RUN_BACKEND_STATUS=0", result.stdout)
		self.assertIn("DATABASE CONFLICT (passed on rerun): sellos.tests.test_crm_fresh_site", result.stdout)
		self.assertEqual(len(calls), 2)
		self.assertEqual(
			calls[1],
			"bench --site sellos_test.localhost run-tests --app sellos --module sellos.tests.test_crm_fresh_site",
		)
		self.assertIn("sellos.tests.test_crm_fresh_site", (self.dir / "conflicts.log").read_text())

	def test_a_second_conflict_exits_3_and_says_it_is_not_a_code_failure(self):
		result, calls = self.run_gate((CONFLICT_RUN, 1), (CONFLICT_RUN, 1))
		self.assertEqual(result.returncode, 3)
		self.assertIn("database conflict (1020), not a code failure", result.stdout)
		self.assertEqual((self.dir / "env-exit").read_text().strip(), "3")
		self.assertNotIn("RUN_BACKEND_STATUS", result.stdout)
		self.assertEqual(len(calls), 2)

	def test_a_code_failure_is_not_rerun(self):
		result, calls = self.run_gate((CODE_FAILURE, 1))
		self.assertIn("RUN_BACKEND_STATUS=1", result.stdout)
		self.assertEqual(len(calls), 1)
		self.assertFalse((self.dir / "env-exit").exists())

	def test_a_conflict_whose_rerun_fails_another_way_is_a_code_failure(self):
		result, calls = self.run_gate((CONFLICT_RUN, 1), (CODE_FAILURE, 1))
		self.assertIn("RUN_BACKEND_STATUS=1", result.stdout)
		self.assertNotIn("not a code failure", result.stdout)
		self.assertEqual(len(calls), 2)

	def test_a_passing_run_runs_once_with_the_options_given(self):
		result, calls = self.run_gate((PASSED, 0), args=("--module", "sellos.tests.test_contact_race"))
		self.assertIn("RUN_BACKEND_STATUS=0", result.stdout)
		self.assertEqual(
			calls,
			[
				"bench --site sellos_test.localhost run-tests --app sellos --module sellos.tests.test_contact_race"
			],
		)
