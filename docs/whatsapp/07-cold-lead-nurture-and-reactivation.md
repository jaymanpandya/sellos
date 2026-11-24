# Flow 7: Cold lead nurture and reactivation

* **Document IDs:** B22 (Stage based nurture), B23 (Dormant lead reactivation)
* **Built by:** SOS-P6-17 (group two)
* **Document phase:** none. The document's phase lists do not name B22 or B23.
* **Source:** `SOURCE_workflow_design.md`, "Buyer workflows (B)", "Nurture and special paths"

## Purpose

Keep cold and quiet leads warm with messages that are worth reading, and revive a dormant lead with a relevant hook. Never "just checking in". A lead that stays quiet is closed lost with a reason.

## Trigger

* Flow 2 scores a lead cold, or flow 5 or 6 cools a lead.
* A lead has been quiet for a set period (B23).
* A scheduled nurture step is due for a lead at its stage and interest.

## Who

Leads who are buyers and who have not asked to stop. Identity rules apply.

## Steps

**Nurture (B22)**

1. Choose the next message by stage and interest: a market note, a matching new launch, a locality story or a shortlist reminder. Content comes from approved material and SellOS data, with an "as on" date on every number.
2. Apply the central cap on marketing messages per person each week, quiet hours at night in India, and no offers to a person who opted in only for updates. Every outbound message has a reason.
3. Send through the consent function, which records the lead's consent status and warning.
4. A reply re-enters routing (flow 2 or flow 8). A button reply such as "not now" pauses the sequence.

**Reactivation (B23)**

5. After the quiet period, send a relevant hook: new inventory that matches, a price change on a shortlisted project, or a rate change. Never "just checking in".
6. If the person answers, the lead is revived and routed. If not after the last attempt, close the lead lost with a reason (the lost reasons the company keeps).

## STOP (decision of 24 November 2026)

If the person sends STOP at any point, all WhatsApp to them is suppressed at once: no nurture message, no reactivation hook, no campaign, no partner digest. The flow sends one confirmation reply, creates a task for the assigned advisor and records Opted out in the consent log. After STOP the bot only replies to messages the person sends, and sends nothing unprompted until they opt in again. Calls and SMS are never blocked by consent. A nurture sequence in progress stops. Whether a new opt in restarts it is not decided here.

## Writes to SellOS

* Messages with their template and the lead's consent status and warning.
* A stage or lost reason on closing; a task for the advisor on a revived lead.
* The nurture step reached, so the sequence does not repeat.

## Handoff

A reply that asks for a human, an offer, a complaint or anger: flow 8. A revived hot lead alerts the advisor.

## Messages and templates

Nurture and reactivation are outside the service window, so they use approved marketing templates. The document's library includes `price_alert` (Shortlist change), `new_launch` (Matching launch) and `market_note` (Weekly), all marketing. A locality story and a rate change hook have no template there.

## Guardrails that apply

No hype, no urgency tricks, no promises on returns. Compliance check before send (O15, in the backlog) for banned claims, consent and, where required, the RERA number (an open question for counsel, see `README.md`).

## Test conversations (fake WhatsApp provider)

1. A cold lead. Expect the first nurture message at its due time, a reason on the message, and the consent status recorded.
2. The weekly cap is reached. Expect no further marketing message that week.
3. A dormant lead and a new matching unit. Expect a hook that names the unit, never "just checking in".
4. A reply "not now". Expect the sequence paused.
5. STOP in the middle of a sequence. Expect one confirmation, an advisor task, Opted out recorded, and no more messages.
6. The last attempt unanswered. Expect the lead closed lost with a reason.

## Gaps

* **Nurture engine.** SellOS has no nurture sequences, no stage based content selection, no message cadence cap, no quiet hours and no "quiet period" detection.
* **Marketing templates for every hook.** A locality story and a rate change hook have no template in the document's library, and `price_alert` needs a shortlist change event SellOS does not send.
* **Suppression after STOP.** Today no send is refused on consent while Consent enforcement is Off. See "Conflicts to settle" in `README.md`.
* **Content.** Market notes, locality stories and approved research are not in SellOS.
* **The brain** (see flow 1).
