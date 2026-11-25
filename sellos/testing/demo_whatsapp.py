"""The demo's WhatsApp builder: the company's number, its templates and 42 conversations on its leads.

The content generators at the top are pure (no Frappe import, no bench): they take a random generator, a region
key and a date, and return plain dicts, so the unit tests read them without a site. `build(ctx)` at the bottom is
the Frappe side. It runs last, after the CRM builder has left `ctx.leads`, and makes every conversation through
the production functions of `sellos.whatsapp.conversations` with the fake provider (token `FAKEOK...`), so the
consent warning, the opt in, the stop request and the handoff are what a real conversation leaves. A lead that
already has a conversation is skipped, so a second run creates nothing. Demo seed.
"""

from datetime import datetime, time, timedelta

DEMO_WHATSAPP_TOKEN = "FAKEOK-DEMO-WHATSAPP"  # FAKEOK: the fake provider accepts it
DEMO_WHATSAPP_SECRET = "demo-whatsapp-signing-secret"  # never a real secret

STYLES = ("english", "hinglish", "gujarati", "marathi")
# How the customers of each region write (weights).
STYLE_WEIGHTS = {
	"bom": {"english": 40, "hinglish": 40, "gujarati": 10, "marathi": 10},
	"amd": {"gujarati": 60, "english": 20, "hinglish": 20},
}

# What each kind of conversation leaves, and how many of the 42 of one company are of that kind.
KIND_COUNTS = {
	"waiting": 8,  # the customer wrote last, the conversation is open and waits for a reply
	"template_only": 4,  # a template went out and nobody has replied yet
	"handoff": 5,  # handed to a human with a note
	"closed": 6,
	"stop": 2,  # the person sends STOP
	"start": 2,  # the person sends START
	"warning": 4,  # a lead whose consent status shows a warning
	"chat": 11,  # a back and forth that ends with our reply
}
WARNING_STATES = ("Opted out", "Registered DND")

