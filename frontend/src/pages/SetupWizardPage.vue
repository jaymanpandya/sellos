<template>
	<div class="max-w-3xl" data-testid="sellos-setup-page">
		<h1 class="text-2xl font-semibold text-ink">Set up your company</h1>
		<p
			v-if="loadError"
			role="alert"
			class="mt-4 text-accent"
			data-testid="sellos-setup-load-error"
		>
			{{ loadError }}
		</p>
		<p v-else-if="!state" class="mt-4 text-ink-muted">Loading.</p>

		<template v-else>
			<div
				v-if="state.complete && !editing"
				class="mt-4 rounded-input border border-line bg-surface p-4"
				data-testid="sellos-setup-done"
			>
				<p class="font-medium text-ink">Your company is set up.</p>
				<p class="mt-1 text-ink-muted">
					{{ session.company.name }} now shows in the app with your logo and colours.
				</p>
				<router-link
					to="/"
					class="btn mt-3 inline-block"
					data-testid="sellos-setup-go-home"
				>
					Go to home
				</router-link>
				<button
					type="button"
					class="ml-2 text-sm text-ink-muted underline"
					data-testid="sellos-setup-edit"
					@click="editing = true"
				>
					Change a setting
				</button>
			</div>

			<template v-else>
				<p v-if="resumed" class="mt-2 text-ink-muted" data-testid="sellos-setup-resumed">
					Welcome back. You are carrying on where you left off.
				</p>
				<ol class="mt-4 flex flex-wrap gap-2" data-testid="sellos-setup-steps">
					<li v-for="(key, i) in state.steps" :key="key">
						<button
							type="button"
							class="rounded-input border px-3 py-1 text-sm"
							:class="
								step === key
									? 'border-brand bg-brand text-white'
									: 'border-line bg-surface text-ink'
							"
							:data-testid="`sellos-setup-step-${key}`"
							:data-done="state.steps_done.includes(key)"
							@click="step = key"
						>
							{{ i + 1 }}. {{ STEP_LABELS[key] }}
							<span v-if="state.steps_done.includes(key)" aria-label="done">✓</span>
						</button>
					</li>
				</ol>

				<form
					v-if="step === 'profile'"
					class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
					data-testid="sellos-setup-profile"
					@submit.prevent="run(saveProfile, 'branding')"
				>
					<label class="block text-sm text-ink">
						Company name
						<input
							v-model="profile.company_name"
							required
							class="field"
							data-testid="sellos-setup-company-name"
						/>
					</label>
					<label class="block text-sm text-ink">
						Company phone
						<input
							v-model="profile.contact_phone"
							class="field"
							data-testid="sellos-setup-phone"
						/>
					</label>
					<label class="block text-sm text-ink">
						Company email
						<input
							v-model="profile.contact_email"
							type="email"
							class="field"
							data-testid="sellos-setup-email"
						/>
					</label>
					<label class="block text-sm text-ink">
						City
						<input
							v-model="profile.city"
							class="field"
							data-testid="sellos-setup-city"
						/>
					</label>
					<label class="block text-sm text-ink">
						Address
						<textarea
							v-model="profile.address"
							rows="2"
							class="field"
							data-testid="sellos-setup-address"
						/>
					</label>
					<button
						type="submit"
						class="btn"
						:disabled="busy"
						data-testid="sellos-setup-save-profile"
					>
						Save and continue
					</button>
				</form>

				<form
					v-else-if="step === 'branding'"
					class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
					data-testid="sellos-setup-branding"
					@submit.prevent="run(saveBranding, 'stages')"
				>
					<div class="flex items-center gap-3">
						<img
							v-if="logoPreview"
							:src="logoPreview"
							alt="Logo preview"
							class="h-12 w-auto"
							data-testid="sellos-setup-logo-preview"
						/>
						<span v-else class="text-sm text-ink-muted">No logo yet.</span>
					</div>
					<label class="block text-sm text-ink">
						Logo (PNG, JPG, GIF or WebP, up to 1 MB)
						<input
							type="file"
							accept="image/png,image/jpeg,image/gif,image/webp"
							class="field"
							data-testid="sellos-setup-logo-file"
							@change="chooseLogo"
						/>
					</label>
					<button
						v-if="logoPreview"
						type="button"
						class="text-sm text-ink-muted underline"
						data-testid="sellos-setup-logo-remove"
						@click="removeLogo"
					>
						Remove the logo
					</button>
					<label class="block text-sm text-ink">
						Brand colour
						<span class="mt-1 flex items-center gap-2">
							<input
								v-model="branding.brand_color"
								type="color"
								aria-label="Pick the brand colour"
								data-testid="sellos-setup-color-picker"
							/>
							<input
								v-model="branding.brand_color"
								pattern="#[0-9a-fA-F]{6}"
								class="field max-w-[8rem]"
								data-testid="sellos-setup-color"
							/>
						</span>
					</label>
					<button
						type="submit"
						class="btn"
						:disabled="busy"
						data-testid="sellos-setup-save-branding"
					>
						Save and continue
					</button>
				</form>

				<form
					v-else-if="step === 'stages'"
					class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
					data-testid="sellos-setup-stages"
					@submit.prevent="run(saveStages, 'users')"
				>
					<p class="text-sm text-ink-muted">
						These are the stages a lead moves through. Rename them, reorder them or add
						your own. Keep at least one Won and one Lost stage.
					</p>
					<ul class="space-y-2">
						<li
							v-for="(s, i) in stages"
							:key="i"
							class="flex items-center gap-2"
							data-testid="sellos-setup-stage-row"
						>
							<input
								v-model="s.stage_name"
								required
								class="field"
								aria-label="Stage name"
								data-testid="sellos-setup-stage-name"
							/>
							<select
								v-model="s.stage_type"
								class="field max-w-[7rem]"
								aria-label="Kind"
								data-testid="sellos-setup-stage-type"
							>
								<option>Open</option>
								<option>Won</option>
								<option>Lost</option>
							</select>
							<button
								type="button"
								class="px-2 text-ink-muted"
								aria-label="Move up"
								:disabled="i === 0"
								@click="move(i, -1)"
							>
								↑
							</button>
							<button
								type="button"
								class="px-2 text-ink-muted"
								aria-label="Move down"
								:disabled="i === stages.length - 1"
								@click="move(i, 1)"
							>
								↓
							</button>
							<button
								type="button"
								class="px-2 text-ink-muted"
								aria-label="Remove stage"
								data-testid="sellos-setup-stage-remove"
								@click="stages.splice(i, 1)"
							>
								✕
							</button>
						</li>
					</ul>
					<button
						type="button"
						class="text-sm text-ink-muted underline"
						data-testid="sellos-setup-stage-add"
						@click="stages.push({ stage_name: '', stage_type: 'Open' })"
					>
						Add a stage
					</button>
					<div>
						<button
							type="submit"
							class="btn"
							:disabled="busy"
							data-testid="sellos-setup-save-stages"
						>
							Save and continue
						</button>
					</div>
				</form>

				<div
					v-else
					class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
					data-testid="sellos-setup-users"
				>
					<p class="text-sm text-ink-muted">
						Add the first people on your team. Each gets one role and an email to set a
						password when your company can send email. You can add more later.
					</p>
					<ul class="divide-y divide-line">
						<li
							v-for="u in state.users"
							:key="u.email"
							class="py-2 text-sm"
							data-testid="sellos-setup-user-row"
						>
							<span class="font-medium text-ink">{{ u.full_name || u.email }}</span>
							<span class="text-ink-muted">
								· {{ u.email }} ·
								{{ u.roles.map((r) => ROLE_LABELS[r] || r).join(", ") }}</span
							>
						</li>
					</ul>
					<form
						class="space-y-2"
						data-testid="sellos-setup-user-form"
						@submit.prevent="addUser"
					>
						<input
							v-model="user.first_name"
							required
							placeholder="First name"
							class="field"
							data-testid="sellos-setup-user-first-name"
						/>
						<input
							v-model="user.last_name"
							placeholder="Last name"
							class="field"
							data-testid="sellos-setup-user-last-name"
						/>
						<input
							v-model="user.email"
							type="email"
							required
							placeholder="Email"
							class="field"
							data-testid="sellos-setup-user-email"
						/>
						<select
							v-model="user.role"
							class="field"
							aria-label="Role"
							data-testid="sellos-setup-user-role"
						>
							<option v-for="r in state.grantable_roles" :key="r" :value="r">
								{{ ROLE_LABELS[r] || r }}
							</option>
						</select>
						<button
							type="submit"
							class="btn"
							:disabled="busy"
							data-testid="sellos-setup-add-user"
						>
							Add person
						</button>
					</form>
					<button
						type="button"
						class="btn"
						:disabled="busy"
						data-testid="sellos-setup-finish"
						@click="finish"
					>
						Finish setup
					</button>
				</div>

				<p
					v-if="error"
					role="alert"
					class="mt-3 text-sm text-accent"
					data-testid="sellos-setup-error"
				>
					{{ error }}
				</p>
			</template>
		</template>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import { serverMessage } from "../crm/crmApi";
import { applyCompanyTheme, session } from "../session";
import { ROLE_LABELS, STEP_LABELS, setupApi } from "../setup/setupApi";

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
const user = reactive({ first_name: "", last_name: "", email: "", role: "SellOS Agent" });

function fill(s) {
	state.value = s;
	Object.assign(profile, s.profile);
	branding.brand_color = s.branding.brand_color;
	logoPreview.value = logoData.value || (logoRemoved.value ? "" : s.branding.logo);
	stages.value = s.stages.map((x) => ({ ...x }));
}

onMounted(async () => {
	try {
		fill(await setupApi.state());
		step.value = state.value.next_step;
		resumed.value = state.value.steps_done.length > 0 && !state.value.complete;
	} catch (e) {
		loadError.value = serverMessage(e, "The setup could not be loaded.");
		console.error("setup failed", e);
	}
});

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
