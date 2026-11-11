"""SOS-SETUP-19: how scripts/lib/tasks.py picks the next task (Jayman's decisions of 10 November 2026).

* A Not Needed dependency counts as satisfied, and a Not Needed task is never picked or reported.
* The loop chooses by Launch tier first (Dec 20 before Jan 1), then dependencies, then file order.
  Priority no longer orders.
* The real TASKS.md: every task has a Launch line, only SOS-REG-L depends on a SOS-REG task, and the
  Status values line names Not Needed.
"""

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_FILE = REPO_ROOT / "TASKS.md"
_spec = importlib.util.spec_from_file_location(
	"sellos_loop_tasks", REPO_ROOT / "scripts" / "lib" / "tasks.py"
)
tasks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tasks)


def block(task_id, status="Not Started", deps="none", launch="Dec 20", priority="P0", owner="Claude Code"):
	lines = [f"### {task_id}: a task", f"- **Owner:** {owner}", f"- **Priority:** {priority}"]
	if launch is not None:
		lines.append(f"- **Launch:** {launch}")
	lines += [f"- **Dependencies:** {deps}", f"- **Status:** {status}", ""]
	return "\n".join(lines)


def parse(*blocks):
	with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
		f.write("# Tasks\n\n" + "\n".join(blocks))
	try:
		return tasks.parse(f.name)
	finally:
		Path(f.name).unlink()


class NotNeeded(unittest.TestCase):
	def test_a_not_needed_dependency_counts_as_satisfied(self):
		parsed = parse(block("SOS-N09", status="Not Needed"), block("SOS-P2-01", deps="SOS-N09"))
		self.assertEqual(tasks.select_next(parsed), "SOS-P2-01")

	def test_a_waiting_dependency_is_still_unmet(self):
		parsed = parse(block("SOS-N12", status="Waiting"), block("SOS-P3-01", deps="SOS-N12"))
		self.assertEqual(tasks.select_next(parsed), "NONE_ELIGIBLE")

	def test_a_not_needed_task_is_never_picked(self):
		parsed = parse(block("SOS-P2-12", status="Not Needed"))
		self.assertEqual(tasks.select_next(parsed), "NONE_ELIGIBLE")
		self.assertEqual(tasks.pick_order(parsed), [])

	def test_a_not_needed_task_is_never_reported(self):
		parsed = parse(
			block("SOS-N10", status="Not Needed", deps="SOS-N09"),
			block("SOS-N09", status="Not Needed"),
			block("SOS-N12", status="Waiting", deps="SOS-N11", owner="Jayman"),
			block("SOS-N11", status="Not Needed"),
			block("SOS-P3-01", deps="SOS-N10, SOS-N12"),
		)
		report = "\n".join(tasks.waiting_report(parsed))
		self.assertIn("SOS-N12 waits on its owner, Jayman; holds up SOS-P3-01", report)
		for task_id in ("SOS-N09", "SOS-N10", "SOS-N11"):
			self.assertNotIn(task_id, report)
		self.assertEqual(tasks.select_next(parsed), "NONE_ELIGIBLE")

	def test_a_not_needed_task_is_not_in_the_blocked_list(self):
		parsed = parse(block("SOS-P2-12", status="Not Needed"), block("SOS-P2-03", status="Blocked"))
		self.assertEqual(tasks.select_next(parsed), "BLOCKED_EXISTS:SOS-P2-03")


class TierThenDependenciesThenFileOrder(unittest.TestCase):
	def test_dec_20_is_picked_before_an_earlier_jan_1_task(self):
		parsed = parse(block("SOS-P1-14", launch="Jan 1", priority="P1"), block("SOS-P5-07", priority="P5"))
		self.assertEqual(tasks.select_next(parsed), "SOS-P5-07")

	def test_priority_does_not_order_within_a_tier(self):
		parsed = parse(block("SOS-P2-01", priority="P2"), block("SOS-P0-01", priority="P0"))
		self.assertEqual(tasks.select_next(parsed), "SOS-P2-01")

	def test_an_earlier_tier_task_with_unmet_dependencies_is_passed_over(self):
		parsed = parse(
			block("SOS-N21", status="Waiting", owner="Jayman"),
			block("SOS-P5-07", deps="SOS-N21"),
			block("SOS-P3-01", launch="Jan 1"),
		)
		self.assertEqual(tasks.select_next(parsed), "SOS-P3-01")

	def test_a_task_with_no_launch_line_comes_after_every_tier(self):
		parsed = parse(block("SOS-X-1", launch=None), block("SOS-X-2", launch="Jan 1"))
		self.assertEqual(tasks.select_next(parsed), "SOS-X-2")

	def test_in_progress_is_resumed_first(self):
		parsed = parse(block("SOS-X-1"), block("SOS-X-2", launch="Jan 1", status="In Progress"))
		self.assertEqual(tasks.select_next(parsed), "SOS-X-2")

	def test_pick_order_follows_tier_then_dependencies_then_file_order(self):
		parsed = parse(
			block("SOS-A", launch="Jan 1"),
			block("SOS-B", deps="SOS-C"),
			block("SOS-C"),
			block("SOS-D", deps="SOS-A"),
			block("SOS-E", status="Waiting"),
			block("SOS-F", deps="SOS-E"),
		)
		self.assertEqual(tasks.pick_order(parsed), ["SOS-C", "SOS-B", "SOS-A", "SOS-D"])
		self.assertEqual(tasks.pick_order(parsed, 2), ["SOS-C", "SOS-B"])


