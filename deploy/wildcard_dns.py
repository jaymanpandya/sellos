#!/usr/bin/env python3
"""SOS-P0-05: the wildcard DNS record and the wildcard certificate for SellOS.

Creates or updates the A record `*.sellos.interactivesoftwares.com` through the DigitalOcean DNS
API (a second run changes nothing), issues the wildcard certificate through the DNS challenge with
lego, and installs a systemd timer that renews it.

    SELLOS_DO_TOKEN=... deploy/wildcard_dns.py --ip 203.0.113.10 --email ops@example.com
    deploy/wildcard_dns.py --ip 203.0.113.10 --email ops@example.com --dry-run

The DigitalOcean token is read only from the environment variable SELLOS_DO_TOKEN. It is handed to
lego only through the child process's environment, and never printed, logged, put on a command
line or written to a file. The renewal service reads it from an environment file that the operator
creates by hand (default /etc/sellos/do-token.env, mode 0600, one line: SELLOS_DO_TOKEN=...).
SELLOS_DO_API_URL overrides the API address (the tests point it at a fake).

--dry-run prints every step and calls nothing: no API request, no command, no file written.
Running this on the real domain is SOS-P0-05D (AMP Labs), never the build loop's.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ZONE = "interactivesoftwares.com"
WILDCARD_LABEL = "*.sellos"
BASE_DOMAIN = f"sellos.{ZONE}"
WILDCARD_FQDN = f"*.{BASE_DOMAIN}"
DEFAULT_API = "https://api.digitalocean.com/v2"
DEFAULT_TTL = 300
TOKEN_VARIABLE = "SELLOS_DO_TOKEN"
DEFAULT_LEGO_PATH = "/var/lib/sellos/lego"
DEFAULT_SYSTEMD_DIR = "/etc/systemd/system"
DEFAULT_ENV_FILE = "/etc/sellos/do-token.env"
DEFAULT_RENEW_HOOK = "systemctl reload nginx"
TIMER_NAME = "sellos-cert-renew.timer"
SERVICE_NAME = "sellos-cert-renew.service"


class DeployError(Exception):
	"""A clear, token free message for the operator."""


def redact(text, token):
	return text.replace(token, "[token]") if token else text


class DigitalOcean:
	def __init__(self, base_url, token):
		self.base_url = base_url.rstrip("/")
		self.token = token

	def call(self, method, path, body=None):
		data = json.dumps(body).encode() if body is not None else None
		request = urllib.request.Request(self.base_url + path, data=data, method=method)
		request.add_header("Authorization", f"Bearer {self.token}")
		request.add_header("Content-Type", "application/json")
		try:
			with urllib.request.urlopen(request, timeout=30) as response:
				raw = response.read()
		except urllib.error.HTTPError as error:
			detail = redact(error.read().decode("utf-8", "replace")[:200], self.token)
			raise DeployError(f"DigitalOcean answered {error.code} to {method} {path}: {detail}") from None
		except (urllib.error.URLError, OSError) as error:
			raise DeployError(
				f"Could not reach DigitalOcean for {method} {path}: {error.__class__.__name__}"
			) from None
		return json.loads(raw) if raw else {}


def ensure_record(api, ip, ttl, say):
	"""Create or update the wildcard A record. Returns 'created', 'updated' or 'unchanged'."""
	path = f"/domains/{ZONE}/records"
	listing = api.call("GET", f"{path}?type=A&name={WILDCARD_FQDN.replace('*', '%2A')}")
	records = [
		r
		for r in listing.get("domain_records", [])
		if r.get("type") == "A" and r.get("name") == WILDCARD_LABEL
	]
	wanted = {"type": "A", "name": WILDCARD_LABEL, "data": ip, "ttl": ttl}
	if not records:
		api.call("POST", path, wanted)
		say(f"Created {WILDCARD_FQDN} A {ip}.")
		return "created"
	if len(records) > 1:
		raise DeployError(
			f"{len(records)} records already exist for {WILDCARD_FQDN}; remove the extras by hand."
		)
	current = records[0]
	if current.get("data") == ip and current.get("ttl") == ttl:
		say(f"{WILDCARD_FQDN} already points to {ip}. Nothing changed.")
		return "unchanged"
	api.call("PUT", f"{path}/{current['id']}", wanted)
	say(f"Updated {WILDCARD_FQDN} to {ip}.")
	return "updated"


def lego_base(options):
	return [
		"lego",
		"--accept-tos",
		"--email",
		options.email,
		"--dns",
		"digitalocean",
		"--domains",
		BASE_DOMAIN,
		"--domains",
		WILDCARD_FQDN,
		"--path",
		options.lego_path,
	]


def unit_files(options):
	renew = " ".join(lego_base(options)) + f" renew --days 30 --renew-hook '{options.renew_hook}'"
	service = (
		"[Unit]\n"
		"Description=Renew the SellOS wildcard certificate\n\n"
		"[Service]\n"
		"Type=oneshot\n"
		f"EnvironmentFile={options.env_file}\n"
		f"ExecStart=/bin/sh -c 'DO_AUTH_TOKEN=\"${TOKEN_VARIABLE}\" exec {renew}'\n"
	)
	timer = (
		"[Unit]\n"
		"Description=Check twice a day whether the SellOS wildcard certificate needs renewing\n\n"
		"[Timer]\n"
		"OnCalendar=*-*-* 03,15:00:00\n"
		"RandomizedDelaySec=1h\n"
		"Persistent=true\n\n"
		"[Install]\n"
		"WantedBy=timers.target\n"
	)
	folder = Path(options.systemd_dir)
	return {folder / SERVICE_NAME: service, folder / TIMER_NAME: timer}


def default_runner(argv, env):
	subprocess.run(argv, env=env, check=True)  # the token only ever travels in env


def ensure_certificate(options, token, runner, say):
	certificate = Path(options.lego_path) / "certificates" / f"_.{BASE_DOMAIN}.crt"
	if certificate.exists():
		say(f"Certificate already issued ({certificate}). Renewal is the timer's job.")
	else:
		if not options.skip_tool_check and shutil.which("lego") is None:
			raise DeployError(
				"lego is not installed. Install it (https://go-acme.github.io/lego/) and run again."
			)
		say(f"Issuing the wildcard certificate for {BASE_DOMAIN} and {WILDCARD_FQDN} by the DNS challenge.")
		runner([*lego_base(options), "run"], {**os.environ, "DO_AUTH_TOKEN": token})
	changed = False
	for path, content in unit_files(options).items():
		if path.exists() and path.read_text(encoding="utf-8") == content:
			continue
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(content, encoding="utf-8")
		say(f"Wrote {path}.")
		changed = True
	if changed:
		runner(["systemctl", "daemon-reload"], dict(os.environ))
		runner(["systemctl", "enable", "--now", TIMER_NAME], dict(os.environ))
		say(f"Renewal timer {TIMER_NAME} is enabled.")
	else:
		say(f"Renewal timer {TIMER_NAME} is already installed.")


def dry_run(options, say):
	say("Dry run: no request, no command, no file.")
	say(f"1. Read the token from {TOKEN_VARIABLE} (not needed for a dry run).")
	say(f"2. GET {options.api_url}/domains/{ZONE}/records?type=A&name={WILDCARD_FQDN}")
	say(f"3. POST (or PUT when it differs) the A record {WILDCARD_FQDN} -> {options.ip}, ttl {options.ttl}.")
	say(f"4. Run: {' '.join(lego_base(options))} run  (token in the child environment as DO_AUTH_TOKEN)")
	for path in unit_files(options):
		say(f"5. Write {path}")
	say(f"6. Run: systemctl daemon-reload, then systemctl enable --now {TIMER_NAME}")
	say(
		f"The renewal service reads {TOKEN_VARIABLE} from {options.env_file}, which you create by hand (0600)."
	)


def parse(argv, env):
	parser = argparse.ArgumentParser(
		description="Wildcard DNS record and certificate for SellOS (SOS-P0-05)."
	)
	parser.add_argument(
		"--ip", default=env.get("SELLOS_SERVER_IP"), help="the server's IPv4 (or SELLOS_SERVER_IP)"
	)
	parser.add_argument(
		"--email", default=env.get("SELLOS_ACME_EMAIL"), help="ACME account email (or SELLOS_ACME_EMAIL)"
	)
	parser.add_argument("--ttl", type=int, default=DEFAULT_TTL)
	parser.add_argument("--api-url", default=env.get("SELLOS_DO_API_URL", DEFAULT_API))
	parser.add_argument("--lego-path", default=DEFAULT_LEGO_PATH)
	parser.add_argument("--systemd-dir", default=DEFAULT_SYSTEMD_DIR)
	parser.add_argument("--env-file", default=DEFAULT_ENV_FILE)
	parser.add_argument("--renew-hook", default=DEFAULT_RENEW_HOOK)
	parser.add_argument("--skip-tool-check", action="store_true", help=argparse.SUPPRESS)
	parser.add_argument("--dry-run", action="store_true", help="print every step, call nothing")
	return parser.parse_args(argv)


def run(argv, env, out, runner=default_runner):
	"""The whole script. Returns the exit code; every message goes through `out`."""
	token = env.get(TOKEN_VARIABLE, "")

	def say(text):
		out(redact(text, token))

	try:
		options = parse(argv, env)
		if not options.ip:
			raise DeployError("Give the server's IPv4 with --ip or SELLOS_SERVER_IP.")
		if not options.email:
			raise DeployError("Give the ACME account email with --email or SELLOS_ACME_EMAIL.")
		if options.dry_run:
			dry_run(options, say)
			return 0
		if not token:
			raise DeployError(
				f"{TOKEN_VARIABLE} is not set. Export the DigitalOcean token in {TOKEN_VARIABLE}."
			)
		ensure_record(DigitalOcean(options.api_url, token), options.ip, options.ttl, say)
		ensure_certificate(options, token, runner, say)
	except DeployError as error:
		say(f"Error: {error}")
		return 1
	except subprocess.CalledProcessError as error:
		say(f"Error: the command {error.cmd[0]} failed with exit code {error.returncode}.")
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(run(sys.argv[1:], dict(os.environ), print))
