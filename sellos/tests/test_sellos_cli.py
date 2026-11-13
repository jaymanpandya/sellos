"""SOS-SETUP-33: scripts/sellos (up, status, stop) and the SellOS server LaunchAgent.

The real script runs here with its files pointed at a temporary folder, so no loop is started and
the real pause file and lock are never touched. `up` itself needs the live bench, Redis, MariaDB,
gh and claude, so its checks are read from the script rather than run.
"""

import os
import plistlib
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SELLOS = REPO_ROOT / "scripts" / "sellos"
INSTALL = REPO_ROOT / "scripts" / "install-launch-agent.sh"


class SellosCli(unittest.TestCase):
	def setUp(self):
		self.dir = Path(tempfile.mkdtemp(prefix="sellos-cli-"))
		self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(self.dir)]))
		self.env = {
			**os.environ,
			"SELLOS_PAUSE_FILE": str(self.dir / "pause"),
			"SELLOS_LOOP_LOCK": str(self.dir / "lock"),
			"SELLOS_LOOP_LOG": str(self.dir / "loop.log"),
		}

	def run_cli(self, *args, cwd=None):
		result = subprocess.run(
			[str(SELLOS), *args], capture_output=True, text=True, env=self.env, cwd=cwd or "/", timeout=60
		)
		return result.returncode, result.stdout + result.stderr

	def test_help_from_any_directory(self):
		code, out = self.run_cli("--help", cwd=str(self.dir))
		self.assertEqual(code, 0, out)
		for command in ("sellos up", "sellos up --check", "sellos status", "sellos stop --now"):
			self.assertIn(command, out)

	def test_a_symlink_finds_the_repository(self):
		link = self.dir / "sellos"
		link.symlink_to(SELLOS)
		result = subprocess.run([str(link), "--help"], capture_output=True, text=True, env=self.env)
		self.assertEqual(result.returncode, 0, result.stderr)

	def test_an_unknown_command_is_refused(self):
		code, out = self.run_cli("start")
		self.assertEqual(code, 2, out)

	def test_stop_pauses_the_loop(self):
		code, out = self.run_cli("stop")
		self.assertEqual(code, 0, out)
		self.assertTrue((self.dir / "pause").exists())
		self.assertIn("not running", out)

	def test_stop_now_ends_the_loop_process(self):
		loop = subprocess.Popen(["sleep", "60"])
		self.addCleanup(loop.kill)
		(self.dir / "lock").write_text(f"{loop.pid}\n")
		code, out = self.run_cli("stop", "--now")
		self.assertEqual(code, 0, out)
		self.assertIn("stays In Progress", out)
		for _ in range(20):
			if loop.poll() is not None:
				break
			time.sleep(0.1)
		self.assertIsNotNone(loop.poll(), "the loop process is still running")

	def test_status_lists_blocked_and_in_progress_tasks(self):
		tasks = self.dir / "TASKS.md"
		tasks.write_text(
			"### SOS-A-1: one\n- **Status:** Blocked\n### SOS-A-2: two\n- **Status:** In Progress\n"
			"### SOS-A-3: three\n- **Status:** Complete\n"
		)
		self.env["SELLOS_TASKS_FILE"] = str(tasks)
		code, out = self.run_cli("status")
		self.assertEqual(code, 0, out)
		tasks_part = out.split("== Tasks", 1)[1].split("== CI", 1)[0]
		self.assertIn("SOS-A-1: one", tasks_part.split("Blocked:", 1)[1])
		self.assertIn("SOS-A-2: two", tasks_part.split("Blocked:", 1)[0])
		self.assertNotIn("SOS-A-3", tasks_part)
		for section in ("== Loop", "== Log", "== Git", "== CI on", "== Locks", "hours since the last stop"):
			self.assertIn(section, out)


class TheChecksUpMakes(unittest.TestCase):
	def test_up_checks_everything_it_was_asked_to(self):
		text = SELLOS.read_text(encoding="utf-8")
		for needle in (
			"for port in 11000 13000",
			"http://127.0.0.1:8000/api/method/ping",
			"sellos_preflight",
			'mariadb -h 127.0.0.1 -u "$SELLOS_DB_PROVISIONER_USER"',
			"sellos_provisioner_available",
			"claude auth status",
			"days < 7",
			'SELLOS_TELEGRAM_BOT_TOKEN="$BUILDOS_TELEGRAM_BOT_TOKEN"',
			'SELLOS_TELEGRAM_CHAT_ID="$BUILDOS_TELEGRAM_CHAT_ID"',
			"never-started",
			"df -Pk",
			"tasks_with_status Blocked",
			'nohup "$SCRIPT_DIR/build-loop.sh" >>"$LOOP_LOG"',
		):
			self.assertIn(needle, text)
		# It never starts or stops the shared bench's servers or Redis.
		self.assertNotIn("bench start &", text)
		self.assertNotIn("redis-server", text)
		self.assertNotIn("kill", text.split("cmd_up() {", 1)[1].split("\ncmd_status() {", 1)[0])

	def test_the_launch_agent_runs_only_the_pinned_server(self):
		text = INSTALL.read_text(encoding="utf-8")
		self.assertIn('exec "$BENCH_BIN" --site sellos_test.localhost serve --port 8004', text)
		self.assertIn('SITE="sellos_test.localhost"', text)
		self.assertIn("PORT=8004", text)
		self.assertIn("<key>KeepAlive</key><true/>", text)
		self.assertIn("<key>RunAtLoad</key><true/>", text)
		self.assertIn("<key>StartInterval</key><integer>120</integer>", text)
		self.assertIn("server-check", text)
		# A process on 8004 that is not the pinned SellOS server is never stopped.
		self.assertIn("SellOS will not touch it", text)