# The message texts of each style, as pure data. Placeholders: {name} the customer's first name, {project},
# {locality}, {price}, {time}, {agent}, {company}. A customer asks (ask_*), an agent answers (reply_*).
MESSAGES = {
	"english": {
		"ask_price": (
			"Hi, what is the price of a 2 BHK at {project}?",
			"Could you share the all inclusive price for a 3 BHK in {project}, {locality}?",
			"Hello, I saw your ad for {project}. What is the starting price?",
		),
		"ask_availability": (
			"Is a 2 BHK still available at {project}?",
			"Do you have any ready flats left in {locality}?",
			"Which floors are open for a 3 BHK in {project}?",
		),
		"ask_visit": (
			"Can I visit {project} this Saturday around 11 am?",
			"What time can we see the sample flat tomorrow? I am free after 5 pm.",
			"We would like a site visit on Sunday morning, is that possible?",
		),
		"ask_brochure": (
			"Please send the brochure and floor plans for {project}.",
			"Can you share the price sheet and the payment plan here?",
			"Do you have a video walkthrough of {project}?",
		),
		"ask_loan": (
			"Which banks do you tie up with for a home loan?",
			"What is the booking amount, and can the rest be paid through a loan?",
			"Can you help with the loan paperwork? I am a salaried buyer.",
		),
		"ask_possession": (
			"When is the possession for {project}?",
			"Is the building RERA registered, and what is the possession date?",
			"Is there any delay expected on the handover at {project}?",
		),
		"reply_price": (
			"Hello {name}! A 2 BHK at {project} starts at {price} all inclusive. Shall I send the cost sheet?",
			"Hi {name}, the current price there is {price}. The cost sheet has the full breakup.",
		),
		"reply_availability": (
			"Yes {name}, we have a few 2 BHK flats open at {project}. I can hold one for you.",
			"Hi {name}, a couple of units are available, the higher floors are filling fast.",
		),
		"reply_visit": (
			"Sure {name}, I have booked your visit at {time}. I will meet you at the sales office.",
			"That works {name}. Your site visit is confirmed for {time}. Please bring an ID.",
		),
		"reply_brochure": (
			"Sharing the brochure and the price sheet now, {name}. Please check and tell me what you think.",
			"Here is the project brochure, {name}. The payment plan is on the last page.",
		),
		"reply_loan": (
			"We work with three leading banks, {name}. I can set up a call with the loan desk.",
			"Booking amount is 5 percent, the balance can be financed. Our loan partner will call you.",
		),
		"reply_possession": (
			"Possession at {project} is planned for December 2028, and it is RERA registered, {name}.",
			"Construction is on schedule, {name}. The RERA possession date is December 2028.",
		),
		"thanks": (
			"Thanks a lot, this is helpful.",
			"Great, thank you. I will discuss with my family and get back.",
		),
	},
	"hinglish": {
		"ask_price": (
			"Hi, {project} me 2 BHK ka price kya hai?",
			"{locality} me 3 BHK ka all inclusive rate bata dijiye.",
			"Aapka {project} ka ad dekha, starting price kitna hai?",
		),
		"ask_availability": (
			"Kya {project} me 2 BHK abhi available hai?",
			"{locality} me ready to move flats bache hain kya?",
			"{project} me 3 BHK ke liye kaun si floors khuli hain?",
		),
		"ask_visit": (
			"Main Saturday 11 baje {project} aa sakta hoon?",
			"Kal sample flat dekhne ka time kya rahega? Main 5 baje ke baad free hoon.",
			"Sunday subah site visit ho sakta hai kya?",
		),
		"ask_brochure": (
			"{project} ka brochure aur floor plan bhej dijiye please.",
			"Price sheet aur payment plan yahin bhej do.",
			"Kya {project} ka walkthrough video hai?",
		),
		"ask_loan": (
			"Home loan ke liye kaun se banks se tie-up hai?",
			"Booking amount kitna hoga, baaki loan se ho jayega kya?",
			"Loan ke kaagaz me madad milegi? Main job karta hoon.",
		),
		"ask_possession": (
			"{project} ka possession kab milega?",
			"Building RERA registered hai? Possession date kya hai?",
			"Handover me koi delay to nahi hoga na?",
		),
		"reply_price": (
			"Namaste {name} ji! {project} me 2 BHK {price} all inclusive hai. Cost sheet bhejun?",
			"Hi {name}, abhi ka rate {price} hai. Poora breakup cost sheet me hai.",
		),
		"reply_availability": (
			"Ji {name}, {project} me kuch 2 BHK available hain. Main ek aapke liye hold kar deta hoon.",
			"Haan {name} ji, do teen units bache hain, upar ki floors jaldi ja rahi hain.",
		),
		"reply_visit": (
			"Bilkul {name} ji, aapka visit {time} ke liye book hai. Sales office me milenge.",
			"Theek hai {name}, site visit {time} ko confirm hai. ID saath le aaiye.",
		),
		"reply_brochure": (
			"Brochure aur price sheet bhej raha hoon {name} ji. Dekh ke bataiye.",
			"Ye lijiye brochure, {name}. Payment plan aakhri page par hai.",
		),
		"reply_loan": (
			"{name} ji, hum teen bade banks ke saath kaam karte hain. Loan desk se call karwa deta hoon.",
			"Booking amount 5 percent hai, baaki loan ho jayega. Hamare loan partner aapko call karenge.",
		),
		"reply_possession": (
			"{project} ka possession December 2028 hai aur RERA registered hai, {name} ji.",
			"Kaam time par chal raha hai {name}. RERA possession date December 2028 hai.",
		),
		"thanks": (
			"Thanks, ye kaam ka tha.",
			"Theek hai, ghar pe baat karke batata hoon.",
		),
	},
	"gujarati": {
		"ask_price": (
			"Kem cho, {project} ma 2 BHK no bhaav shu chhe?",
			"{locality} ma 3 BHK no all inclusive rate janavso?",
			"Tamari {project} ni jaherat joi, starting price ketlo chhe?",
		),
		"ask_availability": (
			"{project} ma 2 BHK haju available chhe?",
			"{locality} ma ready flat baki chhe ke nahi?",
			"3 BHK mate {project} ma kya mala khali chhe?",
		),
		"ask_visit": (
			"Hu Shanivare 11 vagye {project} jovane aavi shaku?",
			"Aavti kale sample flat jova nu time shu rahese? Hu 5 pachi free chhu.",
			"Ravivare savare site visit thai shake?",
		),
		"ask_brochure": (
			"{project} nu brochure ane floor plan moklo ne.",
			"Price sheet ane payment plan ahi mokli apsho?",
			"{project} no walkthrough video chhe?",
		),
		"ask_loan": (
			"Home loan mate kaya bank sathe tie-up chhe?",
			"Booking amount ketlo thase, baaki loan thi thai jase?",
			"Loan na kagal ma madad malse? Hu job karu chhu.",
		),
		"ask_possession": (
			"{project} nu possession kyare malse?",
			"Building RERA registered chhe? Possession date shu chhe?",
			"Handover ma koi delay to nahi thay ne?",
		),
		"reply_price": (
			"Namaste {name},{project} ma 2 BHK {price} all inclusive chhe. Cost sheet mokalu?",
			"Kem cho {name}, atyare no bhaav {price} chhe. Pura breakup cost sheet ma chhe.",
		),
		"reply_availability": (
			"Ha {name}, {project} ma thoda 2 BHK baki chhe. Hu tamara mate hold kari dau.",
			"Ha {name}, be traan unit baki chhe, upar na mala jaldi jai rahya chhe.",
		),
		"reply_visit": (
			"Chokkas {name}, tamaro visit {time} e book chhe. Sales office par malishu.",
			"Saru {name}, site visit {time} e confirm chhe. ID sathe lai aavjo.",
		),
		"reply_brochure": (
			"Brochure ane price sheet mokli rahyo chhu {name}. Jova ne janavjo.",
			"Aa lo brochure, {name}. Payment plan chhella page par chhe.",
		),
		"reply_loan": (
			"{name}, ame traan mota bank sathe kaam karie chhie. Loan desk thi call karavu.",
			"Booking amount 5 taka chhe, baaki loan thi thai jase. Amara loan partner call karse.",
		),
		"reply_possession": (
			"{project} nu possession December 2028 chhe ane RERA registered chhe, {name}.",
			"Kaam samay par chale chhe {name}. RERA possession date December 2028 chhe.",
		),
		"thanks": (
			"Aabhar, khub upyogi hatu.",
			"Saru, ghare vaat kari ne janavish.",
		),
	},
	"marathi": {
		"ask_price": (
			"Namaskar, {project} madhe 2 BHK cha rate kay aahe?",
			"{locality} madhe 3 BHK cha all inclusive bhav sanga ki.",
			"Tumchi {project} chi jahirat pahili, starting price kiti aahe?",
		),
		"ask_availability": (
			"{project} madhe 2 BHK ajun available aahe ka?",
			"{locality} madhe ready flats shillak aahet ka?",
			"3 BHK sathi {project} madhe konte floors mokle aahet?",
		),
		"ask_visit": (
			"Mi Shanivari 11 vajta {project} pahayla yeu shakto ka?",
			"Udya sample flat pahayla kiti vajta yeu? Mi 5 nantar free aahe.",
			"Ravivari sakali site visit hou shakel ka?",
		),
		"ask_brochure": (
			"{project} cha brochure ani floor plan pathva na.",
			"Price sheet ani payment plan ithech pathva.",
			"{project} cha walkthrough video aahe ka?",
		),
		"ask_loan": (
			"Home loan sathi konkonatya banks shi tie-up aahe?",
			"Booking amount kiti lagel, baaki loan ne hoil ka?",
			"Loan chya kagadpatra madhe madat milel ka? Mi nokri karto.",
		),
		"ask_possession": (
			"{project} cha possession kevha milel?",
			"Building RERA registered aahe ka? Possession date kay aahe?",
			"Handover la kahi vilamb honar nahi na?",
		),
		"reply_price": (
			"Namaskar {name}! {project} madhe 2 BHK {price} all inclusive aahe. Cost sheet pathvu ka?",
			"Hi {name}, sadhya cha rate {price} aahe. Purna breakup cost sheet madhe aahe.",
		),
		"reply_availability": (
			"Ho {name}, {project} madhe kahi 2 BHK shillak aahet. Mi tumchyasathi hold karto.",
			"Ho {name}, don teen units aahet, varche floors lavkar jaat aahet.",
		),
		"reply_visit": (
			"Nakki {name}, tumcha visit {time} la book aahe. Sales office madhe bhetu.",
			"Thik aahe {name}, site visit {time} la confirm aahe. ID barobar ghya.",
		),
		"reply_brochure": (
			"Brochure ani price sheet pathvto aahe {name}. Pahun sanga.",
			"He ghya brochure, {name}. Payment plan shevtchya pageevar aahe.",
		),
		"reply_loan": (
			"{name}, amhi tin motthya banks barobar kaam karto. Loan desk kadun call karvto.",
			"Booking amount 5 tkke aahe, baaki loan ne hoil. Amche loan partner call kartil.",
		),
		"reply_possession": (
			"{project} cha possession December 2028 la aahe ani RERA registered aahe, {name}.",
			"Kaam veli chalu aahe {name}. RERA possession date December 2028 aahe.",
		),
		"thanks": (
			"Dhanyavad, khup upyogi hota.",
			"Thik aahe, gharat bolun kalavto.",
		),
	},
}

