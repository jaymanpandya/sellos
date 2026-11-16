"""SOS-SETUP-38: no test pins the live status of a real task in TASKS.md.

The loop moves the real tasks between statuses (Not Started, In Progress, Complete, Blocked), so a test
that reads the real TASKS.md and asserts which status a task has goes red the moment the loop works
on it. CI run 43954312044 on 757df9c did exactly that: test_tasks_selection.py asserted SOS-P1-07 was
Not Started, the loop had marked it In Progress, and the loop stopped on ci-red (docs/STOPS.md, "test
pins a moving value"). A test on the real file may check that a status is one of the valid values,
never which one. A test that writes its own TASKS.md (a temporary repo) may assert anything.

The scan reads every test_*.py under sellos/ and scripts/. A file reads the real TASKS.md when it has
an expression such as REPO_ROOT / "TASKS.md" (a module level name, not self.repo or self.dir). In such
a file, an assert call fails the scan when one argument mentions a status (["status"], .status,
.get("status") or a "**Status:**" string) and another is a literal status value.
"""

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATUSES = {"Not Started", "In Progress", "Complete", "Blocked", "Waiting", "Parked", "Not Needed"}
FIX = (
	'Assert only that the status is valid, as in assertIn(task["status"], STATUSES) '
	"(sellos/tests/test_tasks_selection.py), or test the rule on a TASKS.md the test writes itself."
)


def _reads_real_tasks_file(tree):
	for node in ast.walk(tree):
		if (
			isinstance(node, ast.BinOp)
			and isinstance(node.op, ast.Div)
			and isinstance(node.right, ast.Constant)
			and node.right.value == "TASKS.md"
		):
			left = node.left
			if isinstance(left, ast.Name) and left.id.isupper():
				return True
			if "__file__" in ast.unparse(left):
				return True
	return False


def _mentions_status(node):
	for sub in ast.walk(node):
		if isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant):
			if sub.slice.value == "status":
				return True
		if isinstance(sub, ast.Attribute) and sub.attr == "status":
			return True
		if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "get":
			if sub.args and isinstance(sub.args[0], ast.Constant) and sub.args[0].value == "status":
				return True
	return False


def _status_literal(node):
	if isinstance(node, ast.Constant) and isinstance(node.value, str):
		return node.value.strip() in STATUSES
	return False


def _status_line_literal(node):
	"""A string such as "**Status:** In Progress", asserted against the real file's text."""
	if isinstance(node, ast.Constant) and isinstance(node.value, str) and "**Status:**" in node.value:
		rest = node.value.split("**Status:**", 1)[1].strip()
		return any(rest.startswith(s) for s in STATUSES)
	return False


def find_pins(source, filename="<test>"):
	"""(line, code) for each assertion that pins the live status of a real task."""
	tree = ast.parse(source, filename)
	if not _reads_real_tasks_file(tree):
		return []
	pins = []
	for node in ast.walk(tree):
		if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
			continue
		if not node.func.attr.startswith("assert"):
			continue
		args = list(node.args) + [k.value for k in node.keywords]
		pinned = any(_status_line_literal(a) for a in args) or (
			any(_status_literal(a) for a in args) and any(_mentions_status(a) for a in args)
		)
		if pinned:
			pins.append((node.lineno, ast.unparse(node)))
	return pins


def scan_repository(root=REPO_ROOT):
	found = []
	for folder in ("sellos", "scripts"):
		for path in sorted((root / folder).rglob("test_*.py")):
			for line, code in find_pins(path.read_text(encoding="utf-8"), str(path)):
				found.append(f"{path.relative_to(root)}:{line}: {code}")
	return found


REAL = 'REPO_ROOT = Path(__file__).resolve().parents[2]\nTASKS_FILE = REPO_ROOT / "TASKS.md"\n'


class TestNoLiveStatusPins(unittest.TestCase):
	def test_no_test_pins_the_live_status_of_a_real_task(self):
		found = scan_repository()
		self.assertEqual(found, [], "These tests pin a status the loop changes. " + FIX)

	def test_the_pin_that_stopped_the_loop_is_found(self):
		source = REAL + 'def t(self):\n\tself.assertEqual(p107["status"], "Not Started")\n'
		self.assertEqual([line for line, _ in find_pins(source)], [4])

	def test_every_form_of_pin_is_found(self):
		for body in (
			'self.assertEqual(self.by_id["SOS-N21"]["status"], "Waiting")',
			'self.assertEqual("Complete", task.status)',
			'self.assertNotEqual(t.get("status"), "Blocked")',
			'self.assertIn("**Status:** In Progress", block)',
			'self.assertEqual(t["status"], " In Progress ")',
		):
			with self.subTest(body=body):
				self.assertEqual(len(find_pins(REAL + "def t(self):\n\t" + body + "\n")), 1)

	def test_a_valid_status_check_is_allowed(self):
		source = REAL + 'def t(self):\n\tself.assertIn(p107["status"], STATUSES)\n'
		self.assertEqual(find_pins(source), [])

	def test_a_test_that_writes_its_own_tasks_file_may_assert_a_status(self):
		source = (
			'def t(self):\n\tpath = self.repo / "TASKS.md"\n'
			'\tself.assertEqual(self.status_of("SOS-X-1"), "Blocked")\n'
			'\tself.assertEqual(task["status"], "In Progress")\n'
		)
		self.assertEqual(find_pins(source), [])

	def test_other_status_fields_are_not_task_statuses(self):
		source = REAL + 'def t(self):\n\tself.assertEqual(grant["status"], "Active")\n'
		self.assertEqual(find_pins(source), [])
