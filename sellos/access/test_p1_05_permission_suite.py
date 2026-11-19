# SOS-P1-05 the permission test suite: every whitelisted sellos method is called as every role, as a
# user from another company and as a guest, and no call returns another company's data.
#
# "A user from another company" has no account on this company's site (every company is its own site
# and database, SOS-P0-06L), so on this site that person is a signed-in user who holds no role: the
# `basic` test user. A guest is the signed-out user.
#
# A method that is added with no matrix entry, or with no entry in SAMPLE_CALLS below, fails the build,
# and so does a sellos method that is whitelisted with no declaration (a deliberately open method).
import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from sellos.access import support
from sellos.access.matrix import MATRIX
from sellos.access.registry import (
	declared_methods,
	is_refused,
	load_declared_modules,
	undeclared_whitelisted_methods,
)
from sellos.access.roles import ROLES, ensure_roles
from sellos.access.test_permission_matrix import import_all_sellos_modules, matrix_problems
from sellos.crm import notifications
from sellos.crm.pipeline import DEFAULT_STAGES
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

SECRET_NAME = "P105 Secret Buyer"
SECRET_PHONE = phones.in_mobile(105)
ACTIVITY_NOTE = "p105-secret-activity-note"
ADMIN = "company_admin"

# who -> the key of the test user. "outsider" is a signed-in user from another company. "guest" is signed out.
WHO = {
	"platform_admin": "platform_admin",
	"company_admin": "company_admin",
	"agent": "agent",
	"client": "client",
	"channel_partner": "channel_partner",
	"sales_manager": "sales_manager",
	"outsider": "basic",
	"guest": None,
}
ROLE_KEYS = {
	"SellOS Platform Admin": "platform_admin",
	"SellOS Company Admin": "company_admin",
	"SellOS Agent": "agent",
	"SellOS Client": "client",
	"SellOS Channel Partner": "channel_partner",
	"SellOS Sales Manager": "sales_manager",
}

