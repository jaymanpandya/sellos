"""Deploy a tagged release, promote it, and upgrade company sites one by one (SOS-P0-08).

    python -m sellos.provisioning.deploy deploy <tag> [--dry-run]     # to staging
    python -m sellos.provisioning.deploy promote <tag> [--dry-run]    # to production
    python -m sellos.provisioning.deploy upgrade [--dry-run] [--backup] [--site SITE ...]

deploy and promote build a list of steps for one environment. With --dry-run they print every step on a
line that starts with "+ " and reach no server. Without it they run the steps over ssh, in order, and
stop at the first one that fails. The hosts come from SELLOS_STAGING_HOST and SELLOS_PRODUCTION_HOST
(never from a repository), the bench folder on them from SELLOS_REMOTE_BENCH_DIR.

The rolling upgrade is the last step of both. It migrates the sites one at a time, in the order given.
It stops at the first site whose migration fails, names that site, and leaves every site after it
untouched (not backed up, not migrated, not put in maintenance mode). Rollback is in docs/DEPLOYMENT.md.

Exit codes: 0 done, 1 a step or a site failed, 2 a bad tag, option or site name.
"""

import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sellos.provisioning import tenant_sites

TAG_RE = re.compile(r"v\d+\.\d+\.\d+(-[a-z0-9][a-z0-9.]*)?")
HOST_RE = re.compile(r"([a-z0-9_.-]+@)?[a-z0-9][a-z0-9.-]*")
SITE_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*")
ENVIRONMENTS = {"staging": "SELLOS_STAGING_HOST", "production": "SELLOS_PRODUCTION_HOST"}
REMOTE_BENCH_ENV = "SELLOS_REMOTE_BENCH_DIR"
DEFAULT_REMOTE_BENCH = "~/sellos-bench"
SHARED_BENCH = "iespl-bench"  # the development bench: only tenant test sites may be upgraded there


class DeployError(ValueError):
	pass


@dataclass
class Step:
	title: str
	command: str  # run on the server, through ssh
	on: str = ""  # the environment whose server runs it, when not the one being released to


def check_tag(tag):
	if not isinstance(tag, str) or not TAG_RE.fullmatch(tag):
		raise DeployError(f"A release tag looks like v1.2.3 (or v1.2.3-rc1), not {tag!r}.")
	return tag


def remote_bench():
	value = os.environ.get(REMOTE_BENCH_ENV, DEFAULT_REMOTE_BENCH)
	if not re.fullmatch(r"[A-Za-z0-9_./~-]+", value):
		raise DeployError(f"{REMOTE_BENCH_ENV} is not a plain folder path.")
	return value


def host_for(environment, dry_run):
	"""The ssh host of an environment. A dry run never reads it: it prints a placeholder."""
	if environment not in ENVIRONMENTS:
		raise DeployError(f"The environment is staging or production, not {environment!r}.")
	if dry_run:
		return f"<{environment}-host>"
	variable = ENVIRONMENTS[environment]
	host = os.environ.get(variable, "")
	if not HOST_RE.fullmatch(host):
		raise DeployError(f"Set {variable} to the {environment} server (user@host) before a real run.")
	return host


def plan(environment, tag):
	"""The steps that put `tag` on one environment, the last one being the rolling upgrade."""
	check_tag(tag)
	bench = remote_bench()
	app = f"{bench}/apps/sellos"
	steps = []
	if environment == "production":
		steps.append(
			Step(
				"Check the tag is already on staging",
				f'test "$(git -C {app} describe --tags --exact-match)" = {shlex.quote(tag)}',
				on="staging",
			)
		)
	steps += [
		Step("Record the tag now deployed, for rollback", f"git -C {app} describe --tags --always"),
		Step("Fetch the release tags", f"git -C {app} fetch --tags --force origin"),
		Step(f"Check out {tag}", f"git -C {app} checkout --detach {shlex.quote(tag)}"),
		Step("Install the app's requirements", f"cd {bench} && ./env/bin/pip install -e apps/sellos"),
		Step("Build the web app and assets", f"cd {bench} && bench build --app sellos"),
		Step(
			"Rolling upgrade: back up and migrate each site, one at a time, stop at the first failure",
			f"cd {bench} && ./env/bin/python -m sellos.provisioning.deploy upgrade --backup --all-sites",
		),
		Step("Restart the web and worker processes", f"cd {bench} && bench restart"),
	]
	return steps


def ssh_argv(host, step):
	return ["ssh", "-o", "BatchMode=yes", host, step.command]


def show(environment, tag, host, steps, dry_run, out=print):
	out(f"{'Dry run: ' if dry_run else ''}release {tag} to {environment} ({host})")
	for number, step in enumerate(steps, 1):
		target = host_for(step.on, dry_run) if step.on else host
		out(f"{number}. {step.title}" + (f" (on {step.on})" if step.on else ""))
		out("+ " + shlex.join(ssh_argv(target, step)))


