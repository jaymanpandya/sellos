<template>
	<div v-if="detail" class="max-w-3xl" data-testid="sellos-lead-page">
		<router-link :to="listPath" data-testid="sellos-lead-back" class="text-sm text-ink-muted"
			>Back to leads</router-link
		>
		<div class="mt-2 flex items-start justify-between gap-3">
			<div>
				<h1 class="ui-page-title" data-testid="sellos-lead-name">
					{{ detail.client.client_name }}
				</h1>
				<p class="text-sm text-ink-muted">
					{{ detail.client.client_type }} ·
					<span data-testid="sellos-lead-phone">{{
						detail.client.phone || "No phone"
					}}</span>
					<span v-if="detail.client.overseas_phone">
						· {{ detail.client.overseas_phone }}</span
					>
				</p>
			</div>
			<button
				v-if="canLog"
				type="button"
				class="btn"
				data-testid="sellos-lead-archive"
				@click="archive"
			>
				Archive
			</button>
		</div>

		<section
			v-if="canReassign"
			data-testid="sellos-reassign"
			class="mt-4 space-y-2 rounded-input border border-line bg-surface p-4"
		>
			<h2 class="font-medium text-ink">Assigned agent</h2>
			<p class="text-sm text-ink-muted">
				Now:
				<span data-testid="sellos-reassign-current">{{
					detail.lead.assigned_to || "Nobody"
				}}</span>
			</p>
			<select
				:value="detail.lead.assigned_to || ''"
				aria-label="Assign to"
				data-testid="sellos-reassign-select"
				class="field"
				@change="reassign($event.target.value)"
			>
				<option value="" disabled>Choose an agent</option>
				<option v-for="a in assignees" :key="a.user" :value="a.user">
					{{ a.full_name }}
				</option>
			</select>
			<p
				v-if="reassignError"
				role="alert"
				data-testid="sellos-reassign-error"
				class="text-sm text-accent"
			>
				{{ reassignError }}
			</p>
			<ul
				v-if="detail.assignments && detail.assignments.length"
				class="text-sm text-ink-muted"
				data-testid="sellos-assignment-log"
			>
				<li
					v-for="a in detail.assignments"
					:key="a.name"
					data-testid="sellos-assignment-entry"
				>
					{{ a.method }}: {{ a.from_name || a.from_agent || "nobody" }} to
					{{ a.to_name || a.to_agent || "nobody" }}
				</li>
			</ul>
		</section>

		<section
			v-if="detail.can_merge"
			data-testid="sellos-merge"
			class="mt-4 space-y-2 rounded-input border border-line bg-surface p-4"
		>
			<h2 class="font-medium text-ink">Merge a duplicate client</h2>
			<p class="text-sm text-ink-muted">
				Move another client's leads, activities, tasks and site visits to
				{{ detail.client.client_name }}. The other client is archived, not deleted.
			</p>
			<select v-model="mergeFrom" data-testid="sellos-merge-select" class="field">
				<option value="">Choose the duplicate client</option>
				<option v-for="c in mergeChoices" :key="c.name" :value="c.name">
					{{ c.client_name }} {{ c.phone }}
				</option>
			</select>
			<p
				v-if="mergeError"
				role="alert"
				data-testid="sellos-merge-error"
				class="text-sm text-accent"
			>
				{{ mergeError }}
			</p>
			<p v-if="mergeDone" data-testid="sellos-merge-done" class="text-sm text-ink-muted">
				{{ mergeDone }}
			</p>
			<button
				type="button"
				class="btn"
				:disabled="!mergeFrom"
				data-testid="sellos-merge-save"
				@click="merge"
			>
				Merge into {{ detail.client.client_name }}
			</button>
		</section>

		<section
			v-if="detail.pipeline"
			data-testid="sellos-lead-stage"
			:data-stage="detail.pipeline.stage"
			class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
		>
			<div class="flex flex-wrap items-center justify-between gap-2">
				<h2 class="font-medium text-ink">Stage</h2>
				<select
					v-if="canLog"
					:key="stageSelectKey"
					:value="detail.pipeline.stage"
					class="field max-w-[14rem]"
					aria-label="Stage"
					data-testid="sellos-lead-stage-select"
					@change="chooseStage($event.target.value)"
				>
					<option v-for="s in detail.pipeline.stages" :key="s.name" :value="s.name">
						{{ s.name }}
					</option>
				</select>
				<span v-else data-testid="sellos-lead-stage-name" class="text-sm text-ink-muted">{{
					detail.pipeline.stage
				}}</span>
			</div>
			<form
				v-if="lostStage"
				class="flex flex-wrap items-center gap-2"
				data-testid="sellos-lead-lost-form"
				@submit.prevent="confirmLost"
			>
				<label class="text-sm text-ink-muted" for="sellos-lead-lost-reason">
					Why is this lead going to {{ lostStage }}?
				</label>
				<select
					id="sellos-lead-lost-reason"
					v-model="lostReason"
					required
					class="field w-auto"
					data-testid="sellos-lead-lost-reason"
				>
					<option value="">Choose a lost reason</option>
					<option v-for="r in lostReasons" :key="r.name" :value="r.name">
						{{ r.name }}
					</option>
				</select>
				<button type="submit" class="btn" data-testid="sellos-lead-lost-save">
					Move to {{ lostStage }}
				</button>
				<button
					type="button"
					class="text-sm text-ink-muted underline"
					data-testid="sellos-lead-lost-cancel"
					@click="cancelLost"
				>
					Cancel
				</button>
			</form>
			<p
				v-if="detail.pipeline.lost_reason"
				data-testid="sellos-lead-lost-reason-shown"
				class="text-sm text-ink-muted"
			>
				Lost reason: {{ detail.pipeline.lost_reason }}
			</p>
			<p
				v-if="stageWarning"
				role="alert"
				data-testid="sellos-lead-stage-warning"
				:data-level="stageWarning.level"
				class="rounded-input border px-3 py-2 text-sm"
				:class="
					stageWarning.level === 'red'
						? 'border-[#c0392b] bg-[#fdecea] text-[#8e1f14]'
						: 'border-[#e8954a] bg-[#fdf1e3] text-[#7a4a10]'
				"
			>
				{{ stageWarning.message }}
			</p>
			<p
				v-if="stageError"
				role="alert"
				data-testid="sellos-lead-stage-error"
				class="text-sm text-accent"
			>
				{{ stageError }}
			</p>
			<ul v-if="detail.pipeline.log.length" data-testid="sellos-lead-stage-log">
				<li
					v-for="(row, i) in detail.pipeline.log"
					:key="i"
					data-testid="sellos-lead-stage-change"
					class="text-sm text-ink-muted"
				>
					{{ row.from_stage || "No stage" }} to {{ row.to_stage }},
					{{ String(row.changed_on).slice(0, 16) }}, {{ row.changed_by }}
					<span v-if="row.lost_reason" data-testid="sellos-lead-stage-change-reason">
						. Lost reason: {{ row.lost_reason }}</span
					>
					<span v-if="row.warning" data-testid="sellos-lead-stage-change-warning">
						. {{ row.warning }}</span
					>
				</li>
			</ul>
		</section>

		<section
			v-if="detail.consent"
			data-testid="sellos-lead-consent"
			:data-status="detail.consent.status"
			class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
		>
			<div class="flex flex-wrap items-center justify-between gap-2">
				<h2 class="font-medium text-ink">Consent</h2>
				<span data-testid="sellos-lead-consent-status" class="text-sm text-ink-muted">{{
					detail.consent.status
				}}</span>
			</div>
			<p
				v-if="detail.consent.warning"
				role="alert"
				data-testid="sellos-lead-consent-warning"
				:data-level="detail.consent.warning"
				class="rounded-input border px-3 py-2 text-sm"
				:class="
					detail.consent.warning === 'red'
						? 'border-[#c0392b] bg-[#fdecea] text-[#8e1f14]'
						: 'border-[#e8954a] bg-[#fdf1e3] text-[#7a4a10]'
				"
			>
				{{ detail.consent.message }} You can still call and message this lead.
			</p>
			<ul v-if="detail.consent.records.length" data-testid="sellos-lead-consent-records">
				<li
					v-for="record in detail.consent.records"
					:key="record.name"
					data-testid="sellos-lead-consent-record"
					class="text-sm text-ink-muted"
				>
					{{ record.basis }}, {{ String(record.recorded_on).slice(0, 16) }},
					{{
						record.expires_on
							? (record.live ? "expires " : "expired ") +
							  String(record.expires_on).slice(0, 16)
							: "no expiry"
					}}
					<span v-if="record.renewal_count">, renewal {{ record.renewal_count }}</span>
					<a
						:href="record.evidence_link"
						target="_blank"
						rel="noopener"
						class="ml-1 underline"
						>Evidence</a
					>
				</li>
			</ul>
			<template v-if="canLog">
				<form
					class="flex flex-wrap gap-2"
					data-testid="sellos-lead-consent-form"
					@submit.prevent="addConsent"
				>
					<select
						v-model="consentForm.basis"
						data-testid="sellos-lead-consent-basis"
						class="field w-auto"
					>
						<option v-for="b in CONSENT_BASES" :key="b">{{ b }}</option>
					</select>
					<input
						v-model="consentForm.evidence"
						data-testid="sellos-lead-consent-evidence"
						required
						placeholder="Evidence link"
						class="field flex-1"
					/>
					<button type="submit" class="btn" data-testid="sellos-lead-consent-save">
						Record basis
					</button>
				</form>
				<p
					v-if="consentError"
					data-testid="sellos-lead-consent-error"
					class="text-sm text-accent"
				>
					{{ consentError }}
				</p>
				<div class="flex flex-wrap gap-2">
					<select
						v-model="stopSource"
						data-testid="sellos-lead-optout-source"
						class="field w-auto"
					>
						<option v-for="s in STOP_SOURCES" :key="s">{{ s }}</option>
					</select>
					<button
						type="button"
						class="btn"
						data-testid="sellos-lead-optout"
						@click="optOut"
					>
						Record stop request
					</button>
					<button
						type="button"
						class="btn"
						data-testid="sellos-lead-dnd"
						@click="setDnd(1)"
					>
						Number is on the DND list
					</button>
					<button
						v-if="detail.consent.status === 'Registered DND'"
						type="button"
						class="btn"
						data-testid="sellos-lead-dnd-clear"
						@click="setDnd(0)"
					>
						Number is not on the DND list
					</button>
				</div>
			</template>
		</section>

		<section
			data-testid="sellos-lead-requirements"
			class="mt-4 space-y-3 rounded-input border border-line bg-surface p-4"
		>
			<h2 class="font-medium text-ink">Requirements</h2>
			<form v-if="canLog" class="space-y-3" @submit.prevent="saveRequirements">
				<div class="flex flex-wrap gap-2">
					<input
						v-model.number="req.budget_from"
						data-testid="sellos-lead-req-budget-from"
						type="number"
						min="0"
						placeholder="Budget from (rupees)"
						class="field flex-1"
					/>
					<input
						v-model.number="req.budget_to"
						data-testid="sellos-lead-req-budget-to"
						type="number"
						min="0"
						placeholder="Budget to (rupees)"
						class="field flex-1"
					/>
				</div>
				<fieldset class="flex flex-wrap gap-3 text-sm text-ink">
					<legend class="text-ink-muted">Configuration</legend>
					<label v-for="c in CONFIGURATIONS" :key="c" class="flex items-center gap-1">
						<input
							v-model="req.configuration"
							type="checkbox"
							:value="c"
							data-testid="sellos-lead-req-configuration"
						/>
						{{ c }}
					</label>
				</fieldset>
				<div class="flex flex-wrap gap-2">
					<select
						v-model="req.property_type"
						data-testid="sellos-lead-req-property-type"
						class="field w-auto"
					>
						<option value="">Property type</option>
						<option v-for="o in PROPERTY_TYPES" :key="o">{{ o }}</option>
					</select>
					<select
						v-model="req.purpose"
						data-testid="sellos-lead-req-purpose"
						class="field w-auto"
					>
						<option value="">Purpose</option>
						<option v-for="o in PURPOSES" :key="o">{{ o }}</option>
					</select>
					<select
						v-model="req.timeline"
						data-testid="sellos-lead-req-timeline"
						class="field w-auto"
					>
						<option value="">Timeline</option>
						<option v-for="o in TIMELINES" :key="o">{{ o }}</option>
					</select>
					<select
						v-model="req.possession"
						data-testid="sellos-lead-req-possession"
						class="field w-auto"
					>
						<option value="">Possession</option>
						<option v-for="o in POSSESSIONS" :key="o">{{ o }}</option>
					</select>
				</div>
				<input
					v-model="req.localities"
					data-testid="sellos-lead-req-localities"
					placeholder="Preferred localities, separated by commas"
					class="field"
				/>
				<p
					v-if="requirementsError"
					role="alert"
					data-testid="sellos-lead-req-error"
					class="text-sm text-accent"
				>
					{{ requirementsError }}
				</p>
				<button type="submit" class="btn" data-testid="sellos-lead-req-save">
					Save requirements
				</button>
			</form>
			<p data-testid="sellos-lead-req-summary" class="text-sm text-ink-muted">
				{{ summary }}
			</p>
		</section>

		<section
			data-testid="sellos-lead-follow-up"
			:data-state="followUp.follow_up_state || 'none'"
			class="mt-6 flex flex-wrap items-center gap-3 rounded-input border border-line bg-surface p-4"
		>
			<h2 class="font-medium text-ink">Next follow up</h2>
			<span
				v-if="followUp.next_follow_up"
				data-testid="sellos-lead-next-follow-up"
				class="text-ink"
			>
				{{ followUp.next_follow_up_title }}, {{ whenLabel(followUp.next_follow_up) }}
			</span>
			<span v-else data-testid="sellos-lead-next-follow-up" class="text-ink-muted">
				No open follow up
			</span>
			<span
				v-if="followUp.follow_up_state === 'overdue'"
				data-testid="sellos-lead-follow-up-overdue"
				class="rounded-input bg-accent px-2 py-1 text-xs text-white"
				>Overdue</span
			>
			<span
				v-if="followUp.follow_up_untouched"
				data-testid="sellos-lead-follow-up-untouched"
				class="rounded-input border border-accent px-2 py-1 text-xs text-accent"
				>Untouched, no follow up for {{ followUp.untouched_days }} days</span
			>
		</section>

		<section
			v-if="canLog"
			data-testid="sellos-lead-call"
			class="mt-6 space-y-3 rounded-input border border-line bg-surface p-4"
		>
			<h2 class="font-medium text-ink">Log a call</h2>
			<form class="space-y-3" data-testid="sellos-lead-call-form" @submit.prevent="logCall">
				<div class="flex flex-wrap gap-2">
					<select
						v-model="call.outcome"
						required
						aria-label="Outcome"
						data-testid="sellos-lead-call-outcome"
						class="field w-auto"
					>
						<option value="">Outcome</option>
						<option v-for="o in outcomes" :key="o.name" :value="o.name">
							{{ o.name }}
						</option>
					</select>
					<input
						v-model.number="call.minutes"
						type="number"
						min="0"
						step="any"
						aria-label="Duration in minutes"
						placeholder="Minutes"
						data-testid="sellos-lead-call-minutes"
						class="field w-28"
					/>
					<input
						v-model="call.notes"
						placeholder="Notes"
						data-testid="sellos-lead-call-notes"
						class="field flex-1"
					/>
				</div>
				<label v-if="chosenOutcome?.needs_follow_up" class="block text-sm text-ink-muted">
					Follow up on
					<input
						v-model="call.followUp"
						required
						type="datetime-local"
						data-testid="sellos-lead-call-follow-up"
						class="field w-auto"
					/>
				</label>
				<div class="flex flex-wrap items-center gap-2">
					<select
						v-model="call.stage"
						aria-label="Stage after this call"
						data-testid="sellos-lead-call-stage"
						class="field w-auto"
					>
						<option value="">Keep the stage ({{ detail.pipeline?.stage }})</option>
						<option v-for="s in otherStages" :key="s.name" :value="s.name">
							{{ s.name }}{{ s.name === suggestedStage ? " (suggested)" : "" }}
						</option>
					</select>
					<button
						v-if="suggestedStage && call.stage !== suggestedStage"
						type="button"
						class="text-sm text-ink-muted underline"
						data-testid="sellos-lead-call-suggestion"
						@click="call.stage = suggestedStage"
					>
						Suggested stage: {{ suggestedStage }}. Use it
					</button>
					<select
						v-if="callStageIsLost"
						v-model="call.lostReason"
						required
						aria-label="Lost reason"
						data-testid="sellos-lead-call-lost-reason"
						class="field w-auto"
					>
						<option value="">Choose a lost reason</option>
						<option v-for="r in lostReasons" :key="r.name" :value="r.name">
							{{ r.name }}
						</option>
					</select>
				</div>
				<p
					v-if="callError"
					role="alert"
					data-testid="sellos-lead-call-error"
					class="text-sm text-accent"
				>
					{{ callError }}
				</p>
				<p
					v-if="callSaved"
					data-testid="sellos-lead-call-saved"
					class="text-sm text-ink-muted"
				>
					{{ callSaved }}
				</p>
				<button type="submit" class="btn" data-testid="sellos-lead-call-save">
					Log call
				</button>
			</form>
		</section>

		<section
			v-if="canLog"
			data-testid="sellos-lead-log"
			class="mt-6 space-y-3 rounded-input border border-line bg-surface p-4"
		>
			<h2 class="font-medium text-ink">Log something</h2>
			<form
				class="flex flex-wrap gap-2"
				data-testid="sellos-lead-activity-form"
				@submit.prevent="logActivity"
			>
				<select
					v-model="activity.type"
					data-testid="sellos-lead-activity-type"
					class="field w-auto"
				>
					<option v-for="t in ACTIVITY_TYPES" :key="t">{{ t }}</option>
				</select>
				<input
					v-model="activity.notes"
					data-testid="sellos-lead-activity-notes"
					placeholder="Notes"
					class="field flex-1"
				/>
				<button type="submit" class="btn" data-testid="sellos-lead-activity-save">
					Add activity
				</button>
			</form>
			<form
				class="flex flex-wrap gap-2"
				data-testid="sellos-lead-task-form"
				@submit.prevent="addTask"
			>
				<input
					v-model="task.title"
					data-testid="sellos-lead-task-title"
					required
					placeholder="Task"
					class="field flex-1"
				/>
				<input
					v-model="task.due_at"
					data-testid="sellos-lead-task-due"
					required
					type="datetime-local"
					aria-label="Follow up date and time"
					class="field w-auto"
				/>
				<button type="submit" class="btn" data-testid="sellos-lead-task-save">
					Add follow up
				</button>
			</form>
			<form
				class="flex flex-wrap gap-2"
				data-testid="sellos-lead-visit-form"
				@submit.prevent="addVisit"
			>
				<input
					v-model="visit.project_name"
					data-testid="sellos-lead-visit-project"
					required
					placeholder="Site visit: project"
					class="field flex-1"
				/>
				<input
					v-model="visit.visit_datetime"
					data-testid="sellos-lead-visit-when"
					required
					type="datetime-local"
					class="field w-auto"
				/>
				<select
					v-model="visit.agent"
					aria-label="Agent for the visit"
					data-testid="sellos-lead-visit-agent"
					class="field w-auto"
				>
					<option value="">The lead's agent</option>
					<option v-for="a in visitOptions.agents" :key="a.name" :value="a.name">
						{{ a.full_name }}
					</option>
				</select>
				<button type="submit" class="btn" data-testid="sellos-lead-visit-save">
					Add visit
				</button>
			</form>
		</section>

		<h2 class="mt-6 font-medium text-ink">Timeline</h2>
		<p
			v-if="!detail.timeline.length"
			data-testid="sellos-lead-timeline-empty"
			class="mt-2 text-ink-muted"
		>
			Nothing logged yet.
		</p>
		<ul class="mt-2 space-y-2" data-testid="sellos-lead-timeline">
			<li
				v-for="item in detail.timeline"
				data-testid="sellos-lead-timeline-item"
				:key="item.kind + item.name"
				class="rounded-input border border-line bg-surface p-3"
			>
				<div class="flex items-center justify-between gap-2">
					<span class="font-medium text-ink">
						<span class="mr-2 text-xs uppercase text-ink-muted">{{ item.kind }}</span
						>{{ item.title }}
						<span
							v-if="item.outcome"
							data-testid="sellos-lead-timeline-outcome"
							class="ml-1 text-sm text-ink-muted"
							>{{ item.outcome }}{{ callLength(item) }}</span
						>
					</span>
					<span
						v-if="item.overdue"
						data-testid="sellos-lead-timeline-overdue"
						class="rounded-input bg-accent px-2 py-1 text-xs text-white"
						>Overdue</span
					>
					<span v-else-if="item.status" class="text-xs text-ink-muted">{{
						item.status
					}}</span>
				</div>
				<p class="text-sm text-ink-muted">{{ String(item.when).slice(0, 16) }}</p>
				<p v-if="item.notes" class="mt-1 text-sm text-ink">{{ item.notes }}</p>
				<p
					v-if="item.kind === 'visit'"
					data-testid="sellos-lead-visit-confirmation"
					class="text-sm text-ink-muted"
				>
					{{ item.confirmation_status
					}}<template v-if="item.agent"> , agent {{ item.agent }}</template
					><template v-if="item.visit_outcome"
						>, outcome: {{ item.visit_outcome }}</template
					>
				</p>
				<div
					v-if="canLog && item.kind === 'visit' && item.status === 'Scheduled'"
					class="mt-2 flex flex-wrap gap-2"
				>
					<VisitConfirm
						:visit="item"
						:confirmations="visitOptions.confirmations"
						@changed="load"
					/>
					<button
						type="button"
						class="text-sm text-ink-muted underline"
						data-testid="sellos-lead-visit-done"
						@click="startVisitDone(item)"
					>
						Mark visit done
					</button>
				</div>
				<form
					v-if="visitDoing === item.name"
					class="mt-2 space-y-2"
					data-testid="sellos-lead-visit-done-form"
					@submit.prevent="finishVisitDone(item)"
				>
					<div class="flex flex-wrap gap-2">
						<select
							v-model="visitDone.outcome"
							aria-label="Outcome of the visit"
							data-testid="sellos-lead-visit-outcome"
							class="field w-auto"
						>
							<option value="">Choose the outcome</option>
							<option
								v-for="o in visitOptions.outcomes"
								:key="o.name"
								:value="o.name"
							>
								{{ o.name }}
							</option>
						</select>
						<input
							v-model="visitDone.notes"
							placeholder="Note"
							aria-label="Visit note"
							data-testid="sellos-lead-visit-outcome-notes"
							class="field flex-1"
						/>
					</div>
					<p
						v-if="visitError"
						role="alert"
						data-testid="sellos-lead-visit-error"
						class="text-sm text-accent"
					>
						{{ visitError }}
					</p>
					<div class="flex gap-2">
						<button
							type="submit"
							class="btn"
							data-testid="sellos-lead-visit-done-save"
						>
							Done
						</button>
						<button type="button" class="btn" @click="visitDoing = ''">Cancel</button>
					</div>
				</form>
				<p
					v-if="offeredStage && offeredFor === item.name"
					data-testid="sellos-lead-visit-offer"
					class="mt-2 text-sm text-ink"
				>
					Next stage: {{ offeredStage }}.
					<button
						type="button"
						class="underline"
						data-testid="sellos-lead-visit-offer-use"
						@click="acceptOffer"
					>
						Move the lead to {{ offeredStage }}
					</button>
				</p>
				<button
					v-if="canLog && item.kind === 'task' && item.status !== 'Done'"
					type="button"
					class="mt-2 text-sm text-ink-muted underline"
					data-testid="sellos-lead-task-done"
					@click="startDone(item)"
				>
					Mark done
				</button>
				<form
					v-if="doing === item.name"
					class="mt-2 space-y-2"
					data-testid="sellos-lead-done-form"
					@submit.prevent="finishDone(item)"
				>
					<p class="text-sm text-ink-muted">
						Choose how the call went, or write a note.
					</p>
					<div class="flex flex-wrap gap-2">
						<select
							v-model="doneForm.outcome"
							aria-label="Call outcome"
							data-testid="sellos-lead-done-outcome"
							class="field w-auto"
						>
							<option value="">No outcome, a note only</option>
							<option v-for="o in outcomes" :key="o.name" :value="o.name">
								{{ o.name }}
							</option>
						</select>
						<input
							v-model="doneForm.notes"
							placeholder="Note"
							aria-label="Note"
							data-testid="sellos-lead-done-notes"
							class="field flex-1"
						/>
					</div>
					<label
						v-if="doneOutcome?.needs_follow_up"
						class="block text-sm text-ink-muted"
					>
						Next follow up on
						<input
							v-model="doneForm.followUp"
							required
							type="datetime-local"
							data-testid="sellos-lead-done-follow-up"
							class="field w-auto"
						/>
					</label>
					<p
						v-if="doneError"
						role="alert"
						data-testid="sellos-lead-done-error"
						class="text-sm text-accent"
					>
						{{ doneError }}
					</p>
					<div class="flex gap-2">
						<button type="submit" class="btn" data-testid="sellos-lead-done-save">
							Done
						</button>
						<button
							type="button"
							class="btn"
							data-testid="sellos-lead-done-cancel"
							@click="doing = ''"
						>
							Cancel
						</button>
					</div>
				</form>
			</li>
		</ul>
	</div>
	<p v-else data-testid="sellos-lead-loading" class="text-ink-muted">{{ error || "Loading" }}</p>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import VisitConfirm from "../components/VisitConfirm.vue";
