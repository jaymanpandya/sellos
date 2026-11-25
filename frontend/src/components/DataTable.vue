<template>
	<!-- The table's test id marks a loaded table: while rows are loading it is the loading skeleton that is on screen. -->
	<section class="ui-table-card" :data-testid="loading ? 'sellos-table-pending' : testid">
		<h2 v-if="title" class="ui-card-heading border-b border-line-soft px-ui-md py-ui-sm">
			{{ title }}
		</h2>
		<LoadingSkeleton
			v-if="loading"
			:rows="4"
			:label="loadingLabel"
			class="p-ui-md"
			:data-testid="loadingTestid"
		/>
		<EmptyState
			v-else-if="!rows.length"
			:title="emptyTitle"
			:text="emptyText"
			:icon="emptyIcon"
			class="m-ui-md"
			:data-testid="emptyTestid"
		>
			<slot name="empty-action" />
		</EmptyState>

		<template v-else>
			<!-- Tablet and computer: a real table with a sticky header, inside its card. -->
			<div v-if="!viewport.phone" class="ui-table-scroll" data-testid="sellos-table-view">
				<table class="ui-table" :class="dense ? 'ui-table-dense' : ''">
					<caption v-if="caption" class="sr-only">
						{{
							caption
						}}
					</caption>
					<thead>
						<tr role="row">
							<th v-if="selectable" scope="col" class="w-11 !pr-0">
								<AppCheckbox
									:model-value="allSelected"
									:aria-label="`Select all ${rows.length} shown`"
									:data-testid="selectAllTestid"
									@update:model-value="toggleAll"
								/>
							</th>
							<th
								v-for="column in columns"
								:key="column.key"
								scope="col"
								:class="[
									column.align === 'right' ? 'text-right' : '',
									column.thClass,
								]"
								:aria-sort="ariaSort(column)"
							>
								<button
									v-if="column.sortable"
									type="button"
									class="inline-flex items-center gap-1 uppercase"
									:data-testid="`sellos-sort-${column.key}`"
									@click="sortBy(column)"
								>
									{{ column.label }}
									<span
										:class="sortIcon(column)"
										class="icon-inherit size-3.5"
										aria-hidden="true"
									/>
								</button>
								<template v-else>{{ column.label }}</template>
							</th>
							<th v-if="actions" scope="col" class="w-12">
								<span class="sr-only">Actions</span>
							</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="row in pageRows"
							:key="row[rowKey]"
							:data-testid="rowTestid"
							:data-name="row[rowKey]"
							v-bind="rowAttrs ? rowAttrs(row) : {}"
							:class="rowTo || rowClickable ? 'is-clickable cursor-pointer' : ''"
							@click="openRow($event, row)"
						>
							<td v-if="selectable" class="w-11 !pr-0">
								<AppCheckbox
									:model-value="selected.includes(row[rowKey])"
									:value="row[rowKey]"
									:aria-label="selectLabel(row)"
									:data-testid="selectTestid"
									@update:model-value="toggleRow(row[rowKey], $event)"
								/>
							</td>
							<td
								v-for="column in columns"
								:key="column.key"
								:class="[
									column.align === 'right' ? 'text-right' : '',
									column.class,
									column.wrap ? '' : 'whitespace-nowrap',
								]"
							>
								<router-link
									v-if="column.primary && rowTo"
									:to="rowTo(row)"
									class="block font-medium text-ink no-underline hover:underline"
								>
									<slot
										:name="`cell-${column.key}`"
										:row="row"
										:value="row[column.key]"
										>{{ row[column.key] }}</slot
									>
								</router-link>
								<slot
									v-else
									:name="`cell-${column.key}`"
									:row="row"
									:value="row[column.key]"
									>{{ row[column.key] }}</slot
								>
							</td>
							<td v-if="actions" class="w-12 !py-1 text-right">
								<RowMenu
									:options="actions(row)"
									:label="`Actions for ${rowLabel(row)}`"
								/>
							</td>
						</tr>
					</tbody>
				</table>
			</div>

			<!-- Phone: one card per row, each value under its column name. -->
			<ul v-else class="divide-y divide-line-soft" data-testid="sellos-card-view">
				<li
					v-for="row in pageRows"
					:key="row[rowKey]"
					:data-testid="rowTestid"
					:data-name="row[rowKey]"
					v-bind="rowAttrs ? rowAttrs(row) : {}"
					class="flex items-start gap-ui-sm p-ui-md"
				>
					<AppCheckbox
						v-if="selectable"
						:model-value="selected.includes(row[rowKey])"
						:value="row[rowKey]"
						:aria-label="selectLabel(row)"
						:data-testid="selectTestid"
						@update:model-value="toggleRow(row[rowKey], $event)"
					/>
					<component
						:is="rowTo ? 'router-link' : 'div'"
						:to="rowTo ? rowTo(row) : undefined"
						class="grid min-w-0 flex-1 grid-cols-2 gap-x-ui-md gap-y-1 text-sm no-underline"
					>
						<div
							v-for="column in columns"
							:key="column.key"
							class="min-w-0"
							:class="column.primary ? 'col-span-2 text-base font-medium' : ''"
						>
							<span v-if="!column.primary" class="block text-xs text-ink-muted">{{
								column.label
							}}</span>
							<span class="block break-words text-ink">
								<slot
									:name="`cell-${column.key}`"
									:row="row"
									:value="row[column.key]"
									>{{ row[column.key] }}</slot
								>
							</span>
						</div>
					</component>
					<RowMenu
						v-if="actions"
						:options="actions(row)"
						:label="`Actions for ${rowLabel(row)}`"
					/>
				</li>
			</ul>

			<!-- Pagination. -->
			<footer
				class="flex flex-wrap items-center justify-between gap-ui-sm border-t border-line-soft px-ui-md py-ui-sm text-sm text-ink-muted"
				data-testid="sellos-pagination"
			>
				<span data-testid="sellos-pagination-range">
					Showing {{ firstShown }} to {{ lastShown }} of {{ rows.length }}
				</span>
				<span v-if="pageCount > 1" class="flex items-center gap-ui-sm">
					<AppButton
						type="button"
						:disabled="page <= 1"
						data-testid="sellos-pagination-prev"
						@click="page -= 1"
					>
						Previous
					</AppButton>
					<span>Page {{ page }} of {{ pageCount }}</span>
					<AppButton
						type="button"
						:disabled="page >= pageCount"
						data-testid="sellos-pagination-next"
						@click="page += 1"
					>
						Next
					</AppButton>
				</span>
			</footer>
		</template>
	</section>
