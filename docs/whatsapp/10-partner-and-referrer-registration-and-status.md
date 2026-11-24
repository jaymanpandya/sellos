# Flow 10: Partner and referrer registration and status

* **Document IDs:** P10 (Client registration), P11 (Referral status tracking), P15 (Refer a Client by chat)
* **Built by:** SOS-P6-17 (group two)
* **Document phase:** P10 and P11 are in phase 2 (P01 to P13), P15 is in phase 2 (named alone)
* **Source:** `SOURCE_workflow_design.md`, "Channel partner workflows (P)", "Deals and money" and "Events and referrers"

## Purpose

A channel partner, or a referrer such as an accountant, lawyer, private banker or architect, registers a client by message and follows the client's progress by asking "Where is my client?" or by being told at each stage. The registration is protected in the partner's name under the company's rules.

## Trigger

* A message with the source code `REFER` (the Refer a Client page), or flow 1 hands over a person who chose Partner with us.
* A registered partner sends a client's name, number and requirement.
* A stage changes on a registered client (a push), or the partner asks for status.

## Who

* **A channel partner** of an Approved firm (SOS-P7-01): identified by the registered number, with a one time code for sensitive actions.
* **A referrer without SellOS access** (P15): identified by the registered number.

A partner sees only their own registrations, with phone numbers masked. A partner never sees another partner's client, an owner's contact on an exclusive listing, or why a registration was refused.

## Steps

**Register (P10, P15)**

1. Identify the sender. An unknown number is told how to register as a partner (partner onboarding P01 is in the backlog) and offered a person (flow 8).
2. Ask for the client's name, phone and requirement (project of interest, a note). One question at a time.
3. Show the **Partner confirmation wording** (the company setting, `{company}` filled in): "I confirm my client has agreed that {company} and its agents may contact them about this enquiry." The partner answers yes or no. A yes records a Consent Record on the lead through the same function as the partner screen; a no leaves the consent status Unknown, with a warning. Consent never blocks.
4. Register through the one registration method of SOS-P7-02, never a second path. It checks duplicates with the matching function and applies the partner lead limit (default 20 per partner per hour).
5. Reply. A new buyer: the registration is received, with its reference and time, and it waits for the Company Admin to approve it. The protection window (default 90 days) is counted from the approval, so the message says that and not that the client is protected yet. An existing buyer: the only answer is "Not accepted: this buyer is already registered with the company." It never says who registered them, their name, their agent or their stage.

**Status (P11)**

6. When a registration's status changes (Registered, Approved, Visited, Booked, Expired, Rejected), push a short message to the partner who registered it. A rejection is pushed as a status only: SOS-P7-02 does not say whether a partner sees the reason, so none is sent.
7. When the partner asks "Where is my client?", answer with that registration's current status and the date it changed, and nothing else about the client.

## STOP (decision of 24 November 2026)

If a partner or referrer sends STOP, all WhatsApp to them is suppressed at once: the bot, campaigns and partner digests (including status pushes). One confirmation reply is sent, a task is created for the assigned advisor and the opt out is recorded in the consent log. After STOP the bot only replies to messages the person sends, which includes a "Where is my client?" they send, and sends nothing unprompted until they opt in again. A STOP from the client of a registered lead is the client's own: it is recorded on the lead, and calls and SMS are never blocked by consent.

## Writes to SellOS

* A Partner Registration (and the Client and Lead it creates, source Channel partner), through SOS-P7-02's method.
* A Consent Record when the partner confirmed the client agreed, with the wording shown as evidence.
* Status pushes as messages logged on the conversation.
* A log of every registration attempt (SOS-P7-02 records them).

## Handoff

Duplicate and conflict disputes, a delayed payout, a commission question or a changed bank detail are never decided by the bot. They go to a person (flow 8; the dispute flow P13 and the commission statement P12 are in the backlog). A request for a human or two failed attempts also go to flow 8.

## Messages and templates

`referral_update` (utility), from the document's library, for the push on a stage change.

## Guardrails that apply

A partner sees only their own commission and clients. Duplicate registrations and disputes are never decided by the bot. A registration is never discussed in a group chat. The reply to a duplicate holds nothing but the fixed sentence.

## Test conversations (fake WhatsApp provider)

1. A partner of an Approved firm registers a new buyer and confirms the client agreed. Expect a Partner Registration in status Registered, a Consent Record, and a reply with the reference that says protection starts on approval.
2. The same partner registers the same buyer again. Expect only the fixed "Not accepted" sentence.
3. The partner registers a 21st buyer in an hour. Expect a clear refusal about the limit.
4. A number that is not a registered partner. Expect no registration and a pointer to registering as a partner.
5. A Company Admin approves the registration. Expect a status push to the partner.
6. The partner asks "Where is my client?". Expect the status and its date, and no name, phone, stage notes or agent.
7. The partner sends STOP. Expect one confirmation, an advisor task, Opted out recorded, and no further push; a later question from the partner is still answered.

## Gaps

* **Referrers without SellOS access.** SellOS has the Channel Partner role, for a partner of an Approved firm who signs in. It has no referrer without a login and no way to register a referrer by their number alone, so P15 as the document describes it has nothing to identify the sender.
* **One time codes for sensitive actions** (identity rule 3) do not exist.
* **Conflict alert to staff.** The document says P10 raises a conflict alert to staff on a duplicate. SOS-P7-02 tells the partner only the fixed sentence and has no staff alert.
* **Stages.** The document's stages are enquiry, visit, offer, booking, agreement, registration and payout. A Partner Registration has Registered, Approved, Visited, Booked, Expired and Rejected. There is no offer, agreement, registration or payout stage on it.
* **Written protection terms at registration.** The document confirms the protection terms in writing at registration. In SellOS protection begins at approval, so the message must say so; whether that is acceptable is not decided here.
* **Status pushes** need an event on every status change and an outbound message through the WhatsApp channel; neither is wired.
* **Partner-facing text** in other languages, and **the brain**, buttons and lists (see flow 1).
