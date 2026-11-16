"""SOS-SETUP-17: scripts/notify-telegram.sh never stops the build loop.

The loop calls the notifier after every task. With no Telegram token it used to exit 1, which ended
the loop after its first completed task and lost the message. These run the real script.
SOS-SETUP-37: the message goes as plain text, cut below Telegram's limit, and the log says whether
Telegram took it.
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTIFY = REPO_ROOT / "scripts" / "notify-telegram.sh"


class TestNotifyTelegram(unittest.TestCase):
	def run_notify(self, extra_env, *args):
		env = {k: v for k, v in os.environ.items() if not k.startswith("SELLOS_TELEGRAM_")}
		env.update(extra_env)
		return subprocess.run(
			["bash", str(NOTIFY), *args], capture_output=True, text=True, env=env, timeout=60
		)

	def test_without_a_token_it_prints_the_message_and_exits_0(self):
		result = self.run_notify({}, "SellOS loop: SOS-X-1 complete.")
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("NOTIFY: SellOS loop: SOS-X-1 complete.", result.stdout)
		self.assertIn("not sent to Telegram", result.stderr)

	def test_a_failed_send_exits_0_and_never_prints_the_token(self):
		with tempfile.TemporaryDirectory() as fake_bin:
			curl = Path(fake_bin) / "curl"
			curl.write_text("#!/usr/bin/env bash\nexit 7\n", encoding="utf-8")
			curl.chmod(0o755)
			env = {
				"PATH": f"{fake_bin}:{os.environ.get('PATH', '/usr/bin:/bin')}",
				"SELLOS_TELEGRAM_BOT_TOKEN": "fake-token-value",
				"SELLOS_TELEGRAM_CHAT_ID": "1",
			}
			result = self.run_notify(env, "a message")
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("NOTIFY: a message", result.stdout)
		self.assertIn("the Telegram send failed", result.stderr)
		self.assertNotIn("fake-token-value", result.stdout + result.stderr)

	def send_with_fake_curl(self, curl_body, message):
		with tempfile.TemporaryDirectory() as fake_bin:
			curl = Path(fake_bin) / "curl"
			curl.write_text(
				'#!/usr/bin/env bash\nprintf \'%s\\0\' "$@" >"$(dirname "$0")/args"\n' + curl_body,
				encoding="utf-8",
			)
			curl.chmod(0o755)
			env = {
				"PATH": f"{fake_bin}:{os.environ.get('PATH', '/usr/bin:/bin')}",
				"SELLOS_TELEGRAM_BOT_TOKEN": "fake-token-value",
				"SELLOS_TELEGRAM_CHAT_ID": "1",
			}
			result = self.run_notify(env, message)
			args = (Path(fake_bin) / "args").read_text(encoding="utf-8")
		return result, args

	def test_a_message_telegram_accepts_is_logged_as_sent(self):
		# SOS-SETUP-37: the log says whether a notice arrived.
		result, args = self.send_with_fake_curl(
			'echo \'{"ok":true,"result":{"message_id":4321}}\'\n', "SellOS loop: SOS-X-1 complete."
		)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("NOTIFY: sent to Telegram (message_id 4321).", result.stdout)
		self.assertNotIn("parse_mode", args, "plain text: a < in a message must not make Telegram refuse it")

	def test_a_message_telegram_refuses_is_logged_with_its_reason(self):
		result, _ = self.send_with_fake_curl(
			'echo \'{"ok":false,"error_code":400,"description":"Bad Request: message is too long"}\'\n',
			"run scripts/set-task-status.sh <ID> Complete, then <li> was not found",
		)
		self.assertEqual(result.returncode, 0, result.stderr)
		self.assertIn("NOTIFY: Telegram refused the message: Bad Request: message is too long", result.stderr)
		self.assertNotIn("sent to Telegram", result.stdout)
		self.assertNotIn("fake-token-value", result.stdout + result.stderr)

	def test_a_long_message_is_cut_below_telegrams_limit(self):
		_, args = self.send_with_fake_curl('echo \'{"ok":true,"result":{"message_id":1}}\'\n', "x" * 9000)
		text = next(arg for arg in args.split("\0") if arg.startswith("text="))
		self.assertLessEqual(len(text) - len("text="), 4000)
		self.assertIn("(cut; the whole message is in the loop log)", text)

	def test_without_a_message_it_shows_the_usage(self):
		result = self.run_notify({})
		self.assertNotEqual(result.returncode, 0)
		self.assertIn("Usage", result.stderr)


if __name__ == "__main__":
	unittest.main()
