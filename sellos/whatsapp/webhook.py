"""WhatsApp's events (SOS-P6-11): a registered provider webhook (sellos.access.webhooks).

The provider calls this with no SellOS user. The shared checks (body cap, rate limit per tenant,
signature before any write, replay) are in `sellos.access.webhooks`. This module supplies the signature
check (`X-Hub-Signature-256`, signed with the tenant's webhook signing secret from WhatsApp Settings), the
rule for an out of order event, and the handlers (`sellos.whatsapp.conversations`). The tenant is the site
the request arrives on.
"""

import hashlib
import hmac

import frappe

from sellos.access.webhooks import WebhookRequest, provider_webhook
from sellos.telephony.base import ProviderError
from sellos.whatsapp import conversations, settings
from sellos.whatsapp.base import InboundMessage, StatusEvent
from sellos.whatsapp.meta import SIGNATURE_PREFIX, signature_header
from sellos.whatsapp.provider import get_provider

PROVIDER = "whatsapp"
SECRET_SETTING = "WhatsApp Settings.app_secret"
MAX_BODY_BYTES = 256 * 1024
REQUESTS_PER_MINUTE = 600


def verify_signature(request: WebhookRequest, secret: str) -> str | None:
	"""The provider's signature of the raw body against the tenant's secret. Returns the replay key (a hash
	of the signed body) when the signature is valid, and None otherwise."""
	header = request.headers.get("x-hub-signature-256", "").strip()
	if not header.startswith(SIGNATURE_PREFIX) or not request.body:
		return None
	if not hmac.compare_digest(signature_header(request.body, secret), header):
		return None
	return hashlib.sha256(request.body).hexdigest()


@provider_webhook(
	provider=PROVIDER,
	signature=verify_signature,
	replay=(
		"A hash of the signed body is remembered per tenant in Webhook Event and a second delivery of the "
		"same body changes nothing. A customer message is also remembered by the provider's message id. A "
		"status for an earlier step than the message has reached (a late 'sent' after 'read') is ignored."
	),
	max_body_bytes=MAX_BODY_BYTES,
	rate_limit_per_tenant=REQUESTS_PER_MINUTE,
	secret_setting=SECRET_SETTING,
)
def whatsapp_event(request: WebhookRequest):
	"""WhatsApp's customer messages and message statuses."""
	token, _secret = settings._keys()
	number_id = frappe.db.get_single_value(settings.DOCTYPE, "phone_number_id") or ""
	try:
		events = get_provider(token, number_id).read_webhook(request.body)
	except ProviderError:
		return "ignored"
	for event in events:
		if isinstance(event, InboundMessage):
			conversations.receive(event)
		elif isinstance(event, StatusEvent):
			conversations.apply_status(event)
	return "ok"
