"""SOS-P7-04: commission rates per project and partner firm, the payout made when a deal's split is approved,
its way through Due, Approved and Paid (or On hold), a partner's own statement and a Company Admin's export."""

import csv
import io
from decimal import Decimal

import frappe

from sellos.access.roles import CHANNEL_PARTNER
from sellos.crm.test_crm import as_user, email
from sellos.inventory import commissions, deals
from sellos.inventory.test_p4_06_deal import COMPANY, DealCase
from sellos.tests import phones

PRICE = 10000000
PARTNER_MAIL = "p406_partner@example.com"  # the firm DealCase makes


class CommissionCase(DealCase):
	def setUp(self):
		super().setUp()
		self.project = frappe.db.get_value("Unit", self.unit, "project")

	def rate(self, value=2, start="2026-01-01", rate_type="Percentage", firm=None, project=None):
		as_user("company_admin")
		return commissions.save_commission_rate(
			{
				"project": project or self.project,
				"partner_firm": firm,
				"rate_type": rate_type,
				"value": value,
				"start_date": start,
			}
		)["name"]

	def approved_deal(self, deal_date="2026-03-15", share=20, price=PRICE, firm=None):
		"""A deal of the unit whose split gives the partner `share` percent, approved. Returns its name."""
		agent = 100 - share - 30
		name = self.deal(
			[
				self.agent_row(agent),
				self.partner_row(share, firm),
				{**COMPANY, "percent": 30},
			],
			deal_date=deal_date,
			price=price,
		)
		as_user("company_admin")
		deals.approve_splits(name)
		return name

	def payout_of(self, deal, firm=None):
		name = frappe.db.get_value("Commission Payout", {"deal": deal, "partner_firm": firm or self.firm})
		return frappe.get_doc("Commission Payout", name) if name else None

	def move(self, payout, to, **kw):
		as_user("company_admin")
		return commissions.move_payout(payout.name, to, **kw)

	def as_partner(self, mail=PARTNER_MAIL):
		frappe.set_user(mail)


