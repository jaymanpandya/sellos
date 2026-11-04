"""Who may see which leads (P1.04). P1.06 creates the Lead DocType and these hooks apply to it.

* Platform Admin, Company Admin and System Manager see every lead of the site.
* An Agent or Channel Partner sees only the leads they own or are assigned, plus leads shared with
  them through Frappe's normal share.
* A Client sees no leads.
"""

import frappe

from sellos.access.roles import AGENT, CHANNEL_PARTNER, COMPANY_ADMIN, PLATFORM_ADMIN

SEES_ALL = frozenset({PLATFORM_ADMIN, COMPANY_ADMIN, "System Manager"})
SEES_OWN = frozenset({AGENT, CHANNEL_PARTNER})
DOCTYPE = "Lead"


def scope_for(roles) -> str:
	"""'all', 'own' or 'none' for a set of roles. The widest scope wins."""
	roles = set(roles)
	if roles & SEES_ALL:
		return "all"
	if roles & SEES_OWN:
		return "own"
	return "none"


def get_permission_query_conditions(user=None, doctype=DOCTYPE):
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	scope = scope_for(frappe.get_roles(user))
	if scope == "all":
		return ""
	if scope == "none":
		return "1=0"
	quoted_user = frappe.db.escape(user)
	table = f"`tab{doctype}`"
	return (
		f"({table}.`owner` = {quoted_user} or {table}.`assigned_to` = {quoted_user}"
		f" or {table}.`name` in (select `share_name` from `tabDocShare`"
		f" where `user` = {quoted_user} and `share_doctype` = {frappe.db.escape(doctype)} and `read` = 1))"
	)


def has_permission(doc, ptype=None, user=None, **kwargs):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	scope = scope_for(frappe.get_roles(user))
	if scope == "all":
		return True
	if scope == "none":
		return False
	if user in (doc.get("owner"), doc.get("assigned_to")):
		return True
	return bool(
		frappe.db.exists(
			"DocShare",
			{"user": user, "share_doctype": doc.doctype, "share_name": doc.name, **_share_flag(ptype)},
		)
	)


def _share_flag(ptype):
	# Sharing grants read, write and so on separately. Anything else needs read.
	flag = ptype if ptype in ("read", "write", "share", "submit") else "read"
	return {flag: 1}
