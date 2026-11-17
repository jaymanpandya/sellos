"""SOS-P1-07: the buyer pipeline. The eleven stages, a move from any consent status, the warning and the
stage change log, the patch from the seven old stages, and the rules for a Company Admin's stage list."""

import frappe
from frappe.model.rename_doc import rename_doc

from sellos.config import setup_wizard as wizard
from sellos.crm import api, consent, pipeline
from sellos.crm.test_crm import CrmCase, as_user
from sellos.patches import p1_07_buyer_pipeline

ELEVEN = [
	("New", "Open"),
	("Consent pending", "Open"),
	("Contacted", "Open"),
	("Qualified", "Open"),
	("Site visit booked", "Open"),
	("Site visit done", "Open"),
	("Negotiation", "Open"),
	("Booking", "Won"),
	("Closed won", "Won"),
	("Closed lost", "Lost"),
	("Nurture", "Open"),
]
OLD_SEVEN = [
	("New", "Open"),
	("Contacted", "Open"),
	("Site visit scheduled", "Open"),
	("Site visit done", "Open"),
	("Negotiation", "Open"),
	("Booked", "Won"),
	("Lost", "Lost"),
]
STATUSES = ("Consented", "Unknown", "Opted out", "Registered DND")


def stages_now():
	return [
		(row.name, row.stage_type)
		for row in frappe.get_all(
			pipeline.STAGE, fields=["name", "stage_type"], order_by="position asc, name asc"
		)
	]


def clear_stages():
	"""A site with no stages. The leads come off theirs first (tests only, the test rolls back)."""
	frappe.db.set_value("Lead", {"stage": ["is", "set"]}, "stage", None, update_modified=False)
	for name in frappe.get_all(pipeline.STAGE, pluck="name"):
		frappe.delete_doc(pipeline.STAGE, name, ignore_permissions=True)


def make_old_stages():
	clear_stages()
	for position, (name, kind) in enumerate(OLD_SEVEN, start=1):
		frappe.get_doc(
			{"doctype": pipeline.STAGE, "stage_name": name, "stage_type": kind, "position": position}
		).insert(ignore_permissions=True)


class PipelineCase(CrmCase):
	def lead_with_status(self, status, user="company_admin"):
		"""A lead on the first stage whose consent status is `status`, made through the CRM API."""
		as_user(user)
		client = api.save_client(values={"client_name": f"P107 {status} Buyer", "client_type": "Buyer"})
		lead = api.save_lead(
			values={"client": client["name"], "source": "Website", "assigned_to": frappe.session.user}
		)["lead"]["name"]
		if status == "Consented":
			api.record_consent(lead, "Consent", "https://example.com/evidence/p107")
		elif status == "Opted out":
			api.record_opt_out(lead, "WhatsApp")
		elif status == "Registered DND":
			api.record_dnd_result(lead, 1)
		self.assertEqual(consent.compute_status(lead), status)
		return lead


class TestTheStages(PipelineCase):
	"""SOS-P1-07: the eleven stages in order, with their kinds, on a fresh site and after the patch."""

	def test_the_site_has_the_eleven_stages_in_order_with_their_kinds(self):
		self.assertEqual(stages_now(), ELEVEN)
		self.assertEqual([(s["stage_name"], s["stage_type"]) for s in pipeline.DEFAULT_STAGES], ELEVEN)

	def test_a_fresh_company_site_is_given_the_eleven_and_a_second_run_changes_nothing(self):
		clear_stages()
		self.assertEqual(stages_now(), [])
		made = pipeline.ensure_default_stages()
		self.assertEqual([(name, None) for name in made], [(n, None) for n, _ in ELEVEN])
		self.assertEqual(stages_now(), ELEVEN)
		self.assertEqual(pipeline.ensure_default_stages(), [])
		self.assertEqual(stages_now(), ELEVEN)

	def test_a_company_that_changed_its_stages_is_not_given_the_standard_ones_again(self):
		clear_stages()
		wizard.save_stages(
			[
				{"stage_name": "Enquiry", "stage_type": "Open"},
				{"stage_name": "Booking", "stage_type": "Won"},
				{"stage_name": "Closed lost", "stage_type": "Lost"},
			]
		)
		before = stages_now()
		self.assertEqual(pipeline.ensure_default_stages(), [])
		self.assertEqual(stages_now(), before)

	def test_a_new_lead_starts_on_the_first_stage(self):
		lead = self.lead_with_status("Unknown")
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "New")

	def test_a_stage_that_does_not_exist_is_the_only_refusal(self):
		lead = self.lead_with_status("Unknown")
		with self.assertRaises(frappe.ValidationError):
			api.move_lead_stage(lead, "Nowhere")
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "New")


