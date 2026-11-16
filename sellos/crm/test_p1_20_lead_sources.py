"""SOS-P1-20: the list of lead sources. The list, who may extend it, the delete refusal and the patch."""

from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from sellos.crm import api, lead_sources
from sellos.crm.test_crm import CrmCase, as_user, email
from sellos.patches import p1_20_lead_sources

STORY_SOURCES = (
	"Website",
	"Portal",
	"Referral",
	"Walk in",
	"Channel partner",
	"Facebook",
	"Missed call",
	"Bought list",
)


class TestTheList(CrmCase):
	"""SOS-P1-20: the eight sources, the picker's list and who may extend it."""

	def test_the_eight_sources_in_the_story_are_there_and_enabled(self):
		self.assertEqual(lead_sources.DEFAULT_SOURCES, STORY_SOURCES)
		for name in STORY_SOURCES:
			self.assertEqual(frappe.db.get_value("Lead Source", name, "enabled"), 1, name)

	def test_the_source_of_a_lead_is_a_required_link_to_the_list(self):
		field = frappe.get_meta("Lead").get_field("source")
		self.assertEqual((field.fieldtype, field.options, field.reqd), ("Link", "Lead Source", 1))
		self.assertEqual(frappe.get_meta("Lead").get_field("campaign").fieldtype, "Data")
		self.assertFalse(frappe.get_meta("Lead").get_field("campaign").reqd)

	def test_a_lead_needs_a_source_from_the_list(self):
		as_user("agent")
		client = api.save_client(values={"client_name": "No Source Buyer", "client_type": "Buyer"})
		with self.assertRaises(frappe.ValidationError):
			api.save_lead(values={"client": client["name"]})
		with self.assertRaises(frappe.ValidationError):
			api.save_lead(values={"client": client["name"], "source": "Not on the list at all"})

	def test_the_stories_that_set_a_source_use_names_on_the_list(self):
		# SOS-P1-09 (Website), SOS-P1-12 (Bought list) and SOS-P2-08 (Missed call) use these constants.
		self.assertEqual(
			(lead_sources.WEBSITE, lead_sources.BOUGHT_LIST, lead_sources.MISSED_CALL),
			("Website", "Bought list", "Missed call"),
		)
		for name in (lead_sources.WEBSITE, lead_sources.BOUGHT_LIST, lead_sources.MISSED_CALL):
			_, lead = self.make_lead("company_admin", source=name)
			self.assertEqual(api.get_lead(lead)["lead"]["source"], name)

	def test_a_lead_keeps_an_optional_campaign(self):
		_, lead = self.make_lead("agent", source="Facebook", campaign="Diwali 2026")
		self.assertEqual(api.get_lead(lead)["lead"]["campaign"], "Diwali 2026")
		_, bare = self.make_lead("agent")
		self.assertFalse(api.get_lead(bare)["lead"].get("campaign"))

	def test_a_company_admin_extends_the_list_and_an_agent_cannot(self):
		as_user("company_admin")
		saved = api.save_lead_source(values={"source_name": "  P120 Newspaper   ad "})
		self.assertEqual(saved, {"name": "P120 Newspaper ad", "enabled": 1})
		names = [row["name"] for row in api.list_lead_sources()["sources"]]
		self.assertIn("P120 Newspaper ad", names)
		_, lead = self.make_lead("agent", source="P120 Newspaper ad")
		self.assertEqual(api.get_lead(lead)["lead"]["source"], "P120 Newspaper ad")
		as_user("agent")
		with self.assertRaises(frappe.PermissionError):
			api.save_lead_source(values={"source_name": "P120 Agent made"})
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": "Lead Source", "source_name": "P120 Agent direct"}).insert()

	def test_a_disabled_source_is_hidden_from_pickers_and_refused_for_a_new_choice(self):
		as_user("company_admin")
		api.save_lead_source(values={"source_name": "P120 Old Hoarding"})
		api.save_lead_source(name="P120 Old Hoarding", values={"enabled": 0})
		self.assertEqual(frappe.db.get_value("Lead Source", "P120 Old Hoarding", "enabled"), 0)
		admin_view = api.list_lead_sources(include_disabled=1)
		self.assertIn(("P120 Old Hoarding", 0), [(r["name"], r["enabled"]) for r in admin_view["sources"]])
		self.assertTrue(admin_view["can_manage"])
		self.assertNotIn("P120 Old Hoarding", [r["name"] for r in api.list_lead_sources()["sources"]])
		as_user("agent")
		agent_view = api.list_lead_sources(include_disabled=1)
		self.assertNotIn("P120 Old Hoarding", [r["name"] for r in agent_view["sources"]])
		self.assertFalse(agent_view["can_manage"])
		client = api.save_client(values={"client_name": "Hoarding Buyer", "client_type": "Buyer"})
		with self.assertRaises(frappe.ValidationError):
			api.save_lead(values={"client": client["name"], "source": "P120 Old Hoarding"})

	def test_a_lead_on_a_source_disabled_later_can_still_be_edited(self):
		as_user("company_admin")
		api.save_lead_source(values={"source_name": "P120 Later Off"})
		_, lead = self.make_lead("agent", source="P120 Later Off")
		as_user("company_admin")
		api.save_lead_source(name="P120 Later Off", values={"enabled": 0})
		as_user("agent")
		api.save_lead(name=lead, values={"notes": "still editable"})
		self.assertEqual(api.get_lead(lead)["lead"]["source"], "P120 Later Off")

	def test_a_source_cannot_be_renamed_so_the_reports_keep_one_name(self):
		as_user("company_admin")
		api.save_lead_source(values={"source_name": "P120 Fixed Name"})
		doc = frappe.get_doc("Lead Source", "P120 Fixed Name")
		doc.source_name = "P120 Other Name"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_the_source_list_is_change_tracked(self):
		self.assertTrue(frappe.get_meta("Lead Source").track_changes)


