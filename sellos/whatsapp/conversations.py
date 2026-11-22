"""WhatsApp conversations (SOS-P6-11): inbound, outbound, opt in, stop request and handoff.

* Inbound. A message from a customer goes to `sellos.crm.intake.take`, the one lead intake function, so a
  number is matched, a lead is made or merged and consent is recorded the same way as everywhere. A plain
  message makes or updates the lead and logs an activity. An explicit opt in ("START") also makes a Consent
  Record (basis Consent) whose evidence is the message saved as a private file. A stop request ("STOP") is
  recorded as Opted out with a red warning, with the message as its private file. Nothing here moves a
  lead along the pipeline.
* Outbound. Every send goes through the one consent function, `sellos.crm.consent.check_contact`, before the
  provider is called. The message links to its Consent Check and holds no consent fields of its own. With
  Consent enforcement Off (the default) no send is refused, whatever the status, an Opted out lead
  included (Jayman, 10 November 2026). WhatsApp's own rule is separate from consent: free text goes only
  within 24 hours of the customer's last message, and a template goes at any time.
* Handoff. A conversation can be handed to a human, who is told and sees it with the lead.

The number is the client's and is read only when a message is sent. No record here copies it.
"""

import re

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now_datetime

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.crm import consent, intake, lead_sources, notifications
from sellos.telephony import call_log
from sellos.whatsapp import settings
from sellos.whatsapp.base import STATUS_RANK, InboundMessage, ProviderError, StatusEvent

CONVERSATION = "WhatsApp Conversation"
MESSAGE = "WhatsApp Message"
SOURCE = "WhatsApp"
SESSION_HOURS = 24
STATES = ("Open", "With a human", "Closed")
STOP, OPT_IN = "Stop", "Opt in"
# A whole message, in lower case with punctuation removed, that means one of these.
STOP_PHRASES = frozenset(
	{"stop", "stop all", "stopall", "unsubscribe", "opt out", "optout", "please stop", "stop messaging me"}
)
OPT_IN_PHRASES = frozenset({"start", "subscribe", "opt in", "optin", "i agree", "i consent"})
HANDOFF_EVENT = notifications.WHATSAPP_HANDOFF
MAX_TEXT = 4096


def classify(text: str) -> str:
	"""'Stop', 'Opt in' or '' for the text of a customer's message. Only a whole message that says so
	counts, so "do not stop the visit" is a plain message."""
	words = " ".join(re.sub(r"[^\w\s]", " ", (text or "").lower()).split())
	if words in STOP_PHRASES:
		return STOP
	if words in OPT_IN_PHRASES:
		return OPT_IN
	return ""


def _source() -> str:
	"""The WhatsApp lead source, made the first time it is needed. A company that switched it off gets
	Website instead, as a disabled source is not offered to new leads."""
	if not frappe.db.exists("Lead Source", SOURCE):
		frappe.get_doc({"doctype": "Lead Source", "source_name": SOURCE, "enabled": 1}).insert(
			ignore_permissions=True
		)
	if frappe.db.get_value("Lead Source", SOURCE, "enabled"):
		return SOURCE
	lead_sources.ensure_default_sources()
	return lead_sources.WEBSITE


def conversation_for(lead) -> str:
	"""The lead's conversation, made on the first message in either direction."""
	name = frappe.db.get_value(CONVERSATION, {"lead": lead})
	if name:
		return name
	return (
		frappe.get_doc({"doctype": CONVERSATION, "lead": lead, "state": "Open"})
		.insert(ignore_permissions=True)
		.name
	)


def _touch(conversation, direction):
	"""Move the conversation's clock on, and reopen a closed one when the customer writes."""
	values = {"last_message_on": now_datetime(), "last_direction": direction}
	if direction == "Inbound":
		values["last_inbound_on"] = values["last_message_on"]
		if frappe.db.get_value(CONVERSATION, conversation, "state") == "Closed":
			values["state"] = "Open"
	frappe.db.set_value(CONVERSATION, conversation, values)


# -- inbound ------------------------------------------------------------------------------------------


