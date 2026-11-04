import unittest

from sellos.spa import SellOSPage


class TestSellOSPage(unittest.TestCase):
	def test_renders_the_app_route_and_everything_under_it(self):
		for path in ("sellos", "/sellos/", "sellos/leads/L1"):
			self.assertTrue(SellOSPage(path).can_render(), path)

	def test_ignores_other_routes(self):
		for path in ("login", "app/user", "sellos2", "crm/sellos"):
			self.assertFalse(SellOSPage(path).can_render(), path)
