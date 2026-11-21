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

from sellos.access.roles import (
	AGENT,
	CHANNEL_PARTNER,
	CLIENT,
	COMPANY_ADMIN,
	PLATFORM_ADMIN,
	SALES_MANAGER,
)

# SOS-P1-18: the Sales Manager reads and logs like an Agent, on its team's leads.
_READERS = frozenset({AGENT, CHANNEL_PARTNER, COMPANY_ADMIN, SALES_MANAGER})
_LOGGERS = frozenset({AGENT, COMPANY_ADMIN, SALES_MANAGER})
_TEAM_USERS = frozenset({COMPANY_ADMIN, SALES_MANAGER})
_ADMIN_ONLY = frozenset({COMPANY_ADMIN})
_PARTNER_ONLY = frozenset({CHANNEL_PARTNER})
_INVENTORY_EDITORS = frozenset({COMPANY_ADMIN, AGENT})
_INVENTORY_READERS = frozenset({COMPANY_ADMIN, AGENT, SALES_MANAGER})
_OPENERS = frozenset({PLATFORM_ADMIN, COMPANY_ADMIN, AGENT, CLIENT, CHANNEL_PARTNER, SALES_MANAGER})

# dotted method path -> the roles that may call it.
MATRIX: dict[str, frozenset[str]] = {
	"sellos.crm.api.list_clients": _READERS,
	"sellos.crm.api.find_duplicates": _LOGGERS,
	"sellos.crm.api.merge_clients": _ADMIN_ONLY,
	"sellos.crm.api.save_client": _READERS,
	"sellos.crm.api.list_leads": _READERS,
	"sellos.crm.api.get_board": _READERS,
	"sellos.crm.api.lead_filter_options": _READERS,
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
	"sellos.crm.api.reassign_lead": _TEAM_USERS,
	# SOS-P1-19: bulk reassignment, the agents to pick from, the assignment rules and the default team.
	"sellos.crm.api.bulk_reassign_leads": _TEAM_USERS,
	"sellos.crm.api.reassign_options": _TEAM_USERS,
	"sellos.crm.api.list_assignment_rules": _ADMIN_ONLY,
	"sellos.crm.api.save_assignment_rule": _ADMIN_ONLY,
	"sellos.crm.api.delete_assignment_rule": _ADMIN_ONLY,
	"sellos.crm.api.set_default_team": _ADMIN_ONLY,
	# SOS-P1-12: the bought list import.
	"sellos.crm.api.preview_lead_import": _ADMIN_ONLY,
	"sellos.crm.api.import_bought_list": _ADMIN_ONLY,
	"sellos.crm.api.save_lead": _READERS,
	"sellos.crm.api.get_lead": _READERS,
	"sellos.crm.api.add_activity": _LOGGERS,
	"sellos.crm.api.save_task": _LOGGERS,
	"sellos.crm.api.save_site_visit": _LOGGERS,
	# SOS-P1-25: the calendar, tomorrow's confirmations, confirming and finishing a visit.
	"sellos.crm.api.site_visit_calendar": _LOGGERS,
	"sellos.crm.api.tomorrows_site_visits": _LOGGERS,
	"sellos.crm.api.confirm_site_visit": _LOGGERS,
	"sellos.crm.api.complete_site_visit": _LOGGERS,
	"sellos.crm.api.site_visit_options": _LOGGERS,
	# SOS-P1-26: the Today screen reads what the caller may see.
	"sellos.crm.api.today_screen": _LOGGERS,
	# SOS-P2-09: the caller queue reads the leads the caller may see.
	"sellos.crm.api.caller_queue": _LOGGERS,
	# SOS-P1-22: follow ups. The untouched setting is the Company Admin's.
	"sellos.crm.api.complete_follow_up": _LOGGERS,
	"sellos.crm.api.list_follow_ups": _LOGGERS,
	"sellos.crm.api.get_follow_up_settings": _READERS,
	"sellos.crm.api.save_follow_up_settings": _ADMIN_ONLY,
	"sellos.crm.api.set_archived": _READERS,
	# SOS-P1-23: the bell, for every role that has leads. Each reads and changes its own only.
	"sellos.crm.api.list_notifications": _READERS,
	"sellos.crm.api.mark_notification_read": _READERS,
	"sellos.crm.api.mark_all_notifications_read": _READERS,
	# SOS-P2-04: Consent enforcement is the Company Admin's. Others may read whether it is on.
	"sellos.crm.api.get_consent_enforcement": _READERS,
	"sellos.crm.api.set_consent_enforcement": _ADMIN_ONLY,
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
	# SOS-P1-18: sales teams, and the report a Sales Manager reads for its own team.
	"sellos.access.teams.list_teams": _TEAM_USERS,
	"sellos.access.teams.save_team": _ADMIN_ONLY,
	"sellos.access.teams.delete_team": _ADMIN_ONLY,
	# SOS-P7-01: channel partner firms. The Company Admin invites, approves and suspends; the partner
	# completes its own firm's details.
	"sellos.access.partner_firms.list_partner_firms": _ADMIN_ONLY,
	"sellos.access.partner_firms.invite_partner_firm": _ADMIN_ONLY,
	"sellos.access.partner_firms.update_partner_firm": _ADMIN_ONLY,
	"sellos.access.partner_firms.approve_partner_firm": _ADMIN_ONLY,
	"sellos.access.partner_firms.suspend_partner_firm": _ADMIN_ONLY,
	"sellos.access.partner_firms.reinstate_partner_firm": _ADMIN_ONLY,
	"sellos.access.partner_firms.upload_agreement_for_firm": _ADMIN_ONLY,
	"sellos.access.partner_firms.my_partner_firm": _PARTNER_ONLY,
	"sellos.access.partner_firms.submit_partner_details": _PARTNER_ONLY,
	"sellos.access.partner_firms.upload_my_agreement": _PARTNER_ONLY,
	# SOS-P7-02: a partner of an approved firm registers a buyer; a Company Admin decides and sets the rules.
	"sellos.access.partner_registrations.partner_registration_form": _PARTNER_ONLY,
	"sellos.access.partner_registrations.register_buyer": _PARTNER_ONLY,
	"sellos.access.partner_registrations.my_partner_registrations": _PARTNER_ONLY,
	"sellos.access.partner_registrations.list_partner_registrations": _ADMIN_ONLY,
	"sellos.access.partner_registrations.approve_partner_registration": _ADMIN_ONLY,
	"sellos.access.partner_registrations.reject_partner_registration": _ADMIN_ONLY,
	"sellos.access.partner_registrations.change_lead_partner": _ADMIN_ONLY,
	"sellos.access.partner_registrations.get_partner_settings": _ADMIN_ONLY,
	"sellos.access.partner_registrations.save_partner_settings": _ADMIN_ONLY,
	# SOS-P4-01: inventory. A Company Admin or an Agent records it, a Sales Manager reads it.
	"sellos.inventory.api.inventory_overview": _INVENTORY_READERS,
	"sellos.inventory.api.get_project": _INVENTORY_READERS,
	"sellos.inventory.api.save_developer": _INVENTORY_EDITORS,
	"sellos.inventory.api.save_project": _INVENTORY_EDITORS,
	"sellos.inventory.api.save_unit": _INVENTORY_EDITORS,
	"sellos.inventory.api.save_property": _INVENTORY_EDITORS,
	"sellos.inventory.api.set_inventory_status": _INVENTORY_EDITORS,
	"sellos.inventory.api.set_inventory_archived": _ADMIN_ONLY,
	# SOS-P7-05: towers, wings, floors, the units of a floor, and a project's details. Editors lay them out.
	"sellos.inventory.structure.add_tower": _INVENTORY_EDITORS,
	"sellos.inventory.structure.add_floors": _INVENTORY_EDITORS,
	"sellos.inventory.structure.remove_floor": _INVENTORY_EDITORS,
	"sellos.inventory.structure.remove_tower": _INVENTORY_EDITORS,
	"sellos.inventory.structure.generate_floor_units": _INVENTORY_EDITORS,
	"sellos.inventory.structure.save_project_details": _INVENTORY_EDITORS,
	"sellos.inventory.structure.add_project_brochure": _INVENTORY_EDITORS,
	"sellos.inventory.structure.remove_project_brochure": _INVENTORY_EDITORS,
	"sellos.inventory.structure.save_amenity": _ADMIN_ONLY,
	# SOS-P7-06: the availability grid, and holds, blocks and the hold hours on it.
	"sellos.inventory.holds.unit_grid": _INVENTORY_READERS,
	"sellos.inventory.holds.hold_unit": _INVENTORY_EDITORS,
	"sellos.inventory.holds.release_hold": _INVENTORY_EDITORS,
	"sellos.inventory.holds.block_unit": _ADMIN_ONLY,
	"sellos.inventory.holds.unblock_unit": _ADMIN_ONLY,
	"sellos.inventory.holds.get_hold_settings": _ADMIN_ONLY,
	"sellos.inventory.holds.save_hold_settings": _ADMIN_ONLY,
	# SOS-P7-07: price lists, payment plans and cost sheets. A Company Admin keeps the price lists, the payment
	# plans and the percentages; an Agent reads them; an Agent or a Company Admin makes and reads cost sheets.
	"sellos.inventory.pricing.project_pricing": _INVENTORY_READERS,
	"sellos.inventory.pricing.save_price_list": _ADMIN_ONLY,
	"sellos.inventory.pricing.save_payment_plan": _ADMIN_ONLY,
	"sellos.inventory.pricing.archive_payment_plan": _ADMIN_ONLY,
	"sellos.inventory.pricing.save_cost_settings": _ADMIN_ONLY,
	"sellos.inventory.cost_sheet.cost_sheet_options": _INVENTORY_EDITORS,
	"sellos.inventory.cost_sheet.make_cost_sheet": _INVENTORY_EDITORS,
	"sellos.inventory.cost_sheet.unit_cost_sheets": _INVENTORY_EDITORS,
	"sellos.inventory.cost_sheet.get_cost_sheet": _INVENTORY_EDITORS,
	"sellos.inventory.cost_sheet.cost_sheet_pdf": _INVENTORY_EDITORS,
	# SOS-P4-02: listings. An Agent or a Company Admin makes, publishes and withdraws them, a Sales Manager reads
	# them, and only a Company Admin archives one.
	"sellos.inventory.listings.listing_overview": _INVENTORY_READERS,
	"sellos.inventory.listings.save_listing": _INVENTORY_EDITORS,
	"sellos.inventory.listings.publish_listing": _INVENTORY_EDITORS,
	"sellos.inventory.listings.unpublish_listing": _INVENTORY_EDITORS,
	"sellos.inventory.listings.set_listing_archived": _ADMIN_ONLY,
	# SOS-P4-03: photos and videos of a listing. An Agent or a Company Admin uploads, links, unlinks and orders
	# them, a Sales Manager reads them.
	"sellos.inventory.media.listing_media": _INVENTORY_READERS,
	"sellos.inventory.media.upload_listing_media": _INVENTORY_EDITORS,
	"sellos.inventory.media.link_listing_media": _INVENTORY_EDITORS,
	"sellos.inventory.media.unlink_listing_media": _INVENTORY_EDITORS,
	"sellos.inventory.media.reorder_listing_media": _INVENTORY_EDITORS,
	"sellos.reports.team.team_report": _TEAM_USERS,
	"sellos.crm.enquiry.get_enquiry_settings": _ADMIN_ONLY,  # SOS-P2-08
	"sellos.crm.enquiry.rotate_enquiry_key": _ADMIN_ONLY,  # SOS-P2-08
	"sellos.crm.website_form.get_website_settings": _ADMIN_ONLY,  # SOS-P1-09
	"sellos.crm.website_form.rotate_website_key": _ADMIN_ONLY,
	"sellos.reports.calls.call_report": _ADMIN_ONLY,
	"sellos.reports.calls.call_report_calls": _ADMIN_ONLY,
	"sellos.telephony.settings.get_telephony_settings": _ADMIN_ONLY,
	"sellos.telephony.settings.save_telephony_settings": _ADMIN_ONLY,
	"sellos.telephony.settings.check_connection": _ADMIN_ONLY,
	# SOS-P2-07: click to call, its status during the call and the outcome form after it.
	"sellos.telephony.click_to_call.call_preview": _LOGGERS,
	"sellos.telephony.click_to_call.click_to_call": _LOGGERS,
	"sellos.telephony.click_to_call.call_status": _LOGGERS,
	"sellos.telephony.click_to_call.pending_outcomes": _LOGGERS,
	"sellos.telephony.click_to_call.record_outcome": _LOGGERS,
	# SOS-P2-10: calling hours and the do not call list, for the Company Admin.
	# SOS-P5-07: the voice agent's providers, model, disclosure line and keyterms; the keys are never returned.
	"sellos.voice.agent.settings.get_voice_agent_settings": _ADMIN_ONLY,
	"sellos.voice.agent.settings.save_voice_agent_settings": _ADMIN_ONLY,
	"sellos.telephony.hours.get_calling_hours": _ADMIN_ONLY,
	"sellos.telephony.hours.save_calling_hours": _ADMIN_ONLY,
	"sellos.telephony.dnd.import_do_not_call_list": _ADMIN_ONLY,
	"sellos.telephony.dnd.do_not_call_summary": _ADMIN_ONLY,
	"sellos.access.field_history.getdoc": _OPENERS,
	"sellos.access.field_history.get_docinfo": _OPENERS,
}
