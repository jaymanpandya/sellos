# SellOS permission table

Story P1.04. Every role name is created from code by `sellos/access/roles.py` on install and on
every migrate. Nothing here is set up in the Desk.

## Roles and where they work

| Role | Role name in code | Web app areas | Frappe desk |
| --- | --- | --- | --- |
| Platform Admin | `SellOS Platform Admin` | platform, home, profile | Yes, the only role, control site only |
| Company Admin | `SellOS Company Admin` | company, crm, reports, home, profile | No |
| Agent | `SellOS Agent` | crm, home, profile | No |
| Channel Partner | `SellOS Channel Partner` | partner, home, profile | No |
| Client | `SellOS Client` | client, home, profile | No |
| Sales Manager | `SellOS Sales Manager` | crm, reports, home, profile | No |

The Sales Manager was approved by Jayman on 13 November 2026 (SOS-SETUP-35) and built in SOS-P1-18. It sees
and edits the leads, activities, tasks and site visits of the agents in the teams it manages (and any lead it
owns itself), reassigns leads within the team, reads the team's report, and sees phone numbers masked as an
Agent does. A Company Admin makes the teams (a manager and agents, an agent in at most one team). The scope
is "team" in `sellos/access/lead_permissions.py` (`scope_for`, `team_members`, `visible_users`).

The areas come from `frontend/src/personas.js`. The desk block is `sellos/access/desk_guard.py`.

## Data rules

Sees (CRM data, P1.06): "all" is every record on the site, "own" is the leads the user owns, is assigned, or
has a Frappe share on, plus the records that follow those leads. "Team" (Sales Manager, SOS-P1-18) is the leads owned by or assigned to the manager or to the agents of the teams they manage, plus the records that follow those leads; a Sales Manager edits them like an Agent, with masked phone numbers. "None" is nothing.

| Data | Platform Admin | Company Admin | Agent | Channel Partner | Client |
| --- | --- | --- | --- | --- | --- |
| Lead | None, or read only while a support grant is active (P1.13) | All, edit, reassign, archive | Own, edit own | Own, create and edit own | None |
| Client (record) | None | All, full phone | Created by them, or on a lead they can see. Masked phone | Same as Agent | None |
| Activity, Task, Site Visit | None | All, create and edit | Follow the lead, create and edit | Follow the lead, read only | None |
| Delete | Nobody. Records are archived | | | | |
| Bulk export | Yes (`export` permission) | No | No | No | No |
| Change tracking | Every field of all five DocTypes | | | | |
| SellOS Settings | System Manager only (the wizard in P1.03 writes it for the Company Admin) | | | | |

"Own" means the lead's owner or its `assigned_to` user. Sharing uses Frappe's normal share. A shared
lead brings its timeline with it. The rules are in `sellos/access/lead_permissions.py`. Phone numbers
sit at permission level 1, so a direct read (`/api/resource/Client`) gives an Agent or Partner only
`phone_masked`. The Platform Admin's `export` and level 1 rows exist on the DocTypes but give no data
on a company site, because the data scope above is "none".

## API methods

* A method is written with `@sellos_api(<roles>)` from `sellos/access/registry.py`, never with a
  bare `@frappe.whitelist()`.
* The decorator checks the roles on every call.
* A whitelisted method in the `sellos` package that has no declaration is refused with a 403 for
  every user, before it runs (`guard_api`, a `before_request` hook).
* `undeclared_whitelisted_methods()` lists any such method, so the matrix in P1.05 can fail the
  build on it.

