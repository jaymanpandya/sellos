# Flow 5: Site visit booking, reminders and no show

* **Document IDs:** B13 (Site visit booking), B14 (Reminders and rescheduling), B15 (No show recovery)
* **Built by:** SOS-P6-16 (group one). Note: the description of SOS-P6-17 also mentions site visit booking; this README puts it in group one, see `README.md`.
* **Document phase:** 1 (B13 to B17)
* **Source:** `SOURCE_workflow_design.md`, "Buyer workflows (B)", "Visit"

## Purpose

Move a buyer from interest to a booked visit, keep the visit from failing with reminders the person can answer with a tap, and win back a person who did not come. "The agent's calendar" means Site Visit records (decided by Jayman, 13 November 2026).

## Trigger

* The person says yes to a visit, in flows 2 or 4 or on a project message.
* A Site Visit becomes due for a reminder: the day before and two hours before.
* A Site Visit passes its time with no outcome and the person did not come.

## Who

Buyers and visitors who have enquired. Identity rules apply. Builder name and RERA details are shared only after the person enquires.

## Steps

**Booking (B13)**

1. Offer slots. The document offers them from the advisor's calendar and the developer's site timings.
2. The person picks a slot. Create the Site Visit on the lead with the agent and the project.
3. Confirm in a message: the location pin, a parking note and who will meet them.

**Reminders and rescheduling (B14)**

4. The day before and two hours before, send a reminder (`visit_reminder`, utility) with three buttons: confirm, reschedule, cancel.
5. Confirm sets the visit's confirmation to Confirmed. Reschedule offers new slots and moves the visit. Cancel marks the visit Cancelled and frees the slot, then offers one new time without pressure.

**No show recovery (B15)**

6. Within the hour of a missed visit, send a gentle message (`visit_missed`, utility) with fresh slots. No guilt.
7. A rebooked visit continues at step 3. If the person does not answer, the lead is cooled with a reason and handed to flow 7.

## Writes to SellOS

* Site Visit: project, date and time, agent, status (Scheduled, Done, Cancelled), confirmation (Not confirmed, Confirmed, Rescheduled, Cancelled), and the outcome (Liked it, Undecided, Wants a second visit, Not interested, Did not come).
* A task for the agent on each booking and each no show.
* Notes, and a stage change when the visit is booked.

## Consent

Recorded and shown as a warning. It never stops a call or an SMS. Reminders and no show messages are sent through the consent function like any send. After a WhatsApp STOP, flow 1's rule applies: no reminder or recovery message is sent unprompted until the person opts in again. The advisor's task from the STOP says so, so a person phones to confirm the visit.

## Handoff

Asks for a human, negotiation or any offer, anger or a complaint (the manager is alerted and the bot only acknowledges), or two failed attempts: flow 8.

## Messages and templates

`visit_confirmation`, `visit_reminder`, `visit_missed` (all utility, from the document's template library).

## Guardrails that apply

Reminders carry the reason for the message. No urgency tricks. Quiet hours at night in India apply to every outbound message.

## Test conversations (fake WhatsApp provider)

1. A buyer books a slot. Expect a Site Visit, the confirmation message with the pin, parking note and the person who will meet them, and an agent task.
2. The day before reminder, answered with Confirm. Expect the confirmation status Confirmed.
3. A reminder answered with Cancel. Expect the visit Cancelled, the slot free, and one offer of a new time.
4. A visit with no outcome an hour past its time. Expect the no show message with fresh slots, and a rebooked visit when the person picks one.
5. A buyer who sent STOP before the day. Expect no reminder, and the advisor's task.

## Gaps

* **Advisor calendar and developer site timings.** SellOS has Site Visit records only. There is no calendar of an advisor's free slots and no developer site timings, so the bot cannot offer slots from them.
* **Reminder jobs.** There is no scheduler for "the day before" and "two hours before", no no show detection, and no quiet hours or message cadence setting.
* **Sending interactive buttons and the location pin.** A send is text or a template. Reminder buttons, a location message and slot lists are not available.
* **Who will meet them and a parking note** are not fields of the Site Visit or the Project.
* **Freeing a slot.** With no calendar, a cancellation has no slot to free.
* **The brain** (see flow 1).
