"""SOS-P1-15: what each buyer wants. The fields, who edits them, the budget check, the list filters and the patch."""

import json
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from sellos.crm import api, requirements
from sellos.crm.test_crm import CrmCase, as_user, email
from sellos.patches import p1_15_lead_requirements

WANTS = {
	"budget_from": 5000000,
	"budget_to": 9000000,
	"configuration": ["2 BHK", "3 BHK"],
	"property_type": "Apartment",
	"preferred_localities": ["Powai", "Andheri West"],
	"purpose": "End use",
	"timeline": "Within 3 months",
	"possession": "Under construction",
}


class TestRequirementFields(IntegrationTestCase):
	"""SOS-P1-15: the fields."""

	def test_every_field_is_on_the_lead_and_change_tracked(self):
		meta = frappe.get_meta("Lead")
		self.assertTrue(meta.track_changes)
		for field in requirements.REQUIREMENT_FIELDS:
			self.assertTrue(meta.has_field(field), field)
			self.assertEqual(meta.get_field(field).permlevel, 0, field)

	def test_the_options_are_the_ones_the_story_names(self):
		meta = frappe.get_meta("Lead")
		for field, options in requirements.SINGLE_CHOICES.items():
			self.assertEqual(meta.get_field(field).options.split("\n"), ["", *options], field)
		self.assertEqual(requirements.CONFIGURATIONS, ("1 RK", "1 BHK", "2 BHK", "3 BHK", "4 BHK and above"))
		self.assertEqual(requirements.PROPERTY_TYPES, ("Apartment", "Villa", "Plot", "Office", "Shop"))
		self.assertEqual(requirements.PURPOSES, ("End use", "Investment"))
		self.assertEqual(
			requirements.TIMELINES, ("Immediate", "Within 3 months", "3 to 6 months", "Over 6 months")
		)
		self.assertEqual(requirements.POSSESSIONS, ("Ready", "Under construction", "Any"))

	def test_the_budget_is_in_rupees(self):
		meta = frappe.get_meta("Lead")
		for field in requirements.BUDGET_FIELDS:
			self.assertEqual(meta.get_field(field).fieldtype, "Currency")
			self.assertIn("rupees", meta.get_field(field).label)


class TestPureRules(IntegrationTestCase):
	"""SOS-P1-15: the list and filter rules."""

	def test_lists_are_trimmed_and_deduplicated(self):
		self.assertEqual(requirements.split_values(" Powai \n\npowai\nBandra "), ["Powai", "Bandra"])
		self.assertEqual(requirements.split_values(None), [])
		self.assertEqual(requirements.join_values(["A", "a", " B "]), "A\nB")

	def test_matches_applies_every_filter_given(self):
		row = {**WANTS, "configuration": "2 BHK\n3 BHK", "preferred_localities": "Powai\nAndheri West"}
		self.assertTrue(requirements.matches(row))
		self.assertTrue(requirements.matches(row, budget_min=9000000))  # the ranges touch
		self.assertFalse(requirements.matches(row, budget_min=9000001))
		self.assertTrue(requirements.matches(row, budget_max=5000000))
		self.assertFalse(requirements.matches(row, budget_max=4999999))
		self.assertTrue(requirements.matches(row, configuration="3 BHK"))
		self.assertTrue(requirements.matches(row, configuration=["1 RK", "2 BHK"]))
		self.assertFalse(requirements.matches(row, configuration="1 RK"))
		self.assertTrue(requirements.matches(row, locality="andheri"))
		self.assertFalse(requirements.matches(row, locality="Bandra"))
		self.assertTrue(requirements.matches(row, timeline="Within 3 months"))
		self.assertFalse(requirements.matches(row, timeline="Immediate"))
		self.assertFalse(requirements.matches(row, locality="Powai", timeline="Immediate"))

	def test_a_lead_with_no_budget_never_matches_a_budget_filter(self):
		self.assertFalse(requirements.matches({}, budget_min=1))
		self.assertFalse(requirements.matches({}, budget_max=10))
		self.assertTrue(requirements.matches({}))


