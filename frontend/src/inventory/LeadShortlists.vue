<template>
	<SectionCard title="Shortlists" data-testid="sellos-lead-shortlists">
		<p class="mb-ui-sm ui-text-muted">
			Homes for this buyer, in the order you choose, shared as a link to their own view or as
			a PDF. Add homes from the matching homes above.
		</p>
		<AppButton type="button" data-testid="sellos-shortlist-new" @click="create">
			New shortlist
		</AppButton>
		<p
			v-if="error"
			role="alert"
			data-testid="sellos-shortlist-error"
			class="mt-ui-sm ui-text-error"
		>
			{{ error }}
		</p>
		<EmptyState
			v-if="loaded && !rows.length"
			title="No shortlist yet"
			text="Make one, or press Add to shortlist on a matching home."
			icon="lucide-list-checks"
		/>
		<ul class="mt-ui-sm ui-list">
			<li
				v-for="row in rows"
				:key="row.name"
				class="space-y-ui-sm"
				data-testid="sellos-shortlist-row"
				:data-name="row.name"
			>
				<div class="flex flex-wrap items-center gap-3">
					<span class="ui-text-strong">{{ row.title }}</span>
					<StatusBadge
						:tone="row.shared ? 'success' : 'neutral'"
						:label="row.shared ? 'Shared' : 'Draft'"
					/>
					<span class="ui-text-muted">{{ row.item_count }} homes</span>
					<AppButton
						type="button"
						data-testid="sellos-shortlist-open"
						@click="open(row.name)"
					>
						{{ current && current.name === row.name ? "Close" : "Open" }}
					</AppButton>
				</div>
				<div
					v-if="current && current.name === row.name"
					class="mt-ui-md space-y-ui-md"
					data-testid="sellos-shortlist-editor"
					:data-name="current.name"
				>
					<div class="flex flex-wrap items-end gap-ui-sm">
						<FormField
							v-model="title"
							label="Title"
							class="w-72"
							data-testid="sellos-shortlist-title"
						/>
						<FormField
							v-model="note"
							label="Note to the buyer"
							class="w-96"
							data-testid="sellos-shortlist-note"
						/>
						<AppButton
							type="button"
							data-testid="sellos-shortlist-save"
							@click="saveHead"
						>
							Save
						</AppButton>
					</div>
					<EmptyState
						v-if="!current.items.length"
						title="No homes yet"
						text="Add homes from the matching homes above."
						icon="lucide-building"
					/>
					<ol class="ui-list">
						<li
							v-for="(item, index) in current.items"
							:key="item.name"
							class="space-y-ui-sm"
							data-testid="sellos-shortlist-item"
							:data-title="item.title"
							:data-unavailable="item.unavailable"
						>
							<div class="flex flex-wrap items-center gap-3">
								<span class="ui-text-strong">
									{{ index + 1 }}. {{ item.title }}
								</span>
								<StatusBadge tone="info" :label="item.kind" />
								<span class="ui-text-muted">
									{{ item.price ? rupees(item.price) : "No price yet" }}
								</span>
								<StatusBadge
									v-if="item.unavailable"
									tone="danger"
									:label="item.reason"
									data-testid="sellos-shortlist-unavailable"
								/>
								<span
									class="ui-text-muted"
									data-testid="sellos-shortlist-opened"
									:data-count="item.opened.count"
								>
									{{ openedText(item.opened) }}
								</span>
							</div>
							<div class="mt-ui-sm flex flex-wrap items-end gap-ui-sm">
								<FormField
									v-model="notes[item.name]"
									label="Note on this home"
									class="w-96"
									data-testid="sellos-shortlist-item-note"
								/>
								<AppButton
									type="button"
									data-testid="sellos-shortlist-item-save"
									@click="saveNote(item)"
								>
									Save note
								</AppButton>
								<AppButton
									type="button"
									:disabled="index === 0"
									data-testid="sellos-shortlist-up"
									@click="move(index, -1)"
								>
									Move up
								</AppButton>
								<AppButton
									type="button"
									:disabled="index === current.items.length - 1"
									data-testid="sellos-shortlist-down"
									@click="move(index, 1)"
								>
									Move down
								</AppButton>
								<AppButton
									type="button"
									data-testid="sellos-shortlist-remove"
									@click="remove(item)"
								>
									Remove
								</AppButton>
							</div>
						</li>
					</ol>
					<div class="flex flex-wrap items-center gap-ui-sm">
						<AppButton
							type="button"
							variant="primary"
							data-testid="sellos-shortlist-share-link"
							@click="share('Link')"
						>
							Share link
						</AppButton>
						<AppButton
							type="button"
							data-testid="sellos-shortlist-share-pdf"
							@click="share('PDF')"
						>
							Share PDF
						</AppButton>
						<a
							class="ui-link"
							:href="pdfUrl(current.name)"
							target="_blank"
							rel="noopener"
							data-testid="sellos-shortlist-pdf"
						>
							Download PDF
						</a>
						<AppButton
							type="button"
							data-testid="sellos-shortlist-archive"
							@click="archive"
						>
							Archive
						</AppButton>
					</div>
					<p
						v-if="notice"
						role="status"
						data-testid="sellos-shortlist-notice"
						class="ui-text-small"
					>
						{{ notice }}
					</p>
					<p v-if="shared" class="ui-text-muted" data-testid="sellos-shortlist-link">
						{{ shared.link }}
					</p>
					<p v-if="current.shared" class="ui-text-muted">
						Shared {{ current.share_count }} time(s), last on
						{{ whenText(current.shared_on) }}. {{ current.opened_count }} of
						{{ current.item_count }} homes opened by the buyer.
					</p>
				</div>
			</li>
		</ul>
	</SectionCard>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";

