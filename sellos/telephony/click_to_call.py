"""Click to call (SOS-P2-07): an agent clicks a lead and is connected without dialling.

The flow, in two legs that both stay in India:

1. start_call rings the agent's own Indian mobile first, from the 022 number. The agent's number is the
   `mobile_no` of their user (SOS-P1-17). A number outside India is refused with a clear message.
2. When the provider reports that the agent answered, `connect_lead` rings the lead and the call is
   bridged. If the lead cannot be anchored in India, or the provider cannot connect the second leg, the
   Call Log keeps the reason in `bridge_error` and the agent is told. This is the media anchoring error path.
3. When the call has ended the agent must record its outcome (`record_outcome`), through the same
   call outcome list as a call logged by hand (SOS-P1-21). `pending_outcomes` lists the calls still owed one.

Consent never blocks (Jayman, 10 November 2026). The lead's consent status and warning come back before the
call (`call_preview`) and during it (`call_status`), and every status may be called: the only refusal is the
one consent function, and only when the company setting "Consent enforcement" is On. Nothing here returns the
lead's phone number: the agent never sees a number they are not allowed to see.
"""

import frappe
from frappe import _
from frappe.utils import cint, get_url

from sellos.access.registry import sellos_api
from sellos.access.roles import AGENT, COMPANY_ADMIN, SALES_MANAGER
from sellos.crm import call_outcomes, consent
from sellos.telephony import call_log, router, settings
from sellos.telephony.base import ProviderError
from sellos.telephony.provider import get_provider

DOCTYPE = call_log.DOCTYPE
FINAL_STATES = ("completed", "busy", "no-answer", "failed", "cancelled")
ANSWER_PATH = "/api/method/sellos.telephony.webhook.plivo_call_event"
# The words the screen shows for each step of a call.
STAGES = {
	"agent_ringing": "Calling your phone. Answer it to be connected.",
	"connecting": "You answered. Connecting the lead.",
	"lead_ringing": "Ringing the lead.",
	"connected": "Connected to the lead.",
	"ended": "The call has ended.",
	"no_answer": "Your phone did not answer, so the lead was not called.",
	"error": "The lead could not be connected.",
}


def agent_mobile(user=None) -> str:
	"""The user's Indian mobile number in E.164, or a ProviderError with a clear message.

	Both legs stay in India, so a number that is missing, is not Indian or is not a mobile is refused."""
	user = user or frappe.session.user
	number = router._compact(frappe.db.get_value("User", user, "mobile_no") or "")
	if not number:
		raise ProviderError(
			_("Your user has no mobile number. Ask your Company Admin to add your Indian mobile.")
		)
	if not number.startswith("+91") or not router._IN_MOBILE.match(number):
		raise ProviderError(
			_(
				"Your mobile number is not an Indian number (+91 and ten digits). Both legs of a call stay in India."
			)
		)
	return number


def _lead_doc(lead):
	if not frappe.db.exists("Lead", lead):
		frappe.throw(_("Lead {0} was not found.").format(lead), frappe.DoesNotExistError)
	doc = frappe.get_doc("Lead", lead)
	doc.check_permission("write")
	return doc


def _fail(error: ProviderError):
	frappe.throw(str(error), frappe.ValidationError)


def _consent_view(lead, purpose=None) -> dict:
	"""The lead's consent status and its warning (no write, no number)."""
	status = consent.compute_status(lead)
	level, message = consent.WARNINGS[status]
	extra = router.purpose_warning(purpose) if purpose else ""
	return {
		"consent_status": status,
		"consent_warning": level or "none",
		"consent_message": " ".join(part for part in (message, extra) if part),
	}


@sellos_api(AGENT, COMPANY_ADMIN, SALES_MANAGER)
def call_preview(lead, purpose="Service"):
	"""What the Call button shows before the call: the consent status and warning, the purpose's warning
	and whether the user can be rung (their Indian mobile). A lead in any consent status can be called."""
	_lead_doc(lead)
	view = _consent_view(lead, purpose)
	error = ""
	try:
		agent_mobile()
		call_log._lead_number(lead)
	except ProviderError as exc:
		error = str(exc)
	view.update({"lead": lead, "purposes": list(router.PURPOSES), "can_call": not error, "error": error})
	return view


def _urls() -> tuple[str, str]:
	url = get_url() + ANSWER_PATH
	return url, url


@sellos_api(AGENT, COMPANY_ADMIN, SALES_MANAGER)
def click_to_call(lead, purpose="Service"):
	"""Ring the user's mobile first, then the lead. Returns the Call Log and the consent status and warning.

	With Consent enforcement Off (the default) every consent status proceeds. With it On the one consent
	function may refuse, and then `refused` is true, `reason` says why and no call is placed. A number
	outside India, a missing number or a provider failure shows its clear message and places no call."""
	_lead_doc(lead)
	try:
		agent_number = agent_mobile()
		route = router.route_call(call_log._lead_number(lead), purpose)
	except ProviderError as error:
		_fail(error)
	check = consent.check_contact(lead, "Call", route.purpose)
	view = _consent_view(lead, route.purpose)
	if check.refused:
		return {"call_log": None, "refused": True, "reason": check.reason, **view}
	auth_id, auth_token = settings._keys()
	answer_url, status_url = _urls()
	try:
		provider = get_provider(auth_id, auth_token)
		placed = provider.place_call(route.from_number, agent_number, answer_url, status_url)
	except ProviderError as error:
		_fail(error)
	log = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"lead": lead,
			"provider": provider.name,
			"call_id": placed.call_id,
			"mode": "Manual",
			"purpose": route.purpose,
			"state": placed.state,
			"started_on": frappe.utils.now_datetime(),
			"agent": frappe.session.user,
			"consent_check": check.check,
			"consent_record": consent.live_record(lead),
		}
	).insert(ignore_permissions=True)
	consent.link_check(check.check, DOCTYPE, log.name)
	return {"call_log": log.name, "refused": False, "reason": "", **view}