def receive(message: InboundMessage) -> dict | None:
	"""Take one customer message. Returns {"lead", "conversation", "message", "intent"}, or None for a
	message already taken (the provider id is remembered, so a replay changes nothing)."""
	if frappe.db.exists(MESSAGE, {"provider_message_id": message.message_id}):
		return None
	text = (message.text or "").strip()[:MAX_TEXT]
	intent = classify(text)
	reference = frappe.scrub(message.message_id)[:40] or frappe.generate_hash(length=8)
	common = {
		"phone": message.from_number,
		"source": _source(),
		"kind": "whatsapp",
		"reference": reference,
		"evidence": {
			"channel": "WhatsApp",
			"message_id": message.message_id,
			"text": text,
			"intent": intent or "message",
			"received_on": str(now_datetime()),
			"profile_name": message.name,
		},
		"name": message.name or None,
		"activity_type": "WhatsApp",
	}
	if intent == STOP:
		result = intake.take(**common, stop_source="WhatsApp")
	elif intent == OPT_IN:
		result = intake.take(
			**common,
			basis="Consent",
			notes=_("Opted in to WhatsApp messages."),
		)
	else:
		result = intake.take(
			**common,
			has_consent=False,
			notes=_("WhatsApp message received: {0}").format(text[:200]),
		)
	lead = result["lead"]
	conversation = conversation_for(lead)
	row = frappe.get_doc(
		{
			"doctype": MESSAGE,
			"conversation": conversation,
			"lead": lead,
			"direction": "Inbound",
			"kind": "Text",
			"body": text,
			"intent": intent,
			"provider_message_id": message.message_id,
			"status": "received",
			"sent_on": now_datetime(),
			"evidence_link": result["evidence_link"] if intent else None,
			"consent_record": result["consent_record"],
		}
	).insert(ignore_permissions=True)
	_touch(conversation, "Inbound")
	return {"lead": lead, "conversation": conversation, "message": row.name, "intent": intent}


def apply_status(event: StatusEvent) -> str | None:
	"""Move a message the company sent along (sent, delivered, read, failed). Returns its name when it
	changed. A status for an earlier step than the message has reached, or for a message we do not know,
	is ignored: a late "sent" never undoes "read"."""
	row = frappe.db.get_value(
		MESSAGE, {"provider_message_id": event.message_id}, ["name", "status"], as_dict=True
	)
	if not row or event.status not in STATUS_RANK:
		return None
	if STATUS_RANK[event.status] <= STATUS_RANK.get(row.status, -1):
		return None
	values = {"status": event.status}
	if event.status == "failed":
		values["error"] = event.error or _("WhatsApp could not deliver this message.")
	frappe.db.set_value(MESSAGE, row.name, values)
	return row.name


# -- outbound -----------------------------------------------------------------------------------------


def _lead_doc(lead):
	if not frappe.db.exists("Lead", lead):
		frappe.throw(_("Lead {0} was not found.").format(lead), frappe.DoesNotExistError)
	doc = frappe.get_doc("Lead", lead)
	doc.check_permission("write")
	return doc


def window_open(conversation, on=None) -> bool:
	"""True when the customer wrote within the last 24 hours, so free text may be sent."""
	last = frappe.db.get_value(CONVERSATION, conversation, "last_inbound_on")
	if not last:
		return False
	return get_datetime(last) >= add_to_date(get_datetime(on or now_datetime()), hours=-SESSION_HOURS)


def _render(body, parameters) -> str:
	for index, value in enumerate(parameters or [], start=1):
		body = body.replace("{{%d}}" % index, str(value))
	return body


def _consent_view(check) -> dict:
	return {
		"consent_status": check.status,
		"consent_warning": check.warning_level or "none",
		"consent_message": check.warning,
	}


