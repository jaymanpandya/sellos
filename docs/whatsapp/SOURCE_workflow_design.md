# Pandya WhatsApp AI Bot: Complete Workflow Design

Nov 24, 2026 · @Jayman Pandya

One bot brain serves three doors: the Pandya Realtors website, a direct WhatsApp number, and a panel inside SellOS. It covers the daily work of a Mumbai real estate advisory for buyers, sellers, NRIs, channel partners, developers, tenants and your own staff. The design below lists 175 workflows in eleven families. Each has a trigger, the bot's steps, and the point where a human takes over.

## Purpose and design principles

- **One brain, three doors.** The same logic and memory run everywhere. Only permissions and tone change by role.
- **SellOS is the single source of truth.** The bot reads inventory, prices and calendars from SellOS and writes every lead, note, task and consent back. It never answers a price or availability question from memory.
- **Ask less, tap more.** Buttons, lists and WhatsApp Flows replace typing. Voice notes, Hindi, Marathi, Gujarati and Hinglish are accepted.
- **Humans are part of the design.** The bot qualifies, schedules, reminds and reports. Advisors negotiate and close. A handoff passes a summary, not a transcript.
- **Trust before volume.** No promises on returns, no legal or tax opinions, and every number carries a source and an "as on" date.
- **Every workflow earns its place.** Each one ties to a listing won, a buyer converted, a partner deal closed or staff time saved, in service of the 2 crore revenue target.
- **Respect the channel.** Opt in, opt out, quiet hours, and no unofficial automation on the Pandya number.

## Workflow families

IDs use a letter for the family and a number, for example B04. The same ID is used in SellOS tickets, analytics and the build plan.

| Prefix | Family | Main users | Section |
| --- | --- | --- | --- |
| B | Buyer and investor journey | Buyers, investors | Buyer workflows |
| S | Seller and owner journey | Owners, landlords | Seller and owner workflows |
| N | NRI and HNI concierge | NRIs, HNIs, UHNIs | NRI and HNI workflows |
| P | Channel partners and referrers | CPs, accountants, lawyers, bankers | Channel partner workflows |
| D | Developers and primary market | Developer sales teams | Developer workflows |
| R | Rental, leasing, property management | Tenants, landlords | Rental workflows |
| F | Finance, legal, tax, documents | Everyone with a deal | Finance and legal workflows |
| O | Office operations | Staff, managers | Staff workflows |
| T | Trust, content, referral | Prospects, subscribers | Trust and content workflows |
| A | After sale and relationship | Clients post booking | After sale workflows |
| X | Automation and platform | System | Automation section |

## Surfaces, identity and roles

The three doors share one official WhatsApp Business number and one brain, so context travels with the person. WhatsApp itself cannot be embedded as a chat window inside a web page. On the website, "embedded" therefore means a web chat widget running the same brain, plus Message us on WhatsApp buttons that carry context into the real WhatsApp thread.

| Surface | How it works | Context it passes in | Best for |
| --- | --- | --- | --- |
| Website | Web chat widget on every page, and WhatsApp buttons in the hero, the TerraLeads project modal, Refer a Client, Sell, Technology and the floating chip. One tap moves the chat to WhatsApp. | Page, project item\_id, UTM, language, consent state | First contact, TerraLeads enquiries, replacing forms with a conversation |
| Direct WhatsApp | The official number, reached by QR codes on hoardings and brochures, click to WhatsApp ads, the Instagram bio, email signatures and visiting cards. | A source code in the prefilled first message | The main surface for every role |
| SellOS panel | A chat panel inside SellOS for staff and partners. Same brain, tools scoped by role, and it can act inside the app. | Logged in user, role, the record on screen | Staff operations, partner self service, approvals |

### Who the bot thinks it is talking to

| Role | Identified by | Can ask the bot for | Never sees |
| --- | --- | --- | --- |
| Visitor | Unknown number | Public information, TerraLeads search, calculators, a site visit booking | Builder name and RERA details before an enquiry, anyone else's data |
| Client (buyer, seller, tenant, landlord) | Phone number match in SellOS, OTP for sensitive actions | Own status, visits, documents, payments, agreements | Other clients |
| NRI, HNI, UHNI | Same as client, plus a concierge flag | Everything a client can, with priority routing | Other clients |
| Channel partner | Registered number plus OTP | Partner inventory, own client registrations, own commission statements | Other partners' clients, owner contacts on exclusive listings |
| Referrer without SellOS access | Registered number | Refer a client, track own referrals by message | Everything else |
| Developer representative | Registered number plus OTP | Own project inventory, leads, approvals | Other developers' data |
| Staff advisor | SellOS login | CRM actions, drafting, matching, reports within team scope | Other teams' private notes if scoped |
| Manager and owner | SellOS login | Everything, including revenue reports and approvals | Nothing |
| Admin (technology team) | SellOS login | Templates, configuration, audit trail | Client content unless granted |

Identity rules:

1. The bot matches the sending number to a SellOS contact before it says anything personal.
2. If one number holds two roles, it asks once: "Are you contacting us as an owner, a buyer or a partner?"
3. Sensitive actions (documents, payment links, commission statements, agreement downloads) need a one time code sent to the registered number.
4. A staff number is elevated only inside the SellOS panel. On public WhatsApp, a staff member is treated like any client until verified.
5. The bot's number is the official WhatsApp Business Platform number. The separate listener SIM planned for channel partner group monitoring is a different pipeline and is never the Pandya number.

## Core engine: entry, routing, handoff, memory

Every message, from any door, passes through the same eight steps before a workflow runs.

&#91;embedded content: three doors, one brain, one record\]

The doors differ only in how a person arrives. Identity, intent, tools and guardrails are shared, and every action lands in SellOS.

1. **Receive.** Text, voice note, image, document, location pin, button tap or Flow submission.
2. **Identify.** Match the number or login to a role and a SellOS contact.
3. **Language.** Detect it, transcribe voice notes, reply in the same language. Hinglish is allowed.
4. **Intent.** Pick one workflow, or ask one clarifying question with buttons. Open questions go to the expert answer mode (T03).
5. **Context.** Load the open lead, requirement card, last visit, open tasks and a summary of recent messages.
6. **Act.** Run the next step of the workflow, calling SellOS tools. Guardrails check every outgoing message.
7. **Write back.** Note, tags, stage change, task and consent go to SellOS.
8. **Decide.** Continue, wait for a reply with a timer, or hand off to a person.

