"""The one place a key meets a request (SOS-N21A, docs/DEV_STRATEGY.md row 29).

`_exchange` reads the key, puts it in the request header and sends it. It never raises: it returns a
short failure sentence, so no traceback passes through a frame that holds the key. `post` holds only
the key's name and raises ProviderError with that sentence, which never has a key or a response body.
"""

import time
import urllib.error
import urllib.request

from sellos.voice.bakeoff import keys

TIMEOUT_SECONDS = 120


class ProviderError(RuntimeError):
	"""A provider call failed. The message holds no key and no response body."""


class Reply:
	def __init__(self, status, first_byte_s, total_s, body):
		self.status, self.first_byte_s, self.total_s, self.body = status, first_byte_s, total_s, body


def _exchange(url, body, headers, auth, on_chunk, keep_body):
	header_name, prefix, key_name = auth
	started = time.perf_counter()
	first = None
	collected = []
	try:
		request = urllib.request.Request(url, data=body, method="POST")
		for name, value in headers.items():
			request.add_header(name, value)
		request.add_header(header_name, prefix + keys.get_secret(key_name))
		with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
			status = response.status
			while True:
				chunk = response.read1(8192) if hasattr(response, "read1") else response.read(8192)
				if not chunk:
					break
				now = time.perf_counter() - started
				if first is None:
					first = now
				if keep_body:
					collected.append(chunk)
				if on_chunk is not None:
					on_chunk(chunk, now)
	except urllib.error.HTTPError as exc:
		return None, f"the provider answered HTTP {exc.code}"
	except keys.SecretMissing as exc:
		return None, str(exc)
	except (urllib.error.URLError, OSError, ValueError) as exc:
		return None, f"the request failed ({type(exc).__name__})"
	total = time.perf_counter() - started
	return Reply(status, first if first is not None else total, total, b"".join(collected)), None


def post(url, body, auth, headers=None, on_chunk=None, keep_body=True):
	"""POST `body`; `auth` is (header name, value prefix, Keychain item name). Returns a Reply."""
	reply, failure = _exchange(url, body, headers or {}, auth, on_chunk, keep_body)
	if failure:
		raise ProviderError(failure)
	return reply
