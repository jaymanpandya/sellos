"""SOS-INT-1: the Integrations screen's methods. Only a Company Admin may call them; a secret is encrypted and
reads back only as "Saved, ending xxxx"; replacing works; Test connection reports Connected, or Failed with the
provider's plain reason, against fakes. No test reaches a real provider."""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.matrix import MATRIX
from sellos.access.roles import COMPANY_ADMIN, ensure_roles
from sellos.config import integration_checks, integrations
from sellos.testing.users import TEST_USERS, create_test_users

METHODS = ("list_integrations", "save_integration", "check_integration")
ARGS = {
	"list_integrations": {},
	"save_integration": {"provider": "legiscore", "values": {}},
	"check_integration": {"provider": "legiscore"},
}
LEGI_KEY = "FAKEOK-legiscore-0a1b2c3d4e5f"
LEGI_TAIL = "4e5f"
META_TOKEN = "meta-page-token-9f8e7d6c5b4a"
WA_TOKEN = "FAKEOK-whatsapp-7a6b5c4d3e2f"
WA_SECRET = "wa-app-secret-1122334455667788"
WA_VERIFY = "wa-verify-token-99887766554433"


def no_network(*args, **kwargs):
	raise AssertionError("a test reached a real provider")


class IntegrationsCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		for name, value in (("allow_tests", 1),):
			patcher = patch.dict(frappe.local.conf, {name: value})
			patcher.start()
			self.addCleanup(patcher.stop)
		for target in ("requests.get", "requests.request"):
			patcher = patch(target, no_network)
			patcher.start()
			self.addCleanup(patcher.stop)
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.rollback)
		frappe.set_user(TEST_USERS["company_admin"]["email"])

	def card(self, provider):
		return next(c for c in integrations.list_integrations()["providers"] if c["provider"] == provider)

	def field(self, provider, key):
		return next(f for f in self.card(provider)["fields"] if f["key"] == key)


class TestPermissions(IntegrationsCase):
	def test_the_matrix_names_only_a_company_admin(self):
		for method in METHODS:
			self.assertEqual(MATRIX[f"sellos.config.integrations.{method}"], frozenset({COMPANY_ADMIN}))

	def test_no_other_role_and_no_guest_may_call_any_method(self):
		for key, user in TEST_USERS.items():
			if key == "company_admin":
				continue
			for method in METHODS:
				frappe.set_user(user["email"])
				with self.assertRaises(frappe.PermissionError, msg=f"{key} {method}"):
					getattr(integrations, method)(**ARGS[method])
		frappe.set_user("Guest")
		for method in METHODS:
			with self.assertRaises(frappe.PermissionError, msg=f"guest {method}"):
				getattr(integrations, method)(**ARGS[method])

	def test_the_company_admin_may_call_all_three(self):
		for method in METHODS:
			getattr(integrations, method)(**ARGS[method])

	def test_no_method_takes_a_company_or_a_site_so_keys_stay_on_this_site(self):
		for method in METHODS:
			names = getattr(integrations, method).__wrapped__.__code__.co_varnames
			self.assertFalse({"site", "company", "tenant"} & set(names), method)