# What the bot (a template or an automatic reply) says, per style.
BOT = {
	"english": {
		"stop_confirm": "You will not get messages from {company} unless you write to us. You can still message us here.",
		"start_welcome": "Thank you {name}, you are now on the list for updates from {company}. Ask us anything here.",
	},
	"hinglish": {
		"stop_confirm": "Ab {company} aapko koi message nahi bhejega jab tak aap khud na likhen. Aap yahan likh sakte hain.",
		"start_welcome": "Shukriya {name} ji, ab aapko {company} ke updates milenge. Kuch bhi poochhna ho to yahin likhiye.",
	},
	"gujarati": {
		"stop_confirm": "Have {company} tamne message nahi moklse jyaa sudhi tame pote na lakho. Tame ahi lakhi shako chho.",
		"start_welcome": "Aabhar {name}, have tamne {company} na updates malse. Kai pan puchhvu hoy to ahi lakho.",
	},
	"marathi": {
		"stop_confirm": "Ata {company} tumhala message pathvnar nahi, tumhi swata lihit nahi tovar. Tumhi ithe lihu shakta.",
		"start_welcome": "Dhanyavad {name}, ata tumhala {company} che updates milatil. Kahihi vicharaycha asel tar ithe liha.",
	},
}

# The note an agent leaves when handing a conversation to a human.
HANDOFF_NOTES = (
	"Asks about the booking amount and home loan tie ups, please call today.",
	"Wants a negotiation on the price for two units, needs the sales head.",
	"Asked for a callback in the evening about the payment plan.",
	"NRI buyer, needs help with the power of attorney and the payment route.",
	"Comparing two towers, wants a senior advisor to explain the floor rise charges.",
	"Wants to move the site visit to the weekend and bring the family, please confirm by phone.",
)