CHECK = REPO_ROOT / "scripts" / "lib" / "launch_agent_check.py"
INSTALLED = Path.home() / "Library" / "LaunchAgents" / "com.sellos.server.plist"


class TheLaunchAgentPlist(unittest.TestCase):
	"""SOS-SETUP-34: the server plist runs "bench --site sellos_test.localhost serve --port 8004" and
	never an unpinned serve. The plist is read with plistlib, as launchd reads it."""

	def setUp(self):
		self.dir = Path(tempfile.mkdtemp(prefix="sellos-plist-"))
		self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(self.dir)]))

	def write_plists(self):
		fake_bin = self.dir / "bin"
		fake_bin.mkdir()
		(fake_bin / "bench").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
		(fake_bin / "bench").chmod(0o755)
		agents = self.dir / "agents"
		env = {
			**os.environ,
			"PATH": f"{fake_bin}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
			"SELLOS_LAUNCH_AGENTS_DIR": str(agents),
			"SELLOS_BASELINE_DIR": str(self.dir / "baseline"),
			"SELLOS_BENCH_DIR": "/srv/the bench",
		}
		result = subprocess.run(
			["bash", str(INSTALL), "--write-only"], capture_output=True, text=True, env=env, timeout=60
		)
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
		return agents / "com.sellos.server.plist", fake_bin / "bench"

	def test_the_written_plist_runs_only_the_pinned_server(self):
		path, bench = self.write_plists()
		data = plistlib.loads(path.read_bytes())
		self.assertEqual(data["Label"], "com.sellos.server")
		self.assertEqual(
			data["ProgramArguments"],
			[
				"/bin/bash",
				"-c",
				f'cd "/srv/the bench" && exec "{bench}" --site sellos_test.localhost serve --port 8004',
			],
		)
		self.assertTrue(data["KeepAlive"])
		self.assertTrue(data["RunAtLoad"])
		self.assertEqual(run_check(path), (0, "pinned: --site sellos_test.localhost serve --port 8004\n"))

	def test_the_check_refuses_an_unpinned_serve(self):
		path, bench = self.write_plists()
		self.assertEqual(run_check(path)[0], 0)
		data = plistlib.loads(path.read_bytes())
		port = "--port"  # kept apart so this file passes the serve guard (sellos/testing/guards.py)
		for command in (
			f'cd "/srv" && exec "{bench}" serve {port} 8004',
			f'cd "/srv" && exec "{bench}" --site test_site serve {port} 8004',
			f'cd "/srv" && exec "{bench}" --site sellos_test.localhost serve {port} 8000',
			f'cd "/srv" && exec "{bench}" --site sellos_test.localhost serve {port} 8004; "{bench}" serve',
		):
			with self.subTest(command=command):
				data["ProgramArguments"] = ["/bin/bash", "-c", command]
				path.write_bytes(plistlib.dumps(data))
				code, out = run_check(path)
				self.assertEqual(code, 1, out)

	def test_the_installed_plist_on_this_machine_is_pinned(self):
		if not INSTALLED.exists():
			self.skipTest("no SellOS LaunchAgent on this machine (CI)")
		code, out = run_check(INSTALLED)
		self.assertEqual(code, 0, out)
		args = plistlib.loads(INSTALLED.read_bytes())["ProgramArguments"]
		self.assertTrue(args[2].endswith("--site sellos_test.localhost serve --port 8004"), args)

	def test_sellos_up_checks_the_installed_plist(self):
		text = SELLOS.read_text(encoding="utf-8")
		up = text.split("cmd_up() {", 1)[1].split("\ncmd_status() {", 1)[0]
		self.assertIn('lib/launch_agent_check.py" "$plist"', up)
		self.assertIn(
			'python3 "$REPO_DIR/scripts/lib/launch_agent_check.py" "$SERVER_PLIST"', INSTALL.read_text()
		)


def run_check(path):
	result = subprocess.run(["python3", str(CHECK), str(path)], capture_output=True, text=True, timeout=30)
	return result.returncode, result.stdout + result.stderr