# Arguments for every method in the matrix. `{client}` and `{lead}` are filled in with the records the
# test makes. Each one aims at the company's own record, which only the Company Admin may open.
SAMPLE_CALLS = {
	"sellos.crm.api.list_clients": {},
	"sellos.crm.api.find_duplicates": {"phone": SECRET_PHONE},
	"sellos.crm.api.merge_clients": {"keep": "{client}", "merge": "{client_other}"},
	"sellos.crm.api.save_client": {"name": "{client}", "values": {"city": "Pune"}},
	"sellos.crm.api.list_leads": {},
	"sellos.crm.api.get_board": {},
	"sellos.crm.api.lead_filter_options": {},
	"sellos.crm.api.list_lead_sources": {},
	"sellos.crm.api.save_lead_source": {"name": "{spare_source}", "values": {"enabled": 0}},
	"sellos.crm.api.delete_lead_source": {"name": "{spare_source}"},
	"sellos.crm.api.list_stages": {},
	"sellos.crm.api.move_lead_stage": {"lead": "{lead}", "stage": "Contacted"},
	# SOS-P1-21: Wrong number needs no follow up, so the call is one write.
	"sellos.crm.api.list_call_outcomes": {},
	"sellos.crm.api.save_call_outcome": {"name": "{spare_outcome}", "values": {"enabled": 0}},
	"sellos.crm.api.delete_call_outcome": {"name": "{spare_outcome}"},
	"sellos.crm.api.list_lost_reasons": {},
	"sellos.crm.api.save_lost_reason": {"name": "{spare_reason}", "values": {"enabled": 0}},
	"sellos.crm.api.delete_lost_reason": {"name": "{spare_reason}"},
	"sellos.crm.api.log_call": {"lead": "{lead}", "outcome": "Wrong number", "notes": "p121 call"},
	# SOS-P1-18: the lead goes to the test agent, who is in no team.
	"sellos.crm.api.reassign_lead": {"lead": "{lead}", "assigned_to": "{agent}"},
	# SOS-P1-19: a bulk move of the one lead, the agents to pick from, the rules and the default team.
	"sellos.crm.api.bulk_reassign_leads": {"leads": "{lead_list}", "assigned_to": "{agent}"},
	"sellos.crm.api.reassign_options": {},
	"sellos.crm.api.list_assignment_rules": {},
	"sellos.crm.api.save_assignment_rule": {"name": "{spare_rule}", "values": {"priority": 5}},
	"sellos.crm.api.delete_assignment_rule": {"name": "{spare_rule}"},
	"sellos.crm.api.set_default_team": {"team": "{rule_team}"},
	"sellos.crm.api.save_lead": {"name": "{lead}", "values": {"notes": "p105 edit"}},
	"sellos.crm.api.get_lead": {"name": "{lead}"},
	"sellos.crm.api.add_activity": {"lead": "{lead}", "activity_type": "Note", "notes": "p105 added"},
	"sellos.crm.api.save_task": {
		"values": {"lead": "{lead}", "title": "p105 task", "due_date": "2030-01-01"}
	},
	"sellos.crm.api.save_site_visit": {
		"values": {"lead": "{lead}", "project_name": "P105 Tower", "visit_datetime": "2030-01-01 10:00:00"}
	},
	# SOS-P1-25: the calendar and the list read what the caller may see. The visit is the test's own.
	"sellos.crm.api.site_visit_calendar": {"view": "week", "date": "2030-01-01"},
	"sellos.crm.api.tomorrows_site_visits": {},
	"sellos.crm.api.confirm_site_visit": {"name": "{visit}", "confirmation_status": "Confirmed"},
	"sellos.crm.api.complete_site_visit": {"name": "{visit}", "outcome": "Liked it"},
	"sellos.crm.api.site_visit_options": {},
	"sellos.crm.api.set_archived": {"doctype": "Lead", "name": "{lead}", "archived": 0},
	# SOS-P1-22: a follow up made for the test, completed with a note. The setting is the Company Admin's.
	"sellos.crm.api.complete_follow_up": {"name": "{task}", "notes": "p122 done"},
	"sellos.crm.api.list_follow_ups": {},
	"sellos.crm.api.get_follow_up_settings": {},
	"sellos.crm.api.save_follow_up_settings": {"untouched_days": 3},
	# SOS-P1-23: a user's own notifications. Marking all read touches only the caller's.
	"sellos.crm.api.list_notifications": {},
	"sellos.crm.api.mark_notification_read": {"name": "{notification}"},
	"sellos.crm.api.mark_all_notifications_read": {},
	"sellos.crm.api.record_consent": {
		"lead": "{lead}",
		"basis": "Inquiry",
		"evidence_link": "https://example.com/p108-evidence",
	},
	"sellos.crm.api.record_opt_out": {"lead": "{lead}", "source": "Phone call"},
	"sellos.crm.api.record_dnd_result": {"lead": "{lead}", "registered": 1},
	"sellos.access.support.list_support_users": {},
	"sellos.access.support.grant_support_access": {
		"support_user": "{support_user}",
		"duration_minutes": 60,
		"reason": "p105 check",
	},
	"sellos.access.support.revoke_support_access": {"grant": "{grant}"},
	"sellos.access.support.list_support_grants": {},
	"sellos.access.support.support_access_log": {"grant": "{grant}"},
	"sellos.config.setup_wizard.get_setup_state": {},
	"sellos.config.setup_wizard.save_profile": {"values": {"company_name": "P105 Realty"}},
	"sellos.config.setup_wizard.save_branding": {"brand_color": "#0f4c35"},
	# SOS-P1-07: a stage with leads is never deleted, and the test makes a lead, so the call keeps the
	# eleven stages and adds one.
	"sellos.config.setup_wizard.save_stages": {
		"stages": [*DEFAULT_STAGES, {"stage_name": "P105 Open", "stage_type": "Open"}]
	},
	"sellos.config.setup_wizard.add_user": {
		"email": "p105_wizard_user@example.com",
		"first_name": "P105",
		"role": "SellOS Agent",
	},
	"sellos.config.setup_wizard.finish_setup": {},
	# SOS-P1-17: the calls act on a spare agent made for the test, never on the caller.
	"sellos.access.users.list_users": {},
	"sellos.access.users.user_open_work": {"email": "{spare_user}"},
	"sellos.access.users.invite_user": {
		"email": "p117_invited@example.com",
		"first_name": "P117",
		"role": "SellOS Agent",
	},
	"sellos.access.users.resend_invitation": {"email": "{spare_user}"},
	"sellos.access.users.save_user": {"email": "{spare_user}", "values": {"first_name": "P117 Edit"}},
	"sellos.access.users.deactivate_user": {"email": "{spare_user}"},
	"sellos.access.users.reactivate_user": {"email": "{spare_user}"},
	# SOS-P1-18: the calls act on a spare team made for the test.
	"sellos.access.teams.list_teams": {},
	"sellos.access.teams.save_team": {"name": "{spare_team}", "values": {"members": []}},
	"sellos.access.teams.delete_team": {"name": "{spare_team}"},
	"sellos.reports.team.team_report": {},
	# SOS-P2-01: blank values keep what is saved, so the Company Admin's call changes nothing.
	"sellos.telephony.settings.get_telephony_settings": {},
	"sellos.telephony.settings.save_telephony_settings": {},
	"sellos.telephony.settings.check_connection": {},
	"sellos.access.field_history.getdoc": {"doctype": "Client", "name": "{client}"},
	"sellos.access.field_history.get_docinfo": {"doctype": "Client", "name": "{client}"},
}

