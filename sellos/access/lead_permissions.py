"""Who may see which CRM records (P1.04, extended in P1.06).

* Company Admin and System Manager see every record of the site.
* The Platform Admin sees no company CRM data. Support gets in through a time limited grant
  (P1.13), never by role: while the grant is active the user reads every record, and may change
  nothing. (Decided by Jayman, P1.06.)
* An Agent or Channel Partner sees only the leads they own or are assigned, plus leads shared with
  them through Frappe's normal share.
* Activities, tasks and site visits follow their lead. A client record follows the leads that use
  it, and a record the user created.
* A Sales Manager sees the leads of the agents in the teams they manage, and the leads they own or are
  assigned themselves, with the records that follow those leads (SOS-P1-18).
* A Channel Partner whose firm is Invited, Pending approval or Suspended sees nothing and registers
  nothing, like a Client (SOS-P7-01).
* A Client (the role) sees nothing.
"""

import frappe
from frappe import _

from sellos.access.partner_firms import is_pure_partner
from sellos.access.roles import AGENT, CHANNEL_PARTNER, COMPANY_ADMIN, PLATFORM_ADMIN, SALES_MANAGER
from sellos.access.support import has_support_access

SEES_ALL = frozenset({COMPANY_ADMIN, "System Manager"})
SEES_OWN = frozenset({AGENT, CHANNEL_PARTNER})
SEES_TEAM = frozenset({SALES_MANAGER})
TEAM_DOCTYPE = "Sales Team"
DOCTYPE = "Lead"
CLIENT_DOCTYPE = "Client"
LEAD_CHILDREN = (
	"Lead Activity",
	"Lead Task",
	"Site Visit",
	"Consent Record",
	"Call Log",
	"WhatsApp Conversation",
	"WhatsApp Message",
)
# What a support grant allows (P1.13). A missing permission type means read.
SUPPORT_PTYPES = frozenset({"read", "select", "print", "report"})
# SOS-P7-02: a Channel Partner reads their own leads and logs nothing. The registration method makes the lead.
PARTNER_REFUSED_PTYPES = frozenset({"write", "create", "delete", "submit", "cancel", "amend"})


def scope_for(roles) -> str:
	"""'all', 'team', 'own' or 'none' for a set of roles. The widest scope wins."""
	roles = set(roles)
	if roles & SEES_ALL:
		return "all"
	if roles & SEES_TEAM:
		return "team"
	if roles & SEES_OWN:
		return "own"
	return "none"


def team_members(manager) -> list[str]:
	"""The agents in the teams this user manages (SOS-P1-18)."""
	teams = frappe.get_all(TEAM_DOCTYPE, filters={"manager": manager}, pluck="name")
	if not teams:
		return []
	return frappe.get_all(
		"Sales Team Member", filters={"parenttype": TEAM_DOCTYPE, "parent": ["in", teams]}, pluck="agent"
	)


def visible_users(user, scope="own") -> list[str]:
	"""Whose leads the user sees: their own, and for a Sales Manager the agents of their teams."""
	if scope == "team":
		return [user, *sorted(set(team_members(user)) - {user})]
	return [user]


def _own_lead_sql(user, scope="own") -> str:
	return _own_sql(user, "Lead", scope)


def _in_sql(column, users) -> str:
	if len(users) == 1:
		return f"{column} = {frappe.db.escape(users[0])}"
	return f"{column} in ({', '.join(frappe.db.escape(u) for u in users)})"


