"""SOS-P0-08: deploy and promote dry runs, and the rolling upgrade that stops at the first failure."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest import TestCase, mock

from frappe.tests import IntegrationTestCase

from sellos.provisioning import deploy, tenant_sites

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestP008DryRun(TestCase):
	"""SOS-P0-08: deploy and promote print every step in --dry-run and reach no server."""

	def run_release(self, environment, tag="v1.2.3"):
		lines = []
		with mock.patch.object(subprocess, "run", side_effect=AssertionError("reached a server")):
			code = deploy.release(environment, tag, dry_run=True, out=lines.append)
		return code, "\n".join(lines)

	def test_deploy_dry_run_prints_staging_and_production_steps(self):
		code, text = self.run_release("staging")
		self.assertEqual(code, 0)
		self.assertIn("release v1.2.3 to staging", text)
		self.assertIn("release v1.2.3 to production", text)
		self.assertIn("checkout --detach v1.2.3", text)
		self.assertIn("sellos.provisioning.deploy upgrade --backup --all-sites", text)
		self.assertGreaterEqual(len(re.findall(r"^\+ ssh ", text, re.M)), 14)

	def test_promote_dry_run_checks_staging_first(self):
		code, text = self.run_release("production", "v1.2.3-rc1")
		self.assertEqual(code, 0)
		self.assertIn("Check the tag is already on staging (on staging)", text)
		self.assertIn("+ ssh -o BatchMode=yes '<staging-host>' ", text.split("Not run by")[0])

	def test_bad_tags_are_refused(self):
		for bad in ("1.2.3", "main", "v1.2", "v1.2.3; rm -rf /", "v1.2.3 --force"):
			with self.assertRaises(deploy.DeployError):
				deploy.plan("staging", bad)

	def test_real_run_without_a_host_is_refused_and_stops_at_first_failed_step(self):
		with mock.patch.dict(os.environ, {"SELLOS_STAGING_HOST": ""}):
			with self.assertRaises(deploy.DeployError):
				deploy.release("staging", "v1.2.3")
		calls, lines = [], []

		def runner(host, step):
			calls.append(step.title)
			return 1 if len(calls) == 3 else 0

		with mock.patch.dict(os.environ, {"SELLOS_STAGING_HOST": "deploy@staging.example.com"}):
			self.assertEqual(deploy.release("staging", "v1.2.3", out=lines.append, runner=runner), 1)
		self.assertEqual(len(calls), 3)
		self.assertIn("Step 3 failed", lines[-1])

	def test_scripts_dry_run_end_to_end(self):
		# The scripts default to the bench's own Python under the home folder; CI's bench lives elsewhere.
		env_vars = {**os.environ, "SELLOS_DEPLOY_PYTHON": sys.executable}
		for script, env in (("deploy", "staging"), ("promote", "production")):
			result = subprocess.run(
				[str(REPO_ROOT / "deploy" / f"{script}.sh"), "v2.0.0", "--dry-run"],
				capture_output=True,
				text=True,
				check=False,
				env=env_vars,
			)
			self.assertEqual(result.returncode, 0, result.stderr)
			self.assertIn(f"Dry run: release v2.0.0 to {env}", result.stdout)
		bad = subprocess.run(
			[str(REPO_ROOT / "deploy" / "deploy.sh"), "latest", "--dry-run"],
			capture_output=True,
			text=True,
			check=False,
			env=env_vars,
		)
		self.assertEqual(bad.returncode, 2)


class TestP008RollingUpgradeLogic(TestCase):
	"""SOS-P0-08: the rolling upgrade with a fake migration."""

	def test_stops_at_first_failure_and_leaves_the_rest(self):
		seen = []

		def migrate(site, backup=False):
			seen.append(site)
			return "boom" if site == "b.example.com" else None

		out = []
		result = deploy.rolling_upgrade(
			["a.example.com", "b.example.com", "c.example.com", "d.example.com"], migrate, out=out.append
		)
		self.assertEqual(seen, ["a.example.com", "b.example.com"])
		self.assertEqual(result.migrated, ["a.example.com"])
		self.assertEqual(result.failed, "b.example.com")
		self.assertEqual(result.untouched, ["c.example.com", "d.example.com"])
		self.assertIn("FAILED b.example.com: boom", out)

	def test_all_sites_migrate_in_order_when_none_fails(self):
		seen = []
		result = deploy.rolling_upgrade(
			["a.example.com", "b.example.com"], lambda s, backup=False: seen.append(s), out=lambda _: None
		)
		self.assertTrue(result.ok)
		self.assertEqual(seen, ["a.example.com", "b.example.com"])

	def test_bad_site_names_are_refused_before_any_migration(self):
		seen = []
		for bad in (["a.example.com", "../x"], ["a.example.com", "a.example.com"]):
			with self.assertRaises(deploy.DeployError):
				deploy.rolling_upgrade(bad, lambda s, backup=False: seen.append(s))
		self.assertEqual(seen, [])


class TestP008RollingUpgradeOnTenantSites(IntegrationTestCase):
	"""SOS-P0-08: two real tenant sites, the first forced to fail its migration."""

	def test_failure_on_first_site_stops_the_run_and_spares_the_second(self):
		ids = ("upga", "upgb")
		sites = [tenant_sites.names(i)[0] for i in ids]
		for tenant_id in ids:
			self.addCleanup(self.drop_quietly, tenant_id)
		for tenant_id in ids:
			tenant_sites.create(tenant_id)

		bench_sites = tenant_sites.bench_dir() / "sites"
		first_config = bench_sites / sites[0] / "site_config.json"
		second_config = bench_sites / sites[1] / "site_config.json"
		original = first_config.read_text(encoding="utf-8")
		second_before = second_config.read_text(encoding="utf-8")
		# Point the first site at a database that does not exist, so its migration cannot connect.
		broken = json.loads(original)
		broken["db_name"] = "sellos_tenant_doesnotexist"
		first_config.write_text(json.dumps(broken), encoding="utf-8")
		self.addCleanup(first_config.write_text, original, encoding="utf-8")

		out = []
		result = deploy.rolling_upgrade(sites, out=out.append)

		self.assertFalse(result.ok)
		self.assertEqual(result.failed, sites[0])
		self.assertEqual(result.migrated, [])
		self.assertEqual(result.untouched, [sites[1]])
		self.assertTrue(any(line.startswith(f"FAILED {sites[0]}") for line in out))
		self.assertFalse(any(sites[1] in line and "Migrating" in line for line in out))
		self.assertEqual(second_config.read_text(encoding="utf-8"), second_before)

	@staticmethod
	def drop_quietly(tenant_id):
		site, _ = tenant_sites.names(tenant_id)
		if site in tenant_sites.list_sites():
			tenant_sites.drop(tenant_id)
