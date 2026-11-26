"""SOS-LOOP (26 Nov 2026): the list rules of docs/DESIGN_SYSTEM.md ("Lists", rules a to d and f) are enforced by
scripts/check_design_system.py. A page with a button in a row cell, a name cell joined to a source, or a bare dash
fails; a page built as the Leads, Sellers, Mandates and Deals lists are passes."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
	"check_design_system", ROOT / "scripts" / "check_design_system.py"
)
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

PAGE = """<template>
	<DataTable :columns="columns" :rows="rows">
		{cells}
		<template #empty-action><AppButton>Add</AppButton></template>
	</DataTable>
</template>
<script setup></script>
"""


class TestListRules(unittest.TestCase):
	def found(self, cells):
		with tempfile.TemporaryDirectory() as folder:
			page = Path(folder) / "Page.vue"
			page.write_text(PAGE.replace("{cells}", cells), encoding="utf-8")
			return [(rule, what) for _line, rule, what in check.list_findings(page)]

	def test_a_name_cell_with_plain_values_and_pills_passes(self):
		cells = (
			'<template #cell-name="{ row }"><NameCell :name="row.client_name" :identifier="row.phone" '
			':detail="row.city" /></template>'
			'<template #cell-stage="{ row }"><StatusBadge :label="row.stage" /></template>'
			'<template #cell-agent="{ row }"><CellText :value="row.agent" /></template>'
		)
		self.assertEqual(self.found(cells), [])

	def test_a_button_in_a_row_cell_fails_but_the_empty_state_action_does_not(self):
		found = self.found(
			'<template #cell-x="{ row }"><AppButton @click="go(row)">Go</AppButton></template>'
		)
		self.assertEqual(found, [("control in a row", "<AppButton>")])

	def test_a_field_or_a_link_in_a_row_cell_fails(self):
		for cell in (
			'<FormField v-model="row.stage" type="select" />',
			'<a :href="row.file">Download</a>',
			'<router-link :to="row.to" class="ui-link">Open</router-link>',
		):
			found = self.found(f'<template #cell-x="{{ row }}">{cell}</template>')
			self.assertTrue(found, cell)
			self.assertTrue(all(rule == "control in a row" for rule, _ in found), cell)

	def test_a_name_joined_to_a_source_property_or_status_fails(self):
		for name in (
			"`${row.client_name} ${row.source}`",
			"row.client_name + ' ' + row.status",
			"row.client_name + row.property",
		):
			found = self.found(f'<template #cell-name="{{ row }}"><NameCell :name="{name}" /></template>')
			self.assertEqual([rule for rule, _ in found], ["name joined to a detail"], name)

	def test_a_bare_dash_fails(self):
		for cell in (
			'<span v-if="row.x">{{ row.x }}</span><span v-else>-</span>',
			"<span>{{ row.x ? row.x : '-' }}</span>",
			'<span>{{ row.x || "—" }}</span>',
		):
			found = self.found(f'<template #cell-x="{{ row }}">{cell}</template>')
			self.assertIn("bare dash", [rule for rule, _ in found], cell)

	def test_no_page_of_the_app_breaks_a_list_rule(self):
		pages = [p for p in check.pages() if p.suffix == ".vue"]
		self.assertGreater(len(pages), 20)
		for page in pages:
			self.assertEqual(check.list_findings(page), [], page.name)


if __name__ == "__main__":
	unittest.main()
