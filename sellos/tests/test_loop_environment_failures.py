"""SOS-SETUP-14: an environment problem is never a task failure.

The real scripts/build-loop.sh runs in a throwaway bench and repository, with a fake gate whose exit
codes the test chooses, a fake claude, a fake notifier and a fake server on a free port. Gate exit 1
is repaired. Gate exit 2 or 3, a failed server preflight after a failed gate run, and a gate output
of nothing but connection errors to a dead server all stop the loop with the task still In Progress,
its work untouched in the working tree, no repair run, no reset, no salvage branch, and a
notification that says "Environment problem, not the task".

The real scripts/run-tests.sh is also run in the throwaway bench: a server that answers ping but
404s /sellos makes the gate exit 3, and a command that fails with status 2 inside the gate comes out
as 1, so only the preflight can report an environment problem.

The only change to the copied scripts is SELLOS_PORT in lib/sellos_server.sh, set to the fake
server's port, because the real 8004 belongs to the running SellOS server.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
TASK = "SOS-X-1"
SITE = "127.0.0.1"
TASKS_MD = f"""# Tasks

### {TASK}: a task
- **Status:** Not Started
- **Priority:** P0
- **Dependencies:** None
"""
GIT_ENV = {
	"GIT_AUTHOR_NAME": "Loop Test",
	"GIT_AUTHOR_EMAIL": "loop@test.invalid",
	"GIT_COMMITTER_NAME": "Loop Test",
	"GIT_COMMITTER_EMAIL": "loop@test.invalid",
}
FAKE_GATE = """#!/usr/bin/env bash
# A fake gate: takes the next exit code from codes.txt and prints out.txt, writing its log as the gate does.
F="$FAKE_DIR"
echo run >>"$F/gate_calls"
code="$(head -n 1 "$F/codes.txt")"; tail -n +2 "$F/codes.txt" >"$F/codes.rest"; mv "$F/codes.rest" "$F/codes.txt"
mkdir -p "$SELLOS_LOG_DIR"
cat "$F/out.txt" | tee "$SELLOS_LOG_DIR/latest.log"
exit "${code:-1}"
"""
FAKE_CLAUDE = """#!/usr/bin/env bash
echo call >>"$FAKE_DIR/claude_calls"
echo "work $(wc -l <"$FAKE_DIR/claude_calls" | tr -d ' ')" >>sellos/work.py
echo "IMPLEMENTATION_READY: did the work"
"""
FAKE_NOTIFY = """#!/usr/bin/env bash
printf '%s\\n----\\n' "$1" >>"$FAKE_DIR/notifications"
"""
FAKE_GH = "#!/usr/bin/env bash\nexit 0\n"
ENV_HEADLINE = "Environment problem, not the task"
REFUSED_OUTPUT = """  1) smoke app shell loads:
     CypressError: `cy.visit()` failed trying to load:

     http://127.0.0.1:{port}/sellos

     We attempted to make an http request to this URL but the request failed without a response.

     We received this error at the network level:

       > Error: connect ECONNREFUSED 127.0.0.1:{port}

  ✖  1 of 1 failed (100%)
