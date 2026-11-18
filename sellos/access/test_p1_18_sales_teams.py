"""SOS-P1-18: sales teams and the Sales Manager. Every role is checked against two teams."""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from sellos.access import lead_permissions as lp
from sellos.access import teams
from sellos.access.roles import AGENT, SALES_MANAGER, ensure_roles
from sellos.crm import api
from sellos.reports import team as team_report
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones

PHONE = phones.in_mobile(118)
SECOND_AGENT = "p118_agent_two@example.com"
THIRD_AGENT = "p118_agent_three@example.com"
SECOND_MANAGER = "p118_manager_two@example.com"
CHILDREN = ("Lead Activity", "Lead Task", "Site Visit")


def _email(key):
	return TEST_USERS[key]["email"]


def _make_user(email, role):
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"send_welcome_email": 0,
			"roles": [{"role": role}],
		}
	)
	user.flags.ignore_permissions = True
	user.insert()
	return email


class SalesTeamCase(IntegrationTestCase):
	"""Team A: the test manager with the test agent and a third agent. Team B: a second manager and
	a second agent. One lead each for the two agents, and one nobody on a team owns."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		self.agent_a, self.agent_b = _email("agent"), _make_user(SECOND_AGENT, AGENT)
		self.agent_a2 = _make_user(THIRD_AGENT, AGENT)
		self.manager_a, self.manager_b = _email("sales_manager"), _make_user(SECOND_MANAGER, SALES_MANAGER)
		self.admin = _email("company_admin")
		frappe.set_user(self.admin)
		self.team_a = self.make_team("P118 Team A", self.manager_a, [self.agent_a, self.agent_a2])
		self.team_b = self.make_team("P118 Team B", self.manager_b, [self.agent_b])
		self.lead_a = self.make_lead("P118 Buyer A", self.agent_a)
		self.lead_b = self.make_lead("P118 Buyer B", self.agent_b)
		self.lead_free = self.make_lead("P118 Buyer Free", None)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def make_team(self, name, manager, members):
		return frappe.get_doc(
			{
				"doctype": "Sales Team",
				"team_name": name,
				"manager": manager,
				"members": [{"agent": m} for m in members],
			}
		).insert()

	def make_lead(self, name, assigned_to):
		client = api.save_client(values={"client_name": name, "client_type": "Buyer", "phone": PHONE})
		lead = api.save_lead(
			values={"client": client["name"], "source": "Website", "assigned_to": assigned_to}
		)["lead"]["name"]
		for doctype, extra in (
			("Lead Activity", {"activity_type": "Note", "activity_date": now_datetime()}),
			("Lead Task", {"title": f"{name} task", "due_date": "2030-01-01"}),
			("Site Visit", {"project_name": "P118 Tower", "visit_datetime": "2030-01-01 10:00:00"}),
		):
			frappe.get_doc({"doctype": doctype, "lead": lead, **extra}).insert()
		return lead

	def visible(self, user, doctype="Lead"):
		frappe.set_user(user)
		try:
			return set(frappe.get_list(doctype, pluck="name", limit_page_length=0))
		except frappe.PermissionError:
			return set()


class TestTeamRules(SalesTeamCase):
	"""SOS-P1-18: a Company Admin creates teams, and an agent is in at most one."""

	def test_a_company_admin_creates_a_team_and_reads_it_back(self):
		frappe.set_user(self.admin)
		saved = teams.save_team(values={"team_name": "P118 Team C", "manager": self.manager_a, "members": []})
		self.assertEqual(saved["manager"], self.manager_a)
		listed = teams.list_teams()
		self.assertEqual(
			{t["team_name"] for t in listed["teams"]}, {"P118 Team A", "P118 Team B", "P118 Team C"}
		)
		self.assertIn(self.manager_b, {m["name"] for m in listed["managers"]})
		team_a = next(t for t in listed["teams"] if t["team_name"] == "P118 Team A")
		self.assertEqual({m["user"] for m in team_a["members"]}, {self.agent_a, self.agent_a2})

	def test_an_agent_is_in_at_most_one_team(self):
		frappe.set_user(self.admin)
		with self.assertRaises(frappe.ValidationError):
			self.make_team("P118 Team C", self.manager_b, [self.agent_a])
		with self.assertRaises(frappe.ValidationError):
			teams.save_team(name=self.team_b.name, values={"members": [self.agent_b, self.agent_a2]})
		# moving an agent is done by taking them out of the first team
		teams.save_team(name=self.team_a.name, values={"members": [self.agent_a]})
		teams.save_team(name=self.team_b.name, values={"members": [self.agent_b, self.agent_a2]})

	def test_the_manager_and_the_members_must_hold_the_right_roles(self):
		frappe.set_user(self.admin)
		with self.assertRaises(frappe.ValidationError):
			self.make_team("P118 Team C", self.agent_a, [])  # an agent is no manager
		with self.assertRaises(frappe.ValidationError):
			self.make_team("P118 Team C", self.manager_a, [self.manager_b])  # a manager is no agent
		with self.assertRaises(frappe.ValidationError):
			teams.save_team(name=self.team_a.name, values={"members": [self.agent_a, self.agent_a]})

	def test_only_a_company_admin_changes_teams(self):
		for user in (self.manager_a, self.agent_a, _email("channel_partner"), _email("client")):
			frappe.set_user(user)
			for fn, kwargs in (
				(teams.save_team, {"name": self.team_a.name, "values": {"members": []}}),
				(teams.delete_team, {"name": self.team_a.name}),
			):
				with self.subTest(user=user, fn=fn.__name__), self.assertRaises(frappe.PermissionError):
					fn(**kwargs)

	def test_a_sales_manager_reads_only_the_team_they_manage(self):
		frappe.set_user(self.manager_a)
		listed = teams.list_teams()
		self.assertEqual([t["team_name"] for t in listed["teams"]], ["P118 Team A"])
		self.assertNotIn("managers", listed)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Sales Team", self.team_b.name).check_permission("read")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Sales Team", self.team_a.name).check_permission("write")


class TestEveryRoleAgainstTwoTeams(SalesTeamCase):
	"""SOS-P1-18: who sees which leads and records when two teams exist."""

	def children_of(self, lead):
		return {
			doctype: frappe.get_all(doctype, filters={"lead": lead}, pluck="name") for doctype in CHILDREN
		}

	def test_a_sales_manager_sees_exactly_their_teams_leads_and_records(self):
		self.assertEqual(self.visible(self.manager_a), {self.lead_a})
		self.assertEqual(self.visible(self.manager_b), {self.lead_b})
		for manager, own, other in (
			(self.manager_a, self.lead_a, self.lead_b),
			(self.manager_b, self.lead_b, self.lead_a),
		):
			frappe.set_user("Administrator")
			own_children, other_children = self.children_of(own), self.children_of(other)
			for doctype in CHILDREN:
				self.assertEqual(self.visible(manager, doctype), set(own_children[doctype]), doctype)
				self.assertFalse(set(other_children[doctype]) & self.visible(manager, doctype))
			frappe.set_user(manager)
			frappe.get_doc("Lead", own).check_permission("write")
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc("Lead", other).check_permission("read")
			for doctype, names in other_children.items():
				self.assertFalse(frappe.has_permission(doctype, "read", doc=names[0]), doctype)
			self.assertTrue(frappe.has_permission("Lead Task", "write", doc=own_children["Lead Task"][0]))

	def test_the_record_api_and_the_list_show_only_the_team(self):
		frappe.set_user(self.manager_a)
		self.assertEqual({lead["name"] for lead in api.list_leads()}, {self.lead_a})
		self.assertEqual(api.get_lead(self.lead_a)["lead"]["name"], self.lead_a)
		for lead in (self.lead_b, self.lead_free):
			with self.assertRaises(frappe.PermissionError):
				api.get_lead(lead)
		self.assertEqual({c["client_name"] for c in api.list_clients()}, {"P118 Buyer A"})
		with self.assertRaises(frappe.PermissionError):
			api.add_activity(self.lead_b, "Note", "not my team")
		api.add_activity(self.lead_a, "Note", "my team")

	def test_every_other_role_against_the_two_teams(self):
		expected = {
			self.agent_a: {self.lead_a},
			self.agent_a2: set(),
			self.agent_b: {self.lead_b},
			self.admin: {self.lead_a, self.lead_b, self.lead_free},
			_email("platform_admin"): set(),
			_email("client"): set(),
			_email("channel_partner"): set(),
			_email("basic"): set(),
		}
		for user, leads in expected.items():
			with self.subTest(user=user):
				self.assertEqual(self.visible(user), leads)

	def test_a_sales_manager_sees_masked_phone_numbers_only(self):
		frappe.set_user(self.manager_a)
		texts = [
			json.dumps(api.get_lead(self.lead_a), default=str),
			json.dumps(api.list_clients(), default=str),
			json.dumps(api.list_leads(), default=str),
		]
		client = frappe.get_doc("Lead", self.lead_a).client
		self.assertTrue(api.save_client(name=client, values={"city": "Pune"})["phone"].startswith("*"))
		for text in texts:
			for form in phones.forms(PHONE):
				self.assertNotIn(form, text)
		self.assertEqual(api.get_lead(self.lead_a)["client"]["phone"], "*" * 9 + PHONE[-3:])
		rows = frappe.get_list("Client", fields=["name", "phone", "phone_masked"])
		self.assertTrue(rows)
		for row in rows:
			self.assertFalse(row.get("phone"), "a direct read gave the full number")

	def test_the_scope_function_gives_the_manager_a_team_scope(self):
		self.assertEqual(lp.scope_for([SALES_MANAGER]), "team")
		self.assertEqual(
			lp.visible_users(self.manager_a, "team"), [self.manager_a, *sorted([self.agent_a, self.agent_a2])]
		)
		self.assertEqual(lp.visible_users(self.agent_a, "own"), [self.agent_a])
		self.assertEqual(lp.team_members(self.agent_a), [])


class TestReassigningAndReports(SalesTeamCase):
	"""SOS-P1-18: reassigning within the team, and the team's report."""

	def test_a_manager_reassigns_a_lead_within_the_team(self):
		frappe.set_user(self.manager_a)
		self.assertEqual(api.reassign_lead(self.lead_a, self.agent_a2)["assigned_to"], self.agent_a2)
		self.assertEqual(frappe.db.get_value("Lead", self.lead_a, "assigned_to"), self.agent_a2)

	def test_a_manager_cannot_move_a_lead_out_of_or_into_another_team(self):
		frappe.set_user(self.manager_a)
		with self.assertRaises(frappe.PermissionError):
			api.reassign_lead(self.lead_a, self.agent_b)  # another team's agent
		with self.assertRaises(frappe.PermissionError):
			api.save_lead(name=self.lead_a, values={"assigned_to": self.agent_b})
		with self.assertRaises(frappe.PermissionError):
			api.reassign_lead(self.lead_b, self.agent_a)  # another team's lead
		self.assertEqual(frappe.db.get_value("Lead", self.lead_a, "assigned_to"), self.agent_a)
		self.assertEqual(frappe.db.get_value("Lead", self.lead_b, "assigned_to"), self.agent_b)

	def test_a_company_admin_reassigns_across_teams_and_agents_may_not_call_it(self):
		frappe.set_user(self.admin)
		api.reassign_lead(self.lead_a, self.agent_b)
		self.assertEqual(frappe.db.get_value("Lead", self.lead_a, "assigned_to"), self.agent_b)
		for user in (self.agent_b, _email("channel_partner"), _email("client")):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				api.reassign_lead(self.lead_a, self.agent_b)

	def test_a_managers_report_counts_only_their_team(self):
		frappe.set_user(self.manager_a)
		report = team_report.team_report()
		self.assertEqual(report["total"], 1)
		self.assertEqual([row["agent"] for row in report["by_agent"]], [self.agent_a])
		self.assertEqual(report["teams"], ["P118 Team A"])
		frappe.set_user(self.manager_b)
		self.assertEqual([row["agent"] for row in team_report.team_report()["by_agent"]], [self.agent_b])
		frappe.set_user(self.admin)
		self.assertEqual(team_report.team_report()["total"], 3)
		for user in (self.agent_a, _email("client"), _email("channel_partner")):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				team_report.team_report()


