"""SOS-P1-19: assign and reassign leads. Each rule (source, locality, round robin, the default team), round
robin over a deactivated agent, the log, one and bulk reassignment with the move of follow ups and future
site visits, a Sales Manager's team limit, and deactivating an agent who holds work."""

import itertools
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from sellos.access import users
from sellos.access.roles import AGENT, SALES_MANAGER, ensure_roles
from sellos.crm import api, assignment, notifications, pipeline
from sellos.crm.test_crm import as_user, email
from sellos.testing.users import create_test_users
from sellos.tests import phones

_SEEDS = itertools.count(420)
SOURCE = "Website"


def make_user(address, role):
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": address,
			"first_name": address.split("@")[0],
			"send_welcome_email": 0,
			"roles": [{"role": role}],
		}
	)
	user.flags.ignore_permissions = True
	user.insert()
	return address


class AssignmentCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user("Administrator")
		pipeline.ensure_default_stages()
		self.agents = [make_user(f"p119_agent_{n}@example.com", AGENT) for n in (1, 2, 3)]
		self.outside = make_user("p119_outside@example.com", AGENT)
		self.manager = email("sales_manager")
		self.other_manager = make_user("p119_manager_two@example.com", SALES_MANAGER)
		self.team = self.make_team("P119 North", self.manager, self.agents)
		self.team_two = self.make_team("P119 South", self.other_manager, [self.outside])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def make_team(self, name, manager, members):
		return (
			frappe.get_doc(
				{
					"doctype": "Sales Team",
					"team_name": name,
					"manager": manager,
					"members": [{"agent": agent} for agent in members],
				}
			)
			.insert()
			.name
		)

	def make_rule(self, name, rule_type, team, priority=10, **values):
		return (
			frappe.get_doc(
				{
					"doctype": "Lead Assignment Rule",
					"rule_name": name,
					"rule_type": rule_type,
					"team": team,
					"priority": priority,
					**values,
				}
			)
			.insert()
			.name
		)

	def new_lead(self, source=SOURCE, who="company_admin", assigned_to=None, **values):
		as_user(who)
		client = api.save_client(
			values={
				"client_name": "P119 Buyer",
				"client_type": "Buyer",
				"phone": phones.in_mobile(next(_SEEDS)),
			}
		)
		lead = {"client": client["name"], "source": source, **values}
		if assigned_to:
			lead["assigned_to"] = assigned_to
		return api.save_lead(values=lead)["lead"]["name"]

	def agent_of(self, lead):
		return frappe.db.get_value("Lead", lead, "assigned_to")

	def log_of(self, lead):
		return frappe.get_all(
			"Lead Assignment",
			filters={"lead": lead},
			fields=["from_agent", "to_agent", "method", "rule", "team"],
			order_by="creation asc",
		)