import { teamsApi } from "../company/teamsApi";
import { session } from "../session";

import {
	ACTIVITY_TYPES,
	CONFIGURATIONS,
	CONSENT_BASES,
	POSSESSIONS,
	PROPERTY_TYPES,
	PURPOSES,
	STOP_SOURCES,
	TIMELINES,
	crmApi,
	serverMessage,
} from "../crm/crmApi";

const route = useRoute();
const router = useRouter();
const partner = computed(() => route.meta.area === "partner");
const canLog = computed(() => !partner.value); // a partner reads the timeline but does not log
const listPath = computed(() => (partner.value ? "/partner/leads" : "/crm/leads"));
const detail = ref(null);
const error = ref("");
const activity = reactive({ type: "Call", notes: "" });
const task = reactive({ title: "", due_at: "" });
const followUp = computed(() => detail.value?.follow_up || {});
// "2030-03-04 10:30:00" shows as "4 Mar 2030, 10:30". A follow up with only a day shows the day.
function whenLabel(value) {
	const [day, time] = String(value || "").split(/[ T]/);
	const date = new Date(`${day}T00:00:00`);
	if (Number.isNaN(date.getTime())) return String(value || "");
	const label = date.toLocaleDateString("en-IN", {
		day: "numeric",
		month: "short",
		year: "numeric",
	});
	return time && followUp.value.next_follow_up_has_time
		? `${label}, ${time.slice(0, 5)}`
		: label;
}
const visit = reactive({ project_name: "", visit_datetime: "", agent: "" });
// Site visits (SOS-P1-25): the lists the forms offer, the confirmation and the outcome of a visit.
const visitOptions = ref({ agents: [], outcomes: [], confirmations: [] });
const visitDoing = ref("");
const visitDone = reactive({ outcome: "", notes: "" });
const visitError = ref("");
const offeredStage = ref("");
const offeredFor = ref("");