class TestMovesIgnoreConsent(PipelineCase):
	"""SOS-P1-07: every consent status moves to Contacted and every other stage. Only Contacted warns."""

	def test_every_consent_status_moves_to_contacted_with_a_warning_except_consented(self):
		for status in STATUSES:
			with self.subTest(status=status):
				lead = self.lead_with_status(status, "agent")
				result = api.move_lead_stage(lead, "Contacted")
				self.assertTrue(result["moved"])
				self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "Contacted")
				view = api.get_lead(lead)["pipeline"]
				row = view["log"][0]
				self.assertEqual((row["from_stage"], row["to_stage"]), ("New", "Contacted"))
				if status == "Consented":
					self.assertIsNone(result["warning"])
					self.assertIsNone(view["warning"])
					self.assertEqual(row["warning"], "")
				else:
					self.assertIn("Moved to Contacted", result["warning"]["message"])
					self.assertEqual(result["warning"]["status"], status)
					self.assertEqual(view["warning"]["status"], status)
					self.assertIn("Contacted", view["warning"]["message"])
					self.assertEqual(row["warning"], result["warning"]["message"])

	def test_a_lead_with_no_live_consent_record_is_told_so(self):
		lead = self.lead_with_status("Unknown", "agent")
		warning = api.move_lead_stage(lead, "Contacted")["warning"]
		self.assertIn("without a live Consent Record", warning["message"])
		self.assertEqual(warning["level"], "amber")
		stored = frappe.get_doc("Lead", lead).stage_log[0].warning
		self.assertEqual(stored, warning["message"])

	def test_an_opted_out_lead_gets_a_red_warning_and_still_moves(self):
		lead = self.lead_with_status("Opted out", "agent")
		warning = api.move_lead_stage(lead, "Contacted")["warning"]
		self.assertEqual(warning["level"], "red")
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "Contacted")

	def test_every_status_moves_to_every_stage(self):
		for status in STATUSES:
			lead = self.lead_with_status(status, "agent")
			for name, _kind in ELEVEN:
				with self.subTest(status=status, stage=name):
					api.move_lead_stage(lead, name)
					self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), name)
		# Consent pending is a stage like any other: nothing put a lead there, and nothing holds it there.
		lead = self.lead_with_status("Consented", "agent")
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "New")
		api.move_lead_stage(lead, "Consent pending")
		api.record_consent(lead, "Consent", "https://example.com/evidence/p107b")
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "Consent pending")
		api.move_lead_stage(lead, "Qualified")
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "Qualified")

	def test_only_the_contacted_stage_warns(self):
		lead = self.lead_with_status("Unknown", "agent")
		for name, _kind in ELEVEN:
			if name != "Contacted":
				self.assertIsNone(api.move_lead_stage(lead, name)["warning"], name)
		self.assertTrue(all(not row["warning"] for row in api.get_lead(lead)["pipeline"]["log"]))

	def test_the_warning_follows_the_stage_not_its_name(self):
		rename_doc(
			pipeline.STAGE, "Contacted", "Called", force=True, ignore_permissions=True, rebuild_search=False
		)
		lead = self.lead_with_status("Unknown", "agent")
		self.assertIsNotNone(api.move_lead_stage(lead, "Called")["warning"])

	def test_a_move_to_the_same_stage_is_not_logged_again(self):
		lead = self.lead_with_status("Unknown", "agent")
		api.move_lead_stage(lead, "Qualified")
		again = api.move_lead_stage(lead, "Qualified")
		self.assertFalse(again["moved"])
		self.assertEqual(len(frappe.get_doc("Lead", lead).stage_log), 1)

	def test_every_move_is_logged_with_who_when_and_where_from(self):
		lead = self.lead_with_status("Consented", "agent")
		api.move_lead_stage(lead, "Qualified")
		api.move_lead_stage(lead, "Site visit booked")
		log = api.get_lead(lead)["pipeline"]["log"]
		self.assertEqual(
			[(r["from_stage"], r["to_stage"], r["changed_by"]) for r in log],
			[
				("Qualified", "Site visit booked", frappe.session.user),
				("New", "Qualified", frappe.session.user),
			],
		)
		self.assertTrue(all(r["changed_on"] for r in log))

	def test_a_channel_partner_a_client_and_an_outsider_cannot_move_a_lead(self):
		lead = self.lead_with_status("Unknown", "agent")
		for who in ("channel_partner", "client", "basic"):
			as_user(who)
			with self.subTest(who=who), self.assertRaises(frappe.PermissionError):
				api.move_lead_stage(lead, "Contacted")


