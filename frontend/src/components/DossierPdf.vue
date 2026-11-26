<template>
	<div class="space-y-3" data-testid="sellos-dossier-pdf">
		<p class="ui-text-muted">
			A branded PDF of the Dossier: a cover page, the seller and property, the mandate and
			its signing status, the notes by type with their photos, and page numbers.
		</p>
		<p v-if="pdf" data-testid="sellos-dossier-pdf-version">
			Version {{ pdf.version }}, made {{ formatWhen(pdf.generated_on) }}.
		</p>
		<p v-else class="ui-text-muted" data-testid="sellos-dossier-pdf-none">
			No PDF has been made yet.
		</p>
		<div class="flex flex-wrap gap-2">
			<AppButton
				v-if="pdf"
				type="button"
				variant="primary"
				data-testid="sellos-dossier-pdf-download"
				@click="download"
			>
				Download
			</AppButton>
			<AppButton
				type="button"
				:variant="pdf ? 'secondary' : 'primary'"
				:disabled="busy"
				data-testid="sellos-dossier-pdf-generate"
				@click="generate"
			>
				{{ pdf ? "Regenerate" : "Make the PDF" }}
			</AppButton>
		</div>
		<p v-if="error" role="alert" class="ui-text-error" data-testid="sellos-dossier-pdf-error">
			{{ error }}
		</p>
	</div>
</template>

<script setup>
// The Dossier as a branded PDF (SOS-LOOP). Made on the server, kept on the mandate with a version, regenerated on
// request. Shown only for a released (signed) mandate.
import { ref } from "vue";

import AppButton from "./AppButton.vue";
import { serverMessage } from "../crm/crmApi";
import { mandateApi } from "../crm/mandatesApi";
import { formatWhen } from "../format";

const props = defineProps({
	mandate: { type: Object, required: true },
	pdf: { type: Object, default: null },
});
const emit = defineEmits(["changed"]);
const busy = ref(false);
const error = ref("");

const download = () => window.open(props.pdf.file, "_blank", "noopener");

async function generate() {
	busy.value = true;
	error.value = "";
	try {
		await mandateApi.generateDossierPdf(props.mandate.name);
		emit("changed", "The Dossier PDF is made.");
	} catch (e) {
		error.value = serverMessage(e, "The PDF could not be made.");
	} finally {
		busy.value = false;
	}
}
</script>
