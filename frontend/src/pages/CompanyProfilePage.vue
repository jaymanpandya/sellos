<template>
	<PageTemplate shape="form" data-testid="sellos-profile-page">
		<template #header>
			<PageHeader
				title="Company profile"
				text="Your name, logo, colours and contact details. They brand the Dossier PDF and the mandate document."
				icon="lucide-building-2"
			>
				<AppButton
					type="button"
					variant="primary"
					data-testid="sellos-profile-save"
					@click="save"
				>
					Save profile
				</AppButton>
			</PageHeader>
		</template>

		<LoadError
			v-if="loadError"
			:message="loadError"
			data-testid="sellos-profile-load-error"
			@retry="load"
		/>
		<template v-else>
			<p
				v-if="notice"
				role="status"
				class="ui-text-small"
				data-testid="sellos-profile-notice"
			>
				{{ notice }}
			</p>
			<p v-if="error" role="alert" class="ui-text-error" data-testid="sellos-profile-error">
				{{ error }}
			</p>

			<SectionCard title="Identity">
				<div class="grid gap-4 md:grid-cols-2">
					<FormField
						v-model="form.company_name"
						label="Company name"
						data-testid="sellos-profile-name"
					/>
					<FormField
						v-model="form.rera_number"
						label="RERA number"
						hint="The company's own registration, as printed."
						data-testid="sellos-profile-rera"
					/>
				</div>
				<div class="mt-4 flex flex-wrap items-end gap-4">
					<LogoPreview
						v-if="profile.logo"
						:src="profile.logo"
						alt="Company logo"
						data-testid="sellos-profile-logo"
					/>
					<FileField
						label="Logo"
						accept=".png,.jpg,.jpeg"
						hint="A PNG or JPG of up to 1 MB. It is saved as soon as you choose it."
						data-testid="sellos-profile-logo-file"
						@change="uploadLogo"
					/>
				</div>
			</SectionCard>

			<SectionCard
				title="Colours"
				help="The primary colour carries white text, so it must read well against white."
			>
				<div class="grid gap-4 md:grid-cols-2">
					<ColourField
						v-model="form.brand_color"
						label="Primary colour"
						:minimum="profile.min_primary_contrast"
						hint="Empty uses the default."
						data-testid="sellos-profile-primary"
					/>
					<ColourField
						v-model="form.accent_color"
						label="Accent colour"
						:minimum="profile.min_accent_contrast"
						hint="Used for rules and highlights. Empty uses the default."
						data-testid="sellos-profile-accent"
					/>
				</div>
			</SectionCard>

			<SectionCard title="Contact and footer">
				<div class="grid gap-4 md:grid-cols-2">
					<FormField
						v-model="form.address"
						label="Address"
						data-testid="sellos-profile-address"
					/>
					<FormField
						v-model="form.city"
						label="City"
						data-testid="sellos-profile-city"
					/>
					<FormField
						v-model="form.contact_phone"
						label="Phone"
						data-testid="sellos-profile-phone"
					/>
					<FormField
						v-model="form.contact_email"
						type="email"
						label="Email"
						data-testid="sellos-profile-email"
					/>
					<FormField
						v-model="form.website"
						label="Website"
						hint="Starting with https://"
						data-testid="sellos-profile-website"
					/>
					<FormField
						v-model="form.footer_text"
						label="Footer text"
						hint="Printed at the foot of every page."
						data-testid="sellos-profile-footer"
					/>
				</div>
			</SectionCard>
		</template>
	</PageTemplate>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import ColourField from "../components/ColourField.vue";
import FileField from "../components/FileField.vue";
import FormField from "../components/FormField.vue";
import LoadError from "../components/LoadError.vue";
import LogoPreview from "../components/LogoPreview.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import SectionCard from "../components/SectionCard.vue";
import { readFileBase64 } from "../company/partnersApi";
import { serverMessage } from "../crm/crmApi";
import { profileApi } from "../crm/docusealApi";

// The Company Profile (SOS-LOOP). A Company Admin only. The server checks the colours for contrast and every
// field again; the live contrast under each colour only helps the person choosing.
const FIELDS = [
	"company_name",
	"rera_number",
	"brand_color",
	"accent_color",
	"address",
	"city",
	"contact_phone",
	"contact_email",
	"website",
	"footer_text",
];
const profile = reactive({ logo: "", min_primary_contrast: 4.5, min_accent_contrast: 3 });
const form = reactive(Object.fromEntries(FIELDS.map((f) => [f, ""])));
const error = ref("");
const notice = ref("");
const loadError = ref("");

function show(result) {
	Object.assign(profile, result);
	for (const f of FIELDS) form[f] = result[f] || "";
}

async function load() {
	loadError.value = "";
	try {
		show(await profileApi.get());
	} catch (e) {
		loadError.value = serverMessage(e, "The company profile could not be loaded.");
	}
}

async function save() {
	error.value = "";
	notice.value = "";
	try {
		show(await profileApi.save({ ...form }));
		notice.value = "The company profile is saved.";
	} catch (e) {
		error.value = serverMessage(e, "The profile could not be saved.");
	}
}

async function uploadLogo(event) {
	const file = event.target.files?.[0];
	if (!file) return;
	error.value = "";
	notice.value = "";
	try {
		show(await profileApi.uploadLogo(file.name, await readFileBase64(file)));
		notice.value = "The logo is saved.";
	} catch (e) {
		error.value = serverMessage(e, "The logo could not be saved.");
	}
	event.target.value = "";
}

onMounted(load);
</script>
