"""SOS-SETUP-13: SellOS runs only on port 8004, and the preflight proves the server is SellOS.

The port comes from sites/<site>/site_config.json first and sites/common_site_config.json second,
the order frappe.get_conf(site) uses, and anything but 8004 is refused with exit 2. The preflight is
tried against a fake server on a free port: one that answers ping but 404s /sellos (what a server
started without --site does, serving BuildOS's site) must exit 3, and one that redirects a guest
from /sellos must pass. Every case runs the real functions from scripts/lib/sellos_server.sh, and
the lines the gate and prepare-regression.sh run are read from the scripts themselves.
"""

import json
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
LIB = SCRIPTS / "lib" / "sellos_server.sh"
SERVE_CMD = "cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004"
SITE = "sellos_test.localhost"


def fake_server(sellos_status):
	"""A server on a free port that answers ping 200 and /sellos with `sellos_status`."""

	class Handler(BaseHTTPRequestHandler):
		def do_GET(self):
			if self.path == "/api/method/ping":
				body = b'{"message":"pong"}'
				self.send_response(200)
			elif self.path == "/sellos":
				body = b""
				self.send_response(sellos_status)
				if sellos_status in (301, 302):
					self.send_header("Location", "/login?redirect-to=/sellos")
			else:
				body = b""
				self.send_response(404)
			self.send_header("Content-Length", str(len(body)))
			self.end_headers()
			self.wfile.write(body)

		def log_message(self, *args):
			pass

	server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
	threading.Thread(target=server.serve_forever, daemon=True).start()
	return server


def free_port():
	server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
	port = server.server_address[1]
	server.server_close()
	return port


def bash(script, env=None):
	return subprocess.run(
		["bash", "-c", f"set -euo pipefail\nsource {LIB}\n{script}"],
		capture_output=True,
		text=True,
		env=env,
	)


class PortLookup(unittest.TestCase):
	def setUp(self):
		self.bench = Path(tempfile.mkdtemp(prefix="sellos-port-bench-"))
		self.addCleanup(shutil.rmtree, self.bench, ignore_errors=True)
		(self.bench / "sites" / SITE).mkdir(parents=True)

	def config(self, rel, conf):
		(self.bench / "sites" / rel).write_text(json.dumps(conf), encoding="utf-8")

	def require(self):
		return bash(f'sellos_require_port "{self.bench}" "{SITE}"\necho "PORT=$PORT"')

	def test_site_config_wins_over_shared_config(self):
		self.config("common_site_config.json", {"webserver_port": 8000})
		self.config(f"{SITE}/site_config.json", {"webserver_port": 8004})
		result = self.require()
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("PORT=8004", result.stdout)

	def test_shared_config_is_the_fallback(self):
		self.config("common_site_config.json", {"webserver_port": 8004})
		self.config(f"{SITE}/site_config.json", {"db_name": "x"})
		result = self.require()
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("PORT=8004", result.stdout)

	def test_shared_8000_without_a_site_port_is_refused(self):
		# This bench's real shared config says 8000 (BuildOS). The old lookup read only that file.
		self.config("common_site_config.json", {"webserver_port": 8000})
		self.config(f"{SITE}/site_config.json", {"db_name": "x"})
		result = self.require()
		self.assertEqual(result.returncode, 2, result.stdout)
		self.assertIn("'8000', not 8004", result.stderr)

	def test_any_port_but_8004_is_refused(self):
		self.config("common_site_config.json", {"webserver_port": 8004})
		for port in (8000, 8002, 8003, 8005, 8006):
			with self.subTest(port=port):
				self.config(f"{SITE}/site_config.json", {"webserver_port": port})
				result = self.require()
				self.assertEqual(result.returncode, 2, result.stdout)
				self.assertIn(f"'{port}', not 8004", result.stderr)

	def test_no_port_anywhere_is_refused(self):
		self.config(f"{SITE}/site_config.json", {"db_name": "x"})
		result = self.require()
		self.assertEqual(result.returncode, 2, result.stdout)
		self.assertIn("'unset', not 8004", result.stderr)


