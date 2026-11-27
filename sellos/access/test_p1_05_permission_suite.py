# SOS-P1-05 the permission test suite: every whitelisted sellos method is called as every role, as a
# user from another company and as a guest, and no call returns another company's data.
#
# "A user from another company" has no account on this company's site (every company is its own site
# and database, SOS-P0-06L), so on this site that person is a signed-in user who holds no role: the
# `basic` test user. A guest is the signed-out user.
#
# A method that is added with no matrix entry, or with no entry in SAMPLE_CALLS below, fails the build,
# and so does a sellos method that is whitelisted with no declaration (a deliberately open method).
import json
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from sellos.access import support
from sellos.access.matrix import MATRIX
from sellos.access.registry import (
	declared_methods,
	is_refused,
	load_declared_modules,
	undeclared_whitelisted_methods,
)
from sellos.access.roles import ROLES, ensure_roles
from sellos.access.test_permission_matrix import import_all_sellos_modules, matrix_problems
from sellos.crm import notifications
from sellos.crm.pipeline import DEFAULT_STAGES
from sellos.inventory import cost_sheet
from sellos.reports.engine import ensure_default_definitions
from sellos.telephony.settings import save_telephony_settings
from sellos.testing.users import TEST_USERS, create_test_users
from sellos.tests import phones
from sellos.tests.files import tiny_pdf_base64

SECRET_NAME = "P105 Secret Buyer"
SECRET_PHONE = phones.in_mobile(105)
# SOS-P2-07: the 022 number the fake provider rings from, made from a generated number.
LANDLINE_022 = f"{phones.in_mobile(2007)[:3]}22{phones.in_mobile(2007)[-8:]}"
DND_SAMPLE = phones.in_mobile(2010)  # SOS-P2-10
ACTIVITY_NOTE = "p105-secret-activity-note"
# SOS-P7-01: a tiny PDF for the agreement upload calls. The file lands on disk, so the test removes it.
AGREEMENT_B64 = tiny_pdf_base64()
ADMIN = "company_admin"

# who -> the key of the test user. "outsider" is a signed-in user from another company. "guest" is signed out.
WHO = {
	"platform_admin": "platform_admin",
	"company_admin": "company_admin",
	"agent": "agent",
	"client": "client",
	"channel_partner": "channel_partner",
	"sales_manager": "sales_manager",
	"outsider": "basic",
	"guest": None,
}
ROLE_KEYS = {
	"SellOS Platform Admin": "platform_admin",
	"SellOS Company Admin": "company_admin",
	"SellOS Agent": "agent",
	"SellOS Client": "client",
	"SellOS Channel Partner": "channel_partner",
	"SellOS Sales Manager": "sales_manager",
}