const req = reactive({
	budget_from: "",
	budget_to: "",
	configuration: [],
	property_type: "",
	localities: "",
	purpose: "",
	timeline: "",
	possession: "",
});
const requirementsError = ref("");
const rupees = (n) => (n ? "₹" + Number(n).toLocaleString("en-IN") : "");
const requirementRows = computed(() => {
	const r = detail.value?.requirements || {};
	return [
		[
			"Budget",
			[rupees(r.budget_from), rupees(r.budget_to)].filter(Boolean).join(" to ") || "Not set",
		],
		["Configuration", (r.configuration || []).join(", ") || "Not set"],
		["Property type", r.property_type || "Not set"],
		["Preferred localities", (r.preferred_localities || []).join(", ") || "Not set"],
		["Purpose", r.purpose || "Not set"],
		["Timeline", r.timeline || "Not set"],
		["Possession", r.possession || "Not set"],
	];
});
const summary = computed(() => requirementRows.value.map((r) => `${r[0]} ${r[1]}`).join(". "));

function fillRequirements() {
	const r = detail.value.requirements || {};
	Object.assign(req, {
		budget_from: r.budget_from ?? "",
		budget_to: r.budget_to ?? "",
		configuration: [...(r.configuration || [])],
		property_type: r.property_type || "",
		localities: (r.preferred_localities || []).join(", "),
		purpose: r.purpose || "",
		timeline: r.timeline || "",
		possession: r.possession || "",
	});
}