# The WhatsApp templates a company uses: (name, language, category, body with {company}). {{1}} is the customer's
# first name and {{2}} the visit time, project or advisor. Gujarati ones only for the Ahmedabad company.
TEMPLATES = (
	(
		"site_visit_reminder",
		"en",
		"Utility",
		"Hello {{1}}, a reminder from {company}: your site visit is at {{2}}. Reply here to change the time.",
	),
	(
		"site_visit_reminder_hi",
		"hi",
		"Utility",
		"Namaste {{1}}, {company} ki taraf se yaad dilana: aapka site visit {{2}} par hai. Time badalna ho to yahin likhiye.",
	),
	(
		"site_visit_reminder_gu",
		"gu",
		"Utility",
		"Namaste {{1}}, {company} taraf thi yaad: tamaro site visit {{2}} e chhe. Samay badalvo hoy to ahi lakho.",
	),
	(
		"welcome_enquiry",
		"en",
		"Utility",
		"Hello {{1}}, thank you for contacting {company}. Your advisor {{2}} will call you shortly.",
	),
	(
		"welcome_enquiry_hi",
		"hi",
		"Utility",
		"Namaste {{1}}, {company} se sampark karne ke liye shukriya. Aapke advisor {{2}} aapko jaldi call karenge.",
	),
	(
		"welcome_enquiry_gu",
		"gu",
		"Utility",
		"Namaste {{1}}, {company} no sampark karva badal aabhar. Tamara advisor {{2}} tamne jaldi call karse.",
	),
	(
		"brochure_share",
		"en",
		"Utility",
		"Hi {{1}}, thank you for your interest in {{2}}. {company} has shared the brochure and price sheet here.",
	),
	(
		"brochure_share_hi",
		"hi",
		"Utility",
		"Hi {{1}}, {{2}} me dilchaspi ke liye shukriya. {company} ne brochure aur price sheet yahan bheji hai.",
	),
	(
		"instalment_reminder",
		"en",
		"Utility",
		"Hello {{1}}, a gentle reminder from {company}: your next instalment of {{2}} is due this week.",
	),
	(
		"new_launch_update",
		"en",
		"Marketing",
		"Hi {{1}}, {company} has a new launch, {{2}}. Reply here to get the brochure and the price sheet.",
	),
)
# The template a style uses (the visit reminder, the welcome and the brochure).
TEMPLATE_OF = {
	"english": ("site_visit_reminder", "welcome_enquiry", "brochure_share"),
	"hinglish": ("site_visit_reminder_hi", "welcome_enquiry_hi", "brochure_share_hi"),
	"marathi": ("site_visit_reminder_hi", "welcome_enquiry_hi", "brochure_share_hi"),
	"gujarati": ("site_visit_reminder_gu", "welcome_enquiry_gu", "brochure_share"),
}
VISIT_TIMES = ("Saturday 11 am", "Sunday 10.30 am", "tomorrow 5.30 pm", "Saturday 4 pm", "Friday 6 pm")
TOPICS = ("price", "availability", "visit", "brochure", "loan", "possession")