### Handoff rules

| Trigger | What happens |
| --- | --- |
| The person asks for a human | Routed at once to the assigned advisor, or the duty advisor if none |
| HNI or UHNI flag, or a large ticket size | Senior advisor alerted with priority, concierge workflow N09 starts |
| Negotiation, discount, token or any offer | Advisor takes over. The bot keeps logging. |
| Anger, complaint or a threat of escalation | Manager alerted, bot stops selling and only acknowledges |
| A legal, tax or valuation opinion is asked for | Routed to the panel professional or advisor. The bot explains why. |
| Two failed attempts to understand the person | Bot offers a human instead of a third try |
| Payment, refund or dispute | Staff only |
| Low confidence in an answer | Bot says it will check, creates a task, and does not guess |

A handoff carries a three line summary, the requirement card, the last messages and a suggested first reply. When a human replies, the bot goes quiet on that thread. It resumes after a set period of human silence, or when the advisor taps Return to bot. Outside business hours the bot still answers information questions and takes bookings, tells the person plainly when a human will reply, and creates the task for the start of the next working day.

### Memory and voice

- **Per contact memory:** language, preferred call time, requirement card, shortlist, objections raised, documents received, consent flags, and a rolling summary of the relationship.
- **Session memory:** the current workflow step, so a person can leave and return mid flow.
- **Voice of the bot:** calm, precise and advisory, like a senior associate. Short messages, one question at a time, no hype, no emoji clutter, no urgency tricks.

## Buyer workflows (B)

The buyer journey runs from first hello to booking, in primary and secondary markets, for self use and investment. Twenty five workflows in five stages.

### Discover and qualify

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| B01 | Welcome and intent | Greets in the person's language, asks consent to message, offers buttons: Buy, Sell, Rent, Invest, Partner with us, Something else. If a source code is present (a project, an ad, a page) it skips the menu. | Contact and source created in SellOS |
| B02 | Requirement capture | A WhatsApp Flow form: purpose (own use or investment), budget band, micro market, configuration, possession timeline, new launch or resale, funding method, must haves. Skips anything already known. | Requirement card saved, lead scored |
| B03 | Qualification and scoring | Checks budget readiness, timeline, decision maker, funding, and whether an existing home must be sold first. Scores hot, warm or cold with the reason. | Hot leads alert the advisor within minutes. Cold leads go to B22. |
| B04 | Lead routing | Assigns by micro market, language, ticket size and advisor load. | Advisor gets a card with a summary and a suggested first reply |
| B05 | First time buyer guide | A short guided path: how buying works in Mumbai, budget planning, loan basics, documents, timeline. | Moves into B02 when the person is ready |

### Search and decide

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| B06 | Conversational project search (TerraLeads on WhatsApp) | "3 BHK in Powai under 3.5 crore" returns up to three project cards from SellOS: photo, type and locality, price range, and a link to the project page. Builder name and RERA details are shared after the person enquires, matching the website. | Shortlist updated, project item\_id logged for analytics |
| B07 | Resale and secondary search | The same search over verified secondary inventory: building age, floor, society, carpet area, asking price, exclusivity. Owner identity stays hidden. | Enquiry relayed through S09 |
| B08 | Locality guide | Answers "How is Chembur for families?" from approved Pandya research: connectivity, schools, hospitals, price range, rental yield, upcoming infrastructure. Every figure has an as on date. | Offers matching projects |
| B09 | Compare options | Up to three options side by side: price per sq ft, carpet efficiency, possession date, developer track record, amenities, resale liquidity. | Comparison PDF, advisor prompt |
| B10 | Shortlist and alerts | Save, rename, remove. Messages the person when a shortlisted project changes price, releases inventory or reports a construction milestone. | Alert history in SellOS |
| B11 | Brochure, floor plan, price sheet | Sends documents on request and tracks opens. Price sheets only after an enquiry. | Document sent event, follow up task |
| B12 | Second opinion on a property found elsewhere | The buyer sends a listing or brochure. The bot collects details and queues a Pandya review: price against comparables, builder and RERA check, red flags. | Written review, advisor call |

### Visit

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| B13 | Site visit booking | Offers slots from the advisor's calendar and the developer's site timings. Confirms, then sends the location pin, parking note and who will meet them. | Calendar event, visit record |
| B14 | Reminders and rescheduling | Reminders the day before and two hours before, with buttons to confirm, reschedule or cancel. | A cancellation frees the slot |
| B15 | No show recovery | A gentle message within the hour with fresh slots. No guilt. | Rebooked visit, or lead cooled with a reason |
| B16 | Virtual visit | Books a video walkthrough with the advisor, sends the link and a short checklist. | Feeds N03 for remote buyers |
| B17 | Post visit feedback | Within hours asks three things: what they liked, what worried them, what next. Accepts voice notes. | Objections tagged, advisor task |

### Offer and booking

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| B18 | Objection handling | For price, location, builder trust, resale value or possession delay, answers with approved facts. Anything beyond that goes to the advisor. | Objection log by project for the team |
| B19 | Offer and negotiation log | Records the buyer's offer and conditions, passes it to the advisor, and tracks the seller or developer response against timers. | Offer record with status |
| B20 | Booking intent and token | When the buyer says yes, lists the next steps and documents. Payment links are created in SellOS and approved by staff. The bot never takes card or bank details in chat. | Booking record, advisor task |
| B21 | Booking documents | Sends a secure upload link for KYC and booking forms and tracks what is missing. | A complete checklist triggers the F workflows |

### Nurture and special paths

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| B22 | Stage based nurture | Sequences by stage and interest: a market note, a matching new launch, a locality story, a shortlist reminder. Frequency capped centrally. | Replies re enter routing |
| B23 | Dormant lead reactivation | After a quiet period, sends a relevant hook such as new inventory, a price change or a rate change, never "just checking in". | Revived, or closed lost with a reason |
| B24 | Investor path | Captures ticket size, yield target, horizon and liquidity needs. Proposes curated options: new launch, resale, commercial, plots such as Alibaug. | Investment shortlist with assumptions stated |
| B25 | Redevelopment and SRA enquiries | Collects society details and goals, explains how Pandya can introduce developers, and logs a society lead. | Society record, senior advisor |