async function saveRequirements() {
	requirementsError.value = "";
	try {
		const { localities, ...rest } = req;
		const saved = await crmApi.saveLead(
			{
				...rest,
				budget_from: req.budget_from || 0,
				budget_to: req.budget_to || 0,
				preferred_localities: localities
					.split(",")
					.map((l) => l.trim())
					.filter(Boolean),
			},
			route.params.name
		);
		detail.value = { ...detail.value, ...saved };
		fillRequirements();
	} catch (e) {
		requirementsError.value = serverMessage(e, "The requirements could not be saved.");
	}
}

async function load() {
	try {
		detail.value = await crmApi.getLead(route.params.name);
		fillRequirements();
		await loadMergeChoices();
	} catch (e) {
		error.value = "This lead could not be opened.";
	}
}

// The stage warning (SOS-P1-07): the one a move just returned, else the one the lead screen computes.
const movedWarning = ref(null);
const stageError = ref("");
const stageWarning = computed(() => movedWarning.value || detail.value?.pipeline?.warning || null);

async function moveStage(stage, reason = null) {
	stageError.value = "";
	try {
		const result = await crmApi.moveLeadStage(route.params.name, stage, reason);
		movedWarning.value = result.warning;
		await load();
	} catch (e) {
		stageError.value = serverMessage(e, "The lead could not be moved.");
		await load();
	}
}

