<template>
	<div
		class="flex flex-col items-end gap-ui-sm sm:items-start"
		data-testid="sellos-today-actions"
	>
		<div class="flex flex-wrap gap-ui-sm">
			<AppButton
				type="button"
				data-testid="sellos-today-call"
				:aria-expanded="showNumber"
				@click="showNumber = !showNumber"
			>
				Call
			</AppButton>
			<AppButton type="button" data-testid="sellos-today-log" @click="emit('log', row)">
				Log
			</AppButton>
		</div>
		<p v-if="showNumber" class="text-sm text-ink" data-testid="sellos-today-number">
			<template v-if="row.phone">
				<a v-if="fullNumbers" :href="`tel:${row.phone}`" class="ui-link">{{
					row.phone
				}}</a>
				<span v-else>{{ row.phone }}</span>
				<span v-if="row.overseas_phone"> · {{ row.overseas_phone }}</span>
			</template>
			<template v-else>No phone</template>
		</p>
	</div>
</template>

<script setup>
import { ref } from "vue";

import AppButton from "./AppButton.vue";

// The action cell of one row of the Today screen (SOS-P1-26). Call shows the number the person's role
// may see (a Company Admin's is a link to dial, an Agent's and a Sales Manager's is masked). Log asks
// the page to open its log drawer for the row: on a follow up it marks the follow up done, on any other
// row it logs a call on the lead. Consent is shown as a warning and never stops either.
defineProps({
	row: { type: Object, required: true },
	fullNumbers: { type: Boolean, default: false },
});
const emit = defineEmits(["log"]);

const showNumber = ref(false);
</script>
