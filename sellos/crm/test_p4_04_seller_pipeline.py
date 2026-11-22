"""SOS-P4-04: the seller pipeline. The ten stages, the pipeline field on stages and leads, the limits that
apply to each pipeline alone, the stage rules and the stage change log."""

import frappe

from sellos.config import setup_wizard as wizard
from sellos.crm import api, board, call_outcomes, pipeline
from sellos.crm.test_crm import CrmCase, as_user
from sellos.crm.test_p1_07_buyer_pipeline import ELEVEN
from sellos.patches import p4_04_seller_pipeline

TEN = [
	("New owner enquiry", "Open"),
	("Qualified", "Open"),
	("Valuation shared", "Open"),
	("Mandate proposed", "Open"),
	("Mandate signed", "Open"),
	("Listed", "Open"),
	("Offers received", "Open"),
	("Sold", "Won"),
	("Closed lost", "Lost"),
	("Nurture", "Open"),
]


def seller_stages():
	return [
		(row.stage_name, row.stage_type)
		for row in frappe.get_all(
			pipeline.STAGE,
			filters={"pipeline": pipeline.SELLER},
			fields=["stage_name", "stage_type"],
			order_by="position asc",
		)
	]


class SellerCase(CrmCase):
	def setUp(self):
		super().setUp()
		call_outcomes.ensure_default_lost_reasons()
		pipeline.ensure_default_stages(pipeline.SELLER)

	def seller(self, label="Owner"):
		as_user("company_admin")
		client = api.save_client(values={"client_name": f"P404 {label}", "client_type": "Seller"})
		made = api.save_lead(
			values={
				"client": client["name"],
				"source": "Website",
				"pipeline": "Seller",
				"assigned_to": frappe.session.user,
			}
		)["lead"]["name"]
		return made

	def buyer(self):
		as_user("company_admin")
		client = api.save_client(values={"client_name": "P404 Buyer", "client_type": "Buyer"})
		return api.save_lead(
			values={"client": client["name"], "source": "Website", "assigned_to": frappe.session.user}
		)["lead"]["name"]


class TestTheSellerStages(SellerCase):
	"""SOS-P4-04: all ten stages exist, in order, with their kinds, and the buyer's eleven are untouched."""

	def test_all_ten_seller_stages_exist_in_order_with_their_kinds(self):
		self.assertEqual(seller_stages(), TEN)
		self.assertEqual([(s["stage_name"], s["stage_type"]) for s in pipeline.SELLER_STAGES], TEN)
		listed = pipeline.list_stages(pipeline.SELLER)
		self.assertEqual([(s["label"], s["stage_type"]) for s in listed], TEN)
		self.assertEqual({s["pipeline"] for s in listed}, {"Seller"})

	def test_the_buyer_pipeline_keeps_its_eleven_and_shares_no_stage_with_the_seller(self):
		buyer = [(s["name"], s["stage_type"]) for s in pipeline.list_stages(pipeline.BUYER)]
		self.assertEqual(buyer, ELEVEN)
		self.assertEqual(
			api.list_stages()[0]["name"], "New", "the buyer screens ask for no pipeline and get the Buyer's"
		)
		self.assertTrue(frappe.db.exists(pipeline.STAGE, "Seller Qualified"))
		self.assertEqual(frappe.db.get_value(pipeline.STAGE, "Qualified", "pipeline"), "Buyer")

	def test_a_second_seeding_changes_nothing(self):
		self.assertEqual(pipeline.ensure_default_stages(pipeline.SELLER), [])
		self.assertEqual(seller_stages(), TEN)

	def test_the_patch_sets_buyer_on_what_has_no_pipeline_and_can_run_again(self):
		lead = self.buyer()
		frappe.db.sql("update `tabPipeline Stage` set pipeline = '' where pipeline = 'Buyer'")
		frappe.db.sql("update `tabLead` set pipeline = '' where name = %s", lead)
		p4_04_seller_pipeline.execute()
		self.assertEqual(frappe.db.get_value("Lead", lead, "pipeline"), "Buyer")
		self.assertEqual(frappe.db.count(pipeline.STAGE, {"pipeline": "Buyer"}), 11)
		self.assertEqual(seller_stages(), TEN)
		p4_04_seller_pipeline.execute()
		self.assertEqual(frappe.db.count(pipeline.STAGE, {"pipeline": "Buyer"}), 11)
		self.assertEqual(seller_stages(), TEN)

	def test_a_stage_name_is_unique_inside_a_pipeline_only(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": pipeline.STAGE,
					"pipeline": "Seller",
					"stage_name": "Qualified",
					"stage_type": "Open",
					"position": 20,
				}
			).insert(ignore_permissions=True)