def _own_sql(user, doctype, scope="own") -> str:
	quoted_user = frappe.db.escape(user)
	table = f"`tab{doctype}`"
	users = visible_users(user, scope)
	return (
		f"({_in_sql(f'{table}.`owner`', users)} or {_in_sql(f'{table}.`assigned_to`', users)}"
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
	return build(user, scope)


def get_permission_query_conditions(user=None, doctype=DOCTYPE):
	return _conditions(user, lambda u, scope: _own_sql(u, doctype, scope))


def get_child_query_conditions(user=None, doctype="Lead Activity"):
	"""Activities, tasks and site visits: the user can see the lead."""
	return _conditions(
		user,
		lambda u, scope: (
			f"`tab{doctype}`.`lead` in (select `name` from `tabLead` where {_own_lead_sql(u, scope)})"
		),
	)


def get_client_query_conditions(user=None, doctype=CLIENT_DOCTYPE):
	"""Clients the user (or their team) created, or whose lead the user can see."""
	return _conditions(
		user,
		lambda u, scope: (
			f"({_in_sql(f'`tab{doctype}`.`owner`', visible_users(u, scope))} or `tab{doctype}`.`name` in"
			f" (select `client` from `tabLead` where {_own_lead_sql(u, scope)}))"
		),
	)


def get_team_query_conditions(user=None, doctype=TEAM_DOCTYPE):
	"""A Sales Manager reads only the teams they manage. The Company Admin reads all."""
	return _conditions(user, lambda u, scope: f"`tab{doctype}`.`manager` = {frappe.db.escape(u)}")


def has_team_permission(doc, ptype=None, user=None, **kwargs):
	user, scope = _scope(user)
	if scope == "team":
		return (ptype or "read") in ("read", "select") and doc.get("manager") == user
	return _without_own(scope, ptype)


def _share_flag(ptype):
	# Sharing grants read, write and so on separately. Anything else needs read.
	flag = ptype if ptype in ("read", "write", "share", "submit") else "read"
	return {flag: 1}


def _can_use_lead(lead, ptype, user, scope="own") -> bool:
	"""True when the user (or, for a Sales Manager, their team) owns or is assigned the lead, or the user has a share."""
	row = frappe.db.get_value("Lead", lead, ["owner", "assigned_to"], as_dict=True)
	if not row:
		return False
	if set(visible_users(user, scope)) & {row.owner, row.assigned_to}:
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
	if scope == "own":
		from sellos.access.partner_firms import blocks_partner

		# SOS-P7-01: a partner whose firm is not Approved registers and sees no lead.
		if blocks_partner(user, roles):
			return "none"
	if scope == "none" and PLATFORM_ADMIN in roles and has_support_access(user, roles):
		return "support"
	return scope


def _partner_may_not(user, ptype) -> bool:
	"""True when a user whose only way in is a Channel Partner login asks to change something."""
	return ptype in PARTNER_REFUSED_PTYPES and is_pure_partner(frappe.get_roles(user))


def _without_own(scope, ptype) -> bool:
	"""The answer for a scope that is not 'own'. A support grant reads and does nothing else."""
	if scope == "support":
		return (ptype or "read") in SUPPORT_PTYPES
	return scope == "all"


def has_permission(doc, ptype=None, user=None, **kwargs):
	user, scope = _scope(user)
	if scope not in ("own", "team"):
		return _without_own(scope, ptype)
	if _partner_may_not(user, ptype):
		return False
	if ptype == "create":
		return True  # a new lead has no owner yet, the doctype's role rows decide who may create
	if set(visible_users(user, scope)) & {doc.get("owner"), doc.get("assigned_to")}:
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
	if scope not in ("own", "team"):
		return _without_own(scope, ptype)
	if _partner_may_not(user, ptype):
		return False
	lead = doc.get("lead")
	if not lead:
		return False
	return _can_use_lead(lead, "write" if ptype == "create" else ptype, user, scope)


def has_client_permission(doc, ptype=None, user=None, **kwargs):
	user, scope = _scope(user)
	if scope not in ("own", "team"):
		return _without_own(scope, ptype)
	if _partner_may_not(user, ptype):
		return False
	if ptype == "create" or doc.get("owner") in visible_users(user, scope):
		return True
	leads = frappe.get_all("Lead", filters={"client": doc.name}, pluck="name")
	return any(_can_use_lead(lead, ptype, user, scope) for lead in leads)


def check_assignee_in_team(lead) -> None:
	"""A Sales Manager reassigns leads within their team only (SOS-P1-18). Run when a lead is saved."""
	if not lead.assigned_to or not (lead.is_new() or lead.has_value_changed("assigned_to")):
		return
	if lead.flags.assigned_by_rule:  # SOS-P1-19: the company's own rule chose the agent, not the manager
		return
	user = frappe.session.user
	if user == "Administrator" or _user_scope(user) != "team":
		return
	if lead.assigned_to not in visible_users(user, "team"):
		frappe.throw(
			_("A Sales Manager assigns leads to the agents of their own team only."), frappe.PermissionError
		)