def connect_lead(log_name) -> bool:
	"""The agent answered: ring the lead from the 022 number. True when the second leg was placed.

	Run by the webhook (SOS-P2-06) on the agent's answer event, so a replayed event is already dropped
	and a second call is dropped here too. A failure is kept on the log as `bridge_error` and the call is
	marked failed, so the screen says why: the lead is never left ringing into nothing."""
	row = frappe.db.get_value(
		DOCTYPE, log_name, ["lead", "purpose", "agent", "lead_call_id", "bridge_error"], as_dict=True
	)
	if not row or not row.agent or row.lead_call_id or row.bridge_error:
		return False
	try:
		# Both legs must be in India: the lead's number is routed again, so a number that changed to one
		# outside India after the agent leg was placed is refused here, before any second leg.
		route = router.route_call(call_log._lead_number(row.lead), row.purpose)
		auth_id, auth_token = settings._keys()
		placed = get_provider(auth_id, auth_token).place_call(route.from_number, route.to_number, *_urls())
	except ProviderError as error:
		frappe.db.set_value(DOCTYPE, log_name, {"bridge_error": str(error)[:500], "state": "failed"})
		return False
	frappe.db.set_value(DOCTYPE, log_name, {"lead_call_id": placed.call_id, "lead_state": "queued"})
	return True


def lead_leg(call_id):
	"""The Call Log row whose second leg (to the lead) has this provider id, or None."""
	return frappe.db.get_value(
		DOCTYPE,
		{"lead_call_id": call_id},
		["name", "call_id", "state", "lead_state"],
		as_dict=True,
	)


# --- the call in progress ---------------------------------------------------------------------------------


def _stage(row) -> str:
	state, lead_state = row.state, row.lead_state or ""
	if row.bridge_error:
		return "error"
	if state in FINAL_STATES:
		return "no_answer" if state in ("no-answer", "busy") and not row.lead_call_id else "ended"
	if lead_state == "in-progress":
		return "connected"
	if row.lead_call_id:
		return "lead_ringing" if lead_state == "ringing" else "connecting"
	return "connecting" if state == "in-progress" else "agent_ringing"


def _owned_log(call_log_name):
	row = frappe.db.get_value(
		DOCTYPE,
		call_log_name,
		[
			"name",
			"lead",
			"state",
			"lead_state",
			"lead_call_id",
			"bridge_error",
			"agent",
			"outcome",
			"consent_check",
			"duration",
		],
		as_dict=True,
	)
	if not row or row.agent != frappe.session.user:
		frappe.throw(_("This is not your call."), frappe.PermissionError)
	return row


def _status(row) -> dict:
	check = (
		frappe.db.get_value(
			"Consent Check", row.consent_check, ["consent_status", "warning_level", "warning"], as_dict=True
		)
		if row.consent_check
		else None
	)
	stage = _stage(row)
	ended = row.state in FINAL_STATES or stage == "error"
	return {
		"call_log": row.name,
		"lead": row.lead,
		"state": row.state,
		"lead_state": row.lead_state or "",
		"stage": stage,
		"message": _(STAGES[stage]),
		"error": row.bridge_error or "",
		"ended": ended,
		"outcome_needed": ended and not row.outcome,
		"outcome": row.outcome or "",
		"consent_status": check.consent_status if check else "",
		"consent_warning": (check.warning_level if check else "") or "none",
		"consent_message": check.warning if check else "",
		"duration": cint(row.duration),
	}


@sellos_api(AGENT, COMPANY_ADMIN, SALES_MANAGER)
def call_status(call_log):
	"""Where the user's call has got to, with the lead's consent status and warning (shown during the call)."""
	return _status(_owned_log(call_log))


@sellos_api(AGENT, COMPANY_ADMIN, SALES_MANAGER)
def pending_outcomes():
	"""The user's ended calls that still have no outcome, oldest first. The outcome form is required, so the
	screen asks again until each one has it."""
	names = frappe.get_all(
		DOCTYPE,
		filters={"agent": frappe.session.user, "outcome": ["is", "not set"], "state": ["in", FINAL_STATES]},
		order_by="creation asc",
		limit_page_length=20,
		pluck="name",
	)
	return [_status(_owned_log(name)) for name in names]


@sellos_api(AGENT, COMPANY_ADMIN, SALES_MANAGER)
def record_outcome(call_log, outcome, notes=None, follow_up_at=None, stage=None, lost_reason=None):
	"""The outcome form after the call. An outcome is required, from the company's list, and so is the follow
	up date when the outcome needs one. It is saved on the Call Log and as a Call activity on the lead."""
	row = _owned_log(call_log)
	if _stage(row) not in ("ended", "no_answer", "error"):
		frappe.throw(_("The call is still going. Record its outcome when it ends."))
	if row.outcome:
		frappe.throw(_("The outcome of this call is already recorded."))
	_lead_doc(row.lead)
	log = frappe.db.get_value(DOCTYPE, call_log, ["duration", "started_on"], as_dict=True)
	result = call_outcomes.log_call(
		row.lead, outcome, notes, log.duration, follow_up_at, stage, lost_reason, log.started_on
	)
	frappe.db.set_value(DOCTYPE, call_log, "outcome", outcome)
	return result
