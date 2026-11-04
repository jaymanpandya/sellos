import os

import frappe
from frappe import _
from frappe.website.page_renderers.base_renderer import BaseRenderer

SPA_ROUTE = "sellos"


class SellOSPage(BaseRenderer):
	"""Serves the SellOS web app for /sellos and every path under it.

	Frappe asks each renderer in the page_renderer hook whether it can render a path before it runs
	its own page lookup, so this does not depend on the www folder being discovered.
	"""

	def can_render(self):
		return self.path == SPA_ROUTE or self.path.startswith(SPA_ROUTE + "/")

	def render(self):
		if frappe.session.user == "Guest":
			frappe.local.flags.redirect_location = f"/login?redirect-to=/{SPA_ROUTE}"
			raise frappe.Redirect

		return self.build_response(get_html(), headers={"Cache-Control": "no-store"})


def get_html():
	"""The built app page, with the boot data written into it."""
	path = os.path.join(frappe.get_app_path("sellos"), "www", "sellos.html")
	if not os.path.isfile(path):
		frappe.throw(_("The SellOS app has not been built. Run bench build --app sellos."))

	with open(path, encoding="utf-8") as f:
		source = f.read()

	return frappe.render_template(source, {"boot": get_boot()}, safe_render=False)


def get_boot():
	user = frappe.get_cached_doc("User", frappe.session.user)
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosemgrep: page renders are GET requests, so the token is saved by hand

	return {
		"csrf_token": csrf_token,
		"sellos_boot": {
			"user": frappe.session.user,
			"full_name": user.full_name,
			"roles": frappe.get_roles(),
			# Filled from the company profile once the setup wizard story (P1.03) exists.
			"company": {"name": frappe.local.site, "brand_color": ""},
		},
	}