// Moving to a Lost stage asks for a reason from the Company Admin's list (SOS-P1-21).
const lostStage = ref("");
const lostReason = ref("");
const stageSelectKey = ref(0);
const outcomes = computed(() => detail.value?.call_lists?.outcomes || []);
const lostReasons = computed(() => detail.value?.call_lists?.lost_reasons || []);
const isLost = (name) =>
	(detail.value?.pipeline?.stages || []).find((s) => s.name === name)?.stage_type === "Lost";

function chooseStage(stage) {
	if (isLost(stage) && stage !== detail.value.pipeline.stage) {
		lostStage.value = stage;
		lostReason.value = "";
		stageError.value = "";
		return;
	}
	return moveStage(stage);
}

function cancelLost() {
	lostStage.value = "";
	stageSelectKey.value += 1; // puts the stage box back on the lead's own stage
}

async function confirmLost() {
	const stage = lostStage.value;
	lostStage.value = "";
	await moveStage(stage, lostReason.value);
	stageSelectKey.value += 1;
}

// Logging a call by hand (SOS-P1-21). The outcome's suggested stage is offered, never applied.
const call = reactive({
	outcome: "",
	minutes: "",
	notes: "",
	followUp: "",
	stage: "",
	lostReason: "",
});
const callError = ref("");
const callSaved = ref("");
const chosenOutcome = computed(() => outcomes.value.find((o) => o.name === call.outcome));
const suggestedStage = computed(() => {
	const stage = chosenOutcome.value?.suggested_stage;
	return stage && stage !== detail.value?.pipeline?.stage ? stage : "";
});
const otherStages = computed(() =>
	(detail.value?.pipeline?.stages || []).filter((s) => s.name !== detail.value.pipeline.stage)
);
const callStageIsLost = computed(() => Boolean(call.stage) && isLost(call.stage));
const callLength = (item) =>
	item.duration_seconds ? `, ${Math.round((item.duration_seconds / 60) * 10) / 10} min` : "";