import AppButton from "../components/AppButton.vue";
import EmptyState from "../components/EmptyState.vue";
import FormField from "../components/FormField.vue";
import SectionCard from "../components/SectionCard.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { serverMessage } from "../crm/crmApi";
import { rupees, shortlistApi, whenText } from "./inventoryApi";

// A lead's shortlists: build one, order it, add a note to each home, share it, and see which homes the buyer
// opened and when (SOS-P7-09).
const props = defineProps({ lead: { type: String, required: true } });

const rows = ref([]);
const loaded = ref(false);
const current = ref(null);
const title = ref("");
const note = ref("");
const notes = reactive({});
const error = ref("");
const notice = ref("");
const shared = ref(null);

const pdfUrl = (name) =>
	`/api/method/sellos.inventory.shortlists.shortlist_pdf?name=${encodeURIComponent(name)}`;

function openedText(opened) {
	if (!opened.count) return "Not opened yet";
	return `Opened ${opened.count} time(s), last on ${whenText(opened.last)}`;
}

async function run(action, fallback) {
	error.value = "";
	try {
		return await action();
	} catch (e) {
		error.value = serverMessage(e, fallback);
		return null;
	}
}

async function reload() {
	const result = await run(
		() => shortlistApi.list(props.lead),
		"The shortlists could not be loaded."
	);
	if (result) {
		rows.value = result.shortlists;
		loaded.value = true;
	}
	if (current.value) await show(current.value.name);
}

function show(name) {
	return run(async () => {
		const view = await shortlistApi.get(name);
		take(view);
	}, "The shortlist could not be loaded.");
}

function take(view) {
	current.value = view;
	title.value = view.title;
	note.value = view.note;
	for (const key of Object.keys(notes)) delete notes[key];
	for (const item of view.items) notes[item.name] = item.note;
	const row = rows.value.find((r) => r.name === view.name);
	if (row) {
		row.title = view.title;
		row.item_count = view.item_count;
		row.shared = view.shared;
	}
}

async function open(name) {
	notice.value = "";
	shared.value = null;
	if (current.value && current.value.name === name) {
		current.value = null;
		return;
	}
	await show(name);
}

async function create() {
	notice.value = "";
	const view = await run(
		() => shortlistApi.create(props.lead),
		"The shortlist could not be made."
	);
	if (!view) return;
	await reload();
	await open(view.name);
}

async function change(action, fallback, message = "") {
	notice.value = "";
	const view = await run(action, fallback);
	if (view) {
		take(view);
		notice.value = message;
	}
	return view;
}

const saveHead = () =>
	change(
		() => shortlistApi.update(current.value.name, { title: title.value, note: note.value }),
		"The shortlist could not be saved.",
		"The shortlist is saved."
	);
const saveNote = (item) =>
	change(
		() => shortlistApi.saveNote(current.value.name, item.name, notes[item.name]),
		"The note could not be saved.",
		"The note is saved."
	);
const remove = (item) =>
	change(
		() => shortlistApi.remove(current.value.name, item.name),
		"The home could not be removed.",
		"The home is removed."
	);

function move(index, step) {
	const order = current.value.items.map((i) => i.name);
	[order[index], order[index + step]] = [order[index + step], order[index]];
	return change(
		() => shortlistApi.reorder(current.value.name, order),
		"The order could not be saved.",
		"The order is saved."
	);
}

async function archive() {
	const name = current.value.name;
	if (!(await change(() => shortlistApi.archive(name), "The shortlist could not be archived.")))
		return;
	current.value = null;
	await reload();
}

async function share(via) {
	notice.value = "";
	const result = await run(
		() => shortlistApi.share(current.value.name, via),
		"The shortlist could not be shared."
	);
	if (!result) return;
	take(result.shortlist);
	shared.value = result;
	notice.value = result.emailed
		? `Shared as a ${via === "PDF" ? "PDF" : "link"} and emailed to the buyer.`
		: `Shared as a ${
				via === "PDF" ? "PDF" : "link"
		  }. The buyer was not emailed, so send them the link.`;
}

onMounted(reload);
defineExpose({ reload });
</script>
