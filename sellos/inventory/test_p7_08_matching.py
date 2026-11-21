"""SOS-P7-08: match buyers to inventory. The score on hand worked examples, what is never suggested, the
permissions in both directions, the weights, and the time of one lead against 5,000 units and listings."""

import time

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import now

from sellos.crm import api as crm
from sellos.crm.requirements import requirements_view
from sellos.inventory import api, listings, matching, pricing, structure
from sellos.inventory.test_p4_01_inventory import InventoryCase, _as
from sellos.testing.users import TEST_USERS
from sellos.tests import phones

EVEN = {part: 25 for part in matching.PARTS}


def req(**given):
	"""A lead's requirements as requirements_view returns them, with only what the example gives."""
	base = {
		"budget_from": None,
		"budget_to": None,
		"configuration": [],
		"property_type": "",
		"preferred_localities": [],
		"purpose": "",
		"timeline": "",
		"possession": "",
	}
	return {**base, **given}


def part(result, key):
	return next(p for p in result["parts"] if p["key"] == key)


class TestScoreByHand(UnitTestCase):
	"""SOS-P7-08: each part and the total, worked out by hand."""

	def test_five_percent_over_budget_scores_80_with_its_reason(self):
		result = matching.score(req(budget_to=1_000_000), {"price": 1_050_000}, EVEN)
		self.assertEqual(part(result, "budget")["score"], 80)  # 100 - 4 points for each of 5 percent
		self.assertEqual(part(result, "budget")["reason"], "5 percent over budget")
		self.assertEqual(result["score"], 80)  # only the budget applies, so it is the whole score

	def test_inside_the_range_scores_100_and_far_over_scores_0(self):
		self.assertEqual(matching.budget_part(900_000, 1_000_000, 950_000), (100.0, "Within budget"))
		self.assertEqual(matching.budget_part(None, 1_000_000, 1_300_000)[0], 0.0)  # 30 percent over
		self.assertEqual(matching.budget_part(None, 1_000_000, 1_000_000)[0], 100.0)

	def test_under_the_bottom_costs_one_point_a_percent(self):
		self.assertEqual(
			matching.budget_part(1_000_000, 2_000_000, 900_000),
			(90.0, "10 percent under budget"),
		)

	def test_a_price_with_no_value_scores_0_when_a_budget_is_given(self):
		self.assertEqual(matching.budget_part(1, 2, None), (0.0, "No price is set"))
		self.assertIsNone(matching.budget_part(None, None, 5))  # no budget given: the part is left out

	def test_configuration_exact_half_a_bedroom_a_bedroom_and_above(self):
		def score(wanted, have, kind="Apartment"):
			return matching.configuration_part(wanted, have, kind)

		self.assertEqual(score(["2 BHK"], "2 BHK"), (100.0, "2 BHK matches"))
		self.assertEqual(score(["2 BHK"], "2.5 BHK")[0], 60.0)
		self.assertEqual(score(["2 BHK"], "3 BHK")[0], 30.0)
		self.assertEqual(score(["2 BHK"], "1 BHK")[0], 30.0)
		self.assertEqual(score(["3 BHK"], "1 BHK")[0], 0.0)
		self.assertEqual(score(["1 BHK", "3 BHK"], "3 BHK")[0], 100.0)  # the best of those wanted
		self.assertEqual(score(["4 BHK and above"], "5 BHK")[0], 100.0)
		self.assertEqual(score(["4 BHK and above"], "3 BHK")[0], 30.0)
		self.assertEqual(score(["2 BHK"], "")[0], 0.0)
		self.assertIsNone(score(["2 BHK"], "", "Plot"))  # a plot has no configuration: left out
		self.assertIsNone(score([], "2 BHK"))

	def test_locality_exact_partial_and_other(self):
		self.assertEqual(matching.locality_part(["Powai"], "powai")[0], 100.0)
		self.assertEqual(matching.locality_part(["Powai"], "Powai Lake")[0], 70.0)
		self.assertEqual(matching.locality_part(["Powai", "Bandra"], "Andheri")[0], 0.0)
		self.assertEqual(matching.locality_part(["Powai"], "")[0], 0.0)
		self.assertIsNone(matching.locality_part([], "Powai"))

	def test_property_type_exact_similar_and_other(self):
		self.assertEqual(matching.type_part("Villa", "Villa")[0], 100.0)
		self.assertEqual(matching.type_part("Villa", "Independent house")[0], 60.0)
		self.assertEqual(matching.type_part("Villa", "Plot")[0], 0.0)
		self.assertIsNone(matching.type_part("", "Plot"))

	def test_the_total_is_the_weighted_average_of_the_parts_that_apply(self):
		wants = req(
			budget_to=1_000_000,
			configuration=["2 BHK"],
			preferred_localities=["Powai"],
			property_type="Apartment",
		)
		home = {
			"price": 1_050_000,
			"configuration": "2 BHK",
			"locality": "Powai",
			"property_type": "Apartment",
		}
		even = matching.score(wants, home, EVEN)
		self.assertEqual(even["score"], 95)  # (80 + 100 + 100 + 100) / 4
		self.assertEqual([p["points"] for p in even["parts"]], [20.0, 25.0, 25.0, 25.0])
		heavy = {"budget": 40, "configuration": 20, "locality": 20, "property_type": 20}
		self.assertEqual(matching.score(wants, home, heavy)["score"], 92)  # (80*40 + 100*60) / 100
		none_but_budget = {"budget": 0, "configuration": 10, "locality": 10, "property_type": 10}
		self.assertEqual(matching.score(wants, home, none_but_budget)["score"], 100)

	def test_a_part_the_buyer_did_not_give_is_left_out_with_a_note(self):
		result = matching.score(req(configuration=["2 BHK"]), {"configuration": "2 BHK"}, EVEN)
		self.assertEqual(result["score"], 100)
		self.assertFalse(part(result, "budget")["applies"])
		self.assertEqual(part(result, "budget")["reason"], "The buyer did not say")
		self.assertEqual(part(result, "budget")["points"], 0)

	def test_a_buyer_who_asked_for_nothing_scores_every_home_0(self):
		self.assertEqual(matching.score(req(), {"price": 5, "configuration": "2 BHK"}, EVEN)["score"], 0)

	def test_all_weights_at_zero_score_0(self):
		zero = {part: 0 for part in matching.PARTS}
		self.assertEqual(matching.score(req(budget_to=10), {"price": 10}, zero)["score"], 0)


