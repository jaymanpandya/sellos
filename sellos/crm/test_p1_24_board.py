"""SOS-P1-24: the pipeline board and the lead list filters."""

import itertools

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, now_datetime

from sellos.access.roles import ensure_roles
from sellos.crm import api, board
from sellos.crm.test_crm import as_user, email
from sellos.testing.users import create_test_users
from sellos.tests import phones

STAGES = (
	"New",
	"Consent pending",
	"Contacted",
	"Qualified",
	"Site visit booked",
	"Site visit done",
	"Negotiation",
	"Booking",
	"Closed won",
	"Closed lost",
	"Nurture",
)


_SEEDS = itertools.count(240)


class BoardCase(IntegrationTestCase):
	"""Leads made through the production API, as the people who own them."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def lead(self, key, name, **values):
		as_user(key)
		client = api.save_client(
			values={"client_name": name, "client_type": "Buyer", "phone": phones.in_mobile(next(_SEEDS))}
		)
		made = api.save_lead(values={"client": client["name"], "source": "Website", **values})
		return made["lead"]["name"]

	def names(self, rows):
		return {row["client_name"] for row in rows}

	def column(self, result, stage):
		return next(c for c in result["columns"] if c["stage"] == stage)


class TestBoard(BoardCase):
	"""SOS-P1-24: the board shows a column per stage with the count and the total budget."""

	def test_one_column_per_stage_in_order_with_count_and_total_budget(self):
		self.lead("agent", "P124 Cheap", budget_from=1000000, budget_to=2000000)
		self.lead("agent", "P124 Dear", budget_to=5000000)
		self.lead("agent", "P124 No Budget")
		as_user("agent")
		result = api.get_board()
		self.assertEqual([c["stage"] for c in result["columns"]], list(STAGES))
		new = self.column(result, "New")
		self.assertEqual(new["count"], len(new["leads"]))
		self.assertEqual(new["total_budget"], sum(c["budget"] for c in new["leads"]))
		mine = {c["client_name"]: c["budget"] for c in new["leads"]}
		self.assertEqual(mine["P124 Cheap"], 2000000)
		self.assertEqual(mine["P124 Dear"], 5000000)
		self.assertEqual(mine["P124 No Budget"], 0)
		self.assertEqual(result["total"], sum(c["count"] for c in result["columns"]))
		self.assertEqual(self.column(result, "Nurture")["count"], 0)

	def test_an_agent_sees_only_their_own_leads_on_the_board(self):
		self.lead("agent", "P124 Own")
		self.lead("company_admin", "P124 Not Theirs")
		as_user("agent")
		shown = {c["client_name"] for col in api.get_board()["columns"] for c in col["leads"]}
		self.assertIn("P124 Own", shown)
		self.assertNotIn("P124 Not Theirs", shown)
		as_user("company_admin")
		everyone = {c["client_name"] for col in api.get_board()["columns"] for c in col["leads"]}
		self.assertTrue({"P124 Own", "P124 Not Theirs"} <= everyone)

	def test_a_card_moves_to_any_stage_whatever_its_consent_and_the_move_is_logged(self):
		lead = self.lead("agent", "P124 Opted Out")
		api.record_opt_out(lead, "Phone call")
		for stage in ("Contacted", "Booking", "Nurture"):
			moved = api.move_lead_stage(lead, stage)
			self.assertTrue(moved["moved"])
			self.assertEqual(moved["stage"], stage)
		contacted = frappe.get_doc("Lead", lead).stage_log
		self.assertEqual([r.to_stage for r in contacted], ["Contacted", "Booking", "Nurture"])
		self.assertTrue(contacted[0].warning)
		result = api.get_board()
		self.assertEqual(self.column(result, "Nurture")["leads"][0]["consent_status"], "Opted out")
		self.assertEqual(self.column(result, "Nurture")["leads"][0]["consent_warning"], "red")

	def test_a_partner_sees_their_leads_and_cannot_move_one(self):
		as_user("channel_partner")
		self.assertEqual(api.get_board()["total"], 0)
		with self.assertRaises(frappe.PermissionError):
			api.move_lead_stage("none", "Contacted")


class TestFilters(BoardCase):
	"""SOS-P1-24: each filter, and the filters together."""

	def test_stage_source_and_search_filters(self):
		one = self.lead("agent", "P124 Stage One")
		self.lead("agent", "P124 Stage Two", source="Referral")
		api.move_lead_stage(one, "Qualified")
		self.assertEqual(self.names(api.list_leads(stage="Qualified")), {"P124 Stage One"})
		self.assertEqual(self.names(api.list_leads(source="Referral")), {"P124 Stage Two"})
		self.assertEqual(self.names(api.list_leads(stage="Qualified", source="Referral")), set())
		self.assertEqual(self.names(api.list_leads(search="Referral")), {"P124 Stage Two"})

	def test_agent_and_team_filters(self):
		frappe.set_user("Administrator")
		frappe.get_doc(
			{
				"doctype": "Sales Team",
				"team_name": "P124 Team",
				"manager": email("sales_manager"),
				"members": [{"agent": email("agent")}],
			}
		).insert()
		self.lead("agent", "P124 Team Lead", assigned_to=email("agent"))
		self.lead("company_admin", "P124 Free Lead")
		as_user("company_admin")
		team = frappe.db.get_value("Sales Team", {"team_name": "P124 Team"}, "name")
		self.assertEqual(self.names(api.list_leads(team=team)), {"P124 Team Lead"})
		self.assertEqual(self.names(api.list_leads(assigned_to=email("agent"))), {"P124 Team Lead"})
		self.assertEqual(self.names(api.list_leads(team=team, assigned_to=email("company_admin"))), set())
		self.assertEqual(self.names(api.list_leads(team="no such team")), set())
		options = api.lead_filter_options()
		self.assertIn(email("agent"), [a["name"] for a in options["agents"]])
		self.assertIn(team, [t["name"] for t in options["teams"]])
		as_user("sales_manager")
		self.assertEqual(self.names(api.list_leads(team=team)), {"P124 Team Lead"})
		as_user("agent")
		self.assertEqual(api.lead_filter_options()["teams"], [])

	def test_consent_status_filter(self):
		out = self.lead("agent", "P124 Out")
		self.lead("agent", "P124 Unknown")
		api.record_opt_out(out, "SMS")
		self.assertEqual(self.names(api.list_leads(consent_status="Opted out")), {"P124 Out"})
		self.assertEqual(self.names(api.list_leads(consent_status="Unknown")), {"P124 Unknown"})
		self.assertEqual(self.names(api.list_leads(consent_status="Consented")), set())

	def test_requirement_filters_still_combine_with_the_new_ones(self):
		self.lead("agent", "P124 Big", budget_from=9000000, budget_to=9500000, configuration=["3 BHK"])
		self.lead("agent", "P124 Small", budget_from=1000000, budget_to=2000000, configuration=["1 BHK"])
		self.assertEqual(self.names(api.list_leads(budget_min=8000000)), {"P124 Big"})
		self.assertEqual(self.names(api.list_leads(configuration="1 BHK", stage="New")), {"P124 Small"})
		self.assertEqual(self.names(api.list_leads(configuration="1 BHK", stage="Booking")), set())

	def test_last_contacted_and_untouched(self):
		fresh = self.lead("agent", "P124 Fresh")
		stale = self.lead("agent", "P124 Stale")
		never = self.lead("agent", "P124 Never")
		api.add_activity(fresh, "Call", activity_date=add_days(now_datetime(), -1))
		api.add_activity(stale, "Call", activity_date=add_days(now_datetime(), -30))
		api.add_activity(never, "Note")  # a note is not a contact
		old = add_days(now_datetime(), -30)
		frappe.db.set_value("Lead", stale, "creation", old, update_modified=False)
		frappe.db.set_value("Lead", never, "creation", old, update_modified=False)
		frappe.db.set_value("Lead Activity", {"lead": stale}, "activity_date", add_days(now_datetime(), -30))
		recent = add_days(now_datetime(), -5).date().isoformat()
		self.assertEqual(self.names(api.list_leads(last_contacted_from=recent)), {"P124 Fresh"})
		self.assertEqual(self.names(api.list_leads(last_contacted_to=recent)), {"P124 Stale", "P124 Never"})
		self.assertEqual(self.names(api.list_leads(untouched=1)), {"P124 Stale"})
		rows = {r["client_name"]: r for r in api.list_leads()}
		self.assertFalse(rows["P124 Fresh"]["untouched"])
		self.assertTrue(rows["P124 Stale"]["untouched"])
		self.assertFalse(rows["P124 Never"]["untouched"])  # its note is recent activity
		self.assertEqual(board.UNTOUCHED_DAYS, 7)

	def test_untouched_is_marked_on_the_board_too(self):
		lead = self.lead("agent", "P124 Old Lead")
		frappe.db.set_value("Lead", lead, "creation", add_days(now_datetime(), -40), update_modified=False)
		as_user("agent")
		card = self.column(api.get_board(), "New")["leads"][0]
		self.assertTrue(card["untouched"])
		self.assertEqual(
			self.names(self.column(api.get_board(untouched=1), "New")["leads"]), {"P124 Old Lead"}
		)


class TestRegressionSeed(BoardCase):
	"""SOS-P1-24: the dormant regression lead the board and the list mark as untouched."""

	def test_the_dormant_lead_is_made_through_the_api_and_is_marked_untouched(self):
		from sellos.tests import ui_fixtures

		agent, admin = email("agent"), email("company_admin")
		ui_fixtures._seed_dormant_lead(admin, agent)
		ui_fixtures._seed_dormant_lead(admin, agent)  # safe to run again: still one
		as_user("agent")
		rows = [r for r in api.list_leads() if r["client_name"] == "Regression Dormant Eight"]
		self.assertEqual(len(rows), 1)
		self.assertTrue(rows[0]["untouched"])
		self.assertEqual(rows[0]["budget"], 7000000)
		self.assertEqual(rows[0]["stage"], "New")
		self.assertEqual(rows[0]["source"], "Referral")
