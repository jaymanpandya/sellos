"""SOS-P0-05: deploy/wildcard_dns.py against a fake DigitalOcean API.

Covers: create, a second run that changes nothing, an update when the address differs, a dry run
that makes no call, a missing token, and a fake token that never appears in output, logs, an error,
a command line or a file.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "deploy" / "wildcard_dns.py"
TOKEN = "fake-do-token-5e8c21aa"
IP = "198.51.100.7"
OTHER_IP = "198.51.100.8"


def load_script():
	spec = importlib.util.spec_from_file_location("wildcard_dns_under_test", SCRIPT)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


class FakeDigitalOcean:
	"""A small DigitalOcean DNS API on a local port. Records every request."""

	def __init__(self, reject_with=None):
		self.records = []
		self.requests = []
		self.reject_with = reject_with
		fake = self

		class Handler(BaseHTTPRequestHandler):
			def log_message(self, *args):
				pass

			def answer(self, code, body):
				raw = json.dumps(body).encode()
				self.send_response(code)
				self.send_header("Content-Length", str(len(raw)))
				self.end_headers()
				self.wfile.write(raw)

			def handle_any(self):
				length = int(self.headers.get("Content-Length") or 0)
				body = json.loads(self.rfile.read(length)) if length else None
				fake.requests.append((self.command, self.path, self.headers.get("Authorization"), body))
				if fake.reject_with:
					return self.answer(401, {"message": fake.reject_with})
				if self.command == "GET":
					return self.answer(200, {"domain_records": list(fake.records)})
				if self.command == "POST":
					record = {**body, "id": len(fake.records) + 1}
					fake.records.append(record)
					return self.answer(201, {"domain_record": record})
				record_id = int(self.path.rsplit("/", 1)[1])
				for record in fake.records:
					if record["id"] == record_id:
						record.update(body)
				return self.answer(200, {})

			do_GET = do_POST = do_PUT = handle_any

		self.server = HTTPServer(("127.0.0.1", 0), Handler)
		self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
		self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

	def __enter__(self):
		self.thread.start()
		return self

	def __exit__(self, *exc):
		self.server.shutdown()
		self.server.server_close()

	def writes(self):
		return [r for r in self.requests if r[0] != "GET"]


class TestWildcardDns(unittest.TestCase):
	"""SOS-P0-05: the wildcard record and certificate script."""

	def setUp(self):
		self.module = load_script()
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		self.root = Path(self.tmp.name)
		self.commands = []
		self.lines = []

	def runner(self, argv, env):
		self.commands.append((list(argv), dict(env)))

	def run_script(self, api_url, env=None, extra=()):
		env = {"SELLOS_DO_TOKEN": TOKEN} if env is None else env
		argv = [
			"--ip",
			IP,
			"--email",
			"ops@example.invalid",
			"--api-url",
			api_url,
			"--lego-path",
			str(self.root / "lego"),
			"--systemd-dir",
			str(self.root / "systemd"),
			"--skip-tool-check",
			*extra,
		]
		return self.module.run(argv, env, self.lines.append, self.runner)

	def output(self):
		return "\n".join(self.lines)

	def test_creates_the_wildcard_record_and_configures_the_certificate(self):
		with FakeDigitalOcean() as api:
			self.assertEqual(self.run_script(api.url), 0)
			self.assertEqual(len(api.records), 1)
			record = api.records[0]
			self.assertEqual((record["type"], record["name"], record["data"]), ("A", "*.sellos", IP))
			self.assertEqual(api.requests[0][2], f"Bearer {TOKEN}")
		lego = self.commands[0][0]
		self.assertEqual(lego[0], "lego")
		self.assertIn("*.sellos.interactivesoftwares.com", lego)
		self.assertEqual(lego[lego.index("--dns") + 1], "digitalocean")
		self.assertEqual(lego[-1], "run")
		self.assertEqual(self.commands[0][1]["DO_AUTH_TOKEN"], TOKEN)
		self.assertIn(
			["systemctl", "enable", "--now", "sellos-cert-renew.timer"], [c[0] for c in self.commands]
		)
		timer = (self.root / "systemd" / "sellos-cert-renew.timer").read_text()
		self.assertIn("OnCalendar=", timer)
		service = (self.root / "systemd" / "sellos-cert-renew.service").read_text()
		self.assertIn("renew --days 30", service)
		self.assertIn("EnvironmentFile=", service)

	def test_a_second_run_changes_nothing(self):
		with FakeDigitalOcean() as api:
			self.assertEqual(self.run_script(api.url), 0)
			(self.root / "lego" / "certificates").mkdir(parents=True)
			(self.root / "lego" / "certificates" / "_.sellos.interactivesoftwares.com.crt").write_text("x")
			writes_before = len(api.writes())
			commands_before = len(self.commands)
			self.lines.clear()
			self.assertEqual(self.run_script(api.url), 0)
			self.assertEqual(len(api.writes()), writes_before)
			self.assertEqual(len(api.records), 1)
		self.assertEqual(len(self.commands), commands_before)
		self.assertIn("Nothing changed", self.output())

	def test_a_different_address_updates_the_record(self):
		with FakeDigitalOcean() as api:
			api.records.append({"id": 9, "type": "A", "name": "*.sellos", "data": OTHER_IP, "ttl": 300})
			self.assertEqual(self.run_script(api.url), 0)
			self.assertEqual(api.records[0]["data"], IP)
			self.assertEqual([w[0] for w in api.writes()], ["PUT"])

	def test_a_dry_run_prints_every_step_and_calls_nothing(self):
		with FakeDigitalOcean() as api:
			self.assertEqual(self.run_script(api.url, extra=["--dry-run"]), 0)
			self.assertEqual(api.requests, [])
		self.assertEqual(self.commands, [])
		self.assertFalse((self.root / "systemd").exists())
		for step in ("GET", "POST", "lego", "sellos-cert-renew.timer", "systemctl daemon-reload"):
			self.assertIn(step, self.output())

	def test_a_missing_token_is_a_clear_error_and_calls_nothing(self):
		with FakeDigitalOcean() as api:
			self.assertEqual(self.run_script(api.url, env={}), 1)
			self.assertEqual(api.requests, [])
		self.assertEqual(self.commands, [])
		self.assertIn("SELLOS_DO_TOKEN is not set", self.output())

	def test_the_token_never_appears_in_output_commands_or_files(self):
		with FakeDigitalOcean() as api:
			self.run_script(api.url)
		for argv, _env in self.commands:
			self.assertNotIn(TOKEN, " ".join(argv))
		self.assertNotIn(TOKEN, self.output())
		for path in self.root.rglob("*"):
			if path.is_file():
				self.assertNotIn(TOKEN, path.read_text())

	def test_an_api_error_that_echoes_the_token_is_redacted(self):
		with FakeDigitalOcean(reject_with=f"bad token {TOKEN}") as api:
			self.assertEqual(self.run_script(api.url), 1)
		self.assertIn("401", self.output())
		self.assertNotIn(TOKEN, self.output())

	def test_the_command_line_script_reports_a_missing_token_and_a_dry_run(self):
		base = [sys.executable, "-I", str(SCRIPT), "--ip", IP, "--email", "ops@example.invalid"]
		missing = subprocess.run(base, env={}, capture_output=True, text=True)
		self.assertEqual(missing.returncode, 1)
		self.assertIn("SELLOS_DO_TOKEN is not set", missing.stdout)
		dry = subprocess.run(
			[*base, "--dry-run"], env={"SELLOS_DO_TOKEN": TOKEN}, capture_output=True, text=True
		)
		self.assertEqual(dry.returncode, 0)
		self.assertNotIn(TOKEN, dry.stdout + dry.stderr)
		self.assertIn("Dry run", dry.stdout)
