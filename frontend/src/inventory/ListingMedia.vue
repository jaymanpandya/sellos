<template>
	<div class="mt-ui-sm rounded-input border border-line-soft p-ui-md" data-testid="sellos-media">
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-media-error"
			class="mb-ui-sm text-sm text-accent"
		>
			{{ error }}
		</p>
		<p
			v-if="notice"
			role="status"
			data-testid="sellos-media-notice"
			class="mb-ui-sm text-sm text-ink"
		>
			{{ notice }}
		</p>
		<div v-if="loadError" data-testid="sellos-media-load-error">
			<LoadError :message="loadError" @retry="load" />
		</div>
		<p
			v-if="loaded && !loadError && !media.length"
			class="text-sm text-ink-muted"
			data-testid="sellos-media-empty"
		>
			No photos or videos yet.
		</p>
		<ol class="space-y-ui-sm" data-testid="sellos-media-list">
			<li
				v-for="(m, i) in media"
				:key="m.name"
				data-testid="sellos-media-row"
				:data-title="m.title"
				:data-position="m.position"
				class="flex flex-wrap items-center gap-ui-md"
			>
				<img
					v-if="m.media_type === 'Photo'"
					:src="m.file_url"
					:alt="m.title"
					class="h-16 w-24 rounded-input object-cover"
					data-testid="sellos-media-picture"
				/>
				<video
					v-else
					:src="m.file_url"
					controls
					preload="metadata"
					class="h-16 w-24 rounded-input"
					data-testid="sellos-media-video"
				/>
				<div class="min-w-0 flex-1">
					<span class="font-medium text-ink" data-testid="sellos-media-title">
						{{ m.position }}. {{ m.title }}
					</span>
					<StatusBadge
						tone="info"
						:label="m.media_type"
						class="ml-ui-sm"
						data-testid="sellos-media-kind"
					/>
					<span class="ml-ui-sm text-sm text-ink-muted">{{ size(m.size_bytes) }}</span>
				</div>
				<div v-if="canEdit" class="flex flex-wrap gap-ui-sm">
					<AppButton
						type="button"
						:disabled="i === 0"
						:aria-label="`Move ${m.title} up`"
						data-testid="sellos-media-up"
						@click="move(i, -1)"
					>
						Move up
					</AppButton>
					<AppButton
						type="button"
						:disabled="i === media.length - 1"
						:aria-label="`Move ${m.title} down`"
						data-testid="sellos-media-down"
						@click="move(i, 1)"
					>
						Move down
					</AppButton>
					<AppButton
						type="button"
						:aria-label="`Remove ${m.title} from the listing`"
						data-testid="sellos-media-remove"
						@click="
							act(
								() => mediaApi.unlink(listing, m.name),
								`${m.title} was taken off.`
							)
						"
					>
						Remove
					</AppButton>
				</div>
			</li>
		</ol>

		<div v-if="canEdit" class="mt-ui-md grid grid-cols-1 gap-ui-md md:grid-cols-2">
			<FormField
				v-model="title"
				label="Title of the new file"
				hint="Leave it blank to use the file's name."
				data-testid="sellos-media-title-field"
			/>
			<FileField
				label="Photo or video"
				:accept="accept"
				:hint="`A ${allowed} file. A photo can be up to ${limits.photo_mb} MB and a video up to ${limits.video_mb} MB.`"
				data-testid="sellos-media-file"
				@change="upload"
			/>
			<FormField
				v-model="chosen"
				type="select"
				label="Or link a file from the library"
				:options="libraryOptions"
				data-testid="sellos-media-library"
			/>
			<div class="flex items-end">
				<AppButton
					type="button"
					:disabled="!chosen"
					data-testid="sellos-media-link"
					@click="link"
				>
					Link this file
				</AppButton>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import FileField from "../components/FileField.vue";
import FormField from "../components/FormField.vue";
import LoadError from "../components/LoadError.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { readFileBase64 } from "../company/partnersApi";
import { serverMessage } from "../crm/crmApi";
import { mediaApi } from "./inventoryApi";

// The photos and videos of one listing (SOS-P4-03). Every change is made on the server and read back, so the
// order and the files shown are the ones saved. The server decides what is a valid file.
const props = defineProps({ listing: { type: String, required: true } });
const emit = defineEmits(["changed"]);

const media = ref([]);
const library = ref([]);
const canEdit = ref(false);
const limits = ref({ photo_mb: 5, video_mb: 20 });
const allowed = ref("JPG, PNG, WEBP, MP4, MOV or WEBM");
const accept = ".jpg,.jpeg,.png,.webp,.mp4,.mov,.webm";
const title = ref("");
const chosen = ref("");
const error = ref("");
const notice = ref("");
const loadError = ref("");
const loaded = ref(false);

const libraryOptions = computed(() => [
	{ label: "Choose a file", value: "" },
	...library.value
		.filter((a) => !a.linked)
		.map((a) => ({ label: `${a.title} (${a.media_type})`, value: a.name })),
]);

const size = (bytes) =>
	bytes >= 1048576
		? `${(bytes / 1048576).toFixed(1)} MB`
		: `${Math.max(1, Math.round(bytes / 1024))} KB`;

function show(data) {
	media.value = data.media;
	library.value = data.library;
	canEdit.value = data.can_edit;
	limits.value = data.limits;
	allowed.value = data.allowed;
}

async function load() {
	loadError.value = "";
	try {
		show(await mediaApi.get(props.listing));
	} catch (e) {
		loadError.value = serverMessage(e, "The photos and videos could not be loaded.");
	} finally {
		loaded.value = true;
	}
}

async function act(action, message) {
	error.value = "";
	notice.value = "";
	try {
		show(await action());
		notice.value = message;
		emit("changed");
		return true;
	} catch (e) {
		error.value = serverMessage(e, "The change could not be saved.");
		return false;
	}
}

async function upload(event) {
	const file = event.target.files?.[0];
	if (!file) return;
	if (file.size > limits.value.video_mb * 1048576) {
		error.value = `A file can be up to ${limits.value.video_mb} MB.`;
		event.target.value = "";
		return;
	}
	const name = title.value || file.name;
	const done = await act(
		async () =>
			mediaApi.upload(props.listing, title.value, file.name, await readFileBase64(file)),
		`${name} was added.`
	);
	if (done) title.value = "";
	event.target.value = "";
}

const link = async () => {
	if (await act(() => mediaApi.link(props.listing, chosen.value), "The file was linked.")) {
		chosen.value = "";
	}
};

function move(index, step) {
	const order = media.value.map((m) => m.name);
	[order[index], order[index + step]] = [order[index + step], order[index]];
	return act(() => mediaApi.reorder(props.listing, order), "The order was saved.");
}

onMounted(load);
</script>