class RealTasksFile(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.tasks = tasks.parse(str(TASKS_FILE))
		cls.by_id = {t["id"]: t for t in cls.tasks}
		cls.text = TASKS_FILE.read_text(encoding="utf-8")

	def test_every_task_has_a_launch_line(self):
		missing = [t["id"] for t in self.tasks if not t["launch"]]
		self.assertEqual(missing, [])
		self.assertEqual([t["id"] for t in self.tasks if "after" in t["launch"].lower()], [])

	def test_every_active_task_is_in_a_tier(self):
		for t in self.tasks:
			if t["status"] in ("Not Needed", "Parked"):
				continue
			self.assertIn(tasks.launch_rank(t["launch"]), (0, 1), t["id"])

	def test_only_reg_l_depends_on_a_regression_task(self):
		for t in self.tasks:
			if t["id"] == "SOS-REG-L":
				continue
			self.assertEqual([d for d in t["deps"] if d.startswith("SOS-REG")], [], t["id"])

	def test_reg_l_depends_on_every_other_active_task(self):
		active = {t["id"] for t in self.tasks if t["status"] not in ("Not Needed", "Parked")}
		self.assertEqual(set(self.by_id["SOS-REG-L"]["deps"]), active - {"SOS-REG-L"})

	def test_every_dependency_names_a_task(self):
		for t in self.tasks:
			for d in t["deps"]:
				self.assertIn(d, self.by_id, f"{t['id']} depends on unknown {d}")

	def test_the_voice_pilot_chain(self):
		self.assertEqual(set(self.by_id["SOS-P5-07"]["deps"]), {"SOS-P2-03", "SOS-P2-04", "SOS-N21"})
		self.assertEqual(self.by_id["SOS-P5-08"]["deps"], ["SOS-P5-07", "SOS-P2-14"])
		self.assertEqual(self.by_id["SOS-P5-09"]["deps"], ["SOS-P5-08"])

	def test_the_hinglish_bakeoff_blocks_the_voice_choice(self):
		"""SOS-SETUP-30: SOS-N21 is chosen from SOS-N21A's bake-off on our own Hinglish audio."""
		n21, n21a = self.by_id["SOS-N21"], self.by_id["SOS-N21A"]
		self.assertEqual(n21["deps"], ["SOS-N21A"])
		self.assertEqual(n21["status"], "Waiting")
		self.assertEqual(n21a["deps"], [])
		self.assertEqual(n21a["launch"], "Dec 20")
		self.assertIn("SOS-N21A", self.by_id["SOS-REG-L"]["deps"])
		block = self.text.split("### SOS-N21A:", 1)[1].split("\n### ", 1)[0]
		for i in range(1, 21):
			self.assertIn(f"`{i:02d}.wav`", block)
		for name in ("sellos_sarvam_key", "sellos_deepgram_key", "sellos_elevenlabs_key", "get_secret(name)"):
			self.assertIn(name, block)
		self.assertIn("docs/bakeoff/results.md", self.text.split("### SOS-N21:", 1)[1].split("\n### ", 1)[0])

	def test_the_status_values_line_names_not_needed(self):
		line = next(x for x in self.text.splitlines() if x.startswith("* Status values:"))
		self.assertIn("Not Needed", line)

	def test_the_status_of_every_task_is_a_known_value(self):
		known = {"Not Started", "In Progress", "Complete", "Blocked", "Waiting", "Parked", "Not Needed"}
		for t in self.tasks:
			self.assertIn(t["status"], known, t["id"])

	def test_no_task_id_repeats(self):
		ids = re.findall(r"^### ([A-Za-z0-9_-]+):", self.text, flags=re.M)
		self.assertEqual(len(ids), len(set(ids)))