class TestFixtures(SalesTeamCase):
	"""SOS-P1-18: what the browser spec and the regression data make, read back."""

	def test_the_spec_seed_makes_two_teams_and_one_lead_each_and_the_cleanup_removes_them(self):
		from sellos.tests import ui_fixtures

		frappe.set_user("Administrator")
		frappe.db.delete("Sales Team Member")  # the case's own teams hold the test agent
		frappe.db.delete("Sales Team")
		with patch.object(frappe.db, "commit"):  # the fixtures commit for the browser. The test rolls back.
			made = ui_fixtures.seed_sales_teams()
			seeded = frappe.db.get_value("Lead", {"lead_title": ["like", f"{made['own']}%"]}, "name")
			self.assertEqual(self.visible(self.manager_a), {self.lead_a, seeded})
			self.assertEqual(
				frappe.db.get_value("Sales Team", made["team_b"], "manager"), "gate_team_manager@example.com"
			)
			self.assertEqual(ui_fixtures.remove_sales_teams(), {"teams": 2})
		self.assertFalse(frappe.db.exists("Sales Team", made["team_a"]))
		self.assertFalse(frappe.db.exists("User", "gate_team_agent@example.com"))

	def test_the_regression_seed_is_read_back_and_safe_to_run_twice(self):
		from sellos.tests import ui_fixtures

		frappe.set_user("Administrator")
		frappe.db.delete("Sales Team Member")
		frappe.db.delete("Sales Team")
		agents = (self.agent_a, self.agent_b, self.agent_a2)
		for _ in range(2):
			ui_fixtures._seed_sales_teams(self.admin, *agents)
			north = frappe.get_doc("Sales Team", "Regression Team North")
			self.assertEqual(north.manager, self.manager_a)
			self.assertEqual({m.agent for m in north.members}, {self.agent_a, self.agent_b})
			self.assertEqual(
				[m.agent for m in frappe.get_doc("Sales Team", "Regression Team South").members],
				[self.agent_a2],
			)
