"""SOS-P7-07: price lists, payment plans and cost sheets, on hand worked examples."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import getdate

from sellos.inventory import api, cost_sheet, pricing
from sellos.inventory.test_p4_01_inventory import InventoryCase, _as
from sellos.testing.users import TEST_USERS
from sellos.tests import phones

RATES = {"stamp_duty_percent": 6, "registration_percent": 1, "gst_percent": 5}
# A 650 sq ft unit on floor 12 with one parking slot, a base rate of Rs 12,000 and a floor rise of Rs 100 per
# sq ft above floor 4:
#   base price       12,000 x 650            = 78,00,000
#   floor rise       8 floors x 100 x 650    =  5,20,000
#   preferred loc.   150 x 650               =    97,500
#   parking          4,00,000 x 1 slot       =  4,00,000
#   development      2,50,000                =  2,50,000
#   agreement value                          = 90,67,500
#   stamp duty 6%      5,44,050   registration 1%    90,675   GST 5%   4,53,375
#   total                                    = 1,01,55,600
WORKED = {
	"carpet_area": 650,
	"floor": 12,
	"parking": 1,
	"base_rate": 12000,
	"floor_rise_rate": 100,
	"floor_rise_from_floor": 4,
	"charges": [
		{
			"charge_type": "Preferred location",
			"charge_name": "Garden",
			"basis": "Rate per sq ft",
			"value": 150,
		},
		{"charge_type": "Parking", "charge_name": "Parking", "basis": "Amount", "value": 400000},
		{"charge_type": "Other", "charge_name": "Development", "basis": "Amount", "value": 250000},
	],
	**RATES,
}
LIST_CHARGES = [
	{"charge_type": "Preferred location", "charge_name": "Garden", "basis": "Rate per sq ft", "value": 150},
	{"charge_type": "Parking", "charge_name": "Parking", "basis": "Amount", "value": 400000},
	{
		"charge_type": "Other",
		"charge_name": "Development",
		"basis": "Amount",
		"value": 250000,
		"always_apply": 1,
	},
]
PLAN = [
	{"label": "On booking", "due_on": "On booking", "percent": 20},
	{"label": "On slab", "due_on": "On the 5th floor slab", "percent": 30},
	{"label": "On possession", "due_on": "On possession", "percent": 50},
]


class TestCostArithmetic(UnitTestCase):
	"""SOS-P7-07: the price of a unit, in whole rupees, on hand worked examples."""

	def test_the_worked_example_adds_up_line_by_line(self):
		got = pricing.cost_breakdown(**WORKED)
		self.assertEqual(
			(got["base_price"], got["floor_rise_amount"], got["floors_above"]), (7800000, 520000, 8)
		)
		self.assertEqual([c["amount"] for c in got["charges"]], [97500, 400000, 250000])
		self.assertEqual(got["agreement_value"], 9067500)
		self.assertEqual((got["stamp_duty"], got["registration"], got["gst"]), (544050, 90675, 453375))
		self.assertEqual(got["total"], 10155600)

	def test_every_amount_is_rounded_half_up_to_the_rupee(self):
		got = pricing.cost_breakdown(
			carpet_area=612.5,
			floor=2,
			parking=0,
			base_rate=9999.5,
			floor_rise_rate=0,
			floor_rise_from_floor=0,
			charges=[],
			stamp_duty_percent=5,
			registration_percent=1,
			gst_percent=5,
		)
		# 9,999.5 x 612.5 = 61,24,693.75 and 5% of 61,24,694 = 3,06,234.70.
		self.assertEqual(got["base_price"], 6124694)
		self.assertEqual((got["stamp_duty"], got["registration"], got["gst"]), (306235, 61247, 306235))
		self.assertEqual(got["total"], 6798411)

	def test_a_half_rupee_goes_up_and_a_floor_at_or_below_the_set_floor_has_no_rise(self):
		self.assertEqual([pricing.rupees(v) for v in (0.5, 1.5, 2.49, 2.5)], [1, 2, 2, 3])
		for floor in (None, 0, 4):
			got = pricing.cost_breakdown(**{**WORKED, "floor": floor})
			self.assertEqual(got["floor_rise_amount"], 0, floor)

	def test_parking_is_per_slot_and_a_rate_is_per_sq_ft(self):
		parking = {"charge_type": "Parking", "charge_name": "P", "basis": "Amount", "value": 400000}
		per_sq_ft = {**parking, "basis": "Rate per sq ft", "value": 100}
		self.assertEqual(pricing.charge_amount(parking, 650, 2), 800000)
		self.assertEqual(pricing.charge_amount(parking, 650, 0), 0)
		self.assertEqual(pricing.charge_amount(per_sq_ft, 650, 2), 65000)

	def test_the_schedule_adds_up_to_the_total_whatever_the_rounding(self):
		plan = [
			{"label": "A", "percent": 33.33},
			{"label": "B", "percent": 33.33},
			{"label": "C", "percent": 33.34},
		]
		rows = pricing.payment_schedule(plan, 10155600)
		self.assertEqual(sum(r["amount"] for r in rows), 10155600)
		self.assertEqual([r["amount"] for r in rows], [3384861, 3384861, 3385878])
		rows = pricing.payment_schedule([dict(p) for p in PLAN], 10155600)
		self.assertEqual([r["amount"] for r in rows], [2031120, 3046680, 5077800])


class PricingCase(InventoryCase):
	def setUp(self):
		super().setUp()
		self.project = self.make_project("P707 Project", rera="P51800070701", developer="P707 Developer")
		self.unit = self.make_unit(
			self.project, "1201", configuration="2 BHK", floor=12, parking=1, carpet_area=650
		)
		clock = patch.object(pricing, "today", return_value=getdate("2030-06-01"))
		clock.start()
		self.addCleanup(clock.stop)
		self.addCleanup(setattr, frappe.local, "response", frappe._dict())

	def make_list(self, title="P707 List", on="2030-01-01", **extra):
		values = {
			"title": title,
			"effective_from": on,
			"base_rate": 12000,
			"floor_rise_rate": 100,
			"floor_rise_from_floor": 4,
			"charges": LIST_CHARGES,
			**extra,
		}
		return pricing.save_price_list(self.project, values)

	def make_plan(self, name="P707 Plan", plan_type="Construction linked", instalments=None):
		return pricing.save_payment_plan(
			self.project,
			{
				"plan_name": name,
				"plan_type": plan_type,
				"instalments": PLAN if instalments is None else instalments,
			},
		)["name"]

	def set_rates(self, **rates):
		pricing.save_cost_settings(**{**RATES, **rates})

	def ready(self):
		self.make_list()
		self.set_rates()
		return self.make_plan()


class TestPriceLists(PricingCase):
	"""SOS-P7-07: dated price lists, one in force at a time, earlier ones kept."""

	def test_the_list_in_force_is_the_latest_one_whose_date_has_come(self):
		self.make_list("Old", "2029-01-01", base_rate=10000)
		self.make_list("Current", "2030-01-01")
		later = self.make_list("Later", "2031-01-01", base_rate=14000)
		forced = pricing.price_list_in_force(self.project)
		self.assertEqual(forced.title, "Current")
		self.assertEqual(pricing.price_list_in_force(self.project, "2029-06-01").title, "Old")
		self.assertIsNone(pricing.price_list_in_force(self.project, "2028-12-31"))
		state = pricing.project_pricing(self.project)
		self.assertEqual(
			[(row["title"], row["in_force"], row["scheduled"]) for row in state["price_lists"]],
			[("Later", False, True), ("Current", True, False), ("Old", False, False)],
		)
		# The earlier lists are kept as they were when the later one is made.
		self.assertEqual(frappe.db.get_value("Price List", {"title": "Old"}, "base_rate"), 10000)
		self.assertEqual(later["price_lists"][0]["title"], "Later")

	def test_a_new_list_takes_over_on_its_date_and_the_old_one_stays(self):
		self.make_list("Old", "2030-01-01")
		self.make_list("New", "2030-06-02", base_rate=13000)
		self.assertEqual(pricing.price_list_in_force(self.project).title, "Old")
		with patch.object(pricing, "today", return_value=getdate("2030-06-02")):
			self.assertEqual(pricing.price_list_in_force(self.project).title, "New")
		self.assertEqual(frappe.db.count("Price List", {"project": self.project}), 2)

	def test_a_list_is_never_changed_or_deleted_and_a_date_is_used_once(self):
		self.make_list("Old", "2030-01-01")
		doc = frappe.get_doc("Price List", {"title": "Old"})
		doc.base_rate = 1
		with self.assertRaises(frappe.PermissionError):  # not even a Company Admin has a write permission
			doc.save()
		doc.flags.ignore_permissions = True
		with self.assertRaises(frappe.ValidationError) as caught:  # and the record itself refuses
			doc.save()
		self.assertIn("not changed once made", str(caught.exception))
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Price List", doc.name)
		with self.assertRaises(frappe.ValidationError):
			self.make_list("Same day", "2030-01-01")

	def test_the_charges_are_checked_and_parking_always_applies(self):
		for charges in (
			[{"charge_type": "Other", "charge_name": " ", "basis": "Amount", "value": 1}],
			[
				{"charge_type": "Other", "charge_name": "Fee", "basis": "Amount", "value": 1},
				{"charge_type": "Other", "charge_name": "fee", "basis": "Amount", "value": 2},
			],
			[{"charge_type": "Other", "charge_name": "Fee", "basis": "Amount", "value": -5}],
		):
			with self.subTest(charges=charges), self.assertRaises(frappe.ValidationError):
				self.make_list("Bad", charges=charges)
		self.make_list()
		parking = pricing.price_list_in_force(self.project).charges[1]
		self.assertEqual((parking.charge_name, parking.always_apply), ("Parking", 1))

	def test_a_base_rate_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_list(base_rate=None)

	def test_only_a_company_admin_makes_a_list_and_an_agent_reads_it(self):
		self.make_list()
		_as("agent")
		self.assertEqual(pricing.project_pricing(self.project)["can_edit"], False)
		with self.assertRaises(frappe.PermissionError):
			pricing.save_price_list(
				self.project, {"title": "x", "effective_from": "2030-02-02", "base_rate": 1}
			)
		_as("sales_manager")
		self.assertEqual(len(pricing.project_pricing(self.project)["price_lists"]), 1)


class TestPaymentPlans(PricingCase):
	"""SOS-P7-07: payment plan templates whose instalments add up to 100 percent."""

	def test_a_plan_of_each_kind_that_adds_up_to_100_is_saved(self):
		self.make_plan("Construction")
		self.make_plan(
			"Time",
			"Time linked",
			[
				{"label": "Now", "days_after_booking": 0, "percent": 10},
				{"label": "After 30 days", "days_after_booking": 30, "percent": 90},
			],
		)
		self.make_plan("Down", "Down payment", [{"label": "On booking", "percent": 100}])
		self.assertEqual(frappe.db.count("Payment Plan", {"project": self.project}), 3)

	def test_a_plan_that_does_not_add_up_to_100_is_refused(self):
		for percents in ([20, 30, 49], [50, 30, 30], [99.99], [33.33, 33.33, 33.33]):
			rows = [{"label": f"R{i}", "due_on": "x", "percent": p} for i, p in enumerate(percents)]
			with self.subTest(percents=percents), self.assertRaises(frappe.ValidationError) as caught:
				self.make_plan("Bad", instalments=rows)
			self.assertIn("must add up to 100", str(caught.exception))
		self.assertEqual(frappe.db.count("Payment Plan", {"project": self.project}), 0)

	def test_decimals_that_add_up_to_100_exactly_are_accepted(self):
		rows = [{"label": f"R{i}", "due_on": "x", "percent": p} for i, p in enumerate([33.33, 33.33, 33.34])]
		self.make_plan("Thirds", instalments=rows)

	def test_each_kind_needs_its_own_detail_and_each_instalment_a_percent(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_plan(
				"No stage", instalments=[{"label": "A", "percent": 100}]
			)  # construction needs a stage
		with self.assertRaises(frappe.ValidationError):
			self.make_plan(
				"Backwards",
				"Time linked",
				[
					{"label": "A", "days_after_booking": 30, "percent": 50},
					{"label": "B", "days_after_booking": 10, "percent": 50},
				],
			)
		with self.assertRaises(frappe.ValidationError):
			self.make_plan(
				"Zero", "Down payment", [{"label": "A", "percent": 0}, {"label": "B", "percent": 100}]
			)
		with self.assertRaises(frappe.ValidationError):
			self.make_plan("Empty", "Down payment", [])

	def test_a_plan_is_corrected_archived_and_a_name_is_used_once(self):
		name = self.make_plan()
		with self.assertRaises(frappe.ValidationError):
			self.make_plan()
		other = self.make_plan("Down", "Down payment", [{"label": "On booking", "percent": 100}])
		state = pricing.save_payment_plan(
			self.project,
			{
				"plan_name": "P707 Plan",
				"plan_type": "Down payment",
				"instalments": [{"label": "All", "percent": 100}],
			},
			name,
		)
		self.assertEqual(frappe.get_doc("Payment Plan", name).plan_type, "Down payment")
		with self.assertRaises(frappe.ValidationError):  # an edit is held to the 100 percent rule too
			pricing.save_payment_plan(self.project, {"instalments": [{"label": "All", "percent": 90}]}, name)
		pricing.archive_payment_plan(other)
		self.assertEqual(frappe.db.get_value("Payment Plan", other, "archived"), 1)
		self.assertEqual(len(state["payment_plans"]), 2)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Payment Plan", other)


class TestCostSettings(PricingCase):
	"""SOS-P7-07: the percentages are company settings a Company Admin sets."""

	def test_the_percentages_are_saved_read_back_and_checked(self):
		self.assertIsNone(pricing.cost_rates())
		pricing.save_cost_settings("5.5", 1, 0)
		self.assertEqual(
			pricing.cost_rates(), {"stamp_duty_percent": 5.5, "registration_percent": 1, "gst_percent": 0}
		)
		for bad in ("abc", -1, 101, "", "nan"):
			with self.subTest(bad=bad), self.assertRaises(frappe.ValidationError):
				pricing.save_cost_settings(bad, 1, 5)
		self.assertEqual(pricing.cost_rates()["stamp_duty_percent"], 5.5)

	def test_a_cost_sheet_waits_for_the_price_list_and_the_percentages(self):
		plan = self.make_plan()
		options = cost_sheet.cost_sheet_options(self.unit)
		self.assertFalse(options["ready"])
		self.assertIn("no price list in force", options["problem"])
		with self.assertRaises(frappe.ValidationError):
			cost_sheet.make_cost_sheet(self.unit, plan)
		self.make_list()
		self.assertIn("percentages are not set", cost_sheet.cost_sheet_options(self.unit)["problem"])
		with self.assertRaises(frappe.ValidationError):
			cost_sheet.make_cost_sheet(self.unit, plan)
		self.set_rates()
		self.assertTrue(cost_sheet.cost_sheet_options(self.unit)["ready"])

	def test_an_agent_may_not_set_them(self):
		_as("agent")
		with self.assertRaises(frappe.PermissionError):
			pricing.save_cost_settings(5, 1, 5)


class TestCostSheets(PricingCase):
	"""SOS-P7-07: a cost sheet of a unit, kept as it was issued."""

	def test_a_cost_sheet_matches_the_worked_example(self):
		plan = self.ready()
		sheet = cost_sheet.make_cost_sheet(self.unit, plan, ["Garden"])
		self.assertEqual(
			(sheet["base_price"], sheet["floor_rise_amount"], sheet["charges_total"]),
			(7800000, 520000, 747500),
		)
		self.assertEqual(
			[(c["charge_name"], c["amount"]) for c in sheet["charges"]],
			[("Garden", 97500), ("Parking", 400000), ("Development", 250000)],
		)
		self.assertEqual(sheet["agreement_value"], 9067500)
		self.assertEqual((sheet["stamp_duty"], sheet["registration"], sheet["gst"]), (544050, 90675, 453375))
		self.assertEqual(sheet["total"], 10155600)
		self.assertEqual(
			[(i["label"], i["due_on"], i["amount"]) for i in sheet["instalments"]],
			[
				("On booking", "On booking", 2031120),
				("On slab", "On the 5th floor slab", 3046680),
				("On possession", "On possession", 5077800),
			],
		)
		self.assertEqual(sum(i["amount"] for i in sheet["instalments"]), sheet["total"])
		self.assertEqual(frappe.get_doc("Cost Sheet", sheet["name"]).total, 10155600)

	def test_an_optional_charge_is_left_out_unless_the_agent_chooses_it(self):
		plan = self.ready()
		sheet = cost_sheet.make_cost_sheet(self.unit, plan)
		self.assertEqual([c["charge_name"] for c in sheet["charges"]], ["Parking", "Development"])
		self.assertEqual(sheet["total"], 10155600 - 97500 - round(97500 * 0.12))
		with self.assertRaises(frappe.ValidationError):
			cost_sheet.make_cost_sheet(self.unit, plan, ["Pool view"])
		with self.assertRaises(frappe.ValidationError):  # parking is not the agent's to choose
			cost_sheet.make_cost_sheet(self.unit, plan, ["Parking"])

	def test_the_sheet_records_the_list_and_the_percentages_it_used(self):
		plan = self.ready()
		sheet = cost_sheet.make_cost_sheet(self.unit, plan, ["Garden"])
		self.assertEqual(
			(
				sheet["price_list_title"],
				sheet["price_list_from"],
				sheet["base_rate"],
				sheet["floor_rise_rate"],
			),
			("P707 List", "2030-01-01", 12000, 100),
		)
		self.assertEqual(
			(sheet["stamp_duty_percent"], sheet["registration_percent"], sheet["gst_percent"]), (6, 1, 5)
		)
		self.assertEqual(
			(sheet["unit_number"], sheet["carpet_area"], sheet["floor"], sheet["parking"]),
			("1201", 650, 12, 1),
		)
		self.assertEqual((sheet["plan_name"], sheet["plan_type"]), ("P707 Plan", "Construction linked"))

	def test_an_issued_sheet_is_unchanged_after_a_price_change(self):
		plan = self.ready()
		first = cost_sheet.make_cost_sheet(self.unit, plan, ["Garden"])
		# A new price list takes over, the percentages change, the plan is rewritten and the unit is corrected.
		self.make_list("Dearer", "2030-05-01", base_rate=20000, charges=[])
		self.set_rates(stamp_duty_percent=7, gst_percent=12)
		pricing.save_payment_plan(
			self.project,
			{
				"plan_name": "P707 Plan",
				"plan_type": "Down payment",
				"instalments": [{"label": "All", "percent": 100}],
			},
			plan,
		)
		api.save_unit({"carpet_area": 700, "floor": 3}, self.unit)
		again = cost_sheet.get_cost_sheet(first["name"])
		for key in (
			"base_price",
			"floor_rise_amount",
			"charges_total",
			"agreement_value",
			"stamp_duty",
			"registration",
			"gst",
			"total",
			"charges",
			"instalments",
			"stamp_duty_percent",
			"gst_percent",
			"price_list_title",
			"carpet_area",
			"floor",
			"plan_type",
		):
			self.assertEqual(again[key], first[key], key)
		self.assertEqual(again["total"], 10155600)
		# A new sheet uses what is in force now.
		second = cost_sheet.make_cost_sheet(self.unit, plan)
		self.assertEqual(
			(second["price_list_title"], second["base_rate"], second["gst_percent"]), ("Dearer", 20000, 12)
		)
		self.assertEqual(second["base_price"], 14000000)
		self.assertEqual(len(cost_sheet.unit_cost_sheets(self.unit)["sheets"]), 2)

	def test_a_sheet_is_never_changed_or_deleted(self):
		sheet = cost_sheet.make_cost_sheet(self.unit, self.ready())
		doc = frappe.get_doc("Cost Sheet", sheet["name"])
		doc.total = 1
		with self.assertRaises(frappe.PermissionError):
			doc.save()
		doc.flags.ignore_permissions = True
		with self.assertRaises(frappe.ValidationError) as caught:
			doc.save()
		self.assertIn("not changed once issued", str(caught.exception))
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Cost Sheet", doc.name)
		self.assertEqual(frappe.db.get_value("Cost Sheet", doc.name, "total"), sheet["total"])

	def test_the_plan_must_be_of_the_units_project_and_not_archived(self):
		plan = self.ready()
		other = self.make_project("P707 Other", rera="P51800070702", developer="P707 Developer")
		foreign = pricing.save_payment_plan(
			other,
			{
				"plan_name": "Foreign",
				"plan_type": "Down payment",
				"instalments": [{"label": "A", "percent": 100}],
			},
		)["name"]
		for bad in (foreign, "", "no such plan"):
			with self.subTest(plan=bad), self.assertRaises(frappe.ValidationError):
				cost_sheet.make_cost_sheet(self.unit, bad)
		pricing.archive_payment_plan(plan)
		with self.assertRaises(frappe.ValidationError):
			cost_sheet.make_cost_sheet(self.unit, plan)
		self.assertEqual(cost_sheet.cost_sheet_options(self.unit)["plans"], [])

	def test_an_agent_makes_a_sheet_and_sees_only_their_own(self):
		plan = self.ready()
		admin_sheet = cost_sheet.make_cost_sheet(self.unit, plan)["name"]
		_as("agent")
		own = cost_sheet.make_cost_sheet(self.unit, plan)["name"]
		self.assertEqual([s["name"] for s in cost_sheet.unit_cost_sheets(self.unit)["sheets"]], [own])
		self.assertEqual(cost_sheet.get_cost_sheet(own)["total"], 10155600 - 97500 - round(97500 * 0.12))
		with self.assertRaises(frappe.PermissionError):
			cost_sheet.get_cost_sheet(admin_sheet)
		with self.assertRaises(frappe.PermissionError):
			cost_sheet.cost_sheet_pdf(admin_sheet)
		_as("company_admin")
		self.assertEqual(
			{s["name"] for s in cost_sheet.unit_cost_sheets(self.unit)["sheets"]}, {admin_sheet, own}
		)

	def test_a_sales_manager_a_client_and_a_partner_have_no_cost_sheet_method(self):
		plan = self.ready()
		name = cost_sheet.make_cost_sheet(self.unit, plan)["name"]
		for key in ("sales_manager", "client", "channel_partner", "platform_admin"):
			_as(key)
			for call in (
				lambda: cost_sheet.get_cost_sheet(name),
				lambda: cost_sheet.cost_sheet_pdf(name),
				lambda: cost_sheet.cost_sheet_options(self.unit),
				lambda: cost_sheet.make_cost_sheet(self.unit, plan),
			):
				with self.subTest(who=key), self.assertRaises(frappe.PermissionError):
					call()


PHONE = phones.in_mobile(7071)


class TestCostSheetPdf(PricingCase):
	"""SOS-P7-07: the cost sheet as a PDF with the company's branding."""

	def brand(self):
		for field, value in (
			("company_name", "P707 Realty <b>"),
			("brand_color", "#AA2200"),
			("contact_phone", PHONE),
			("contact_email", "sales@p707.example"),
			("address", "7 Test Road, Mumbai"),
		):
			frappe.db.set_single_value("SellOS Settings", field, value)

	def test_the_page_carries_the_branding_the_figures_and_the_schedule_escaped(self):
		self.brand()
		sheet = cost_sheet.make_cost_sheet(self.unit, self.ready(), ["Garden"])
		html = cost_sheet.sheet_html(cost_sheet.get_cost_sheet(sheet["name"]))
		for text in (
			"P707 Realty &lt;b&gt;",
			"#AA2200",
			"sales@p707.example",
			PHONE,
			"7 Test Road, Mumbai",
			"Rs 1,01,55,600",
			"Rs 78,00,000",
			"Rs 5,44,050",
			"Rs 20,31,120",
			"P707 Project",
			"On the 5th floor slab",
		):
			self.assertIn(text, html)
		self.assertNotIn("P707 Realty <b>", html)

	def test_the_colour_must_be_a_real_colour(self):
		frappe.db.set_single_value("SellOS Settings", "brand_color", "red; background:url(x)")
		sheet = cost_sheet.make_cost_sheet(self.unit, self.ready())
		self.assertIn(cost_sheet.DEFAULT_COLOUR, cost_sheet.sheet_html(sheet))
		self.assertNotIn("url(x)", cost_sheet.sheet_html(sheet))

	def test_the_pdf_is_a_pdf_named_for_the_sheet(self):
		self.brand()
		sheet = cost_sheet.make_cost_sheet(self.unit, self.ready())
		frappe.local.response = frappe._dict()
		cost_sheet.cost_sheet_pdf(sheet["name"])
		self.assertTrue(frappe.local.response.filecontent.startswith(b"%PDF"))
		self.assertEqual(
			(frappe.local.response.type, frappe.local.response.filename), ("pdf", f"{sheet['name']}.pdf")
		)

	def test_indian_grouping(self):
		self.assertEqual(
			[cost_sheet.inr(n) for n in (0, 999, 1000, 100000, 10155600, 123456789, -2500)],
			["Rs 0", "Rs 999", "Rs 1,000", "Rs 1,00,000", "Rs 1,01,55,600", "Rs 12,34,56,789", "-Rs 2,500"],
		)


