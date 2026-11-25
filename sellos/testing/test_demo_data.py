"""The demo's companies, sign ins and content are realistic and consistent (demo rebuild, 25 November 2026).

Unit tests, no bench: they read the company config, the sign ins, the names and the pure content generators of the
builders (demo_inventory, demo_crm, demo_sales, demo_whatsapp). The records the content becomes are checked by
sellos/tests/test_demo_environment.py, which seeds a real demo site.
"""

import json
import random
import re
import unittest
from collections import Counter
from datetime import date

from sellos.testing import demo, demo_crm, demo_ctx, demo_data, demo_inventory, demo_names, demo_sales

TODAY = date(2026, 11, 25)
OLD_WORDS = ("sky" + "line", "green" + "field", "demo" + "alpha", "demo" + "beta", "Pu" + "ne")


def strings(value):
	"""Every string in a nested data structure."""
	if isinstance(value, str):
		yield value
	elif isinstance(value, dict):
		for item in value.values():
			yield from strings(item)
	elif isinstance(value, (list, tuple)):
		for item in value:
			yield from strings(item)


class TestDemoCompanies(unittest.TestCase):
	"""The two company sites: Pandya Realtors - BOM (Mumbai) and Pandya Realtors - AMD (Ahmedabad)."""

	def test_the_companies_are_bom_and_amd(self):
		self.assertEqual(
			[c["name"] for c in demo.COMPANIES], ["Pandya Realtors - BOM", "Pandya Realtors - AMD"]
		)
		self.assertEqual([c["city"] for c in demo.COMPANIES], ["Mumbai", "Ahmedabad"])
		self.assertEqual([c["word"] for c in demo.COMPANIES], ["bom", "amd"])

	def test_the_sites_are_demo_sites_named_for_the_cities(self):
		self.assertEqual(demo.COMPANY_IDS, ("demobom", "demoamd"))
		self.assertEqual(demo.CONTROL_ID, "democontrol")
		for tenant_id in (demo.CONTROL_ID, *demo.COMPANY_IDS):
			self.assertTrue(demo.is_demo_site(demo.site_of(tenant_id)), tenant_id)
		self.assertFalse(demo.is_demo_site("sellos_test.localhost"))

	def test_each_company_has_a_sign_in_for_every_role(self):
		for i in range(len(demo.COMPANIES)):
			roles = Counter(role for _email, _name, role in demo.company_users(i))
			self.assertEqual(roles[demo.COMPANY_ADMIN], 1)
			self.assertEqual(roles[demo.SALES_MANAGER], 1)
			self.assertEqual(roles[demo.AGENT], 4)
			self.assertEqual(roles[demo.CHANNEL_PARTNER], 1)
			self.assertEqual(roles[demo.CLIENT], 1)

	def test_the_sign_ins_are_named_for_the_company_and_use_example_domains(self):
		for i, company in enumerate(demo.COMPANIES):
			emails = [email for email, _name, _role in demo.company_users(i)]
			self.assertEqual(len(emails), len(set(emails)))
			for email in emails:
				self.assertTrue(email.endswith(f".{company['word']}@demo.example.com"), email)
			self.assertIn(f"admin.{company['word']}@demo.example.com", emails)
			self.assertIn(f"agent4.{company['word']}@demo.example.com", emails)

	def test_users_of_gives_the_builders_their_emails(self):
		users = demo.users_of(0)
		self.assertEqual(users["admin"], "admin.bom@demo.example.com")
		self.assertEqual(len(users["agents"]), 4)
		self.assertEqual(users["partner"], "partner.bom@demo.example.com")
		self.assertEqual(demo.users_of(1)["client"], "client.amd@demo.example.com")

	def test_the_sign_in_names_are_the_fixed_staff_names(self):
		for i, company in enumerate(demo.COMPANIES):
			names = [name for _email, name, _role in demo.company_users(i)]
			staff = demo_names.STAFF[company["word"]]
			self.assertIn(staff["admin"], names)
			self.assertIn(staff["agents"][3], names)

	def test_nothing_of_the_first_demo_remains_in_the_config(self):
		for text in strings([demo.COMPANIES, [demo.company_users(i) for i in range(2)], demo.COMPANY_IDS]):
			for word in OLD_WORDS:
				self.assertNotIn(word.lower(), text.lower(), text)

	def test_the_password_is_unchanged_and_the_platform_admin_is_one_person(self):
		self.assertEqual(demo.DEMO_PASSWORD, "Demo@2026")
		self.assertEqual(demo.PLATFORM_ADMIN_EMAIL, "platform@demo.example.com")