## Seller and owner workflows (S)

Winning the listing is the first revenue event in the secondary market, so these workflows are built to earn the mandate and then keep the owner informed every week.

### Win the listing

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| S01 | Seller or landlord intake | A Flow form: building and society, wing, floor, configuration, carpet area, age, facing, parking, status (self occupied, tenanted, vacant), expected price, urgency, reason for selling, preferred contact time. | Property record and seller lead created |
| S02 | Document readiness check | Asks for ownership papers, share certificate, society NOC, occupancy certificate, tax receipts, outstanding loan, any encumbrance. Collects through a secure upload link. | Readiness score, gaps flagged to the advisor |
| S03 | Quick price opinion | Returns a range from comparable sales and live listings with the as on date and a clear note that a visit confirms it. | Booked valuation visit |
| S04 | Valuation visit | Books the visit, sends the advisor profile and a one page prep list, and sends a thank you summary afterwards. | Visit record, valuation note |
| S05 | Mandate and listing agreement | Sends the agreement for digital signature, explains exclusive and non exclusive terms in plain words, and chases the signature. | Signed mandate stored, listing task opened |
| S06 | Remote or HNI discreet listing | Offers a private listing that is shown only to selected buyers and trusted partners, not to the open web or groups. | Private mandate flag, restricted visibility |

### Market the listing

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| S07 | Photo and video capture | Books the shoot, or guides the owner to send photos and a walkthrough video by chat with a short shot list. | Media saved to the property record |
| S08 | Listing creation | Drafts the description and key facts from the record. Staff approve. Publishes to the website, TerraLeads, approved portals and the partner network. | Live listing with source tags |
| S09 | Buyer enquiry relay | Buyer interest reaches the owner with the buyer's profile, never raw contact details. The owner approves visits by button. | Visit scheduled, owner privacy kept |
| S10 | Showing coordination | Confirms keys, tenant access, parking and a showing window, and reminds both sides. | Visit log |
| S11 | Weekly seller report | Every week: views, enquiries, visits, feedback themes, comparable activity, and a recommendation. | Delivered on a fixed day, owner can reply |
| S12 | Price revision advice | When enquiries stall, proposes a price or terms change with evidence. The owner approves in the chat. | Price change logged, listing refreshed |

### Offer to close

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| S13 | Offer received | Shows each offer in a clear card: price, conditions, buyer readiness, funding. The owner can accept, counter or decline, and the advisor is in the loop. | Offer tracker with timestamps |
| S14 | Tenanted property sale | Coordinates with the tenant on showings, notice, and handover terms. | Tenant record linked to the sale |
| S15 | Sale readiness for closing | Tracks the loan foreclosure letter, society NOC, share transfer, no dues certificate, agreement drafts and registration date. | Checklist with owners and due dates |
| S16 | Exit tax estimate | Gives an indicative capital gains and TDS view for planning and refers the owner to the panel chartered accountant. | Referral to F11 |
| S17 | Closing and key handover | Confirms payment milestones, registration and key handover, then asks for a review. | Deal closed in SellOS, A10 begins |
| S18 | Portfolio owner review | For owners of several units, summarises each unit's value, rent and hold or sell options on request. | Advisor meeting |

## NRI and HNI workflows (N)

These clients value time, discretion and certainty. The bot handles the logistics across time zones and gives HNI and UHNI clients a faster, quieter path to a senior advisor.

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| N01 | NRI intake | Captures country, time zone, preferred contact hours, budget in rupees and in the home currency, funding route (NRE, NRO, foreign income), purpose, and who in Mumbai can act for them. | NRI flag and requirement card |
| N02 | Time zone aware scheduling | Offers call and video slots in the client's local time, shows both time zones, and reminds in the client's morning or evening. | Calendar event with both zones |
| N03 | Remote buying toolkit | Books a live video walkthrough with a Pandya representative on site, shares a visit video, neighbourhood clip and building condition notes, and records questions during the call. | Visit record with media and notes |
| N04 | Power of attorney | Explains the options, collects details, tracks drafting, attestation, courier movement and receipt. Legal content comes from the panel lawyer. | POA checklist with status |
| N05 | FEMA and tax guide | Plain language guide on repatriation, TDS on sale, tax residency and reporting. Marked as general information, with a referral to the panel chartered accountant. | Referral to F11 |
| N06 | Currency and total cost estimator | Converts the price to the home currency at the current rate, adds stamp duty, registration, GST where applicable and typical one time costs. | Estimate PDF with the as on date |
| N07 | Family representative coordination | Lets the client name a trusted relative in Mumbai for visits and documents, with limited permissions the client can change. | Delegate record in SellOS |
| N08 | Property care for NRIs | After purchase: rent collection, periodic inspection with photos, maintenance quotes, tax and society dues reminders. | Feeds R12 and R13 |
| N09 | HNI and UHNI concierge | A private line to a named senior advisor. The bot confirms receipt, shares nothing in groups, and escalates at once. Requests are handled in a discreet thread. | Priority alert, named advisor |
| N10 | Off market alerts | Matches the client's brief to private and off market secondary listings from the partner network and sends them one at a time with a short rationale. | Interest recorded, advisor follows up |
| N11 | Wealth manager and family office introductions | Accountants, lawyers and private bankers introduce clients through chat. The bot registers the referrer, keeps them updated and protects the client's privacy. | Referral registered (P15) |
| N12 | Discreet deal mode | For sensitive sales or purchases: no broadcasts, restricted visibility, named participants only, an access log kept. | Private deal flag |
| N13 | Succession and gifting enquiries | Collects the situation at a high level and routes to the panel estate lawyer. No opinions from the bot. | Referral with context |
| N14 | Private briefings and events | Invites select clients to market briefings, launch previews and developer meetings and manages RSVPs. | Guest list and follow ups |

## Channel partner workflows (P)

Channel partners are a main source of secondary listings and buyers for the HNI and UHNI segment. These workflows make Pandya the easiest, fairest and most reliable partner to work with, and give partners self service without needing a SellOS login. Partners who do have SellOS use the same workflows in the panel.