class TestTheSellerStageRules(SellerCase):
	"""SOS-P4-04: stage rules. A seller is a Lead on the Seller pipeline, linked to a Client, and moves only
	along its own stages. The Listed rule is SOS-P4-05's."""

	def test_a_seller_is_a_lead_linked_to_a_client_that_starts_on_the_first_seller_stage(self):
		lead = self.seller()
		doc = frappe.get_doc("Lead", lead)
		self.assertEqual(doc.pipeline, "Seller")
		self.assertEqual(doc.stage, "Seller New owner enquiry")
		self.assertTrue(frappe.db.exists("Client", doc.client))

	def test_a_seller_moves_along_its_stages_and_every_move_is_logged(self):
		lead = self.seller()
		for stage in ("Seller Qualified", "Seller Valuation shared", "Seller Mandate proposed"):
			result = api.move_lead_stage(lead, stage)
			self.assertTrue(result["moved"])
		log = frappe.get_doc("Lead", lead).stage_log
		self.assertEqual(
			[(r.from_stage, r.to_stage) for r in log],
			[
				("Seller New owner enquiry", "Seller Qualified"),
				("Seller Qualified", "Seller Valuation shared"),
				("Seller Valuation shared", "Seller Mandate proposed"),
			],
		)
		self.assertTrue(all(r.changed_by and r.changed_on for r in log))

	def test_a_seller_cannot_move_to_a_buyer_stage_nor_a_buyer_to_a_seller_stage(self):
		seller, buyer = self.seller(), self.buyer()
		with self.assertRaises(frappe.ValidationError):
			api.move_lead_stage(seller, "Contacted")
		with self.assertRaises(frappe.ValidationError):
			api.move_lead_stage(buyer, "Seller Qualified")
		self.assertEqual(frappe.db.get_value("Lead", seller, "stage"), "Seller New owner enquiry")
		self.assertEqual(frappe.db.get_value("Lead", buyer, "stage"), "New")

	def test_a_lead_keeps_its_pipeline_once_made(self):
		lead = self.seller()
		doc = frappe.get_doc("Lead", lead)
		doc.pipeline = "Buyer"
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_a_move_to_closed_lost_asks_for_a_reason(self):
		lead = self.seller()
		with self.assertRaises(frappe.MandatoryError):
			api.move_lead_stage(lead, "Seller Closed lost")
		reason = frappe.get_all("Lost Reason", filters={"enabled": 1}, pluck="name", limit=1)[0]
		api.move_lead_stage(lead, "Seller Closed lost", lost_reason=reason)
		self.assertEqual(frappe.db.get_value("Lead", lead, "stage"), "Seller Closed lost")

	def test_sold_is_a_won_stage_and_listed_is_open(self):
		self.assertEqual(frappe.db.get_value(pipeline.STAGE, "Seller Sold", "stage_type"), "Won")
		self.assertEqual(frappe.db.get_value(pipeline.STAGE, "Seller Listed", "stage_type"), "Open")
		# The signed mandate rule needs Mandate and is SOS-P4-05's: until then Listed is reachable.
		lead = self.seller()
		self.assertTrue(api.move_lead_stage(lead, "Seller Listed")["moved"])

	def test_a_stage_with_seller_leads_cannot_be_deleted_and_the_message_says_how_many(self):
		for label in ("One", "Two"):
			self.seller(label)
		with self.assertRaises(frappe.ValidationError) as caught:
			frappe.delete_doc(pipeline.STAGE, "Seller New owner enquiry", ignore_permissions=True)
		self.assertIn("2 lead(s)", str(caught.exception))

	def test_the_wizard_changes_only_the_buyer_stages_and_the_limits_are_per_pipeline(self):
		as_user("company_admin")
		wizard.save_stages(wizard.DEFAULT_STAGES)
		self.assertEqual(seller_stages(), TEN)
		self.assertEqual(len(wizard.get_setup_state()["stages"]), 11)
		# Twenty buyer stages are allowed even though the site holds ten seller stages besides.
		many = [{"stage_name": f"Step {i}", "stage_type": "Open"} for i in range(18)]
		many += [{"stage_name": "Won", "stage_type": "Won"}, {"stage_name": "Lost", "stage_type": "Lost"}]
		wizard.save_stages(many)
		self.assertEqual(len(wizard.get_setup_state()["stages"]), 20)
		self.assertEqual(seller_stages(), TEN)


class TestSellersAndBuyersStayApart(SellerCase):
	"""SOS-P4-04: the buyer list and board show buyers, and a seller board shows sellers."""

	def test_lists_and_boards_filter_on_the_pipeline(self):
		seller, buyer = self.seller(), self.buyer()
		self.assertIn(buyer, [lead.name for lead in api.list_leads()])
		self.assertNotIn(seller, [lead.name for lead in api.list_leads()])
		self.assertEqual([lead.name for lead in api.list_leads(pipeline="Seller")], [seller])
		columns = api.get_board(pipeline="Seller")["columns"]
		self.assertEqual([(c["label"], c["stage_type"]) for c in columns], TEN)
		self.assertEqual([c["count"] for c in columns].count(1), 1)
		self.assertEqual(board.board()["columns"][0]["stage"], "New")
		with self.assertRaises(frappe.ValidationError):
			api.list_leads(pipeline="Nowhere")


class TestTheRegressionSellers(SellerCase):
	"""SOS-P4-04: the regression seed makes two sellers through the API, and a second run changes nothing."""

	def test_the_seed_makes_two_sellers_and_a_second_run_changes_nothing(self):
		from sellos.testing.users import TEST_USERS
		from sellos.tests import ui_fixtures

		ui_fixtures._test_users()
		admin = TEST_USERS["company_admin"]["email"]
		agent = TEST_USERS["agent"]["email"]
		ui_fixtures._seed_sellers(admin, agent)
		ui_fixtures._seed_sellers(admin, agent)
		rows = frappe.get_all(
			"Lead",
			filters={"lead_title": ["like", "Regression Seller %"]},
			fields=["lead_title", "pipeline", "stage", "assigned_to", "client"],
			order_by="lead_title asc",
		)
		self.assertEqual(len(rows), 2)
		self.assertEqual({r.pipeline for r in rows}, {"Seller"})
		self.assertEqual(rows[0].stage, "Seller Valuation shared")
		self.assertEqual(rows[1].stage, "Seller New owner enquiry")
		self.assertTrue(all(r.assigned_to == agent and r.client for r in rows))
