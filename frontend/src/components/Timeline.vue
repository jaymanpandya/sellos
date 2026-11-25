<template>
	<ol
		class="ml-1 space-y-ui-md border-l border-line pl-ui-md"
		:aria-label="label"
		:data-testid="testid"
	>
		<li v-for="(item, i) in items" :key="i" class="relative" :data-testid="itemTestid">
			<span
				class="absolute -left-[1.4rem] top-1.5 size-2 rounded-round bg-brand"
				aria-hidden="true"
			/>
			<p class="ui-text-strong">{{ item.title }}</p>
			<p v-if="item.when" class="ui-text-muted">{{ item.when }}</p>
			<p
				v-for="(note, n) in item.notes || []"
				:key="n"
				class="ui-text-muted"
				:data-testid="note.testid"
			>
				{{ note.text }}
			</p>
		</li>
	</ol>
</template>

<script setup>
// A vertical timeline (docs/UI_STYLE.md): one entry per event, a dot on the line, a strong title, a muted
// time line and muted notes. `items` is [{ title, when, notes: [{ text, testid }] }], in the order to show.
defineProps({
	items: { type: Array, required: true },
	label: { type: String, default: "Timeline" },
	testid: { type: String, default: "" },
	itemTestid: { type: String, default: "" },
});
</script>
