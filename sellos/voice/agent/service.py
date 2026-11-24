"""The voice agent service (SOS-P5-07): consent and the call log before a call, lead context in, the
outcome and transcript back.

* start_agent_call places an AI call through the one call function (SOS-P2-05), which runs the consent
  function (SOS-P2-04) and links its Consent Check, with the status and warning, to the Call Log. Consent
  never blocks while Consent enforcement is Off. The call's purpose is recorded there too, and a
  promotional purpose on the 022 number is a warning on the check.
* handle_stream runs one Plivo stream: it finds the Call Log by the call id, builds the session from the
  company's settings and the lead's context, and writes the result back when the call ends.
* The agent never calls a real provider in tests: every adapter has a fake behind the settings.
"""

import json
import time
from dataclasses import dataclass

import frappe
from frappe import _

from sellos.telephony import call_log
from sellos.voice.agent import config, stream
from sellos.voice.agent.http import VoiceProviderError
from sellos.voice.agent.session import AgentSession

DOCTYPE = "Call Log"
OUTCOME = "Call Outcome"


@dataclass
class CallHandle:
	log: str
	session: AgentSession
	providers: str


def lead_context(lead: str) -> str:
	"""What the agent may say about the lead, as plain text. It holds no phone number and no email."""
	row = frappe.db.get_value(
		"Lead",
		lead,
		[
			"client",
			"configuration",
			"property_type",
			"preferred_localities",
			"purpose",
			"timeline",
			"possession",
			"budget_from",
			"budget_to",
			"source",
		],
		as_dict=True,
	)
	if not row:
		return ""
	name = (frappe.db.get_value("Client", row.client, "client_name") or "").split(" ")[0]
	parts = [f"Lead: {name}" if name else "Lead"]
	for label, value in (
		("configuration", row.configuration),
		("property type", row.property_type),
		("localities", row.preferred_localities),
		("buying for", row.purpose),
		("timeline", row.timeline),
		("possession", row.possession),
		("source", row.source),
	):
		if value:
			parts.append(f"{label}: {' '.join(str(value).split())}")
	if row.budget_from or row.budget_to:
		parts.append(f"budget: {row.budget_from or 0} to {row.budget_to or 0} rupees")
	return ". ".join(parts) + "."


def require_disclosure(settings) -> None:
	"""The agent never speaks, or places a live call, without its AI disclosure line (SOS-N21C)."""
	if not settings.disclosure:
		raise VoiceProviderError(_("The AI disclosure line is empty. Set it in the voice agent settings."))


def start_agent_call(lead, purpose, answer_url="", status_url=""):
	"""Place an AI call to the lead. Returns what place_logged_call returns, with the consent status and
	warning read back from the Consent Check. Raises VoiceProviderError before any call is placed when
	the agent is not set up or its AI disclosure line is empty (SOS-N21C)."""
	require_disclosure(config.load())
	config.build_adapters()  # a call is never placed for an agent that could not answer it
	placed = call_log.place_logged_call(
		lead, purpose, mode="AI", answer_url=answer_url, status_url=status_url
	)
	check = placed["check"]
	placed["consent_status"], placed["warning"] = check.status, check.warning
	return placed


def open_call(call_id, send, clock=None, adapters=None) -> CallHandle:
	"""The session for the AI call the stream belongs to. `adapters` is (stt, llm, tts), for a test that
	scripts the fakes; otherwise they come from the settings."""
	row = (
		frappe.db.get_value(DOCTYPE, {"call_id": call_id, "mode": "AI"}, ["name", "lead"], as_dict=True)
		if call_id
		else None
	)
	if not row:
		raise VoiceProviderError(_("This is not an AI call on this site."))
	settings = config.load()
	clock = clock or time.monotonic
	stt, llm, tts = adapters or config.build_adapters(settings, clock if hasattr(clock, "advance") else None)
	require_disclosure(settings)
	session = AgentSession(
		stt=stt,
		llm=llm,
		tts=tts,
		send=send,
		clock=clock,
		disclosure=settings.disclosure,
		keyterms=settings.keyterms,
		context=lead_context(row.lead),
		outcomes=frappe.get_all(OUTCOME, {"enabled": 1}, pluck="name", order_by="name"),
	)
	return CallHandle(row.name, session, f"{stt.name}, {llm.name}, {tts.name}")


def result_values(handle: CallHandle) -> dict:
	"""The Call Log values for the session's outcome, transcript, turn times and handover."""
	result = handle.session.result()
	values = {
		"transcript": result.transcript,
		"turn_latencies": json.dumps(result.latencies_ms),
		"turn_count": result.turns,
		"median_latency_ms": result.summary["median_ms"],
		"slowest_latency_ms": result.summary["slowest_ms"],
		"handed_over": 1 if result.handed_over else 0,
		"handover_reason": result.handover_reason,
		"ai_end_reason": result.end_reason,
		"ai_providers": handle.providers,
	}
	if result.outcome:
		values["outcome"] = result.outcome
	return values


def save_values(log: str, values: dict):
	"""Write the values to the Call Log. An outcome that is not on the company's list is left out."""
	values = dict(values)
	if values.get("outcome") and not frappe.db.exists(OUTCOME, values["outcome"]):
		del values["outcome"]
	frappe.db.set_value(DOCTYPE, log, values)


def run_stream(messages, send, clock=None, adapters=None):
	"""Run one call's stream: `messages` is an iterable of Plivo events, `send` takes one message to send.
	Returns the CallHandle, or None when the stream never started a call. Nothing is written."""
	handle = None
	for raw in messages:
		try:
			if handle is None:
				event = stream.parse(raw)
				if event.kind != "start":
					continue
				handle = open_call(event.call_id, send, clock, adapters)
			handle.session.handle(raw)
		except stream.StreamError:
			continue
		if handle.session.ended:
			break
	if handle is not None:
		handle.session.close("the connection closed")
	return handle


def handle_stream(messages, send, clock=None, adapters=None):
	"""Run one call and write its result to the Call Log. Returns the session's Result, or None."""
	handle = run_stream(messages, send, clock, adapters)
	if handle is None:
		return None
	save_values(handle.log, result_values(handle))
	return handle.session.result()