class TestSecretsAreMasked(IntegrationsCase):
	def test_a_saved_secret_reads_back_as_saved_ending_four_and_replacing_works(self):
		integrations.save_integration("legiscore", {"api_key": LEGI_KEY})
		shown = self.field("legiscore", "api_key")
		self.assertEqual(shown["saved"], f"Saved, ending {LEGI_TAIL}")
		self.assertEqual(shown["value"], "")
		replaced = LEGI_KEY[:-4] + "9z8y"
		integrations.save_integration("legiscore", {"api_key": replaced})
		self.assertEqual(self.field("legiscore", "api_key")["saved"], "Saved, ending 9z8y")
		doc = frappe.get_doc(integrations.STORE)
		self.assertEqual(doc.get_password("legiscore_api_key"), replaced)

	def test_a_blank_secret_keeps_the_saved_one_and_a_short_one_shows_no_tail(self):
		integrations.save_integration("legiscore", {"api_key": LEGI_KEY})
		integrations.save_integration("legiscore", {"api_key": "  "})
		self.assertEqual(self.field("legiscore", "api_key")["saved"], f"Saved, ending {LEGI_TAIL}")
		integrations.save_integration("legiscore", {"api_key": "short"})
		self.assertEqual(self.field("legiscore", "api_key")["saved"], "Saved")

	def test_no_response_log_error_or_export_holds_a_secret(self):
		secrets = (LEGI_KEY, META_TOKEN, WA_TOKEN, WA_SECRET, WA_VERIFY)
		integrations.save_integration("legiscore", {"api_key": LEGI_KEY})
		integrations.save_integration(
			"meta_lead_ads",
			{
				"page_access_token": META_TOKEN,
				"page_id": "123456789",
				"app_id": "5550001",
				"app_secret": "x" * 20,
			},
		)
		integrations.save_integration(
			"whatsapp",
			{
				"access_token": WA_TOKEN,
				"phone_number_id": "1234567890",
				"app_secret": WA_SECRET,
				"verify_token": WA_VERIFY,
			},
		)
		errors = frappe.db.count("Error Log")
		with self.assertNoLogs():
			listed = json.dumps(integrations.list_integrations())
			saved = json.dumps(integrations.save_integration("legiscore", {"api_key": LEGI_KEY}))
			checked = json.dumps(
				[integrations.check_integration(p) for p in ("legiscore", "whatsapp", "meta_lead_ads")]
			)
		# The provider's own answer repeats the token: the message the admin sees must not.
		with (
			patch.dict(frappe.local.conf, {"allow_tests": 0}),
			patch.object(
				integration_checks,
				"http_get",
				return_value=(400, {"error": {"message": f"Invalid token {META_TOKEN} for this page"}}),
			),
		):
			echoed = json.dumps(integrations.check_integration("meta_lead_ads"))
		exported = json.dumps(frappe.get_doc(integrations.STORE).as_dict(), default=str) + json.dumps(
			frappe.get_doc("WhatsApp Settings").as_dict(), default=str
		)
		for secret in secrets:
			for name, text in (
				("list", listed),
				("save", saved),
				("check", checked),
				("echo", echoed),
				("export", exported),
			):
				self.assertNotIn(secret, text, name)
		self.assertIn("***", echoed)
		self.assertEqual(frappe.db.count("Error Log"), errors)
		stored = frappe.db.get_value(
			"Singles", {"doctype": integrations.STORE, "field": "legiscore_api_key"}, "value", order_by=None
		)
		self.assertNotEqual(stored, LEGI_KEY)


class TestCards(IntegrationsCase):
	def test_every_card_and_the_voice_link_are_listed(self):
		listed = integrations.list_integrations()
		self.assertEqual(
			[c["provider"] for c in listed["providers"]],
			["whatsapp", "meta_lead_ads", "email", "docuseal", "legiscore"],
		)
		self.assertEqual(listed["voice"]["path"], "/company/telephony")
		keys = {c["provider"]: [f["key"] for f in c["fields"]] for c in listed["providers"]}
		self.assertEqual(
			keys["whatsapp"], ["access_token", "phone_number_id", "waba_id", "app_secret", "verify_token"]
		)
		self.assertEqual(keys["meta_lead_ads"], ["app_id", "app_secret", "page_access_token", "page_id"])
		self.assertEqual(
			keys["email"], ["host", "port", "user", "password", "from_name", "from_address", "api_key"]
		)
		self.assertEqual(
			keys["docuseal"], ["url", "api_key", "webhook_secret", "signer_name", "signer_email"]
		)
		self.assertEqual(keys["legiscore"], ["api_key"])
		self.assertTrue(
			self.card("whatsapp")["webhook_url"].endswith("sellos.whatsapp.webhook.whatsapp_event")
		)

	def test_the_whatsapp_card_writes_the_record_the_whatsapp_channel_reads(self):
		from sellos.whatsapp import settings as whatsapp

		integrations.save_integration(
			"whatsapp",
			{
				"access_token": WA_TOKEN,
				"phone_number_id": "1234567890",
				"app_secret": WA_SECRET,
				"waba_id": "777888",
			},
		)
		self.assertEqual(whatsapp._keys(), (WA_TOKEN, WA_SECRET))
		self.assertEqual(frappe.db.get_single_value("WhatsApp Settings", "phone_number_id"), "1234567890")
		self.assertEqual(self.field("whatsapp", "waba_id")["value"], "777888")

	def test_the_docuseal_card_reads_and_writes_the_one_record_company_settings_used(self):
		from sellos.inventory import docuseal

		integrations.save_integration(
			"docuseal",
			{
				"url": "https://sign.example.com",
				"api_key": "docuseal-key-0123456789",
				"signer_name": "Int Signer",
				"signer_email": "int.signer@example.com",
			},
		)
		config = docuseal._cfg()
		self.assertEqual(
			(config.url, config.key, config.signer_name),
			("https://sign.example.com", "docuseal-key-0123456789", "Int Signer"),
		)
		self.assertEqual(self.field("docuseal", "api_key")["saved"], "Saved, ending 6789")
		self.assertEqual(self.card("docuseal")["webhook_header"], "X-Webhook-Secret")
		self.assertEqual(docuseal._settings_view()["signer_name"], "Int Signer")  # the old reader sees it too

	def test_values_are_checked_and_an_unknown_field_or_provider_is_refused(self):
		bad = (
			("email", {"port": "99999"}),
			("email", {"from_address": "not an address"}),
			("email", {"host": "bad host!"}),
			("whatsapp", {"phone_number_id": "abc"}),
			("docuseal", {"url": "http://sign.example.com"}),
			("legiscore", {"other": "x"}),
			("legiscore", {"api_key": "k" * 2000}),
			("nothing", {}),
		)
		for provider, values in bad:
			with self.assertRaises(frappe.ValidationError, msg=f"{provider} {values}"):
				integrations.save_integration(provider, values)

	def test_the_email_card_saves_smtp_details(self):
		integrations.save_integration(
			"email",
			{
				"host": "smtp.example.com",
				"port": "587",
				"user": "mailer",
				"password": "smtp-password-5566",
				"from_name": "Int Realty",
				"from_address": "hello@example.com",
			},
		)
		card = self.card("email")
		self.assertEqual(self.field("email", "host")["value"], "smtp.example.com")
		self.assertEqual(self.field("email", "port")["value"], "587")
		self.assertEqual(self.field("email", "password")["saved"], "Saved, ending 5566")
		self.assertEqual(card["status"], "Not tested")