| Method | Roles |
| --- | --- |
| `sellos.crm.api.list_clients`, `save_client`, `list_leads`, `get_lead`, `save_lead`, `set_archived` | Company Admin, Agent, Channel Partner |
| `sellos.crm.api.get_board`, `lead_filter_options` (SOS-P1-24, the pipeline board and the filter choices for the lead list and board. Phone numbers masked as the viewer's role requires) | Company Admin, Agent, Sales Manager, Channel Partner |
| `sellos.crm.api.list_notifications`, `mark_notification_read`, `mark_all_notifications_read` (SOS-P1-23, the bell. Each role reads and changes only its own) | Company Admin, Agent, Sales Manager, Channel Partner |
| `sellos.crm.api.list_lead_sources` (P1.20, the lead source list for a picker. A Company Admin also sees the disabled ones) | Company Admin, Agent, Channel Partner |
| `sellos.crm.api.save_lead_source`, `delete_lead_source` (P1.20, extend, disable or delete a source. A source in use is never deleted) | Company Admin |
| `sellos.crm.api.list_stages` (SOS-P1-07, the buyer pipeline's stages with their lead counts) | Company Admin, Agent, Channel Partner |
| `sellos.crm.api.move_lead_stage` (SOS-P1-07, move a lead to any stage whatever its consent status, logged, with a warning and no refusal when Contacted has no live Consent Record) | Company Admin, Agent, Sales Manager |
| `sellos.crm.api.list_call_outcomes`, `list_lost_reasons` (SOS-P1-21, the lists for the call form and the move to Closed lost. A Company Admin also sees the disabled ones) | Company Admin, Agent, Sales Manager |
| `sellos.crm.api.log_call` (SOS-P1-21, a call logged by hand with its outcome, notes and duration, and the follow up the outcome needs. Whatever the consent status) | Company Admin, Agent, Sales Manager |
| `sellos.crm.api.save_call_outcome`, `delete_call_outcome`, `save_lost_reason`, `delete_lost_reason` (SOS-P1-21, edit the two lists. One in use is never deleted) | Company Admin |
| `sellos.access.users.list_users`, `user_open_work` (SOS-P1-17, the Company Admins, Agents and Channel Partners on the site with their mobile number, whether click to call works for them, and their open leads and tasks. A Platform Admin is never listed) | Company Admin |
| `sellos.access.users.invite_user`, `resend_invitation` (SOS-P1-17, a user made with one of Company Admin, Agent or Channel Partner and emailed a link to set a password. Never the Platform Admin role) | Company Admin |
| `sellos.crm.response_times.get_response_limits`, `save_response_limits` (SOS-P7-13, the two response time limits, 1 to 2880 minutes. The check that alerts runs from the scheduler, not from a method) | Company Admin |
| `sellos.access.users.save_user` (SOS-P1-17, a user's name, Indian mobile number as +91 and ten digits, or role. A user who holds the Platform Admin role is not touched, and nobody changes their own role) | Company Admin |
| `sellos.access.users.deactivate_user`, `reactivate_user` (SOS-P1-17, deactivating ends sign in and every session at once. SOS-P1-19: a user with open leads, follow ups or future visits is not deactivated until the caller names who takes them, `reassign_to` or `distribute`; nothing is left with an inactive user. Not yourself, not the last active Company Admin. Nothing is deleted) | Company Admin |
| `sellos.access.partner_firms.list_partner_firms`, `invite_partner_firm`, `update_partner_firm`, `upload_agreement_for_firm` (SOS-P7-01, channel partner firms: invite a firm by email through SOS-P1-17's invitation with the Channel Partner role, correct its details, upload its signed agreement. The PAN, the full phone number and the agreement are seen by a Company Admin only; the agreement is a private file) | Company Admin |
| `sellos.access.partner_firms.approve_partner_firm`, `suspend_partner_firm`, `reinstate_partner_firm` (SOS-P7-01, only a Company Admin approves a firm that is Pending approval, suspends one with a reason, or reinstates a suspended one. Each change is logged with who and when. Nothing is deleted) | Company Admin |
| `sellos.access.partner_firms.my_partner_firm`, `submit_partner_details`, `upload_my_agreement` (SOS-P7-01, a partner reads its own firm's status, with the phone masked and the PAN and agreement only as given or not, and completes the details of an Invited or Pending firm, which moves it to Pending approval. A partner whose firm is not Approved registers and sees no lead, and sees no inventory) | Channel Partner |
| `sellos.access.partner_registrations.partner_registration_form`, `register_buyer`, `my_partner_registrations` (SOS-P7-02, a partner of an Approved firm registers a buyer: name, phone, project of interest, a note and whether the buyer agreed, with the company's consent wording shown. The phone and email are matched by SOS-P1-16, a buyer the company already has makes no second lead and the partner is told only "Not accepted: this buyer is already registered with the company.", and the company setting Partner lead limit (default 20 an hour) refuses the next one. A partner sees only their own registrations, with the phone masked, and changes nothing afterwards; a partner whose firm is not Approved is refused) | Channel Partner |
| `sellos.access.partner_registrations.list_partner_registrations`, `approve_partner_registration`, `reject_partner_registration` (SOS-P7-02, only a Company Admin approves a registration, which is then protected in the partner's name for the company setting Partner protection days (default 90) from the approval, or rejects it with a reason; each move is logged) | Company Admin |
| `sellos.access.partner_registrations.change_lead_partner` (SOS-P7-02, only a Company Admin changes the partner on a lead, also while the registration is protected; the change is logged. A save of a lead by anyone else that changes the partner is refused. Protection never blocks a call, a message or an agent's work) | Company Admin |
| `sellos.access.partner_registrations.get_partner_settings`, `save_partner_settings` (SOS-P7-02, the company settings Partner lead limit, Partner protection days and Consent wording) | Company Admin |
| `sellos.inventory.import_data.import_template`, `import_overview`, `preview_inventory_import`, `run_inventory_import` (SOS-P4-10C, a CSV of developers, projects, units, properties, listings or mandates: the template per record type, a dry run that writes nothing, and the import, which updates what it matches (projects on RERA number, units on project and unit number) instead of doubling it, imports listings as drafts and mandates unsigned, never sets a status, and writes a reconciliation report) | Company Admin |
| `sellos.inventory.partner_shares.partner_share_options`, `list_partner_shares`, `share_project`, `update_partner_share`, `withdraw_partner_share` (SOS-P7-03, a Company Admin shares a project with chosen Approved partner firms or with every Approved firm: all its units or chosen ones, its price list in force and chosen brochures, changes a share and withdraws it. Every share, change and withdrawal is logged with who and when. Nothing is deleted) | Company Admin |
| `sellos.inventory.partner_shares.my_shared_projects`, `my_shared_project` (SOS-P7-03, a partner of an Approved firm reads only what is shared with their firm, worked out at each call: a withdrawn share, an archived record or a firm that is not Approved stops showing at once. No other project, unit, price or file, and nothing about other partners or their registrations. The partner holds no read permission on any inventory record) | Channel Partner |
| `sellos.inventory.api.save_developer`, `save_project`, `save_unit`, `save_property`, `set_inventory_status` (SOS-P4-01, developers, projects with their RERA numbers, units and secondary properties. A unit's or property's status is Available, Held or Sold and every change is logged with who made it and when. Nothing is deleted) | Company Admin, Agent |
| `sellos.inventory.api.inventory_overview`, `get_project` (SOS-P4-01, read only; a Sales Manager reads inventory and can not change it. A Client, a Channel Partner and the Platform Admin see none) | Company Admin, Agent, Sales Manager |
| `sellos.inventory.api.set_inventory_archived` (SOS-P4-01, archives or restores a developer, project, unit or property. Nothing is deleted) | Company Admin |
| `sellos.inventory.structure.add_tower`, `add_floors`, `remove_floor`, `remove_tower`, `generate_floor_units`, `save_project_details`, `add_project_brochure`, `remove_project_brochure` (SOS-P7-05, towers or wings of a project with their floors, the units of a floor made from a pattern such as 1201 to 1208 (again changes nothing), the possession date, amenities and brochure files. Removing a tower or floor archives it and is refused when a unit on it is in any status but Available) | Company Admin, Agent |
| `sellos.inventory.structure.save_amenity` (SOS-P7-05, adds, archives or restores an entry of the amenity list projects choose from) | Company Admin |
| `sellos.inventory.holds.hold_unit`, `release_hold` (SOS-P7-06, an agent holds an Available unit for one of their own leads for the company's Unit hold hours, and releases a hold they made; a Company Admin releases any. Two holds on one unit never both succeed: the second is refused with who holds it and until when. A lapsed hold is released by the scheduler) | Company Admin, Agent |
| `sellos.inventory.holds.block_unit`, `unblock_unit`, `get_hold_settings`, `save_hold_settings` (SOS-P7-06, a Company Admin blocks an Available unit from sale or unblocks it, always with a reason, and sets the Unit hold hours) | Company Admin |
| `sellos.inventory.holds.unit_grid` (SOS-P7-06, read only: each tower's floors and units by status, filtered by configuration and status. A held unit shows its agent; the lead's name shows only to a user who may see that lead) | Company Admin, Agent, Sales Manager |
| `sellos.inventory.pricing.project_pricing` (SOS-P7-07, read only: a project's dated price lists with the one in force marked, its payment plans and the company's stamp duty, registration and GST percentages) | Company Admin, Agent, Sales Manager |
| `sellos.inventory.pricing.save_price_list`, `save_payment_plan`, `archive_payment_plan`, `save_cost_settings` (SOS-P7-07, a Company Admin makes a dated price list, which is never changed once made, makes and corrects payment plan templates whose instalments must add up to 100 percent, archives them, and sets the stamp duty, registration and GST percentages) | Company Admin |
| `sellos.inventory.cost_sheet.cost_sheet_options`, `make_cost_sheet`, `unit_cost_sheets`, `get_cost_sheet`, `cost_sheet_pdf` (SOS-P7-07, a cost sheet made from a unit, on screen and as a PDF with the company's branding. It keeps the price list and percentages it used and is never changed or deleted. A Company Admin sees every sheet, an Agent only the ones they made, a Sales Manager none) | Company Admin, Agent |
| `sellos.inventory.listings.listing_overview` (SOS-P4-02, read only: listings with their change history, and the units and properties that can be offered) | Company Admin, Agent, Sales Manager |
| `sellos.inventory.listings.save_listing`, `publish_listing`, `unpublish_listing` (SOS-P4-02, an Agent or a Company Admin makes a listing typed Primary, Direct or Partner, corrects it, publishes it and withdraws it. Publishing is refused, naming what is missing, unless it has a title, a type, a unit or a property, an asking price and a description. Every change is logged with who and when) | Company Admin, Agent |
| `sellos.inventory.listings.set_listing_archived` (SOS-P4-02, archives or restores a listing, which also unpublishes it; nothing is deleted) | Company Admin |
| `sellos.inventory.media.listing_media` (SOS-P4-03, read only: a listing's photos and videos in order, and the asset library they can be linked from) | Company Admin, Agent, Sales Manager |
| `sellos.inventory.media.upload_listing_media`, `link_listing_media`, `unlink_listing_media`, `reorder_listing_media` (SOS-P4-03, an Agent or a Company Admin uploads a photo (up to 5 MB) or a video (up to 20 MB) to the asset library and puts it on a listing, links one already in the library, takes one off, and changes the order. A file whose type or first bytes are not a JPG, PNG, WEBP, MP4, MOV or WEBM is refused. Nothing is deleted: a file taken off stays in the library) | Company Admin, Agent |
| `sellos.inventory.mandates.mandate_overview` (SOS-P4-05, read only: the mandates of the seller leads the caller may see, with their type, term, fee and status, and the sellers a mandate can be made for. The Private Sale Dossier of a mandate that is not signed shows nothing, not even a count) | Company Admin, Agent |
| `sellos.inventory.mandates.save_mandate`, `sign_mandate`, `add_dossier_note`, `add_dossier_file` (SOS-P4-05, records a mandate as a Draft with its type, term and fee for a seller lead the caller may write, signs it by uploading the signed document (a PDF, PNG or JPG of up to 5 MB, a private file; it is required), and adds notes and files to its Dossier, which stay hidden until the signature. A signed mandate keeps its terms) | Company Admin, Agent |
| `sellos.inventory.mandates.open_dossier` (SOS-P4-05, opens the Private Sale Dossier, which is the files and notes attached to a mandate. It is refused unless the mandate is signed and not archived, and each opening is logged with who and when. The Dossier files and the signed document are private files, opened only by who may read the mandate, and the Dossier files only while it is signed) | Company Admin, Agent |
| `sellos.inventory.mandates.set_mandate_archived` (SOS-P4-05, archives or restores a mandate. An archived mandate no longer counts as signed for the Listed stage and releases no Dossier; nothing is deleted) | Company Admin |
| `sellos.inventory.matching.matches_for_lead`, `leads_for_unit`, `leads_for_listing` (SOS-P7-08, read only: the published listings and Available units that suit a lead the caller may see, scored 0 to 100 on budget, configuration, locality and property type with a reason for each part; and the leads an Available unit or a published listing suits among the leads the caller may see, which is an agent's own, a Sales Manager's team's and a Company Admin's all. A unit that is not Available and a listing that is not published are never suggested. Phone numbers are masked for everyone but a Company Admin) | Company Admin, Agent, Sales Manager |
| `sellos.inventory.matching.get_match_settings`, `save_match_settings` (SOS-P7-08, the four weights of the match score, 25 each by default) | Company Admin |
| `sellos.inventory.shortlists.list_shortlists`, `get_shortlist`, `shortlist_pdf` (SOS-P7-09, read only: the shortlists of homes made for a client that the caller may see, which is an agent's own, a Sales Manager's team's and a Company Admin's all; one with its homes in order, prices, photos, notes, the homes no longer available and which ones the client opened and when; and its PDF with the company's branding, the photos and the prices. No phone number is returned but the agent's own in the PDF) | Company Admin, Agent, Sales Manager |
| `sellos.inventory.shortlists.create_shortlist`, `update_shortlist`, `add_to_shortlist`, `save_item_note`, `remove_shortlist_item`, `reorder_shortlist`, `archive_shortlist`, `share_shortlist` (SOS-P7-09, an Agent or a Company Admin makes a shortlist for a client they may see, puts Available units and published listings on it, orders them, adds a note to each, shares it with the client as a link to their own client view or as a PDF, and archives it. Nothing is deleted. A Sales Manager reads its team's shortlists and changes none) | Company Admin, Agent |
| `sellos.inventory.shortlists.my_shortlists`, `my_shortlist`, `open_shortlist_item`, `my_shortlist_pdf` (SOS-P7-09, a Client reads only the shortlists shared with the Client record whose email is the signed in user's, never a draft, an archived one or another client's, and opening a home marks it opened for the agent. The agent's name and phone are shown and no other phone number or client) | Client |
| `sellos.telephony.settings.get_telephony_settings`, `save_telephony_settings`, `check_connection` (SOS-P2-01, the Plivo India account: the auth ID and token are encrypted and never returned, only whether each is set) | Company Admin |
| `sellos.telephony.click_to_call.call_preview`, `click_to_call`, `call_status`, `pending_outcomes`, `record_outcome` (SOS-P2-07, click to call: rings the user's own Indian mobile first, then the lead, both legs in India. The lead's consent status and warning come back before and during the call and never block; no lead phone number is returned; a user sees and records only their own calls, and only for a lead they may write) | Company Admin, Agent, Sales Manager |
| `sellos.voice.agent.settings.get_voice_agent_settings`, `save_voice_agent_settings` (SOS-P5-07, the voice agent: the speech to text, language model and text to speech providers, the Voice agent model, the AI disclosure line and the real estate keyterms; the keys are encrypted and never returned, only whether each is set) | Company Admin |
| `sellos.telephony.hours.get_calling_hours`, `save_calling_hours` (SOS-P2-10, the company's calling hours: a switch, start, end and days in India time; a call outside them is refused with the hours in the message) | Company Admin |
| `sellos.whatsapp.settings.get_whatsapp_settings`, `save_whatsapp_settings`, `check_whatsapp_connection`, `save_whatsapp_template` (SOS-P6-11, the company's own WhatsApp number and its templates: the access token and the webhook signing secret are encrypted and never returned, only whether each is set; a template is switched off, never deleted) | Company Admin |
| `sellos.whatsapp.settings.list_whatsapp_templates` (SOS-P6-11, the enabled, provider approved templates a sender may send) | Company Admin, Sales Manager, Agent |
| `sellos.whatsapp.conversations.list_whatsapp_conversations`, `get_whatsapp_conversation`, `whatsapp_conversation_for_lead`, `send_whatsapp_message`, `hand_off_whatsapp_conversation`, `close_whatsapp_conversation` (SOS-P6-11, WhatsApp conversations of the leads the caller may see: an Agent's own, a Sales Manager's team's, a Company Admin's all. Every send goes through the consent function of SOS-P2-04 and is never refused while Consent enforcement is Off; no method returns a phone number) | Company Admin, Sales Manager, Agent |
| `sellos.telephony.dnd.import_do_not_call_list`, `do_not_call_summary` (SOS-P2-10, import a do not call list; a listed number gives its lead Registered DND with an amber warning, through `record_dnd_result`, and never blocks a call) | Company Admin |
| `sellos.crm.api.find_duplicates` (P1.16, the clients that already have a phone or email, masked as the viewer's role requires) | Company Admin, Agent, Sales Manager |
| `sellos.crm.api.merge_clients` (P1.16, moves a client's leads to the one kept, nothing deleted, logged) | Company Admin |
| `sellos.crm.api.complete_follow_up`, `list_follow_ups` (SOS-P1-22, mark a follow up done with a call outcome or a note, and list the signed in user's follow ups, or those of every lead they may see) | Company Admin, Agent, Sales Manager |
| `sellos.crm.api.get_follow_up_settings` (SOS-P1-22, the days after which a lead with no open follow up is untouched) | Company Admin, Agent, Sales Manager, Channel Partner |
| `sellos.crm.api.save_follow_up_settings` (SOS-P1-22, a Company Admin sets those days) | Company Admin |
| `sellos.crm.api.site_visit_calendar`, `tomorrows_site_visits`, `confirm_site_visit`, `complete_site_visit`, `site_visit_options` (SOS-P1-25, the calendar and the confirmation list, each showing the user's own visits, a Sales Manager's team's and a Company Admin's everyone's, confirming and finishing a visit) | Company Admin, Agent, Sales Manager |
| `sellos.crm.api.today_screen` (SOS-P1-26, the Today screen: follow ups due and overdue, new leads, today's and tomorrow's site visits, each showing the user's own records, a Sales Manager's team's by agent and a Company Admin's everyone's; phone numbers masked except for a Company Admin) | Company Admin, Agent, Sales Manager |
| `sellos.crm.api.caller_queue` (SOS-P2-09, the caller queue: every lead the user may see, Consented first by soonest expiry, each with its consent warning; phone numbers masked except for a Company Admin; consent never blocks) | Company Admin, Agent, Sales Manager |
| `sellos.crm.api.add_activity`, `save_task`, `save_site_visit` (a new visit moves its lead to Site visit booked, SOS-P1-25) | Company Admin, Agent, Sales Manager |
| `sellos.crm.api.record_consent`, `record_opt_out`, `record_dnd_result` (P1.08, the Consent Record; consent never blocks) | Company Admin, Agent, Sales Manager |
| `sellos.crm.api.get_consent_enforcement` (SOS-P2-04, reads the company setting Consent enforcement, Off by default) | Company Admin, Agent, Sales Manager, Channel Partner |
| `sellos.crm.api.set_consent_enforcement` (SOS-P2-04, changes the company setting Consent enforcement; every change is logged) | Company Admin |
| `sellos.access.support.list_support_users`, `grant_support_access`, `revoke_support_access`, `list_support_grants`, `support_access_log` (P1.13) | Company Admin |
| `sellos.config.setup_wizard.get_setup_state`, `save_profile`, `save_branding`, `save_stages`, `add_user`, `finish_setup` (P1.03, the setup wizard) | Company Admin |
| `sellos.access.field_history.getdoc`, `get_docinfo` (P1.06B: the record loader, with the history of fields the reader may not read left out) | Every role |
| `sellos.access.teams.list_teams` (SOS-P1-18, every team for a Company Admin with the managers and agents to pick from, only the teams they manage for a Sales Manager) | Company Admin, Sales Manager |
| `sellos.access.teams.save_team`, `delete_team` (SOS-P1-18, make a team, set its manager and agents, remove it. An agent is in one team only) | Company Admin |
| `sellos.crm.api.reassign_lead` (SOS-P1-18, give a lead to another agent. A Sales Manager only within its own team) | Company Admin, Sales Manager |
| `sellos.crm.api.bulk_reassign_leads`, `reassign_options` (SOS-P1-19, give the listed leads, or the leads a filter finds, to one agent, with their open follow ups and future site visits, logged. A Sales Manager only the leads and agents of its own team. All or none) | Company Admin, Sales Manager |
| `sellos.crm.api.preview_lead_import`, `import_bought_list` (SOS-P1-12, a CSV of a bought lead list: the preview writes nothing, the import makes leads with the source Bought list and the consent status Unknown or Registered DND, merges duplicates, and sets nothing that stops contact) | Company Admin |
| `sellos.crm.api.list_assignment_rules`, `save_assignment_rule`, `delete_assignment_rule`, `set_default_team` (SOS-P1-19, the rules that assign new leads by round robin, source or locality, and the default team) | Company Admin |
| `sellos.reports.team.team_report` (SOS-P1-18, the leads the reader may see by agent and by stage) | Company Admin, Sales Manager |
| `sellos.crm.enquiry.get_enquiry_settings`, `rotate_enquiry_key` (SOS-P2-08, the enquiry page link with its form key and the consent wording it shows; rotating the key stops every link shared before) | Company Admin |
| `sellos.crm.website_form.get_website_settings`, `rotate_website_key` (SOS-P1-09, the website form's endpoint address and the Lead intake keys made so far, never a key; rotating makes a new key, shown once, and stops the old ones) | Company Admin |
| `sellos.inventory.listings_feed.get_listings_feed_settings`, `rotate_listings_key`, `save_listings_webhook` (SOS-P4-08, the listings feed address, the Listings read keys made so far, never a key, and the change webhook address; rotating makes a new key, shown once, and stops the old ones; saving an https address makes the webhook secret, shown once) | Company Admin |
| `sellos.reports.calls.call_report`, `call_report_calls` (SOS-P2-11, the call reports for a range of dates: cost by agent and by purpose, connect rate, talk time and consent coverage, and the calls behind each figure) | Company Admin |
| `sellos.reports.ai_comparison.ai_comparison`, `ai_comparison_calls` (SOS-P5-09, AI calling against human calling and the four week human baseline for a range of dates: connect rate, qualified lead rate, site visits booked, cost per qualified lead, handover rate and complaints, and the calls behind each figure) | Company Admin |
| `sellos.reports.engine.list_reports`, `run_report`, `report_records` (SOS-P5-01, the report engine: the reports made visible to the reader's role, a report's figures for a range of dates and the records behind a figure; a Company Admin reads all records, a Sales Manager its own team's and an Agent its own, and no figure or record holds a phone number) | Company Admin, Sales Manager, Agent |
| `sellos.reports.engine.refresh_report`, `save_report_definition` (SOS-P5-01, rebuild a report's summary table now, and make or change a report definition) | Company Admin |
| `sellos.reports.partner.partner_report` (SOS-P5-03, a channel partner's own leads by stage for a range of dates, with their deal and commission panels that switch on when SOS-P4-06 and SOS-P7-04 are done; only a pure partner login, and only their own records) | Channel Partner |
| `sellos.reports.platform.list_platform_reports`, `run_platform_report` (SOS-P5-03, companies, usage and calling spend as totals per company, with revenue, churn and failed payment panels that switch on when billing is live; totals only, no lead, client or call record and no phone number) | Platform Admin |

Each story that adds a method adds a row here.

## API method matrix

`sellos/access/matrix.py` lists the roles for every method. The build fails when the list and the `@sellos_api` declarations disagree, or when a sellos method is whitelisted without a declaration (P1.05).

## Provider webhooks

Decided by Jayman on 20 November 2026 (SOS-P2-06). A provider webhook is one of two kinds of method that may be called without a
login (the other is public intake, below): the provider (Plivo, a WhatsApp or email provider, a payment provider) has no SellOS user. It is not an `@sellos_api`
method. It is registered in `sellos.access.webhooks` as a webhook and allows guests, and nothing else in the `sellos` package may allow
guests except a public intake method (see "Public intake forms"). `sellos/access/test_webhook_guest_guard.py` fails the build if a guest method is not registered with these checks.

Each webhook, whatever the provider, has all of these:

| Check | Rule |
| --- | --- |
| Signature | Verified before any database work. An invalid or missing signature writes nothing and reveals nothing (one short answer for every refusal) |
| Replay and order | A replayed event changes nothing; an out of order event is ignored |
| Body size | Capped; a larger body is refused before it is read in full |
| Rate limit | Per tenant |
| Tenant | The site the request arrives on. Never the body, a header or the query |
| Secret | Per tenant in company settings, never in a log, an error or a test |

Registered webhooks (one heading each as they are built):

| Webhook | Provider | Task | Secret field | Writes |
| --- | --- | --- | --- | --- |
| `sellos.telephony.webhook.plivo_call_event` (Plivo call events) | Plivo | SOS-P2-06 | Telephony Settings, auth token (Plivo signs with it) | Call Log (state, duration, hangup cause, recording link), Webhook Event (replay keys), a private recording file |
| `sellos.whatsapp.webhook.whatsapp_event` (WhatsApp customer messages and message statuses) | WhatsApp (Meta Cloud API) | SOS-P6-11 | WhatsApp Settings, webhook signing secret (`X-Hub-Signature-256`) | Lead, Client, Lead Activity, Consent Record and its private evidence file (through `sellos.crm.intake.take`), WhatsApp Conversation, WhatsApp Message, Webhook Event (replay keys) |

Plivo call events (SOS-P2-06) is the first: body cap 64 KB, 600 requests a minute per tenant, replay key the signing nonce. A refused signature is always answered `refused` (HTTP 403), a body over the cap 413 and a rate limited request 429, and none writes anything. WhatsApp events (SOS-P6-11): body cap 256 KB, 600 requests a minute per tenant, replay key a hash of the signed body, and a customer message is also remembered by the provider's message id; a message status for an earlier step than the message has reached is ignored. Email (P5) and payment (P6) webhooks are added the same way, each under its own row
here, and each task adds its row.

## Public intake forms

Decided by Jayman on 21 November 2026 (SOS-LOOP). The second kind of method that may be called without a login: the submit method of a public form (the enquiry page, SOS-P2-08; the website form, SOS-P1-09). It only creates or merges a lead through `sellos.crm.intake`. It is registered in `sellos.access.public_intake`, built once in SOS-P2-08, and allows guests. `sellos/access/test_webhook_guest_guard.py` fails the build if a guest method is not a registered provider webhook, a registered public intake method with these checks, or a registered public listings feed.

| Check | Rule |
| --- | --- |
| Write only | Answers a thank you and a reference code; nothing about whether the person existed |
| Rate limit | Per address and per tenant, in the cache |
| Honeypot | A filled honeypot gets the same thank you and writes nothing |
| Body size | Capped; a larger body is refused before it is read in full |
| Validation | Strict: known fields only, types and lengths checked |
| Form key | Per tenant; a Company Admin can rotate it |
| Consent evidence | The wording shown, its version, the time and the address, saved as a private file and linked as evidence |
| Tenant | The site the request arrives on. Never the body, a header or the query |
| Cookies and reads | No cookies; nothing readable back |

Registered public intake methods (one row each as they are built):

| Method | Task | Writes |
| --- | --- | --- |
| `sellos.crm.enquiry.submit_enquiry` (the enquiry page's form: name, phone, optional email and message, a "Stop contacting me" box; body cap 8 KB, 10 requests a minute per address and 120 per tenant, honeypot field `website`, form key in the link, rotated by a Company Admin) | SOS-P2-08 | A client and a lead on the New stage (or the lead the number already belongs to, with no stage change) through `sellos.crm.intake.take`, an inquiry Consent Record (7 days) with a private evidence file (wording, its version, time, address, submission), a Lead Activity. A stop request records Opted out instead and no inquiry |
| `sellos.crm.website_form.submit_website_lead` (the website's form: name, phone, optional email, message, form name and the consent wording shown; body cap 16 KB, 60 requests a minute per address and 300 per tenant, honeypot field `company_url`, the company's "Lead intake" key in the `key` field, made and rotated by a Company Admin, only its hash kept and shown once) | SOS-P1-09 | A client and a lead (or the lead the number belongs to) through `sellos.crm.intake.take`. With wording: an inquiry Consent Record (7 days) with a private evidence file and the lead Consented. Without wording: accepted, the lead stays Unknown, a Lead Activity records the warning and no Consent Record is made |

A missed call to the 022 number (SOS-P2-08) is not a public method: it arrives as a Plivo event through the provider webhook (`plivo_call_event`, signature first) and goes to the same `sellos.crm.intake.take`.

## Public listings feed

Decided by Jayman on 22 November 2026 (SOS-LOOP). The third kind of method that may be called without a login: the read method the company's website uses to show published listings (SOS-P4-08), using only the Listings read key from the per company key record of SOS-P1-09. It is registered in `sellos.access.public_listings`, built once in SOS-P4-08, and allows guests. `sellos/access/test_webhook_guest_guard.py` fails the build if a guest method is not a registered provider webhook, a registered public intake method or a registered public listings feed with these checks.

| Check | Rule |
| --- | --- |
| Access | Read only; published listings only |
| Fields | An explicit allowlist. No owner or seller data, no phone numbers, no mandate or dossier files, no internal notes, no unpublished media |
| Key | The Listings read key, in a header, never in the URL. A Lead intake key is refused here and a Listings read key never creates leads |
| Refusal | A bad key gets one short answer that reveals nothing |
| Rate limit | Per key and per tenant, in the cache |
| Page size | Capped |
| Caching | ETag; an unchanged request gets a not modified answer |
| Tenant | The site the request arrives on. Never the body, a header or the query |
| Cookies | None |

Outbound change webhook (not a guest method, SellOS calls the website): signed with a per tenant secret that never appears in a log, retried, HTTPS only, refuses private addresses, carries no personal data (ids and change kind only).

Registered public listings feeds (one row each as they are built):

| Method | Task | Reads |
| --- | --- | --- |
| `sellos.inventory.listings_feed.published_listings` (GET; the Listings read key in the `X-Listings-Key` header; `start` and `page_size` in the query, page size capped at 50; 120 requests a minute per key and 600 per tenant; ETag and `If-None-Match`) | SOS-P4-08 | Published, unarchived listings: id, title, type, asking price, description, published and modified times, project, property type, city, locality, configuration, carpet area, floor, parking and the photos and videos (title, type, url) |

The change webhook (`sellos.inventory.listing_webhook`) is set by a Company Admin (`save_listings_webhook`), is called when a listing is published, changed while published or unpublished, and carries `{"event", "kind", "listing"}` only. It is signed `X-SellOS-Signature: sha256=<HMAC-SHA256 of "<timestamp>.<body>">` with `X-SellOS-Timestamp`, tried up to 3 times, https only and never to a private address.

## The permission test suite (P1.05)

`sellos/access/test_p1_05_permission_suite.py` calls every method in the matrix as each of the six roles,
as a user from another company (on a company's own site, a signed-in user with no role) and as a guest,
against one company's seeded records. It fails the build when a refused caller is not refused, when any
caller other than the Company Admin gets the company's record or a full phone number, when a method has no
matrix entry or no sample arguments, or when a sellos method is whitelisted with no declaration. It runs
in continuous integration with the rest of the backend tests (`bench run-tests --app sellos`).

## Support access grants (P1.13)

The Platform Admin sees no company data by role. A Company Admin gives one support user read access for a
chosen time, from 1 minute to 4 hours (`/sellos/company/support` in the web app, `sellos/access/support.py`).

* While the grant is active the user may read the five CRM DocTypes and nothing else: no write, create,
  share, delete or per record export. `lead_permissions` decides this from the grant, on every call.
  The user keeps the level 1 phone rows the Platform Admin role has, so a support user sees full phone numbers
  while a grant is active. Every request is logged.
* The end is checked on every use: a grant lasts to its expiry, and never more than 4 hours after it started,
  whether or not the scheduler has run. The scheduler (`expire_due_grants`, every tick) marks it Expired.
* Every request the user makes, and each grant, revoke and expiry, is a line in the Support Access Log with the
  user, the time, the method and the path. Grants and log lines are never edited or deleted. A grant's holder and
  length can not change: revoke it and make a new one.
* The Company Admin may read grants and the log (`Support Grant`, `Support Access Log`) and change them only
  through the methods above.

## The control site (P1.01)

The control site is the Platform Admin's own site. It holds three DocTypes, made from code like every other:
Tenant (one company, with its site and database names), Plan (a stub: name, switch, user limit; the tiers
come with P6.02) and Provisioning Job (one request to make a site). Their statuses are Requested,
Provisioning, Active and Failed, and `sellos/provisioning/status.py` is the one list of the order they may
change in: Requested to Provisioning, Provisioning to Active or Failed, Failed back to Provisioning. Active
is final. The DocType controllers enforce it on every save, whoever saves.

* Only the Platform Admin (and System Manager, read only) holds permission on the three DocTypes. No company
  role has any, so a company user's read, create, write, delete and export are all refused.
* Nothing is deleted: `on_trash` refuses it for every role.
* The web app page is `/sellos/control/tenants` (area `platform`, the Platform Admin only). It uses the
  framework's document methods, which check the DocType permission, so it adds no `sellos` API method.
* A site with `sellos_control_site` set to 1 in its `site_config.json` is a control site. There the
  `guard_control_site` request hook (`sellos/provisioning/control.py`) refuses every signed in user who is
  not a Platform Admin, apart from sign out. Company sites never have the setting.
* Company Usage (SOS-P5-03) is a fourth DocType there: one row per company and month with four counts and
  the calling spend in rupees, read by the Platform Admin's reports (`/sellos/control/reports`). It holds no
  lead, client or call record and no phone number, `record_usage` refuses any other key, and it is never
  deleted. Only the Platform Admin (and System Manager, read only) holds permission on it.