### Onboard and activate

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| P01 | Partner onboarding | A Flow form: name, firm, RERA agent registration number, areas and property types served, languages, GST status, referral source. Bank details through a secure link only. | Partner record pending verification |
| P02 | Verification and agreement | Checks the registration number, sends the partner terms for digital acceptance, confirms the commission structure in writing. | Active partner, optional SellOS access |
| P03 | Tiering and reactivation | Uses activity data to tier partners. Inactive partners receive useful, specific messages such as new inventory in their area, not generic broadcasts. | Reactivated or dormant flag |
| P04 | Partner training and Q and A | Answers questions on projects, RERA rules, process and scripts from the approved knowledge base. Short voice note explainers for new launches. | Questions logged to find content gaps |

### Inventory

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| P05 | Inventory query | "2 BHK Andheri West under 3 crore, resale" returns partner shareable inventory with the commission terms that apply to that partner only. | Query log reveals demand |
| P06 | Inventory posting by partner | The partner sends listing text, photos or a voice note. The bot extracts location, type, sale or rent, BHK, carpet area, price and contact, merges reposts of the same listing, asks for missing fields, and sends it for staff review. | Structured listing in SellOS |
| P07 | Daily and weekly digest | New launches, price changes and new listings in the partner's chosen areas and budgets, plus demand from Pandya's own buyers. | Opt in by area, one tap to change |
| P08 | What is new today | A partner or staff member asks "What is new in Andheri West today?" The bot answers from the group monitoring pipeline and the listings sheet. | Source and timestamp shown |
| P09 | Collateral on demand | Brochures, floor plans, creatives and forwardable cards co branded for the partner. | Delivered in the chat, usage tracked |

### Deals and money

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| P10 | Client registration | The partner sends client name, number and requirement. The bot checks duplicates and conflicts, issues a registration ID with a timestamp, and confirms the protection terms in writing. | Registration record, conflict alert to staff |
| P11 | Referral status tracking | Pushes each stage to the partner: enquiry, visit, offer, booking, agreement, registration, payout. The partner can ask "Where is my client?" at any time. | One status source for everyone |
| P12 | Commission statement and payout | Shows expected and earned commission, TDS, invoice status and payment dates. Helps raise the invoice with a template. | Payout task for accounts |
| P13 | Dispute and escalation | Logs a conflict, duplicate claim or delayed payout with evidence and sends it to the manager with a clock. | Ticket with owner and SLA |
| P14 | Recognition | Monthly leaderboard and milestones sent to top partners, with their permission. | Opt in only |

### Events and referrers

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| P15 | Refer a Client by chat | For accountants, lawyers, private bankers, architects and brokers without SellOS access: they message the client's name and what the client wants. The bot registers it, keeps them updated by message, sends a closing summary, and shows what was agreed on payment. Matches the Refer a Client page. | Referral record, referrer updates |
| P16 | Channel partner meet | For the Samaana sponsored meet and later events: invitation, RSVP, reminders, QR check in, a developer lead capture sheet, feedback, and a follow up within a day. | Attendance and leads in SellOS |

## Developer and primary market workflows (D)

Primary market revenue depends on accurate inventory, fast approvals and clean reporting to the developer. The bot keeps developer sales teams in the loop with a few taps and removes phone chasing.

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| D01 | Developer and project onboarding | Collects project name, RERA number, towers, configurations, carpet areas, price sheet, payment plans, amenities, possession dates and brochures. Flags missing items. | Project record in SellOS, ready for TerraLeads |
| D02 | Inventory availability sync | Each morning asks the developer's sales head to confirm changes with buttons: available, on hold, sold. Updates unit status in SellOS. | Fresh inventory, stale alerts if unanswered |
| D03 | Price and scheme updates | Developer sends a revised price list or scheme. The bot extracts changes, shows a diff, staff approve, and shortlisted buyers and partners are alerted. | Versioned price history |
| D04 | Launch campaign | A launch brief becomes a plan: content requests to the marketing tool, partner broadcast, lead capture through TerraLeads, visit slots at the site. | Launch dashboard for the developer |
| D05 | Site visit coordination | Confirms the developer's team, slot and gate arrangements for each booked visit, and sends the site team a daily list. | Fewer failed visits |
| D06 | Lead and visit reports | A daily and weekly report to the developer: leads, visits, feedback, objections, bookings. Sent as a short message and a PDF. | Report log |
| D07 | Discount and approval requests | The advisor asks, the bot packages the buyer's offer and sends it to the developer contact, tracks the response against a timer and nudges. | Approval record |
| D08 | Booking confirmation and demand tracking | After a booking, confirms unit, payment plan and demand letter dates with the developer and the buyer. | Schedule in SellOS |
| D09 | Brokerage claims | Packages booking proof and the invoice, submits to the developer, and tracks follow ups until paid. | Claim status for accounts |
| D10 | Construction progress feed | Collects milestone photos and notes from the developer and sends them to booked buyers (A03). | Progress log per project |
| D11 | Sponsored content and podcast | For sponsored episodes such as the Alibaug series and sponsored partner meets: brief intake, approval steps, schedule, and a performance summary. | Sponsor report |
| D12 | Developer escalation | A missed approval, a wrong price shown or a buyer complaint goes to the developer's senior contact and Pandya's manager with context. | Ticket with a clock |

## Rental, leasing and property management workflows (R)

Rentals bring steady cash flow, build relationships with future buyers and sellers, and suit the many Mumbai owners who let out a second home. Statutory steps such as agreement registration and tenant intimation to the police are confirmed with your legal panel before launch.

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| R01 | Landlord listing | Collects property details, rent and deposit expectations, furnishing, tenant preference, availability date. Creates a rental listing after staff review. | Rental listing |
| R02 | Tenant requirement | Budget, area, configuration, move in date, family or company lease, pets, parking, work location. | Tenant lead |
| R03 | Matching and visits | Sends matching homes, books visits in batches to save travel time, and collects feedback. | Visit records |
| R04 | Tenant screening | Collects ID, employment proof and references through a secure link, runs a checklist, and shares a summary with the landlord. | Screening note for the landlord |
| R05 | Leave and license agreement | Gathers terms, drafts through the legal template, arranges digital stamping and registration appointments, and tracks biometric slots for both parties. | Registered agreement stored |
| R06 | Move in | Checklist for society NOC, inventory list with photos, utility transfers, key handover and deposit receipt. | Move in record |
| R07 | Rent reminders | Polite reminders to tenants before the due date, receipts after payment, and an overdue ladder that ends with the landlord and the advisor. | Payment ledger |
| R08 | Maintenance requests | Tenant sends a photo or voice note, the bot classifies it, assigns a vendor from the panel, shares a quote with the landlord for approval, and closes with a photo. | Work order |
| R09 | Renewal | Starts sixty and thirty days before expiry: asks both sides, suggests a rent revision with evidence, and triggers the new agreement. | Renewed or notice flow |
| R10 | Move out and deposit | Books an inspection, compares with the move in inventory, proposes a deposit settlement, and relists the home. | Deposit settlement note |
| R11 | Commercial leasing | Office, retail and pre leased asset enquiries: area, floor, lock in, fit out, escalation terms, power backup, parking. Escalates to a specialist advisor. | Commercial lead |
| R12 | Periodic inspection | Scheduled visits for owners who live abroad or elsewhere, with a photo report and a short condition summary. | Inspection report |
| R13 | Landlord statements | Monthly rent received, expenses, society and property tax dues, and documents needed for tax filing. | Statement and document vault |