class MatchCase(InventoryCase):
	def setUp(self):
		super().setUp()
		self.agent = TEST_USERS["agent"]["email"]
		self.manager = TEST_USERS["sales_manager"]["email"]
		self.project = self.make_project(
			"P708 Powai Project", rera="P51800070801", developer="P708 Developer"
		)
		frappe.db.set_value("Project", self.project, "locality", "Powai")
		self.tower = structure.add_tower(self.project, "Tower M", "1 to 1")["name"]
		structure.generate_floor_units(self.tower, 1, "101 to 105", 640, "2 BHK", "M")
		self.units = {u["unit_number"]: u["name"] for u in api.get_project(self.project)["units"]}
		pricing.save_price_list(
			self.project, {"title": "P708 prices", "effective_from": "2020-01-01", "base_rate": 12500}
		)  # 640 sq ft at 12,500 is 80,00,000
		self.lead = self.make_lead(self.agent, 7081, budget_to=7_619_000)

	def make_lead(self, owner, seed, **extra):
		client = crm.save_client(
			values={
				"client_name": f"P708 Buyer {seed}",
				"client_type": "Buyer",
				"phone": phones.in_mobile(seed),
			}
		)
		values = {
			"client": client["name"],
			"source": "Website",
			"assigned_to": owner,
			"configuration": ["2 BHK"],
			"property_type": "Apartment",
			"preferred_localities": ["Powai"],
			**extra,
		}
		return crm.save_lead(values=values)["lead"]["name"]

	def matches(self, lead=None):
		return matching.matches_for_lead(lead or self.lead)

	def titles(self, result, kind="Unit"):
		return {m["name"] for m in result["matches"] if m["kind"] == kind}

	def publish_listing(self, **extra):
		prop = api.save_property(
			{
				"title": "P708 Powai Flat",
				"property_type": "Apartment",
				"city": "Mumbai",
				"locality": "Powai",
				"configuration": "2 BHK",
				"carpet_area": 700,
			}
		)["name"]
		values = {
			"title": "P708 Listing",
			"listing_type": "Direct",
			"property": prop,
			"asking_price": 7_500_000,
			"description": "A flat",
			**extra,
		}
		name = listings.save_listing(values)["name"]
		listings.publish_listing(name)
		return name