class TestCalculation(CommissionCase):
	"""SOS-P7-04: the commission due, on hand worked examples."""

	def test_a_project_rate_of_two_percent_and_a_partner_share_of_twenty_percent(self):
		# Rs 1,00,00,000 at 2% is Rs 2,00,000. A fifth of it is Rs 40,000.
		self.rate(2)
		payout = self.payout_of(self.approved_deal())
		self.assertEqual(payout.status, "Due")
		self.assertEqual(
			(payout.commission_total, payout.commission_due, payout.partner_percent, payout.agreement_value),
			(200000.0, 40000.0, 20.0, 1e7),
		)
		self.assertEqual((payout.rate_basis, payout.project), ("2% of the agreement value", self.project))

	def test_a_fixed_amount_rate_is_the_commission_whatever_the_price(self):
		self.rate(150000, rate_type="Fixed amount")
		payout = self.payout_of(self.approved_deal(share=40))
		self.assertEqual((payout.commission_total, payout.commission_due), (150000.0, 60000.0))

	def test_a_firm_rate_overrides_the_project_rate_for_that_firm_only(self):
		self.rate(2)
		self.rate(50000, rate_type="Fixed amount", firm=self.firm)
		other = self.make_firm("p704_other@example.com", "P704 Other Firm")
		mine = self.payout_of(self.approved_deal())
		theirs = self.payout_of(self.approved_deal(firm=other), other)
		self.assertEqual((mine.commission_total, mine.commission_due), (50000.0, 10000.0))
		self.assertEqual((theirs.commission_total, theirs.commission_due), (200000.0, 40000.0))

	def test_the_rate_in_force_on_the_booking_date_is_used_not_the_latest(self):
		first = self.rate(2, start="2026-01-01")
		second = self.rate(3, start="2026-06-01")
		early = self.payout_of(self.approved_deal(deal_date="2026-03-15"))
		late = self.payout_of(self.approved_deal(deal_date="2026-07-01"))
		self.assertEqual((early.rate, early.commission_due), (first, 40000.0))
		self.assertEqual((late.rate, late.commission_due), (second, 60000.0))

	def test_a_rate_changed_after_the_booking_date_does_not_touch_the_payout(self):
		self.rate(2, start="2026-01-01")
		deal = self.approved_deal(deal_date="2026-03-15")
		self.rate(5, start="2026-08-01")
		self.assertEqual(self.payout_of(deal).commission_due, 40000.0)
		# Even a payout worked out again at a later approval uses the rate of the booking date.
		as_user("company_admin")
		deals.reopen_splits(deal)
		deals.approve_splits(deal)
		self.assertEqual(self.payout_of(deal).commission_due, 40000.0)

	def test_the_earlier_rates_are_kept_and_an_archived_rate_is_not_used(self):
		first = self.rate(2, start="2026-01-01")
		second = self.rate(3, start="2026-06-01")
		self.assertTrue(all(frappe.db.exists("Commission Rate", r) for r in (first, second)))
		as_user("company_admin")
		commissions.set_commission_rate_archived(second)
		chosen = commissions.rate_in_force(self.project, self.firm, "2026-07-01")
		self.assertEqual(chosen["name"], first)

	def test_amounts_are_in_rupees_to_two_decimals_half_up(self):
		self.rate(1.75)
		deal = self.deal(
			[
				self.agent_row(33.33),
				self.partner_row(33.33),
				{**COMPANY, "percent": 33.34},
			],
			price=3333333.33,
			deal_date="2026-03-15",
		)
		as_user("company_admin")
		deals.approve_splits(deal)
		payout = self.payout_of(deal)
		# 3333333.33 * 1.75% = 58333.33 (to the paisa); 33.33% of that is 19442.498889, so 19442.50.
		self.assertEqual((payout.commission_total, payout.commission_due), (58333.33, 19442.5))
		rate = {"rate_type": "Percentage", "value": 1.75}
		self.assertEqual(
			commissions.partner_due(3333333.33, rate, 33.33), (Decimal("58333.33"), Decimal("19442.50"))
		)

	def test_a_deal_without_a_channel_partner_share_makes_no_payout(self):
		self.rate(2)
		name = self.deal([self.agent_row(70), {**COMPANY, "percent": 30}], deal_date="2026-03-15")
		as_user("company_admin")
		deals.approve_splits(name)
		self.assertEqual(frappe.db.count("Commission Payout", {"deal": name}), 0)
		self.assertEqual(commissions.waiting_deals(), [])

	def test_a_pending_deal_makes_no_payout_and_approving_twice_makes_one(self):
		self.rate(2)
		name = self.deal(deal_date="2026-03-15")
		self.assertIsNone(self.payout_of(name))
		as_user("company_admin")
		deals.approve_splits(name)
		deals.reopen_splits(name)
		deals.approve_splits(name)
		self.assertEqual(frappe.db.count("Commission Payout", {"deal": name}), 1)

	def test_a_reopened_split_that_is_corrected_works_a_due_payout_out_again(self):
		self.rate(2)
		deal = self.approved_deal(share=20)
		as_user("company_admin")
		deals.reopen_splits(deal)
		deals.save_deal(
			{"splits": [self.agent_row(40), self.partner_row(30), {**COMPANY, "percent": 30}]}, name=deal
		)
		deals.approve_splits(deal)
		self.assertEqual(self.payout_of(deal).commission_due, 60000.0)

	def test_a_payout_that_has_moved_on_is_not_worked_out_again(self):
		self.rate(2)
		deal = self.approved_deal(share=20)
		payout = self.payout_of(deal)
		self.move(payout, "Approved")
		as_user("company_admin")
		deals.reopen_splits(deal)
		deals.save_deal(
			{"splits": [self.agent_row(40), self.partner_row(30), {**COMPANY, "percent": 30}]}, name=deal
		)
		deals.approve_splits(deal)
		self.assertEqual(self.payout_of(deal).commission_due, 40000.0)