## Finance, legal, tax and documentation workflows (F)

This is where an advisory earns trust and where tertiary service revenue sits. The bot calculates, checks and organises. Lawyers, chartered accountants and banks on the Pandya panel give the opinions. Rates, charges and rules live in a maintained table that staff review, and every answer shows its as on date.

### Money

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| F01 | EMI calculator | Loan amount, rate, tenure, with a prepayment option. Shows the monthly outgo and total interest. | Saved to the requirement card |
| F02 | Affordability check | Income range, obligations, down payment and savings give a comfortable budget band and a stretch band. | Budget band for B02 |
| F03 | Home loan assist | Collects the documents, shares the profile with partner banks after consent, and compares indicative offers. | Loan case in SellOS |
| F04 | Loan status and sanction | Tracks login, valuation, sanction and disbursement, and nudges for missing papers. | Status visible to buyer and advisor |
| F05 | Stamp duty and registration estimate | Calculates for the property type and buyer profile using the maintained table. | Estimate with the as on date |
| F06 | Total cost sheet | Agreement value, stamp duty, registration, GST where it applies, parking, maintenance deposits, legal, interiors, moving. | One page PDF |
| F07 | Ready reckoner lookup | Returns the government rate for the locality and the gap to the agreement value. | Shown in comparison B09 |

### Checks and legal

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| F08 | RERA verification | Looks up the project's registration number and returns status, promoter, completion date, extensions and complaints in plain words. | Verification note stored |
| F09 | Due diligence order | Orders title search and property checks through the panel lawyer: society documents, occupancy and commencement certificates, litigation search, encumbrance, and for land such as Alibaug the 7/12 extract and village records. | Report tracker, delivered in chat |
| F10 | Agreement review | Sends the draft agreement to the panel lawyer, tracks the review, and returns a short list of red flags from the lawyer's note. | Lawyer's note shared. The bot gives no legal opinion. |
| F11 | Tax and chartered accountant referral | Capital gains planning, TDS compliance for buyers and sellers, NRI tax. The bot collects facts and books a call. | Referral with context |
| F12 | Document vault | Secure upload links for KYC, ownership papers and agreements. Expiry reminders. Nothing sensitive is requested in the chat itself. | Encrypted store, access log |
| F13 | Digital signature and stamping | Sends agreements for signature, tracks each signer and reminds. | Signed copies stored |
| F14 | Registration day | Books the sub registrar slot, lists documents and witnesses, sends the checklist the day before and travel details on the morning. | Registered deed filed |

### Related services

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| F15 | Insurance | Home and loan protection quotes through partners, with consent. | Lead for the partner |
| F16 | Home services desk | Interiors, vastu, packers and movers, cleaning, furniture and appliances. Collects the brief and connects vetted vendors. | Service lead with source |
| F17 | Society transfer matters | Share certificate transfer, society NOC, transfer charges, and dues clearance guidance. | Checklist with owners |

## Staff workflows inside SellOS (O)

Inside SellOS the bot works for the team, not the client. Advisors talk to it in plain language or by voice note and it acts on records: it creates, updates, schedules, drafts, matches and reports. Every action that changes a record or sends something outward shows a preview and waits for a tap.

### Daily work

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| O01 | Morning briefing | "What is my day?" lists visits with travel time, follow ups due, hot leads, stale leads, offers waiting, and tasks overdue. Can be sent automatically at a set hour. | One screen day plan |
| O02 | Lead intake and assignment | New leads from any source arrive with a summary. The bot suggests an owner by area, language, ticket size and load. A manager confirms or it assigns automatically. | Assigned lead, alert to advisor |
| O03 | Natural language CRM | "Add lead Rohan Shah, 3 BHK Powai, 3.5 crore, call Friday" creates the lead and task. "Log call with Mehta, wants to see Hiranandani again" adds a note. Voice notes become structured notes. | Clean records without typing |
| O04 | Client 360 | "Tell me about Mrs Kapoor" returns requirement, shortlist, visits, objections, documents, last conversation and next step. | Summary card |
| O05 | Follow up scheduler | Sets, snoozes and reassigns follow ups. Escalates a task that crosses its time limit to the manager. | Task list with owners |
| O06 | Reply drafting | Drafts a reply in the client's language and Pandya's voice, with options for short or detailed. Nothing is sent until the advisor approves. | Draft, edit, send |
| O07 | Matching engine | A new listing finds matching buyers and partners. A new buyer finds matching listings. One tap sends the selection. | Match list with reasons |
| O08 | Inventory desk | "Any 2 BHK in Bandra West under 4 crore?" returns primary and secondary options with commission, owner status, key availability and exclusivity, all visible to staff only. | Fast answers during calls |
| O09 | Visit day planner | Orders the day's visits by area and traffic, adds buffers, parking notes and who is meeting whom, and updates when something changes. | Route plan |
| O10 | Field check in | The advisor shares a location pin at the start and end of a visit. The bot logs it and asks for feedback. | Visit proof and prompt feedback |