def send(lead, text=None, template=None, parameters=None) -> dict:
	"""Send one WhatsApp message to the lead, checking consent first.

	Returns {"sent", "refused", "reason", "error", "message", "consent_status", "consent_warning",
	"consent_message"}. With Consent enforcement Off nothing is refused for consent. A message that
	WhatsApp's own rules or a provider failure stop is reported with a clear message: a provider failure
	is kept on the thread as a failed message."""
	_lead_doc(lead)
	text = (text or "").strip()
	if bool(text) == bool(template):
		frappe.throw(_("Send either a message or a template."), frappe.ValidationError)
	if len(text) > MAX_TEXT:
		frappe.throw(_("The message is too long."), frappe.ValidationError)
	tpl = None
	if template:
		tpl = frappe.db.get_value(
			settings.TEMPLATE, template, ["name", "language", "body", "status", "enabled"], as_dict=True
		)
		if not tpl or not tpl.enabled or tpl.status != "Approved":
			frappe.throw(_("That template is not available. Choose an approved one."), frappe.ValidationError)
	conversation = conversation_for(lead)
	if text and not window_open(conversation):
		frappe.throw(
			_(
				"The 24 hour window is closed: this customer has not written in the last 24 hours. Send a template."
			),
			frappe.ValidationError,
		)
	try:
		number = call_log._lead_number(lead)
		provider = settings.connected_provider()
	except ProviderError as error:
		frappe.throw(str(error), frappe.ValidationError)
	check = consent.check_contact(lead, "WhatsApp")
	view = _consent_view(check)
	if check.refused:
		return {"sent": False, "refused": True, "reason": check.reason, "error": "", "message": None, **view}
	body = _render(tpl.body, parameters) if tpl else text
	values = {
		"doctype": MESSAGE,
		"conversation": conversation,
		"lead": lead,
		"direction": "Outbound",
		"kind": "Template" if tpl else "Text",
		"body": body,
		"template": tpl.name if tpl else None,
		"sent_by": frappe.session.user,
		"sent_on": now_datetime(),
		"consent_check": check.check,
	}
	try:
		sent = (
			provider.send_template(number, tpl.name, tpl.language, [str(p) for p in parameters or []])
			if tpl
			else provider.send_text(number, text)
		)
	except ProviderError as error:
		failed = frappe.get_doc({**values, "status": "failed", "error": str(error)[:500]}).insert(
			ignore_permissions=True
		)
		consent.link_check(check.check, MESSAGE, failed.name)
		_touch(conversation, "Outbound")
		return {
			"sent": False,
			"refused": False,
			"reason": "",
			"error": str(error),
			"message": failed.name,
			**view,
		}
	row = frappe.get_doc({**values, "status": sent.status, "provider_message_id": sent.message_id}).insert(
		ignore_permissions=True
	)
	consent.link_check(check.check, MESSAGE, row.name)
	_touch(conversation, "Outbound")
	return {"sent": True, "refused": False, "reason": "", "error": "", "message": row.name, **view}


# -- handoff ------------------------------------------------------------------------------------------

HUMAN_ROLES = (AGENT, SALES_MANAGER, COMPANY_ADMIN)


def hand_off(conversation, to_user=None, note=None) -> dict:
	"""Hand the conversation to a human. The human is the one named, else the lead's agent, else the user
	who clicked. They are told, and the handoff is logged on the lead."""
	lead = frappe.db.get_value(CONVERSATION, conversation, "lead")
	if not lead:
		frappe.throw(_("Conversation {0} was not found.").format(conversation), frappe.DoesNotExistError)
	_lead_doc(lead)
	to_user = to_user or frappe.db.get_value("Lead", lead, "assigned_to") or frappe.session.user
	if not frappe.db.get_value("User", to_user, "enabled") or not set(frappe.get_roles(to_user)) & set(
		HUMAN_ROLES
	):
		frappe.throw(
			_("Choose an agent, sales manager or company admin to hand this to."), frappe.ValidationError
		)
	note = (note or "").strip()[:500]
	frappe.db.set_value(
		CONVERSATION,
		conversation,
		{"state": "With a human", "handed_to": to_user, "handed_on": now_datetime(), "handoff_note": note},
	)
	intake._log_activity(
		lead,
		"WhatsApp",
		_("WhatsApp conversation handed to {0}.").format(
			frappe.get_cached_value("User", to_user, "full_name")
		)
		+ (f" {note}" if note else ""),
	)
	if to_user != frappe.session.user:
		notifications.notify(
			to_user,
			HANDOFF_EVENT,
			_("A WhatsApp conversation was handed to you"),
			note or None,
			lead=lead,
			dedupe_key=f"wa-handoff:{conversation}:{now_datetime().isoformat()}",
		)
	return {"conversation": conversation, "state": "With a human", "handed_to": to_user}


