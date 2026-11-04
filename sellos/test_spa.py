import unittest

from sellos.spa import SellOSPage


class TestSellOSPage(unittest.TestCase):
	def test_renders_the_app_route_and_everything_under_it(self):
		for path in ("sellos", "/sellos/", "sellos/leads/L1"):
			self.assertTrue(SellOSPage(path).can_render(), path)

	def test_ignores_other_routes(self):
		for path in ("login", "app/user", "sellos2", "crm/sellos"):
			self.assertFalse(SellOSPage(path).can_render(), path)


class TestCompanyBranding(unittest.TestCase):
	def test_branding_comes_from_settings(self):
		import frappe

		from sellos.spa import get_company_branding

		settings = frappe.get_doc("SellOS Settings")
		old = (settings.company_name, settings.logo, settings.brand_color)
		try:
			settings.company_name = "Pandya Realtors"
			settings.brand_color = "#112233"
			settings.save()
			frappe.clear_document_cache("SellOS Settings", "SellOS Settings")
			branding = get_company_branding()
			self.assertEqual(branding["name"], "Pandya Realtors")
			self.assertEqual(branding["brand_color"], "#112233")
		finally:
			settings.company_name, settings.logo, settings.brand_color = old
			settings.save()
			frappe.db.rollback()