### Documents, content and approvals

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| O11 | Call and meeting summary | Upload a recording or notes. The bot returns a summary, decisions, objections and action items, and updates the CRM after approval. | Notes and tasks created |
| O12 | Document generation | Offer letters, client proposals, comparison sheets, portfolio PDFs, branded brochures and summary decks. | Files in the record |
| O13 | Content requests | "Make a reel script on Bandra redevelopment" or "Post for the new listing" goes to the marketing tool and content agents with the record attached. | Draft returned for approval |
| O14 | Approvals | One tap approvals for listings, discounts, payment links, price changes, payouts and broadcasts, with the key facts shown. | Approval log |
| O15 | Compliance check | Before anything goes out, checks for banned claims such as guaranteed returns, missing RERA number where required, and missing consent. | Pass or fix list |
| O16 | Broadcast builder | Choose a segment, a template, preview, schedule, then track delivery and replies. Respects consent, frequency and quiet hours. | Campaign report |

### Management and quality

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| O17 | Pipeline and revenue view | "How far are we from 2 crore?" shows closed brokerage, expected brokerage by stage and probability, deals at risk, and the gap with the actions that would close it. | Live forecast |
| O18 | Team performance | Response time, visit conversion, follow up discipline and handoff quality by advisor and by source. | Weekly team review |
| O19 | Handoff inbox | A queue of conversations waiting for a human. Claim, reply, return to bot. | Queue with ages |
| O20 | Data quality | Finds duplicates, missing fields, stale listings and leads with no next step, and proposes fixes in bulk. | Clean data |
| O21 | Staff knowledge base | Answers process, project and policy questions from approved documents and links to the source. | Fewer interruptions |
| O22 | New staff training | Daily scenario drills and quizzes, with feedback on tone and compliance. | Skill record |

## Trust, content and referral workflows (T)

The project aim is to make Pandya the most reliable real estate service provider through content. These workflows turn the content engine (market notes, pocket books, the podcast, reels) into permission based conversations, so the bot becomes the place where trust turns into enquiries.

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| T01 | Market note subscription | Weekly Mumbai notes by micro market and by theme (new launches, resale, rentals, commercial). The person picks topics and frequency with buttons. | Subscriber segment in SellOS |
| T02 | Launch and inventory alerts | Matches new launches and fresh listings to saved interests and sends one message per item. | Click and reply tracking |
| T03 | Ask the expert | Free questions answered from the approved Pandya knowledge base, such as redevelopment, society rules or loan basics. States sources, never guesses, offers a human for anything personal. | Question log feeds new content |
| T04 | Pocket book lead magnet | Delivers a chapter or checklist from the planned pocket book series after a name and area of interest, then invites the next chapter. | Reader leads by topic |
| T05 | Podcast companion | Episode alerts, show notes, a question for the guest, and a sponsor spotlight when an episode has a sponsor. | Listener segment |
| T06 | Events and webinars | Invitation, RSVP, reminders, joining link, recording after, and a follow up message by interest. | Attendee leads |
| T07 | Client to friend referral | Happy clients can introduce a friend or family member by chat. The bot thanks them, keeps them updated, and handles the recognition agreed. | Referral record (compare P15) |
| T08 | Reviews and testimonials | After a good milestone, asks for a review, shares the link, and asks consent before any public use. | Reviews and permissions stored |
| T09 | WhatsApp Channel | A one way Pandya Realtors channel for market notes and launches, with a link into the chat for questions. | Follower growth, clicks |
| T10 | Ad and social entry points | Click to WhatsApp ads, Instagram bio, reels and stories each open a chat with a source code so the first reply speaks to what the person just saw. | Source attribution per campaign |
| T11 | Polls and surveys | Short questions on budget, area and content preferences. Answers update the person's profile. | Better segments |
| T12 | Festive and milestone greetings | Gudi Padwa, Akshaya Tritiya, Diwali, anniversaries of a purchase. Personal, brief and rare, with no offers unless the person opted in to offers. | Relationship touch points |
| T13 | Decision calculators | Rent or buy, yield on a rental home, price per sq ft comparison, and the true monthly cost of a purchase. | Saved into the profile |
| T14 | News explainers | A short note when a policy, rate, infrastructure or redevelopment announcement affects a micro market, with a view from Pandya. | Approved by staff before sending |

## After sale and relationship workflows (A)

A closed deal is the start of the next one. Clients who feel looked after refer friends, resell through Pandya, and let their homes through Pandya. These workflows keep the relationship warm without becoming noise.

| ID | Workflow | Bot flow | Output and handoff |
| --- | --- | --- | --- |
| A01 | Post booking welcome | Thanks the buyer, shares the booking summary, the next three steps and one named contact. | Welcome logged, journey starts |
| A02 | Payment schedule reminders | Reminds before each demand letter or instalment date, shows the amount from the developer's schedule, and sends a staff approved payment link where used. | Payment ledger per unit |
| A03 | Construction updates | Sends milestone photos and notes from the developer (D10) to booked buyers of that project, with a way to ask questions. | Update history per project |
| A04 | Loan and documents follow through | Keeps the loan disbursement, agreement and registration steps moving with reminders to every party. | Open items list |
| A05 | Pre possession inspection | Books a snagging inspection, collects the defect list with photos, and sends it to the developer with a due date. | Snag list with status |
| A06 | Possession and key handover | Confirms dues, documents, society formalities and the handover slot. Collects a photo of the signed handover. | Possession recorded |
| A07 | Move in and interiors | Connects interiors, packers, cleaning, furniture, utility transfers and the society move in process (F16). | Service leads |
| A08 | Grievance handling | Logs any complaint as a ticket with a number, category and owner, acknowledges within the hour, updates on progress, and escalates on a clock. | Ticket with SLA |
| A09 | Yearly check in | On the purchase anniversary shares a value note for the micro market and asks whether the client wants to hold, let out or sell. | Opportunity flagged for the advisor |
| A10 | Referral and review request | After possession or after a closed sale, asks for a review and for introductions, one request per milestone. | T07 and T08 |
| A11 | Dues and tax reminders | Society dues, municipal property tax and insurance renewals for clients who opted in. | Reminder log |
| A12 | Resale and rent out prompts | When the market moves or the lock in ends, suggests a valuation or a rental listing. | Seller or landlord lead |

## Automation, templates and WhatsApp platform rules (X)

The rules of the WhatsApp Business Platform shape what the bot can send and when. Details such as window lengths, template categories and pricing change, so confirm each against Meta's current documentation and the rate card for India before build.

### Platform rules that shape the design

