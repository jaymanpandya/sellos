"""SOS-P7-10: book a unit from a lead, cancel the booking, and what each refusal and failure leaves behind."""

import threading
from unittest.mock import patch

import frappe
from frappe.utils import add_days, now_datetime

from sellos.access import partner_registrations
from sellos.crm import api as crm
from sellos.crm import consent, pipeline
from sellos.inventory import bookings, holds
from sellos.inventory.test_p4_01_inventory import _as
from sellos.inventory.test_p7_06_holds import HoldCase
from sellos.testing.users import TEST_USERS

PRICE = 8000000
AMOUNT = 100000


class BookingCase(HoldCase):
	def setUp(self):
		super().setUp()
		pipeline.ensure_default_stages()
		self.admin = TEST_USERS["company_admin"]["email"]
		self.partner_email = TEST_USERS["channel_partner"]["email"]

	def book(self, number="G101", lead=None, **extra):
		values = {
			"lead": lead or self.lead,
			"unit": self.units[number],
			"price": PRICE,
			"booking_amount": AMOUNT,
		}
		return bookings.book_unit(**{**values, **extra})

	def make_firm(self):
		firm = frappe.get_doc(
			{
				"doctype": "Channel Partner Firm",
				"firm_name": "P710 Firm",
				"contact_user": self.partner_email,
				"contact_person": "P710 Contact",
				"email": self.partner_email,
			}
		).insert(ignore_permissions=True)
		firm.db_set("status", "Approved")
		return firm.name

	def register(self, firm, lead):
		doc = frappe.get_doc(
			{
				"doctype": "Partner Registration",
				"buyer_name": "P710 Buyer",
				"partner_firm": firm,
				"partner_user": self.partner_email,
				"lead": lead,
			}
		).insert(ignore_permissions=True)
		doc.change_status("Approved")
		return doc.name

	def stage(self, lead=None):
		return frappe.db.get_value("Lead", lead or self.lead, "stage")


