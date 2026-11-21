<template>
	<div v-if="detail" data-testid="sellos-lead-page">
		<router-link :to="listPath" data-testid="sellos-lead-back" class="ui-link text-sm"
			>Back to leads</router-link
		>
		<div class="mt-2 flex flex-wrap items-start justify-between gap-ui-md">
			<div>
				<h1 class="ui-page-title" data-testid="sellos-lead-name">
					{{ detail.client.client_name }}
				</h1>
				<p class="ui-page-lead">
					{{ detail.client.client_type }} ·
					<span data-testid="sellos-lead-phone">{{
						detail.client.phone || "No phone"
					}}</span>
					<span v-if="detail.client.overseas_phone">
						· {{ detail.client.overseas_phone }}</span
					>
				</p>
			</div>
			<div v-if="canLog" class="flex flex-wrap items-center gap-ui-sm">
				<ClickToCall :lead="route.params.name" check-pending @done="load" />
				<AppButton type="button" data-testid="sellos-lead-archive" @click="archive">
					Archive
				</AppButton>
			</div>
		</div>

		<div
			class="mt-ui-lg grid grid-cols-1 gap-ui-md lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]"
		>
			<div class="min-w-0 space-y-ui-md">
				<ListCard
					v-if="detail.pipeline"
					title="Stage"
					data-testid="sellos-lead-stage"
					:data-stage="detail.pipeline.stage"
					class="space-y-ui-md"
				>
					<div class="flex flex-wrap items-end justify-between gap-ui-sm">
						<FormField
							v-if="canLog"
							:key="stageSelectKey"
							type="select"
							label="Stage"
							class="w-full max-w-[14rem]"
							:model-value="detail.pipeline.stage"
							:options="stageOptions"
							data-testid="sellos-lead-stage-select"
							@update:model-value="chooseStage"
						/>
						<StatusBadge
							v-else
							tone="info"
							:label="detail.pipeline.stage"
							data-testid="sellos-lead-stage-name"
						/>
					</div>
					<form
						v-if="lostStage"
						class="flex flex-wrap items-end gap-ui-sm"
						data-testid="sellos-lead-lost-form"
						@submit.prevent="confirmLost"
					>
						<FormField
							v-model="lostReason"
							type="select"
							:label="`Why is this lead going to ${lostStage}?`"
							required
							:options="lostReasonOptions"
							data-testid="sellos-lead-lost-reason"
						/>
						<AppButton
							variant="primary"
							type="submit"
							data-testid="sellos-lead-lost-save"
						>
							Move to {{ lostStage }}
						</AppButton>
						<AppButton
							type="button"
							data-testid="sellos-lead-lost-cancel"
							@click="cancelLost"
						>
							Cancel
						</AppButton>
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
								? 'border-tone-danger-line bg-tone-danger-bg text-tone-danger'
								: 'border-tone-warning-line bg-tone-warning-bg text-tone-warning'
						"
					>
						{{ stageWarning.message }}
					</p>
					<p
						v-if="stageError"
						role="alert"
						data-testid="sellos-lead-stage-error"
						class="text-sm text-danger"
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
							<span
								v-if="row.lost_reason"
								data-testid="sellos-lead-stage-change-reason"
							>
								. Lost reason: {{ row.lost_reason }}</span
							>
							<span
								v-if="row.warning"
								data-testid="sellos-lead-stage-change-warning"
							>
								. {{ row.warning }}</span
							>
						</li>
					</ul>
				</ListCard>

				<ListCard
					title="Requirements"
					data-testid="sellos-lead-requirements"
					class="space-y-ui-md"
				>
					<form v-if="canLog" class="space-y-ui-md" @submit.prevent="saveRequirements">
						<div class="grid grid-cols-1 gap-ui-md sm:grid-cols-2">
							<MoneyField
								v-model="req.budget_from"
								label="Budget from (₹)"
								data-testid="sellos-lead-req-budget-from"
							/>
							<MoneyField
								v-model="req.budget_to"
								label="Budget to (₹)"
								data-testid="sellos-lead-req-budget-to"
							/>
						</div>
						<fieldset class="flex flex-wrap gap-ui-md text-sm text-ink">
							<legend class="mb-1 text-ink-body">Configuration</legend>
							<FormField
								v-for="c in CONFIGURATIONS"
								:key="c"
								type="checkbox"
								:label="c"
								:value="c"
								:model-value="req.configuration.includes(c)"
								data-testid="sellos-lead-req-configuration"
								@update:model-value="toggleConfiguration(c, $event)"
							/>
						</fieldset>
						<div class="grid grid-cols-1 gap-ui-md sm:grid-cols-2">
							<FormField
								v-model="req.property_type"
								type="select"
								label="Property type"
								:options="withBlank(PROPERTY_TYPES, 'Not set')"
								data-testid="sellos-lead-req-property-type"
							/>
							<FormField
								v-model="req.purpose"
								type="select"
								label="Purpose"
								:options="withBlank(PURPOSES, 'Not set')"
								data-testid="sellos-lead-req-purpose"
							/>
							<FormField
								v-model="req.timeline"
								type="select"
								label="Timeline"
								:options="withBlank(TIMELINES, 'Not set')"
								data-testid="sellos-lead-req-timeline"
							/>
							<FormField
								v-model="req.possession"
								type="select"
								label="Possession"
								:options="withBlank(POSSESSIONS, 'Not set')"
								data-testid="sellos-lead-req-possession"
							/>
						</div>
						<FormField
							v-model="req.localities"
							label="Preferred localities"
							hint="Separate them with commas."
							data-testid="sellos-lead-req-localities"
						/>
						<p
							v-if="requirementsError"
							role="alert"
							data-testid="sellos-lead-req-error"
							class="text-sm text-danger"
						>
							{{ requirementsError }}
						</p>
						<AppButton
							variant="primary"
							type="submit"
							data-testid="sellos-lead-req-save"
						>
							Save requirements
						</AppButton>
					</form>
					<p data-testid="sellos-lead-req-summary" class="text-sm text-ink-muted">
						{{ summary }}
					</p>
				</ListCard>

				<LeadMatches v-if="canLog" :lead="route.params.name" />

				<section
					data-testid="sellos-lead-follow-up"
					:data-state="followUp.follow_up_state || 'none'"
					class="ui-card flex flex-wrap items-center gap-ui-md"
				>
					<h2 class="ui-card-heading">Next follow up</h2>
					<span
						v-if="followUp.next_follow_up"
						data-testid="sellos-lead-next-follow-up"
						class="text-ink"
					>
						{{ followUp.next_follow_up_title }},
						{{ whenLabel(followUp.next_follow_up) }}
					</span>
					<span v-else data-testid="sellos-lead-next-follow-up" class="text-ink-muted">
						No open follow up
					</span>
					<StatusBadge
						v-if="followUp.follow_up_state === 'overdue'"
						tone="danger"
						label="Overdue"
						data-testid="sellos-lead-follow-up-overdue"
					/>
					<StatusBadge
						v-if="followUp.follow_up_untouched"
						tone="warning"
						:label="`Untouched, no follow up for ${followUp.untouched_days} days`"
						data-testid="sellos-lead-follow-up-untouched"
					/>
				</section>

				<ListCard
					v-if="canLog"
					title="Log a call"
					data-testid="sellos-lead-call"
					class="space-y-ui-md"
				>
					<form
						class="space-y-ui-md"
						data-testid="sellos-lead-call-form"
						@submit.prevent="logCall"
					>
						<div class="grid grid-cols-1 gap-ui-md sm:grid-cols-2">
							<FormField
								v-model="call.outcome"
								type="select"
								label="Outcome"
								required
								:options="outcomeOptions"
								data-testid="sellos-lead-call-outcome"
							/>
							<FormField
								v-model.number="call.minutes"
								type="number"
								label="Duration in minutes"
								min="0"
								step="any"
								data-testid="sellos-lead-call-minutes"
							/>
						</div>
						<FormField
							v-model="call.notes"
							label="Notes"
							data-testid="sellos-lead-call-notes"
						/>
						<FormField
							v-if="chosenOutcome?.needs_follow_up"
							v-model="call.followUp"
							label="Follow up on"
							required
							type="datetime-local"
							data-testid="sellos-lead-call-follow-up"
						/>
						<div class="flex flex-wrap items-end gap-ui-md">
							<FormField
								v-model="call.stage"
								type="select"
								label="Stage after this call"
								:options="callStageOptions"
								data-testid="sellos-lead-call-stage"
							/>
							<AppButton
								v-if="suggestedStage && call.stage !== suggestedStage"
								type="button"
								data-testid="sellos-lead-call-suggestion"
								@click="call.stage = suggestedStage"
							>
								Suggested stage: {{ suggestedStage }}. Use it
							</AppButton>
							<FormField
								v-if="callStageIsLost"
								v-model="call.lostReason"
								type="select"
								label="Lost reason"
								required
								:options="lostReasonOptions"
								data-testid="sellos-lead-call-lost-reason"
							/>
						</div>
						<p
							v-if="callError"
							role="alert"
							data-testid="sellos-lead-call-error"
							class="text-sm text-danger"
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
						<AppButton
							variant="primary"
							type="submit"
							data-testid="sellos-lead-call-save"
							>Log call</AppButton
						>
					</form>
				</ListCard>

				<ListCard
					v-if="canLog"
					title="Log something"
					data-testid="sellos-lead-log"
					class="space-y-ui-lg"
				>
					<form
						class="grid grid-cols-1 items-end gap-ui-md sm:grid-cols-[10rem_1fr_auto]"
						data-testid="sellos-lead-activity-form"
						@submit.prevent="logActivity"
					>
						<FormField
							v-model="activity.type"
							type="select"
							label="Activity type"
							:options="ACTIVITY_TYPES"
							data-testid="sellos-lead-activity-type"
						/>
						<FormField
							v-model="activity.notes"
							label="Notes"
							data-testid="sellos-lead-activity-notes"
						/>
						<AppButton
							variant="primary"
							type="submit"
							data-testid="sellos-lead-activity-save"
						>
							Add activity
						</AppButton>
					</form>
					<form
						class="grid grid-cols-1 items-end gap-ui-md sm:grid-cols-[1fr_14rem_auto]"
						data-testid="sellos-lead-task-form"
						@submit.prevent="addTask"
					>
						<FormField
							v-model="task.title"
							label="Task"
							required
							data-testid="sellos-lead-task-title"
						/>
						<FormField
							v-model="task.due_at"
							label="Follow up date and time"
							required
							type="datetime-local"
							data-testid="sellos-lead-task-due"
						/>
						<AppButton type="submit" data-testid="sellos-lead-task-save">
							Add follow up
						</AppButton>
					</form>
					<form
						class="grid grid-cols-1 items-end gap-ui-md sm:grid-cols-2"
						data-testid="sellos-lead-visit-form"
						@submit.prevent="addVisit"
					>
						<FormField
							v-model="visit.project_name"
							label="Site visit: project"
							required
							data-testid="sellos-lead-visit-project"
						/>
						<FormField
							v-model="visit.visit_datetime"
							label="Site visit: date and time"
							required
							type="datetime-local"
							data-testid="sellos-lead-visit-when"
						/>
						<FormField
							v-model="visit.agent"
							type="select"
							label="Agent for the visit"
							:options="visitAgentOptions"
							data-testid="sellos-lead-visit-agent"
						/>
						<div>
							<AppButton type="submit" data-testid="sellos-lead-visit-save">
								Add visit
							</AppButton>
						</div>
					</form>
				</ListCard>

				<ListCard
					v-if="detail.can_merge"
					title="Merge a duplicate client"
					data-testid="sellos-merge"
					class="space-y-ui-sm"
				>
					<p class="text-sm text-ink-muted">
						Move another client's leads, activities, tasks and site visits to
						{{ detail.client.client_name }}. The other client is archived, not deleted.
					</p>
					<FormField
						v-model="mergeFrom"
						type="select"
						label="Duplicate client"
						:options="mergeOptions"
						data-testid="sellos-merge-select"
					/>
					<p
						v-if="mergeError"
						role="alert"
						data-testid="sellos-merge-error"
						class="text-sm text-danger"
					>
						{{ mergeError }}
					</p>
					<p
						v-if="mergeDone"
						data-testid="sellos-merge-done"
						class="text-sm text-ink-muted"
					>
						{{ mergeDone }}
					</p>
					<AppButton
						variant="primary"
						type="button"
						:disabled="!mergeFrom"
						data-testid="sellos-merge-save"
						@click="merge"
					>
						Merge into {{ detail.client.client_name }}
					</AppButton>
				</ListCard>
			</div>
			<aside class="min-w-0 space-y-ui-md">
				<ListCard
					v-if="canReassign"
					title="Assigned agent"
					data-testid="sellos-reassign"
					class="space-y-ui-sm"
				>
					<p class="text-sm text-ink-muted">
						Now:
						<span data-testid="sellos-reassign-current">{{
							detail.lead.assigned_to || "Nobody"
						}}</span>
					</p>
					<FormField
						type="select"
						label="Assign to"
						:model-value="detail.lead.assigned_to || ''"
						:options="assigneeOptions"
						data-testid="sellos-reassign-select"
						@update:model-value="reassign"
					/>
					<p
						v-if="reassignError"
						role="alert"
						data-testid="sellos-reassign-error"
						class="text-sm text-danger"
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
				</ListCard>

				<ListCard
					v-if="detail.consent"
					title="Consent"
					data-testid="sellos-lead-consent"
					:data-status="detail.consent.status"
					class="space-y-ui-md"
				>
					<div>
						<StatusBadge
							:tone="consentTone"
							:label="detail.consent.status"
							data-testid="sellos-lead-consent-status"
						/>
					</div>
					<p
						v-if="detail.consent.warning"
						role="alert"
						data-testid="sellos-lead-consent-warning"
						:data-level="detail.consent.warning"
						class="rounded-input border px-3 py-2 text-sm"
						:class="
							detail.consent.warning === 'red'
								? 'border-tone-danger-line bg-tone-danger-bg text-tone-danger'
								: 'border-tone-warning-line bg-tone-warning-bg text-tone-warning'
						"
					>
						{{ detail.consent.message }} You can still call and message this lead.
					</p>
					<ul
						v-if="detail.consent.records.length"
						data-testid="sellos-lead-consent-records"
					>
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
							<span v-if="record.renewal_count"
								>, renewal {{ record.renewal_count }}</span
							>
							<a
								:href="record.evidence_link"
								target="_blank"
								rel="noopener"
								class="ui-link ml-1"
								>Evidence</a
							>
						</li>
					</ul>
					<template v-if="canLog">
						<form
							class="grid grid-cols-1 items-end gap-ui-md"
							data-testid="sellos-lead-consent-form"
							@submit.prevent="addConsent"
						>
							<FormField
								v-model="consentForm.basis"
								type="select"
								label="Consent basis"
								:options="CONSENT_BASES"
								data-testid="sellos-lead-consent-basis"
							/>
							<FormField
								v-model="consentForm.evidence"
								label="Evidence link"
								required
								data-testid="sellos-lead-consent-evidence"
							/>
							<AppButton
								variant="primary"
								type="submit"
								data-testid="sellos-lead-consent-save"
							>
								Record basis
							</AppButton>
						</form>
						<p
							v-if="consentError"
							data-testid="sellos-lead-consent-error"
							class="text-sm text-danger"
						>
							{{ consentError }}
						</p>
						<div class="flex flex-wrap items-end gap-ui-sm">
							<FormField
								v-model="stopSource"
								type="select"
								label="Stop request came by"
								:options="STOP_SOURCES"
								data-testid="sellos-lead-optout-source"
							/>
							<AppButton
								type="button"
								data-testid="sellos-lead-optout"
								@click="optOut"
							>
								Record stop request
							</AppButton>
							<AppButton
								type="button"
								data-testid="sellos-lead-dnd"
								@click="setDnd(1)"
							>
								Number is on the DND list
							</AppButton>
							<AppButton
								v-if="detail.consent.status === 'Registered DND'"
								type="button"
								data-testid="sellos-lead-dnd-clear"
								@click="setDnd(0)"
							>
								Number is not on the DND list
							</AppButton>
						</div>
					</template>
				</ListCard>

				<div>
					<h2 class="ui-card-heading">Timeline</h2>
					<p
						v-if="!detail.timeline.length"
						data-testid="sellos-lead-timeline-empty"
						class="mt-2 text-ink-muted"
					>
						Nothing logged yet.
					</p>
					<ul class="mt-2 space-y-ui-sm" data-testid="sellos-lead-timeline">
						<li
							v-for="item in detail.timeline"
							data-testid="sellos-lead-timeline-item"
							:key="item.kind + item.name"
							class="ui-card !p-ui-md"
						>
							<div class="flex items-center justify-between gap-2">
								<span class="font-medium text-ink">
									<span class="mr-2 text-xs uppercase text-ink-muted">{{
										item.kind
									}}</span
									>{{ item.title }}
									<span
										v-if="item.outcome"
										data-testid="sellos-lead-timeline-outcome"
										class="ml-1 text-sm text-ink-muted"
										>{{ item.outcome }}{{ callLength(item) }}</span
									>
								</span>
								<StatusBadge
									v-if="item.overdue"
									tone="danger"
									label="Overdue"
									data-testid="sellos-lead-timeline-overdue"
								/>
								<span v-else-if="item.status" class="text-xs text-ink-muted">{{
									item.status
								}}</span>
							</div>
							<p class="text-sm text-ink-muted">
								{{ String(item.when).slice(0, 16) }}
							</p>
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
								v-if="
									canLog && item.kind === 'visit' && item.status === 'Scheduled'
								"
								class="mt-2 flex flex-wrap gap-2"
							>
								<VisitConfirm
									:visit="item"
									:confirmations="visitOptions.confirmations"
									@changed="load"
								/>
								<AppButton
									type="button"
									data-testid="sellos-lead-visit-done"
									@click="startVisitDone(item)"
								>
									Mark visit done
								</AppButton>
							</div>
							<form
								v-if="visitDoing === item.name"
								class="mt-2 space-y-ui-sm"
								data-testid="sellos-lead-visit-done-form"
								@submit.prevent="finishVisitDone(item)"
							>
								<div class="grid grid-cols-1 gap-ui-md sm:grid-cols-2">
									<FormField
										v-model="visitDone.outcome"
										type="select"
										label="Outcome of the visit"
										:options="visitOutcomeOptions"
										data-testid="sellos-lead-visit-outcome"
									/>
									<FormField
										v-model="visitDone.notes"
										label="Visit note"
										data-testid="sellos-lead-visit-outcome-notes"
									/>
								</div>
								<p
									v-if="visitError"
									role="alert"
									data-testid="sellos-lead-visit-error"
									class="text-sm text-danger"
								>
									{{ visitError }}
								</p>
								<div class="flex gap-2">
									<AppButton
										variant="primary"
										type="submit"
										data-testid="sellos-lead-visit-done-save"
									>
										Done
									</AppButton>
									<AppButton type="button" @click="visitDoing = ''"
										>Cancel</AppButton
									>
								</div>
							</form>
							<p
								v-if="offeredStage && offeredFor === item.name"
								data-testid="sellos-lead-visit-offer"
								class="mt-2 text-sm text-ink"
							>
								Next stage: {{ offeredStage }}.
								<AppButton
									type="button"
									data-testid="sellos-lead-visit-offer-use"
									@click="acceptOffer"
								>
									Move the lead to {{ offeredStage }}
								</AppButton>
							</p>
							<AppButton
								v-if="canLog && item.kind === 'task' && item.status !== 'Done'"
								type="button"
								class="mt-2"
								data-testid="sellos-lead-task-done"
								@click="startDone(item)"
							>
								Mark done
							</AppButton>
							<form
								v-if="doing === item.name"
								class="mt-2 space-y-ui-sm"
								data-testid="sellos-lead-done-form"
								@submit.prevent="finishDone(item)"
							>
								<p class="text-sm text-ink-muted">
									Choose how the call went, or write a note.
								</p>
								<div class="grid grid-cols-1 gap-ui-md sm:grid-cols-2">
									<FormField
										v-model="doneForm.outcome"
										type="select"
										label="Call outcome"
										:options="doneOutcomeOptions"
										data-testid="sellos-lead-done-outcome"
									/>
									<FormField
										v-model="doneForm.notes"
										label="Note"
										data-testid="sellos-lead-done-notes"
									/>
								</div>
								<FormField
									v-if="doneOutcome?.needs_follow_up"
									v-model="doneForm.followUp"
									label="Next follow up on"
									required
									type="datetime-local"
									data-testid="sellos-lead-done-follow-up"
								/>
								<p
									v-if="doneError"
									role="alert"
									data-testid="sellos-lead-done-error"
									class="text-sm text-danger"
								>
									{{ doneError }}
								</p>
								<div class="flex gap-2">
									<AppButton
										variant="primary"
										type="submit"
										data-testid="sellos-lead-done-save"
										>Done</AppButton
									>
									<AppButton
										type="button"
										data-testid="sellos-lead-done-cancel"
										@click="doing = ''"
									>
										Cancel
									</AppButton>
								</div>
							</form>
						</li>
					</ul>
				</div>
			</aside>
		</div>
	</div>
	<LoadError
		v-else-if="error"
		:message="error"
		:retry="false"
		data-testid="sellos-lead-loading"
	/>
	<p v-else data-testid="sellos-lead-loading" class="text-ink-muted">Loading</p>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import AppButton from "../components/AppButton.vue";
