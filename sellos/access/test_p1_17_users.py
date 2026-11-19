"""SOS-P1-17: a Company Admin invites, edits and deactivates users in the web app."""

from unittest.mock import MagicMock, patch

import frappe
from frappe.core.doctype.user.user import update_password
from frappe.tests import IntegrationTestCase
from frappe.utils.password import check_password

from sellos.access import users
from sellos.access.roles import (
	AGENT,
	CHANNEL_PARTNER,
	CLIENT,
	COMPANY_ADMIN,
	PLATFORM_ADMIN,
	ensure_roles,
)
from sellos.crm import pipeline
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

PASSWORD = "P117#Fresh2026!word"
NEW_EMAIL = "p117_new_agent@example.com"


def _email(key):
	return TEST_USERS[key]["email"]


class UsersCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()
		pipeline.ensure_default_stages()

	def setUp(self):
		frappe.set_user(_email("company_admin"))
		self.addCleanup(frappe.set_user, "Administrator")
		self.sent = []
		self.addCleanup(frappe.db.rollback)

	def invite(self, email=NEW_EMAIL, role=AGENT, mobile="", mail=True, **extra):
		"""Invite with the mail captured. The mail is never sent for real (SOS-P0-13)."""
		with (
			patch.object(users, "mail_ready", return_value=mail),
			patch("frappe.sendmail", side_effect=lambda **kw: self.sent.append(kw)),
		):
			return users.invite_user(email, "P117 New", role, "Agent", mobile, **extra)

	def key_from_mail(self):
		return self.sent[-1]["message"].split("key=")[1].split("'")[0]

	def set_password(self, key, password=PASSWORD):
		"""What the invitation page does with the link. Returns the refusal message, or None."""
		frappe.local.login_manager = MagicMock()
		result = update_password(password, key=key)
		return result if "link" in str(result) else None

	def row(self, email, state=None):
		return next(u for u in (state or users.list_users())["users"] if u["email"] == email)


class TestInvite(UsersCase):
	"""SOS-P1-17: an invited user gets a mail, sets a password from it and signs in."""

	def test_an_invited_user_sets_a_password_from_the_mail_and_signs_in(self):
		mobile = phones.in_mobile(1701)
		result = self.invite(mobile=mobile)
		self.assertTrue(result["invited"])
		self.assertEqual(len(self.sent), 1)
		mail = self.sent[0]
		self.assertEqual(mail["recipients"], [NEW_EMAIL])
		self.assertNotIn("Frappe", mail["message"] + mail["subject"])
		key = self.key_from_mail()
		self.assertTrue(frappe.db.get_value("User", NEW_EMAIL, "enabled"))
		self.assertEqual(self.row(NEW_EMAIL, result)["status"], "Invited")
		self.assertIsNone(self.set_password(key))
		check_password(NEW_EMAIL, PASSWORD)  # raises when the password is wrong
		self.assertIn(AGENT, frappe.get_roles(NEW_EMAIL))
		self.assertEqual(frappe.db.get_value("User", NEW_EMAIL, "mobile_no"), mobile)

	def test_the_invitation_link_works_once(self):
		self.invite()
		key = self.key_from_mail()
		self.assertIsNone(self.set_password(key))
		self.assertIsNotNone(self.set_password(key, "Another#Pass2026!x"))
		with self.assertRaises(frappe.AuthenticationError):
			check_password(NEW_EMAIL, "Another#Pass2026!x")

	def test_without_mail_the_user_is_made_and_the_screen_is_told_not_sent(self):
		result = self.invite(mail=False)
		self.assertFalse(result["invited"])
		self.assertEqual(self.sent, [])
		self.assertTrue(frappe.db.exists("User", NEW_EMAIL))
		with (
			patch.object(users, "mail_ready", return_value=True),
			patch("frappe.sendmail", side_effect=lambda **kw: self.sent.append(kw)),
		):
			self.assertTrue(users.resend_invitation(NEW_EMAIL)["invited"])
		self.assertEqual(len(self.sent), 1)

	def test_the_three_roles_can_be_given_and_the_user_holds_only_that_one(self):
		for index, role in enumerate((COMPANY_ADMIN, AGENT, CHANNEL_PARTNER)):
			email = f"p117_role_{index}@example.com"
			self.invite(email=email, role=role)
			held = {r for r in frappe.get_roles(email) if r.startswith("SellOS")}
			self.assertEqual(held, {role})
			self.assertEqual(self.row(email)["role"], role)

	def test_a_bad_email_a_missing_name_or_a_taken_address_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.invite(email="not an email")
		with self.assertRaises(frappe.ValidationError):
			users.invite_user(NEW_EMAIL, "", AGENT)
		with self.assertRaises(frappe.ValidationError):
			self.invite(email=_email("agent"))

	def test_the_plan_user_limit_is_kept(self):
		with patch.object(users, "_max_users", return_value=len(users._users())):
			with self.assertRaises(frappe.ValidationError):
				self.invite()
		self.assertFalse(frappe.db.exists("User", NEW_EMAIL))


