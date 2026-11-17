"""SOS-P2-01: Telephony Settings. The Plivo India account is saved encrypted, no API returns the keys,
the test connection button reports success or the error against the fake provider, and only a Company
Admin may use it."""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.matrix import MATRIX
from sellos.access.roles import COMPANY_ADMIN, ensure_roles
from sellos.telephony import provider, settings
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

METHODS = ("get_telephony_settings", "save_telephony_settings", "check_connection")
GOOD_ID = "FAKEOK0A1B2C3D4E5F6"
GOOD_TOKEN = "tokenvalue7f3a9c1e5b2d4f68"
BAD_ID = "WRONG-ID-1"
DOWN_ID = "FAKEDOWN-1"
EIGHT = phones.in_mobile(2201)[-8:]
LANDLINE = f"022 {EIGHT}"
COUNTRY = phones.in_mobile(2201)[:3]
STORED = f"{COUNTRY}22{EIGHT}"
OTHER = phones.in_mobile(2202)[-8:]


class TelephonyCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		patcher = patch.dict(frappe.local.conf, {"allow_tests": 1})
		patcher.start()
		self.addCleanup(patcher.stop)
		frappe.db.set_single_value(settings.DOCTYPE, "provider", "fake")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)

	def as_role(self, key):
		frappe.set_user(TEST_USERS[key]["email"])

	def save(self, **values):
		self.as_role("company_admin")
		return settings.save_telephony_settings(**values)


class TestSettings(TelephonyCase):
	def test_the_india_account_is_saved_and_read_back(self):
		state = self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		self.assertEqual(state["phone_number"], STORED)
		self.assertTrue(state["auth_id_set"])
		self.assertTrue(state["auth_token_set"])
		self.assertTrue(state["configured"])
		doc = frappe.get_doc(settings.DOCTYPE)
		self.assertEqual(doc.get_password("auth_id"), GOOD_ID)
		self.assertEqual(doc.get_password("auth_token"), GOOD_TOKEN)

	def test_the_keys_are_stored_encrypted(self):
		self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		rows = frappe.db.sql(
			"select `fieldname`, `password`, `encrypted` from `__Auth` where doctype=%s and name=%s",
			(settings.DOCTYPE, settings.DOCTYPE),
			as_dict=True,
		)
		self.assertEqual({row.fieldname for row in rows}, {"auth_id", "auth_token"})
		for row in rows:
			self.assertEqual(row.encrypted, 1)
			self.assertNotIn(row.password, (GOOD_ID, GOOD_TOKEN))
			self.assertNotIn(GOOD_ID, row.password)
			self.assertNotIn(GOOD_TOKEN, row.password)
		singles = frappe.db.sql(
			"select `field`, `value` from `tabSingles` where doctype=%s", settings.DOCTYPE, as_dict=True
		)
		self.assertIn("phone_number", {row.field for row in singles})
		for row in singles:
			self.assertNotIn(GOOD_ID, str(row.value))
			self.assertNotIn(GOOD_TOKEN, str(row.value))

	def test_a_blank_key_keeps_the_saved_one(self):
		self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		state = self.save(auth_id="", auth_token="  ", phone_number=f"{COUNTRY} 22 {OTHER}")
		self.assertEqual(state["phone_number"], f"{COUNTRY}22{OTHER}")
		doc = frappe.get_doc(settings.DOCTYPE)
		self.assertEqual(doc.get_password("auth_id"), GOOD_ID)
		self.assertEqual(doc.get_password("auth_token"), GOOD_TOKEN)

	def test_a_number_that_is_not_a_022_number_is_refused(self):
		for bad in ("022 123", f"011 {EIGHT}", f"+1 415 {EIGHT[:7]}", "abc"):
			with self.assertRaises(frappe.ValidationError, msg=bad):
				self.save(phone_number=bad)

	def test_the_022_number_is_accepted_in_every_usual_form(self):
		for value in (
			f"022{EIGHT}",
			STORED,
			f"91 22 {EIGHT[:4]} {EIGHT[4:]}",
			f"(022) {EIGHT[:4]}-{EIGHT[4:]}",
		):
			self.assertEqual(settings.normalise_landline(value), STORED, value)

	def test_there_is_one_account_only(self):
		meta = frappe.get_meta(settings.DOCTYPE)
		self.assertTrue(meta.issingle)
		self.assertEqual(
			[f.fieldname for f in meta.fields], ["auth_id", "auth_token", "phone_number", "provider"]
		)
		self.assertEqual({meta.get_field(n).fieldtype for n in ("auth_id", "auth_token")}, {"Password"})
		self.assertEqual((meta.get_field("provider").hidden, meta.get_field("provider").read_only), (1, 1))
		self.assertNotIn(
			"provider", settings.get_telephony_settings() if frappe.session.user != "Guest" else {}
		)