class TestThePatch(PipelineCase):
	"""SOS-P1-07: the patch carries the seven old stages and their leads over, and is safe to run twice."""

	def old_site(self):
		make_old_stages()
		leads = {}
		for index, (name, _kind) in enumerate(OLD_SEVEN):
			client = frappe.get_doc(
				{"doctype": "Client", "client_name": f"P107 Old {index}", "client_type": "Buyer"}
			).insert()
			lead = frappe.get_doc({"doctype": "Lead", "client": client.name, "source": "Website"}).insert()
			frappe.db.set_value("Lead", lead.name, "stage", name, update_modified=False)
			leads[name] = lead.name
		return leads

	def stages_of(self, leads):
		return {old: frappe.db.get_value("Lead", lead, "stage") for old, lead in leads.items()}

	def test_every_lead_goes_where_the_story_says_and_a_second_run_changes_nothing(self):
		leads = self.old_site()
		p1_07_buyer_pipeline.execute()
		expected = {
			"New": "New",
			"Contacted": "Contacted",
			"Site visit scheduled": "Site visit booked",
			"Site visit done": "Site visit done",
			"Negotiation": "Negotiation",
			"Booked": "Booking",
			"Lost": "Closed lost",
		}
		self.assertEqual(self.stages_of(leads), expected)
		self.assertEqual(stages_now(), ELEVEN)
		stage_rows = frappe.get_all(pipeline.STAGE, fields=["*"], order_by="position asc")
		lead_rows = frappe.get_all("Lead", filters={"name": ["in", list(leads.values())]}, fields=["*"])
		p1_07_buyer_pipeline.execute()
		self.assertEqual(self.stages_of(leads), expected)
		self.assertEqual(stages_now(), ELEVEN)
		self.assertEqual(frappe.get_all(pipeline.STAGE, fields=["*"], order_by="position asc"), stage_rows)
		self.assertEqual(
			frappe.get_all("Lead", filters={"name": ["in", list(leads.values())]}, fields=["*"]), lead_rows
		)

	def test_the_second_run_reports_nothing_to_do(self):
		self.old_site()
		first = pipeline.carry_over_stages()
		self.assertEqual(first["leads_moved"], 3)
		self.assertEqual(sorted(first["added"]), ["Closed won", "Consent pending", "Nurture", "Qualified"])
		second = pipeline.carry_over_stages()
		self.assertEqual(
			(second["renamed"], second["added"], second["leads_moved"], second["leads_placed"]),
			([], [], 0, 0),
		)

	def test_the_stages_the_old_list_lacked_are_added_in_order_and_the_won_and_lost_kinds_hold(self):
		self.old_site()
		p1_07_buyer_pipeline.execute()
		self.assertEqual(frappe.db.get_value(pipeline.STAGE, "Contacted", "is_contact_stage"), 1)
		kinds = dict(stages_now())
		self.assertEqual(
			(kinds["Booking"], kinds["Closed won"], kinds["Closed lost"]), ("Won", "Won", "Lost")
		)

	def test_a_lead_with_no_stage_goes_on_the_first_one(self):
		leads = self.old_site()
		frappe.db.set_value("Lead", leads["New"], "stage", None, update_modified=False)
		p1_07_buyer_pipeline.execute()
		self.assertEqual(frappe.db.get_value("Lead", leads["New"], "stage"), "New")

	def test_a_stage_a_company_added_is_kept_after_the_standard_ones(self):
		self.old_site()
		frappe.get_doc(
			{"doctype": pipeline.STAGE, "stage_name": "P107 Custom", "stage_type": "Open", "position": 8}
		).insert()
		p1_07_buyer_pipeline.execute()
		self.assertEqual(stages_now(), [*ELEVEN, ("P107 Custom", "Open")])