def templates_for(region):
	"""The templates of a company: Gujarati ones only for Ahmedabad."""
	return [t for t in TEMPLATES if region == "amd" or t[1] != "gu"]


def company_body(body, company):
	"""A template body with the company's name in. Only `{company}` is replaced: `str.format` would turn the
	template's own `{{1}}` and `{{2}}` into `{1}` and `{2}`, which no message could fill."""
	return body.replace("{company}", company)


def all_texts():
	"""Every message text of every style (for the tests)."""
	for style in STYLES:
		yield from (text for group in MESSAGES[style].values() for text in group)
		yield from BOT[style].values()


def price_text(rupees):
	"""A price in lakh or crore, the way people write it: 1.85 crore, 85 lakh."""
	rupees = float(rupees)
	if rupees >= 10_000_000:
		return f"Rs {rupees / 10_000_000:.2f} crore"
	return f"Rs {round(rupees / 100_000)} lakh"


def pick_style(rng, region):
	weights = STYLE_WEIGHTS[region]
	return rng.choices(list(weights), weights=list(weights.values()))[0]


def pick_leads(rng, leads):
	"""(lead, kind) for the 42 conversations. The leads are spread over the stages; the warning ones are leads
	whose consent shows a warning, the START and STOP ones are leads with an unknown consent."""
	total = sum(KIND_COUNTS.values())
	ordered = sorted(leads, key=lambda lead: lead["name"])
	chosen, taken = [], set()

	def take(pool, n, kind):
		pool = [lead for lead in pool if lead["name"] not in taken]
		by_stage = {}
		for lead in pool:
			by_stage.setdefault(lead.get("stage", ""), []).append(lead)
		for group in by_stage.values():
			rng.shuffle(group)
		stages = sorted(by_stage)
		found = []
		while len(found) < n and any(by_stage.values()):
			for stage in stages:
				if by_stage[stage] and len(found) < n:
					found.append(by_stage[stage].pop())
		for lead in found:
			taken.add(lead["name"])
			chosen.append((lead, kind))
		return len(found)

	warned = take(
		[lead for lead in ordered if lead.get("consent") in WARNING_STATES], KIND_COUNTS["warning"], "warning"
	)
	unknown = [lead for lead in ordered if lead.get("consent") == "Unknown"]
	for kind in ("stop", "start"):
		found = take(unknown, KIND_COUNTS[kind], kind)
		take(ordered, KIND_COUNTS[kind] - found, kind)  # too few Unknown leads: any other lead
	rest = [kind for kind in KIND_COUNTS if kind not in ("warning", "stop", "start")]
	kinds = [kind for kind in rest for _ in range(KIND_COUNTS[kind])]
	kinds += ["chat"] * (KIND_COUNTS["warning"] - warned)
	rng.shuffle(kinds)
	take(ordered, len(kinds), "")
	chosen_rest = [pair for pair in chosen if pair[1] == ""]
	chosen = [pair for pair in chosen if pair[1] != ""]
	chosen += [(lead, kind) for (lead, _), kind in zip(chosen_rest, kinds, strict=False)]
	if len(chosen) < total:
		raise ValueError(f"Only {len(chosen)} leads fit the {total} WhatsApp conversations.")
	return chosen