class TestWaitingForARate(CommissionCase):
	"""SOS-P7-04: an approved deal with no rate in force waits, and gets its payout when a rate is added."""

	def test_a_deal_approved_before_any_rate_waits_and_the_rate_makes_its_payout(self):
		deal = self.approved_deal(deal_date="2026-03-15")
		self.assertIsNone(self.payout_of(deal))
		waiting = commissions.commission_overview()["waiting"]
		self.assertEqual([(w["deal"], w["partner_firm"]) for w in waiting], [(deal, self.firm)])
		made = commissions.save_commission_rate(
			{"project": self.project, "rate_type": "Percentage", "value": 2, "start_date": "2026-01-01"}
		)
		self.assertEqual(self.payout_of(deal).name, made["payouts_made"][0])
		self.assertEqual(made["waiting"], [])

	def test_a_rate_that_starts_after_the_booking_date_does_not_apply_to_it(self):
		deal = self.approved_deal(deal_date="2026-03-15")
		commissions.save_commission_rate(
			{"project": self.project, "rate_type": "Percentage", "value": 2, "start_date": "2026-06-01"}
		)
		self.assertIsNone(self.payout_of(deal))
		self.assertEqual(len(commissions.commission_overview()["waiting"]), 1)

	def test_a_deal_for_a_property_has_no_project_so_it_waits_with_that_reason(self):
		as_user("company_admin")
		name = deals.save_deal(
			{
				"client": self.client_name,
				"property": self.property.name,
				"price": 5000000,
				"splits": [self.partner_row(50), {**COMPANY, "percent": 50}],
			}
		)["name"]
		deals.approve_splits(name)
		waiting = commissions.commission_overview()["waiting"]
		self.assertIn("no project", waiting[0]["reason"])

	def test_create_missing_payouts_makes_them_and_runs_again_safely(self):
		deal = self.approved_deal()
		self.assertEqual(commissions.create_missing_payouts()["payouts_made"], [])
		# A rate made behind the API's back (the Desk is closed to customers, so a patch or a test does this).
		frappe.get_doc(
			{
				"doctype": "Commission Rate",
				"project": self.project,
				"rate_type": "Percentage",
				"value": 2,
				"start_date": "2026-01-01",
			}
		).insert(ignore_permissions=True)
		self.assertEqual(len(commissions.create_missing_payouts()["payouts_made"]), 1)
		self.assertEqual(commissions.create_missing_payouts()["payouts_made"], [])
		self.assertTrue(self.payout_of(deal))


class TestRateRules(CommissionCase):
	"""SOS-P7-04: what a rate may be, and that it is kept."""

	def test_bad_rates_are_refused(self):
		for bad in (
			{"value": 0},
			{"value": -1},
			{"value": 101},
			{"rate_type": "Per square foot"},
			{"start_date": None},
			{"project": "no-such-project"},
			{"partner_firm": "no-such-firm"},
		):
			values = {
				"project": self.project,
				"rate_type": "Percentage",
				"value": 2,
				"start_date": "2026-01-01",
				**bad,
			}
			with self.assertRaises(frappe.ValidationError, msg=str(bad)):
				commissions.save_commission_rate(values)
		self.assertEqual(frappe.db.count("Commission Rate", {"project": self.project}), 0)

	def test_a_fixed_amount_may_be_above_a_hundred(self):
		self.rate(250000, rate_type="Fixed amount")
		self.assertEqual(frappe.db.count("Commission Rate", {"project": self.project}), 1)

	def test_two_rates_may_not_start_on_the_same_day_for_the_same_project_and_firm(self):
		self.rate(2)
		with self.assertRaises(frappe.ValidationError):
			self.rate(3)
		self.rate(3, firm=self.firm)  # a firm's own rate on that day is another rate

	def test_a_rate_is_not_changed_or_deleted(self):
		name = self.rate(2)
		doc = frappe.get_doc("Commission Rate", name)
		doc.value = 9
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Commission Rate", name, force=True)
		self.assertEqual(frappe.db.get_value("Commission Rate", name, "value"), 2)

	def test_a_rate_is_set_by_a_company_admin_only(self):
		for who in ("agent", "sales_manager", "client", "platform_admin"):
			as_user(who)
			with self.assertRaises(frappe.PermissionError, msg=who):
				commissions.save_commission_rate(
					{
						"project": self.project,
						"rate_type": "Percentage",
						"value": 2,
						"start_date": "2026-01-01",
					}
				)
		self.as_partner()
		with self.assertRaises(frappe.PermissionError):
			commissions.commission_overview()


