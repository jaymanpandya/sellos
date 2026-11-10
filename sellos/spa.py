import os
import re

import frappe
from frappe import _
from frappe.website.page_renderers.base_renderer import BaseRenderer

from sellos.config.setup_wizard import is_setup_complete

SPA_ROUTE = "sellos"
TAB_ICONS = re.compile(r"(<!-- tab-icons -->).*?(<!-- /tab-icons -->)", re.DOTALL)


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

	with open(path, encoding="utf-8") as f:  # fixed path inside the app, no user input  # nosemgrep
		source = f.read()

	source = set_tab_icon(source, get_company_branding()["logo"])

	# The source is the built app page from this repository, not user input.
	return frappe.render_template(source, {"boot": get_boot()}, safe_render=False)  # nosemgrep


def set_tab_icon(source: str, logo: str) -> str:
	"""Put the company logo in the tab icon. With no logo the built page keeps the SellOS icon."""
	if not logo:
		return source
	link = f'<link rel="icon" href="{frappe.utils.escape_html(logo)}" />'
	return TAB_ICONS.sub(lambda m: f"{m.group(1)}\n\t\t{link}\n\t\t{m.group(2)}", source, count=1)


def get_boot():
	user = frappe.get_cached_doc("User", frappe.session.user)
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # page renders are GET requests, so the token is saved by hand  # nosemgrep

	return {
		"csrf_token": csrf_token,
		"sellos_boot": {
			"user": frappe.session.user,
			"full_name": user.full_name,
			"roles": frappe.get_roles(),
			"company": get_company_branding(),
			"setup_complete": is_setup_complete(),
		},
	}


def get_company_branding():
	"""Company name, logo and colour from SellOS Settings (P0.10). The wizard fills them in (P1.03)."""
	# Read straight from the single doctype: the branding is public to every signed in user.
	settings = frappe.get_cached_doc("SellOS Settings")
	return {
		"name": settings.company_name or "",
		"logo": settings.logo or "",
		"brand_color": settings.brand_color or "",
	}
