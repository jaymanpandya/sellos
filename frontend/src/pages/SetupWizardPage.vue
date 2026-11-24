<template>
	<!-- A wizard, not a list: the header card, the step buttons, and one headed card per step. -->
	<PageTemplate data-testid="sellos-setup-page">
		<template #header>
			<PageHeader
				title="Set up your company"
				text="Four short steps: your company, your logo and colour, your lead stages and your first people."
				icon="lucide-settings"
			/>
		</template>
		<div v-if="loadError" class="mb-ui-md" data-testid="sellos-setup-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<LoadingSkeleton v-else-if="!state" :rows="3" />

		<template v-else>
			<div v-if="state.complete && !editing" class="ui-card" data-testid="sellos-setup-done">
				<div class="flex items-center gap-2">
					<StatusBadge label="Done" tone="success" />
					<p class="font-medium text-ink">Your company is set up.</p>
				</div>
				<p class="mt-1 text-ink-muted">
					{{ session.company.name }} now shows in the app with your logo and colours.
				</p>
				<div class="mt-ui-md flex flex-wrap gap-ui-sm">
					<AppButton
						variant="primary"
						data-testid="sellos-setup-go-home"
						@click="router.push('/')"
					>
						Go to home
					</AppButton>
					<AppButton
						type="button"
						data-testid="sellos-setup-edit"
						@click="editing = true"
					>
						Change a setting
					</AppButton>
				</div>
			</div>

			<template v-else>
				<p
					v-if="resumed"
					class="mb-ui-md text-ink-muted"
					data-testid="sellos-setup-resumed"
				>
					Welcome back. You are carrying on where you left off.
				</p>
				<ol class="mb-ui-md flex flex-wrap gap-ui-sm" data-testid="sellos-setup-steps">
					<li v-for="(key, i) in state.steps" :key="key">
						<AppButton
							type="button"
							:active="step === key"
							:data-testid="`sellos-setup-step-${key}`"
							:data-done="state.steps_done.includes(key)"
							@click="step = key"
						>
							{{ i + 1 }}. {{ STEP_LABELS[key] }}
							<span v-if="state.steps_done.includes(key)" aria-label="done">✓</span>
						</AppButton>
					</li>
				</ol>

				<form
					v-if="step === 'profile'"
					class="ui-card"
					data-testid="sellos-setup-profile"
					@submit.prevent="run(saveProfile, 'branding')"
				>
					<FormSection title="Your company">
						<FormField
							v-model="profile.company_name"
							label="Company name"
							required
							data-testid="sellos-setup-company-name"
						/>
						<FormField
							v-model="profile.contact_phone"
							type="tel"
							label="Company phone"
							data-testid="sellos-setup-phone"
						/>
						<FormField
							v-model="profile.contact_email"
							type="email"
							label="Company email"
							data-testid="sellos-setup-email"
						/>
						<FormField
							v-model="profile.city"
							label="City"
							data-testid="sellos-setup-city"
						/>
						<FormField
							v-model="profile.address"
							type="textarea"
							label="Address"
							class="md:col-span-2"
							data-testid="sellos-setup-address"
						/>
					</FormSection>
					<div class="mt-ui-md">
						<AppButton
							type="submit"
							variant="primary"
							:disabled="busy"
							data-testid="sellos-setup-save-profile"
						>
							Save and continue
						</AppButton>
					</div>
				</form>

				<form
					v-else-if="step === 'branding'"
					class="ui-card"
					data-testid="sellos-setup-branding"
					@submit.prevent="run(saveBranding, 'stages')"
				>
					<FormSection title="Logo and colour">
						<div class="flex items-center gap-3 md:col-span-2">
							<img
								v-if="logoPreview"
								:src="logoPreview"
								alt="Logo preview"
								class="h-12 w-auto"
								data-testid="sellos-setup-logo-preview"
							/>
							<span v-else class="text-sm text-ink-muted">No logo yet.</span>
						</div>
						<FileField
							label="Logo (PNG, JPG, GIF or WebP, up to 1 MB)"
							accept="image/png,image/jpeg,image/gif,image/webp"
							data-testid="sellos-setup-logo-file"
							class="md:col-span-2"
							@change="chooseLogo"
						/>
						<div v-if="logoPreview" class="md:col-span-2">
							<AppButton
								type="button"
								data-testid="sellos-setup-logo-remove"
								@click="removeLogo"
							>
								Remove the logo
							</AppButton>
						</div>
						<div class="flex items-end gap-ui-sm md:col-span-2">
							<FormField
								v-model="branding.brand_color"
								label="Brand colour"
								hint="A hex colour such as #0f4c35."
								pattern="#[0-9a-fA-F]{6}"
								class="max-w-[12rem]"
								data-testid="sellos-setup-color"
							/>
							<span
								class="mb-7 inline-block h-11 w-11 shrink-0 rounded border border-line"
								:style="{ backgroundColor: branding.brand_color }"
								aria-hidden="true"
								data-testid="sellos-setup-color-swatch"
							/>
						</div>
					</FormSection>
					<div class="mt-ui-md">
						<AppButton
							type="submit"
							variant="primary"
							:disabled="busy"
							data-testid="sellos-setup-save-branding"
						>
							Save and continue
						</AppButton>
					</div>
				</form>

				<form
					v-else-if="step === 'stages'"
					class="ui-card"
					data-testid="sellos-setup-stages"
					@submit.prevent="run(saveStages, 'users')"
				>
					<FormSection title="Lead stages">
						<p class="text-sm text-ink-muted md:col-span-2">
							These are the stages a lead moves through. Rename them, reorder them or
							add your own. Keep at least one Won and one Lost stage. A stage that
							has leads cannot be removed: move its leads first.
						</p>
						<ul class="space-y-ui-sm md:col-span-2">
							<li
								v-for="(s, i) in stages"
								:key="i"
								class="flex flex-wrap items-end gap-2"
								data-testid="sellos-setup-stage-row"
							>
								<FormField
									v-model="s.stage_name"
									label="Stage name"
									required
									class="min-w-[10rem] flex-1"
									data-testid="sellos-setup-stage-name"
								/>
								<FormField
									v-model="s.stage_type"
									type="select"
									label="Kind"
									:options="STAGE_KINDS"
									class="w-32"
									data-testid="sellos-setup-stage-type"
								/>
								<span
									v-if="s.leads"
									class="mb-3 whitespace-nowrap text-xs text-ink-muted"
									data-testid="sellos-setup-stage-leads"
								>
									{{ s.leads }} {{ s.leads === 1 ? "lead" : "leads" }}
								</span>
								<AppButton
									type="button"
									aria-label="Move up"
									:disabled="i === 0"
									@click="move(i, -1)"
								>
									<span
										class="lucide-arrow-up icon-inherit size-4"
										aria-hidden="true"
									/>
								</AppButton>
								<AppButton
									type="button"
									aria-label="Move down"
									:disabled="i === stages.length - 1"
									@click="move(i, 1)"
								>
									<span
										class="lucide-arrow-down icon-inherit size-4"
										aria-hidden="true"
									/>
								</AppButton>
								<AppButton
									type="button"
									aria-label="Remove stage"
									data-testid="sellos-setup-stage-remove"
									@click="stages.splice(i, 1)"
								>
									<span
										class="lucide-x icon-inherit size-4"
										aria-hidden="true"
									/>
								</AppButton>
							</li>
						</ul>
					</FormSection>
					<div class="mt-ui-md flex flex-wrap gap-ui-sm">
						<AppButton
							type="button"
							data-testid="sellos-setup-stage-add"
							@click="stages.push({ stage_name: '', stage_type: 'Open' })"
						>
							Add a stage
						</AppButton>
						<AppButton
							type="submit"
							variant="primary"
							:disabled="busy"
							data-testid="sellos-setup-save-stages"
						>
							Save and continue
						</AppButton>
					</div>
				</form>

				<div v-else class="space-y-ui-md" data-testid="sellos-setup-users">
					<DataTable
						title="Your first people"
						caption="People added so far"
						:columns="userColumns"
						:rows="state.users"
						row-key="email"
						empty-title="No one added yet"
						empty-text="Add the first people on your team below."
						empty-icon="lucide-users"
						testid="sellos-setup-user-list"
						row-testid="sellos-setup-user-row"
					>
						<template #cell-full_name="{ row }">
							<span class="font-medium text-ink">{{
								row.full_name || row.email
							}}</span>
						</template>
						<template #cell-roles="{ row }">
							<span class="text-ink-body">{{
								row.roles.map((r) => ROLE_LABELS[r] || r).join(", ")
							}}</span>
						</template>
					</DataTable>
					<form
						class="ui-card"
						data-testid="sellos-setup-user-form"
						@submit.prevent="addUser"
					>
						<FormSection title="Add a person">
							<p class="text-sm text-ink-muted md:col-span-2">
								Each person gets one role and an email to set a password when your
								company can send email. You can add more later.
							</p>
							<FormField
								v-model="user.first_name"
								label="First name"
								required
								data-testid="sellos-setup-user-first-name"
							/>
							<FormField
								v-model="user.last_name"
								label="Last name"
								data-testid="sellos-setup-user-last-name"
							/>
							<FormField
								v-model="user.email"
								type="email"
								label="Email"
								required
								data-testid="sellos-setup-user-email"
							/>
							<FormField
								v-model="user.role"
								type="select"
								label="Role"
								:options="roleOptions"
								data-testid="sellos-setup-user-role"
							/>
						</FormSection>
						<div class="mt-ui-md">
							<AppButton
								type="submit"
								:disabled="busy"
								data-testid="sellos-setup-add-user"
							>
								Add person
							</AppButton>
						</div>
					</form>
					<AppButton
						type="button"
						variant="primary"
						:disabled="busy"
						data-testid="sellos-setup-finish"
						@click="finish"
					>
						Finish setup
					</AppButton>
				</div>

				<p
					v-if="error"
					role="alert"
					class="mt-ui-md text-sm text-danger"
					data-testid="sellos-setup-error"
				>
					{{ error }}
				</p>
			</template>
		</template>
	</PageTemplate>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import AppButton from "../components/AppButton.vue";
