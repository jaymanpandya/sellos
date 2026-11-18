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
	"sellos.crm.api.find_duplicates": _LOGGERS,
	"sellos.crm.api.merge_clients": _ADMIN_ONLY,
	"sellos.crm.api.save_client": _READERS,
	"sellos.crm.api.list_leads": _READERS,
	"sellos.crm.api.list_lead_sources": _READERS,
	"sellos.crm.api.save_lead_source": _ADMIN_ONLY,
	"sellos.crm.api.delete_lead_source": _ADMIN_ONLY,
	"sellos.crm.api.list_stages": _READERS,
	"sellos.crm.api.move_lead_stage": _LOGGERS,
	"sellos.crm.api.list_call_outcomes": _LOGGERS,
	"sellos.crm.api.save_call_outcome": _ADMIN_ONLY,
	"sellos.crm.api.delete_call_outcome": _ADMIN_ONLY,
	"sellos.crm.api.list_lost_reasons": _LOGGERS,
	"sellos.crm.api.save_lost_reason": _ADMIN_ONLY,
	"sellos.crm.api.delete_lost_reason": _ADMIN_ONLY,
	"sellos.crm.api.log_call": _LOGGERS,
	"sellos.crm.api.save_lead": _READERS,
	"sellos.crm.api.get_lead": _READERS,
	"sellos.crm.api.add_activity": _LOGGERS,
	"sellos.crm.api.save_task": _LOGGERS,
	"sellos.crm.api.save_site_visit": _LOGGERS,
	"sellos.crm.api.set_archived": _READERS,
	"sellos.crm.api.record_consent": _LOGGERS,
	"sellos.crm.api.record_opt_out": _LOGGERS,
	"sellos.crm.api.record_dnd_result": _LOGGERS,
	"sellos.access.support.list_support_users": _ADMIN_ONLY,
	"sellos.access.support.grant_support_access": _ADMIN_ONLY,
	"sellos.access.support.revoke_support_access": _ADMIN_ONLY,
	"sellos.access.support.list_support_grants": _ADMIN_ONLY,
	"sellos.access.support.support_access_log": _ADMIN_ONLY,
	"sellos.config.setup_wizard.get_setup_state": _ADMIN_ONLY,
	"sellos.config.setup_wizard.save_profile": _ADMIN_ONLY,
	"sellos.config.setup_wizard.save_branding": _ADMIN_ONLY,
	"sellos.config.setup_wizard.save_stages": _ADMIN_ONLY,
	"sellos.config.setup_wizard.add_user": _ADMIN_ONLY,
	"sellos.config.setup_wizard.finish_setup": _ADMIN_ONLY,
	# SOS-P1-17: the Company Admin manages users in the web app.
	"sellos.access.users.list_users": _ADMIN_ONLY,
	"sellos.access.users.user_open_work": _ADMIN_ONLY,
	"sellos.access.users.invite_user": _ADMIN_ONLY,
	"sellos.access.users.resend_invitation": _ADMIN_ONLY,
	"sellos.access.users.save_user": _ADMIN_ONLY,
	"sellos.access.users.deactivate_user": _ADMIN_ONLY,
	"sellos.access.users.reactivate_user": _ADMIN_ONLY,
	"sellos.telephony.settings.get_telephony_settings": _ADMIN_ONLY,
	"sellos.telephony.settings.save_telephony_settings": _ADMIN_ONLY,
	"sellos.telephony.settings.check_connection": _ADMIN_ONLY,
	"sellos.access.field_history.getdoc": _OPENERS,
	"sellos.access.field_history.get_docinfo": _OPENERS,
}
