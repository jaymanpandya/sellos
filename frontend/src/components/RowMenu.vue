<template>
	<Dropdown :options="options" placement="left" data-testid="sellos-row-menu">
		<template #default>
			<button
				type="button"
				class="inline-flex min-h-touch min-w-touch items-center justify-center rounded-control text-ink-muted hover:bg-brand-soft"
				:aria-label="label"
				aria-haspopup="menu"
				data-testid="sellos-row-menu-button"
			>
				<span class="lucide-ellipsis-vertical icon-inherit size-4" aria-hidden="true" />
			</button>
		</template>
	</Dropdown>
</template>

<script setup>
// The row action menu of a DataTable: a kebab button that opens frappe-ui's Dropdown (one radius, the
// shared shadow). `options` is [{ label, icon, onClick }].
import { Dropdown } from "frappe-ui";

defineProps({
	options: { type: Array, default: () => [] },
	label: { type: String, default: "Row actions" },
});
</script>