def release(environment, tag, dry_run=False, out=print, runner=None):
	"""Print the steps (dry run) or run them over ssh. Returns 0, or 1 at the first failed step.

	A dry run prints the steps for staging and for production and reaches no server. A real run does
	only `environment`'s, and stops at the first step that fails.
	"""
	if environment not in ENVIRONMENTS:
		raise DeployError(f"The environment is staging or production, not {environment!r}.")
	if dry_run:
		show(environment, tag, host_for(environment, True), plan(environment, tag), True, out)
		other = "production" if environment == "staging" else "staging"
		out(f"Not run by this command, for reference: the {other} steps.")
		show(other, tag, host_for(other, True), plan(other, tag), True, out)
		return 0
	steps = plan(environment, tag)
	host = host_for(environment, False)
	show(environment, tag, host, steps, False, out)
	runner = runner or _ssh
	for number, step in enumerate(steps, 1):
		target = host_for(step.on, False) if step.on else host
		if runner(target, step) != 0:
			out(
				f"Step {number} failed: {step.title}. Nothing after it ran. See docs/DEPLOYMENT.md, Rollback."
			)
			return 1
	return 0


def _ssh(host, step):
	return subprocess.run(ssh_argv(host, step), check=False).returncode


# The rolling upgrade


@dataclass
class UpgradeResult:
	migrated: list = field(default_factory=list)
	failed: str | None = None
	reason: str = ""
	untouched: list = field(default_factory=list)

	@property
	def ok(self):
		return self.failed is None


def check_site_name(site):
	if not isinstance(site, str) or not SITE_RE.fullmatch(site):
		raise DeployError(f"{site!r} is not a site name.")
	return site


def _frappe(site, *args):
	"""Run one Frappe site command (python -m frappe.utils.bench_helper frappe --site <site> ...)."""
	bench = tenant_sites.bench_dir()
	if bench.name == SHARED_BENCH and not re.fullmatch(rf"{tenant_sites.PREFIX}[a-z0-9]+\.localhost", site):
		raise DeployError(f"Refusing {site}: only tenant test sites are upgraded on the shared bench.")
	command = [str(bench / "env" / "bin" / "python"), "-m", "frappe.utils.bench_helper", "frappe"]
	command += ["--site", site, *args]
	try:
		result = subprocess.run(
			command, cwd=bench / "sites", capture_output=True, text=True, check=False, timeout=1800
		)
	except (OSError, subprocess.TimeoutExpired) as e:
		return f"{args[0]} could not run on {site}: {type(e).__name__}"
	if result.returncode != 0:
		tail = (result.stdout + result.stderr).strip().splitlines()[-3:]
		return f"{args[0]} exited with code {result.returncode}: " + " | ".join(tail)
	return None


def migrate_site(site, backup=False):
	"""Back up (if asked) and migrate one site. Returns None, or the reason it failed."""
	if backup:
		error = _frappe(site, "backup")
		if error:
			return error
	return _frappe(site, "migrate")


def default_sites():
	"""Every site folder of the bench that has a site_config.json, sorted (the control site included)."""
	sites = tenant_sites.bench_dir() / "sites"
	return sorted(p.name for p in sites.iterdir() if (p / "site_config.json").is_file())


def rolling_upgrade(sites, migrate=migrate_site, backup=False, out=print):
	"""Migrate `sites` one at a time. Stops at the first failure and leaves the rest untouched."""
	sites = [check_site_name(s) for s in sites]
	if len(set(sites)) != len(sites):
		raise DeployError("A site is listed twice.")
	result = UpgradeResult()
	for index, site in enumerate(sites):
		out(f"Migrating {site} ({index + 1} of {len(sites)})")
		error = migrate(site, backup=backup)
		if error:
			result.failed, result.reason = site, error
			result.untouched = sites[index + 1 :]
			out(f"FAILED {site}: {error}")
			out(
				f"Stopped. Untouched: {', '.join(result.untouched) or 'none'}. See docs/DEPLOYMENT.md, Rollback."
			)
			return result
		result.migrated.append(site)
		out(f"Migrated {site}")
	out(f"Upgraded {len(result.migrated)} sites.")
	return result


USAGE = (
	"usage: deploy deploy <tag> [--dry-run] | promote <tag> [--dry-run] | "
	"upgrade [--dry-run] [--backup] (--all-sites | --site SITE ...)"
)


def main(argv=None):
	argv = list(sys.argv[1:] if argv is None else argv)
	if not argv or argv[0] not in ("deploy", "promote", "upgrade"):
		print(USAGE, file=sys.stderr)
		return 2
	command, rest = argv[0], argv[1:]
	dry_run = "--dry-run" in rest
	rest = [a for a in rest if a != "--dry-run"]
	try:
		if command in ("deploy", "promote"):
			if len(rest) != 1 or rest[0].startswith("-"):
				print(USAGE, file=sys.stderr)
				return 2
			return release("staging" if command == "deploy" else "production", rest[0], dry_run)
		backup = "--backup" in rest
		rest = [a for a in rest if a != "--backup"]
		sites, all_sites = [], False
		while rest:
			arg = rest.pop(0)
			if arg == "--all-sites":
				all_sites = True
			elif arg == "--site" and rest:
				sites.append(rest.pop(0))
			else:
				print(USAGE, file=sys.stderr)
				return 2
		if all_sites == bool(sites):
			print(USAGE, file=sys.stderr)
			return 2
		sites = default_sites() if all_sites else sites
		if dry_run:
			for site in [check_site_name(s) for s in sites]:
				print(f"Would {'back up and ' if backup else ''}migrate {site}")
			return 0
		return 0 if rolling_upgrade(sites, backup=backup).ok else 1
	except DeployError as e:
		print(str(e), file=sys.stderr)
		return 2


if __name__ == "__main__":
	sys.exit(main())