class TestMobileNumber(UsersCase):
	"""SOS-P1-17: +91 and ten digits, and an agent without one can not use click to call."""

	def test_the_number_is_checked_as_plus_91_and_ten_digits(self):
		number = phones.in_mobile(1702)
		self.assertEqual(users.normalize_mobile(number), number)
		self.assertEqual(users.normalize_mobile(number[-10:]), number)
		self.assertEqual(users.normalize_mobile(f"+91 {number[3:8]} {number[8:]}"), number)
		self.assertIsNone(users.normalize_mobile("  "))
		for bad in (
			phones.au_mobile(1),
			phones.ae_mobile(1),
			number[:-1],
			number + "1",
			"+91" + "5" + number[4:],
			"abc",
		):
			with self.subTest(bad=bad), self.assertRaises(frappe.ValidationError):
				users.normalize_mobile(bad)

	def test_an_invite_with_a_foreign_number_makes_no_user(self):
		with self.assertRaises(frappe.ValidationError):
			self.invite(mobile=phones.au_mobile(2))
		self.assertFalse(frappe.db.exists("User", NEW_EMAIL))

	def test_an_agent_with_no_number_is_shown_as_unable_to_use_click_to_call(self):
		self.invite()
		row = self.row(NEW_EMAIL)
		self.assertFalse(row["can_click_to_call"])
		self.assertIn("click to call", row["click_to_call_note"])
		number = phones.in_mobile(1703)
		state = users.save_user(NEW_EMAIL, {"mobile_no": number})
		row = self.row(NEW_EMAIL, state)
		self.assertTrue(row["can_click_to_call"])
		self.assertEqual(row["mobile_no"], number)
		self.assertIsNone(row["click_to_call_note"])
		state = users.save_user(NEW_EMAIL, {"mobile_no": ""})
		self.assertFalse(self.row(NEW_EMAIL, state)["can_click_to_call"])

	def test_two_users_can_not_share_a_number(self):
		number = phones.in_mobile(1704)
		self.invite(mobile=number)
		with self.assertRaises(frappe.ValidationError):
			self.invite(email="p117_other@example.com", mobile=number)
		self.assertFalse(frappe.db.exists("User", "p117_other@example.com"))


