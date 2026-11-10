"""The permission matrix (P1.05): the roles that may call each whitelisted sellos method.

This list is written by hand, apart from the `@sellos_api` declarations, so a change to who may call
a method has to be made in two places and a reviewer sees both. `test_permission_matrix.py` calls
every method here as every role, as an outsider and as a guest, and fails the build when:

* a declared method is missing from this list,
* this list names a method that does not exist,
* the two lists disagree about the roles, or
* a sellos method is whitelisted with no declaration.

Add one line per method, in the same commit that adds the method.
"""

from sellos.access.roles import AGENT, CHANNEL_PARTNER, CLIENT, COMPANY_ADMIN, PLATFORM_ADMIN

_READERS = frozenset({AGENT, CHANNEL_PARTNER, COMPANY_ADMIN})
_LOGGERS = frozenset({AGENT, COMPANY_ADMIN})
_ADMIN_ONLY = frozenset({COMPANY_ADMIN})
_OPENERS = frozenset({PLATFORM_ADMIN, COMPANY_ADMIN, AGENT, CLIENT, CHANNEL_PARTNER})

# dotted method path -> the roles that may call it.
MATRIX: dict[str, frozenset[str]] = {
	"sellos.crm.api.list_clients": _READERS,
	"sellos.crm.api.save_client": _READERS,
	"sellos.crm.api.list_leads": _READERS,
	"sellos.crm.api.save_lead": _READERS,
	"sellos.crm.api.get_lead": _READERS,
	"sellos.crm.api.add_activity": _LOGGERS,
	"sellos.crm.api.save_task": _LOGGERS,
	"sellos.crm.api.save_site_visit": _LOGGERS,
	"sellos.crm.api.set_archived": _READERS,
	"sellos.access.support.list_support_users": _ADMIN_ONLY,
	"sellos.access.support.grant_support_access": _ADMIN_ONLY,
	"sellos.access.support.revoke_support_access": _ADMIN_ONLY,
	"sellos.access.support.list_support_grants": _ADMIN_ONLY,
	"sellos.access.support.support_access_log": _ADMIN_ONLY,
	"sellos.access.field_history.getdoc": _OPENERS,
	"sellos.access.field_history.get_docinfo": _OPENERS,
}