import FileField from "../components/FileField.vue";
import DataTable from "../components/DataTable.vue";
import FormField from "../components/FormField.vue";
import FormSection from "../components/FormSection.vue";
import LoadError from "../components/LoadError.vue";
import LoadingSkeleton from "../components/LoadingSkeleton.vue";
import PageHeader from "../components/PageHeader.vue";
import PageTemplate from "../components/PageTemplate.vue";
import StatusBadge from "../components/StatusBadge.vue";

import { serverMessage } from "../crm/crmApi";
import { logRequestError } from "../api";
import { applyCompanyTheme, session } from "../session";
import { ROLE_LABELS, STEP_LABELS, setupApi } from "../setup/setupApi";

const router = useRouter();
const state = ref(null);
const step = ref("profile");
const resumed = ref(false);
const editing = ref(false);
const busy = ref(false);
const error = ref("");
const loadError = ref("");
const profile = reactive({});
const branding = reactive({ brand_color: "#0f4c35" });
const logoData = ref(null);
const logoPreview = ref("");
const logoRemoved = ref(false);
const stages = ref([]);
const roleOptions = computed(() =>
	(state.value?.grantable_roles || []).map((r) => ({ label: ROLE_LABELS[r] || r, value: r }))
);
const userColumns = [
	{ key: "full_name", label: "Name", primary: true },
	{ key: "email", label: "Email" },
	{ key: "roles", label: "Role" },
];
const STAGE_KINDS = ["Open", "Won", "Lost"];
const user = reactive({ first_name: "", last_name: "", email: "", role: "SellOS Agent" });