class TestPayoutStatus(CommissionCase):
	"""SOS-P7-04: Due, Approved, Paid or On hold, each change logged, nothing deleted."""

	def setUp(self):
		super().setUp()
		self.rate(2)
		self.deal_name = self.approved_deal()
		self.payout = self.payout_of(self.deal_name)

	def test_a_payout_goes_from_due_to_approved_to_paid_with_its_reference_and_date(self):
		self.move(self.payout, "Approved")
		doc = self.payout_of(self.deal_name)
		self.assertEqual((doc.status, doc.approved_by), ("Approved", frappe.session.user))
		self.assertTrue(doc.approved_on)
		self.move(self.payout, "Paid", payment_reference="UTR704001", paid_on="2026-04-02")
		doc = self.payout_of(self.deal_name)
		self.assertEqual(
			(doc.status, doc.payment_reference, str(doc.paid_on)), ("Paid", "UTR704001", "2026-04-02")
		)

	def test_paying_needs_the_reference_and_the_date_and_a_date_that_is_not_in_the_future(self):
		self.move(self.payout, "Approved")
		for bad in (
			{},
			{"payment_reference": "UTR1"},
			{"paid_on": "2026-04-02"},
			{"payment_reference": "UTR1", "paid_on": "2999-01-01"},
		):
			with self.assertRaises(frappe.ValidationError, msg=str(bad)):
				self.move(self.payout, "Paid", **bad)
		self.assertEqual(self.payout_of(self.deal_name).status, "Approved")

	def test_a_payout_may_not_skip_a_status_or_go_back(self):
		with self.assertRaises(frappe.ValidationError):
			self.move(self.payout, "Paid", payment_reference="UTR1", paid_on="2026-04-02")
		with self.assertRaises(frappe.ValidationError):
			self.move(self.payout, "Cancelled")
		self.move(self.payout, "Approved")
		with self.assertRaises(frappe.ValidationError):
			self.move(self.payout, "Due")

	def test_a_payout_is_put_on_hold_with_a_reason_and_goes_back_to_where_it_was(self):
		with self.assertRaises(frappe.ValidationError):
			self.move(self.payout, "On hold")
		self.move(self.payout, "Approved")
		self.move(self.payout, "On hold", reason="Waiting for the agreement copy")
		doc = self.payout_of(self.deal_name)
		self.assertEqual(
			(doc.status, doc.hold_reason, doc.held_from),
			("On hold", "Waiting for the agreement copy", "Approved"),
		)
		with self.assertRaises(frappe.ValidationError):
			self.move(self.payout, "Due")
		self.move(self.payout, "Approved")
		doc = self.payout_of(self.deal_name)
		self.assertEqual((doc.status, doc.hold_reason, doc.held_from), ("Approved", None, None))

	def test_a_due_payout_held_goes_back_to_due(self):
		self.move(self.payout, "On hold", reason="Query on the booking")
		self.move(self.payout, "Due")
		self.assertEqual(self.payout_of(self.deal_name).status, "Due")

	def test_a_paid_payout_is_final(self):
		self.move(self.payout, "Approved")
		self.move(self.payout, "Paid", payment_reference="UTR704002", paid_on="2026-04-02")
		for to in ("Due", "Approved", "On hold"):
			with self.assertRaises(frappe.ValidationError, msg=to):
				self.move(self.payout, to, reason="x")
		doc = self.payout_of(self.deal_name)
		doc.payment_reference = "OTHER"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_the_figures_are_worked_out_and_cannot_be_typed(self):
		doc = self.payout_of(self.deal_name)
		doc.commission_due = 1
		with self.assertRaises(frappe.ValidationError):
			doc.save()
		self.assertEqual(self.payout_of(self.deal_name).commission_due, 40000.0)

	def test_nothing_is_deleted(self):
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Commission Payout", self.payout.name, force=True)
		self.assertTrue(frappe.db.exists("Commission Payout", self.payout.name))

	def test_every_change_is_logged_with_who_and_what(self):
		"""Frappe writes its change log (a Version) on every save of a tracked DocType, but not while tests run,
		so this test saves with the log on and reads it back."""
		doc = frappe.get_doc("Commission Payout", self.payout.name)
		doc.status = "Approved"
		doc._save(ignore_version=False)
		versions = frappe.get_all(
			"Version",
			filters={"ref_doctype": "Commission Payout", "docname": self.payout.name},
			fields=["owner", "data"],
		)
		self.assertEqual(len(versions), 1)
		self.assertIn("Approved", versions[0].data)
		self.assertEqual(versions[0].owner, frappe.session.user)
		self.assertEqual(
			(
				frappe.get_meta("Commission Payout").track_changes,
				frappe.get_meta("Commission Rate").track_changes,
			),
			(1, 1),
		)

	def test_an_agent_and_a_partner_may_not_move_a_payout(self):
		as_user("agent")
		with self.assertRaises(frappe.PermissionError):
			commissions.move_payout(self.payout.name, "Approved")
		self.as_partner()
		with self.assertRaises(frappe.PermissionError):
			commissions.move_payout(self.payout.name, "Approved")
		self.assertEqual(self.payout_of(self.deal_name).status, "Due")