async function logCall() {
	callError.value = "";
	callSaved.value = "";
	try {
		const result = await crmApi.logCall(route.params.name, {
			outcome: call.outcome,
			notes: call.notes,
			duration_seconds: call.minutes ? Math.round(call.minutes * 60) : 0,
			follow_up_at: chosenOutcome.value?.needs_follow_up ? call.followUp : null,
			stage: call.stage || null,
			lost_reason: callStageIsLost.value ? call.lostReason : null,
		});
		movedWarning.value = result.warning;
		callSaved.value = result.follow_up ? "Call logged and follow up set." : "Call logged.";
		Object.assign(call, {
			outcome: "",
			minutes: "",
			notes: "",
			followUp: "",
			stage: "",
			lostReason: "",
		});
		await load();
	} catch (e) {
		callError.value = serverMessage(e, "The call could not be logged.");
	}
}

const consentForm = reactive({ basis: "Inquiry", evidence: "" });
const consentError = ref("");
const stopSource = ref("Phone call");

async function addConsent() {
	consentError.value = "";
	try {
		await crmApi.recordConsent(route.params.name, consentForm.basis, consentForm.evidence);
		consentForm.evidence = "";
		await load();
	} catch (e) {
		consentError.value = serverMessage(e, "The consent record could not be saved.");
	}
}

