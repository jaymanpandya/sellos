<template>
	<PageTemplate shape="record" data-testid="sellos-partner-firm-page">
		<template #header>
			<RecordHeader
				:title="firm ? firm.firm_name : 'Your firm'"
				title-testid="sellos-partner-firm-name"
			>
				<template v-if="firm" #status>
					<StatusBadge
						:tone="STATUS_TONE[firm.status] || 'neutral'"
						:label="firm.status"
						data-testid="sellos-partner-firm-status"
					/>
				</template>
				<template v-if="firm" #line>
					<p class="ui-text-muted mt-0.5" data-testid="sellos-partner-firm-code">
						Partner code {{ firm.partner_code }}
					</p>
				</template>
				<template v-if="firm && firm.can_edit" #actions>
					<AppButton
						type="button"
						variant="primary"
						data-testid="sellos-partner-firm-edit"
						@click="editing = true"
					>
						Edit firm details
					</AppButton>
				</template>
			</RecordHeader>
		</template>

		<div v-if="loadError" data-testid="sellos-partner-firm-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<p
			v-if="error && !editing"
			role="alert"
			data-testid="sellos-partner-firm-error"
			class="ui-text-error"
		>
			{{ error }}
		</p>

		<EmptyState
			v-if="loaded && !loadError && !firm"
			title="Your login is not linked to a firm"
			text="Ask the company to invite your firm."
			icon="lucide-handshake"
		/>

		<template v-if="firm">
			<SectionCard
				title="Where your firm stands"
				data-testid="sellos-partner-firm-state"
				:data-status="firm.status"
			>
				<p class="ui-text-body" data-testid="sellos-partner-firm-message">
					{{ message }}
				</p>
				<p v-if="firm.missing.length" class="mt-ui-sm ui-text-muted">
					Still needed: {{ firm.missing.join(", ") }}.
				</p>
			</SectionCard>
			<SectionCard
				title="Firm details"
				help="The company sees these before it approves your firm."
			>
				<dl>
					<FieldGrid>
						<ReadField label="Firm name" :value="firm.firm_name" />
						<ReadField label="Contact person" :value="firm.contact_person" />
						<ReadField label="Email" :value="firm.email" />
						<ReadField label="Phone" :value="firm.phone_masked" />
						<ReadField
							label="RERA agent registration number"
							:value="firm.rera_number"
						/>
						<ReadField
							label="PAN"
							:value="firm.has_pan ? 'Given, only the company sees it' : ''"
						/>
						<ReadField
							label="Signed agreement"
							:value="firm.has_agreement ? 'Uploaded' : ''"
						/>
					</FieldGrid>
				</dl>
			</SectionCard>
		</template>

		<template #side>
			<SectionCard title="Summary">
				<dl v-if="firm">
					<FieldGrid :columns="1">
						<ReadField label="Status" :value="firm.status" />
						<ReadField label="Partner code" :value="firm.partner_code" />
						<ReadField
							label="Can register leads"
							:value="firm.can_work ? 'Yes' : 'Not yet'"
						/>
					</FieldGrid>
				</dl>
				<p v-else class="ui-text-muted">Your firm is loading.</p>
			</SectionCard>
			<SectionCard title="What happens next">
				<p class="ui-text-muted">
					A firm that is not approved can register no lead and see no inventory. Complete
					the details, and the company approves your firm.
				</p>
			</SectionCard>
		</template>

		<!-- The firm's details are a drawer opened from the header. -->
		<FormDrawer
			v-if="firm && firm.can_edit"
			:open="editing"
			title="Firm details"
			text="The company sees these before it approves your firm."
			submit-label="Save details"
			testid="sellos-partner-firm-form"
			submit-testid="sellos-partner-firm-save"
			@close="editing = false"
			@submit="save"
		>
			<FormSection title="Firm">
				<FormField
					v-model="form.firm_name"
					label="Firm name"
					required
					data-testid="sellos-partner-firm-name-input"
				/>
				<FormField
					v-model="form.contact_person"
					label="Contact person"
					required
					data-testid="sellos-partner-firm-contact"
				/>
				<FormField
					v-model="form.phone"
					type="tel"
					label="Phone"
					:hint="firm.phone_masked ? `Saved: ${firm.phone_masked}` : ''"
					data-testid="sellos-partner-firm-phone"
				/>
			</FormSection>
			<FormSection title="Registration">
				<FormField
					v-model="form.rera_number"
					label="RERA agent registration number"
					data-testid="sellos-partner-firm-rera"
				/>
				<FormField
					v-model="form.pan"
					label="PAN"
					:hint="
						firm.has_pan
							? 'Saved. Only the company sees it.'
							: 'Only the company sees it.'
					"
					data-testid="sellos-partner-firm-pan"
				/>
				<FileField
					label="Signed agreement"
					accept=".pdf,.png,.jpg,.jpeg"
					:hint="
						firm.has_agreement
							? 'Uploaded. Choose a file to replace it.'
							: 'A PDF, PNG or JPG file of up to 5 MB.'
					"
					class="md:col-span-2"
					data-testid="sellos-partner-firm-agreement"
					@change="chooseFile"
				/>
			</FormSection>
			<p
				v-if="error"
				role="alert"
				data-testid="sellos-partner-firm-error"
				class="ui-text-error"
			>
				{{ error }}
			</p>
		</FormDrawer>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FieldGrid from "../components/FieldGrid.vue";
