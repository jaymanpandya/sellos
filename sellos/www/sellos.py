import frappe

no_cache = 1


def get_context(context):
	"""Serves every path under /sellos. The built app reads the boot data written here."""
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/sellos"
		raise frappe.Redirect

	user = frappe.get_cached_doc("User", frappe.session.user)
	context.boot = {
		"csrf_token": frappe.sessions.get_csrf_token(),
		"sellos_boot": {
			"user": frappe.session.user,
			"full_name": user.full_name,
			"roles": frappe.get_roles(),
			# Filled from the company profile once the setup wizard story (P1.03) exists.
			"company": {"name": frappe.local.site, "brand_color": ""},
		},
	}
	return context
