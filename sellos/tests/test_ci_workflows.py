"""SOS-P0-07: continuous integration workflows."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestCiWorkflows(unittest.TestCase):
	"""SOS-P0-07 pipeline runs on pull requests, covers lint, tests and build, reports run time."""

	@classmethod
	def setUpClass(cls):
		cls.ci = (ROOT / ".github/workflows/ci.yml").read_text()
		cls.lint = (ROOT / ".github/workflows/linter.yml").read_text()

	def test_runs_on_every_pull_request(self):
		for text in (self.ci, self.lint):
			self.assertRegex(text, r"(?m)^  pull_request:\s*$")

	def test_runs_lint_tests_and_build(self):
		self.assertIn("pre-commit/action", self.lint)
		self.assertIn("run-tests --app sellos", self.ci)
		self.assertIn("npm run build", self.ci)

	def test_ci_jobs_are_named_for_branch_protection(self):
		jobs = re.findall(r"(?m)^  (frontend|tests|ui):\s*$", self.ci)
		self.assertEqual(sorted(jobs), ["frontend", "tests", "ui"])
		for name in ("Frontend", "Server", "UI"):
			self.assertRegex(self.ci, rf"(?m)^    name: {name}\s*$")

	def test_the_provisioner_gets_the_plain_tenant_grant_that_new_site_needs(self):
		"""SOS-SETUP-24: with only `sellos\\_tenant\\_%` MariaDB refuses new-site's GRANT (1044)."""
		self.assertIn(
			"GRANT ALL PRIVILEGES ON \\`sellos_tenant_%\\`.* TO 'sellos_provisioner'@'%' WITH GRANT OPTION;",
			self.ci,
		)
		self.assertIn(
			"GRANT ALL PRIVILEGES ON \\`sellos\\\\_tenant\\\\_%\\`.* TO 'sellos_provisioner'@'%' WITH GRANT OPTION;",
			self.ci,
		)

	def test_run_time_reporting_documented(self):
		doc = (ROOT / "docs/CI.md").read_text()
		self.assertIn("run time", doc)

	def test_no_job_is_allowed_to_fail(self):
		self.assertNotIn("continue-on-error", self.ci + self.lint)

	def test_branch_protection_steps_documented(self):
		doc = (ROOT / "docs/CI.md").read_text()
		self.assertIn("Require status checks to pass before merging", doc)