def make_steps(rng, kind, style, data):
	"""The steps of one conversation: ("in", text), ("out", text), ("template", (name, [p1, p2])), ("handoff",
	note), ("close", None), ("task", title). `data` holds name, project, locality, price, time, agent, company."""

	def ask(topic):
		return ("in", rng.choice(MESSAGES[style][f"ask_{topic}"]).format(**data))

	def reply(topic):
		return ("out", rng.choice(MESSAGES[style][f"reply_{topic}"]).format(**data))

	first, second, third = rng.sample(TOPICS, 3)
	visit_t, welcome_t, brochure_t = TEMPLATE_OF[style]
	if kind == "waiting":
		steps = [ask(first)]
		if rng.random() < 0.5:
			steps += [reply(first), ask(second)]
		return steps
	if kind == "template_only":
		name, params = rng.choice(
			(
				(visit_t, [data["name"], data["time"]]),
				(welcome_t, [data["name"], data["agent"]]),
				(brochure_t, [data["name"], data["project"]]),
			)
		)
		return [("template", (name, params))]
	if kind == "handoff":
		return [
			ask("loan"),
			reply("loan"),
			ask(second if second != "loan" else third),
			("handoff", rng.choice(HANDOFF_NOTES)),
		]
	if kind == "closed":
		return [
			ask(first),
			reply(first),
			("in", rng.choice(MESSAGES[style]["thanks"]).format(**data)),
			("out", rng.choice(MESSAGES[style][f"reply_{second}"]).format(**data)),
			("close", None),
		]
	if kind == "stop":
		return [
			ask(first),
			reply(first),
			("in", "STOP"),
			("out", BOT[style]["stop_confirm"].format(**data)),
			("task", "WhatsApp STOP: confirm the opt out with the customer and keep them off campaigns"),
		]
	if kind == "start":
		return [
			("in", "START"),
			("out", BOT[style]["start_welcome"].format(**data)),
			ask(first),
			reply(first),
		]
	# chat and warning: a back and forth that ends with our reply
	steps = [ask(first), reply(first), ask(second), reply(second)]
	if rng.random() < 0.4:
		steps += [ask(third), reply(third)]
	return steps


def schedule(rng, today, kind, steps):
	"""One datetime per step, in the past, within one day: the conversation starts `days` days before `today`."""
	days = rng.randint(1, 2) if kind in ("waiting", "chat") else rng.randint(2, 38)
	if kind == "template_only":
		days = rng.randint(1, 5)
	moment = datetime.combine(today - timedelta(days=days), time(rng.randint(9, 16), rng.randint(0, 59)))
	times = []
	for _step in steps:
		times.append(moment)
		moment += timedelta(minutes=rng.randint(2, 40))
	return times