import FileField from "../components/FileField.vue";
import FormDrawer from "../components/FormDrawer.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import LoadError from "../components/LoadError.vue";
import PageTemplate from "../components/PageTemplate.vue";
import ReadField from "../components/ReadField.vue";
import RecordHeader from "../components/RecordHeader.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { partnersApi, readFileBase64 } from "../company/partnersApi";
import { serverMessage } from "../crm/crmApi";
import { setPartnerFirm } from "../partnerState";

// A partner's own firm (SOS-P7-01): its state, and the details the contact person completes. A firm that is
// not Approved can register no lead and see no inventory, and this page says so.
const STATUS_TONE = {
	Invited: "info",
	"Pending approval": "warning",
	Approved: "success",
	Suspended: "danger",
};

const firm = ref(null);
const error = ref("");
const loadError = ref("");
const loaded = ref(false);
const editing = ref(false);
const form = reactive({ firm_name: "", contact_person: "", phone: "", rera_number: "", pan: "" });
let chosen = null;

const message = computed(() => {
	switch (firm.value?.status) {
		case "Invited":
			return "Complete your firm's details below. The company can approve your firm once they are in.";
		case "Pending approval":
			return "Your details are with the company, waiting for approval. You can not register leads or see inventory until your firm is approved.";
		case "Approved":
			return "Your firm is approved. You can register leads.";
		case "Suspended":
			return `Your firm is suspended${
				firm.value.status_reason ? `: ${firm.value.status_reason}` : ""
			}. You can not register leads or see inventory. Contact the company.`;
		default:
			return "";
	}
});

function show(data) {
	firm.value = data.firm;
	setPartnerFirm(data.firm);
	if (data.firm) {
		Object.assign(form, {
			firm_name: data.firm.firm_name,
			contact_person: data.firm.contact_person,
		});
	}
}

async function load() {
	loadError.value = "";
	try {
		show(await partnersApi.mine());
	} catch (e) {
		loadError.value = serverMessage(e, "Your firm could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

const chooseFile = (event) => {
	chosen = event.target.files?.[0] || null;
};

async function save() {
	error.value = "";
	try {
		const values = Object.fromEntries(Object.entries(form).filter(([, v]) => v !== ""));
		show(await partnersApi.submitDetails(values));
		if (chosen) {
			show(await partnersApi.uploadMyAgreement(chosen.name, await readFileBase64(chosen)));
			chosen = null;
		}
		form.pan = "";
		form.phone = "";
		editing.value = false;
	} catch (e) {
		error.value = serverMessage(e, "The details could not be saved.");
	}
}

onMounted(load);
</script>