class TestDeactivation(UsersCase):
	"""SOS-P1-17: deactivating ends sign in at once and lists the open leads and tasks."""

	def make_agent_with_work(self):
		self.invite()
		client = frappe.get_doc(
			{"doctype": "Client", "client_name": "P117 Buyer", "client_type": "Buyer"}
		).insert()
		open_lead = frappe.get_doc(
			{"doctype": "Lead", "client": client.name, "source": "Website", "assigned_to": NEW_EMAIL}
		).insert()
		lost = frappe.get_doc(
			{
				"doctype": "Lead",
				"client": client.name,
				"source": "Website",
				"assigned_to": NEW_EMAIL,
				"stage": pipeline.CLOSED_LOST,
			}
		).insert()
		frappe.get_doc({"doctype": "Lead", "client": client.name, "source": "Website"}).insert()
		task = frappe.get_doc(
			{
				"doctype": "Lead Task",
				"lead": open_lead.name,
				"title": "P117 call",
				"due_date": "2030-01-01",
				"assigned_to": NEW_EMAIL,
			}
		).insert()
		done = frappe.get_doc(
			{
				"doctype": "Lead Task",
				"lead": open_lead.name,
				"title": "P117 done",
				"due_date": "2030-01-01",
				"assigned_to": NEW_EMAIL,
				"status": "Done",
			}
		).insert()
		return open_lead, lost, task, done

	def test_it_lists_the_open_leads_and_tasks_and_deletes_nothing(self):
		open_lead, lost, task, done = self.make_agent_with_work()
		row = self.row(NEW_EMAIL)
		self.assertEqual((row["open_leads"], row["open_tasks"]), (1, 1))
		# SOS-P1-19: an agent who holds open work is not deactivated until the caller says where it goes.
		result = users.deactivate_user(NEW_EMAIL)
		self.assertTrue(result["needs_handover"])
		# A lead in a closed stage and a task that is done are not open work.
		self.assertEqual([lead["name"] for lead in result["open_leads"]], [open_lead.name])
		self.assertEqual([t["name"] for t in result["open_tasks"]], [task.name])
		self.assertNotIn(lost.name, [lead["name"] for lead in result["open_leads"]])
		self.assertNotIn(done.name, [t["name"] for t in result["open_tasks"]])
		self.assertEqual((result["open_lead_count"], result["open_task_count"]), (1, 1))
		self.assertEqual(self.row(NEW_EMAIL, result)["status"], "Invited")
		self.assertEqual(frappe.db.get_value("Lead", open_lead.name, "assigned_to"), NEW_EMAIL)
		# Told where it goes, the user is deactivated and nothing stays with them. Nothing is deleted.
		with patch.object(frappe.db, "commit"):
			result = users.deactivate_user(NEW_EMAIL, reassign_to=_email("agent"))
		self.assertEqual(self.row(NEW_EMAIL, result)["status"], "Deactivated")
		self.assertEqual((result["open_lead_count"], result["open_task_count"]), (0, 0))
		self.assertEqual(frappe.db.get_value("Lead", open_lead.name, "assigned_to"), _email("agent"))
		self.assertEqual(frappe.db.get_value("Lead Task", task.name, "assigned_to"), _email("agent"))
		self.assertEqual(frappe.db.get_value("Lead", lost.name, "assigned_to"), NEW_EMAIL)
		self.assertTrue(frappe.db.exists("User", NEW_EMAIL))

	def test_sign_in_stops_at_once_and_every_session_ends(self):
		from frappe.core.doctype.user.user import User

		self.invite()
		self.assertIsNone(self.set_password(self.key_from_mail()))
		check_password(NEW_EMAIL, PASSWORD)
		frappe.db.sql(
			"insert into `tabSessions` (user, sid, status, lastupdate, sessiondata)"
			" values (%s, %s, 'Active', now(), '{}')",
			(NEW_EMAIL, "p117sid"),
		)
		self.assertEqual(frappe.db.count("Sessions", {"user": NEW_EMAIL}), 1)
		# Ending a session commits in Frappe. The test keeps its rollback.
		with patch.object(frappe.db, "commit"):
			users.deactivate_user(NEW_EMAIL)
		self.assertEqual(frappe.db.count("Sessions", {"user": NEW_EMAIL}), 0)
		# Frappe refuses a sign in when the account is not enabled (its LoginManager checks this flag).
		self.assertEqual(frappe.db.get_value("User", NEW_EMAIL, "enabled"), 0)
		self.assertEqual(User.find_by_credentials(NEW_EMAIL, PASSWORD).enabled, 0)

	def test_an_unused_invitation_link_stops_working(self):
		self.invite()
		key = self.key_from_mail()
		users.deactivate_user(NEW_EMAIL)
		self.assertIsNotNone(self.set_password(key))
		self.assertFalse(
			frappe.db.exists("__Auth", {"doctype": "User", "name": NEW_EMAIL, "fieldname": "password"})
		)

	def test_it_is_safe_to_run_again_and_a_user_can_be_turned_back_on(self):
		self.invite()
		users.deactivate_user(NEW_EMAIL)
		users.deactivate_user(NEW_EMAIL)
		state = users.reactivate_user(NEW_EMAIL)
		self.assertEqual(self.row(NEW_EMAIL, state)["enabled"], 1)

	def test_you_can_not_deactivate_yourself_or_the_last_company_admin(self):
		with self.assertRaises(frappe.ValidationError):
			users.deactivate_user(_email("company_admin"))
		self.assertTrue(frappe.db.get_value("User", _email("company_admin"), "enabled"))
		# Another admin can not remove the only other one when it is the last active admin.
		self.invite(email="p117_second_admin@example.com", role=COMPANY_ADMIN)
		frappe.set_user("Administrator")
		with patch.object(users, "_enabled_admins", return_value=1):
			with self.assertRaises(frappe.ValidationError):
				users.deactivate_user("p117_second_admin@example.com")


