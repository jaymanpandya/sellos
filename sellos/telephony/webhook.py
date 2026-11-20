"""Plivo's call events (SOS-P2-06): a registered provider webhook (sellos.access.webhooks).

Plivo calls this with no SellOS user. The shared checks (body cap, rate limit per tenant, signature
before any write, replay) are in `sellos.access.webhooks`. This module supplies Plivo's signature check
(SOS-P2-02's V3 signature, signed with the tenant's auth token from Telephony Settings), the rule for
an out of order event, and the Call Log update (SOS-P2-05). The tenant is the site the request arrives
on. After a call ends with a recording the recording is fetched in a background job.
"""

import dataclasses
import hmac

import frappe
from frappe import _
from frappe.utils.file_manager import save_file

from sellos.access.webhooks import WebhookRequest, provider_webhook
from sellos.telephony import call_log, click_to_call, settings
from sellos.telephony.base import CallEvent, ProviderError
from sellos.telephony.plivo import PlivoProvider, signature_v3
from sellos.telephony.provider import get_provider

PROVIDER = "plivo"
SECRET_SETTING = "Telephony Settings.auth_token"
MAX_BODY_BYTES = 64 * 1024
REQUESTS_PER_MINUTE = 600
# How far a call has got. An event for an earlier step than the log has reached is out of order.
STATE_RANK = {
	"queued": 0,
	"ringing": 1,
	"in-progress": 2,
	"completed": 3,
	"busy": 3,
	"no-answer": 3,
	"failed": 3,
	"cancelled": 3,
}
FINAL_RANK = 3
EXTENSIONS = {"audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/wav": "wav", "audio/x-wav": "wav"}


def verify_plivo_signature(request: WebhookRequest, secret: str) -> str | None:
	"""Plivo's V3 signature against the tenant's auth token. Returns the nonce (the replay key) when the
	signature is valid, and None otherwise."""
	signature = request.headers.get("x-plivo-signature-v3", "").strip()
	nonce = request.headers.get("x-plivo-signature-v3-nonce", "").strip()
	if not signature or not nonce:
		return None
	expected = signature_v3(secret, request.url, request.params, nonce)
	return nonce if hmac.compare_digest(expected, signature) else None


def plan(current_state: str, event: CallEvent) -> str | None:
	"""What to do with an event for a call whose log is in `current_state`.

	"all": apply it. "recording": the call is over, so keep its state and take only the duration and
	the recording. None: ignore it (an earlier step than the call has reached, or a second end)."""
	current = STATE_RANK.get(current_state or "queued", 0)
	incoming = STATE_RANK.get(event.state, 0)
	if current >= FINAL_RANK:
		if event.recording_url or (event.state == current_state and event.duration):
			return "recording"
		return None
	return "all" if incoming >= current else None


@provider_webhook(
	provider=PROVIDER,
	signature=verify_plivo_signature,
	replay=(
		"The nonce Plivo signs with is remembered per tenant in Webhook Event and a second event with it "
		"changes nothing. An event for an earlier step than the call has reached, and a second ending, are "
		"ignored."
	),
	max_body_bytes=MAX_BODY_BYTES,
	rate_limit_per_tenant=REQUESTS_PER_MINUTE,
	secret_setting=SECRET_SETTING,
)
def plivo_call_event(request: WebhookRequest):
	"""Plivo's call status and recording events: update the Call Log of the call."""
	try:
		events = PlivoProvider("", settings._keys()[1]).read_webhook(
			request.params, request.url, request.headers
		)
	except ProviderError:
		return "ignored"
	for event in events:
		apply_plivo_event(event)
	return "ok"


def apply_plivo_event(event: CallEvent) -> str | None:
	"""Update the Call Log for one event, in order. Returns the log name when something was written.

	An event may belong to the agent's leg (the log's own call ID) or, for click to call (SOS-P2-07), to the
	lead's leg. When the agent answers a click to call, the lead is rung."""
	name = frappe.db.get_value(call_log.DOCTYPE, {"call_id": event.call_id}, ["name", "state"], as_dict=True)
	if not name:
		return _apply_lead_leg_event(event)
	what = plan(name.state, event)
	if not what:
		return None
	cause = None
	if what == "recording":
		event.state = name.state
	elif STATE_RANK.get(event.state, 0) >= FINAL_RANK:
		cause = event.raw.get("HangupCauseName") or event.raw.get("HangupCause")
	call_log.apply_event(event, hangup_cause=cause)
	if event.recording_url:
		_enqueue_recording(name.name)
	if event.state == "in-progress" and what == "all":
		click_to_call.connect_lead(name.name)
	return name.name


def _enqueue_recording(log):
	frappe.enqueue(
		"sellos.telephony.webhook.fetch_recording",
		queue="short",
		enqueue_after_commit=True,
		log=log,
	)


def _apply_lead_leg_event(event: CallEvent) -> str | None:
	"""An event of the lead's leg of a click to call: track it in `lead_state`. The end of the lead's leg
	ends the call, with its duration, and its recording goes on the log."""
	row = click_to_call.lead_leg(event.call_id)
	if not row:
		return None
	what = plan(row.lead_state, event)
	if not what:
		return None
	if what == "all":
		frappe.db.set_value(call_log.DOCTYPE, row.name, "lead_state", event.state)
	as_log = dataclasses.replace(event, call_id=row.call_id)
	if STATE_RANK.get(event.state, 0) >= FINAL_RANK or event.recording_url:
		log_plan = plan(row.state, as_log)
		if log_plan == "recording":
			as_log.state = row.state
		if log_plan:
			cause = event.raw.get("HangupCauseName") or event.raw.get("HangupCause")
			call_log.apply_event(as_log, hangup_cause=cause if log_plan == "all" else None)
	if event.recording_url:
		_enqueue_recording(row.name)
	return row.name


def fetch_recording(log: str) -> str | None:
	"""Fetch the recording of a finished call and keep it as a private file on the Call Log.

	A failure is logged with the provider's message, which never holds a key, and does not raise: the
	recording link on the log stays, so the file can be fetched again."""
	row = frappe.db.get_value(call_log.DOCTYPE, log, ["recording_link", "state"], as_dict=True)
	if not row or not row.recording_link:
		return None
	existing = frappe.db.get_value(
		"File", {"attached_to_doctype": call_log.DOCTYPE, "attached_to_name": log}, "name"
	)
	if existing:
		return existing
	auth_id, auth_token = settings._keys()
	try:
		recording = get_provider(auth_id, auth_token).fetch_recording(row.recording_link)
	except ProviderError as error:
		frappe.log_error(title=_("Call recording not fetched"), message=str(error))
		return None
	extension = EXTENSIONS.get(recording.content_type.split(";")[0].strip().lower(), "mp3")
	file = save_file(f"{log}.{extension}", recording.content, call_log.DOCTYPE, log, is_private=1)
	return file.name
