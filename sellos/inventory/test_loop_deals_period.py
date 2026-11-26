"""SOS-LOOP: the Deals page's period switch (day, week, month, year to date), its totals, and a deal with 1, 2
and 3 channel partner splits. Today is fixed to Wednesday 25 November 2026."""

import datetime
from unittest.mock import patch

import frappe

from sellos.access.matrix import MATRIX
from sellos.inventory import deals
from sellos.inventory.test_p4_06_deal import COMPANY, DealCase

TODAY = datetime.date(2026, 11, 25)  # a Wednesday: the week began Monday the 23rd


class TestDealPeriods(DealCase):
	def setUp(self):
		super().setUp()
		patcher = patch.object(deals, "_today", return_value=TODAY)
		patcher.start()
		self.addCleanup(patcher.stop)

	def dated(self, day, commission=100000):
		return self.deal(
			[self.agent_row(50), {**COMPANY, "percent": 50}], deal_date=str(day), commission_amount=commission
		)

	def names(self, period):
		as_user_admin()
		return {d["name"] for d in deals.deal_overview(period=period)["deals"]}

	def test_the_dates_of_each_period_end_today(self):
		cases = {
			"day": ("2026-11-25", "2026-11-25"),
			"week": ("2026-11-23", "2026-11-25"),
			"month": ("2026-11-01", "2026-11-25"),
			"year": ("2026-01-01", "2026-11-25"),
		}
		as_user_admin()
		for key, (start, end) in cases.items():
			period = deals.deal_overview(period=key)["period"]
			self.assertEqual((period["start"], period["end"]), (start, end), key)
		self.assertEqual(deals.deal_overview()["period"]["key"], "all")
		with self.assertRaises(frappe.ValidationError):
			deals.deal_overview(period="decade")

	def test_every_period_boundary_is_in_or_out_by_one_day(self):
		d = datetime.date
		made = {
			"today": self.dated(d(2026, 11, 25)),
			"yesterday": self.dated(d(2026, 11, 24)),  # Tuesday: this week, not today
			"monday": self.dated(d(2026, 11, 23)),  # the first day of the week
			"sunday_before": self.dated(d(2026, 11, 22)),  # last week, this month
			"first_of_month": self.dated(d(2026, 11, 1)),
			"last_of_october": self.dated(d(2026, 10, 31)),  # last month, this year
			"first_of_year": self.dated(d(2026, 1, 1)),
			"last_of_last_year": self.dated(d(2025, 12, 31)),
			"tomorrow": self.dated(d(2026, 11, 26)),  # not yet: a period ends today
		}
		self.assertEqual(self.names("day") & set(made.values()), {made["today"]})
		self.assertEqual(
			self.names("week") & set(made.values()), {made["today"], made["yesterday"], made["monday"]}
		)
		self.assertEqual(
			self.names("month") & set(made.values()),
			{made[k] for k in ("today", "yesterday", "monday", "sunday_before", "first_of_month")},
		)
		self.assertEqual(
			self.names("year") & set(made.values()),
			{made[k] for k in made if k not in ("last_of_last_year", "tomorrow")},
		)
		self.assertEqual(self.names("all") & set(made.values()), set(made.values()))

	def test_the_totals_follow_the_period(self):
		self.dated(datetime.date(2026, 11, 25), 100000)
		self.dated(datetime.date(2026, 11, 2), 300000)
		self.dated(datetime.date(2026, 3, 2), 500000)
		as_user_admin()
		self.assertEqual(deals.deal_overview(period="day")["totals"]["total_commission"], 100000)
		month = deals.deal_overview(period="month")["totals"]
		self.assertEqual(
			(month["count"], month["total_commission"], month["company_share"]), (2, 400000, 200000)
		)
		self.assertEqual(deals.deal_overview(period="year")["totals"]["total_commission"], 900000)

	def test_one_two_and_three_channel_partner_splits(self):
		second = self.make_firm("p406_partner2@example.com", "P406 Second Firm")
		third = self.make_firm("p406_partner3@example.com", "P406 Third Firm")
		one = self.deal([self.agent_row(40), self.partner_row(20), {**COMPANY, "percent": 40}])
		two = self.deal(
			[
				self.agent_row(30),
				self.partner_row(10),
				self.partner_row(15, second),
				{**COMPANY, "percent": 45},
			]
		)
		three = self.deal(
			[
				self.agent_row(20),
				self.partner_row(10),
				self.partner_row(10, second),
				self.partner_row(10, third),
				{**COMPANY, "percent": 50},
			]
		)
		none = self.deal([self.agent_row(60), {**COMPANY, "percent": 40}])
		self.assertEqual([len(self.row(n)["partner_splits"]) for n in (one, two, three, none)], [1, 2, 3, 0])
		self.assertEqual([self.row(n)["has_commission_split"] for n in (one, two, three, none)], [1, 1, 1, 0])
		row = self.row(two)
		self.assertEqual(
			[(p["party"], p["percent"], p["amount"]) for p in row["partner_splits"]],
			[("P406 Partner Firm", 10, 20000), ("P406 Second Firm", 15, 30000)],
		)
		self.assertEqual(
			(row["agent_share"], row["company_share"]),
			(
				{"percent": 30, "amount": 60000},
				{"percent": 45, "amount": 90000},
			),
		)
		as_user_admin()
		totals = deals.deal_overview()["totals"]
		# partners: 20% + 25% + 30% of 200000, the company 40% + 45% + 50% + 40% of 200000
		self.assertEqual(totals["partner_payout"], 40000 + 50000 + 60000)
		self.assertEqual(totals["company_share"], 80000 + 90000 + 100000 + 80000)

	def test_a_cancelled_deal_counts_for_nothing_in_the_totals(self):
		name = self.dated(TODAY, 100000)
		frappe.db.set_value("Deal", name, "deal_status", "Cancelled")
		as_user_admin()
		totals = deals.deal_overview(period="day")["totals"]
		self.assertEqual((totals["count"], totals["total_commission"]), (1, 0))

	def test_get_deal_returns_one_deal_of_any_date_and_is_for_the_company_admin_only(self):
		old = self.dated(datetime.date(2020, 1, 1))
		as_user_admin()
		self.assertEqual(deals.get_deal(old)["deal"]["name"], old)
		self.assertEqual(
			MATRIX["sellos.inventory.deals.get_deal"], MATRIX["sellos.inventory.deals.save_deal"]
		)


def as_user_admin():
	from sellos.crm.test_crm import as_user

	as_user("company_admin")
