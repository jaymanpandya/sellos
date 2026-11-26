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
_NOTE_USERS = frozenset({COMPANY_ADMIN, AGENT, SALES_MANAGER})
_PARTNER_ONLY = frozenset({CHANNEL_PARTNER})
_CLIENT_ONLY = frozenset({CLIENT})
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
	# SOS-LOOP: notes on a lead, a seller and a mandate, judged on the record. The types are the admin's.
	"sellos.crm.notes.note_types": _NOTE_USERS,
	"sellos.crm.notes.list_notes": _NOTE_USERS,
	"sellos.crm.notes.add_note": _NOTE_USERS,
	"sellos.crm.notes.update_note": _NOTE_USERS,
	"sellos.crm.notes.delete_note": _NOTE_USERS,
	"sellos.crm.notes.note_type_settings": _ADMIN_ONLY,
	"sellos.crm.notes.save_note_type": _ADMIN_ONLY,
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
	# SOS-P7-03: a Company Admin shares projects with partner firms; a partner sees only what is shared with theirs.
	# SOS-P4-10C: the inventory, listings and mandates import.
	"sellos.inventory.import_data.import_template": _ADMIN_ONLY,
	"sellos.inventory.import_data.import_overview": _ADMIN_ONLY,
	"sellos.inventory.import_data.preview_inventory_import": _ADMIN_ONLY,
	"sellos.inventory.import_data.run_inventory_import": _ADMIN_ONLY,
	"sellos.inventory.partner_shares.partner_share_options": _ADMIN_ONLY,
	"sellos.inventory.partner_shares.list_partner_shares": _ADMIN_ONLY,
	"sellos.inventory.partner_shares.share_project": _ADMIN_ONLY,
	"sellos.inventory.partner_shares.update_partner_share": _ADMIN_ONLY,
	"sellos.inventory.partner_shares.withdraw_partner_share": _ADMIN_ONLY,
	"sellos.inventory.partner_shares.my_shared_projects": _PARTNER_ONLY,
	"sellos.inventory.partner_shares.my_shared_project": _PARTNER_ONLY,
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
	# SOS-P7-10: a Company Admin or an Agent books a unit from a lead and cancels the booking.
	"sellos.inventory.bookings.booking_panel": _INVENTORY_EDITORS,
	"sellos.inventory.bookings.book_unit": _INVENTORY_EDITORS,
	"sellos.inventory.bookings.cancel_booking": _INVENTORY_EDITORS,
	"sellos.inventory.holds.get_hold_settings": _ADMIN_ONLY,
	"sellos.inventory.holds.save_hold_settings": _ADMIN_ONLY,
	# SOS-P7-13: the two response time limits.
	"sellos.crm.response_times.get_response_limits": _ADMIN_ONLY,
	"sellos.crm.response_times.save_response_limits": _ADMIN_ONLY,
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
	# SOS-P4-05: mandates and the Private Sale Dossier. A Company Admin or an Agent; the archive is the admin's.
	"sellos.inventory.mandates.mandate_overview": _INVENTORY_EDITORS,
	"sellos.inventory.mandates.mandate_status": frozenset({SALES_MANAGER}),
	"sellos.inventory.mandates.save_mandate": _INVENTORY_EDITORS,
	"sellos.inventory.docuseal.send_for_signing": _INVENTORY_EDITORS,  # SOS-LOOP, before the manual signature
	"sellos.inventory.mandates.sign_mandate": _INVENTORY_EDITORS,
	"sellos.inventory.mandates.add_dossier_note": _INVENTORY_EDITORS,
	"sellos.inventory.mandates.add_dossier_file": _INVENTORY_EDITORS,
	"sellos.inventory.mandates.open_dossier": _INVENTORY_EDITORS,
	"sellos.inventory.mandates.generate_dossier_pdf": _INVENTORY_EDITORS,
	# SOS-LOOP: the Company Profile (branding of the dossier and the mandate document). A Company Admin only.
	# SOS-LOOP: DocuSeal signing of a mandate. Sending is the editors'; the settings are the admin's.
	"sellos.inventory.docuseal.docuseal_status": _INVENTORY_EDITORS,
	"sellos.inventory.docuseal.get_docuseal_settings": _ADMIN_ONLY,
	"sellos.inventory.docuseal.save_docuseal_settings": _ADMIN_ONLY,
	"sellos.inventory.docuseal.check_docuseal_connection": _ADMIN_ONLY,
	"sellos.inventory.branding.get_company_profile": _ADMIN_ONLY,
	"sellos.inventory.branding.save_company_profile": _ADMIN_ONLY,
	"sellos.inventory.branding.upload_company_logo": _ADMIN_ONLY,
	"sellos.inventory.mandates.set_mandate_archived": _ADMIN_ONLY,
	# SOS-P4-06: deals and their commission splits. A Company Admin only.
	"sellos.inventory.deals.deal_overview": _ADMIN_ONLY,
	"sellos.inventory.deals.get_deal": _ADMIN_ONLY,
	"sellos.inventory.deals.save_deal": _ADMIN_ONLY,
	"sellos.inventory.deals.approve_splits": _ADMIN_ONLY,
	"sellos.inventory.deals.reopen_splits": _ADMIN_ONLY,
	"sellos.inventory.deals.set_deal_archived": _ADMIN_ONLY,
	# SOS-P7-04: commission rates, payouts and the partner's statement. A Company Admin sets rates, moves payouts
	# and exports a statement; a partner reads only their own.
	"sellos.inventory.commissions.commission_overview": _ADMIN_ONLY,
	"sellos.inventory.commissions.save_commission_rate": _ADMIN_ONLY,
	"sellos.inventory.commissions.set_commission_rate_archived": _ADMIN_ONLY,
	"sellos.inventory.commissions.create_missing_payouts": _ADMIN_ONLY,
	"sellos.inventory.commissions.move_payout": _ADMIN_ONLY,
	"sellos.inventory.commissions.export_partner_statement": _ADMIN_ONLY,
	"sellos.inventory.commissions.partner_commission": _PARTNER_ONLY,
	# SOS-P5-06: the partner's own deals, earnings and QR code.
	"sellos.crm.partner_views.partner_overview": _PARTNER_ONLY,
	# SOS-P7-08: match buyers to inventory, and the weights of the score.
	"sellos.inventory.matching.matches_for_lead": _INVENTORY_READERS,
	"sellos.inventory.matching.leads_for_unit": _INVENTORY_READERS,
	"sellos.inventory.matching.leads_for_listing": _INVENTORY_READERS,
	"sellos.inventory.matching.get_match_settings": _ADMIN_ONLY,
	"sellos.inventory.matching.save_match_settings": _ADMIN_ONLY,
	# SOS-P7-09: shortlists. An Agent or a Company Admin builds and shares them, a Sales Manager reads its team's,
	# and a Client reads only the ones shared with them.
	"sellos.inventory.shortlists.list_shortlists": _INVENTORY_READERS,
	"sellos.inventory.shortlists.get_shortlist": _INVENTORY_READERS,
	"sellos.inventory.shortlists.shortlist_pdf": _INVENTORY_READERS,
	"sellos.inventory.shortlists.create_shortlist": _INVENTORY_EDITORS,
	"sellos.inventory.shortlists.update_shortlist": _INVENTORY_EDITORS,
	"sellos.inventory.shortlists.add_to_shortlist": _INVENTORY_EDITORS,
	"sellos.inventory.shortlists.save_item_note": _INVENTORY_EDITORS,
	"sellos.inventory.shortlists.remove_shortlist_item": _INVENTORY_EDITORS,
	"sellos.inventory.shortlists.reorder_shortlist": _INVENTORY_EDITORS,
	"sellos.inventory.shortlists.archive_shortlist": _INVENTORY_EDITORS,
	"sellos.inventory.shortlists.share_shortlist": _INVENTORY_EDITORS,
	"sellos.inventory.shortlists.my_shortlists": _CLIENT_ONLY,
	"sellos.inventory.shortlists.my_shortlist": _CLIENT_ONLY,
	"sellos.inventory.shortlists.open_shortlist_item": _CLIENT_ONLY,
	"sellos.inventory.shortlists.my_shortlist_pdf": _CLIENT_ONLY,
	"sellos.crm.client_views.my_overview": _CLIENT_ONLY,  # SOS-P5-05
	"sellos.reports.team.team_report": _TEAM_USERS,
	"sellos.crm.enquiry.get_enquiry_settings": _ADMIN_ONLY,  # SOS-P2-08
	"sellos.crm.enquiry.rotate_enquiry_key": _ADMIN_ONLY,  # SOS-P2-08
	"sellos.crm.website_form.get_website_settings": _ADMIN_ONLY,  # SOS-P1-09
	"sellos.crm.website_form.rotate_website_key": _ADMIN_ONLY,
	"sellos.inventory.listings_feed.get_listings_feed_settings": _ADMIN_ONLY,  # SOS-P4-08
	"sellos.inventory.listings_feed.rotate_listings_key": _ADMIN_ONLY,
	"sellos.inventory.listings_feed.save_listings_webhook": _ADMIN_ONLY,
	"sellos.reports.calls.call_report": _ADMIN_ONLY,
	"sellos.reports.calls.call_report_calls": _ADMIN_ONLY,
	"sellos.reports.standard.lead_funnel": _ADMIN_ONLY,  # SOS-P5-02
	"sellos.reports.standard.source_performance": _ADMIN_ONLY,
	"sellos.reports.standard.agent_productivity": _ADMIN_ONLY,
	"sellos.reports.standard.ageing_report": _ADMIN_ONLY,
	"sellos.reports.ai_comparison.ai_comparison": _ADMIN_ONLY,  # SOS-P5-09
	"sellos.reports.ai_comparison.ai_comparison_calls": _ADMIN_ONLY,
	# SOS-P5-01: the report engine. Everyone who works leads reads the reports made visible to their role,
	# on the records they may see. Only a Company Admin refreshes and defines reports.
	"sellos.reports.engine.list_reports": _LOGGERS,
	"sellos.reports.engine.run_report": _LOGGERS,
	"sellos.reports.engine.report_records": _LOGGERS,
	"sellos.reports.engine.refresh_report": _ADMIN_ONLY,
	"sellos.reports.engine.save_report_definition": _ADMIN_ONLY,
	# SOS-P5-04: saved views for everyone who reads reports; export and schedules for a Company Admin only.
	"sellos.reports.exports.list_report_views": _LOGGERS,
	"sellos.reports.exports.save_report_view": _LOGGERS,
	"sellos.reports.exports.delete_report_view": _LOGGERS,
	"sellos.reports.exports.export_report": _ADMIN_ONLY,
	"sellos.reports.exports.list_report_schedules": _ADMIN_ONLY,
	"sellos.reports.exports.save_report_schedule": _ADMIN_ONLY,
	"sellos.reports.exports.delete_report_schedule": _ADMIN_ONLY,
	"sellos.reports.exports.send_report_schedule_now": _ADMIN_ONLY,
	# SOS-P5-03: a partner reads their own report, and the Platform Admin the totals per company.
	"sellos.reports.partner.partner_report": _PARTNER_ONLY,
	"sellos.reports.platform.list_platform_reports": frozenset({PLATFORM_ADMIN}),
	"sellos.reports.platform.run_platform_report": frozenset({PLATFORM_ADMIN}),
	# SOS-P3-02: the raw transaction table is on the control site and is read through this method only.
	"sellos.intel.api.list_raw_transactions": frozenset({PLATFORM_ADMIN}),
	# SOS-P3-12: Index II party names, for a Company Admin only, every view logged.
	"sellos.intel.party_names.get_party_names": _ADMIN_ONLY,
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
	# Design system pass: which sidebar sections a person has closed, their own setting.
	"sellos.access.preferences.get_nav_state": _OPENERS,
	"sellos.access.preferences.set_nav_state": _OPENERS,
	"sellos.access.field_history.getdoc": _OPENERS,
	"sellos.access.field_history.get_docinfo": _OPENERS,
	# SOS-P6-11: the company's WhatsApp number, its templates, and its conversations.
	"sellos.whatsapp.settings.get_whatsapp_settings": _ADMIN_ONLY,
	"sellos.whatsapp.settings.save_whatsapp_settings": _ADMIN_ONLY,
	"sellos.whatsapp.settings.check_whatsapp_connection": _ADMIN_ONLY,
	"sellos.whatsapp.settings.list_whatsapp_templates": _LOGGERS,
	"sellos.whatsapp.settings.save_whatsapp_template": _ADMIN_ONLY,
	"sellos.whatsapp.conversations.list_whatsapp_conversations": _LOGGERS,
	"sellos.whatsapp.conversations.get_whatsapp_conversation": _LOGGERS,
	"sellos.whatsapp.conversations.send_whatsapp_message": _LOGGERS,
	"sellos.whatsapp.conversations.hand_off_whatsapp_conversation": _LOGGERS,
	"sellos.whatsapp.conversations.close_whatsapp_conversation": _LOGGERS,
	"sellos.whatsapp.conversations.whatsapp_conversation_for_lead": _LOGGERS,
}