class TestMatchesFromALead(MatchCase):
	"""SOS-P7-08: from a lead, the units and listings that suit it, scored, with each part."""

	def test_a_unit_is_scored_with_the_four_parts_and_the_example_reason(self):
		_as("agent")
		result = self.matches()
		unit = next(m for m in result["matches"] if m["name"] == self.units["M101"])
		self.assertEqual(unit["score"], 95)  # 5 percent over budget gives 80, the other three 100
		self.assertEqual([p["key"] for p in unit["parts"]], list(matching.PARTS))
		self.assertEqual(
			[(p["label"], p["score"], p["reason"]) for p in unit["parts"]][:2],
			[("Budget", 80, "5 percent over budget"), ("Configuration", 100, "2 BHK matches")],
		)
		self.assertEqual(unit["price"], 8_000_000)
		self.assertEqual(result["weights"], EVEN)
		self.assertTrue(result["has_requirements"])

	def test_the_best_match_comes_first_and_a_published_listing_is_scored_too(self):
		self.publish_listing()
		_as("agent")
		result = self.matches()
		listing = next(m for m in result["matches"] if m["kind"] == "Listing")
		self.assertEqual(listing["score"], 100)  # 75,00,000 is inside the budget
		self.assertEqual(result["matches"][0]["name"], listing["name"])
		scores = [m["score"] for m in result["matches"]]
		self.assertEqual(scores, sorted(scores, reverse=True))

	def test_a_lead_with_no_requirements_gets_no_matches_and_is_told(self):
		client = crm.save_client(
			values={"client_name": "P708 Blank", "client_type": "Buyer", "phone": phones.in_mobile(7089)}
		)
		blank = crm.save_lead(
			values={"client": client["name"], "source": "Website", "assigned_to": self.agent}
		)["lead"]["name"]
		_as("agent")
		result = self.matches(blank)
		self.assertEqual((result["matches"], result["has_requirements"]), ([], False))

	def test_the_company_weights_change_the_score(self):
		_as("company_admin")
		matching.save_match_settings(budget=70, configuration=10, locality=10, property_type=10)
		_as("agent")
		unit = next(m for m in self.matches()["matches"] if m["name"] == self.units["M101"])
		self.assertEqual(unit["score"], 86)  # 80 * 0.7 + 100 * 0.3 = 86

	def test_a_lead_is_matched_only_by_a_user_who_may_see_it(self):
		_as("sales_manager")  # no team yet, so no lead
		with self.assertRaises(frappe.PermissionError):
			self.matches()


