"""SOS-SETUP-39: a secret in an interactive session's transcript is an environment fault.

The real scripts/lib/transcript_leak.sh and scripts/notify-telegram.sh run against a fake interactive
transcript ("entrypoint":"cli") and a fake loop transcript ("entrypoint":"sdk-cli"), with a fake curl
that records what would go to Telegram.

Interactive: the value is overwritten in place with "*" (same length, same size), exit 3 is recorded
through sellos_env_exit, and Telegram gets the file and variable name, never the value.
Loop agent: the transcript is untouched and the check fails with 1 (an ordinary leak).
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
SECRET = "424242424242"
FAKE_CURL = '#!/usr/bin/env bash\nprintf "%s\\n" "$*" >>"$FAKE_DIR/curl_args"\necho \'{"ok":true,"result":{"message_id":7}}\'\n'


class TestTranscriptSecretFault(unittest.TestCase):
	def run_check(self, entrypoint):
		tmp = Path(tempfile.mkdtemp())
		tr, fake = tmp / "transcripts", tmp / "fake"
		tr.mkdir()
		fake.mkdir()
		curl = fake / "curl"
		curl.write_text(FAKE_CURL)
		curl.chmod(0o755)
		line = f'{{"entrypoint":"{entrypoint}","text":"chat {SECRET} end"}}\n'
		f = tr / "session.jsonl"
		f.write_text(line)
		env = {
			**os.environ,
			"PATH": f"{fake}:{os.environ['PATH']}",
			"FAKE_DIR": str(fake),
			"SELLOS_TELEGRAM_CHAT_ID": SECRET,
			"SELLOS_TELEGRAM_BOT_TOKEN": "123456:" + "A" * 30,
			"SELLOS_ENV_EXIT_FILE": str(tmp / "env-exit"),
		}
		script = f'source "{SCRIPTS}/lib/sellos_server.sh"; source "{SCRIPTS}/lib/transcript_leak.sh"; sellos_transcript_leak_check 0 "{tr}"'
		r = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
		exit_file = tmp / "env-exit"
		curl_args = (fake / "curl_args").read_text() if (fake / "curl_args").exists() else ""
		return r, f, line, exit_file, curl_args

	def test_interactive_transcript_is_scrubbed_reported_and_exit_3(self):
		r, f, line, exit_file, curl_args = self.run_check("cli")
		self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
		self.assertEqual(exit_file.read_text().strip(), "3")
		self.assertEqual(f.read_text(), line.replace(SECRET, "*" * len(SECRET)))
		self.assertEqual(len(f.read_text()), len(line))
		self.assertIn("session.jsonl", curl_args)
		self.assertIn("SELLOS_TELEGRAM_CHAT_ID", curl_args)
		self.assertIn("Not a task failure", curl_args)
		self.assertNotIn(SECRET, r.stdout + r.stderr + curl_args.replace(f"chat_id={SECRET}", ""))
		self.assertIn("sent to Telegram (message_id 7)", r.stdout)

	def test_loop_agent_transcript_is_an_ordinary_leak(self):
		r, f, line, exit_file, curl_args = self.run_check("sdk-cli")
		self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
		self.assertFalse(exit_file.exists())
		self.assertEqual(f.read_text(), line)
		self.assertEqual(curl_args, "")


if __name__ == "__main__":
	unittest.main()
