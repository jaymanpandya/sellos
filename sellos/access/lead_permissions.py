"""Who may see which CRM records (P1.04, extended in P1.06).

* Company Admin and System Manager see every record of the site.
* The Platform Admin sees no company CRM data. Support gets in through a time limited grant
  (P1.13), never by role: while the grant is active the user reads every record, and may change
  nothing. (Decided by Jayman, P1.06.)
* An Agent or Channel Partner sees only the leads they own or are assigned, plus leads shared with
  them through Frappe's normal share.
* Activities, tasks and site visits follow their lead. A client record follows the leads that use
  it, and a record the user created.
* A Client (the role) sees nothing.
"""

import frappe

from sellos.access.roles import AGENT, CHANNEL_PARTNER, COMPANY_ADMIN, PLATFORM_ADMIN
from sellos.access.support import has_support_access

SEES_ALL = frozenset({COMPANY_ADMIN, "System Manager"})
SEES_OWN = frozenset({AGENT, CHANNEL_PARTNER})
DOCTYPE = "Lead"
CLIENT_DOCTYPE = "Client"
LEAD_CHILDREN = ("Lead Activity", "Lead Task", "Site Visit", "Consent Record")
# What a support grant allows (P1.13). A missing permission type means read.
SUPPORT_PTYPES = frozenset({"read", "select", "print", "report"})


def scope_for(roles) -> str:
	"""'all', 'own' or 'none' for a set of roles. The widest scope wins."""
	roles = set(roles)
	if roles & SEES_ALL:
		return "all"
	if roles & SEES_OWN:
		return "own"
	return "none"


def _own_lead_sql(user) -> str:
	return _own_sql(user, "Lead")


def _own_sql(user, doctype) -> str:
	quoted_user = frappe.db.escape(user)
	table = f"`tab{doctype}`"
	return (
		f"({table}.`owner` = {quoted_user} or {table}.`assigned_to` = {quoted_user}"
		f" or {table}.`name` in (select `share_name` from `tabDocShare`"
		f" where `user` = {quoted_user} and `share_doctype` = {frappe.db.escape(doctype)} and `read` = 1))"
	)


def _conditions(user, build):
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	scope = _user_scope(user)
	if scope in ("all", "support"):
		return ""
	if scope == "none":
		return "1=0"
	return build(user)


def get_permission_query_conditions(user=None, doctype=DOCTYPE):
	return _conditions(user, lambda u: _own_sql(u, doctype))


def get_child_query_conditions(user=None, doctype="Lead Activity"):
	"""Activities, tasks and site visits: the user can see the lead."""
	return _conditions(
		user,
		lambda u: f"`tab{doctype}`.`lead` in (select `name` from `tabLead` where {_own_lead_sql(u)})",
	)


def get_client_query_conditions(user=None, doctype=CLIENT_DOCTYPE):
	"""Clients the user created, or whose lead the user can see."""
	return _conditions(
		user,
		lambda u: (
			f"(`tab{doctype}`.`owner` = {frappe.db.escape(u)} or `tab{doctype}`.`name` in"
			f" (select `client` from `tabLead` where {_own_lead_sql(u)}))"
		),
	)


def _share_flag(ptype):
	# Sharing grants read, write and so on separately. Anything else needs read.
	flag = ptype if ptype in ("read", "write", "share", "submit") else "read"
	return {flag: 1}


def _can_use_lead(lead, ptype, user) -> bool:
	"""True when the user owns, is assigned, or has a share on this lead."""
	row = frappe.db.get_value("Lead", lead, ["owner", "assigned_to"], as_dict=True)
	if not row:
		return False
	if user in (row.owner, row.assigned_to):
		return True
	return bool(
		frappe.db.exists(
			"DocShare", {"user": user, "share_doctype": "Lead", "share_name": lead, **_share_flag(ptype)}
		)
	)


def _scope(user):
	user = user or frappe.session.user
	if user == "Administrator":
		return user, "all"
	return user, _user_scope(user)


def _user_scope(user) -> str:
	"""'all', 'own', 'none', or 'support' for a Platform Admin with an active grant (P1.13)."""
	roles = frappe.get_roles(user)
	scope = scope_for(roles)
	if scope == "none" and PLATFORM_ADMIN in roles and has_support_access(user, roles):
		return "support"
	return scope


def _without_own(scope, ptype) -> bool:
	"""The answer for a scope that is not 'own'. A support grant reads and does nothing else."""
	if scope == "support":
		return (ptype or "read") in SUPPORT_PTYPES
	return scope == "all"


def has_permission(doc, ptype=None, user=None, **kwargs):
	user, scope = _scope(user)
	if scope != "own":
		return _without_own(scope, ptype)
	if ptype == "create":
		return True  # a new lead has no owner yet, the doctype's role rows decide who may create
	if user in (doc.get("owner"), doc.get("assigned_to")):
		return True
	return bool(
		frappe.db.exists(
			"DocShare",
			{"user": user, "share_doctype": doc.doctype, "share_name": doc.name, **_share_flag(ptype)},
		)
	)


def has_child_permission(doc, ptype=None, user=None, **kwargs):
	"""An activity, task or site visit is allowed when its lead is."""
	user, scope = _scope(user)
	if scope != "own":
		return _without_own(scope, ptype)
	lead = doc.get("lead")
	if not lead:
		return False
	return _can_use_lead(lead, "write" if ptype == "create" else ptype, user)


def has_client_permission(doc, ptype=None, user=None, **kwargs):
	user, scope = _scope(user)
	if scope != "own":
		return _without_own(scope, ptype)
	if ptype == "create" or user == doc.get("owner"):
		return True
	leads = frappe.get_all("Lead", filters={"client": doc.name}, pluck="name")
	return any(_can_use_lead(lead, ptype, user) for lead in leads)