# Arguments for every method in the matrix. `{client}` and `{lead}` are filled in with the records the
# test makes. Each one aims at the company's own record, which only the Company Admin may open.
SAMPLE_CALLS = {
	"sellos.crm.api.list_clients": {},
	"sellos.crm.api.find_duplicates": {"phone": SECRET_PHONE},
	"sellos.crm.api.merge_clients": {"keep": "{client}", "merge": "{client_other}"},
	"sellos.crm.api.save_client": {"name": "{client}", "values": {"city": "Pune"}},
	"sellos.crm.api.list_leads": {},
	"sellos.crm.api.get_board": {},
	"sellos.crm.api.lead_filter_options": {},
	"sellos.crm.api.list_lead_sources": {},
	"sellos.crm.api.save_lead_source": {"name": "{spare_source}", "values": {"enabled": 0}},
	"sellos.crm.api.delete_lead_source": {"name": "{spare_source}"},
	"sellos.crm.api.list_stages": {},
	"sellos.crm.api.move_lead_stage": {"lead": "{lead}", "stage": "Contacted"},
	# SOS-P1-21: Wrong number needs no follow up, so the call is one write.
	"sellos.crm.api.list_call_outcomes": {},
	"sellos.crm.api.save_call_outcome": {"name": "{spare_outcome}", "values": {"enabled": 0}},
	"sellos.crm.api.delete_call_outcome": {"name": "{spare_outcome}"},
	"sellos.crm.api.list_lost_reasons": {},
	"sellos.crm.api.save_lost_reason": {"name": "{spare_reason}", "values": {"enabled": 0}},
	"sellos.crm.api.delete_lost_reason": {"name": "{spare_reason}"},
	"sellos.crm.api.log_call": {"lead": "{lead}", "outcome": "Wrong number", "notes": "p121 call"},
	# SOS-P1-18: the lead goes to the test agent, who is in no team.
	"sellos.crm.api.reassign_lead": {"lead": "{lead}", "assigned_to": "{agent}"},
	# SOS-P1-19: a bulk move of the one lead, the agents to pick from, the rules and the default team.
	"sellos.crm.api.bulk_reassign_leads": {"leads": "{lead_list}", "assigned_to": "{agent}"},
	"sellos.crm.api.reassign_options": {},
	# SOS-P2-04: reading and switching Consent enforcement (Off is the default, so the call changes nothing).
	"sellos.crm.api.get_consent_enforcement": {},
	"sellos.crm.api.set_consent_enforcement": {"on": 0},
	"sellos.crm.api.list_assignment_rules": {},
	"sellos.crm.api.save_assignment_rule": {"name": "{spare_rule}", "values": {"priority": 5}},
	"sellos.crm.api.delete_assignment_rule": {"name": "{spare_rule}"},
	"sellos.crm.api.set_default_team": {"team": "{rule_team}"},
	# SOS-P1-12: a one row list. The number is generated, never typed.
	"sellos.crm.api.preview_lead_import": {"csv_text": f"Name,Phone\nP112 Matrix,{phones.in_mobile(112)}"},
	"sellos.crm.api.import_bought_list": {"csv_text": f"Name,Phone\nP112 Matrix,{phones.in_mobile(113)}"},
	# SOS-P4-10C: a one row developer file, never run for real by the matrix (a dry run), and the real run
	"sellos.inventory.import_data.import_template": {"record_type": "Developer"},
	"sellos.inventory.import_data.import_overview": {},
	"sellos.inventory.import_data.preview_inventory_import": {
		"record_type": "Developer",
		"csv_text": "Developer name\nP4 10C Matrix",
	},
	"sellos.inventory.import_data.run_inventory_import": {
		"record_type": "Developer",
		"csv_text": "Developer name\nP4 10C Matrix Run",
	},
	"sellos.crm.api.save_lead": {"name": "{lead}", "values": {"notes": "p105 edit"}},
	"sellos.crm.api.get_lead": {"name": "{lead}"},
	"sellos.crm.api.add_activity": {"lead": "{lead}", "activity_type": "Note", "notes": "p105 added"},
	"sellos.crm.api.save_task": {
		"values": {"lead": "{lead}", "title": "p105 task", "due_date": "2030-01-01"}
	},
	"sellos.crm.api.save_site_visit": {
		"values": {"lead": "{lead}", "project_name": "P105 Tower", "visit_datetime": "2030-01-01 10:00:00"}
	},
	# SOS-P1-25: the calendar and the list read what the caller may see. The visit is the test's own.
	"sellos.crm.api.site_visit_calendar": {"view": "week", "date": "2030-01-01"},
	"sellos.crm.api.tomorrows_site_visits": {},
	"sellos.crm.api.confirm_site_visit": {"name": "{visit}", "confirmation_status": "Confirmed"},
	"sellos.crm.api.complete_site_visit": {"name": "{visit}", "outcome": "Liked it"},
	"sellos.crm.api.site_visit_options": {},
	"sellos.crm.api.set_archived": {"doctype": "Lead", "name": "{lead}", "archived": 0},
	# SOS-P1-26: the Today screen, read only.
	"sellos.crm.api.today_screen": {},
	# SOS-P2-09: the caller queue, read only.
	"sellos.crm.api.caller_queue": {},
	# SOS-P1-22: a follow up made for the test, completed with a note. The setting is the Company Admin's.
	"sellos.crm.api.complete_follow_up": {"name": "{task}", "notes": "p122 done"},
	"sellos.crm.api.list_follow_ups": {},
	"sellos.crm.api.get_follow_up_settings": {},
	"sellos.crm.api.save_follow_up_settings": {"untouched_days": 3},
	# SOS-P1-23: a user's own notifications. Marking all read touches only the caller's.
	"sellos.crm.api.list_notifications": {},
	"sellos.crm.api.mark_notification_read": {"name": "{notification}"},
	"sellos.crm.api.mark_all_notifications_read": {},
	"sellos.crm.api.record_consent": {
		"lead": "{lead}",
		"basis": "Inquiry",
		"evidence_link": "https://example.com/p108-evidence",
	},
	"sellos.crm.api.record_opt_out": {"lead": "{lead}", "source": "Phone call"},
	"sellos.crm.api.record_dnd_result": {"lead": "{lead}", "registered": 1},
	"sellos.access.support.list_support_users": {},
	"sellos.access.support.grant_support_access": {
		"support_user": "{support_user}",
		"duration_minutes": 60,
		"reason": "p105 check",
	},
	"sellos.access.support.revoke_support_access": {"grant": "{grant}"},
	"sellos.access.support.list_support_grants": {},
	"sellos.access.support.support_access_log": {"grant": "{grant}"},
	"sellos.config.setup_wizard.get_setup_state": {},
	# SOS-INT-1: LegiScore has no key on the matrix site, so the check answers "enter the details" and calls no one.
	"sellos.config.integrations.list_integrations": {},
	"sellos.config.integrations.save_integration": {"provider": "legiscore", "values": {}},
	"sellos.config.integrations.check_integration": {"provider": "legiscore"},
	"sellos.config.setup_wizard.save_profile": {"values": {"company_name": "P105 Realty"}},
	"sellos.config.setup_wizard.save_branding": {"brand_color": "#0f4c35"},
	# SOS-P1-07: a stage with leads is never deleted, and the test makes a lead, so the call keeps the
	# eleven stages and adds one.
	"sellos.config.setup_wizard.save_stages": {
		"stages": [*DEFAULT_STAGES, {"stage_name": "P105 Open", "stage_type": "Open"}]
	},
	"sellos.config.setup_wizard.add_user": {
		"email": "p105_wizard_user@example.com",
		"first_name": "P105",
		"role": "SellOS Agent",
	},
	"sellos.config.setup_wizard.finish_setup": {},
	# SOS-P1-17: the calls act on a spare agent made for the test, never on the caller.
	"sellos.access.users.list_users": {},
	# Design system pass: the signed in person's own sidebar state, no record in the arguments.
	"sellos.access.preferences.get_nav_state": {},
	"sellos.access.preferences.set_nav_state": {"closed": "[]"},
	"sellos.access.users.user_open_work": {"email": "{spare_user}"},
	"sellos.access.users.invite_user": {
		"email": "p117_invited@example.com",
		"first_name": "P117",
		"role": "SellOS Agent",
	},
	"sellos.access.users.resend_invitation": {"email": "{spare_user}"},
	"sellos.access.users.save_user": {"email": "{spare_user}", "values": {"first_name": "P117 Edit"}},
	"sellos.access.users.deactivate_user": {"email": "{spare_user}"},
	"sellos.access.users.reactivate_user": {"email": "{spare_user}"},
	# SOS-P1-18: the calls act on a spare team made for the test.
	"sellos.access.teams.list_teams": {},
	"sellos.access.teams.save_team": {"name": "{spare_team}", "values": {"members": []}},
	"sellos.access.teams.delete_team": {"name": "{spare_team}"},
	# SOS-P7-01: the calls act on a spare firm that is Pending approval. The Company Admin's calls run in the
	# order of the matrix: approve, suspend, reinstate.
	"sellos.access.partner_firms.list_partner_firms": {},
	"sellos.access.partner_firms.invite_partner_firm": {
		"firm_name": "P701 Invited Firm",
		"contact_person": "P701 Invited",
		"email": "p701_invited@example.com",
	},
	"sellos.access.partner_firms.update_partner_firm": {
		"name": "{spare_firm}",
		"values": {"contact_person": "P701 Edit"},
	},
	"sellos.access.partner_firms.approve_partner_firm": {"name": "{spare_firm}"},
	"sellos.access.partner_firms.suspend_partner_firm": {"name": "{spare_firm}", "reason": "p701 left"},
	"sellos.access.partner_firms.reinstate_partner_firm": {"name": "{spare_firm}"},
	"sellos.access.partner_firms.upload_agreement_for_firm": {
		"name": "{spare_firm}",
		"filename": "p701_suite_agreement.pdf",
		"content_base64": AGREEMENT_B64,
	},
	"sellos.access.partner_firms.my_partner_firm": {},
	"sellos.access.partner_firms.submit_partner_details": {"values": {"contact_person": "P701 Self"}},
	"sellos.access.partner_firms.upload_my_agreement": {
		"filename": "p701_suite_agreement.pdf",
		"content_base64": AGREEMENT_B64,
	},
	# SOS-P7-02: the Channel Partner's test login has no approved firm, so its calls are refused; the Company
	# Admin's calls act on two spare registrations (approve one, reject the other).
	"sellos.access.partner_registrations.partner_registration_form": {},
	"sellos.access.partner_registrations.register_buyer": {
		"buyer_name": "P702 Suite Buyer",
		"phone": phones.in_mobile(7021),
	},
	"sellos.access.partner_registrations.my_partner_registrations": {},
	"sellos.access.partner_registrations.list_partner_registrations": {},
	"sellos.access.partner_registrations.approve_partner_registration": {"name": "{spare_registration}"},
	"sellos.access.partner_registrations.reject_partner_registration": {
		"name": "{spare_registration_two}",
		"reason": "p702 not a buyer",
	},
	"sellos.access.partner_registrations.change_lead_partner": {
		"lead": "{lead}",
		"partner_firm": "{spare_firm}",
	},
	"sellos.access.partner_registrations.get_partner_settings": {},
	"sellos.access.partner_registrations.save_partner_settings": {},
	# SOS-P7-03: sharing acts on the spare project and a spare share made for the test. A partner with no
	# approved firm is refused.
	"sellos.inventory.partner_shares.partner_share_options": {"project": "{spare_project}"},
	"sellos.inventory.partner_shares.list_partner_shares": {},
	"sellos.inventory.partner_shares.share_project": {"project": "{spare_project}", "firms": "all"},
	"sellos.inventory.partner_shares.update_partner_share": {"name": "{spare_share}", "share_price_list": 1},
	"sellos.inventory.partner_shares.withdraw_partner_share": {
		"name": "{spare_share}",
		"reason": "p703 suite",
	},
	"sellos.inventory.partner_shares.my_shared_projects": {},
	"sellos.inventory.partner_shares.my_shared_project": {"project": "{spare_project}"},
	# SOS-P4-01: inventory, on a spare project, unit and property made for the test.
	"sellos.inventory.api.inventory_overview": {},
	"sellos.inventory.api.get_project": {"name": "{spare_project}"},
	"sellos.inventory.api.save_developer": {"values": {"developer_name": "P401 Suite Developer"}},
	"sellos.inventory.api.save_project": {"name": "{spare_project}", "values": {"locality": "P401 Edit"}},
	"sellos.inventory.api.save_unit": {"name": "{spare_unit}", "values": {"floor": 3}},
	"sellos.inventory.api.save_property": {"name": "{spare_property}", "values": {"locality": "P401 Edit"}},
	"sellos.inventory.api.set_inventory_status": {
		"doctype": "Unit",
		"name": "{spare_unit}",
		"status": "Held",
		"reason": "p401 check",
	},
	"sellos.inventory.api.set_inventory_archived": {"doctype": "Property", "name": "{spare_property}"},
	# SOS-P7-05: towers on the spare project; two spare towers so a removal succeeds for the Company Admin.
	"sellos.inventory.structure.add_tower": {"project": "{spare_project}", "tower_name": "P705 Suite New"},
	"sellos.inventory.structure.add_floors": {"tower": "{spare_tower}", "floors": "5 to 6"},
	"sellos.inventory.structure.remove_floor": {"tower": "{spare_tower_two}", "floor": 2},
	"sellos.inventory.structure.remove_tower": {"tower": "{spare_tower_two}"},
	"sellos.inventory.structure.generate_floor_units": {
		"tower": "{spare_tower}",
		"floor": 1,
		"pattern": "101 to 102",
		"carpet_area": 500,
	},
	"sellos.inventory.structure.save_project_details": {
		"project": "{spare_project}",
		"possession_date": "2028-03-31",
	},
	"sellos.inventory.structure.add_project_brochure": {
		"project": "{spare_project}",
		"title": "P705 Suite brochure",
		"filename": "p705_suite_brochure.pdf",
		"content_base64": AGREEMENT_B64,
	},
	"sellos.inventory.structure.remove_project_brochure": {"project": "{spare_project}", "file": "/none"},
	"sellos.inventory.structure.save_amenity": {"amenity_name": "P705 Suite Amenity"},
	# SOS-P7-06: each acts on its own spare unit, so the earlier status change on spare_unit does not matter.
	"sellos.inventory.holds.unit_grid": {"project": "{spare_project}"},
	"sellos.inventory.holds.hold_unit": {"unit": "{spare_unit_hold}", "lead": "{lead}"},
	"sellos.inventory.holds.release_hold": {"unit": "{spare_unit_held}"},
	"sellos.inventory.holds.block_unit": {"unit": "{spare_unit_block}", "reason": "p706 suite"},
	"sellos.inventory.holds.unblock_unit": {"unit": "{spare_unit_blocked}", "reason": "p706 suite"},
	# SOS-P7-10: booking and cancelling each use their own spare unit, and cancelling uses a Booked unit with its deal.
	"sellos.inventory.bookings.booking_panel": {"lead": "{lead}"},
	"sellos.inventory.bookings.book_unit": {
		"lead": "{lead}",
		"unit": "{spare_unit_book}",
		"price": 5000000,
		"booking_amount": 100000,
	},
	"sellos.inventory.bookings.cancel_booking": {"deal": "{spare_booking_deal}", "reason": "p710 suite"},
	"sellos.inventory.holds.get_hold_settings": {},
	"sellos.inventory.holds.save_hold_settings": {"unit_hold_hours": 48},
	"sellos.crm.response_times.get_response_limits": {},
	"sellos.crm.response_times.save_response_limits": {"unassigned_minutes": 10, "contact_minutes": 120},
	# SOS-P7-07: the spare project has a price list in force, a plan and one cost sheet of the spare unit.
	"sellos.inventory.pricing.project_pricing": {"project": "{spare_project}"},
	"sellos.inventory.pricing.save_price_list": {
		"project": "{spare_project}",
		"values": {"title": "P707 Suite later list", "effective_from": "2031-01-01", "base_rate": 9000},
	},
	"sellos.inventory.pricing.save_payment_plan": {
		"project": "{spare_project}",
		"values": {
			"plan_name": "P707 Suite new plan",
			"plan_type": "Down payment",
			"instalments": [{"label": "On booking", "percent": 100}],
		},
	},
	"sellos.inventory.pricing.archive_payment_plan": {"name": "{spare_plan_two}"},
	"sellos.inventory.pricing.save_cost_settings": {
		"stamp_duty_percent": 6,
		"registration_percent": 1,
		"gst_percent": 5,
	},
	"sellos.inventory.cost_sheet.cost_sheet_options": {"unit": "{spare_unit}"},
	"sellos.inventory.cost_sheet.make_cost_sheet": {"unit": "{spare_unit}", "payment_plan": "{spare_plan}"},
	"sellos.inventory.cost_sheet.unit_cost_sheets": {"unit": "{spare_unit}"},
	"sellos.inventory.cost_sheet.get_cost_sheet": {"name": "{spare_sheet}"},
	"sellos.inventory.cost_sheet.cost_sheet_pdf": {"name": "{spare_sheet}"},
	# SOS-P4-02: the spare listing is a complete draft of its own property.
	"sellos.inventory.listings.listing_overview": {},
	"sellos.inventory.listings.save_listing": {
		"name": "{spare_listing}",
		"values": {"description": "P402 Suite edit"},
	},
	"sellos.inventory.listings.publish_listing": {"name": "{spare_listing}"},
	"sellos.inventory.listings.unpublish_listing": {"name": "{spare_listing}"},
	"sellos.inventory.listings.set_listing_archived": {"name": "{spare_listing}"},
	# SOS-P4-03: the media listings are drafts of their own, so the archive call above never reaches them.
	"sellos.inventory.media.listing_media": {"listing": "{media_listing}"},
	"sellos.inventory.media.upload_listing_media": {
		"listing": "{media_listing}",
		"title": "P403 Suite Photo",
		"filename": "p403-suite.png",
		"content_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
	},
	"sellos.inventory.media.link_listing_media": {
		"listing": "{media_listing}",
		"media_asset": "{media_asset}",
	},
	"sellos.inventory.media.unlink_listing_media": {
		"listing": "{media_listing}",
		"media_asset": "{media_asset}",
	},
	"sellos.inventory.media.reorder_listing_media": {
		"listing": "{order_listing}",
		"order": ["{media_asset_two}", "{media_asset}"],
	},
	# SOS-P4-05: one draft mandate of a seller lead the company admin owns. In the matrix's order it is corrected,
	# signed, given a note and a file, opened and archived, so each call finds it in the state it needs.
	"sellos.inventory.mandates.mandate_overview": {},
	# SOS-LOOP: notes. One note of the company admin's lead; it is corrected, then removed, in the matrix's order.
	"sellos.crm.notes.note_types": {},
	"sellos.crm.notes.list_notes": {"lead": "{lead}"},
	"sellos.crm.notes.add_note": {"lead": "{lead}", "note_type": "{note_type}", "body": "p105 suite note"},
	"sellos.crm.notes.update_note": {"name": "{spare_note}", "note_type": "{note_type}", "body": "p105 edit"},
	"sellos.crm.notes.delete_note": {"name": "{spare_note}"},
	"sellos.crm.notes.note_type_settings": {},
	"sellos.crm.notes.save_note_type": {"label": "P105 Suite Type"},
	"sellos.inventory.mandates.mandate_status": {"leads": ["{lead}", "{spare_mandate_lead}"]},  # SOS-LOOP
	"sellos.inventory.mandates.save_mandate": {"name": "{spare_mandate}", "values": {"fee_percent": 2}},
	"sellos.inventory.mandates.sign_mandate": {
		"name": "{spare_mandate}",
		"filename": "p405_suite_signed.pdf",
		"content_base64": tiny_pdf_base64(),
	},
	"sellos.inventory.mandates.add_dossier_note": {
		"name": "{spare_mandate}",
		"title": "P405 Suite Note",
		"note": "p405 suite note",
	},
	"sellos.inventory.mandates.add_dossier_file": {
		"name": "{spare_mandate}",
		"title": "P405 Suite File",
		"filename": "p405_suite_dossier.pdf",
		"content_base64": tiny_pdf_base64(),
	},
	"sellos.inventory.mandates.open_dossier": {"name": "{spare_mandate}"},
	"sellos.inventory.mandates.generate_dossier_pdf": {"name": "{spare_mandate}"},  # SOS-LOOP
	"sellos.inventory.docuseal.docuseal_status": {},
	"sellos.inventory.docuseal.send_for_signing": {"name": "{spare_mandate}"},
	"sellos.inventory.docuseal.get_docuseal_settings": {},
	"sellos.inventory.docuseal.save_docuseal_settings": {"values": {"signer_name": "P105 Signer"}},
	"sellos.inventory.docuseal.check_docuseal_connection": {},
	"sellos.inventory.branding.get_company_profile": {},
	"sellos.inventory.branding.save_company_profile": {"values": {"footer_text": "p105 footer"}},
	"sellos.inventory.branding.upload_company_logo": {
		"filename": "p105.png",
		"content_base64": (
			"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
		),
	},
	"sellos.inventory.mandates.set_mandate_archived": {"name": "{spare_mandate}"},
	# SOS-P4-06: one pending deal. In the matrix's order it is corrected, approved, reopened and archived.
	"sellos.inventory.deals.deal_overview": {},
	"sellos.inventory.deals.get_deal": {"name": "{spare_deal}"},  # SOS-LOOP
	"sellos.inventory.deals.save_deal": {"name": "{spare_deal}", "values": {"commission_amount": 1000}},
	"sellos.inventory.deals.approve_splits": {"name": "{spare_deal}"},
	"sellos.inventory.deals.reopen_splits": {"name": "{spare_deal}"},
	"sellos.inventory.deals.set_deal_archived": {"name": "{spare_deal}"},
	# SOS-P7-04: one rate on the spare project and one Due payout of the spare firm on the spare deal.
	"sellos.inventory.commissions.commission_overview": {},
	"sellos.inventory.commissions.save_commission_rate": {
		"values": {
			"project": "{spare_project}",
			"rate_type": "Percentage",
			"value": 2,
			"start_date": "2030-01-01",
		}
	},
	"sellos.inventory.commissions.set_commission_rate_archived": {"name": "{spare_rate}"},
	"sellos.inventory.commissions.create_missing_payouts": {},
	"sellos.inventory.commissions.move_payout": {"name": "{spare_payout}", "to": "Approved"},
	"sellos.inventory.commissions.export_partner_statement": {"firm": "{spare_firm}"},
	"sellos.inventory.commissions.partner_commission": {},
	"sellos.crm.partner_views.partner_overview": {},
	# SOS-P7-08
	"sellos.inventory.matching.matches_for_lead": {"lead": "{lead}"},
	"sellos.inventory.matching.leads_for_unit": {"unit": "{spare_unit}"},
	"sellos.inventory.matching.leads_for_listing": {"listing": "{spare_listing}"},
	"sellos.inventory.matching.get_match_settings": {},
	"sellos.inventory.matching.save_match_settings": {
		"budget": 25,
		"configuration": 25,
		"locality": 25,
		"property_type": 25,
	},
	# SOS-P7-09: shortlists of the spare units for the secret client. The reorder lists the main shortlist's
	# two homes, an add, a removal and an archive each have a shortlist of their own.
	"sellos.inventory.shortlists.list_shortlists": {},
	"sellos.inventory.shortlists.get_shortlist": {"name": "{shortlist}"},
	"sellos.inventory.shortlists.shortlist_pdf": {"name": "{shortlist}"},
	"sellos.inventory.shortlists.create_shortlist": {"client": "{client}"},
	"sellos.inventory.shortlists.update_shortlist": {"name": "{shortlist}", "title": "P709 Suite"},
	"sellos.inventory.shortlists.add_to_shortlist": {
		"kind": "Unit",
		"target": "{shortlist_unit}",
		"shortlist": "{shortlist_add}",
	},
	"sellos.inventory.shortlists.save_item_note": {
		"name": "{shortlist}",
		"item": "{shortlist_item}",
		"note": "p709 note",
	},
	"sellos.inventory.shortlists.remove_shortlist_item": {
		"name": "{shortlist_remove}",
		"item": "{shortlist_remove_item}",
	},
	"sellos.inventory.shortlists.reorder_shortlist": {
		"name": "{shortlist}",
		"order": ["{shortlist_item_two}", "{shortlist_item}"],
	},
	"sellos.inventory.shortlists.archive_shortlist": {"name": "{shortlist_archive}"},
	"sellos.inventory.shortlists.share_shortlist": {"name": "{shortlist}"},
	"sellos.inventory.shortlists.my_shortlists": {},
	"sellos.crm.client_views.my_overview": {},  # SOS-P5-05
	"sellos.inventory.shortlists.my_shortlist": {"name": "{shortlist}"},
	"sellos.inventory.shortlists.open_shortlist_item": {"name": "{shortlist}", "item": "{shortlist_item}"},
	"sellos.inventory.shortlists.my_shortlist_pdf": {"name": "{shortlist}"},
	"sellos.reports.team.team_report": {},
	"sellos.reports.partner.partner_report": {},  # SOS-P5-03
	"sellos.reports.platform.list_platform_reports": {},
	"sellos.reports.platform.run_platform_report": {"report": "companies"},
	"sellos.crm.enquiry.get_enquiry_settings": {},  # SOS-P2-08
	"sellos.crm.enquiry.rotate_enquiry_key": {},
	"sellos.crm.website_form.get_website_settings": {},  # SOS-P1-09
	"sellos.crm.website_form.rotate_website_key": {},
	"sellos.inventory.listings_feed.get_listings_feed_settings": {},  # SOS-P4-08
	"sellos.inventory.listings_feed.rotate_listings_key": {},
	"sellos.inventory.listings_feed.save_listings_webhook": {},
	"sellos.reports.calls.call_report": {},
	"sellos.reports.calls.call_report_calls": {},
	"sellos.reports.standard.lead_funnel": {},  # SOS-P5-02
	"sellos.reports.standard.source_performance": {},
	"sellos.reports.standard.agent_productivity": {},
	"sellos.reports.standard.ageing_report": {},
	"sellos.reports.ai_comparison.ai_comparison": {},  # SOS-P5-09
	"sellos.reports.ai_comparison.ai_comparison_calls": {"group": "ai"},
	# SOS-P5-01: the default reports are made in setUp.
	"sellos.reports.engine.list_reports": {},
	"sellos.reports.engine.run_report": {"report": "leads-by-stage"},
	"sellos.reports.engine.report_records": {"report": "leads-by-stage", "group": ""},
	"sellos.reports.engine.refresh_report": {"report": "leads-by-stage"},
	"sellos.reports.engine.save_report_definition": {
		"values": {"report_key": "p501-matrix", "title": "P501 Matrix", "source_doctype": "Lead"}
	},
	# SOS-P5-04: saved views, export and schedules; the spare view and schedule are made in setUp.
	"sellos.reports.exports.list_report_views": {},
	"sellos.reports.exports.save_report_view": {
		"values": {"title": "P504 Matrix View", "report": "leads-by-stage", "range_days": 7}
	},
	"sellos.reports.exports.delete_report_view": {"view": "{spare_view}"},
	"sellos.reports.exports.export_report": {"report": "leads-by-stage", "format": "csv"},
	"sellos.reports.exports.list_report_schedules": {},
	"sellos.reports.exports.save_report_schedule": {
		"schedule": "{spare_schedule}",
		"values": {"range_days": 14},
	},
	"sellos.reports.exports.delete_report_schedule": {"schedule": "{spare_schedule_two}"},
	"sellos.reports.exports.send_report_schedule_now": {"schedule": "{spare_schedule}"},
	# SOS-P2-01: blank values keep what is saved, so the Company Admin's call changes nothing.
	"sellos.telephony.settings.get_telephony_settings": {},
	"sellos.telephony.settings.save_telephony_settings": {},
	"sellos.telephony.settings.check_connection": {},
	# SOS-P5-07: blank values keep what is saved.
	"sellos.voice.agent.settings.get_voice_agent_settings": {},
	"sellos.voice.agent.settings.save_voice_agent_settings": {},
	# SOS-P2-07: click to call. The Company Admin has a mobile number here and the fake provider is on, and
	# the call log is the Company Admin's own, ended, so its outcome can be recorded.
	"sellos.telephony.click_to_call.call_preview": {"lead": "{lead}"},
	"sellos.telephony.click_to_call.click_to_call": {"lead": "{lead}"},
	"sellos.telephony.click_to_call.call_status": {"call_log": "{call_log}"},
	"sellos.telephony.click_to_call.pending_outcomes": {},
	"sellos.telephony.click_to_call.record_outcome": {"call_log": "{call_log}", "outcome": "Wrong number"},
	# SOS-P2-10: calling hours and the do not call list.
	"sellos.telephony.hours.get_calling_hours": {},
	"sellos.telephony.hours.save_calling_hours": {"enabled": 0},
	"sellos.telephony.dnd.import_do_not_call_list": {"text": DND_SAMPLE},
	"sellos.telephony.dnd.do_not_call_summary": {},
	# SOS-P3-02: the raw transaction table, read on the control site only.
	"sellos.intel.api.list_raw_transactions": {},
	# SOS-P3-04: micro markets and buildings, on spare ones the setUp makes. The split, the merge and the archive
	# each use their own spare markets, so one call never takes another's away.
	"sellos.intel.buildings_api.list_micro_markets": {},
	"sellos.intel.buildings_api.save_micro_market": {
		"name": "{market_edit}",
		"values": {"parent_area": "P304 Edited City"},
	},
	"sellos.intel.buildings_api.split_micro_market": {
		"name": "{market_split}",
		"first": {"market_name": "P304 Split One"},
		"second": {"market_name": "P304 Split Two"},
		"assignments": {"{market_split_building}": 0},
	},
	"sellos.intel.buildings_api.merge_micro_markets": {"keep": "{market_keep}", "merge": "{market_merge}"},
	"sellos.intel.buildings_api.set_micro_market_archived": {"name": "{market_archive}", "archived": 1},
	"sellos.intel.buildings_api.load_micro_markets": {},
	"sellos.intel.buildings_api.list_buildings": {},
	"sellos.intel.buildings_api.get_building": {"name": "{spare_building}"},
	"sellos.intel.buildings_api.save_building": {
		"name": "{spare_building}",
		"values": {"village": "P304 Edit"},
	},
	"sellos.intel.buildings_api.correct_building": {
		"name": "{spare_building}",
		"values": {"district": "P304 Corrected"},
	},
	"sellos.intel.buildings_api.confirm_building": {"name": "{spare_building}"},
	"sellos.intel.buildings_api.load_building_seed_list": {"text": "P304 Matrix Seed"},
	"sellos.intel.buildings_api.load_platform_master": {},
	# SOS-P3-12: the Index II names of one registration record, a Company Admin only.
	"sellos.intel.party_names.get_party_names": {"source_record_id": "P105-none"},
	"sellos.access.field_history.getdoc": {"doctype": "Client", "name": "{client}"},
	"sellos.access.field_history.get_docinfo": {"doctype": "Client", "name": "{client}"},
	# SOS-P6-11: the fake WhatsApp provider is on and connected, the lead's conversation has a customer
	# message from just now, and an approved template exists, so every call of the Company Admin works.
	"sellos.whatsapp.settings.get_whatsapp_settings": {},
	"sellos.whatsapp.settings.save_whatsapp_settings": {"display_number": "P611 Matrix"},
	"sellos.whatsapp.settings.check_whatsapp_connection": {},
	"sellos.whatsapp.settings.list_whatsapp_templates": {},
	"sellos.whatsapp.settings.save_whatsapp_template": {"name": "p611_matrix", "body": "Hello {{1}}"},
	"sellos.whatsapp.conversations.list_whatsapp_conversations": {},
	"sellos.whatsapp.conversations.get_whatsapp_conversation": {"conversation": "{wa_conversation}"},
	"sellos.whatsapp.conversations.send_whatsapp_message": {"lead": "{lead}", "text": "p611 hello"},
	"sellos.whatsapp.conversations.hand_off_whatsapp_conversation": {"conversation": "{wa_conversation}"},
	"sellos.whatsapp.conversations.close_whatsapp_conversation": {"conversation": "{wa_conversation}"},
	"sellos.whatsapp.conversations.whatsapp_conversation_for_lead": {"lead": "{lead}"},
}