class TestRoleLimits(UsersCase):
	"""SOS-P1-17: only a Company Admin, and nobody can give the Platform Admin role from this screen."""

	def test_the_platform_admin_role_can_not_be_given_by_invite_or_edit(self):
		with self.assertRaises(frappe.PermissionError):
			self.invite(role=PLATFORM_ADMIN)
		self.assertFalse(frappe.db.exists("User", NEW_EMAIL))
		self.invite()
		with self.assertRaises(frappe.PermissionError):
			users.save_user(NEW_EMAIL, {"role": PLATFORM_ADMIN})
		self.assertNotIn(PLATFORM_ADMIN, frappe.get_roles(NEW_EMAIL))
		for role in (CLIENT, "System Manager", "Administrator"):
			with self.subTest(role=role), self.assertRaises(frappe.ValidationError):
				self.invite(email=f"p117_{len(role)}@example.com", role=role)

	def test_a_platform_admin_is_not_listed_and_can_not_be_changed_or_deactivated(self):
		emails = [u["email"] for u in users.list_users()["users"]]
		self.assertNotIn(_email("platform_admin"), emails)
		self.assertIn(_email("agent"), emails)
		self.assertNotIn(_email("client"), emails)
		for call in (
			lambda: users.save_user(_email("platform_admin"), {"first_name": "X"}),
			lambda: users.deactivate_user(_email("platform_admin")),
			lambda: users.reactivate_user(_email("platform_admin")),
			lambda: users.user_open_work(_email("platform_admin")),
			lambda: users.save_user(_email("client"), {"first_name": "X"}),
			lambda: users.deactivate_user("Administrator"),
		):
			with self.assertRaises((frappe.PermissionError, frappe.DoesNotExistError)):
				call()
		self.assertTrue(frappe.db.get_value("User", _email("platform_admin"), "enabled"))

	def test_an_edit_can_change_the_role_but_not_your_own(self):
		self.invite()
		users.save_user(NEW_EMAIL, {"role": COMPANY_ADMIN})
		held = {r for r in frappe.get_roles(NEW_EMAIL) if r.startswith("SellOS")}
		self.assertEqual(held, {COMPANY_ADMIN})
		with self.assertRaises(frappe.ValidationError):
			users.save_user(_email("company_admin"), {"role": AGENT})

	def test_only_a_company_admin_may_call_these_methods(self):
		for who in ("agent", "channel_partner", "client", "platform_admin", "sales_manager", "basic"):
			frappe.set_user(_email(who))
			for method, args in (
				(users.list_users, {}),
				(users.invite_user, {"email": NEW_EMAIL, "first_name": "X", "role": AGENT}),
				(users.save_user, {"email": _email("agent"), "values": {"first_name": "X"}}),
				(users.deactivate_user, {"email": _email("agent")}),
			):
				with self.subTest(who=who, method=method.__name__), self.assertRaises(frappe.PermissionError):
					method(**args)
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			users.list_users()
		self.assertTrue(frappe.db.get_value("User", _email("agent"), "enabled"))


class TestRegressionSeed(UsersCase):
	"""SOS-P1-17: the regression data holds the invited, the no mobile and the deactivated user."""

	def test_the_seeded_users_are_read_back_through_the_production_methods(self):
		from sellos.tests import ui_fixtures

		ui_fixtures._seed_users(_email("company_admin"))
		ui_fixtures._seed_users(_email("company_admin"))  # safe to run again
		state = users.list_users()
		by_status = {u["email"]: u for u in state["users"]}
		new, no_mobile, former = (by_status[email] for email, _name, _seed in ui_fixtures.SEEDED_USERS)
		self.assertEqual(new["status"], "Invited")
		self.assertTrue(new["can_click_to_call"])
		self.assertEqual(no_mobile["status"], "Invited")
		self.assertFalse(no_mobile["can_click_to_call"])
		self.assertEqual((no_mobile["open_leads"], no_mobile["open_tasks"]), (1, 1))  # the former agent's
		self.assertEqual(former["status"], "Deactivated")
		self.assertEqual((former["open_leads"], former["open_tasks"]), (0, 0))  # SOS-P1-19 handed them over
		self.assertEqual(self.sent, [])  # no mail was sent

	def test_the_spec_fixture_gives_a_user_work_and_a_password(self):
		from sellos.tests import ui_fixtures

		self.invite(email="gate_invited_p117@example.com")
		with patch.object(
			frappe.db, "commit"
		):  # the fixture commits for the browser, the test keeps its rollback
			work = ui_fixtures.seed_user_work("gate_invited_p117@example.com")
		self.assertTrue(frappe.db.exists("Lead", work["lead"]))
		self.assertEqual(
			frappe.db.get_value("Lead Task", work["task"], "assigned_to"), "gate_invited_p117@example.com"
		)