class TestNeverSuggested(MatchCase):
	"""SOS-P7-08: a unit that is not Available and a listing that is not published are never suggested."""

	def test_only_available_units_are_suggested(self):
		api.set_inventory_status("Unit", self.units["M102"], "Held")
		frappe.db.set_value("Unit", self.units["M103"], "status", "Booked")
		frappe.db.set_value("Unit", self.units["M104"], "status", "Sold")
		frappe.db.set_value("Unit", self.units["M105"], "status", "Blocked")
		api.set_inventory_archived("Unit", self.units["M101"], 1)
		_as("agent")
		self.assertEqual(self.titles(self.matches()), set())

	def test_a_unit_that_is_available_is_suggested(self):
		_as("agent")
		self.assertEqual(self.titles(self.matches()), set(self.units.values()))

	def test_a_draft_and_a_withdrawn_listing_are_not_suggested(self):
		name = self.publish_listing()
		draft = listings.save_listing(
			{
				"title": "P708 Draft",
				"listing_type": "Primary",
				"unit": self.units["M102"],
				"asking_price": 7_000_000,
				"description": "x",
			}
		)["name"]
		_as("agent")
		self.assertEqual(self.titles(self.matches(), "Listing"), {name})
		_as("company_admin")
		listings.unpublish_listing(name)
		_as("agent")
		self.assertEqual(self.titles(self.matches(), "Listing"), set())
		self.assertNotIn(draft, self.titles(self.matches(), "Listing"))

	def test_a_listing_of_a_held_property_or_unit_is_not_suggested(self):
		name = self.publish_listing()
		prop = frappe.db.get_value("Listing", name, "property")
		api.set_inventory_status("Property", prop, "Held")
		unit_listing = listings.save_listing(
			{
				"title": "P708 Unit Listing",
				"listing_type": "Primary",
				"unit": self.units["M101"],
				"asking_price": 8_000_000,
				"description": "x",
			}
		)["name"]
		listings.publish_listing(unit_listing)
		_as("agent")
		self.assertEqual(self.titles(self.matches(), "Listing"), {unit_listing})
		_as("company_admin")
		api.set_inventory_status("Unit", self.units["M101"], "Held")
		_as("agent")
		self.assertEqual(self.titles(self.matches(), "Listing"), set())

	def test_an_archived_listing_is_not_suggested(self):
		name = self.publish_listing()
		frappe.db.set_value("Listing", name, "archived", 1)
		_as("agent")
		self.assertEqual(self.titles(self.matches(), "Listing"), set())

	def test_from_the_other_side_a_held_unit_and_a_draft_listing_suit_no_lead(self):
		draft = listings.save_listing(
			{
				"title": "P708 Draft Two",
				"listing_type": "Primary",
				"unit": self.units["M101"],
				"asking_price": 8_000_000,
				"description": "x",
			}
		)["name"]
		api.set_inventory_status("Unit", self.units["M102"], "Held")
		_as("agent")
		held = matching.leads_for_unit(self.units["M102"])
		self.assertEqual((held["eligible"], held["leads"]), (False, []))
		unpublished = matching.leads_for_listing(draft)
		self.assertEqual((unpublished["eligible"], unpublished["leads"]), (False, []))
		self.assertTrue(unpublished["message"])


class TestLeadsFromAUnit(MatchCase):
	"""SOS-P7-08: from a unit or a listing, the leads it suits that the user may see, with masked phones."""

	def setUp(self):
		super().setUp()
		self.admin_lead = self.make_lead(TEST_USERS["company_admin"]["email"], 7082, budget_to=7_619_000)
		self.team = frappe.get_doc(
			{
				"doctype": "Sales Team",
				"team_name": "P708 Team",
				"manager": self.manager,
				"members": [{"agent": self.agent}],
			}
		).insert()

	def names(self, result):
		return {lead["name"] for lead in result["leads"]}

	def test_the_company_admin_sees_every_lead_and_the_full_phone(self):
		unit = self.units["M101"]
		result = matching.leads_for_unit(unit)
		self.assertTrue(result["eligible"])
		self.assertEqual(self.names(result), {self.lead, self.admin_lead})
		phones_shown = {lead["phone"] for lead in result["leads"]}
		self.assertIn(phones.in_mobile(7081), phones_shown)

	def test_an_agent_sees_only_their_own_leads_with_masked_phones(self):
		_as("agent")
		result = matching.leads_for_unit(self.units["M101"])
		self.assertEqual(self.names(result), {self.lead})
		text = frappe.as_json(result)
		for form in phones.forms(phones.in_mobile(7081)) + phones.forms(phones.in_mobile(7082)):
			self.assertNotIn(form, text)
		self.assertTrue(result["leads"][0]["phone"])  # a masked number is still shown
		self.assertEqual(result["leads"][0]["score"], 95)

	def test_a_sales_manager_sees_only_their_teams_leads_with_masked_phones(self):
		_as("sales_manager")
		result = matching.leads_for_unit(self.units["M101"])
		self.assertEqual(self.names(result), {self.lead})
		text = frappe.as_json(result)
		for form in phones.forms(phones.in_mobile(7081)):
			self.assertNotIn(form, text)

	def test_a_listing_suits_the_leads_the_user_may_see(self):
		name = self.publish_listing()
		_as("agent")
		result = matching.leads_for_listing(name)
		self.assertTrue(result["eligible"])
		self.assertEqual(self.names(result), {self.lead})
		self.assertEqual(result["leads"][0]["score"], 100)

	def test_a_lead_that_does_not_suit_is_left_out(self):
		unsuited = self.make_lead(
			self.agent, 7083, configuration=["1 RK"], preferred_localities=["Andheri"], property_type="Plot"
		)
		_as("agent")
		self.assertNotIn(unsuited, self.names(matching.leads_for_unit(self.units["M101"])))

	def test_an_archived_lead_is_not_listed(self):
		crm.set_archived("Lead", self.lead, 1)
		_as("agent")
		self.assertEqual(matching.leads_for_unit(self.units["M101"])["leads"], [])

	def test_who_may_call_what(self):
		for who in ("client", "channel_partner", "outsider"):
			if who not in TEST_USERS:
				continue
			_as(who)
			with self.assertRaises(frappe.PermissionError):
				matching.leads_for_unit(self.units["M101"])
		_as("agent")
		with self.assertRaises(frappe.PermissionError):
			matching.save_match_settings(budget=1, configuration=1, locality=1, property_type=1)
		with self.assertRaises(frappe.PermissionError):
			matching.get_match_settings()