# What a refused call may raise. A role check raises PermissionError. A record the user can't see
# may also read as missing.
REFUSALS = (frappe.PermissionError, frappe.DoesNotExistError)


def fill(args, names):
	if isinstance(args, dict):
		return {key: fill(value, names) for key, value in args.items()}
	if isinstance(args, str) and args.startswith("{") and args.endswith("}"):
		return names[args[1:-1]]
	return args


def as_who(who):
	frappe.set_user("Guest" if WHO[who] is None else TEST_USERS[WHO[who]]["email"])


def call(method, args):
	"""Call a method in this process as the current user. Returns everything the caller could see:
	the return value and the response a loader fills."""
	frappe.local.response = frappe._dict({"docs": []})
	fn = frappe.get_attr(method)
	result = fn(**args)
	return json.dumps([result, dict(frappe.local.response)], default=str)


def leaks(text):
	forms = [SECRET_NAME, ACTIVITY_NOTE, *phones.forms(SECRET_PHONE)]
	return [form for form in forms if form in text]


class TestPermissionSuiteCoverage(IntegrationTestCase):
	"""SOS-P1-05: the matrix covers every whitelisted method, and a gap fails the build."""

	def test_the_matrix_covers_every_whitelisted_sellos_method(self):
		load_declared_modules()
		import_all_sellos_modules()
		registry = {p: r for p, r in declared_methods().items() if ".test_" not in p}
		open_methods = [p for p in undeclared_whitelisted_methods() if ".test_" not in p]
		problems = matrix_problems(MATRIX, registry, open_methods)
		self.assertEqual(problems, [], "\n".join(problems))

	def test_every_matrix_method_has_sample_arguments_so_the_suite_calls_it(self):
		missing = sorted(set(MATRIX) - set(SAMPLE_CALLS))
		self.assertEqual(missing, [], f"Add SAMPLE_CALLS entries for: {missing}")
		self.assertEqual(sorted(set(SAMPLE_CALLS) - set(MATRIX)), [], "SAMPLE_CALLS names a stale method")

	def test_the_suite_covers_all_six_roles_an_outsider_and_a_guest(self):
		self.assertEqual(set(ROLE_KEYS.values()) | {"outsider", "guest"}, set(WHO))
		# SOS-SETUP-35: every SellOS role is in the suite, the Sales Manager included.
		self.assertEqual(set(ROLE_KEYS), set(ROLES))
		self.assertEqual({role for roles in MATRIX.values() for role in roles} - set(ROLE_KEYS), set())

	def test_a_sellos_method_with_no_declaration_is_refused_before_it_runs(self):
		self.assertTrue(is_refused("sellos.crm.api.not_declared_anywhere"))
		self.assertFalse(is_refused("sellos.crm.api.list_leads"))