class Preflight(unittest.TestCase):
	def start(self, sellos_status):
		server = fake_server(sellos_status)
		self.addCleanup(server.server_close)
		self.addCleanup(server.shutdown)
		return server.server_address[1]

	def gate_line(self, script):
		"""The preflight call a script runs, taken from the script itself."""
		text = (SCRIPTS / script).read_text(encoding="utf-8")
		line = next(
			line.strip() for line in text.splitlines() if line.strip().startswith("sellos_preflight ")
		)
		self.assertEqual(line, 'sellos_preflight "$SITE" "$PORT"')
		return line

	def preflight(self, port, script="run-tests.sh"):
		return bash(f"SITE=127.0.0.1\nPORT={port}\n{self.gate_line(script)}\necho PREFLIGHT_PASSED")

	def test_ping_but_404_for_sellos_exits_3(self):
		port = self.start(404)
		for script in ("run-tests.sh", "prepare-regression.sh"):
			with self.subTest(script=script):
				result = self.preflight(port, script)
				self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
				self.assertNotIn("PREFLIGHT_PASSED", result.stdout)
				self.assertIn(
					f"The server on port {port} is not serving SellOS. Start it with: {SERVE_CMD}",
					result.stderr,
				)

	def test_ping_and_200_for_sellos_exits_3(self):
		# A desk or website page that renders for a guest is not SellOS: only SellOS redirects.
		result = self.preflight(self.start(200))
		self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

	def test_redirect_for_sellos_passes(self):
		for status in (301, 302):
			with self.subTest(status=status):
				result = self.preflight(self.start(status))
				self.assertEqual(result.returncode, 0, result.stderr)
				self.assertIn("PREFLIGHT_PASSED", result.stdout)

	def test_nothing_listening_exits_3(self):
		result = self.preflight(free_port())
		self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
		self.assertIn(SERVE_CMD, result.stderr)


class ScriptsUseTheRule(unittest.TestCase):
	def read(self, name):
		return (SCRIPTS / name).read_text(encoding="utf-8")

	def test_gate_and_regression_check_port_then_app_before_wiping(self):
		for name, wipe in (
			("run-tests.sh", 'gunzip -c "$BASELINE"'),
			("prepare-regression.sh", 'gunzip -c "$BASELINE"'),
		):
			with self.subTest(script=name):
				text = self.read(name)
				self.assertIn("lib/sellos_server.sh", text)
				require = text.index('sellos_require_port "$BENCH_DIR" "$SITE"')
				preflight = text.index('sellos_preflight "$SITE" "$PORT"')
				self.assertLess(require, preflight)
				self.assertLess(preflight, text.index(wipe))
				self.assertNotIn("common_site_config.json')).get('webserver_port'", text)

	def test_make_baseline_sets_port_8004_after_creating_the_site(self):
		text = self.read("make-baseline.sh")
		new_site = text.index('bench new-site "$SITE"')
		set_port = text.index('bench --site "$SITE" set-config -p webserver_port 8004')
		self.assertLess(new_site, set_port)

	def test_no_unpinned_serve_command_in_the_repository(self):
		files = subprocess.run(
			["git", "ls-files", "--cached", "--others", "--exclude-standard"],
			cwd=REPO_ROOT,
			capture_output=True,
			text=True,
			check=True,
		).stdout.split()
		bad = []
		for rel in files:
			path = REPO_ROOT / rel
			if rel.startswith(("docs/legacy/", "frontend/node_modules/")) or not path.is_file():
				continue
			if (
				path.suffix not in {".md", ".sh", ".js", ".py"}
				or rel == "sellos/tests/test_sellos_server_port.py"
			):
				continue
			for n, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
				# A line warning against the unpinned form names it next to "without --site".
				warning = "without" in line and "--site" in line.split("without", 1)[1]
				if (
					"serve --port" in line
					and "--site sellos_test.localhost serve --port 8004" not in line
					and not warning
				):
					bad.append(f"{rel}:{n}: {line.strip()}")
		self.assertEqual(bad, [], "every serve command must be the pinned SellOS one")


if __name__ == "__main__":
	unittest.main()
