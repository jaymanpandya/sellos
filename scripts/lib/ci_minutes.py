#!/usr/bin/env python3
"""Actions runner minutes for a job and for a push, and runs that never started (SOS-SETUP-28).

CI minutes are a budget (DEV_STRATEGY.md section 4, row 32). GitHub bills each job by its wall time,
rounded up to the next whole minute. This reads the jobs from the GitHub API through `gh api`, with
GH_TOKEN set to the workflow's token (permissions: actions: read).

  ci_minutes.py job <job name>    in a job's last step: "<name>: N runner minutes" to the job summary
  ci_minutes.py push              in the last job: "runner minutes for this push: N" to the summary,
                                  over every workflow run on this commit (CI and Linters)
  ci_minutes.py never-started <run id>
                                  for the build loop: the jobs of a red run that failed before any
                                  step ran, which is what a spent Actions budget or a billing
                                  problem looks like. Prints nothing when there are none.

`job` and `push` never fail the workflow: when the API cannot be read they say so in the summary and
exit 0, so counting minutes cannot turn a green run red.
"""

import json
import math
import os
import subprocess
import sys
from datetime import UTC, datetime


def parse_time(value):
	return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def job_minutes(job, now):
	"""Billed minutes for one job: its wall time rounded up, 0 if it never started."""
	started = parse_time(job.get("started_at"))
	if not started or job.get("conclusion") == "skipped":
		return 0
	ended = parse_time(job.get("completed_at")) if job.get("status") == "completed" else None
	seconds = max(((ended or now) - started).total_seconds(), 0)
	return max(1, math.ceil(seconds / 60))


def total_minutes(jobs, now):
	return sum(job_minutes(j, now) for j in jobs)


def never_started(jobs):
	"""Names of jobs that failed without running a single step."""
	return [
		j["name"]
		for j in jobs
		if j.get("conclusion") in ("failure", "startup_failure") and not j.get("steps")
	]


def gh_api(path):
	result = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
	if result.returncode != 0:
		raise RuntimeError(f"gh api {path} failed: {result.stderr.strip()}")
	return json.loads(result.stdout)


def run_jobs(repo, run_id):
	"""Every job of a run, every attempt included (each attempt is billed)."""
	return gh_api(f"repos/{repo}/actions/runs/{run_id}/jobs?filter=all&per_page=100")["jobs"]


def push_jobs(repo, sha):
	runs = gh_api(f"repos/{repo}/actions/runs?head_sha={sha}&per_page=100")["workflow_runs"]
	return [job for run in runs for job in run_jobs(repo, run["id"])]


def summary(lines):
	text = "\n".join(lines) + "\n"
	print(text, end="")
	path = os.environ.get("GITHUB_STEP_SUMMARY")
	if path:
		with open(path, "a", encoding="utf-8") as f:
			f.write(text)


def main(argv, now=None):
	now = now or datetime.now(UTC)
	repo = os.environ.get("GITHUB_REPOSITORY", "")
	if len(argv) == 2 and argv[0] == "never-started":
		repo = repo or gh_api("repos/{owner}/{repo}")["full_name"]
		names = never_started(run_jobs(repo, argv[1]))
		if names:
			print(", ".join(names))
		return 0
	if len(argv) == 2 and argv[0] == "job":
		try:
			jobs = run_jobs(repo, os.environ["GITHUB_RUN_ID"])
			attempt = int(os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
			mine = [j for j in jobs if j["name"] == argv[1] and j.get("run_attempt", 1) == attempt]
			minutes = total_minutes(mine, now)
		except (RuntimeError, KeyError, ValueError) as e:
			summary([f"{argv[1]}: runner minutes could not be read ({e})."])
			return 0
		summary([f"**{argv[1]}: {minutes} runner minutes** (wall time rounded up, as GitHub bills it)."])
		return 0
	if argv == ["push"]:
		try:
			jobs = push_jobs(repo, os.environ["GITHUB_SHA"])
		except (RuntimeError, KeyError, ValueError) as e:
			summary([f"runner minutes for this push could not be read ({e})."])
			return 0
		lines = [f"runner minutes for this push: {total_minutes(jobs, now)}", ""]
		lines += ["| Job | Runner minutes |", "| --- | --- |"]
		lines += [f"| {j['name']} | {job_minutes(j, now)} |" for j in jobs if job_minutes(j, now)]
		summary(lines)
		return 0
	print(__doc__, file=sys.stderr)
	return 2


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