class TestAssignmentRules(AssignmentCase):
	"""SOS-P1-19: a new lead is assigned by the Company Admin's rules, and the assignment is logged."""

	def test_a_source_rule_sends_the_lead_to_its_team_and_logs_it(self):
		rule = self.make_rule("P119 Referral to South", "Source", self.team_two, source="Referral")
		lead = self.new_lead(source="Referral")
		self.assertEqual(self.agent_of(lead), self.outside)
		self.assertEqual(
			self.log_of(lead),
			[
				frappe._dict(
					from_agent=None, to_agent=self.outside, method="Rule", rule=rule, team=self.team_two
				)
			],
		)

	def test_a_locality_rule_matches_a_wanted_locality_whatever_its_case(self):
		self.make_rule("P119 Powai", "Locality", self.team_two, locality="powai")
		lead = self.new_lead(preferred_localities=["Andheri", "Powai"])
		self.assertEqual(self.agent_of(lead), self.outside)
		elsewhere = self.new_lead(preferred_localities=["Thane"])
		self.assertIsNone(self.agent_of(elsewhere))  # no rule and no default team

	def test_a_round_robin_rule_matches_every_lead_and_rules_go_in_order(self):
		self.make_rule("P119 Everyone", "Round robin", self.team, priority=20)
		self.make_rule("P119 Referral first", "Source", self.team_two, priority=1, source="Referral")
		self.assertEqual(self.agent_of(self.new_lead(source="Referral")), self.outside)
		self.assertEqual(self.agent_of(self.new_lead(source="Website")), self.agents[0])

	def test_a_lead_no_rule_matches_goes_to_the_default_team(self):
		self.make_rule("P119 Referral only", "Source", self.team_two, source="Referral")
		as_user("company_admin")
		api.set_default_team(self.team)
		lead = self.new_lead(source="Website")
		self.assertEqual(self.agent_of(lead), self.agents[0])
		row = self.log_of(lead)[0]
		self.assertEqual((row.method, row.rule, row.team), ("Default team", None, self.team))

	def test_a_rule_whose_team_has_no_active_agent_is_passed_over(self):
		frappe.db.set_value("User", self.outside, "enabled", 0)
		self.make_rule("P119 Empty South", "Source", self.team_two, priority=1, source="Referral")
		self.make_rule("P119 Fallback", "Round robin", self.team, priority=2)
		self.assertEqual(self.agent_of(self.new_lead(source="Referral")), self.agents[0])

	def test_a_disabled_rule_is_ignored_and_with_no_rule_the_lead_stays_unassigned(self):
		rule = self.make_rule("P119 Off", "Round robin", self.team)
		frappe.db.set_value("Lead Assignment Rule", rule, "enabled", 0)
		lead = self.new_lead()
		self.assertIsNone(self.agent_of(lead))
		self.assertEqual(self.log_of(lead), [])

	def test_a_lead_given_an_agent_by_hand_keeps_it_and_the_choice_is_logged(self):
		self.make_rule("P119 Everyone", "Round robin", self.team)
		lead = self.new_lead(assigned_to=self.outside)
		self.assertEqual(self.agent_of(lead), self.outside)
		self.assertEqual([(r.method, r.to_agent) for r in self.log_of(lead)], [("Manual", self.outside)])

	def test_the_lead_made_by_the_website_import_or_hand_path_is_assigned_the_same_way(self):
		# Every path inserts a Lead document, and the rules run when it is inserted.
		self.make_rule("P119 Everyone", "Round robin", self.team)
		frappe.set_user("Administrator")
		client = frappe.get_doc(
			{"doctype": "Client", "client_name": "P119 Import", "client_type": "Buyer"}
		).insert()
		lead = frappe.get_doc({"doctype": "Lead", "client": client.name, "source": SOURCE}).insert()
		self.assertEqual(lead.assigned_to, self.agents[0])
		self.assertEqual(self.log_of(lead.name)[0].method, "Rule")

	def test_the_assigned_agent_is_notified_and_a_sales_manager_creating_a_lead_is_not_refused(self):
		self.make_rule("P119 South", "Round robin", self.team_two)
		lead = self.new_lead(who="sales_manager")  # the rule's team is not the manager's own
		self.assertEqual(self.agent_of(lead), self.outside)
		self.assertTrue(
			frappe.db.exists(
				"App Notification",
				{"recipient": self.outside, "event": notifications.LEAD_ASSIGNED, "lead": lead},
			)
		)

	def test_only_a_company_admin_keeps_the_rules(self):
		for who in ("agent", "sales_manager", "channel_partner"):
			as_user(who)
			with self.assertRaises(frappe.PermissionError):
				api.save_assignment_rule(
					values={"rule_name": "x", "rule_type": "Round robin", "team": self.team}
				)
			with self.assertRaises(frappe.PermissionError):
				api.list_assignment_rules()
		as_user("company_admin")
		saved = api.save_assignment_rule(
			values={"rule_name": "P119 Saved", "rule_type": "Source", "source": "Referral", "team": self.team}
		)
		listed = api.list_assignment_rules()
		self.assertIn(saved["name"], [r.name for r in listed["rules"]])
		self.assertEqual(api.delete_assignment_rule(saved["name"]), {"deleted": saved["name"]})

	def test_a_source_rule_needs_its_source_and_a_locality_rule_its_locality(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_rule("P119 No source", "Source", self.team)
		with self.assertRaises(frappe.ValidationError):
			self.make_rule("P119 No locality", "Locality", self.team)


class TestRoundRobin(AssignmentCase):
	"""SOS-P1-19: round robin skips deactivated agents and spreads leads evenly."""

	def test_leads_are_spread_evenly_in_turn(self):
		self.make_rule("P119 Everyone", "Round robin", self.team)
		leads = [self.new_lead() for _ in range(6)]
		got = [self.agent_of(lead) for lead in leads]
		self.assertEqual(got, self.agents * 2)
		self.assertEqual({got.count(agent) for agent in self.agents}, {2})

	def test_a_deactivated_agent_is_skipped_and_the_rest_share_evenly(self):
		self.make_rule("P119 Everyone", "Round robin", self.team)
		frappe.db.set_value("User", self.agents[1], "enabled", 0)
		got = [self.agent_of(self.new_lead()) for _ in range(4)]
		self.assertNotIn(self.agents[1], got)
		self.assertEqual((got.count(self.agents[0]), got.count(self.agents[2])), (2, 2))

	def test_an_agent_who_is_turned_back_on_takes_a_turn_again(self):
		self.make_rule("P119 Everyone", "Round robin", self.team)
		frappe.db.set_value("User", self.agents[1], "enabled", 0)
		self.new_lead()
		frappe.db.set_value("User", self.agents[1], "enabled", 1)
		got = [self.agent_of(self.new_lead()) for _ in range(3)]
		self.assertEqual(sorted(got), sorted(self.agents))

	def test_a_team_with_no_active_agent_gives_none(self):
		for agent in self.agents:
			frappe.db.set_value("User", agent, "enabled", 0)
		self.assertEqual(assignment.active_agents(self.team), [])
		self.assertIsNone(assignment.next_agent(self.team))


class TestReassignment(AssignmentCase):
	"""SOS-P1-19: one and bulk reassignment, with the follow ups and future visits, within a manager's team."""

	def work_for(self, lead, agent):
		as_user("company_admin")
		task = api.save_task(
			values={"lead": lead, "title": "P119 call", "due_date": "2030-01-01", "assigned_to": agent}
		)
		done = api.save_task(
			values={
				"lead": lead,
				"title": "P119 done",
				"due_date": "2030-01-01",
				"assigned_to": agent,
				"status": "Done",
			}
		)
		future = api.save_site_visit(
			values={"lead": lead, "project_name": "P119 Tower", "visit_datetime": "2030-06-11 10:00:00"}
		)
		past = frappe.get_doc(
			{
				"doctype": "Site Visit",
				"lead": lead,
				"project_name": "P119 Old",
				"visit_datetime": "2020-01-01 10:00:00",
				"agent": agent,
			}
		).insert()
		return task["name"], done["name"], future["name"], past.name

	def test_a_company_admin_reassigns_one_lead_with_its_open_tasks_and_future_visits(self):
		lead = self.new_lead(assigned_to=self.agents[0])
		task, done, future, past = self.work_for(lead, self.agents[0])
		as_user("company_admin")
		result = api.reassign_lead(lead, self.agents[1], note="Busy")
		self.assertEqual((result["tasks_moved"], result["visits_moved"]), (1, 1))
		self.assertEqual(self.agent_of(lead), self.agents[1])
		self.assertEqual(frappe.db.get_value("Lead Task", task, "assigned_to"), self.agents[1])
		self.assertEqual(frappe.db.get_value("Site Visit", future, "agent"), self.agents[1])
		# A finished task and a visit already in the past stay with the agent who did them.
		self.assertEqual(frappe.db.get_value("Lead Task", done, "assigned_to"), self.agents[0])
		self.assertEqual(frappe.db.get_value("Site Visit", past, "agent"), self.agents[0])
		last = self.log_of(lead)[-1]
		self.assertEqual(
			(last.from_agent, last.to_agent, last.method), (self.agents[0], self.agents[1], "Manual")
		)
		self.assertEqual(
			frappe.db.get_value("Lead Assignment", {"lead": lead, "note": "Busy"}, "assigned_by"),
			email("company_admin"),
		)

	def test_the_new_agent_is_notified_and_the_old_one_told_it_moved(self):
		lead = self.new_lead(assigned_to=self.agents[0])
		as_user("company_admin")
		api.reassign_lead(lead, self.agents[1])
		self.assertTrue(
			frappe.db.exists(
				"App Notification",
				{"recipient": self.agents[1], "event": notifications.LEAD_ASSIGNED, "lead": lead},
			)
		)
		self.assertTrue(
			frappe.db.exists(
				"App Notification", {"recipient": self.agents[0], "event": notifications.LEAD_REASSIGNED_AWAY}
			)
		)

	def test_a_lead_can_only_go_to_an_active_agent(self):
		lead = self.new_lead(assigned_to=self.agents[0])
		frappe.db.set_value("User", self.agents[1], "enabled", 0)
		as_user("company_admin")
		with self.assertRaises(frappe.ValidationError):
			api.reassign_lead(lead, self.agents[1])
		with self.assertRaises(frappe.ValidationError):
			api.reassign_lead(lead, email("client"))
		self.assertEqual(self.agent_of(lead), self.agents[0])

	def test_bulk_reassignment_moves_the_listed_leads_with_their_work(self):
		leads = [self.new_lead(assigned_to=self.agents[0]) for _ in range(3)]
		tasks = [self.work_for(lead, self.agents[0])[0] for lead in leads]
		as_user("company_admin")
		result = api.bulk_reassign_leads(self.agents[2], leads=leads)
		self.assertEqual((result["count"], result["tasks_moved"], result["visits_moved"]), (3, 3, 3))
		self.assertEqual({self.agent_of(lead) for lead in leads}, {self.agents[2]})
		self.assertEqual(
			{frappe.db.get_value("Lead Task", t, "assigned_to") for t in tasks}, {self.agents[2]}
		)
		self.assertEqual({self.log_of(lead)[-1].method for lead in leads}, {"Bulk"})

	def test_bulk_reassignment_of_a_filtered_set_moves_only_what_the_filter_finds(self):
		mine = [self.new_lead(source="Referral", assigned_to=self.agents[0]) for _ in range(2)]
		kept = self.new_lead(source="Website", assigned_to=self.agents[0])
		as_user("company_admin")
		result = api.bulk_reassign_leads(
			self.agents[1], filters={"source": "Referral", "assigned_to": self.agents[0]}
		)
		self.assertEqual(sorted(result["moved"]), sorted(mine))
		self.assertEqual(self.agent_of(kept), self.agents[0])
		self.assertEqual({self.agent_of(lead) for lead in mine}, {self.agents[1]})

	def test_bulk_reassignment_needs_leads_and_refuses_too_many(self):
		as_user("company_admin")
		with self.assertRaises(frappe.ValidationError):
			api.bulk_reassign_leads(self.agents[1], leads=[])
		with self.assertRaises(frappe.ValidationError):
			api.bulk_reassign_leads(self.agents[1], filters={"source": "No such source"})
		original = assignment.BULK_LIMIT
		assignment.BULK_LIMIT = 1
		self.addCleanup(setattr, assignment, "BULK_LIMIT", original)
		leads = [self.new_lead(assigned_to=self.agents[0]) for _ in range(2)]
		as_user("company_admin")
		with self.assertRaises(frappe.ValidationError):
			api.bulk_reassign_leads(self.agents[1], leads=leads)
		self.assertEqual({self.agent_of(lead) for lead in leads}, {self.agents[0]})

	def test_a_sales_manager_reassigns_within_their_team_only(self):
		lead = self.new_lead(assigned_to=self.agents[0])
		own_team = self.new_lead(assigned_to=self.agents[1])
		other_team = self.new_lead(assigned_to=self.outside)
		as_user("sales_manager")
		self.assertEqual([a.name for a in api.reassign_options()["agents"]], sorted(self.agents))
		api.reassign_lead(lead, self.agents[2])
		self.assertEqual(self.agent_of(lead), self.agents[2])
		with self.assertRaises(frappe.PermissionError):  # another team's agent
			api.reassign_lead(lead, self.outside)
		with self.assertRaises(frappe.PermissionError):  # another team's lead
			api.reassign_lead(other_team, self.agents[0])
		frappe.db.savepoint("p119_bulk")  # a failed request is rolled back whole, as the server does
		with self.assertRaises(frappe.PermissionError):  # a bulk move that includes another team's lead
			api.bulk_reassign_leads(self.agents[0], leads=[own_team, other_team])
		frappe.db.rollback(save_point="p119_bulk")
		self.assertEqual(self.agent_of(own_team), self.agents[1])
		result = api.bulk_reassign_leads(self.agents[0], filters={})
		self.assertEqual(sorted(result["moved"]), sorted([lead, own_team]))
		self.assertEqual(self.agent_of(other_team), self.outside)

	def test_an_agent_and_a_channel_partner_may_not_reassign(self):
		lead = self.new_lead(assigned_to=self.agents[0])
		for who in ("agent", "channel_partner"):
			as_user(who)
			for call in (
				lambda: api.reassign_lead(lead, self.agents[1]),
				lambda: api.bulk_reassign_leads(self.agents[1], leads=[lead]),
				lambda: api.reassign_options(),
			):
				with self.assertRaises(frappe.PermissionError):
					call()

	def test_the_lead_shows_its_assignment_history(self):
		lead = self.new_lead(assigned_to=self.agents[0])
		as_user("company_admin")
		api.reassign_lead(lead, self.agents[1])
		history = api.get_lead(lead)["assignments"]
		self.assertEqual([h["to_agent"] for h in history], [self.agents[1], self.agents[0]])
		self.assertEqual(history[0]["to_name"], frappe.db.get_value("User", self.agents[1], "full_name"))


class TestDeactivation(AssignmentCase):
	"""SOS-P1-19: deactivating an agent asks where their open leads go, and nothing stays with them."""

	def deactivate(self, *args, **kwargs):
		with patch.object(
			frappe.db, "commit"
		):  # ending a session commits in Frappe. The test keeps its rollback.
			return users.deactivate_user(*args, **kwargs)

	def holdings(self, agent):
		return assignment.open_work(agent)

	def make_work(self, agent):
		lead = self.new_lead(assigned_to=agent)
		as_user("company_admin")
		task = api.save_task(
			values={"lead": lead, "title": "P119 call", "due_date": "2030-01-01", "assigned_to": agent}
		)
		visit = api.save_site_visit(
			values={"lead": lead, "project_name": "P119 Tower", "visit_datetime": "2030-06-11 10:00:00"}
		)
		return lead, task["name"], visit["name"]

	def test_it_asks_where_the_leads_go_and_changes_nothing_until_told(self):
		lead, *_work = self.make_work(self.agents[0])
		as_user("company_admin")
		result = self.deactivate(self.agents[0])
		self.assertTrue(result["needs_handover"])
		self.assertEqual((result["open_lead_count"], result["open_task_count"]), (1, 1))
		self.assertNotIn(self.agents[0], [a.name for a in result["agents"]])
		self.assertEqual(frappe.db.get_value("User", self.agents[0], "enabled"), 1)
		self.assertEqual(self.agent_of(lead), self.agents[0])

	def test_the_chosen_agent_takes_every_open_lead_task_and_visit(self):
		lead, task, visit = self.make_work(self.agents[0])
		as_user("company_admin")
		result = self.deactivate(self.agents[0], reassign_to=self.agents[1])
		self.assertFalse(result["needs_handover"])
		self.assertEqual(result["handed_over"], {"leads": 1, "tasks": 1, "visits": 1})
		self.assertEqual(frappe.db.get_value("User", self.agents[0], "enabled"), 0)
		self.assertEqual(self.agent_of(lead), self.agents[1])
		self.assertEqual(frappe.db.get_value("Lead Task", task, "assigned_to"), self.agents[1])
		self.assertEqual(frappe.db.get_value("Site Visit", visit, "agent"), self.agents[1])
		self.assertEqual(self.log_of(lead)[-1].method, "Deactivation")
		self.assertEqual(self.holdings(self.agents[0]), {"leads": [], "tasks": [], "visits": []})

	def test_distribution_shares_the_leads_among_the_teams_active_agents(self):
		leads = [self.make_work(self.agents[0])[0] for _ in range(4)]
		frappe.db.set_value("User", self.agents[2], "enabled", 0)
		as_user("company_admin")
		self.deactivate(self.agents[0], distribute=1)
		got = [self.agent_of(lead) for lead in leads]
		self.assertEqual(got, [self.agents[1]] * 4)  # the only other active agent of the team
		self.assertEqual(self.holdings(self.agents[0]), {"leads": [], "tasks": [], "visits": []})

	def test_distribution_spreads_over_several_agents(self):
		leads = [self.make_work(self.agents[0])[0] for _ in range(4)]
		as_user("company_admin")
		self.deactivate(self.agents[0], distribute=1)
		got = [self.agent_of(lead) for lead in leads]
		self.assertEqual({got.count(self.agents[1]), got.count(self.agents[2])}, {2})

	def test_it_refuses_when_nobody_can_take_the_leads_and_leaves_the_agent_active(self):
		self.make_work(self.outside)  # the only agent of the South team
		as_user("company_admin")
		with self.assertRaises(frappe.ValidationError):
			self.deactivate(self.outside, distribute=1)
		with self.assertRaises(frappe.ValidationError):
			self.deactivate(self.outside, reassign_to=self.outside)
		with self.assertRaises(frappe.ValidationError):
			self.deactivate(self.outside, reassign_to=email("client"))

	def test_an_agent_with_no_open_work_is_deactivated_at_once(self):
		as_user("company_admin")
		result = self.deactivate(self.agents[2])
		self.assertFalse(result["needs_handover"])
		self.assertEqual(frappe.db.get_value("User", self.agents[2], "enabled"), 0)


class TestSpecFixtures(AssignmentCase):
	"""SOS-P1-19: the data the bulk reassignment spec uses is made through the production API, and is read back."""

	def test_the_spec_seed_holds_three_leads_with_work_and_the_state_reads_back(self):
		from sellos.tests import ui_fixtures

		# The fixture commits for the browser. The test keeps its rollback.
		with patch.object(frappe.db, "commit"):
			seed = ui_fixtures.seed_bulk_reassign()
			state = ui_fixtures.assignment_state(seed["leads"])
			self.assertEqual(set(state["leads"].values()), {seed["holder"]})
			self.assertEqual(state["Lead Task"], {seed["holder"]: 3})
			self.assertEqual(state["Site Visit"], {seed["holder"]: 3})
			as_user("company_admin")
			api.bulk_reassign_leads(seed["taker"], filters={"assigned_to": seed["holder"]})
			frappe.set_user("Administrator")
			state = ui_fixtures.assignment_state(seed["leads"])
			self.assertEqual(set(state["leads"].values()), {seed["taker"]})
			self.assertEqual(
				(state["Lead Task"], state["Site Visit"]), ({seed["taker"]: 3}, {seed["taker"]: 3})
			)
			self.assertEqual(state["log"], [seed["taker"]] * 3)
			ui_fixtures.remove_gate_assignment()
		self.assertFalse(frappe.db.exists("User", seed["taker"]))
		self.assertFalse(frappe.db.exists("Sales Team", seed["team"]))