class TestDeleteRefusal(CrmCase):
	"""SOS-P1-20: a source in use cannot be deleted. It can be disabled."""

	def test_a_source_a_lead_uses_cannot_be_deleted_by_the_api_or_the_record(self):
		as_user("company_admin")
		api.save_lead_source(values={"source_name": "P120 In Use"})
		self.make_lead("company_admin", source="P120 In Use")
		as_user("company_admin")
		with self.assertRaises(frappe.ValidationError) as caught:
			api.delete_lead_source("P120 In Use")
		self.assertIn("Disable it instead", str(caught.exception))
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Lead Source", "P120 In Use")
		self.assertTrue(frappe.db.exists("Lead Source", "P120 In Use"))
		api.save_lead_source(name="P120 In Use", values={"enabled": 0})  # it can be disabled
		self.assertEqual(frappe.db.get_value("Lead Source", "P120 In Use", "enabled"), 0)

	def test_a_source_no_lead_uses_can_be_deleted(self):
		as_user("company_admin")
		api.save_lead_source(values={"source_name": "P120 Unused"})
		self.assertEqual(api.delete_lead_source("P120 Unused"), {"deleted": "P120 Unused"})
		self.assertFalse(frappe.db.exists("Lead Source", "P120 Unused"))

	def test_a_standard_source_cannot_be_deleted_even_when_no_lead_uses_it(self):
		as_user("company_admin")
		with self.assertRaises(frappe.ValidationError):
			api.delete_lead_source("Bought list")
		self.assertTrue(frappe.db.exists("Lead Source", "Bought list"))

	def test_an_agent_cannot_delete_a_source(self):
		as_user("company_admin")
		api.save_lead_source(values={"source_name": "P120 Agent Cannot"})
		as_user("agent")
		with self.assertRaises(frappe.PermissionError):
			api.delete_lead_source("P120 Agent Cannot")
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Lead Source", "P120 Agent Cannot")
		self.assertTrue(frappe.db.exists("Lead Source", "P120 Agent Cannot"))