"""


class Handler(BaseHTTPRequestHandler):
	sellos_status = 302

	def do_GET(self):
		if self.path == "/api/method/ping":
			self.send_response(200)
		else:
			self.send_response(self.sellos_status if self.path == "/sellos" else 404)
			if self.path == "/sellos" and self.sellos_status in (301, 302):
				self.send_header("Location", "/login?redirect-to=/sellos")
		self.send_header("Content-Length", "0")
		self.end_headers()

	def log_message(self, *args):
		pass


def free_port():
	server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
	port = server.server_address[1]
	server.server_close()
	return port


class Sandbox(unittest.TestCase):
	"""A throwaway bench with the SellOS scripts copied in, and a fake server."""

	def setUp(self):
		if subprocess.run(["pgrep", "-f", r"buildos/scripts/(run-tests|build-loop)\.sh"]).returncode == 0:
			self.skipTest("a BuildOS gate or loop is running, and the scripts refuse to start beside it")
		self.root = Path(tempfile.mkdtemp(prefix="sellos-loop-env-"))
		self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
		self.bench = self.root / "bench"
		self.repo = self.bench / "apps" / "sellos"
		self.fake = self.root / "fake"
		self.bin = self.fake / "bin"
		self.logs = self.root / "logs"
		self.bin.mkdir(parents=True)
		(self.repo / "sellos").mkdir(parents=True)
		(self.repo / "scripts" / "lib").mkdir(parents=True)
		self.port = None

	def serve(self, sellos_status):
		handler = type("H", (Handler,), {"sellos_status": sellos_status})
		server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
		threading.Thread(target=server.serve_forever, daemon=True).start()
		self.addCleanup(server.server_close)
		self.addCleanup(server.shutdown)
		self.use_port(server.server_address[1])

	def use_port(self, port):
		self.port = port
		site = self.bench / "sites" / SITE
		site.mkdir(parents=True, exist_ok=True)
		(site / "site_config.json").write_text(json.dumps({"webserver_port": port}), encoding="utf-8")
		(self.bench / "sites" / "common_site_config.json").write_text(
			json.dumps({"webserver_port": 8000}), encoding="utf-8"
		)
		lib = (SCRIPTS / "lib" / "sellos_server.sh").read_text(encoding="utf-8")
		patched = re.sub(r"^SELLOS_PORT=8004$", f"SELLOS_PORT={port}", lib, count=1, flags=re.M)
		self.assertNotEqual(lib, patched, "SELLOS_PORT=8004 is no longer in lib/sellos_server.sh")
		self.write(self.repo / "scripts/lib/sellos_server.sh", patched)

	def write(self, path, text, mode=None):
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(text, encoding="utf-8")
		if mode:
			path.chmod(mode)

	def env(self):
		env = {
			"PATH": f"{self.bin}:{os.environ.get('PATH', '/usr/bin:/bin')}",
			"HOME": str(self.root),
			"FAKE_DIR": str(self.fake),
			"SELLOS_BENCH_DIR": str(self.bench),
			"SELLOS_TEST_SITE": SITE,
			"SELLOS_LOG_DIR": str(self.logs),
			"SELLOS_LOOP_LOCK": str(self.root / "loop.lock"),
			"SELLOS_TASK_BLOCK_PATH": str(self.root / "task-block.md"),
			**GIT_ENV,
		}
		return env

	def read(self, name):
		path = self.fake / name
		return path.read_text(encoding="utf-8") if path.exists() else ""


class LoopEnvironmentFailures(Sandbox):
	def setUp(self):
		super().setUp()
		for name in ("build-loop.sh", "select-next-task.sh", "set-task-status.sh", "limit_wait.py"):
			shutil.copy2(SCRIPTS / name, self.repo / "scripts" / name)
		shutil.copy2(SCRIPTS / "lib" / "tasks.py", self.repo / "scripts" / "lib" / "tasks.py")
		self.write(self.repo / "scripts/run-tests.sh", FAKE_GATE, 0o755)
		self.write(self.repo / "scripts/notify-telegram.sh", FAKE_NOTIFY, 0o755)
		self.write(self.bin / "claude", FAKE_CLAUDE, 0o755)
		self.write(self.bin / "gh", FAKE_GH, 0o755)
		self.write(self.repo / "TASKS.md", TASKS_MD)
		self.write(self.repo / "sellos/work.py", "base = 1\n")
		origin = self.root / "origin.git"
		subprocess.run(["git", "init", "-q", "--bare", "-b", "1.0", str(origin)], check=True)
		self.git("init", "-q", "-b", "1.0")
		self.git("add", "-A")
		self.git("commit", "-q", "-m", "SOS-X-0 base")
		self.git("remote", "add", "origin", str(origin))
		self.git("push", "-q", "origin", "1.0")
		self.base = self.git("rev-parse", "HEAD")
		# The patched lib is written once the fake server has a port. It is not the task's work.
		with open(self.repo / ".git/info/exclude", "a", encoding="utf-8") as f:
			f.write("scripts/lib/sellos_server.sh\n")

	def git(self, *args):
		return subprocess.run(
			["git", *args],
			cwd=self.repo,
			capture_output=True,
			text=True,
			check=True,
			env={**os.environ, **GIT_ENV},
		).stdout.strip()

	def run_loop(self, codes, output="--- a gate run ---\nAssertionError: 1 != 2\n", max_runs=2):
		self.write(self.fake / "codes.txt", "".join(f"{c}\n" for c in codes))
		self.write(self.fake / "out.txt", output)
		env = {**self.env(), "SELLOS_MAX_GATE_RUNS": str(max_runs)}
		result = subprocess.run(
			["bash", str(self.repo / "scripts/build-loop.sh")],
			cwd=self.repo,
			capture_output=True,
			text=True,
			env=env,
			timeout=120,
		)
		self.out = result.stdout + result.stderr
		return result.returncode

	def status(self):
		text = (self.repo / "TASKS.md").read_text(encoding="utf-8")
		return re.search(r"\*\*Status:\*\* *(.*)", text).group(1).strip()

	def calls(self, name):
		return len(self.read(name).splitlines())

	def assert_stopped_for_environment(self, code, *expected_text):
		self.assertEqual(code, 3, self.out)
		self.assertEqual(self.status(), "In Progress", self.out)
		self.assertEqual(self.calls("claude_calls"), 1, "a repair run was started")
		self.assertEqual(
			self.git("log", "-1", "--format=%s"), f"{TASK}: mark In Progress", "something was committed"
		)
		self.assertEqual(self.git("rev-parse", "HEAD~1"), self.base)
		self.assertIn(
			"work 1", (self.repo / "sellos/work.py").read_text(encoding="utf-8"), "the work was reset"
		)
		self.assertEqual(self.git("status", "--porcelain"), "M sellos/work.py")
		self.assertEqual(self.git("branch", "--list", "failed/*"), "", "a salvage branch was made")
		note = self.read("notifications")
		self.assertIn(ENV_HEADLINE, note)
		self.assertIn("restart the loop", note)
		self.assertIn("stays In Progress", note)
		self.assertNotIn("failed tests", note)
		for text in expected_text:
			self.assertIn(text, note)

	def test_gate_exit_1_is_repaired(self):
		self.serve(302)
		code = self.run_loop([1, 1])
		self.assertEqual(code, 0, self.out)
		self.assertEqual(self.calls("gate_calls"), 2)
		self.assertEqual(self.calls("claude_calls"), 2, "exit 1 must start one repair run")
		self.assertEqual(self.status(), "Blocked")
		self.assertNotIn(ENV_HEADLINE, self.read("notifications"))
		self.assertTrue(self.git("branch", "--list", "failed/*"))

	def test_gate_exit_2_stops_without_repair_or_reset(self):
		self.serve(302)
		code = self.run_loop(
			[2], output="The webserver_port for sellos_test.localhost is '8000', not 8004.\n"
		)
		self.assertEqual(self.calls("gate_calls"), 1)
		self.assert_stopped_for_environment(code, "exit 2", "is '8000', not 8004")

	def test_gate_exit_3_stops_without_repair_or_reset(self):
		self.serve(302)
		message = "The server on port 8004 is not serving SellOS. Start it with: cd ~/iespl-bench && bench --site sellos_test.localhost serve --port 8004\n"
		code = self.run_loop([3, 0], output=message)
		self.assertEqual(self.calls("gate_calls"), 1)
		self.assert_stopped_for_environment(code, "exit 3", "is not serving SellOS")

	def test_preflight_before_repair_stops_when_the_server_is_not_sellos(self):
		self.serve(404)
		code = self.run_loop([1, 0])
		self.assertEqual(self.calls("gate_calls"), 1)
		self.assert_stopped_for_environment(code, "server preflight fails", "is not serving SellOS")

	def test_preflight_before_blocking_stops_when_the_server_died(self):
		self.use_port(free_port())
		code = self.run_loop([1], max_runs=1)
		self.assertEqual(self.calls("gate_calls"), 1)
		self.assert_stopped_for_environment(code, "server preflight fails")

	def test_only_connection_errors_and_a_dead_server_is_the_environment(self):
		self.use_port(free_port())
		code = self.run_loop([1, 0], output=REFUSED_OUTPUT.format(port=self.port))
		self.assert_stopped_for_environment(code, "connection error", "ECONNREFUSED")

	def test_only_connection_errors_with_a_live_server_is_repaired(self):
		self.serve(302)
		code = self.run_loop([1, 1], output=REFUSED_OUTPUT.format(port=self.port))
		self.assertEqual(code, 0, self.out)
		self.assertIn("Every failure was a connection error, but the server preflight passes now", self.out)
		self.assertEqual(self.calls("claude_calls"), 2)
		self.assertEqual(self.status(), "Blocked")


class GateExitCodes(Sandbox):
	"""The real run-tests.sh: only its preflight may exit 2 or 3."""

	def setUp(self):
		super().setUp()
		shutil.copy2(SCRIPTS / "run-tests.sh", self.repo / "scripts" / "run-tests.sh")
		# SOS-SETUP-16: the gate checks skipped specs before the baseline restore. Give it the real
		# check, a backlog and a spec folder with no skips, so it passes and the restore still runs.
		shutil.copy2(SCRIPTS / "check_no_stale_skips.py", self.repo / "scripts" / "check_no_stale_skips.py")
		(self.repo / "scripts" / "lib").mkdir(parents=True, exist_ok=True)
		shutil.copy2(SCRIPTS / "lib" / "tasks.py", self.repo / "scripts" / "lib" / "tasks.py")
		self.write(self.repo / "TASKS.md", "### SOS-X-1: a task\n- **Status:** In Progress\n")
		(self.repo / "cypress" / "integration").mkdir(parents=True, exist_ok=True)
		# SOS-SETUP-17: the preflight compares this bench with CI. Give it CI's workflow, a Frappe
		# checkout on CI's branch, and a Python and Node at CI's versions, so the preflight passes.
		shutil.copy2(SCRIPTS / "check_ci_parity.py", self.repo / "scripts" / "check_ci_parity.py")
		(self.repo / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
		shutil.copy2(REPO_ROOT / ".github/workflows/ci.yml", self.repo / ".github/workflows/ci.yml")
		self.frappe = self.bench / "apps" / "frappe"
		self.frappe.mkdir(parents=True)
		subprocess.run(["git", "init", "-q", "-b", "version-16"], cwd=self.frappe, check=True)
		self.write(self.bench / "env/bin/python", "#!/usr/bin/env bash\necho Python 3.14.0\n", 0o755)
		self.write(self.bin / "node", "#!/usr/bin/env bash\necho v24.0.0\n", 0o755)
		subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
		self.baseline = self.root / "baseline"
		semgrep = self.baseline / "semgrep-venv/bin/semgrep"
		self.write(semgrep, "#!/usr/bin/env bash\nexit 0\n", 0o755)
		(self.baseline / "semgrep-rules/rules").mkdir(parents=True)
		subprocess.run(
			["bash", "-c", f"echo select 1 | gzip > {self.baseline}/sellos_test_clean.sql.gz"], check=True
		)
		self.write(self.bin / "pre-commit", "#!/usr/bin/env bash\nexit 0\n", 0o755)
		# The first bench command after the preflight is the baseline restore. This bench fails it with 2.
		self.write(self.bin / "bench", "#!/usr/bin/env bash\necho fake bench failed >&2\nexit 2\n", 0o755)

	def run_gate(self):
		env = {
			**self.env(),
			"SELLOS_TEST_SITE": "sellos_test.localhost",
			"SELLOS_BASELINE_DIR": str(self.baseline),
		}
		# The gate refuses any site but sellos_test, so the fake server is reached by that name.
		site = self.bench / "sites" / "sellos_test.localhost"
		site.mkdir(parents=True, exist_ok=True)
		shutil.copy2(self.bench / "sites" / SITE / "site_config.json", site / "site_config.json")
		result = subprocess.run(
			["bash", str(self.repo / "scripts/run-tests.sh")],
			cwd=self.repo,
			capture_output=True,
			text=True,
			env=env,
			timeout=120,
		)
		self.out = result.stdout + result.stderr
		return result.returncode

	def resolves(self):
		probe = subprocess.run(
			[
				"curl",
				"-s",
				"-o",
				"/dev/null",
				"--max-time",
				"5",
				f"http://sellos_test.localhost:{self.port}/api/method/ping",
			]
		)
		if probe.returncode != 0:
			self.skipTest("sellos_test.localhost does not resolve to this machine here")

	def test_server_that_404s_sellos_makes_the_gate_exit_3(self):
		self.serve(404)
		self.resolves()
		self.assertEqual(self.run_gate(), 3, self.out)
		self.assertIn(f"The server on port {self.port} is not serving SellOS. Start it with:", self.out)
		self.assertNotIn("fake bench failed", self.out)

	def test_a_command_failing_with_2_comes_out_as_1(self):
		self.serve(302)
		self.resolves()
		self.assertEqual(self.run_gate(), 1, self.out)
		self.assertIn("fake bench failed", self.out)
		self.assertIn("Reporting it as a test failure (1)", self.out)

	def test_a_frappe_branch_ci_does_not_build_makes_the_gate_exit_3(self):
		self.serve(302)
		self.resolves()
		subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/develop"], cwd=self.frappe, check=True)
		self.assertEqual(self.run_gate(), 3, self.out)
		self.assertIn("CI installs Frappe version-16", self.out)
		self.assertNotIn("fake bench failed", self.out)

	def test_wrong_port_makes_the_gate_exit_2(self):
		self.serve(302)
		self.resolves()
		(self.bench / "sites" / SITE / "site_config.json").write_text(
			json.dumps({"webserver_port": 8000}), encoding="utf-8"
		)
		self.assertEqual(self.run_gate(), 2, self.out)
		self.assertIn("not " + str(self.port), self.out)


if __name__ == "__main__":
	unittest.main()