class TestStatements(CommissionCase):
	"""SOS-P7-04: a partner sees their own payouts and statement; a Company Admin exports one, logged."""

	def setUp(self):
		super().setUp()
		self.rate(2)
		self.other = self.make_firm("p704_other@example.com", "P704 Other Firm")
		self.mine_march = self.approved_deal(deal_date="2026-03-15")
		self.mine_june = self.approved_deal(deal_date="2026-06-10", share=40)
		self.theirs = self.approved_deal(deal_date="2026-03-20", firm=self.other)
		self.payout_march = self.payout_of(self.mine_march)
		self.move(self.payout_march, "Approved")
		self.move(self.payout_march, "Paid", payment_reference="UTR704003", paid_on="2026-04-02")

	def statement(self, **kw):
		self.as_partner()
		return commissions.partner_commission(**kw)

	def test_a_partner_sees_their_own_payouts_for_a_date_range_and_nobody_elses(self):
		every = self.statement(from_date="2026-01-01", to_date="2026-12-31")
		self.assertEqual({r["deal"] for r in every["rows"]}, {self.mine_march, self.mine_june})
		self.assertEqual(every["firm"], self.firm)
		self.assertEqual(every["totals"]["by_status"]["Paid"], 40000.0)
		self.assertEqual(every["totals"]["by_status"]["Due"], 80000.0)
		self.assertEqual((every["totals"]["total"], every["totals"]["count"]), (120000.0, 2))
		march = self.statement(from_date="2026-03-01", to_date="2026-03-31")
		self.assertEqual([r["deal"] for r in march["rows"]], [self.mine_march])
		self.assertEqual(march["rows"][0]["payment_reference"], "UTR704003")
		self.assertEqual(self.statement(from_date="2025-01-01", to_date="2025-12-31")["rows"], [])

	def test_the_other_firm_sees_only_its_own_payout(self):
		self.as_partner("p704_other@example.com")
		rows = commissions.partner_commission(from_date="2026-01-01", to_date="2026-12-31")["rows"]
		self.assertEqual([r["deal"] for r in rows], [self.theirs])
		names = frappe.get_list("Commission Payout", pluck="name")
		self.assertEqual(names, [self.payout_of(self.theirs, self.other).name])

	def test_a_partner_cannot_read_another_firms_payout_or_change_their_own(self):
		self.as_partner()
		theirs = frappe.get_doc("Commission Payout", self.payout_of(self.theirs, self.other).name)
		self.assertFalse(theirs.has_permission("read"))
		mine = frappe.get_doc("Commission Payout", self.payout_of(self.mine_june).name)
		self.assertTrue(mine.has_permission("read"))
		self.assertFalse(mine.has_permission("write"))
		self.assertFalse(mine.has_permission("delete"))

	def test_nobody_else_reads_a_payout_through_the_list(self):
		for who in ("agent", "sales_manager", "client", "platform_admin"):
			as_user(who)
			with self.assertRaises(frappe.PermissionError, msg=who):
				frappe.get_list("Commission Payout", pluck="name")

	def test_a_partner_login_with_no_firm_has_an_empty_statement(self):
		as_user("channel_partner")
		result = commissions.partner_commission()
		self.assertEqual((result["firm"], result["rows"], result["totals"]["total"]), (None, [], 0.0))

	def test_the_commission_panel_of_the_partner_report_is_switched_on(self):
		from sellos.crm import partner_panels

		self.as_partner()
		panel = partner_panels.commission("2026-01-01", "2026-12-31", firm=self.firm, user=PARTNER_MAIL)
		self.assertEqual(len(panel["rows"]), 2)
		self.assertEqual({s["label"]: s["value"] for s in panel["stats"]}["Paid"], 40000.0)

	def test_a_company_admin_exports_a_partners_statement_and_it_is_logged(self):
		as_user("company_admin")
		result = commissions.export_partner_statement(self.firm, "2026-01-01", "2026-12-31")
		self.assertEqual(result["totals"]["total"], 120000.0)
		table = list(csv.reader(io.StringIO(result["csv"])))
		self.assertEqual(len(table), 3)
		self.assertEqual(table[0][-3:], ["Status", "Payment reference", "Paid on"])
		self.assertEqual(table[1][-3:], ["Paid", "UTR704003", "2026-04-02"])
		self.assertEqual(result["filename"], f"commission-statement-{self.firm}-2026-01-01-2026-12-31.csv")
		log = frappe.get_doc("Commission Statement Export", result["export_log"])
		self.assertEqual(
			(log.partner_firm, log.row_count, log.total_due, log.exported_by),
			(self.firm, 2, 120000.0, frappe.session.user),
		)
		commissions.export_partner_statement(self.firm, "2026-03-01", "2026-03-31")
		self.assertEqual(frappe.db.count("Commission Statement Export", {"partner_firm": self.firm}), 2)

	def test_the_export_masks_the_firms_phone_number(self):
		number = phones.in_mobile(7041)
		frappe.db.set_value("Channel Partner Firm", self.firm, "phone", number)
		as_user("company_admin")
		result = commissions.export_partner_statement(self.firm, "2026-01-01", "2026-12-31")
		self.assertNotIn(number[-10:], str(result))
		self.assertTrue(result["firm_phone_masked"])

	def test_an_export_cell_that_looks_like_a_formula_is_made_plain_text(self):
		self.assertEqual(commissions._safe("=1+1"), "'=1+1")
		self.assertEqual(commissions._safe("-5"), "'-5")
		self.assertEqual(commissions._safe("UTR1"), "UTR1")

	def test_only_a_company_admin_exports_and_the_raw_doctype_export_is_nobodys(self):
		for who in ("agent", "sales_manager", "client", "platform_admin"):
			as_user(who)
			with self.assertRaises(frappe.PermissionError, msg=who):
				commissions.export_partner_statement(self.firm)
		self.as_partner()
		with self.assertRaises(frappe.PermissionError):
			commissions.export_partner_statement(self.firm)
		for doctype in ("Commission Rate", "Commission Payout", "Commission Statement Export"):
			for perm in frappe.get_meta(doctype).permissions:
				self.assertFalse(perm.export or perm.delete or perm.share, f"{doctype} {perm.role}")

	def test_a_partner_statement_method_refuses_a_login_that_is_not_a_partner(self):
		as_user("agent")
		with self.assertRaises(frappe.PermissionError):
			commissions.partner_commission()
		self.assertIn(CHANNEL_PARTNER, frappe.get_roles(PARTNER_MAIL))

	def test_an_export_log_is_never_changed_or_deleted(self):
		as_user("company_admin")
		log = frappe.get_doc(
			"Commission Statement Export",
			commissions.export_partner_statement(self.firm, "2026-01-01", "2026-12-31")["export_log"],
		)
		log.row_count = 99
		with self.assertRaises(frappe.PermissionError):
			log.save()
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Commission Statement Export", log.name, force=True)