class TestDemoContentAcrossBuilders(unittest.TestCase):
	"""What the builders generate fits together: volumes, names, formats, words."""

	def generated(self, region):
		rng = random.Random(demo_ctx.SEED_OF[region])
		used = set()
		developers = demo_inventory.make_developers(rng, region, used)
		projects = demo_inventory.make_projects(rng, region, TODAY, developers)
		properties = demo_inventory.make_properties(rng, region, TODAY)
		agents = [f"agent{n}.{region}@demo.example.com" for n in range(1, 5)]
		rows = [{"name": p["project_name"], "locality": p["locality"]} for p in projects]
		leads = demo_crm.generate_leads(rng, region, TODAY, rows, agents, used)
		sellers = demo_sales.seller_plan(rng, region, TODAY, used)
		return developers, projects, properties, leads, sellers, used

	def test_the_volumes_are_at_least_the_brief(self):
		m = demo_ctx.MINIMUMS
		for region in ("bom", "amd"):
			developers, projects, properties, leads, sellers, _used = self.generated(region)
			self.assertGreaterEqual(len(developers), m["developers"])
			self.assertGreaterEqual(len(projects), m["projects"])
			self.assertGreaterEqual(len(properties), m["properties"])
			self.assertGreaterEqual(len(leads), m["leads"])
			self.assertGreaterEqual(len(sellers), m["sellers"])

	def test_every_pipeline_stage_and_consent_state_has_enough_leads(self):
		m = demo_ctx.MINIMUMS
		for region in ("bom", "amd"):
			leads = self.generated(region)[3]
			stages = Counter(lead["stage"] for lead in leads)
			self.assertEqual(len(stages), 11)
			self.assertGreaterEqual(min(stages.values()), m["leads_per_stage"])
			consent = Counter(lead["consent"] for lead in leads)
			self.assertGreaterEqual(consent["consented"], m["leads_per_consent_state"])
			self.assertGreaterEqual(consent["optedout"], m["leads_per_consent_state"])
			self.assertGreaterEqual(consent["dnd"], m["leads_per_consent_state"])
			self.assertGreaterEqual(consent["unknown"] + consent["expired"], m["leads_per_consent_state"])

	def test_a_person_is_named_once_across_leads_sellers_and_contacts(self):
		for region in ("bom", "amd"):
			_developers, _projects, _properties, leads, sellers, used = self.generated(region)
			names = [lead["name"] for lead in leads] + [seller["name"] for seller in sellers]
			self.assertEqual(len(names), len(set(names)))
			self.assertTrue(set(names) <= used)

	def test_lead_names_are_plain_and_the_source_is_its_own_field(self):
		sources = {"Website", "Referral", "Property portal", "Hoarding campaign", "Walk in", "Instagram"}
		for region in ("bom", "amd"):
			for lead in self.generated(region)[3]:
				self.assertRegex(lead["name"], r"^[A-Z][a-z]+ [A-Z][a-z]+$")
				self.assertTrue(lead["source"])
				for source in sources:
					self.assertNotIn(source.lower(), lead["name"].lower())

	def test_rera_numbers_are_in_the_local_format_and_look_fictional(self):
		bom = self.generated("bom")[1]
		amd = self.generated("amd")[1]
		for project in bom:
			self.assertRegex(project["rera_number"], r"^P518000\d{5}$")
		for project in amd:
			self.assertTrue(project["rera_number"].startswith("PR/GJ/AHMEDABAD/"), project["rera_number"])
		self.assertEqual(len({p["rera_number"] for p in bom}), len(bom))
		self.assertEqual(len({p["rera_number"] for p in amd}), len(amd))

	def test_the_localities_are_each_cities_own(self):
		mumbai = {"Andheri West", "Powai", "Bandra East", "Worli", "Thane", "Mulund", "Chembur", "Goregaon"}
		ahmedabad = {"SG Highway", "Prahlad Nagar", "Bopal", "Shela", "Gota", "Satellite", "Thaltej"}
		self.assertTrue(mumbai <= {p["locality"] for p in self.generated("bom")[1]})
		self.assertTrue(ahmedabad <= {p["locality"] for p in self.generated("amd")[1]})
		self.assertFalse(mumbai & {p["locality"] for p in self.generated("amd")[1]})

	def test_no_generated_text_carries_a_test_word_or_a_real_looking_phone(self):
		for region in ("bom", "amd"):
			content = self.generated(region)
			for text in strings(content[:5]):
				for forbidden in (*demo_data.FORBIDDEN_WORDS, "regression"):
					self.assertNotIn(forbidden, text.lower(), text)
				self.assertIsNone(re.search(r"(?<![\d/])\d{10}(?![\d/])", text), text)

	def test_the_same_seed_gives_the_same_company(self):
		self.assertEqual(
			json.dumps(self.generated("bom")[3], default=str),
			json.dumps(self.generated("bom")[3], default=str),
		)
		self.assertNotEqual(self.generated("bom")[3][0]["name"], self.generated("amd")[3][0]["name"])