class TestWeights(MatchCase):
	"""SOS-P7-08: the four weights are company settings, 25 each by default."""

	def test_the_default_is_25_each_and_a_saved_weight_reads_back(self):
		for field in matching.WEIGHT_FIELDS.values():
			self.assertEqual(frappe.get_meta("SellOS Settings").get_field(field).default, "25")
		self.assertEqual(matching.get_match_settings()["weights"], EVEN)
		saved = matching.save_match_settings(budget="40", configuration=30, locality=20, property_type=0)
		self.assertEqual(
			saved["weights"], {"budget": 40, "configuration": 30, "locality": 20, "property_type": 0}
		)
		self.assertEqual(matching.weights(), saved["weights"])

	def test_a_weight_outside_0_to_100_or_all_zero_is_refused(self):
		for bad in (-1, 101, "x", ""):
			with self.assertRaises(frappe.ValidationError):
				matching.save_match_settings(budget=bad, configuration=25, locality=25, property_type=25)
		with self.assertRaises(frappe.ValidationError):
			matching.save_match_settings(budget=0, configuration=0, locality=0, property_type=0)
		self.assertEqual(matching.weights(), EVEN)


class TestSpeed(MatchCase):
	"""SOS-P7-08: one lead against 5,000 units and listings answers within 2 seconds."""

	def make_records(self, units=4000, listing_count=1000):
		stamp = now()
		unit_rows = [
			(
				f"P708SPEED{i:05d}",
				stamp,
				stamp,
				"Administrator",
				"Administrator",
				self.project,
				f"S{i}",
				"2 BHK" if i % 3 else "3 BHK",
				600 + i % 200,
				i % 30,
				"Available",
			)
			for i in range(units)
		]
		frappe.db.bulk_insert(
			"Unit",
			[
				"name",
				"creation",
				"modified",
				"modified_by",
				"owner",
				"project",
				"unit_number",
				"configuration",
				"carpet_area",
				"floor",
				"status",
			],
			unit_rows,
		)
		listing_rows = [
			(
				f"P708SPEEDL{i:05d}",
				stamp,
				stamp,
				"Administrator",
				"Administrator",
				f"P708 Speed Listing {i}",
				"Primary",
				f"P708SPEED{i:05d}",
				5_000_000 + i * 1000,
				1,
			)
			for i in range(listing_count)
		]
		frappe.db.bulk_insert(
			"Listing",
			[
				"name",
				"creation",
				"modified",
				"modified_by",
				"owner",
				"title",
				"listing_type",
				"unit",
				"asking_price",
				"published",
			],
			listing_rows,
		)

	def test_one_lead_against_5000_homes_takes_under_2_seconds(self):
		self.make_records()
		_as("agent")
		self.assertEqual(frappe.db.count("Unit", {"status": "Available"}), 4005)
		started = time.perf_counter()
		result = self.matches()
		elapsed = time.perf_counter() - started
		self.assertGreater(result["total"], 4000)
		self.assertEqual(len(result["matches"]), matching.MAX_RESULTS)
		self.assertLess(elapsed, 2.0, f"matching took {elapsed:.2f} seconds")
		self.assertEqual(requirements_view(frappe.get_doc("Lead", self.lead))["budget_to"], 7_619_000)
