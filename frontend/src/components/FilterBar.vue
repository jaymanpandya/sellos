<template>
	<form class="ui-card mb-ui-md !p-ui-md" role="search" @submit.prevent="emit('apply')">
		<!-- One row: the search box first, then compact dropdowns, More filters, and Clear when a filter is on. -->
		<div class="flex flex-wrap items-center gap-ui-sm" data-testid="sellos-filter-row">
			<label v-if="!hideSearch" class="relative min-w-[12rem] flex-[1_1_16rem]">
				<span class="sr-only">{{ searchLabel }}</span>
				<span
					class="lucide-search icon-inherit pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-muted"
					aria-hidden="true"
				/>
				<input
					:value="search"
					type="search"
					class="ui-field w-full !pl-9"
					:placeholder="searchPlaceholder"
					:data-testid="searchTestid"
					@input="emit('update:search', $event.target.value)"
				/>
			</label>
			<slot />
			<AppButton
				v-if="$slots.more"
				type="button"
				:aria-expanded="open ? 'true' : 'false'"
				:data-testid="moreTestid"
				@click="emit('update:open', !open)"
			>
				<template #prefix>
					<span
						class="lucide-sliders-horizontal icon-inherit size-4"
						aria-hidden="true"
					/>
				</template>
				More filters
				<span
					v-if="moreCount && !open"
					class="ml-1 rounded-pill bg-brand px-1.5 text-xs text-on-brand-accent"
					:data-testid="moreTestid + '-count'"
					>{{ moreCount }}</span
				>
			</AppButton>
			<AppButton
				v-if="active"
				type="button"
				:data-testid="clearTestid"
				@click="emit('clear')"
			>
				{{ clearLabel }}
			</AppButton>
		</div>
		<!-- The rest. They stay in the page (v-show), so a bookmarked view and a test can reach them. -->
		<div
			v-if="$slots.more"
			v-show="open"
			class="mt-ui-md grid grid-cols-1 gap-x-ui-md gap-y-ui-md border-t border-line-soft pt-ui-md sm:grid-cols-2 xl:grid-cols-4"
			data-testid="sellos-filters-more"
		>
			<slot name="more" />
			<div class="flex flex-wrap items-end gap-ui-sm sm:col-span-2 xl:col-span-4">
				<slot name="actions">
					<AppButton type="submit" variant="primary" :data-testid="applyTestid">
						{{ applyLabel }}
					</AppButton>
				</slot>
			</div>
		</div>
	</form>
</template>

<script setup>
// The filter row (docs/UI_STANDARD.md, "Page template", d): ONE row. A search box first, then compact
// dropdowns in the default slot (FormField compact: no stacked label), a More filters button when the page
// has a `more` slot, and Clear when a filter is on. It replaces the old two row grid of labelled boxes.
import AppButton from "./AppButton.vue";

defineProps({
	search: { type: String, default: "" },
	// A page with nothing to search (the reports) leaves the search box out.
	hideSearch: { type: Boolean, default: false },
	searchLabel: { type: String, default: "Search" },
	searchPlaceholder: { type: String, default: "Search" },
	searchTestid: { type: String, default: "sellos-filter-search" },
	// Whether the `more` slot shows (the page owns it: it opens by itself when a filter in it is on).
	open: { type: Boolean, default: false },
	moreCount: { type: Number, default: 0 },
	// True when any filter or the search is on: Clear shows.
	active: { type: Boolean, default: false },
	applyLabel: { type: String, default: "Apply filters" },
	clearLabel: { type: String, default: "Clear" },
	moreTestid: { type: String, default: "sellos-filters-toggle" },
	clearTestid: { type: String, default: "sellos-filter-clear" },
	applyTestid: { type: String, default: "sellos-filter-apply" },
});
const emit = defineEmits(["apply", "clear", "update:search", "update:open"]);
</script>