</template>

<script setup>
// The one table (docs/UI_STANDARD.md, "Tables"): a header band, row dividers, sortable columns, a sticky
// header, a row action menu, pagination and designed loading and empty states. Status pills go in a cell
// slot (`#cell-<key>="{ row }"`). On a phone each row is a card. Sorting and paging happen here, on the
// rows the page already loaded, so no API call changes. `columns` is
// [{ key, label, sortable, sortValue(row), primary, align, wrap, class }]; the primary column is the link
// to the row when `rowTo` is given. `actions(row)` returns [{ label, icon, onClick, danger }].
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import AppButton from "./AppButton.vue";
import AppCheckbox from "./AppCheckbox.vue";
import EmptyState from "./EmptyState.vue";
import LoadingSkeleton from "./LoadingSkeleton.vue";
import RowMenu from "./RowMenu.vue";
import { useViewport } from "../viewport";

const props = defineProps({
	columns: { type: Array, required: true },
	rows: { type: Array, default: () => [] },
	rowKey: { type: String, default: "name" },
	caption: { type: String, default: "" },
	// A heading on the card, such as "All leads".
	title: { type: String, default: "" },
	loading: { type: Boolean, default: false },
	loadingLabel: { type: String, default: "Loading." },
	emptyTitle: { type: String, default: "Nothing here yet" },
	emptyText: { type: String, default: "" },
	emptyIcon: { type: String, default: "lucide-inbox" },
	// Tighter cell padding, for a table with many columns that must fit 1440 wide without a sideways scroll.
	dense: { type: Boolean, default: false },
	selectable: { type: Boolean, default: false },
	selected: { type: Array, default: () => [] },
	// (row) => a route location. The row, and its primary cell, open it.
	rowTo: { type: Function, default: null },
	actions: { type: Function, default: null },
	// A row with no `rowTo` that still reacts to a click: it emits `row-click` with the row.
	rowClickable: { type: Boolean, default: false },
	// (row) => extra attributes for the row, such as { "data-status": row.status } for a test.
	rowAttrs: { type: Function, default: null },
	// (row) => the name read by a screen reader for the row's checkbox and menu.
	rowName: { type: Function, default: null },
	pageSize: { type: Number, default: 25 },
	testid: { type: String, default: "sellos-table" },
	rowTestid: { type: String, default: "sellos-table-row" },
	selectTestid: { type: String, default: "sellos-table-select" },
	selectAllTestid: { type: String, default: "sellos-table-select-all" },
	loadingTestid: { type: String, default: "sellos-table-loading" },
	emptyTestid: { type: String, default: "sellos-table-empty" },
});
const emit = defineEmits(["update:selected", "row-click"]);