class TestSavingRequirements(CrmCase):
	"""SOS-P1-15: saving and the budget check."""

	def test_the_assigned_agent_saves_every_field_and_reads_it_back(self):
		_, lead = self.make_lead("agent")
		view = api.save_lead(name=lead, values=WANTS)["requirements"]
		self.assertEqual(view["budget_from"], 5000000)
		self.assertEqual(view["budget_to"], 9000000)
		self.assertEqual(view["configuration"], ["2 BHK", "3 BHK"])
		self.assertEqual(view["preferred_localities"], ["Powai", "Andheri West"])
		for field in ("property_type", "purpose", "timeline", "possession"):
			self.assertEqual(view[field], WANTS[field])
		self.assertEqual(api.get_lead(lead)["requirements"], view)
		self.assertEqual(frappe.db.get_value("Lead", lead, "configuration"), "2 BHK\n3 BHK")

	def test_the_company_admin_edits_the_requirements_of_any_lead(self):
		_, lead = self.make_lead("agent")
		as_user("company_admin")
		view = api.save_lead(name=lead, values={"timeline": "Immediate"})["requirements"]
		self.assertEqual(view["timeline"], "Immediate")

	def test_an_agent_the_lead_is_not_assigned_to_cannot_edit_it(self):
		_, lead = self.make_lead("agent")
		as_user("company_admin")
		other = api.save_client(values={"client_name": "Other Buyer", "client_type": "Buyer"})
		other_lead = api.save_lead(values={"client": other["name"], "assigned_to": email("company_admin")})
		as_user("agent")
		with self.assertRaises(frappe.PermissionError):
			api.save_lead(name=other_lead["lead"]["name"], values={"timeline": "Immediate"})
		self.assertEqual(api.get_lead(lead)["requirements"]["timeline"], "")

	def test_a_budget_from_above_the_budget_to_is_refused_with_a_clear_message(self):
		_, lead = self.make_lead("agent")
		with self.assertRaises(frappe.ValidationError) as caught:
			api.save_lead(name=lead, values={"budget_from": 9000000, "budget_to": 5000000})
		self.assertIn("Budget from cannot be above budget to", str(caught.exception))
		self.assertEqual(api.get_lead(lead)["requirements"]["budget_from"], None)

	def test_equal_budgets_and_a_single_budget_are_allowed(self):
		_, lead = self.make_lead("agent")
		self.assertEqual(
			api.save_lead(name=lead, values={"budget_from": 100, "budget_to": 100})["requirements"][
				"budget_to"
			],
			100,
		)
		self.assertEqual(
			api.save_lead(name=lead, values={"budget_from": 0, "budget_to": 500})["requirements"][
				"budget_from"
			],
			None,
		)

	def test_a_negative_budget_and_an_unknown_choice_are_refused(self):
		_, lead = self.make_lead("agent")
		for values in (
			{"budget_from": -1},
			{"configuration": ["5 BHK"]},
			{"timeline": "Someday"},
			{"purpose": "Fun"},
		):
			with self.assertRaises(frappe.ValidationError, msg=str(values)):
				api.save_lead(name=lead, values=values)

	def test_changes_are_kept_in_the_change_history(self):
		_, lead = self.make_lead("agent")
		# Frappe skips versions while tests run, so ask for them, as a real save does.
		for values in (
			{"timeline": "Immediate", "configuration": "1 RK"},
			{"timeline": "Over 6 months", "configuration": "1 RK\n2 BHK"},
		):
			doc = frappe.get_doc("Lead", lead)
			doc.update(values)
			doc.save(ignore_version=False)
		changed = {}
		for version in frappe.get_all(
			"Version", filters={"ref_doctype": "Lead", "docname": lead}, fields=["data"], order_by="creation"
		):
			for field, old, new in json.loads(version.data).get("changed", []):
				changed.setdefault(field, []).append((old, str(new).replace("<br>", "\n")))
		self.assertEqual(changed["timeline"][-1], ("Immediate", "Over 6 months"))
		self.assertEqual(changed["configuration"][-1], ("1 RK", "1 RK\n2 BHK"))


