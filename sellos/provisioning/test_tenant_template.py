"""SOS-SETUP-28: CI builds tenant test sites from a template dump, with one real install per run.

tenant_sites.create adds --source-sql when SELLOS_TENANT_TEMPLATE_SQL names a dump, and the launcher
then gives the site its own Administrator password. full_install() turns the template off, and exactly
one real provisioning test (test_p1_02_worker.TestRealProvisioning.test_plan_limits_are_applied_on_the_site)
uses it.
"""

import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sellos.provisioning import tenant_sites
from sellos.tests import tenant_template
from sellos.tests.tenant_template import full_install

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent


class TemplateOption(unittest.TestCase):
	def setUp(self):
		patcher = mock.patch.dict(os.environ)
		patcher.start()
		self.addCleanup(patcher.stop)
		os.environ.pop(tenant_sites.TEMPLATE_ENV, None)

	def create_args(self):
		with mock.patch.object(tenant_sites, "_run_frappe") as run:
			tenant_sites.create("tmpltest")
		(args, extra), _ = run.call_args
		self.assertTrue(extra[tenant_sites.ADMIN_ENV])
		return args

	def test_without_the_template_a_site_gets_the_full_install(self):
		self.assertNotIn("--source-sql", self.create_args())

	def test_with_the_template_the_site_is_built_from_the_dump(self):
		with tempfile.NamedTemporaryFile(suffix=".sql") as dump:
			os.environ[tenant_sites.TEMPLATE_ENV] = dump.name
			args = self.create_args()
		self.assertEqual(args[args.index("--source-sql") + 1], str(Path(dump.name).resolve()))
		self.assertEqual(args[:2], ["new-site", "sellos_tenant_tmpltest.localhost"])

	def test_a_template_that_is_not_a_file_is_refused_before_any_command_runs(self):
		os.environ[tenant_sites.TEMPLATE_ENV] = "/nonexistent/template.sql"
		with mock.patch.object(tenant_sites, "_run_frappe") as run:
			with self.assertRaisesRegex(tenant_sites.TenantSiteError, "not a file"):
				tenant_sites.create("tmpltest")
		run.assert_not_called()

	def test_full_install_turns_the_template_off_and_back_on(self):
		with tempfile.NamedTemporaryFile(suffix=".sql") as dump:
			os.environ[tenant_sites.TEMPLATE_ENV] = dump.name
			with full_install():
				self.assertNotIn("--source-sql", self.create_args())
			self.assertEqual(os.environ[tenant_sites.TEMPLATE_ENV], dump.name)
			self.assertIn("--source-sql", self.create_args())

	def test_the_launcher_sets_the_admin_password_of_a_site_built_from_a_dump(self):
		launcher = tenant_sites.LAUNCHER
		self.assertIn('from_dump = args[0] == "new-site" and "--source-sql" in args', launcher)
		self.assertIn('update_password("Administrator", admin)', launcher)
		self.assertIn("sys.exit(code)", launcher)


class OneRealInstallPerRun(unittest.TestCase):
	def test_exactly_one_test_uses_the_full_install(self):
		uses = []
		for path in APP_ROOT.rglob("test_*.py"):
			if path.name == Path(__file__).name:
				continue
			uses += [path.name] * len(
				re.findall(r"\bwith full_install\(\)", path.read_text(encoding="utf-8"))
			)
		self.assertEqual(uses, ["test_p1_02_worker.py"])

	def test_ci_makes_the_template_once_and_hands_it_to_the_tests(self):
		ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
		self.assertEqual(ci.count("-m sellos.tests.tenant_template make"), 1)
		self.assertIn('echo "SELLOS_TENANT_TEMPLATE_SQL=', ci)

	def test_in_ci_the_template_is_set_for_the_tests(self):
		if os.environ.get("GITHUB_ACTIONS") == "true":
			self.assertTrue(tenant_template.template_in_use(), "CI's Server job must set the template")
			self.assertTrue(Path(os.environ[tenant_sites.TEMPLATE_ENV]).is_file())