def plan(rng, region, today, leads, projects, company):
	"""The 42 conversations of a company: [{lead, kind, style, steps, times}], each a plain dict. `leads` are
	{name, client_name, stage, consent, ...}; `projects` are {name, locality, prices: [rupees]}."""
	plans = []
	for lead, kind in pick_leads(rng, leads):
		style = pick_style(rng, region)
		project = rng.choice(projects)
		prices = project.get("prices") or [18_500_000]
		data = {
			"name": lead["client_name"].split()[0],
			"project": project["name"],
			"locality": project["locality"],
			"price": price_text(rng.choice(prices)),
			"time": rng.choice(VISIT_TIMES),
			"agent": lead.get("agent_name") or "your advisor",
			"company": company,
		}
		steps = make_steps(rng, kind, style, data)
		if region != "amd":  # the Gujarati templates are the Ahmedabad company's only
			steps = [(k, (p[0].removesuffix("_gu"), p[1])) if k == "template" else (k, p) for k, p in steps]
		plans.append(
			{
				"lead": lead["name"],
				"kind": kind,
				"style": style,
				"steps": steps,
				"times": schedule(rng, today, kind, steps),
			}
		)
	return plans


# -- the Frappe side -----------------------------------------------------------------------------------


def _save_templates(ctx, admin):
	import frappe

	from sellos.tests import ui_fixtures as fx
	from sellos.whatsapp import settings

	fx._save_whatsapp_account(
		admin, "site_visit_reminder", token=DEMO_WHATSAPP_TOKEN, secret=DEMO_WHATSAPP_SECRET
	)
	for name, language, category, body in templates_for(ctx.word):
		is_new = not frappe.db.exists(settings.TEMPLATE, name)
		with fx._as_user(admin):
			settings.save_whatsapp_template(
				name, company_body(body, ctx.company_name), language, category, status="Approved"
			)
		if is_new:
			ctx.count("created", settings.TEMPLATE)


def _project_rows(ctx):
	import frappe

	rows = []
	for project in ctx.projects:
		name = frappe.db.get_value("Project", project["name"], "project_name") or project["name"]
		prices = [
			u["price"]
			for u in ctx.units
			if u.get("project") == project["name"] and u.get("price") and u["price"] >= 3_000_000
		]
		rows.append(
			{"name": name, "locality": project.get("locality") or ctx.region["city"], "prices": prices[:40]}
		)
	return rows