const router = useRouter();
const viewport = useViewport();

// Sorting.
const sortKey = ref("");
const sortDir = ref("asc");
function sortBy(column) {
	if (sortKey.value === column.key) {
		if (sortDir.value === "asc") sortDir.value = "desc";
		else sortKey.value = "";
	} else {
		sortKey.value = column.key;
		sortDir.value = "asc";
	}
	page.value = 1;
}
const ariaSort = (column) =>
	column.sortable && sortKey.value === column.key
		? sortDir.value === "asc"
			? "ascending"
			: "descending"
		: undefined;
const sortIcon = (column) =>
	sortKey.value !== column.key
		? "lucide-chevrons-up-down opacity-50"
		: sortDir.value === "asc"
		? "lucide-arrow-up"
		: "lucide-arrow-down";

const sortedRows = computed(() => {
	const column = props.columns.find((c) => c.key === sortKey.value);
	if (!column) return props.rows;
	const value = (row) => (column.sortValue ? column.sortValue(row) : row[column.key]);
	const direction = sortDir.value === "asc" ? 1 : -1;
	return [...props.rows].sort((a, b) => {
		const x = value(a);
		const y = value(b);
		const empty = (v) => v === "" || v === null || v === undefined;
		if (empty(x) && empty(y)) return 0;
		if (empty(x)) return 1; // empty values go last in both directions
		if (empty(y)) return -1;
		if (typeof x === "number" && typeof y === "number") return (x - y) * direction;
		return String(x).localeCompare(String(y), "en-IN", { numeric: true }) * direction;
	});
});

// Pagination.
const page = ref(1);
const pageCount = computed(() => Math.max(1, Math.ceil(props.rows.length / props.pageSize)));
const pageRows = computed(() =>
	sortedRows.value.slice((page.value - 1) * props.pageSize, page.value * props.pageSize)
);
const firstShown = computed(() => (props.rows.length ? (page.value - 1) * props.pageSize + 1 : 0));
const lastShown = computed(() => Math.min(page.value * props.pageSize, props.rows.length));
watch(
	() => props.rows,
	() => {
		if (page.value > pageCount.value) page.value = pageCount.value;
	}
);

// Selection: "all" is every row of the list, on every page.
const allSelected = computed(
	() => props.rows.length > 0 && props.selected.length === props.rows.length
);
function toggleAll(on) {
	emit("update:selected", on ? props.rows.map((r) => r[props.rowKey]) : []);
}
function toggleRow(key, on) {
	emit(
		"update:selected",
		on
			? [...props.selected.filter((k) => k !== key), key]
			: props.selected.filter((k) => k !== key)
	);
}
const rowLabel = (row) => (props.rowName ? props.rowName(row) : row[props.rowKey]);
const selectLabel = (row) => `Select ${rowLabel(row)}`;

// A click on the row opens it, unless it landed on a link, button or field of its own.
function openRow(event, row) {
	if (!props.rowTo && !props.rowClickable) return;
	if (event.target.closest("a, button, input, label, [role='menu']")) return;
	emit("row-click", row);
	if (props.rowTo) router.push(props.rowTo(row));
}
</script>