class TestBooking(BookingCase):
	"""SOS-P7-10: confirming makes the Deal, marks the unit Booked and moves the lead to Booking."""

	def test_an_agent_books_an_available_unit_in_one_step(self):
		_as("agent")
		before = self.stage()
		result = self.book()
		deal = frappe.get_doc("Deal", result["deal"])
		self.assertEqual(
			(deal.lead, deal.unit, deal.price, deal.booking_amount),
			(self.lead, self.units["G101"], PRICE, AMOUNT),
		)
		self.assertEqual(deal.client, frappe.db.get_value("Lead", self.lead, "client"))
		self.assertEqual((deal.deal_status, deal.approval_status), ("Active", "Pending approval"))
		self.assertEqual(sum(r.percent for r in deal.splits), 100)
		self.assertEqual([r.party_type for r in deal.splits], ["Agent", "Company"])
		self.assertEqual(self.unit("G101").status, "Booked")
		self.assertEqual(self.stage(), "Booking")
		self.assertNotEqual(before, "Booking")
		self.assertEqual(result["stage"], "Booking")
		log = self.unit("G101").status_log[-1]
		self.assertEqual((log.to_status, log.changed_by), ("Booked", self.agent))
		self.assertEqual(len(result["active"]), 1)

	def test_a_unit_held_for_this_lead_can_be_booked_and_the_hold_clears(self):
		_as("agent")
		holds.hold_unit_for(self.units["G102"], self.lead)
		self.book("G102")
		unit = self.unit("G102")
		self.assertEqual((unit.status, unit.held_by, unit.held_for_lead), ("Booked", None, None))

	def test_a_lapsed_hold_for_another_lead_can_be_booked(self):
		holds.hold_unit_for(self.units["G102"], self.other_lead)
		with patch.object(holds, "now", return_value=holds.add_to_date(holds.now(), hours=49)):
			_as("agent")
			self.book("G102")
		self.assertEqual(self.unit("G102").status, "Booked")

	def test_the_cost_sheet_of_the_unit_is_recorded_and_another_units_is_refused(self):
		_as("agent")
		sheet = self.fake_sheet("G101")
		other = self.fake_sheet("G102")
		with self.assertRaises(frappe.ValidationError):
			self.book("G101", cost_sheet=other)
		self.assertEqual(self.unit("G101").status, "Available")
		deal = frappe.get_doc("Deal", self.book("G101", cost_sheet=sheet)["deal"])
		self.assertEqual(deal.cost_sheet, sheet)

	def fake_sheet(self, number):
		unit = self.unit(number)
		return (
			frappe.get_doc(
				{
					"doctype": "Cost Sheet",
					"unit": unit.name,
					"project": unit.project,
					"unit_number": unit.unit_number,
					"total": 1,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def test_the_price_and_booking_amount_are_needed_and_the_amount_is_not_above_the_price(self):
		_as("agent")
		for extra in ({"price": 0}, {"booking_amount": 0}, {"booking_amount": PRICE + 1}):
			with self.assertRaises(frappe.ValidationError):
				self.book(**extra)
		self.assertEqual(self.unit("G101").status, "Available")

	def test_the_agent_may_book_only_for_a_lead_they_may_write(self):
		_as("agent")
		with self.assertRaises(frappe.PermissionError):
			self.book(lead=self.other_lead)
		self.assertEqual(self.unit("G101").status, "Available")

	def test_only_a_company_admin_or_an_agent_may_call_the_methods(self):
		for role in ("sales_manager", "client", "channel_partner"):
			_as(role)
			with self.assertRaises(frappe.PermissionError):
				self.book()
			with self.assertRaises(frappe.PermissionError):
				bookings.cancel_booking("x", "reason")

	def test_consent_never_blocks_the_booking_and_the_warning_shows(self):
		_as("agent")
		frappe.db.set_value("Lead", self.lead, "consent_status", consent.OPTED_OUT)
		self.book()
		self.assertEqual(self.stage(), "Booking")
		panel = bookings.booking_panel(self.lead)
		self.assertEqual(panel["consent"]["status"], consent.compute_status(self.lead))
		self.assertTrue(panel["consent"]["message"])


class TestRefusedUnits(BookingCase):
	"""SOS-P7-10: a Booked, Sold, Blocked or other lead's held unit can not be booked, and nothing changes."""

	def refused(self, number, text):
		_as("agent")
		stage = self.stage()
		deals = frappe.db.count("Deal", {"unit": self.units[number]})
		with self.assertRaises(frappe.ValidationError) as caught:
			self.book(number)
		self.assertIn(text, str(caught.exception))
		self.assertEqual(self.stage(), stage)
		self.assertEqual(frappe.db.count("Deal", {"unit": self.units[number]}), deals)

	def test_a_booked_unit(self):
		self.book("G101", lead=self.other_lead)
		self.refused("G101", "Booked")

	def test_a_sold_unit(self):
		frappe.db.set_value("Unit", self.units["G101"], "status", "Sold")
		self.refused("G101", "Sold")

	def test_a_blocked_unit(self):
		holds.block_unit(self.units["G101"], "Legal check")
		self.refused("G101", "Blocked")

	def test_a_unit_held_for_another_lead_says_who_and_until_when(self):
		holds.hold_unit_for(self.units["G101"], self.other_lead)
		self.refused("G101", "is held by")

	def test_an_archived_unit(self):
		frappe.db.set_value("Unit", self.units["G101"], "archived", 1)
		self.refused("G101", "archived")


class TestRollback(BookingCase):
	"""SOS-P7-10: a failure leaves nothing half done."""

	def test_a_failure_after_the_unit_and_the_stage_changed_undoes_all_of_it(self):
		_as("agent")
		stage = self.stage()
		with patch.object(partner_registrations, "mark_booked", side_effect=RuntimeError("boom")):
			with self.assertRaises(RuntimeError):
				self.book()
		unit = self.unit("G101")
		self.assertEqual(unit.status, "Available")
		self.assertEqual([r.to_status for r in unit.status_log], ["Available"])
		self.assertEqual(self.stage(), stage)
		self.assertNotIn("Booking", [r.to_stage for r in frappe.get_doc("Lead", self.lead).stage_log])
		self.assertFalse(frappe.db.exists("Deal", {"lead": self.lead}))
		self.book()  # and the booking still works afterwards
		self.assertEqual(self.unit("G101").status, "Booked")


class TestCancel(BookingCase):
	"""SOS-P7-10: cancelling needs a reason, frees the unit, keeps the deal and leaves the stage alone."""

	def test_a_cancellation_frees_the_unit_marks_the_deal_and_leaves_the_stage(self):
		_as("agent")
		deal = self.book()["deal"]
		with self.assertRaises(frappe.ValidationError):
			bookings.cancel_booking(deal, "  ")
		self.assertEqual(self.unit("G101").status, "Booked")
		bookings.cancel_booking(deal, "Buyer changed their mind")
		doc = frappe.get_doc("Deal", deal)
		self.assertEqual(
			(doc.deal_status, doc.cancelled_by, doc.cancellation_reason),
			("Cancelled", self.agent, "Buyer changed their mind"),
		)
		self.assertTrue(doc.cancelled_on)
		unit = self.unit("G101")
		self.assertEqual(unit.status, "Available")
		self.assertIn("Buyer changed their mind", unit.status_log[-1].reason)
		self.assertEqual(unit.status_log[-1].changed_by, self.agent)
		self.assertEqual(self.stage(), "Booking")
		self.book()  # the unit can be booked again

	def test_a_cancelled_booking_is_not_cancelled_twice_or_made_active_again(self):
		_as("agent")
		deal = self.book()["deal"]
		bookings.cancel_booking(deal, "Reason")
		with self.assertRaises(frappe.ValidationError):
			bookings.cancel_booking(deal, "Again")
		doc = frappe.get_doc("Deal", deal)
		doc.deal_status = "Active"
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_a_deal_is_not_cancelled_by_a_plain_save_and_is_never_deleted(self):
		_as("agent")
		deal = frappe.get_doc("Deal", self.book()["deal"])
		deal.deal_status = "Cancelled"
		with self.assertRaises(frappe.PermissionError):
			deal.save(ignore_permissions=True)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Deal", deal.name).delete(ignore_permissions=True)

	def test_an_agent_can_not_cancel_a_booking_of_a_lead_they_may_not_write(self):
		deal = self.book(lead=self.other_lead)["deal"]
		_as("agent")
		with self.assertRaises(frappe.PermissionError):
			bookings.cancel_booking(deal, "Reason")
		self.assertEqual(self.unit("G101").status, "Booked")

	def test_a_company_admin_cancels_any_booking(self):
		deal = self.book(lead=self.other_lead)["deal"]
		bookings.cancel_booking(deal, "Admin decision")
		self.assertEqual(frappe.db.get_value("Deal", deal, "deal_status"), "Cancelled")


class TestPartnerRegistration(BookingCase):
	"""SOS-P7-10: a protected partner registration moves to Booked and the commission split includes the firm."""

	def test_the_registration_becomes_booked_and_the_split_names_the_partner(self):
		firm = self.make_firm()
		registration = self.register(firm, self.lead)
		_as("agent")
		deal = frappe.get_doc("Deal", self.book()["deal"])
		self.assertEqual(frappe.db.get_value("Partner Registration", registration, "status"), "Booked")
		parties = {r.party_type: r for r in deal.splits}
		self.assertEqual(parties["Channel Partner"].partner_firm, firm)
		self.assertEqual(sum(r.percent for r in deal.splits), 100)

	def test_a_lead_with_no_registration_has_no_partner_share(self):
		_as("agent")
		deal = frappe.get_doc("Deal", self.book()["deal"])
		self.assertNotIn("Channel Partner", [r.party_type for r in deal.splits])

	def test_an_expired_registration_is_not_protected_and_earns_no_share(self):
		firm = self.make_firm()
		registration = self.register(firm, self.lead)
		frappe.db.set_value(
			"Partner Registration", registration, "protected_until", add_days(now_datetime(), -1)
		)
		_as("agent")
		deal = frappe.get_doc("Deal", self.book()["deal"])
		self.assertNotIn("Channel Partner", [r.party_type for r in deal.splits])


class TestConcurrentBookings(BookingCase):
	"""SOS-P7-10: two bookings of one unit from two database connections: exactly one succeeds."""

	def test_two_bookings_at_the_same_moment_exactly_one_succeeds(self):
		unit = self.units["G101"]
		leads = [self.lead, self.other_lead]
		site, sites_path = frappe.local.site, frappe.local.sites_path
		frappe.db.commit()  # the other connections read what this test made  # nosemgrep

		def remove():
			frappe.set_user("Administrator")
			deals = frappe.get_all("Deal", filters={"lead": ["in", leads]}, pluck="name")
			for doctype, filters in (
				("Commission Split", {"parent": ["in", deals]}),
				("Version", {"ref_doctype": "Deal", "docname": ["in", deals]}),
				("Deal", {"name": ["in", deals]}),
				("Inventory Status Change", {"parent": ["in", list(self.units.values())]}),
				("Unit", {"project": self.project}),
				("Project Tower", {"project": self.project}),
				("Project", {"name": self.project}),
				("Developer", {"name": "P706 Developer"}),
				("Lead Stage Change", {"parent": ["in", leads]}),
				("Lead Assignment", {"lead": ["in", leads]}),
				("Lead", {"name": ["in", leads]}),
				("Client", {"client_name": ["like", "P706 Buyer %"]}),
			):
				frappe.db.delete(doctype, filters)
			frappe.db.commit()  # nosemgrep

		self.addCleanup(remove)
		start = threading.Barrier(2)
		results = {}

		def attempt(key, lead):
			frappe.init(site, sites_path=sites_path)
			frappe.connect()
			try:
				frappe.set_user(self.admin)
				start.wait(timeout=30)
				try:
					bookings.book(lead, unit, PRICE, AMOUNT)
					frappe.db.commit()  # nosemgrep
					results[key] = "booked"
				except frappe.ValidationError as error:
					frappe.db.rollback()
					results[key] = str(error)
			finally:
				frappe.destroy()

		threads = [threading.Thread(target=attempt, args=(str(i), lead)) for i, lead in enumerate(leads)]
		for thread in threads:
			thread.start()
		for thread in threads:
			thread.join(timeout=60)
		outcomes = sorted(results.values(), key=lambda value: value != "booked")
		self.assertEqual(len(outcomes), 2)
		self.assertEqual(outcomes[0], "booked")
		self.assertIn("Booked", outcomes[1])
		frappe.db.rollback()
		self.assertEqual(frappe.db.count("Deal", {"unit": unit}), 1)
		self.assertEqual(frappe.get_doc("Unit", unit).status, "Booked")
		self.assertEqual(
			sum(1 for lead in leads if frappe.db.get_value("Lead", lead, "stage") == "Booking"), 1
		)