class TestTheCompanyAdminsStages(PipelineCase):
	"""SOS-P1-07: rename, reorder and add within the limits. A stage with leads is never deleted."""

	def rows(self):
		return wizard.get_setup_state()["stages"]

	def test_a_stage_is_renamed_and_its_leads_stay_on_it(self):
		lead = self.lead_with_status("Unknown")
		stages = self.rows()
		stages[0]["stage_name"] = "Enquiry"
		wizard.save_stages(stages)
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "Enquiry")
		self.assertFalse(frappe.db.exists(pipeline.STAGE, "New"))
		self.assertEqual(self.rows()[0]["leads"], 1)

	def test_stages_are_reordered_and_two_can_swap_names(self):
		stages = self.rows()
		stages[0], stages[1] = stages[1], stages[0]
		wizard.save_stages(stages)
		self.assertEqual([s["stage_name"] for s in self.rows()][:2], ["Consent pending", "New"])
		names = self.rows()
		names[0]["stage_name"], names[1]["stage_name"] = names[1]["stage_name"], names[0]["stage_name"]
		wizard.save_stages(names)
		self.assertEqual([s["stage_name"] for s in self.rows()][:2], ["New", "Consent pending"])
		self.assertEqual(frappe.db.get_value(pipeline.STAGE, "New", "position"), 1)

	def test_a_stage_is_added_up_to_the_limit_and_no_further(self):
		stages = self.rows()
		for i in range(wizard.MAX_STAGES - len(stages)):
			stages.append({"stage_name": f"P107 Extra {i}", "stage_type": "Open"})
		wizard.save_stages(stages)
		self.assertEqual(len(self.rows()), wizard.MAX_STAGES)
		stages = self.rows()
		stages.append({"stage_name": "One too many", "stage_type": "Open"})
		with self.assertRaises(frappe.ValidationError):
			wizard.save_stages(stages)
		self.assertEqual(len(self.rows()), wizard.MAX_STAGES)

	def test_there_must_still_be_one_won_and_one_lost_stage(self):
		for kind in ("Won", "Lost"):
			stages = [s for s in self.rows() if s["stage_type"] != kind]
			with self.subTest(kind=kind), self.assertRaises(frappe.ValidationError):
				wizard.save_stages(stages)

	def test_a_stage_with_leads_cannot_be_deleted_and_the_message_says_how_many(self):
		for _ in range(2):
			self.lead_with_status("Unknown")
		stages = [s for s in self.rows() if s["stage_name"] != "New"]
		with self.assertRaises(frappe.ValidationError) as caught:
			wizard.save_stages(stages)
		self.assertIn("2 lead(s)", str(caught.exception))
		with self.assertRaises(frappe.ValidationError) as direct:
			frappe.delete_doc(pipeline.STAGE, "New", ignore_permissions=True)
		self.assertIn("2 lead(s)", str(direct.exception))
		self.assertTrue(frappe.db.exists(pipeline.STAGE, "New"))
		self.assertEqual(len(self.rows()), 11)

	def test_a_stage_with_no_leads_is_deleted(self):
		stages = [s for s in self.rows() if s["stage_name"] != "Nurture"]
		wizard.save_stages(stages)
		self.assertFalse(frappe.db.exists(pipeline.STAGE, "Nurture"))
		self.assertEqual(len(self.rows()), 10)

	def test_an_archived_lead_still_holds_its_stage(self):
		lead = self.lead_with_status("Unknown")
		api.set_archived("Lead", lead)
		stages = [s for s in self.rows() if s["stage_name"] != "New"]
		with self.assertRaises(frappe.ValidationError):
			wizard.save_stages(stages)

	def test_the_other_roles_cannot_change_the_stages(self):
		for who in ("agent", "channel_partner"):
			as_user(who)
			with self.subTest(who=who), self.assertRaises(frappe.PermissionError):
				wizard.save_stages(wizard.DEFAULT_STAGES)

	def setUp(self):
		super().setUp()
		as_user("company_admin")