class TestStatusAndConnection(IntegrationsCase):
	def test_a_card_with_no_details_is_not_set_and_the_check_calls_no_one(self):
		self.assertEqual(self.card("legiscore")["status"], "Not set")
		result = integrations.check_integration("legiscore")
		self.assertFalse(result["ok"])
		self.assertEqual(result["card"]["status"], "Not set")

	def test_test_connection_reports_connected_against_a_fake_provider(self):
		integrations.save_integration("legiscore", {"api_key": LEGI_KEY})
		self.assertEqual(self.card("legiscore")["status"], "Not tested")
		result = integrations.check_integration("legiscore")
		self.assertTrue(result["ok"])
		self.assertEqual(result["card"]["status"], "Connected")
		self.assertEqual(self.card("legiscore")["status"], "Connected")

	def test_test_connection_reports_failed_with_the_plain_reason(self):
		integrations.save_integration("legiscore", {"api_key": "FAKEBAD-key-0123456789"})
		result = integrations.check_integration("legiscore")
		self.assertFalse(result["ok"])
		self.assertIn("refused", result["message"])
		self.assertEqual(result["card"]["status"], "Failed")
		self.assertEqual(result["card"]["reason"], result["message"])
		integrations.save_integration("legiscore", {"api_key": "FAKEDOWN-key-0123456789"})
		down = integrations.check_integration("legiscore")
		self.assertIn("could not be reached", down["message"])

	def test_changing_a_value_after_a_test_returns_the_card_to_not_tested(self):
		integrations.save_integration("legiscore", {"api_key": LEGI_KEY})
		integrations.check_integration("legiscore")
		integrations.save_integration("legiscore", {"api_key": LEGI_KEY[:-4] + "0000"})
		self.assertEqual(self.card("legiscore")["status"], "Not tested")

	def test_the_fake_keys_are_refused_on_a_site_that_does_not_allow_tests(self):
		integrations.save_integration("legiscore", {"api_key": LEGI_KEY})
		with (
			patch.dict(frappe.local.conf, {"allow_tests": 0}),
			patch.object(integration_checks, "http_get", return_value=(401, {})),
		):
			result = integrations.check_integration("legiscore")
		self.assertFalse(result["ok"])
		self.assertEqual(result["message"], "LegiScore refused this API key.")


