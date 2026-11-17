"""SOS-P2-03: the call router. A table of numbers and purposes against the expected account and
series. Calls are placed through the fake provider; none reaches Plivo."""

import frappe
from frappe.tests import IntegrationTestCase

from sellos.telephony import router
from sellos.telephony.base import ProviderError
from sellos.telephony.provider import FakeProvider
from sellos.tests import phones

LANDLINE = f"{phones.in_mobile(3300)[:3]}22{phones.in_mobile(3300)[-8:]}"


class TestCallRouter(IntegrationTestCase):
	"""SOS-P2-03: +91 goes through the India account and 022; other countries are refused."""

	def test_routing_table(self):
		table = [
			(phones.in_mobile(3301), "Service", "india", "022", ""),
			(phones.in_mobile(3302), "Transactional", "india", "022", ""),
			(phones.in_mobile(3303), "transactional", "india", "022", ""),
			(phones.in_mobile(3304), "Promotional", "india", "022", "promotional"),
		]
		for number, purpose, account, series, warning in table:
			with self.subTest(number=number, purpose=purpose):
				route = router.route_call(number, purpose, from_number=LANDLINE)
				self.assertEqual(route.account, account)
				self.assertEqual(route.series, series)
				self.assertEqual(route.from_number, LANDLINE)
				self.assertEqual(route.to_number, number)
				self.assertEqual(route.purpose, purpose.title())
				if warning:
					self.assertIn(warning, route.warning)
				else:
					self.assertEqual(route.warning, "")

	def test_other_country_codes_are_refused(self):
		for number in (
			phones.au_mobile(3311),
			phones.ae_mobile(3312),
			"+1" + phones.in_mobile(3313)[-10:],
			"+44" + phones.in_mobile(3314)[-10:],
		):
			with self.subTest(number=number):
				with self.assertRaises(ProviderError) as ctx:
					router.route_call(number, "Service", from_number=LANDLINE)
				self.assertIn("Indian numbers", str(ctx.exception))
				self.assertNotIn(number, str(ctx.exception))

	def test_bad_numbers_and_purposes_are_refused(self):
		indian = phones.in_mobile(3321)
		cases = [
			(indian[-10:], "Service", "country code"),
			(indian[:-1], "Service", "valid Indian mobile"),
			(indian, "", "purpose"),
			(indian, "Marketing", "purpose"),
		]
		for number, purpose, text in cases:
			with self.subTest(number=number, purpose=purpose):
				with self.assertRaises(ProviderError) as ctx:
					router.route_call(number, purpose, from_number=LANDLINE)
				self.assertIn(text, str(ctx.exception))

	def test_number_with_spaces_is_routed(self):
		number = phones.in_mobile(3331)
		spaced = f"{number[:3]} {number[3:8]} {number[8:]}"
		self.assertEqual(router.route_call(spaced, "Service", from_number=LANDLINE).to_number, number)

	def test_the_022_number_comes_from_settings(self):
		settings = frappe.get_doc("Telephony Settings")
		old = settings.phone_number
		self.addCleanup(self._restore, old)
		settings.phone_number = ""
		settings.save(ignore_permissions=True)
		with self.assertRaises(ProviderError) as ctx:
			router.route_call(phones.in_mobile(3341), "Service")
		self.assertIn("022 number", str(ctx.exception))
		settings.phone_number = LANDLINE
		settings.save(ignore_permissions=True)
		self.assertEqual(router.route_call(phones.in_mobile(3341), "Service").from_number, LANDLINE)

	def _restore(self, old):
		settings = frappe.get_doc("Telephony Settings")
		settings.phone_number = old
		settings.save(ignore_permissions=True)

	def test_promotional_call_is_placed_with_a_warning(self):
		provider = FakeProvider("FAKEOK1", "token")
		number = phones.in_mobile(3351)
		route, placed = router.place_routed_call(
			provider, number, "Promotional", "https://a.example/a", from_number=LANDLINE
		)
		self.assertTrue(placed.call_id.startswith("fake-"))
		self.assertEqual(route.purpose, "Promotional")
		self.assertIn("promotional", route.warning)

	def test_other_country_is_not_placed(self):
		provider = FakeProvider("FAKEOK1", "token")
		with self.assertRaises(ProviderError):
			router.place_routed_call(
				provider, phones.au_mobile(3361), "Service", "https://a.example/a", from_number=LANDLINE
			)