class TestThePatch(CrmCase):
	"""SOS-P1-20: the patch maps the free text values, makes a source for a value that matches none, and runs twice."""

	def legacy(self, text, name):
		"""A lead as it was before the list: free text in the source column."""
		_, lead = self.make_lead("company_admin")
		frappe.db.sql("update `tabLead` set source = %s where name = %s", (text, lead))
		return lead

	def source_of(self, lead):
		return frappe.db.get_value("Lead", lead, "source")

	def test_values_are_mapped_new_ones_become_sources_and_a_second_run_changes_nothing(self):
		leads = {
			"walk-in": self.legacy("walk-in", "a"),
			"  facebook ": self.legacy("  facebook ", "b"),
			"MISSED CALL": self.legacy("MISSED CALL", "c"),
			"Referral": self.legacy("Referral", "d"),
			"99acres": self.legacy("99acres", "e"),
			"99 Acres": self.legacy("99 Acres", "f"),
			"": self.legacy("", "g"),
			None: self.legacy(None, "h"),
		}
		before = {name: frappe.db.get_value("Lead", name, "modified") for name in leads.values()}

		first = p1_20_lead_sources.execute()
		self.assertIsNone(first)
		expected = {
			"walk-in": "Walk in",
			"  facebook ": "Facebook",
			"MISSED CALL": "Missed call",
			"Referral": "Referral",
			"99acres": "99acres",
			"99 Acres": "99acres",  # the same source as 99acres, not a second one
			"": lead_sources.NOT_RECORDED,
			None: lead_sources.NOT_RECORDED,
		}
		for raw, lead in leads.items():
			self.assertEqual(self.source_of(lead), expected[raw], repr(raw))
			self.assertTrue(frappe.db.exists("Lead Source", self.source_of(lead)))
			self.assertEqual(frappe.db.get_value("Lead", lead, "modified"), before[lead])
		sources = frappe.get_all("Lead Source", pluck="name", order_by="name")

		for _ in range(2):  # again: nothing is made and nothing moves
			result = lead_sources.map_free_text_sources()
			self.assertEqual(result, {"mapped": {}, "created": [], "leads": 0})
			p1_20_lead_sources.execute()
			self.assertEqual(frappe.get_all("Lead Source", pluck="name", order_by="name"), sources)
			for raw, lead in leads.items():
				self.assertEqual(self.source_of(lead), expected[raw], repr(raw))

	def test_the_result_names_what_was_mapped_and_made(self):
		self.legacy("Billboard near station", "x")
		self.legacy("fb", "y")
		result = lead_sources.map_free_text_sources()
		self.assertEqual(
			result["mapped"], {"Billboard near station": "Billboard near station", "fb": "Facebook"}
		)
		self.assertEqual(result["created"], ["Billboard near station"])
		self.assertEqual(result["leads"], 2)

	def test_a_source_a_company_added_is_matched_before_a_new_one_is_made(self):
		as_user("company_admin")
		api.save_lead_source(values={"source_name": "Open House"})
		lead = self.legacy("open-house", "z")
		result = lead_sources.map_free_text_sources()
		self.assertEqual(self.source_of(lead), "Open House")
		self.assertEqual(result["created"], [])

	def test_the_patch_makes_the_standard_sources_when_they_are_missing(self):
		frappe.db.delete("Lead Source", {"name": "Portal"})
		p1_20_lead_sources.execute()
		self.assertTrue(frappe.db.exists("Lead Source", "Portal"))

	def test_a_disabled_standard_source_stays_disabled(self):
		frappe.db.set_value("Lead Source", "Portal", "enabled", 0)
		lead_sources.ensure_default_sources()
		self.assertEqual(frappe.db.get_value("Lead Source", "Portal", "enabled"), 0)

	def test_the_patch_is_listed_after_the_model_sync(self):
		content = Path(frappe.get_app_path("sellos", "patches.txt")).read_text(encoding="utf-8")
		self.assertGreater(
			content.index("sellos.patches.p1_20_lead_sources"), content.index("[post_model_sync]")
		)


class TestRegressionSeed(IntegrationTestCase):
	"""SOS-P1-20: the regression seed adds a source, a disabled source and a campaign through the API."""

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_the_seed_is_read_back_and_safe_to_run_twice(self):
		from sellos.testing.users import create_test_users
		from sellos.tests import ui_fixtures

		create_test_users()
		as_user("company_admin")
		client = api.save_client(values={"client_name": "Regression Buyer Three", "client_type": "Buyer"})
		lead = api.save_lead(values={"client": client["name"], "source": "Referral"})["lead"]["name"]
		for _ in range(2):
			ui_fixtures._seed_lead_sources(email("company_admin"))
			rows = {r["name"]: r["enabled"] for r in api.list_lead_sources(include_disabled=1)["sources"]}
			self.assertEqual(rows["Regression Roadshow"], 1)
			self.assertEqual(rows["Regression Old Hoarding"], 0)
			seeded = api.get_lead(lead)["lead"]
			self.assertEqual(seeded["source"], "Regression Roadshow")
			self.assertEqual(seeded["campaign"], "Diwali 2026 hoardings")
