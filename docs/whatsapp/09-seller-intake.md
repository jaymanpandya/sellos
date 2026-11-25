# Flow 9: Seller intake

* **Document IDs:** S01 (Seller or landlord intake)
* **Built by:** SOS-P6-17 (group two)
* **Document phase:** 2 (S01 to S13)
* **Source:** `SOURCE_workflow_design.md`, "Seller and owner workflows (S)", "Win the listing"

## Purpose

Winning the listing is the first revenue event in the secondary market. This flow takes an owner's details by chat, creates the property record and a seller lead, and gets an advisor to the owner.

## Trigger

* Flow 1 hands over a person who chose Sell, or a first message with the source code `SELL` (the Sell page).
* A person says they own a property they want to sell or let.

## Who

Owners and landlords, known or not. Identity rules apply. The owner's data is never shown to a buyer or a partner.

## Steps

1. **Intake form (S01).** Ask, one question at a time, with buttons or lists where the answer is a short list: building and society, wing, floor, configuration, carpet area, age, facing, parking, status (self occupied, tenanted, vacant), expected price, urgency, reason for selling, preferred contact time. The document names a WhatsApp Flow form; until Flows can be sent, the same questions run as button, list and text questions. Skip what is known.
2. **Create the records.** A property record and a seller lead (a Lead on the Seller pipeline, linked to the property).
3. **Do not quote a price.** A quick price opinion (S03) and the document readiness check (S02) are in the backlog. The bot does not give a valuation; it says an advisor will visit and confirm.
4. **Tell the owner** who will contact them and when, and offer to book the valuation visit through an advisor (a Site Visit, as in flow 5).
5. **Sensitive data.** No ownership papers, PAN, Aadhaar or bank details in chat. Documents come later through a secure upload link (S02, in the backlog).

## Writes to SellOS

* Property: title, type, building, locality, address, configuration, carpet area, floor, parking.
* A Lead of type Seller linked to the property, assigned to an advisor, with the owner's other answers in the notes.
* A task for the advisor.
* The lead's consent status and warning.

## Consent

Recorded and shown as a warning. It never stops a call or an SMS. After a WhatsApp STOP, flow 1's rule applies: nothing is sent unprompted, and the person can still write to us and get replies.

## Handoff

Asks for a human, a question about price, negotiation, or a legal, tax or valuation question: flow 8. A discreet or private listing request (S06, in the backlog) goes to a senior advisor.

## Guardrails that apply

Owner and buyer contact details are never shared without consent. No valuation, legal or tax opinion from the bot. A seller sees only the four fields of an enquiry on their own property (Client views rule in `CLAUDE.md`); this flow shows no buyer data.

## Test conversations (fake WhatsApp provider)

1. An owner answers every question. Expect a Property, a Seller lead linked to it, an advisor task, and no price opinion in the replies.
2. An owner skips the price. Expect the lead created with the price missing and a task to ask.
3. An owner pastes a PAN number. Expect the message masked and a redirect to a secure upload link.
4. An owner asks "What is my flat worth?". Expect no figure and a handoff.

## Gaps

* **Property fields.** Property holds title, type, building name, RERA number, city, locality, address, configuration, carpet area, floor, parking and status. It has no wing, building age, facing, occupancy status (self occupied, tenanted, vacant), expected price, urgency, reason for selling or preferred contact time, and no link from the property to the owner. Those answers go in the lead's notes until fields exist.
* **Secure upload link and masking of pasted sensitive numbers** (S02, F12 are in the backlog, but this flow depends on masking and a redirect).
* **Sending buttons, lists and Flows**, **the brain**, and **language handling** (see flow 1).
* **The valuation visit.** A Site Visit exists, but booking it needs the advisor calendar gap of flow 5.
