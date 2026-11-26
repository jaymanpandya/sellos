"""DocuSeal's events (SOS-LOOP): a registered provider webhook (sellos.access.webhooks).

DocuSeal calls this with no SellOS user when a signer views, signs or declines, and when a submission completes or
expires. The shared checks (body cap, rate limit per tenant, secret before any write, replay) are in
`sellos.access.webhooks`. DocuSeal lets a webhook carry a header of the company's choosing, so the signature check is
the header `X-Webhook-Secret` against the secret saved in the company's settings (a password field), compared in
constant time. The tenant is the site the request arrives on. See docs/DOCUSEAL.md.
"""

import hashlib
import hmac
import json

from sellos.access.webhooks import WebhookRequest, provider_webhook
from sellos.inventory import docuseal

PROVIDER = "docuseal"
SECRET_SETTING = "SellOS Settings.docuseal_webhook_secret"
MAX_BODY_BYTES = 512 * 1024
REQUESTS_PER_MINUTE = 120
EVENTS = (
	"form.viewed",
	"form.started",
	"form.completed",
	"form.declined",
	"submission.completed",
	"submission.expired",
)


def _payload(body: bytes):
	try:
		payload = json.loads(body)
	except ValueError:
		return None
	if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
		return None
	return payload if isinstance(payload.get("event_type"), str) else None


def verify_secret(request: WebhookRequest, secret: str) -> str | None:
	"""The company's secret in the `X-Webhook-Secret` header. Returns the replay key (a hash of the event's type, time
	and id, which DocuSeal repeats when it retries) when the secret is right and the body is an event, else None."""
	sent = request.headers.get("x-webhook-secret", "")
	if not sent or not hmac.compare_digest(sent.encode(), secret.encode()):
		return None
	payload = _payload(request.body)
	if not payload:
		return None
	return hashlib.sha256(
		f"{payload['event_type']}:{payload.get('timestamp')}:{payload['data'].get('id')}".encode()
	).hexdigest()


@provider_webhook(
	provider=PROVIDER,
	signature=verify_secret,
	replay=(
		"A hash of the event type, DocuSeal's timestamp and the event's id is remembered per tenant in Webhook Event, "
		"so a retry of the same event changes nothing. A status only moves forward (Sent, Viewed, Signed, Declined, "
		"Expired), so a late 'viewed' after 'signed' is ignored."
	),
	max_body_bytes=MAX_BODY_BYTES,
	rate_limit_per_tenant=REQUESTS_PER_MINUTE,
	secret_setting=SECRET_SETTING,
)
def docuseal_event(request: WebhookRequest):
	"""A signer's progress on a mandate, and the signed copy and audit trail when everyone has signed."""
	payload = _payload(request.body)
	if not payload or payload["event_type"] not in EVENTS:
		return "ignored"
	return docuseal.apply_event(payload["event_type"], payload["data"], payload.get("timestamp"))
