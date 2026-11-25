"""Unit tests of the seed's history rules (SOS-LOOP): earliest first, never later than the next event, never in the
future. They need no bench: the planning functions are pure."""

import unittest
from datetime import date, datetime, timedelta

from sellos.testing import demo_history as h

NOW = datetime(2026, 11, 26, 12, 0)
CREATED = datetime(2026, 9, 1, 9, 0)


class TestChain(unittest.TestCase):
	def test_keeps_order_and_never_goes_before_the_floor_or_after_the_ceiling(self):
		times = [CREATED - timedelta(days=1), CREATED, NOW + timedelta(days=3)]
		out = h.chain(times, CREATED, NOW)
		self.assertEqual(out, sorted(out))
		self.assertGreaterEqual(out[0], CREATED)
		self.assertLessEqual(out[-1], NOW)

	def test_a_later_time_is_never_moved_earlier_than_its_predecessor(self):
		a = CREATED + timedelta(days=5)
		out = h.chain([a, CREATED + timedelta(days=2)], CREATED, NOW)
		self.assertLess(out[0], out[1])

	def test_running_it_twice_changes_nothing(self):
		once = h.chain([CREATED, CREATED, CREATED], CREATED, NOW)
		self.assertEqual(h.chain(once, CREATED, NOW), once)


class TestConsent(unittest.TestCase):
	def test_consent_is_recorded_before_the_first_event_and_not_before_the_lead(self):
		first_call = CREATED + timedelta(hours=3)
		late = CREATED + timedelta(days=9)
		early = CREATED - timedelta(days=2)
		(a, b), stop = h.plan_consent(CREATED, first_call, [early, late], None, NOW)
		self.assertGreaterEqual(a, CREATED)
		self.assertLess(a, first_call)
		self.assertLess(a, b)
		self.assertIsNone(stop)

	def test_an_opt_out_comes_after_the_consent_it_ends_and_never_in_the_future(self):
		first_call = CREATED + timedelta(hours=3)
		(a,), stop = h.plan_consent(CREATED, first_call, [CREATED + timedelta(days=4)], CREATED, NOW)
		self.assertGreater(stop, a)
		(a,), stop = h.plan_consent(CREATED, first_call, [CREATED], NOW + timedelta(days=2), NOW)
		self.assertLess(stop, NOW)

	def test_a_lead_with_no_event_yet_keeps_its_consent_at_creation(self):
		(a,), _ = h.plan_consent(CREATED, None, [CREATED + timedelta(days=2)], None, NOW)
		self.assertEqual(a, CREATED)

	def test_it_is_stable_on_a_second_run(self):
		first_call = CREATED + timedelta(hours=3)
		args = (CREATED, first_call, [CREATED + timedelta(days=4)], CREATED + timedelta(days=30), NOW)
		once = h.plan_consent(*args)
		again = h.plan_consent(CREATED, first_call, once[0], once[1], NOW)
		self.assertEqual(once, again)


class TestDeal(unittest.TestCase):
	def test_the_deal_is_approved_after_it_is_made_and_the_payout_after_the_approval(self):
		made, approved, payouts = h.plan_deal(
			date(2026, 10, 1), None, True, NOW, [(True, date(2026, 10, 10))]
		)
		self.assertEqual(made, datetime(2026, 10, 1, 10, 0))
		self.assertGreater(approved, made)
		p_made, p_approved, paid = payouts[0]
		self.assertGreaterEqual(p_made, approved)
		self.assertGreater(p_approved, p_made)
		self.assertGreaterEqual(paid, p_approved.date())

	def test_a_deal_comes_after_the_leads_earlier_activity(self):
		earlier = datetime(2026, 10, 1, 15, 0)
		made, approved, _ = h.plan_deal(date(2026, 10, 1), earlier, True, NOW, [])
		self.assertGreater(made, earlier)
		self.assertGreater(approved, made)

	def test_nothing_is_in_the_future_and_an_unapproved_deal_has_no_approval(self):
		_made, approved, payouts = h.plan_deal(
			date(2026, 11, 26), None, True, NOW, [(True, date(2026, 12, 5))]
		)
		self.assertLessEqual(approved, NOW)
		for _p_made, p_approved, paid in payouts:
			self.assertLessEqual(p_approved, NOW)
			self.assertLessEqual(paid, NOW.date())
		_made, approved, payouts = h.plan_deal(date(2026, 10, 1), None, False, NOW, [(False, None)])
		self.assertIsNone(approved)
		self.assertIsNone(payouts[0][1])
		self.assertIsNone(payouts[0][2])

	def test_it_is_stable_on_a_second_run(self):
		args = (date(2026, 10, 1), None, True, NOW, [(True, date(2026, 10, 10))])
		self.assertEqual(h.plan_deal(*args), h.plan_deal(*args))
