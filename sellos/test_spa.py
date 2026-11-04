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


class TestTabIconAndName(unittest.TestCase):
	"""SOS-P1-06A the tab icon is the company logo or the SellOS icon, never an empty data URL."""

	PAGE = '<head><!-- tab-icons -->\n<link rel="icon" href="/assets/sellos/frontend/sellos-favicon.svg" />\n<!-- /tab-icons --></head>'

	def test_the_logo_replaces_the_default_icon(self):
		from sellos.spa import set_tab_icon

		html = set_tab_icon(self.PAGE, "/files/logo.png")
		self.assertIn('href="/files/logo.png"', html)
		self.assertNotIn("sellos-favicon.svg", html)
		self.assertNotIn("data:,", html)

	def test_with_no_logo_the_default_icon_stays(self):
		from sellos.spa import set_tab_icon

		self.assertEqual(set_tab_icon(self.PAGE, ""), self.PAGE)

	def test_a_logo_cannot_break_out_of_the_attribute(self):
		from sellos.spa import set_tab_icon

		self.assertNotIn('"><script', set_tab_icon(self.PAGE, '"><script>x</script>'))

	def test_the_built_page_has_a_real_default_icon(self):
		import os

		import frappe

		path = os.path.join(frappe.get_app_path("sellos"), "www", "sellos.html")
		with open(path, encoding="utf-8") as f:  # nosemgrep: fixed path inside the app
			html = f.read()
		self.assertNotIn("data:,", html)
		self.assertIn("sellos-favicon.svg", html)

	def test_the_name_is_empty_not_the_site_when_settings_has_none(self):
		import frappe

		from sellos.spa import get_company_branding

		settings = frappe.get_doc("SellOS Settings")
		old = settings.company_name
		try:
			settings.company_name = ""
			settings.save()
			frappe.clear_document_cache("SellOS Settings", "SellOS Settings")
			self.assertEqual(get_company_branding()["name"], "")
		finally:
			settings.company_name = old
			settings.save()
			frappe.db.rollback()