class TestSeedAndGateFixtures(CommissionCase):
	"""SOS-P7-04: the regression seed adds a rate and a Due payout, and the gate fixture for the browser spec makes
	each stage and cleans up."""

	def test_the_seed_adds_a_rate_and_a_due_payout_and_a_second_run_changes_nothing(self):
		from sellos.inventory.test_p4_06_deal import TestRegressionSeed
		from sellos.tests import ui_fixtures

		TestRegressionSeed.prerequisites(self)
		agent = email("agent")
		project = frappe.db.get_value("Project", {"project_name": "Regression Heights"}, "name")
		rates_before = frappe.db.count("Commission Rate", {"project": project}) if project else 0
		for _run in (1, 2):
			ui_fixtures._seed_deals(email("company_admin"), agent)
		self.assertEqual(frappe.db.count("Commission Rate", {"project": project}), max(rates_before, 1))
		if not rates_before:
			rate = frappe.get_doc("Commission Rate", {"project": project})
			self.assertEqual(
				(rate.rate_type, rate.value, str(rate.start_date)), ("Percentage", 2, "2020-01-01")
			)
		client = frappe.db.get_value("Client", {"client_name": "Regression Deal Buyer One"})
		deal = frappe.db.get_value("Deal", {"client": client})
		self.assertEqual(frappe.db.count("Commission Payout", {"deal": deal}), 1)
		payout = frappe.get_doc("Commission Payout", {"deal": deal})
		self.assertEqual(
			(payout.status, payout.commission_total, payout.commission_due), ("Due", 200000.0, 40000.0)
		)

	def test_the_gate_fixture_makes_each_stage_and_remove_takes_it_all_away(self):
		from unittest.mock import patch

		from sellos.tests import ui_fixtures

		commit = patch.object(
			frappe.db, "commit"
		)  # the fixtures commit for the browser: not inside this test
		commit.start()
		self.addCleanup(commit.stop)
		for stage, status, count in (("waiting", None, 0), ("due", "Due", 1), ("paid", "Paid", 1)):
			made = ui_fixtures.make_gate_commission(stage)
			rows = frappe.get_all(
				"Commission Payout", filters={"deal": made["deal"]}, fields=["status", "commission_due"]
			)
			self.assertEqual(len(rows), count, stage)
			if count:
				self.assertEqual((rows[0].status, rows[0].commission_due), (status, 32000.0), stage)
			ui_fixtures.remove_gate_commission()
			self.assertEqual(frappe.db.count("Deal", {"name": made["deal"]}), 0)
			self.assertEqual(frappe.db.count("Commission Payout", {"deal": made["deal"]}), 0)
			self.assertFalse(frappe.db.exists("Project", {"project_name": made["project"]}))
			self.assertFalse(frappe.db.exists("Channel Partner Firm", {"firm_name": made["firm"]}))