def build(ctx):
	"""The company's WhatsApp number, its templates and 42 conversations on ctx.leads."""
	import random as _random

	import frappe
	from frappe.utils import add_days

	from sellos.crm import api as crm
	from sellos.testing.demo_ctx import MINIMUMS, SEED_OF
	from sellos.tests import ui_fixtures as fx
	from sellos.whatsapp import conversations
	from sellos.whatsapp.base import InboundMessage, StatusEvent

	admin, agents = ctx.users["admin"], ctx.users["agents"]
	_save_templates(ctx, admin)
	if not ctx.leads or not ctx.projects:
		raise ValueError("The WhatsApp builder needs ctx.leads and ctx.projects: run the CRM builders first.")
	if frappe.db.count("WhatsApp Conversation") >= sum(KIND_COUNTS.values()):
		return  # made by an earlier run (a STOP or START changed the consent the plan was drawn by)
	# A number shared by two clients (or two leads of one client) would land a message on the other lead.
	shared_keys = {
		r[0]
		for r in frappe.db.sql("select phone_key from `tabClient` group by phone_key having count(*) > 1")
	}
	shared_clients = {
		r[0] for r in frappe.db.sql("select client from `tabLead` group by client having count(*) > 1")
	}
	phones, usable = {}, []
	for lead in ctx.leads:
		row = frappe.db.get_value("Lead", lead["name"], ["client", "assigned_to"], as_dict=True)
		if not row or not row.client or row.client in shared_clients:
			continue
		if frappe.db.get_value("Client", row.client, "phone_key") in shared_keys:
			continue
		phone = frappe.db.get_value("Client", row.client, "phone")
		if phone:
			phones[lead["name"]] = (phone, row.assigned_to or lead.get("agent") or agents[0])
			agent_name = frappe.db.get_value("User", phones[lead["name"]][1], "first_name") or ""
			usable.append({**lead, "agent_name": agent_name})
	rng = _random.Random(SEED_OF.get(ctx.word, 20261125) + 7)
	plans = plan(rng, ctx.word, ctx.today, usable, _project_rows(ctx), ctx.company_name)
	by_name = {lead["name"]: lead for lead in usable}
	for number, item in enumerate(plans):
		lead = item["lead"]
		if frappe.db.exists("WhatsApp Conversation", {"lead": lead}):
			continue
		phone, agent = phones[lead]
		if not frappe.has_permission("Lead", "write", doc=lead, user=agent):
			agent = admin  # an assignee who may not write the lead: the Company Admin answers
		client_name = by_name[lead]["client_name"]
		sent, rows = [], []  # [(message name, time, direction)]
		conversation = None
		for step, ((kind, payload), at) in enumerate(zip(item["steps"], item["times"], strict=True)):
			message_id = f"wamid-demo-{ctx.word}-{frappe.scrub(lead)}-{step}"
			if kind == "in":
				result = conversations.receive(InboundMessage(message_id, phone, payload, name=client_name))
				if not result or result["lead"] != lead:
					raise ValueError(f"WhatsApp message of {lead} did not reach its own lead: {result}")
				conversation = result["conversation"]
				rows.append((result["message"], at, "Inbound"))
			elif kind in ("out", "template"):
				with fx._as_user(agent):
					if kind == "out":
						result = conversations.send(lead, text=payload)
					else:
						result = conversations.send(lead, template=payload[0], parameters=payload[1])
				if not result["sent"]:
					raise ValueError(f"WhatsApp message to {lead} was not sent: {result}")
				conversation = conversations.conversation_for(lead)
				rows.append((result["message"], at, "Outbound"))
				sent.append(result["message"])
			elif kind == "handoff":
				to_user = admin if number % 3 == 2 else None
				with fx._as_user(agent):
					conversations.hand_off(conversation, to_user, payload)
				frappe.db.set_value("WhatsApp Conversation", conversation, "handed_on", at)
			elif kind == "close":
				with fx._as_user(agent):
					conversations.close(conversation)
			elif kind == "task":
				if not frappe.db.exists("Lead Task", {"lead": lead, "title": payload}):
					with fx._as_user(agent):
						crm.save_task(
							values={
								"lead": lead,
								"title": payload,
								"due_at": f"{add_days(ctx.today, 1)} 10:00:00",
								"status": "Open",
								"assigned_to": agent,
							}
						)
					ctx.count("created", "Lead Task")
		# Timestamps in the past, in order, and a status for each message we sent.
		last_inbound = None
		for message, at, direction in rows:
			frappe.db.set_value("WhatsApp Message", message, "sent_on", at, update_modified=False)
			if direction == "Inbound":
				last_inbound = at
		for index, message in enumerate(sent):
			provider_id = frappe.db.get_value("WhatsApp Message", message, "provider_message_id")
			replied = any(
				d == "Inbound" and t > frappe.db.get_value("WhatsApp Message", message, "sent_on")
				for _m, t, d in rows
			)
			status = "read" if replied else ("delivered" if (number + index) % 5 else "sent")
			if provider_id:
				conversations.apply_status(StatusEvent(provider_id, status))
		last_at, last_direction = rows[-1][1], rows[-1][2]
		frappe.db.set_value(
			"WhatsApp Conversation",
			conversation,
			{
				"last_message_on": last_at,
				"last_direction": last_direction,
				"last_inbound_on": last_inbound,
			},
			update_modified=False,
		)
		ctx.count("created", "WhatsApp Conversation")
		ctx.count("created", "WhatsApp Message", len(rows))
	total = frappe.db.count("WhatsApp Conversation")
	if total < MINIMUMS["whatsapp_conversations"]:
		raise ValueError(
			f"{total} WhatsApp conversations, at least {MINIMUMS['whatsapp_conversations']} needed."
		)
