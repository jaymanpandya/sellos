"""The one place the live adapters send a request (SOS-P5-07).

A failure becomes a VoiceProviderError whose message is a short sentence: never the key, the url's
query, the request or the response body. Tests give the adapters a recorded `post` instead.
"""

import urllib.error
import urllib.request

TIMEOUT_SECONDS = 20


class VoiceProviderError(Exception):
	"""A speech, language model or voice provider failed. The message is safe to show and holds no key."""


def _request(url, body, headers):
	request = urllib.request.Request(url, data=body, method="POST")
	for name, value in headers.items():
		request.add_header(name, value)
	return request


def _failure(error) -> VoiceProviderError:
	if isinstance(error, urllib.error.HTTPError):
		return VoiceProviderError(f"The provider answered HTTP {error.code}.")
	return VoiceProviderError("The provider could not be reached.")


def post(url: str, body: bytes, headers: dict) -> bytes:
	"""POST and return the whole response body."""
	try:
		with urllib.request.urlopen(_request(url, body, headers), timeout=TIMEOUT_SECONDS) as reply:
			return reply.read()
	except (urllib.error.URLError, OSError, ValueError) as error:
		raise _failure(error) from None


def stream(url: str, body: bytes, headers: dict, chunk_size: int = 3200):
	"""POST and yield the response in chunks as they arrive."""
	try:
		with urllib.request.urlopen(_request(url, body, headers), timeout=TIMEOUT_SECONDS) as reply:
			while True:
				chunk = reply.read(chunk_size)
				if not chunk:
					return
				yield chunk
	except (urllib.error.URLError, OSError, ValueError) as error:
		raise _failure(error) from None
