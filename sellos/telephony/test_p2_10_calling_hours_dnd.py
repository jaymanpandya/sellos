"""SOS-P2-10: calling hours are a company setting and a do not call list flags leads (Registered DND)
without ever blocking a call."""

from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.roles import ensure_roles
from sellos.crm import api as crm
from sellos.telephony import call_log, dnd, hours, router
from sellos.telephony.base import ProviderError
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

LANDLINE = f"{phones.in_mobile(3400)[:3]}22{phones.in_mobile(3400)[-8:]}"
MONDAY = (2026, 11, 23)  # a Monday
SUNDAY = (2026, 11, 22)


def at(day, hour, minute=0, second=0):
	return datetime(*day, hour, minute, second, tzinfo=hours.IST)


class TestCallingHours(IntegrationTestCase):
	"""SOS-P2-10: boundary times of the calling hours, and the refusal with the hours in its message."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)
		frappe.set_user(TEST_USERS["company_admin"]["email"])
		hours.save_calling_hours(1, "09:00", "21:00", "Mon,Tue,Wed,Thu,Fri,Sat")

	def test_boundaries(self):
		table = [
			(at(MONDAY, 8, 59, 59), False),
			(at(MONDAY, 9, 0, 0), True),
			(at(MONDAY, 20, 59, 59), True),
			(at(MONDAY, 21, 0, 0), False),
			(at(SUNDAY, 12), False),
		]
		for moment, allowed in table:
			with self.subTest(moment=str(moment)):
				self.assertEqual(hours.is_within(moment), allowed)

	def test_utc_moment_is_read_in_india_time(self):
		utc = datetime(2026, 11, 23, 3, 30, tzinfo=hours.ZoneInfo("UTC"))  # 9:00 in India
		self.assertTrue(hours.is_within(utc))

	def test_refusal_names_the_hours(self):
		with self.assertRaises(ProviderError) as ctx:
			router.route_call(phones.in_mobile(3401), "Service", from_number=LANDLINE, now=at(MONDAY, 21))
		message = str(ctx.exception)
		for text in ("9:00 am", "9:00 pm", "Monday to Saturday", "India time"):
			self.assertIn(text, message)
		route = router.route_call(phones.in_mobile(3401), "Service", from_number=LANDLINE, now=at(MONDAY, 10))
		self.assertEqual(route.series, "022")

	def test_off_by_default_means_any_time(self):
		hours.save_calling_hours(0, "09:00", "21:00", "Mon")
		self.assertTrue(hours.is_within(at(SUNDAY, 3)))

	def test_second_leg_is_not_refused(self):
		route = router.route_call(
			phones.in_mobile(3402), "Service", from_number=LANDLINE, check_hours=False, now=at(SUNDAY, 3)
		)
		self.assertEqual(route.account, "india")

	def test_company_admin_saves_and_reads_back(self):
		saved = hours.save_calling_hours(1, "10:30", "18:00", "Tue,Thu")
		self.assertEqual((saved["start"], saved["end"], saved["days"]), ("10:30", "18:00", ["Tue", "Thu"]))
		self.assertEqual(hours.get_calling_hours()["start"], "10:30")

	def test_bad_settings_are_refused(self):
		for args in ((1, "21:00", "09:00", "Mon"), (1, "", "09:00", "Mon"), (1, "09:00", "21:00", "Funday")):
			with self.subTest(args=args), self.assertRaises(frappe.ValidationError):
				hours.save_calling_hours(*args)

	def test_other_roles_are_refused(self):
		for key in ("agent", "client", "channel_partner"):
			frappe.set_user(TEST_USERS[key]["email"])
			with self.subTest(role=key), self.assertRaises(frappe.PermissionError):
				hours.save_calling_hours(0)


class TestDoNotCallList(IntegrationTestCase):
	"""SOS-P2-10: an imported number gives the lead Registered DND with an amber warning, and the call proceeds."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)
		frappe.set_user(TEST_USERS["company_admin"]["email"])

	def make_lead(self, seed):
		client = crm.save_client(
			values={
				"client_name": f"P210 Buyer {seed}",
				"client_type": "Buyer",
				"phone": phones.in_mobile(seed),
			}
		)
		return crm.save_lead(values={"client": client["name"], "source": "Website"})["lead"]["name"]

	def test_normalise(self):
		number = phones.in_mobile(3410)
		national = number[-10:]
		for value in (
			number,
			f"91{national}",
			national,
			f"0{national}",
			f"{number[:3]} {national[:5]} {national[5:]}",
		):
			self.assertEqual(dnd.normalise(value), number)
		self.assertIsNone(dnd.normalise(national[:-1]))
		self.assertIsNone(dnd.normalise(phones.au_mobile(3410)))

	def test_import_flags_the_listed_lead_only(self):
		listed, other = self.make_lead(3411), self.make_lead(3412)
		result = dnd.import_do_not_call_list(
			f"number\n{phones.in_mobile(3411)}\n{phones.in_mobile(3411)}\nnot a number\n"
		)
		self.assertEqual((result["added"], result["skipped"], result["leads_flagged"]), (1, 1, 1))
		self.assertEqual(frappe.db.get_value("Lead", listed, "consent_status"), "Registered DND")
		self.assertNotEqual(frappe.db.get_value("Lead", other, "consent_status"), "Registered DND")
		again = dnd.import_do_not_call_list(phones.in_mobile(3411))
		self.assertEqual((again["added"], again["already_listed"], again["leads_flagged"]), (0, 1, 0))

	def test_amber_warning_on_the_lead_and_the_queue(self):
		from sellos.crm import consent
		from sellos.telephony.queue import caller_queue

		lead = self.make_lead(3413)
		dnd.import_do_not_call_list(phones.in_mobile(3413))
		self.assertEqual(consent.consent_view(lead)["warning"], "amber")
		row = next(r for r in caller_queue() if r["lead"] == lead)
		self.assertEqual((row["consent_status"], row["consent_warning"]), ("Registered DND", "amber"))

	def test_a_lead_made_after_the_import_is_flagged_at_the_call(self):
		dnd.import_do_not_call_list(phones.in_mobile(3414))
		lead = self.make_lead(3414)
		self.assertNotEqual(frappe.db.get_value("Lead", lead, "consent_status"), "Registered DND")
		self.assertTrue(dnd.apply_to_lead(lead))
		self.assertEqual(frappe.db.get_value("Lead", lead, "consent_status"), "Registered DND")

	def test_a_call_to_a_listed_number_proceeds_with_the_warning_recorded(self):
		lead = self.make_lead(3415)
		dnd.import_do_not_call_list(phones.in_mobile(3415))
		frappe.db.set_single_value("Telephony Settings", "provider", "fake")
		frappe.set_user("Administrator")
		with patch.dict(frappe.local.conf, {"allow_tests": 1}):
			from sellos.telephony.settings import save_telephony_settings

			save_telephony_settings("FAKEOK-P210", "token-for-the-fake", LANDLINE)
			result = call_log.place_logged_call(lead, "Service")
		self.assertFalse(result["check"].refused)
		self.assertTrue(result["log"])
		self.assertEqual(result["check"].status, "Registered DND")
		self.assertEqual(result["check"].warning_level, "amber")
		self.assertEqual(
			frappe.db.get_value("Call Log", result["log"], "consent_check"), result["check"].check
		)

	def test_import_needs_a_valid_number_and_a_company_admin(self):
		with self.assertRaises(frappe.ValidationError):
			dnd.import_do_not_call_list("nothing here")
		frappe.set_user(TEST_USERS["agent"]["email"])
		with self.assertRaises(frappe.PermissionError):
			dnd.import_do_not_call_list(phones.in_mobile(3416))