async function optOut() {
	await crmApi.recordOptOut(route.params.name, stopSource.value);
	await load();
}

async function setDnd(registered) {
	await crmApi.recordDndResult(route.params.name, registered);
	await load();
}

async function logActivity() {
	await crmApi.addActivity(route.params.name, activity.type, activity.notes);
	activity.notes = "";
	await load();
}

async function addTask() {
	await crmApi.saveTask({ lead: route.params.name, ...task });
	task.title = "";
	task.due_at = "";
	await load();
}

async function addVisit() {
	await crmApi.saveSiteVisit({ lead: route.params.name, ...visit });
	visit.project_name = "";
	visit.visit_datetime = "";
	visit.agent = "";
	await load();
}

async function loadVisitOptions() {
	if (!canLog.value) return;
	try {
		visitOptions.value = await crmApi.siteVisitOptions();
	} catch (e) {
		visitError.value = serverMessage(e, "The site visit lists could not be loaded.");
	}
}

function startVisitDone(item) {
	visitDoing.value = item.name;
	visitError.value = "";
	Object.assign(visitDone, { outcome: "", notes: "" });
}

async function finishVisitDone(item) {
	visitError.value = "";
	if (!visitDone.outcome) {
		visitError.value = "Choose the outcome of the visit.";
		return;
	}
	try {
		const result = await crmApi.completeSiteVisit(
			item.name,
			visitDone.outcome,
			visitDone.notes
		);
		visitDoing.value = "";
		offeredStage.value = result.suggested_stage || "";
		offeredFor.value = item.name;
		await load();
	} catch (e) {
		visitError.value = serverMessage(e, "The visit could not be marked done.");
	}
}