def close(conversation) -> dict:
	"""Close a conversation. A new message from the customer reopens it."""
	lead = frappe.db.get_value(CONVERSATION, conversation, "lead")
	if not lead:
		frappe.throw(_("Conversation {0} was not found.").format(conversation), frappe.DoesNotExistError)
	_lead_doc(lead)
	frappe.db.set_value(CONVERSATION, conversation, "state", "Closed")
	return {"conversation": conversation, "state": "Closed"}


# -- reads for the screen -----------------------------------------------------------------------------


def _title(lead) -> str:
	client = frappe.db.get_value("Lead", lead, "client")
	return (client and frappe.db.get_value("Client", client, "client_name")) or lead


def list_for_screen(state=None, limit=50) -> list[dict]:
	"""The conversations the user may see (a Frappe permission query on the lead), newest first. No number."""
	filters = {"state": state} if state in STATES else {}
	rows = frappe.get_list(
		CONVERSATION,
		filters=filters,
		fields=["name", "lead", "state", "handed_to", "last_message_on", "last_direction", "last_inbound_on"],
		order_by="last_message_on desc, creation desc",
		limit_page_length=min(cint(limit) or 50, 100),
	)
	for row in rows:
		row["title"] = _title(row.lead)
		row["window_open"] = window_open(row.name)
		row["consent_status"] = consent.compute_status(row.lead)
		level = consent.WARNINGS[row["consent_status"]][0]
		row["consent_warning"] = level or "none"
	return rows


def thread_for_screen(conversation) -> dict:
	"""One conversation with its messages, oldest first, and the lead's consent status and warning."""
	row = frappe.get_doc(CONVERSATION, conversation)
	row.check_permission("read")
	messages = frappe.get_list(
		MESSAGE,
		filters={"conversation": conversation},
		fields=[
			"name",
			"direction",
			"kind",
			"body",
			"intent",
			"status",
			"error",
			"sent_on",
			"sent_by",
			"consent_check",
		],
		order_by="sent_on asc, creation asc",
		limit_page_length=500,
	)
	checks = {
		c.name: c
		for c in frappe.get_all(
			"Consent Check",
			filters={"name": ["in", [m.consent_check for m in messages if m.consent_check] or [""]]},
			fields=["name", "consent_status", "warning_level", "warning"],
		)
	}
	for message in messages:
		check = checks.get(message.consent_check)
		message["consent_status"] = check.consent_status if check else ""
		message["consent_warning"] = (check.warning_level or "none") if check else ""
		message["consent_message"] = check.warning if check else ""
		message.pop("consent_check", None)
	status = consent.compute_status(row.lead)
	level, text = consent.WARNINGS[status]
	return {
		"conversation": row.name,
		"lead": row.lead,
		"title": _title(row.lead),
		"state": row.state,
		"handed_to": row.handed_to,
		"handoff_note": row.handoff_note,
		"window_open": window_open(row.name),
		"consent_status": status,
		"consent_warning": level or "none",
		"consent_message": text,
		"messages": messages,
	}


# -- the API ------------------------------------------------------------------------------------------

_USERS = (AGENT, SALES_MANAGER, COMPANY_ADMIN)


@sellos_api(*_USERS)
def list_whatsapp_conversations(state=None):
	"""The conversations the user may see."""
	return list_for_screen(state)


@sellos_api(*_USERS)
def get_whatsapp_conversation(conversation):
	"""One conversation's thread with each message's consent status and warning."""
	return thread_for_screen(conversation)


@sellos_api(*_USERS)
def send_whatsapp_message(lead, text=None, template=None, parameters=None):
	"""Send a message to the lead, through the consent function. See `send`."""
	if isinstance(parameters, str):
		parameters = frappe.parse_json(parameters)
	return send(lead, text, template, parameters if isinstance(parameters, list) else None)


@sellos_api(*_USERS)
def hand_off_whatsapp_conversation(conversation, to_user=None, note=None):
	"""Hand a conversation to a human. See `hand_off`."""
	return hand_off(conversation, to_user or None, note)


@sellos_api(*_USERS)
def close_whatsapp_conversation(conversation):
	"""Close a conversation."""
	return close(conversation)


@sellos_api(*_USERS)
def whatsapp_conversation_for_lead(lead):
	"""The conversation of a lead the user may see, or None when there is none yet."""
	_lead_doc(lead)
	name = frappe.db.get_value(CONVERSATION, {"lead": lead})
	return thread_for_screen(name) if name else None