class TestEveryMethodAsEveryone(IntegrationTestCase):
	"""SOS-P1-05: each method, as each role, an outsider and a guest, against one company's data."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user(TEST_USERS[ADMIN]["email"])
		client = frappe.get_doc(
			{
				"doctype": "Client",
				"client_name": SECRET_NAME,
				"client_type": "Buyer",
				"phone": SECRET_PHONE,
			}
		).insert()
		other = frappe.get_doc(
			{"doctype": "Client", "client_name": "P116 Other Buyer", "client_type": "Buyer"}
		).insert()
		lead = frappe.get_doc({"doctype": "Lead", "client": client.name, "source": "Website"}).insert()
		spare = frappe.get_doc({"doctype": "Lead Source", "source_name": "P120 Spare Source"}).insert()
		spare_outcome = frappe.get_doc(
			{"doctype": "Call Outcome", "outcome_name": "P121 Spare Outcome"}
		).insert()
		spare_reason = frappe.get_doc({"doctype": "Lost Reason", "reason_name": "P121 Spare Reason"}).insert()
		spare_user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "p117_spare_agent@example.com",
				"first_name": "P117 Spare",
				"send_welcome_email": 0,
				"roles": [{"role": "SellOS Agent"}],
			}
		)
		spare_user.flags.ignore_permissions = True
		spare_user.insert()
		spare_team = frappe.get_doc(
			{
				"doctype": "Sales Team",
				"team_name": "P118 Spare Team",
				"manager": TEST_USERS["sales_manager"]["email"],
			}
		).insert()
		rule_team = frappe.get_doc(
			{
				"doctype": "Sales Team",
				"team_name": "P119 Rule Team",
				"manager": TEST_USERS["sales_manager"]["email"],
			}
		).insert()
		spare_rule = frappe.get_doc(
			{
				"doctype": "Lead Assignment Rule",
				"rule_name": "P119 Spare Rule",
				"rule_type": "Round robin",
				"team": rule_team.name,
			}
		).insert()
		task = frappe.get_doc(
			{
				"doctype": "Lead Task",
				"lead": lead.name,
				"title": "P122 spare follow up",
				"due_date": "2030-01-01",
			}
		).insert()
		visit = frappe.get_doc(
			{
				"doctype": "Site Visit",
				"lead": lead.name,
				"project_name": "P125 Permission Tower",
				"visit_datetime": "2030-01-01 10:00:00",
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "Lead Activity",
				"lead": lead.name,
				"activity_type": "Note",
				"activity_date": now_datetime(),
				"notes": ACTIVITY_NOTE,
			}
		).insert()
		# P1.13: a grant that has already ended, so the support user reads nothing in these tests.
		support_user = TEST_USERS["platform_admin"]["email"]
		grant = support.grant_support_access(support_user, 60)
		support.revoke_support_access(grant["name"])
		# SOS-P1-23: the Company Admin's own notification. Any other user is told it is not found.
		notification = notifications.notify(
			TEST_USERS[ADMIN]["email"], notifications.LEAD_ASSIGNED, "P123 permission suite"
		)
		self.names = {
			"notification": notification,
			"task": task.name,
			"visit": visit.name,
			"client": client.name,
			"client_other": other.name,
			"lead": lead.name,
			"lead_list": [lead.name],
			"spare_source": spare.name,
			"spare_outcome": spare_outcome.name,
			"spare_reason": spare_reason.name,
			"spare_user": spare_user.name,
			"spare_team": spare_team.name,
			"spare_rule": spare_rule.name,
			"rule_team": rule_team.name,
			"agent": TEST_USERS["agent"]["email"],
			"support_user": support_user,
			"grant": grant["name"],
		}
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.response = frappe._dict()
		frappe.db.rollback()

	def args(self, method):
		return fill(SAMPLE_CALLS[method], self.names)

	def test_the_seeded_data_is_what_the_company_admin_sees(self):
		# Not vacuous: the secret is really returned to someone who may see it.
		as_who("company_admin")
		self.assertTrue(leaks(call("sellos.crm.api.get_lead", self.args("sellos.crm.api.get_lead"))))
		self.assertTrue(leaks(call("sellos.crm.api.list_clients", {})))

	def test_a_role_that_is_not_allowed_is_refused_and_gets_nothing(self):
		checked = 0
		for method, allowed in MATRIX.items():
			for who in WHO:
				if who in {ROLE_KEYS[role] for role in allowed}:
					continue
				as_who(who)
				with self.subTest(method=method, who=who), self.assertRaises(frappe.PermissionError):
					call(method, self.args(method))
				checked += 1
		self.assertGreater(checked, 0)

	def test_an_allowed_role_never_gets_another_users_records(self):
		"""The Agent and the Channel Partner may call the reads and writes, but the company's record
		is not theirs: each call is refused, or returns nothing of it."""
		for method, allowed in MATRIX.items():
			for role in allowed:
				who = ROLE_KEYS[role]
				if who == "company_admin":
					continue
				as_who(who)
				with self.subTest(method=method, who=who):
					try:
						text = call(method, self.args(method))
					except REFUSALS:
						continue
					self.assertEqual(leaks(text), [])

	def test_the_company_admin_may_call_every_method(self):
		for method in MATRIX:
			as_who("company_admin")
			with self.subTest(method=method):
				call(method, self.args(method))  # raises if refused

	def test_nobody_but_the_company_admin_is_shown_a_full_phone_number(self):
		for method in MATRIX:
			for who in WHO:
				if who == "company_admin":
					continue
				as_who(who)
				try:
					text = call(method, self.args(method))
				except (frappe.ValidationError, *REFUSALS):
					continue
				with self.subTest(method=method, who=who):
					for form in phones.forms(SECRET_PHONE):
						self.assertNotIn(form, text)

	def test_an_outsider_and_a_guest_get_nothing_from_any_method(self):
		"""A user from another company, and a signed out visitor, are refused by every method."""
		for method in MATRIX:
			for who in ("outsider", "guest"):
				as_who(who)
				with self.subTest(method=method, who=who), self.assertRaises(frappe.PermissionError):
					call(method, self.args(method))