class TestKeysNeverLeave(TelephonyCase):
	def assert_no_keys(self, payload, where):
		text = json.dumps(payload, default=str)
		self.assertNotIn(GOOD_ID, text, where)
		self.assertNotIn(GOOD_TOKEN, text, where)

	def test_no_settings_api_returns_a_key(self):
		saved = self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		self.assert_no_keys(saved, "save")
		self.assertEqual(set(saved), {"auth_id_set", "auth_token_set", "phone_number", "configured"})
		self.assert_no_keys(settings.get_telephony_settings(), "get")
		self.assert_no_keys(settings.check_connection(), "check")

	def test_the_generic_document_apis_return_no_key(self):
		self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		from frappe.client import get, get_value

		frappe.set_user("Administrator")
		self.assert_no_keys(get(settings.DOCTYPE), "frappe.client.get")
		self.assert_no_keys(get_value(settings.DOCTYPE, ["auth_id", "auth_token"]), "get_value")
		frappe.local.response = frappe._dict()
		from frappe.desk.form import load

		load.getdoc(settings.DOCTYPE, settings.DOCTYPE)
		self.assert_no_keys(frappe.response.get("docs"), "getdoc")

	def test_a_company_admin_can_not_read_the_document_directly(self):
		self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		from frappe.client import get

		self.as_role("company_admin")
		with self.assertRaises(frappe.PermissionError):
			get(settings.DOCTYPE)

	def test_the_change_history_holds_no_key(self):
		self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		versions = frappe.get_all("Version", filters={"ref_doctype": settings.DOCTYPE}, fields=["data"])
		self.assert_no_keys([v.data for v in versions], "version")


class TestConnection(TelephonyCase):
	def test_success_against_the_fake_provider(self):
		self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		result = settings.check_connection()
		self.assertTrue(result["ok"])
		self.assertIn("Connected", result["message"])

	def test_the_provider_refusing_the_keys_is_reported(self):
		self.save(auth_id=BAD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		result = settings.check_connection()
		self.assertFalse(result["ok"])
		self.assertIn("refused", result["message"])
		self.assertNotIn(BAD_ID, result["message"])

	def test_an_unreachable_provider_is_reported(self):
		self.save(auth_id=DOWN_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		result = settings.check_connection()
		self.assertFalse(result["ok"])
		self.assertIn("could not be reached", result["message"])

	def test_no_keys_saved_asks_for_them(self):
		self.as_role("company_admin")
		result = settings.check_connection()
		self.assertFalse(result["ok"])
		self.assertIn("Save the auth ID", result["message"])

	def test_a_key_in_a_provider_message_is_hidden(self):
		self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)

		class Leaky(provider.TelephonyProvider):
			def test_connection(self):
				raise provider.ProviderError(f"bad {self.auth_id} and {self.auth_token}")

		with patch.dict(provider.PROVIDERS, {"fake": Leaky}):
			result = settings.check_connection()
		self.assertFalse(result["ok"])
		self.assertNotIn(GOOD_ID, result["message"])
		self.assertNotIn(GOOD_TOKEN, result["message"])

	def test_an_unexpected_failure_gives_a_plain_message(self):
		self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)

		class Broken(provider.TelephonyProvider):
			def test_connection(self):
				raise RuntimeError(f"boom {self.auth_token}")

		with patch.dict(provider.PROVIDERS, {"fake": Broken}):
			result = settings.check_connection()
		self.assertEqual(result, {"ok": False, "message": "The connection test failed. Try again."})

	def test_a_site_with_no_provider_set_is_not_told_it_works(self):
		self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		frappe.db.set_single_value(settings.DOCTYPE, "provider", "")
		result = settings.check_connection()
		self.assertFalse(result["ok"])
		self.assertIn("not available", result["message"])
		self.assertNotIn("Frappe", result["message"])

	def test_the_fake_provider_is_refused_on_a_site_that_does_not_allow_tests(self):
		self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		with patch.dict(frappe.local.conf, {"allow_tests": 0}):
			result = settings.check_connection()
		self.assertFalse(result["ok"])
		self.assertIn("not available", result["message"])


class TestWhoMayUseIt(TelephonyCase):
	def test_only_a_company_admin_may_call_each_method(self):
		for name in METHODS:
			self.assertEqual(MATRIX[f"sellos.telephony.settings.{name}"], frozenset({COMPANY_ADMIN}), name)

	def test_every_other_role_is_blocked_from_every_method(self):
		self.save(auth_id=GOOD_ID, auth_token=GOOD_TOKEN, phone_number=LANDLINE)
		blocked = {"agent", "channel_partner", "client", "platform_admin", "sales_manager", "basic"}
		for key in sorted(blocked):
			self.as_role(key)
			for name in METHODS:
				with self.assertRaises(frappe.PermissionError, msg=f"{key} {name}"):
					getattr(settings, name)()


class TestRegressionSeed(TelephonyCase):
	def test_the_seed_saves_the_account_through_the_api_and_the_fake_provider_accepts_it(self):
		from sellos.tests import ui_fixtures

		with patch.object(frappe.db, "commit"):
			ui_fixtures._seed_telephony(TEST_USERS["company_admin"]["email"])
			ui_fixtures._seed_telephony(TEST_USERS["company_admin"]["email"])  # safe to run again
		self.assertEqual(frappe.db.get_single_value(settings.DOCTYPE, "provider"), "fake")
		self.as_role("company_admin")
		state = settings.get_telephony_settings()
		self.assertTrue(state["configured"])
		self.assertEqual(
			state["phone_number"], COUNTRY + "22" + ui_fixtures.landline_022(ui_fixtures.TELEPHONY_SEED)[-8:]
		)
		self.assertTrue(settings.check_connection()["ok"])