class TestListFilters(CrmCase):
	"""SOS-P1-15: the list filters."""

	def setUp(self):
		super().setUp()
		self.cheap = self.make_lead("agent")[1]
		api.save_lead(
			name=self.cheap,
			values={
				"budget_from": 2000000,
				"budget_to": 4000000,
				"configuration": ["1 BHK"],
				"preferred_localities": ["Thane"],
				"timeline": "Immediate",
			},
		)
		self.rich = self.make_lead("agent")[1]
		api.save_lead(name=self.rich, values=WANTS)
		self.bare = self.make_lead("agent")[1]

	def names(self, **filters):
		return {r["name"] for r in api.list_leads(**filters)}

	def test_no_filter_lists_every_lead_with_its_requirements(self):
		self.assertEqual(self.names(), {self.cheap, self.rich, self.bare})
		row = next(r for r in api.list_leads() if r["name"] == self.rich)
		self.assertEqual(row["requirements"]["configuration"], ["2 BHK", "3 BHK"])

	def test_budget_range(self):
		self.assertEqual(self.names(budget_min=4500000), {self.rich})
		self.assertEqual(self.names(budget_max=3000000), {self.cheap})
		self.assertEqual(self.names(budget_min=3500000, budget_max=6000000), {self.cheap, self.rich})
		self.assertEqual(self.names(budget_min=50000000), set())

	def test_configuration_one_or_several(self):
		self.assertEqual(self.names(configuration="3 BHK"), {self.rich})
		self.assertEqual(self.names(configuration='["1 BHK", "2 BHK"]'), {self.cheap, self.rich})
		self.assertEqual(self.names(configuration="4 BHK and above"), set())

	def test_locality_and_timeline(self):
		self.assertEqual(self.names(locality="powai"), {self.rich})
		self.assertEqual(self.names(locality="Than"), {self.cheap})
		self.assertEqual(self.names(timeline="Immediate"), {self.cheap})
		self.assertEqual(self.names(locality="Powai", timeline="Immediate"), set())

	def test_an_agent_filtering_still_sees_only_their_own_leads(self):
		as_user("company_admin")
		client = api.save_client(values={"client_name": "Admin Buyer", "client_type": "Buyer"})
		theirs = api.save_lead(
			values={"client": client["name"], "assigned_to": email("company_admin"), "timeline": "Immediate"}
		)["lead"]["name"]
		self.assertIn(theirs, self.names(timeline="Immediate"))
		as_user("agent")
		self.assertNotIn(theirs, self.names(timeline="Immediate"))


class TestPatch(CrmCase):
	"""SOS-P1-15: the patch."""

	def test_the_patch_keeps_the_fields_and_changes_no_lead_and_runs_twice(self):
		_, lead = self.make_lead("agent", **WANTS)
		_, bare = self.make_lead("agent")
		before = frappe.db.get_all(
			"Lead", fields=["name", "modified", *requirements.REQUIREMENT_FIELDS], order_by="name"
		)
		for _ in range(2):
			p1_15_lead_requirements.execute()
			for field in requirements.REQUIREMENT_FIELDS:
				self.assertTrue(frappe.db.has_column("Lead", field), field)
			after = frappe.db.get_all(
				"Lead", fields=["name", "modified", *requirements.REQUIREMENT_FIELDS], order_by="name"
			)
			self.assertEqual(after, before)
		self.assertEqual(api.get_lead(lead)["requirements"]["budget_to"], 9000000)
		self.assertEqual(api.get_lead(bare)["requirements"]["configuration"], [])

	def test_the_patch_is_listed_after_the_model_sync(self):
		content = Path(frappe.get_app_path("sellos", "patches.txt")).read_text(encoding="utf-8")
		self.assertGreater(
			content.index("sellos.patches.p1_15_lead_requirements"), content.index("[post_model_sync]")
		)


class TestRegressionSeed(CrmCase):
	"""SOS-P1-15: the regression seed gives two buyers requirements, through the lead API, and is safe to run again."""

	def test_the_seed_fills_two_leads_and_leaves_them_alone_the_second_time(self):
		from sellos.tests import ui_fixtures

		leads = {}
		for title in ("Buyer One", "Investor Four"):
			as_user("agent")
			client = api.save_client(
				values={"client_name": f"{ui_fixtures.REGRESSION_PREFIX}{title}", "client_type": "Buyer"}
			)
			leads[title] = api.save_lead(values={"client": client["name"]})["lead"]["name"]
		for _ in range(2):
			ui_fixtures._seed_requirements(email("agent"), email("agent"))
			one = api.get_lead(leads["Buyer One"])["requirements"]
			self.assertEqual(one["configuration"], ["2 BHK", "3 BHK"])
			self.assertEqual(one["preferred_localities"], ["Andheri West", "Powai"])
			self.assertEqual(one["timeline"], "Within 3 months")
			four = api.get_lead(leads["Investor Four"])["requirements"]
			self.assertEqual(four["property_type"], "Villa")
			self.assertEqual(four["purpose"], "Investment")
