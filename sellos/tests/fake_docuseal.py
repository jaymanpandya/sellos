"""A fake DocuSeal server for tests (SOS-LOOP): it answers the few calls SellOS makes, on this machine, and records
what it was sent. It is never a real signing service, and its key is a fake one. Start it, point the company's
DocuSeal address at `fake.url`, and stop it when the test ends.

    fake = FakeDocuSeal().start()
    self.addCleanup(fake.stop)
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sellos.tests.files import tiny_pdf

KEY = "p-fake-docuseal-key-3f9a"
WEBHOOK_SECRET = "p-fake-docuseal-secret-b71c"
SUBMISSION_ID = 55
SELLER_SUBMITTER = 101
COMPANY_SUBMITTER = 102


class _Handler(BaseHTTPRequestHandler):
	def log_message(self, *args):  # keep the test output clean
		pass

	def _send(self, status, body=b"", content_type="application/json"):
		self.send_response(status)
		self.send_header("Content-Type", content_type)
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)

	def _json(self, status, payload):
		self._send(status, json.dumps(payload).encode())

	def _authorised(self) -> bool:
		return self.headers.get("X-Auth-Token") == KEY

	def do_GET(self):
		fake = self.server.fake
		fake.requests.append(("GET", self.path, None, self.headers.get("X-Auth-Token")))
		if self.path.startswith("/files/"):
			return self._send(200, fake.files.get(self.path, b""), "application/pdf")
		if not self._authorised():
			return self._json(401, {"error": "unauthorised"})
		if self.path.startswith("/api/templates"):
			return self._json(200, {"data": [], "pagination": {}})
		self._json(404, {})

	def do_POST(self):
		fake = self.server.fake
		body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
		fake.requests.append(("POST", self.path, body, self.headers.get("X-Auth-Token")))
		if not self._authorised():
			return self._json(401, {"error": "unauthorised"})
		if fake.fail:
			return self._json(500, {"error": "boom"})
		if self.path == "/api/templates/pdf":
			return self._json(200, {"id": 7, "name": body.get("name")})
		if self.path == "/api/submissions":
			ids = {"Seller": SELLER_SUBMITTER, "Company": COMPANY_SUBMITTER}
			return self._json(
				201,
				[
					{
						"id": ids[s["role"]],
						"submission_id": SUBMISSION_ID,
						"role": s["role"],
						"email": s["email"],
						"status": "sent",
					}
					for s in body["submitters"]
				],
			)
		self._json(404, {})


class FakeDocuSeal:
	def __init__(self):
		self.requests: list[tuple] = []  # (method, path, body, key)
		self.files = {"/files/signed.pdf": tiny_pdf(), "/files/audit.pdf": tiny_pdf() + b"\n% audit trail\n"}
		self.fail = False
		self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
		self._server.fake = self
		self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

	@property
	def url(self) -> str:
		return f"http://127.0.0.1:{self._server.server_address[1]}"

	def start(self):
		self._thread.start()
		return self

	def stop(self):
		self._server.shutdown()
		self._server.server_close()

	def posts(self, path):
		return [body for method, p, body, _key in self.requests if method == "POST" and p == path]