import ClickToCall from "../components/ClickToCall.vue";
import FormField from "../components/FormField.vue";
import MoneyField from "../components/MoneyField.vue";
import LeadMatches from "../inventory/LeadMatches.vue";
import ListCard from "../components/ListCard.vue";
import LoadError from "../components/LoadError.vue";
import StatusBadge from "../components/StatusBadge.vue";
import VisitConfirm from "../components/VisitConfirm.vue";
import { setPageTitle } from "../shell";
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
// Budgets show as rupees with Indian grouping: ₹50,00,000.
const rupeeFormat = new Intl.NumberFormat("en-IN", {
	style: "currency",
	currency: "INR",
	maximumFractionDigits: 0,
});
const rupees = (n) => (n ? rupeeFormat.format(Number(n)) : "");
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
		setPageTitle(detail.value.client.client_name);
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

const toggleConfiguration = (value, on) => {
	const rest = req.configuration.filter((c) => c !== value);
	req.configuration = on ? [...rest, value] : rest;
};
const withBlank = (list, label) => [{ label, value: "" }, ...list];
const consentTone = computed(
	() =>
		({ Consented: "success", "Opted out": "danger", "Registered DND": "warning" }[
			detail.value?.consent?.status
		] || "neutral")
);
const asOptions = (rows, value = "name", label = "name") =>
	(rows || []).map((r) => ({ value: r[value], label: r[label] }));