# What a refused call may raise. A role check raises PermissionError. A record the user can't see
# may also read as missing.
REFUSALS = (frappe.PermissionError, frappe.DoesNotExistError)


def fill(args, names):
	if isinstance(args, dict):
		return {fill(key, names): fill(value, names) for key, value in args.items()}
	if isinstance(args, list):
		return [fill(value, names) for value in args]  # SOS-P4-03: an order is a list of names
	if isinstance(args, str) and args.startswith("{") and args.endswith("}"):
		return names[args[1:-1]]
	return args


def as_who(who):
	frappe.set_user("Guest" if WHO[who] is None else TEST_USERS[WHO[who]]["email"])


def call(method, args):
	"""Call a method in this process as the current user. Returns everything the caller could see:
	the return value and the response a loader fills."""
	frappe.local.response = frappe._dict({"docs": []})
	fn = frappe.get_attr(method)
	result = fn(**args)
	return json.dumps([result, dict(frappe.local.response)], default=str)


def leaks(text):
	forms = [SECRET_NAME, ACTIVITY_NOTE, *phones.forms(SECRET_PHONE)]
	return [form for form in forms if form in text]


class TestPermissionSuiteCoverage(IntegrationTestCase):
	"""SOS-P1-05: the matrix covers every whitelisted method, and a gap fails the build."""

	def test_the_matrix_covers_every_whitelisted_sellos_method(self):
		load_declared_modules()
		import_all_sellos_modules()
		registry = {p: r for p, r in declared_methods().items() if ".test_" not in p}
		open_methods = [p for p in undeclared_whitelisted_methods() if ".test_" not in p]
		problems = matrix_problems(MATRIX, registry, open_methods)
		self.assertEqual(problems, [], "\n".join(problems))

	def test_every_matrix_method_has_sample_arguments_so_the_suite_calls_it(self):
		missing = sorted(set(MATRIX) - set(SAMPLE_CALLS))
		self.assertEqual(missing, [], f"Add SAMPLE_CALLS entries for: {missing}")
		self.assertEqual(sorted(set(SAMPLE_CALLS) - set(MATRIX)), [], "SAMPLE_CALLS names a stale method")

	def test_the_suite_covers_all_six_roles_an_outsider_and_a_guest(self):
		self.assertEqual(set(ROLE_KEYS.values()) | {"outsider", "guest"}, set(WHO))
		# SOS-SETUP-35: every SellOS role is in the suite, the Sales Manager included.
		self.assertEqual(set(ROLE_KEYS), set(ROLES))
		self.assertEqual({role for roles in MATRIX.values() for role in roles} - set(ROLE_KEYS), set())

	def test_a_sellos_method_with_no_declaration_is_refused_before_it_runs(self):
		self.assertTrue(is_refused("sellos.crm.api.not_declared_anywhere"))
		self.assertFalse(is_refused("sellos.crm.api.list_leads"))