class TestDocTypesLoaded(IntegrationTestCase):
	"""SOS-P7-07: the DocTypes and settings fields exist after a migrate."""

	def test_the_doctypes_and_settings_are_there(self):
		for doctype in (
			"Price List",
			"Price List Charge",
			"Payment Plan",
			"Payment Plan Instalment",
			"Cost Sheet",
		):
			self.assertTrue(frappe.db.exists("DocType", doctype), doctype)
		fields = {f.fieldname for f in frappe.get_meta("SellOS Settings").fields}
		self.assertTrue({"stamp_duty_percent", "registration_percent", "gst_percent"} <= fields)


class TestRegressionSeed(PricingCase):
	"""SOS-P7-07: the regression data holds a priced project, two plans and one cost sheet, and is safe to run again."""

	def test_the_seed_makes_the_pricing_and_is_safe_to_run_again(self):
		from sellos.tests import ui_fixtures

		agent = TEST_USERS["agent"]["email"]
		ui_fixtures._seed_pricing(frappe.session.user, agent)
		ui_fixtures._seed_pricing(frappe.session.user, agent)
		project = frappe.db.get_value("Project", {"project_name": "Regression Pricing"}, "name")
		state = pricing.project_pricing(project)
		self.assertEqual(
			[(row["title"], row["in_force"]) for row in state["price_lists"]],
			[("Regression Price List", True)],
		)
		self.assertEqual(
			{row["plan_name"]: [i["percent"] for i in row["instalments"]] for row in state["payment_plans"]},
			{"Regression Construction Plan": [20, 30, 50], "Regression Time Plan": [10, 90]},
		)
		self.assertEqual(
			state["rates"], {"stamp_duty_percent": 6, "registration_percent": 1, "gst_percent": 5}
		)
		sheets = frappe.get_all(
			"Cost Sheet", filters={"project": project}, fields=["total", "owner", "plan_name"]
		)
		self.assertEqual(
			[(s.total, s.owner, s.plan_name) for s in sheets],
			[(10155600, agent, "Regression Construction Plan")],
		)
