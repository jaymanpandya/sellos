# Flow 6: Post visit feedback

* **Document IDs:** B17 (Post visit feedback)
* **Built by:** SOS-P6-17 (group two)
* **Document phase:** 1 (B13 to B17)
* **Source:** `SOURCE_workflow_design.md`, "Buyer workflows (B)", "Visit"

## Purpose

A few hours after a visit, ask the buyer what they liked, what worried them and what they want next, so the objections are known and the advisor has a task with the answers.

## Trigger

A Site Visit is marked Done (the advisor, or the field check in) and a few hours have passed. If the visit was marked "Did not come", flow 5's no show recovery runs instead.

## Who

The buyer who was on the visit. Identity rules apply.

## Steps

1. Within hours of the visit, send one short message that thanks the person and asks three things: what they liked, what worried them, what next. Accept text and voice notes (see Gaps).
2. Offer the "what next" answers as buttons: a second visit, a call with the advisor, shortlist more options, not for me.
3. Tag the worries as objections (price, location, builder trust, resale value, possession delay, other). The bot does not argue; objection answers with approved facts are flow B18, in the backlog, and anything beyond them goes to the advisor.
4. Thank the person and say what happens next. A second visit continues in flow 5.
5. A "not for me" answer asks one gentle reason and, with the person's agreement, moves the lead to flow 7.

## Writes to SellOS

* The Site Visit's outcome (Liked it, Undecided, Wants a second visit, Not interested, Did not come) and outcome notes.
* The objections as notes or tags on the lead.
* A task for the advisor with the answers.

## Consent

Recorded and shown as a warning. It never stops a call or an SMS. After a WhatsApp STOP, flow 1's rule applies: the feedback message is not sent unprompted, and the advisor's STOP task asks the advisor to collect feedback by phone.

## Handoff

Anger, a complaint or a threat of escalation: the manager is alerted and the bot only acknowledges, and stops selling. A request for a human, negotiation or an offer: flow 8.

## Messages and templates

The feedback message goes out inside the 24 hour window when the buyer wrote recently; otherwise it needs an approved utility template. The document's library has none for feedback, so a template is a gap.

## Guardrails that apply

One question at a time, short messages, no pressure. Never promise a discount or concession.

## Test conversations (fake WhatsApp provider)

1. A visit is marked Done. After the delay, expect the feedback message. The buyer answers; expect the outcome and notes saved and an advisor task.
2. The buyer says the price worries them. Expect an objection tag and no argument.
3. The buyer is angry about the visit. Expect an acknowledgement only, and a manager alert.
4. The buyer sends STOP. Expect nothing further unprompted.

## Gaps

* **The feedback template.** The document's template library has no visit feedback template, which an utility message outside the 24 hour window needs.
* **Voice notes.** Transcription of voice notes is not in SellOS.
* **Objection tags.** There is no objection list or tag on the lead, so objections go in notes.
* **Delay after a visit.** There is no scheduled job for "within hours", and no field recording when the visit ended.
* **A manager alert for anger** has no sentiment detection behind it.
* **The brain, buttons and lists** (see flow 1).