class TestAdapters(IntegrationsCase):
	def run_check(self, provider, values, answer):
		integrations.save_integration(provider, values)
		with (
			patch.dict(frappe.local.conf, {"allow_tests": 0}),
			patch.object(integration_checks, "http_get", return_value=answer) as get,
		):
			return integrations.check_integration(provider), get

	def test_meta_lead_ads_connected_and_refused(self):
		values = {"page_access_token": META_TOKEN, "page_id": "123456789"}
		ok, get = self.run_check("meta_lead_ads", values, (200, {"id": "123456789", "name": "Page"}))
		self.assertTrue(ok["ok"])
		url, headers = get.call_args.args[0], get.call_args.args[1]
		self.assertNotIn(META_TOKEN, url)  # the token goes in a header, never the address
		self.assertEqual(headers["Authorization"], f"Bearer {META_TOKEN}")
		refused, _get = self.run_check("meta_lead_ads", values, (401, {}))
		self.assertFalse(refused["ok"])
		self.assertIn("refused this page access token", refused["message"])
		reason, _get = self.run_check(
			"meta_lead_ads", values, (400, {"error": {"message": "Unsupported get request."}})
		)
		self.assertEqual(reason["message"], "Unsupported get request.")

	def test_legiscore_with_its_own_key_uses_the_read_only_balance_call(self):
		allowed = patch.dict(frappe.local.conf, {"allow_tests": 0})
		integrations.save_integration("legiscore", {"api_key": "lsk_real_shape_0123456789"})
		with allowed, patch.object(integration_checks, "http_get", return_value=(200, {"data": {}})) as get:
			result = integrations.check_integration("legiscore")
		self.assertTrue(result["ok"])
		self.assertTrue(get.call_args.args[0].endswith("/search/credits"))

	def test_whatsapp_reports_the_providers_reason(self):
		from sellos.whatsapp.base import ProviderError

		integrations.save_integration(
			"whatsapp", {"access_token": "wa-real-shape-token-0123456789", "phone_number_id": "1234567890"}
		)
		with (
			patch.dict(frappe.local.conf, {"allow_tests": 0}),
			patch(
				"sellos.whatsapp.meta.MetaCloudProvider.test_connection",
				side_effect=ProviderError(
					"WhatsApp refused this access token. Check the token and the number ID."
				),
			),
		):
			result = integrations.check_integration("whatsapp")
		self.assertFalse(result["ok"])
		self.assertIn("refused this access token", result["message"])
		self.assertEqual(result["card"]["status"], "Failed")

	def test_docuseal_is_checked_against_a_fake_docuseal_server(self):
		from sellos.tests.fake_docuseal import KEY, FakeDocuSeal

		fake = FakeDocuSeal().start()
		self.addCleanup(fake.stop)
		with patch("requests.request", wraps=__import__("requests").sessions.Session().request):
			integrations.save_integration("docuseal", {"url": fake.url, "api_key": KEY})
			good = integrations.check_integration("docuseal")
			integrations.save_integration("docuseal", {"api_key": KEY + "-wrong"})
			bad = integrations.check_integration("docuseal")
		self.assertTrue(good["ok"], good["message"])
		self.assertFalse(bad["ok"])
		self.assertIn("refused", bad["message"])
		self.assertNotIn(KEY, json.dumps(bad))

	def test_email_logs_in_and_closes_and_reports_a_refused_login(self):
		import smtplib

		calls = []
		refuse = []

		class FakeServer:
			def __init__(self, host, port, **kwargs):
				calls.append(("connect", host, port))

			def ehlo(self):
				calls.append("ehlo")

			def has_extn(self, name):
				return False

			def login(self, user, password):
				if refuse:
					raise smtplib.SMTPAuthenticationError(535, b"bad")
				calls.append(("login", user))

			def noop(self):
				calls.append("noop")

			def quit(self):
				calls.append("quit")

		values = {
			"host": "localhost",
			"port": "2525",
			"user": "mailer",
			"password": "smtp-password-5566",
			"from_address": "hello@example.com",
		}
		integrations.save_integration("email", values)
		with patch("smtplib.SMTP", FakeServer):
			ok = integrations.check_integration("email")
			refuse.append(True)
			refused = integrations.check_integration("email")
		self.assertTrue(ok["ok"], ok["message"])
		self.assertIn(("login", "mailer"), calls)
		self.assertIn("quit", calls)
		self.assertFalse(refused["ok"])
		self.assertIn("refused this user and password", refused["message"])

	def test_email_with_only_an_api_key_says_it_cannot_be_tested(self):
		integrations.save_integration(
			"email", {"api_key": "mail-api-key-0123456789", "from_address": "a@example.com"}
		)
		result = integrations.check_integration("email")
		self.assertFalse(result["ok"])
		self.assertIn("SMTP host", result["message"])
