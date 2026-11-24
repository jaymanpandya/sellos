<template>
	<div class="ui-page" data-testid="sellos-page-template">
		<!-- a. The top bar (breadcrumb) is the shell's. b. The header card. -->
		<slot name="header" />
		<!-- c. A strip of at most four KPI cards. -->
		<slot name="kpis" />
		<!-- d. One row of filters. -->
		<slot name="filters" />
		<!-- e. The main content: a table or a board. f. The optional "Go to" rail, dashboards only. -->
		<div
			:class="$slots.rail ? 'grid gap-ui-md xl:grid-cols-[minmax(0,1fr)_16rem]' : ''"
			data-testid="sellos-page-main"
		>
			<div class="min-w-0"><slot /></div>
			<aside v-if="$slots.rail" class="min-w-0" aria-label="Go to">
				<slot name="rail" />
			</aside>
		</div>
	</div>
</template>

<script setup>
// The one page template (docs/UI_STANDARD.md, "Page template"): header card, KPI strip, one filter row,
// then a table or a board, and on a dashboard a right rail of "Go to" links. A page fills the slots it
// has and leaves the rest out; the order and the spacing are fixed here, never by the page.
</script>
