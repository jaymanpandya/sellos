<template>
	<div class="ui-page" :data-shape="shape" data-testid="sellos-page-template">
		<!-- The top bar (breadcrumb) is the shell's. The page header, or the record header on a record. -->
		<slot name="header" />
		<!-- A form or settings screen opens with one notice area. -->
		<div v-if="$slots.notice" class="mb-4"><slot name="notice" /></div>
		<!-- A row of stat tiles (list and dashboard). -->
		<slot name="kpis" />
		<!-- One row: search and Filters, then the removable filter chips (list). -->
		<slot name="filters" />

		<!-- Record: two thirds and one third; the side column is never empty. Tabs sit above the main column. -->
		<div
			v-if="shape === 'record'"
			class="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]"
			data-testid="sellos-page-main"
		>
			<div class="min-w-0 space-y-4">
				<slot name="tabs" />
				<slot />
			</div>
			<aside class="min-w-0 space-y-4" aria-label="Summary">
				<slot name="side" />
			</aside>
		</div>

		<!-- Dashboard: two balanced columns of natural height, and a Go to card. -->
		<div
			v-else-if="shape === 'dashboard'"
			class="grid grid-cols-1 items-start gap-4 lg:grid-cols-2"
			data-testid="sellos-page-main"
		>
			<div class="min-w-0 space-y-4"><slot name="left" /></div>
			<div class="min-w-0 space-y-4">
				<slot name="right" />
				<slot name="rail" />
			</div>
			<div v-if="$slots.default" class="min-w-0 lg:col-span-2"><slot /></div>
		</div>

		<!-- List, and form or settings. -->
		<div v-else data-testid="sellos-page-main">
			<div class="min-w-0 space-y-4"><slot /></div>
			<slot name="footer" />
		</div>
	</div>
</template>

<script setup>
// The page template (docs/DESIGN_SYSTEM.md, section 3, the four shapes):
//   list       header, filters, stat tiles, then the table card (default slot) and its empty state;
//   record     RecordHeader, tabs, the main column (default slot) and the side column (slot `side`, never empty);
//   dashboard  header, stat tiles, two balanced columns (slots `left` and `right`) and a Go to card (slot `rail`);
//   form       header, one notice area (slot `notice`), section cards (default slot), sticky footer (slot `footer`).
// A page fills the slots it has; the order and the spacing are fixed here, never by the page.
defineProps({
	shape: { type: String, default: "list" }, // list | record | dashboard | form
});
</script>