| Rule | What it means for the bot |
| --- | --- |
| Official Business Platform number, business verified | Use one verified number with the Pandya Realtors display name. Never run the bot on an unofficial linked device. |
| Service window of about 24 hours after the person's last message | Free form replies inside the window. Outside it, only approved templates. Workflow X04 decides which. A longer window may apply to some ad entry points. |
| Template categories: utility, marketing, authentication | Reminders and status updates are utility. Alerts and market notes are marketing. OTPs are authentication. Each is approved in advance. |
| Explicit opt in and instant opt out | Record time, source and topics for every opt in. A STOP reply suppresses messages at once. |
| Interactive messages | Reply buttons, lists, location requests, link buttons and Flows (in chat forms). Used in place of typing wherever possible. |
| Quality rating and messaging limits | Poor feedback lowers sending limits. Broadcast volumes grow gradually and quality is monitored (X10). |

Message cadence is set centrally: a cap on marketing messages per person each week, quiet hours at night in India, no offers to people who opted in only for updates, and a reason on every outbound message.

### Template library to submit for approval

| Template | Category | Trigger | Used in |
| --- | --- | --- | --- |
| welcome\_and\_consent | Utility | First contact | B01 |
| otp\_code | Authentication | Sensitive action | Identity rules |
| visit\_confirmation, visit\_reminder, visit\_missed | Utility | Visit booked, due, missed | B13 to B15 |
| document\_request | Utility | Checklist gap | B21, F12 |
| loan\_status | Utility | Stage change | F04 |
| referral\_update | Utility | Stage change | P11, P15 |
| payout\_update | Utility | Invoice or payment status | P12 |
| seller\_weekly\_report | Utility | Weekly | S11 |
| payment\_reminder | Utility | Before a due date | A02 |
| construction\_update | Utility | Milestone published | A03 |
| rent\_reminder | Utility | Before and after the due date | R07 |
| ticket\_acknowledged | Utility | Complaint logged | A08 |
| price\_alert | Marketing | Shortlist change | B10 |
| new\_launch | Marketing | Matching launch | T02 |
| market\_note | Marketing | Weekly | T01 |
| event\_invite | Marketing | Event created | T06, P16 |

### Platform workflows

| ID | Workflow | What it does |
| --- | --- | --- |
| X01 | Consent and preference centre | One place to see and change topics, frequency, language and call times. Reachable from any chat with the word Preferences. |
| X02 | Opt out and suppression | Honours STOP at once, across the bot, SellOS campaigns and partner digests. |
| X03 | SLA timers | Starts a clock on each handoff, approval and ticket. Escalates up the chain when it runs out. |
| X04 | Window manager | Checks whether the service window is open before each send. Uses free text if open, the right template if not. |
| X05 | Scheduled jobs | Morning briefings, digests, weekly reports, renewal reminders, alerts and nurture steps. |
| X06 | Listing feed | Nightly import of structured listings from the group monitoring pipeline, with duplicate merging. |
| X07 | Duplicate detection | Matches phone numbers, names and properties across leads, partners and owners and proposes merges. |
| X08 | Analytics events | Sends events to GA4 through the tag manager and to SellOS: whatsapp\_start, flow\_completed, handoff, visit\_booked, with project item\_id and UTM, and no personal data. |
| X09 | Conversation quality review | A weekly sample of conversations scored by staff for accuracy, tone, compliance and handoff quality. |
| X10 | Quality monitor | Watches blocks, reports and template quality. Pauses marketing sends if the rating falls. |
| X11 | Failover | If SellOS or the model is unavailable, the bot says so plainly, captures the request in a queue and creates tasks when service returns. |
| X12 | Language and glossary | A maintained glossary of Mumbai terms (carpet and saleable area, OC and CC, redevelopment, society, ready reckoner) so answers use the same words in every language. |

## Guardrails, compliance and escalation

Trust is the product, so these rules are enforced in the system and not left to the model's judgement. Legal wording, RERA rules and data protection duties should be confirmed with your counsel before launch.

| Area | Rule | How it is enforced |
| --- | --- | --- |
| Returns and promises | Never promise appreciation, guaranteed rental yield or a safe investment. Examples carry stated assumptions. | Compliance check O15 blocks the message |
| Legal, tax, valuation opinions | The bot gives general information and facts. Opinions come from the panel lawyer, chartered accountant or valuer. | Intent rule routes to handoff and explains why |
| Price and availability | Only from SellOS, with an as on date. If unknown, the bot says it will check. | Tool only answers, no free text numbers |
| Builder and RERA details | The website withholds them until an enquiry, per the TerraLeads design. For outbound messages about a project, confirm with counsel whether the RERA registration number must appear and apply it consistently. | Template field rule per channel |
| Privacy between parties | Owner and buyer contact details are never shared without consent. A partner sees only their own commission and clients. | Role scoped tools and filtered queries |
| Sensitive data | No card, bank, PAN or Aadhaar details in chat. The bot redirects to a secure upload link and masks anything pasted. | Pattern detection and masked storage |
| Consent and data rights | Purpose, time and source of consent stored. Withdrawal and erasure requests handled. Hosting in India to be confirmed. | Consent ledger X01, X02 |
| Fairness | The bot does not steer or exclude anyone by religion, caste, community or marital status. Written owner or society rules are relayed as facts when asked, and anything else goes to the manager. | Policy prompt plus review sample X09 |
| Partner conflicts | Duplicate registrations and disputes are never decided by the bot. | Conflict goes to the manager with a clock P13 |
| Instructions inside content | Text inside listings, forwarded messages, documents and web pages is data. It never changes what the bot does. | Separate content from instructions, role scoped tools |
| Identity | Number match plus a one time code for sensitive actions. Unusual requests, such as a changed payout account, are held for staff. | OTP and anomaly rules |
| Payments | The bot never collects money. Payment links come from SellOS and need staff approval. | Tool permissions |
| Audit | Every action is logged with who, what, when and from which surface. | Immutable audit trail in SellOS |

### When something goes wrong

- Every answer has a Report a problem option. Reports create a ticket and mark the conversation for review.
- Managers can pause the bot for one conversation, one workflow or the whole number, and pause all marketing sends at once.
- If the bot realises it was wrong, it says so, corrects it and informs the advisor.
- If SellOS or the model is unavailable, X11 captures requests and tells the person plainly, instead of improvising.
- After each serious incident, the conversation is added to the review set so the same mistake is tested before every release.