function fill(s) {
	state.value = s;
	Object.assign(profile, s.profile);
	branding.brand_color = s.branding.brand_color;
	logoPreview.value = logoData.value || (logoRemoved.value ? "" : s.branding.logo);
	stages.value = s.stages.map((x) => ({ ...x }));
}

async function load() {
	loadError.value = "";
	try {
		fill(await setupApi.state());
		step.value = state.value.next_step;
		resumed.value = state.value.steps_done.length > 0 && !state.value.complete;
	} catch (e) {
		loadError.value = serverMessage(e, "The setup could not be loaded.");
		logRequestError("setup failed", e);
	}
}
onMounted(load);

async function run(action, nextStep) {
	error.value = "";
	busy.value = true;
	try {
		fill(await action());
		step.value = nextStep;
	} catch (e) {
		error.value = serverMessage(e, "This step could not be saved.");
	} finally {
		busy.value = false;
	}
}

const saveProfile = () => setupApi.saveProfile({ ...profile });
const saveBranding = async () => {
	const s = await setupApi.saveBranding(
		branding.brand_color,
		logoData.value,
		logoRemoved.value ? 1 : 0
	);
	logoData.value = null;
	logoRemoved.value = false;
	return s;
};
const saveStages = () => setupApi.saveStages(stages.value);

function chooseLogo(event) {
	const file = event.target.files?.[0];
	if (!file) return;
	if (file.size > 1024 * 1024) {
		error.value = "The logo is larger than 1 MB. Choose a smaller image.";
		event.target.value = "";
		return;
	}
	error.value = "";
	const reader = new FileReader();
	reader.onload = () => {
		logoData.value = reader.result;
		logoPreview.value = reader.result;
		logoRemoved.value = false;
	};
	reader.readAsDataURL(file);
}

function removeLogo() {
	logoData.value = null;
	logoPreview.value = "";
	logoRemoved.value = true;
}

function move(i, by) {
	const list = stages.value;
	[list[i], list[i + by]] = [list[i + by], list[i]];
}

async function addUser() {
	error.value = "";
	busy.value = true;
	try {
		const result = await setupApi.addUser(
			user.email,
			user.first_name,
			user.role,
			user.last_name
		);
		state.value = { ...state.value, users: result.users };
		Object.assign(user, { first_name: "", last_name: "", email: "" });
	} catch (e) {
		error.value = serverMessage(e, "The person could not be added.");
	} finally {
		busy.value = false;
	}
}

async function finish() {
	error.value = "";
	busy.value = true;
	try {
		const result = await setupApi.finish();
		fill(result);
		// The branding shows at once, with no reload.
		session.company = {
			name: result.profile.company_name,
			logo: result.branding.logo,
			brandColor: result.branding.brand_color,
		};
		session.setupComplete = true;
		applyCompanyTheme(session.company);
		editing.value = false;
	} catch (e) {
		error.value = serverMessage(e, "Setup could not be finished.");
	} finally {
		busy.value = false;
	}
}
</script>
