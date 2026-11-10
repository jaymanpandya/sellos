import base64
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access.roles import AGENT, COMPANY_ADMIN, ensure_roles
from sellos.config import setup_wizard as wizard
from sellos.testing.users import TEST_USERS, create_test_users

# A real 1 pixel PNG.
PNG = base64.b64encode(
	bytes.fromhex(
		"89504e470d0a1a0a0000000d4948445200000001000000010806000000"
		"1f15c4890000000d49444154789c6360f8ffff3f0005fe02fea7d6e3250000000049454e44ae426082"
	)
).decode()


def as_admin():
	frappe.set_user(TEST_USERS["company_admin"]["email"])


class TestSetupWizard(IntegrationTestCase):
	"""SOS-P1-03: the setup wizard collects four areas, can be resumed, and its branding is read back."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		as_admin()
		# Start every test from a wizard that has not been started.
		settings = frappe.get_doc("SellOS Settings")
		settings.update({"setup_steps_done": "", "setup_complete": 0, "brand_color": "", "logo": ""})
		settings.save(ignore_permissions=True)
		for name in frappe.get_all(wizard.STAGE, pluck="name"):
			frappe.delete_doc(wizard.STAGE, name, ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")

	def complete(self):
		wizard.save_profile({"company_name": "Wizard Realty", "city": "Pune"})
		wizard.save_branding("#123abc", PNG)
		wizard.save_stages(wizard.DEFAULT_STAGES)
		# The class shares one transaction, so each run adds its own person.
		self.agent = f"p103_agent_{frappe.generate_hash(length=6).lower()}@example.com"
		wizard.add_user(self.agent, "Wizard", AGENT, "Agent")
		return wizard.finish_setup()

	def test_a_fresh_company_starts_at_the_first_step_with_default_stages(self):
		state = wizard.get_setup_state()
		self.assertFalse(state["complete"])
		self.assertEqual(state["next_step"], "profile")
		self.assertEqual(state["steps_done"], [])
		self.assertEqual([s["stage_name"] for s in state["stages"]][:2], ["New", "Contacted"])
		self.assertFalse(state["stages_saved"])

	def test_the_wizard_collects_all_four_areas_and_the_result_is_read_back(self):
		state = self.complete()
		self.assertTrue(state["complete"])
		self.assertEqual(state["steps_done"], wizard.STEPS)
		settings = frappe.get_doc("SellOS Settings")
		self.assertEqual(settings.company_name, "Wizard Realty")
		self.assertEqual(settings.city, "Pune")
		self.assertEqual(settings.brand_color, "#123abc")
		self.assertTrue(settings.logo.startswith("/files/company-logo"))
		self.assertEqual(
			frappe.get_all(wizard.STAGE, pluck="name", order_by="position asc"),
			[s["stage_name"] for s in wizard.DEFAULT_STAGES],
		)
		self.assertEqual(frappe.db.get_value(wizard.STAGE, "Booked", "stage_type"), "Won")
		self.assertEqual(frappe.get_roles(self.agent).count(AGENT), 1)
		self.assertTrue(wizard.is_setup_complete())

	def test_the_branding_reaches_the_app_boot_data(self):
		from sellos.spa import get_company_branding

		self.complete()
		frappe.clear_document_cache("SellOS Settings", "SellOS Settings")
		branding = get_company_branding()
		self.assertEqual(branding["brand_color"], "#123abc")
		self.assertEqual(branding["name"], "Wizard Realty")
		self.assertTrue(branding["logo"])

	def test_it_can_be_resumed_where_the_admin_left_it(self):
		wizard.save_profile({"company_name": "Half Done Realty"})
		wizard.save_branding("#222222")
		# Leave, come back: a new call reads what was saved and opens the next step.
		state = wizard.get_setup_state()
		self.assertEqual(state["steps_done"], ["profile", "branding"])
		self.assertEqual(state["next_step"], "stages")
		self.assertEqual(state["profile"]["company_name"], "Half Done Realty")
		self.assertEqual(state["branding"]["brand_color"], "#222222")
		self.assertFalse(state["complete"])

	def test_it_cannot_finish_with_a_required_step_missing(self):
		wizard.save_profile({"company_name": "Early Realty"})
		with self.assertRaises(frappe.ValidationError):
			wizard.finish_setup()
		self.assertFalse(wizard.is_setup_complete())

	def test_a_step_can_be_saved_again(self):
		wizard.save_stages(wizard.DEFAULT_STAGES)
		state = wizard.save_stages(
			[
				{"stage_name": "Enquiry", "stage_type": "Open"},
				{"stage_name": "Booked", "stage_type": "Won"},
				{"stage_name": "Lost", "stage_type": "Lost"},
			]
		)
		self.assertEqual([s["stage_name"] for s in state["stages"]], ["Enquiry", "Booked", "Lost"])

	def test_bad_input_is_refused_with_a_clear_message(self):
		bad_stages = [
			[{"stage_name": "Only", "stage_type": "Won"}],
			[{"stage_name": "A", "stage_type": "Open"}, {"stage_name": "B", "stage_type": "Open"}],
			[{"stage_name": "A", "stage_type": "Won"}, {"stage_name": "a", "stage_type": "Lost"}],
		]
		for stages in bad_stages:
			with self.subTest(stages=stages), self.assertRaises(frappe.ValidationError):
				wizard.save_stages(stages)
		with self.assertRaises(frappe.ValidationError):
			wizard.save_profile({"company_name": " "})
		with self.assertRaises(frappe.ValidationError):
			wizard.save_profile({"company_name": "X", "contact_email": "not an email"})
		with self.assertRaises(frappe.ValidationError):
			wizard.save_branding("green")
		with self.assertRaises(frappe.ValidationError):
			wizard.save_branding("#123abc", base64.b64encode(b"<svg onload=alert(1)>").decode())
		with self.assertRaises(frappe.ValidationError):
			wizard.save_branding(
				"#123abc", base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 2_000_000).decode()
			)

	def test_users_get_only_the_roles_a_company_admin_may_give(self):
		self.second = f"p103_admin_{frappe.generate_hash(length=6).lower()}@example.com"
		with self.assertRaises(frappe.ValidationError):
			wizard.add_user("p103_boss@example.com", "Boss", "SellOS Platform Admin")
		wizard.add_user(self.second, "Second", COMPANY_ADMIN)
		self.assertIn(COMPANY_ADMIN, frappe.get_roles(self.second))
		with self.assertRaises(frappe.ValidationError):  # the address is taken
			wizard.add_user(self.second, "Again", AGENT)

	def test_the_plan_limit_on_users_is_kept(self):
		with patch.object(wizard, "_max_users", return_value=len(wizard._users())):
			with self.assertRaises(frappe.ValidationError):
				wizard.add_user("p103_over@example.com", "Over", AGENT)
		self.assertFalse(frappe.db.exists("User", "p103_over@example.com"))

	def test_only_a_company_admin_may_use_it(self):
		for who in ("agent", "client", "channel_partner", "platform_admin", "basic"):
			frappe.set_user(TEST_USERS[who]["email"])
			with self.subTest(who=who), self.assertRaises(frappe.PermissionError):
				wizard.get_setup_state()
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			wizard.save_profile({"company_name": "Nope"})