const stageOptions = computed(() => asOptions(detail.value?.pipeline?.stages));
const lostReasonOptions = computed(() => [
	{ label: "Choose a lost reason", value: "" },
	...asOptions(lostReasons.value),
]);
const outcomeOptions = computed(() => [
	{ label: "Outcome", value: "" },
	...asOptions(outcomes.value),
]);
const doneOutcomeOptions = computed(() => [
	{ label: "No outcome, a note only", value: "" },
	...asOptions(outcomes.value),
]);
const callStageOptions = computed(() => [
	{ label: `Keep the stage (${detail.value?.pipeline?.stage})`, value: "" },
	...otherStages.value.map((s) => ({
		value: s.name,
		label: s.name + (s.name === suggestedStage.value ? " (suggested)" : ""),
	})),
]);
const visitAgentOptions = computed(() => [
	{ label: "The lead's agent", value: "" },
	...asOptions(visitOptions.value.agents, "name", "full_name"),
]);
const visitOutcomeOptions = computed(() => [
	{ label: "Choose the outcome", value: "" },
	...asOptions(visitOptions.value.outcomes),
]);
const assigneeOptions = computed(() => [
	{ label: "Choose an agent", value: "" },
	...asOptions(assignees.value, "user", "full_name"),
]);
const mergeOptions = computed(() => [
	{ label: "Choose the duplicate client", value: "" },
	...mergeChoices.value.map((c) => ({
		value: c.name,
		label: `${c.client_name} ${c.phone || ""}`.trim(),
	})),
]);

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

// The lead is its own screen now: opening another lead from this one reloads it.
watch(
	() => route.params.name,
	(name, before) => {
		if (name && name !== before) {
			detail.value = null;
			error.value = "";
			load();
		}
	}
);

onMounted(() => {
	load();
	loadAssignees();
	loadVisitOptions();
});
</script>