// The next stage the outcome offers is moved to only when the agent accepts it.
async function acceptOffer() {
	await crmApi.moveLeadStage(route.params.name, offeredStage.value);
	offeredStage.value = "";
	await load();
}

// Marking a follow up done asks for the call outcome or a note (SOS-P1-22).
const doing = ref("");
const doneForm = reactive({ outcome: "", notes: "", followUp: "" });
const doneError = ref("");
const doneOutcome = computed(() => outcomes.value.find((o) => o.name === doneForm.outcome));

function startDone(item) {
	doing.value = item.name;
	doneError.value = "";
	Object.assign(doneForm, { outcome: "", notes: "", followUp: "" });
}

async function finishDone(item) {
	doneError.value = "";
	if (!doneForm.outcome && !doneForm.notes.trim()) {
		doneError.value = "Choose the call outcome or write a note.";
		return;
	}
	try {
		await crmApi.completeFollowUp(item.name, {
			outcome: doneForm.outcome,
			notes: doneForm.notes,
			follow_up_at: doneOutcome.value?.needs_follow_up ? doneForm.followUp : null,
		});
		doing.value = "";
		await load();
	} catch (e) {
		doneError.value = serverMessage(e, "The follow up could not be marked done.");
	}
}

const mergeFrom = ref("");
const mergeChoices = ref([]);
const mergeError = ref("");
const mergeDone = ref("");

async function loadMergeChoices() {
	if (!detail.value?.can_merge) return;
	try {
		const clients = await crmApi.listClients();
		mergeChoices.value = clients.filter((c) => c.name !== detail.value.lead.client);
	} catch (e) {
		mergeChoices.value = [];
	}
}

// A Company Admin merges a duplicate client into this lead's client (SOS-P1-16).
async function merge() {
	mergeError.value = "";
	mergeDone.value = "";
	try {
		const result = await crmApi.mergeClients(detail.value.lead.client, mergeFrom.value);
		mergeDone.value = `Merged. ${result.leads_moved} lead(s) moved.`;
		mergeFrom.value = "";
		await load();
	} catch (e) {
		mergeError.value = serverMessage(e, "The clients could not be merged.");
	}
}

// Reassigning (SOS-P1-18): a Company Admin picks any agent, a Sales Manager one of its own team.
const canReassign = computed(
	() =>
		!partner.value &&
		(session.roles.includes("SellOS Company Admin") ||
			session.roles.includes("SellOS Sales Manager"))
);
const assignees = ref([]);
const reassignError = ref("");

async function loadAssignees() {
	if (!canReassign.value) return;
	try {
		const data = await teamsApi.list();
		assignees.value = data.agents
			? data.agents.map((a) => ({ user: a.name, full_name: a.full_name }))
			: data.teams.flatMap((t) => t.members);
	} catch (e) {
		reassignError.value = serverMessage(e, "The agents could not be loaded.");
	}
}

async function reassign(user) {
	reassignError.value = "";
	try {
		await teamsApi.reassign(route.params.name, user);
	} catch (e) {
		reassignError.value = serverMessage(e, "The lead could not be reassigned.");
	}
	await load();
}

async function archive() {
	await crmApi.setArchived("Lead", route.params.name);
	router.push(listPath.value);
}

onMounted(() => {
	load();
	loadAssignees();
	loadVisitOptions();
});
</script>
