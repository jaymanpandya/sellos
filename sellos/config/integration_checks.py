"""The read only checks behind Test connection on the Integrations screen (SOS-INT-1).

One adapter per provider. Each only reads (a profile, a balance, a login that is closed again), sends nothing,
spends nothing and creates nothing, and returns a plain success text or raises `CheckFailed` with the provider's
plain reason. A reason never holds a key.

No test calls a real provider. On a site that allows tests, a WhatsApp, Meta or LegiScore key that starts with
FAKEOK is a working one and one that starts with FAKEDOWN is a provider that cannot be reached, so a browser spec
can show both answers; any other key is refused. The fake keys are honoured only where `allow_tests` is set, never
on a company's site. DocuSeal is checked against a fake DocuSeal server on this machine, and email against a
replaced mail connection.
"""

import ipaddress
import smtplib
import socket
import ssl

import frappe
import requests
from frappe import _

TIMEOUT_SECONDS = 15
GRAPH_ROOT = "https://graph.facebook.com/v21.0"
LEGISCORE_ROOT = "https://legiscore.in/api/v1"
FAKE_OK, FAKE_DOWN = "FAKEOK", "FAKEDOWN"


class CheckFailed(Exception):
	"""A check did not pass. The message is the plain reason shown to the Company Admin."""


def http_get(url, headers=None, params=None):
	"""One GET with a timeout and no redirect. Returns (status, parsed JSON or {}). The single place that reaches
	a provider over HTTP, so a test replaces only this."""
	try:
		response = requests.get(
			url, headers=headers or {}, params=params, timeout=TIMEOUT_SECONDS, allow_redirects=False
		)
	except requests.RequestException:
		raise CheckFailed(_("The provider could not be reached. Try again in a few minutes.")) from None
	try:
		body = response.json()
	except ValueError:
		body = {}
	return response.status_code, body if isinstance(body, dict) else {}


def _fake(secret):
	"""The answer for a fake key on a site that allows tests, or None when the key is not a fake one."""
	if not frappe.conf.get("allow_tests") or not secret:
		return None
	if secret.startswith(FAKE_DOWN):
		raise CheckFailed(_("The provider could not be reached. Try again in a few minutes."))
	if secret.startswith(FAKE_OK):
		return _("Connected. The provider accepted the keys.")
	raise CheckFailed(_("The provider refused these keys. Check them and try again."))


def _reason(body, fallback) -> str:
	error = body.get("error")
	text = error.get("message") if isinstance(error, dict) else error or body.get("message")
	return str(text or "").strip()[:200] or fallback


def _bearer(token):
	return {"Authorization": f"Bearer {token}"}


def _failure(status, body, refused, provider):
	if status in (401, 403):
		return CheckFailed(refused)
	if status >= 500:
		return CheckFailed(_("{0} is having a problem. Try again in a few minutes.").format(provider))
	return CheckFailed(
		_reason(body, _("{0} did not accept the details (status {1}).").format(provider, status))
	)


def whatsapp(values) -> str:
	from sellos.whatsapp.base import ProviderError
	from sellos.whatsapp.meta import MetaCloudProvider

	fake = _fake(values["access_token"])
	if fake:
		return fake
	try:
		return str(MetaCloudProvider(values["access_token"], values["phone_number_id"]).test_connection())
	except ProviderError as error:
		raise CheckFailed(str(error)) from None


def meta_lead_ads(values) -> str:
	fake = _fake(values["page_access_token"])
	if fake:
		return fake
	status, body = http_get(
		f"{GRAPH_ROOT}/{values['page_id']}", _bearer(values["page_access_token"]), {"fields": "id,name"}
	)
	if status == 200 and body.get("id"):
		return _("Connected. Meta accepted the page access token.")
	refused = _("Meta refused this page access token. Check the token and the page ID.")
	raise _failure(status, body, refused, "Meta")


def legiscore(values) -> str:
	fake = _fake(values["api_key"])
	if fake:
		return fake
	status, body = http_get(f"{LEGISCORE_ROOT}/search/credits", _bearer(values["api_key"]))
	if status == 200:
		return _("Connected. LegiScore accepted the key.")
	raise _failure(status, body, _("LegiScore refused this API key."), "LegiScore")


def docuseal(values) -> str:
	from sellos.inventory import docuseal as docuseal_api

	try:
		docuseal_api.request("GET", "/templates?limit=1")
	except (docuseal_api.DocuSealError, frappe.ValidationError) as error:
		raise CheckFailed(str(error)) from None
	return _("Connected. DocuSeal answered: the address and the key work.")


def _public_host(host) -> bool:
	"""A host the server may connect to: public addresses only, so the check cannot probe the private network.
	A site that allows tests may use this machine."""
	try:
		addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
	except OSError:
		return False
	if frappe.conf.get("allow_tests") and all(ipaddress.ip_address(a).is_loopback for a in addresses):
		return True
	return bool(addresses) and all(ipaddress.ip_address(a).is_global for a in addresses)


def email(values) -> str:
	host = values["host"]
	if not host:
		raise CheckFailed(
			_("A provider API key has no read only check. Enter the SMTP host to test the connection.")
		)
	port = int(values["port"] or 587)
	if not _public_host(host):
		raise CheckFailed(_("The SMTP host could not be found, or it is not a public address."))
	try:
		context = ssl.create_default_context()
		if port == 465:
			server = smtplib.SMTP_SSL(host, port, timeout=TIMEOUT_SECONDS, context=context)
		else:
			server = smtplib.SMTP(host, port, timeout=TIMEOUT_SECONDS)
		try:
			server.ehlo()
			if port != 465 and server.has_extn("starttls"):
				server.starttls(context=context)
				server.ehlo()
			if values["user"]:
				server.login(values["user"], values["password"])
			server.noop()
		finally:
			try:
				server.quit()
			except (smtplib.SMTPException, OSError):
				pass
	except smtplib.SMTPAuthenticationError:
		raise CheckFailed(_("The mail server refused this user and password.")) from None
	except (smtplib.SMTPException, OSError):
		raise CheckFailed(_("The mail server could not be reached with this host and port.")) from None
	return _("Connected. The mail server accepted the login.")


ADAPTERS = {
	"whatsapp": whatsapp,
	"meta_lead_ads": meta_lead_ads,
	"email": email,
	"docuseal": docuseal,
	"legiscore": legiscore,
}


def run(provider, values) -> str:
	"""The success text of a provider's read only check, or CheckFailed with the plain reason."""
	return ADAPTERS[provider](values)