class TestSeedFailsLoudly(unittest.TestCase):
	"""A failed seed step is named with its error and fails the seed; it is never only a missing section."""

	def test_a_result_with_no_failed_step_has_no_failures(self):
		line = json.dumps({"site": "s", "leads": 3, "failed_steps": []})
		self.assertEqual(demo.failed_steps_of("s", line), [])

	def test_each_failed_step_is_named_with_its_error(self):
		failed = [
			{"step": "partners", "error": "TypeError: bad seed"},
			{"step": "whatsapp", "error": "ValidationError: no template"},
		]
		line = json.dumps({"site": "s", "failed_steps": failed})
		self.assertEqual(
			demo.failed_steps_of("s", line),
			[("s", "partners", "TypeError: bad seed"), ("s", "whatsapp", "ValidationError: no template")],
		)

	def test_a_line_that_is_not_the_result_counts_as_a_failure(self):
		for line in ("seeded", "", '{"site": "s"}', "[1, 2]"):
			found = demo.failed_steps_of("s", line)
			self.assertEqual(len(found), 1, line)
			self.assertIn("not understood", found[0][2])

	def test_a_failing_step_is_rolled_back_recorded_and_the_next_step_still_runs(self):
		from unittest import mock

		import frappe

		del demo.STEP_FAILURES[:]
		self.addCleanup(demo.STEP_FAILURES.clear)
		db = mock.MagicMock()

		def broken():
			raise ValueError("no such project")

		with (
			mock.patch.object(frappe, "db", db),
			mock.patch.object(demo.sys, "stderr", mock.MagicMock()),
		):
			self.assertIsNone(demo._isolated("deals", broken))
			self.assertEqual(demo._isolated("visits", lambda: "made"), "made")
		db.rollback.assert_called_once()
		self.assertEqual(demo.STEP_FAILURES, [{"step": "deals", "error": "ValueError: no such project"}])

	def test_seed_raises_naming_every_failed_site_and_step(self):
		from unittest import mock

		results = {
			"sellos_tenant_demobom.localhost": json.dumps({"failed_steps": []}),
			"sellos_tenant_demoamd.localhost": json.dumps(
				{"failed_steps": [{"step": "deals and commission", "error": "KeyError: 'rate'"}]}
			),
		}
		with (
			mock.patch.object(demo, "ensure_control"),
			mock.patch.object(demo, "provision_companies"),
			mock.patch.object(demo, "_run_on", side_effect=lambda site, *a, **k: results[site]),
			mock.patch("builtins.print"),
		):
			with self.assertRaises(demo.DemoSeedFailed) as caught:
				demo.seed()
			self.assertEqual(demo.main(["seed"]), 1)
		message = str(caught.exception)
		self.assertIn("sellos_tenant_demoamd.localhost", message)
		self.assertIn("deals and commission", message)
		self.assertIn("KeyError: 'rate'", message)
		self.assertNotIn("demo" + "alpha", message)


if __name__ == "__main__":
	unittest.main()