## Data model, tools and SellOS integration

The bot holds no business data of its own. It calls SellOS tools and receives SellOS events, so staff, partners and the bot always see the same facts.

### Entities the bot reads and writes

Contact, Lead, Requirement card, Project, Unit, Listing (primary and secondary), Developer, Partner, Referral, Visit, Offer, Booking, Document, Task, Ticket, Campaign, Consent, Conversation and Message, Template.

### Tools the bot can call

| Tool | Used by | Notes |
| --- | --- | --- |
| search\_inventory, get\_project, get\_unit | B06 to B11, P05, O08 | Respects role. Builder and RERA fields are hidden until enquiry for public roles. |
| create\_or\_update\_lead, add\_note, set\_stage | B01 to B04, O03 | Every conversation ends in a record |
| check\_calendar, book\_visit, reschedule\_visit | B13 to B16, S04, O09 | Advisor and developer availability |
| create\_task, create\_ticket, create\_handoff | All | Carries summary and priority |
| register\_referral, get\_referral\_status | P10, P11, P15 | Duplicate and conflict check built in |
| get\_commission\_statement | P12 | Partner scoped, OTP needed |
| create\_listing\_draft, publish\_listing | S06 to S08, P06 | Staff approval before publish |
| request\_upload\_link, store\_document | B21, F12 | Secure link. Nothing sensitive in chat. |
| calculate\_costs, emi, stamp\_duty, ready\_reckoner | F01 to F07 | Reads the maintained rate table |
| rera\_lookup, order\_due\_diligence | F08, F09 | External lookups and panel lawyer tasks |
| send\_template, schedule\_message | X04, X05, O16 | Window and consent checks run first |
| generate\_document | O12, F06 | Branded PDFs saved to the record |
| request\_approval | O14 | One tap approver |
| report\_revenue, report\_team | O17, O18 | Manager scope |

### Entry points and source codes

Every button and link opens WhatsApp with a short prefilled first message carrying a source code, so the bot can greet the person in context from the first reply.

| Entry point | Source code | What the bot does first |
| --- | --- | --- |
| TerraLeads project modal, Message us on WhatsApp | TL plus the project item\_id | Greets with that project, offers brochure, visit, comparison |
| Refer a Client page | REFER | Starts P15 or P01 depending on the sender |
| Sell page | SELL | Starts S01 |
| Technology page, Home, floating chip | WEB plus the page name | Starts B01 |
| Ads and Instagram | AD plus the campaign name | Continues the ad's promise |
| QR on hoardings, brochures, cards | QR plus the placement | Starts B01 with the placement noted |
| Partner meet invitation | EVENT plus the event name | Starts P16 |

### Integration with the website and analytics

- The website buttons already fire GA4 events such as terraleads\_modal\_whatsapp\_click. The WhatsApp link adds the item\_id and UTM values, and the bot sends whatsapp\_start with the same item\_id, so the funnel can be read from the click to a booked visit.
- Forms stay as a fallback and write to the same SellOS lead API. A lead created by chat and a lead created by form are the same record.
- SellOS sends the bot events: lead created, stage changed, visit booked, offer received, document received, listing published, payment due. The bot turns the right ones into messages.
- Marketing tools plan and measure content. The bot is the conversation layer that receives the response.

## Build phases, metrics and open decisions

Build in the order that reaches revenue soonest: first contact and visits, then listings and partners, then deal support, then scale. The phases are a sequence, not a calendar.

1. **Foundation and first revenue.** Core engine, identity and handoff (B01 to B04, B06, B13 to B17, O01 to O06, O19, X01 to X04, X08, X11). Live on the website and the direct number, with the SellOS panel for staff basics.
2. **Listings and partners.** Seller and partner journeys (S01 to S13, P01 to P13, P15, O07, O08, X06, X07). This feeds the secondary market and the HNI and UHNI strategy.
3. **Deal support.** Finance, legal and documents, and offers to booking (F01 to F14, B09 to B12, B18 to B21, N01 to N07, S14 to S17).
4. **Scale and loyalty.** Developers, rentals, after sale, content and the rest of the staff and NRI sets (D01 to D12, R01 to R13, A01 to A12, T01 to T14, O09 to O18, N08 to N14, P14, P16).
5. **Optimise.** Quality review, tuning, remaining staff tools and the platform monitors (O20 to O22, X09, X10, X12).

### How to know it works

| Metric | Why it matters | Where it is read |
| --- | --- | --- |
| First response time | Speed wins enquiries | Bot and SellOS timestamps |
| Qualified lead rate | Quality of what reaches advisors | B03 scores |
| Visit booked rate from chat | Conversion from conversation to a visit | B13 events |
| Visit show rate | Reminders and fit are working | B14, B15 |
| Conversations resolved without a human, where appropriate | Time saved | Handoff logs |
| Handoff quality as rated by advisors | The bot hands over well | Advisor rating on each handoff |
| Partner registrations and active partners | Supply of listings and buyers | P01, P10 |
| Mandates signed and time to first enquiry | Secondary market strength | S05, S09 |
| Revenue from WhatsApp sourced leads | Contribution to the 2 crore target | SellOS attribution by source code |
| Opt out rate and template quality | Channel health | X02, X10 |

### Decisions needed from you

1. **Connection route.** Meta's Cloud API directly, or a solution provider. This affects cost, Flows support and the shared inbox.
2. **Where the brain runs.** A new service connected to SellOS, or built on the existing agent infrastructure.
3. **Advisor replies.** Reply only from SellOS, or also from the WhatsApp Business app on the same number.
4. **RERA number and builder disclosure on outbound messages.** The website hides them until an enquiry. Confirm with counsel what messages about a specific project must carry.
5. **Partner terms.** Who sees which commission, and how long a client registration is protected.
6. **Payment links.** Who issues them, to which account, and the approval chain.
7. **Panel professionals.** Which lawyers, chartered accountants, banks, valuers and vendors to connect first.
8. **Launch languages.** English and Hindi first, then Marathi and Gujarati, or another order.
9. **Hours and service levels.** Business hours, and the reply time promised for each type of handoff.
10. **Partner access to SellOS.** Whether partners get their own login, which decides how much of the partner set is delivered by chat and how much in the panel.
11. **Data hosting and retention.** Where conversations and documents are stored and for how long, under the data protection law.