class TestEveryMethodAsEveryone(IntegrationTestCase):
	"""SOS-P1-05: each method, as each role, an outsider and a guest, against one company's data."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_roles()
		create_test_users()

	def setUp(self):
		frappe.set_user(TEST_USERS[ADMIN]["email"])
		client = frappe.get_doc(
			{
				"doctype": "Client",
				"client_name": SECRET_NAME,
				"client_type": "Buyer",
				"phone": SECRET_PHONE,
			}
		).insert()
		other = frappe.get_doc(
			{"doctype": "Client", "client_name": "P116 Other Buyer", "client_type": "Buyer"}
		).insert()
		lead = frappe.get_doc({"doctype": "Lead", "client": client.name, "source": "Website"}).insert()
		spare = frappe.get_doc({"doctype": "Lead Source", "source_name": "P120 Spare Source"}).insert()
		spare_outcome = frappe.get_doc(
			{"doctype": "Call Outcome", "outcome_name": "P121 Spare Outcome"}
		).insert()
		spare_reason = frappe.get_doc({"doctype": "Lost Reason", "reason_name": "P121 Spare Reason"}).insert()
		spare_user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "p117_spare_agent@example.com",
				"first_name": "P117 Spare",
				"send_welcome_email": 0,
				"roles": [{"role": "SellOS Agent"}],
			}
		)
		spare_user.flags.ignore_permissions = True
		spare_user.insert()
		spare_team = frappe.get_doc(
			{
				"doctype": "Sales Team",
				"team_name": "P118 Spare Team",
				"manager": TEST_USERS["sales_manager"]["email"],
			}
		).insert()
		firm_user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "p701_spare_partner@example.com",
				"first_name": "P701 Spare",
				"send_welcome_email": 0,
				"roles": [{"role": "SellOS Channel Partner"}],
			}
		)
		firm_user.flags.ignore_permissions = True
		firm_user.insert()
		spare_firm = frappe.get_doc(
			{
				"doctype": "Channel Partner Firm",
				"firm_name": "P701 Spare Firm",
				"contact_user": firm_user.name,
				"contact_person": "P701 Spare",
				"email": firm_user.name,
			}
		).insert()
		spare_firm.db_set("status", "Pending approval")
		spare_registrations = []
		for seed in (7022, 7023):
			spare_client = frappe.get_doc(
				{"doctype": "Client", "client_name": f"P702 Spare Buyer {seed}", "client_type": "Buyer"}
			).insert()
			spare_lead = frappe.get_doc(
				{"doctype": "Lead", "client": spare_client.name, "source": "Channel partner"}
			).insert()
			spare_registrations.append(
				frappe.get_doc(
					{
						"doctype": "Partner Registration",
						"buyer_name": spare_client.client_name,
						"partner_firm": spare_firm.name,
						"partner_user": firm_user.name,
						"lead": spare_lead.name,
						"client": spare_client.name,
					}
				)
				.insert()
				.name
			)
		spare_developer = frappe.get_doc(
			{"doctype": "Developer", "developer_name": "P401 Spare Developer"}
		).insert()
		spare_project = frappe.get_doc(
			{
				"doctype": "Project",
				"project_name": "P401 Spare Project",
				"developer": spare_developer.name,
				"rera_number": "P51800040101",
				"city": "Mumbai",
			}
		).insert()
		spare_share = frappe.get_doc(
			{"doctype": "Partner Share", "project": spare_project.name, "all_firms": 1, "all_units": 1}
		).insert()
		spare_unit = frappe.get_doc(
			{"doctype": "Unit", "project": spare_project.name, "unit_number": "P401-101", "carpet_area": 600}
		).insert()
		spare_unit_hold, spare_unit_held, spare_unit_block, spare_unit_blocked = (
			frappe.get_doc(
				{
					"doctype": "Unit",
					"project": spare_project.name,
					"unit_number": f"P706-{number}",
					"carpet_area": 600,
					"status": status,
				}
			).insert()
			for number, status in (("1", "Available"), ("2", "Held"), ("3", "Available"), ("4", "Blocked"))
		)
		# SOS-P7-10: an Available unit to book, and a Booked unit with the deal to cancel.
		spare_unit_book = frappe.get_doc(
			{
				"doctype": "Unit",
				"project": spare_project.name,
				"unit_number": "P710-1",
				"carpet_area": 600,
				"status": "Available",
			}
		).insert()
		spare_unit_booked = frappe.get_doc(
			{
				"doctype": "Unit",
				"project": spare_project.name,
				"unit_number": "P710-2",
				"carpet_area": 600,
				"status": "Booked",
			}
		).insert()
		spare_booking_deal = frappe.get_doc(
			{
				"doctype": "Deal",
				"client": client.name,
				"lead": lead.name,
				"unit": spare_unit_booked.name,
				"price": 5000000,
				"booking_amount": 100000,
				"splits": [{"party_type": "Company", "percent": 100}],
			}
		).insert(ignore_permissions=True)
		# SOS-P7-09: an Available unit to add, and four shortlists of the secret client (see SAMPLE_CALLS).
		shortlist_unit = frappe.get_doc(
			{"doctype": "Unit", "project": spare_project.name, "unit_number": "P709-1", "carpet_area": 600}
		).insert()

		def make_shortlist(title, *units):
			return frappe.get_doc(
				{
					"doctype": "Shortlist",
					"title": title,
					"client": client.name,
					"items": [{"kind": "Unit", "unit": unit} for unit in units],
				}
			).insert()

		shortlist = make_shortlist("P709 Suite", spare_unit.name, spare_unit_block.name)
		shortlist_add = make_shortlist("P709 Add", spare_unit_blocked.name)
		shortlist_remove = make_shortlist("P709 Remove", spare_unit_held.name)
		shortlist_archive = make_shortlist("P709 Archive", spare_unit.name)
		spare_tower, spare_tower_two = (
			frappe.get_doc(
				{
					"doctype": "Project Tower",
					"project": spare_project.name,
					"tower_name": name,
					"floors": [{"floor_number": 1}, {"floor_number": 2}],
				}
			).insert()
			for name in ("P705 Suite Tower", "P705 Suite Tower Two")
		)
		# SOS-P7-07: a price list in force, two plans and a cost sheet for the spare unit.
		frappe.db.set_single_value("SellOS Settings", "cost_rates_saved", 1)
		frappe.get_doc(
			{
				"doctype": "Price List",
				"project": spare_project.name,
				"title": "P707 Suite list",
				"effective_from": "2020-01-01",
				"base_rate": 10000,
			}
		).insert()
		spare_plan, spare_plan_two = (
			frappe.get_doc(
				{
					"doctype": "Payment Plan",
					"project": spare_project.name,
					"plan_name": name,
					"plan_type": "Down payment",
					"instalments": [{"label": "On booking", "percent": 100}],
				}
			).insert()
			for name in ("P707 Suite plan", "P707 Suite plan two")
		)
		spare_sheet = cost_sheet.make_cost_sheet(spare_unit.name, spare_plan.name)
		spare_property = frappe.get_doc(
			{
				"doctype": "Property",
				"title": "P401 Spare Property",
				"property_type": "Apartment",
				"city": "Pune",
				"carpet_area": 500,
			}
		).insert()
		# SOS-P4-02: a complete draft listing of a property of its own.
		listed_property = frappe.get_doc(
			{
				"doctype": "Property",
				"title": "P402 Suite Property",
				"property_type": "Apartment",
				"city": "Pune",
				"carpet_area": 500,
			}
		).insert()
		spare_listing = frappe.get_doc(
			{
				"doctype": "Listing",
				"title": "P402 Suite Listing",
				"listing_type": "Direct",
				"property": listed_property.name,
				"asking_price": 5000000,
				"description": "P402 suite description",
			}
		).insert()
		# SOS-P4-03: two draft listings and two library files, the second listing holding both files.
		media_assets = [
			frappe.get_doc(
				{
					"doctype": "Media Asset",
					"title": f"P403 Suite Asset {n}",
					"media_type": "Photo",
					"file": f"/files/p403-suite-{n}.png",
					"size_bytes": 100,
				}
			).insert()
			for n in (1, 2)
		]
		media_listing = frappe.get_doc(
			{"doctype": "Listing", "title": "P403 Suite Media Listing", "listing_type": "Direct"}
		).insert()
		order_listing = frappe.get_doc(
			{
				"doctype": "Listing",
				"title": "P403 Suite Order Listing",
				"listing_type": "Direct",
				"media": [{"media_asset": media_assets[1].name}, {"media_asset": media_assets[0].name}],
			}
		).insert()
		# SOS-P4-05: a draft mandate of a seller lead of its own.
		seller = frappe.get_doc(
			{"doctype": "Client", "client_name": "P405 Suite Seller", "client_type": "Seller"}
		).insert()
		seller_lead = frappe.get_doc(
			{"doctype": "Lead", "client": seller.name, "source": "Website", "pipeline": "Seller"}
		).insert()
		spare_mandate = frappe.get_doc(
			{
				"doctype": "Mandate",
				"lead": seller_lead.name,
				"mandate_type": "Exclusive",
				"term_months": 6,
				"fee_percent": 1.5,
				"status": "Draft",
			}
		).insert()
		# SOS-LOOP: DocuSeal is a fake server on this machine, and the seller has an email to be sent the document.
		from sellos.tests.fake_docuseal import KEY, FakeDocuSeal

		fake_docuseal = FakeDocuSeal().start()
		self.addCleanup(fake_docuseal.stop)
		frappe.db.set_value("Client", seller.name, "email", "p105.seller@example.com")
		docuseal_settings = frappe.get_doc("SellOS Settings")
		docuseal_settings.update(
			{
				"docuseal_url": fake_docuseal.url,
				"docuseal_api_key": KEY,
				"docuseal_signer_name": "P105 Company Signer",
				"docuseal_signer_email": "p105.signer@example.com",
			}
		)
		docuseal_settings.save(ignore_permissions=True)
		# SOS-LOOP: a note of the company admin's own lead, for the notes methods.
		from sellos.crm import notes as loop_notes

		loop_notes.ensure_note_types()
		note_type = frappe.get_all("Note Type", pluck="name", order_by="sort_order asc", limit=1)[0]
		spare_note = frappe.get_doc(
			{"doctype": "Record Note", "lead": lead.name, "note_type": note_type, "body": "p105 suite"}
		).insert()
		# SOS-P4-06: a pending deal of the seller's client, for a property of its own, the whole split the company's.
		spare_deal = frappe.get_doc(
			{
				"doctype": "Deal",
				"client": seller.name,
				"property": spare_property.name,
				"price": 5000000,
				"splits": [{"party_type": "Company", "percent": 100}],
			}
		).insert()
		# SOS-P7-04: a rate on the spare project and a Due payout of the spare firm on the spare deal.
		spare_rate = frappe.get_doc(
			{
				"doctype": "Commission Rate",
				"project": spare_project.name,
				"rate_type": "Percentage",
				"value": 1,
				"start_date": "2020-01-01",
			}
		).insert()
		spare_payout = frappe.get_doc(
			{
				"doctype": "Commission Payout",
				"deal": spare_deal.name,
				"partner_firm": spare_firm.name,
				"booking_date": "2026-01-01",
				"commission_due": 1000,
			}
		).insert(ignore_permissions=True)
		before = set(Path(frappe.get_site_path("public", "files")).glob("media-*"))
		self.addCleanup(self._remove_media_files, before)
		self.addCleanup(self._remove_agreement_files)
		rule_team = frappe.get_doc(
			{
				"doctype": "Sales Team",
				"team_name": "P119 Rule Team",
				"manager": TEST_USERS["sales_manager"]["email"],
			}
		).insert()
		spare_rule = frappe.get_doc(
			{
				"doctype": "Lead Assignment Rule",
				"rule_name": "P119 Spare Rule",
				"rule_type": "Round robin",
				"team": rule_team.name,
			}
		).insert()
		task = frappe.get_doc(
			{
				"doctype": "Lead Task",
				"lead": lead.name,
				"title": "P122 spare follow up",
				"due_date": "2030-01-01",
			}
		).insert()
		visit = frappe.get_doc(
			{
				"doctype": "Site Visit",
				"lead": lead.name,
				"project_name": "P125 Permission Tower",
				"visit_datetime": "2030-01-01 10:00:00",
			}
		).insert()
		frappe.get_doc(
			{
				"doctype": "Lead Activity",
				"lead": lead.name,
				"activity_type": "Note",
				"activity_date": now_datetime(),
				"notes": ACTIVITY_NOTE,
			}
		).insert()
		# P1.13: a grant that has already ended, so the support user reads nothing in these tests.
		support_user = TEST_USERS["platform_admin"]["email"]
		grant = support.grant_support_access(support_user, 60)
		support.revoke_support_access(grant["name"])
		# SOS-P1-23: the Company Admin's own notification. Any other user is told it is not found.
		notification = notifications.notify(
			TEST_USERS[ADMIN]["email"], notifications.LEAD_ASSIGNED, "P123 permission suite"
		)
		# SOS-P2-07: click to call rings the user's own mobile, through the fake provider.
		frappe.db.set_value("User", TEST_USERS[ADMIN]["email"], "mobile_no", phones.in_mobile(2007))
		frappe.db.set_single_value("Telephony Settings", "provider", "fake")
		save_telephony_settings("FAKEOK-P207", "token-for-the-fake", LANDLINE_022)
		call_row = frappe.get_doc(
			{
				"doctype": "Call Log",
				"lead": lead.name,
				"provider": "fake",
				"call_id": "fake-p207-suite",
				"purpose": "Service",
				"state": "completed",
				"agent": TEST_USERS[ADMIN]["email"],
			}
		).insert(ignore_permissions=True)
		# SOS-P6-11: a connected fake WhatsApp number and a conversation that is open for free text.
		frappe.db.set_single_value("WhatsApp Settings", "provider", "fake")
		wa_settings = frappe.get_doc("WhatsApp Settings")
		wa_settings.access_token = "FAKEOK-P611"
		wa_settings.app_secret = "fake-secret-p611"
		wa_settings.phone_number_id = "611000611"
		wa_settings.flags.ignore_permissions = True
		wa_settings.save()
		wa_conversation = frappe.get_doc(
			{
				"doctype": "WhatsApp Conversation",
				"lead": lead.name,
				"state": "Open",
				"last_inbound_on": now_datetime(),
			}
		).insert(ignore_permissions=True)
		ensure_default_definitions()  # SOS-P5-01
		spare_view = frappe.get_doc(
			{"doctype": "Saved Report View", "title": "P504 Spare View", "report": "leads-by-stage"}
		).insert(ignore_permissions=True)
		spare_schedules = [
			frappe.get_doc(
				{
					"doctype": "Report Schedule",
					"title": f"P504 Spare Schedule {n}",
					"report": "leads-by-stage",
					"recipients": [{"user": TEST_USERS["company_admin"]["email"]}],
				}
			).insert(ignore_permissions=True)
			for n in (1, 2)
		]
		# SOS-P3-04: spare micro markets (one each for the split, the merge pair, the archive and the edit) and a
		# building under the one that is split.
		spare_markets = {}
		for key in ("edit", "split", "keep", "merge", "archive"):
			spare_markets[key] = frappe.get_doc(
				{
					"doctype": "Micro Market",
					"market_name": f"P304 Spare {key}",
					"country": "India",
					"parent_area": "P304 City",
				}
			).insert()
		spare_building = frappe.get_doc(
			{
				"doctype": "Building",
				"building_name": "P304 Spare Building",
				"micro_market": spare_markets["split"].name,
			}
		).insert()
		self.names = {
			"wa_conversation": wa_conversation.name,
			"call_log": call_row.name,
			"notification": notification,
			"task": task.name,
			"visit": visit.name,
			"client": client.name,
			"client_other": other.name,
			"lead": lead.name,
			"lead_list": [lead.name],
			"market_edit": spare_markets["edit"].name,
			"market_split": spare_markets["split"].name,
			"market_keep": spare_markets["keep"].name,
			"market_merge": spare_markets["merge"].name,
			"market_archive": spare_markets["archive"].name,
			"spare_building": spare_building.name,
			"market_split_building": spare_building.name,
			"spare_source": spare.name,
			"spare_outcome": spare_outcome.name,
			"spare_reason": spare_reason.name,
			"spare_user": spare_user.name,
			"spare_team": spare_team.name,
			"spare_firm": spare_firm.name,
			"spare_registration": spare_registrations[0],
			"spare_registration_two": spare_registrations[1],
			"spare_rule": spare_rule.name,
			"spare_view": spare_view.name,
			"spare_schedule": spare_schedules[0].name,
			"spare_schedule_two": spare_schedules[1].name,
			"spare_project": spare_project.name,
			"spare_share": spare_share.name,
			"spare_unit": spare_unit.name,
			"spare_unit_hold": spare_unit_hold.name,
			"spare_unit_held": spare_unit_held.name,
			"spare_unit_block": spare_unit_block.name,
			"spare_unit_blocked": spare_unit_blocked.name,
			"spare_unit_book": spare_unit_book.name,
			"spare_booking_deal": spare_booking_deal.name,
			"shortlist_unit": shortlist_unit.name,
			"shortlist": shortlist.name,
			"shortlist_item": shortlist.items[0].name,
			"shortlist_item_two": shortlist.items[1].name,
			"shortlist_add": shortlist_add.name,
			"shortlist_remove": shortlist_remove.name,
			"shortlist_remove_item": shortlist_remove.items[0].name,
			"shortlist_archive": shortlist_archive.name,
			"spare_plan": spare_plan.name,
			"spare_plan_two": spare_plan_two.name,
			"spare_sheet": spare_sheet["name"],
			"spare_tower": spare_tower.name,
			"spare_tower_two": spare_tower_two.name,
			"spare_property": spare_property.name,
			"spare_listing": spare_listing.name,
			"spare_mandate": spare_mandate.name,
			"spare_deal": spare_deal.name,
			"spare_note": spare_note.name,
			"note_type": note_type,
			"spare_mandate_lead": seller_lead.name,
			"spare_rate": spare_rate.name,
			"spare_payout": spare_payout.name,
			"media_listing": media_listing.name,
			"order_listing": order_listing.name,
			"media_asset": media_assets[0].name,
			"media_asset_two": media_assets[1].name,
			"rule_team": rule_team.name,
			"agent": TEST_USERS["agent"]["email"],
			"support_user": support_user,
			"grant": grant["name"],
		}
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.response = frappe._dict()
		frappe.db.rollback()

	@staticmethod
	def _remove_agreement_files():
		for pattern in ("p701_suite_agreement*", "p705_suite_brochure*", "p405_suite_*"):
			for path in Path(frappe.get_site_path("private", "files")).glob(pattern):
				path.unlink()

	@staticmethod
	def _remove_media_files(before):
		"""SOS-P4-03: the files the suite's upload call wrote."""
		for path in set(Path(frappe.get_site_path("public", "files")).glob("media-*")) - before:
			path.unlink()

	def args(self, method):
		return fill(SAMPLE_CALLS[method], self.names)

	def test_the_seeded_data_is_what_the_company_admin_sees(self):
		# Not vacuous: the secret is really returned to someone who may see it.
		as_who("company_admin")
		self.assertTrue(leaks(call("sellos.crm.api.get_lead", self.args("sellos.crm.api.get_lead"))))
		self.assertTrue(leaks(call("sellos.crm.api.list_clients", {})))

	def test_a_role_that_is_not_allowed_is_refused_and_gets_nothing(self):
		checked = 0
		for method, allowed in MATRIX.items():
			for who in WHO:
				if who in {ROLE_KEYS[role] for role in allowed}:
					continue
				as_who(who)
				with self.subTest(method=method, who=who), self.assertRaises(frappe.PermissionError):
					call(method, self.args(method))
				checked += 1
		self.assertGreater(checked, 0)

	def test_an_allowed_role_never_gets_another_users_records(self):
		"""The Agent and the Channel Partner may call the reads and writes, but the company's record
		is not theirs: each call is refused, or returns nothing of it."""
		for method, allowed in MATRIX.items():
			for role in allowed:
				who = ROLE_KEYS[role]
				if who == "company_admin":
					continue
				as_who(who)
				with self.subTest(method=method, who=who):
					try:
						text = call(method, self.args(method))
					except REFUSALS:
						continue
					self.assertEqual(leaks(text), [])

	def test_the_company_admin_may_call_every_method(self):
		for method, allowed in MATRIX.items():
			if "SellOS Company Admin" not in allowed:
				continue  # SOS-P7-01: a partner's own firm methods are the partner's, and refuse the admin
			as_who("company_admin")
			with self.subTest(method=method):
				call(method, self.args(method))  # raises if refused

	def test_nobody_but_the_company_admin_is_shown_a_full_phone_number(self):
		for method in MATRIX:
			for who in WHO:
				if who == "company_admin":
					continue
				as_who(who)
				try:
					text = call(method, self.args(method))
				except (frappe.ValidationError, *REFUSALS):
					continue
				with self.subTest(method=method, who=who):
					for form in phones.forms(SECRET_PHONE):
						self.assertNotIn(form, text)

	def test_an_outsider_and_a_guest_get_nothing_from_any_method(self):
		"""A user from another company, and a signed out visitor, are refused by every method."""
		for method in MATRIX:
			for who in ("outsider", "guest"):
				as_who(who)
				with self.subTest(method=method, who=who), self.assertRaises(frappe.PermissionError):
					call(method, self.args(method))
