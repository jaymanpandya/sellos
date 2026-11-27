"""The bake-off's fixed text (SOS-N21A): 20 caller lines with their entities, the keyterms and the 20 agent replies.

docs/bakeoff/reference.tsv, sentences.md and the two rating sheets are written from this module by
`scripts/bakeoff.sh --templates`, and a test checks that the files in docs match it.
"""

import json
from pathlib import Path

# (file, reference, numbers, prices, localities): entities are ';' separated, empty when there is none.
CALLER_LINES = (
	("01.wav", "Namaste, mujhe Bandra West mein ek 2 BHK flat dekhna hai, budget teen crore tak hai.", "2", "3 crore", "Bandra West"),
	("02.wav", "Carpet area kitna hai aur parking kitni milti hai?", "", "", ""),
	("03.wav", "Possession December 2027 ka hai, lekin RERA number kya hai?", "2027", "", ""),
	("04.wav", "Andheri East mein ready to move flat chahiye, price do crore pachaas lakh ke andar.", "", "2.5 crore", "Andheri East"),
	("05.wav", "Main kal shaam chhe baje site visit ke liye aa sakta hoon.", "6", "", ""),
	("06.wav", "Maintenance charge har mahine kitna padega?", "", "", ""),
	("07.wav", "Loan approval ke liye mujhe bank ka contact number chahiye.", "", "", ""),
	("08.wav", "Aap WhatsApp pe brochure bhej dijiye, number nau aath saat chhe paanch chaar teen do ek zero hai.", "9876543210", "", ""),
	("09.wav", "Sea facing wala flat available hai kya, ya sirf city view?", "", "", ""),
	("10.wav", "Mera naam Rahul Mehta hai, main NRI hoon aur Dubai mein rehta hoon.", "", "", ""),
	("11.wav", "Booking amount kitna hoga, aur payment plan kya hai?", "", "", ""),
	("12.wav", "Resale flat hai ya developer se seedha?", "", "", ""),
	("13.wav", "Floor rise charge alag se lagega kya?", "", "", ""),
	("14.wav", "Mujhe abhi baat nahi karni, kal subah gyarah baje call kijiye.", "11", "", ""),
	("15.wav", "Stamp duty aur registration milake total kitna padega?", "", "", ""),
	("16.wav", "Powai ya Goregaon, dono mein se kaunsa better rahega investment ke liye?", "", "", "Powai;Goregaon"),
	("17.wav", "Worli mein ek tower hai jahan mujhe 3 BHK chahiye.", "3", "", "Worli"),
	("18.wav", "Kya aap AI ho ya insaan?", "", "", ""),
	("19.wav", "Thoda dheere boliye, line mein awaaz kat rahi hai.", "", "", ""),
	("20.wav", "Rate per square foot kitna chal raha hai is area mein, around 45 hazaar?", "", "45 hazaar", ""),
)  # fmt: skip

# Real estate words sent to Deepgram Nova-3 as keyterms.
KEYTERMS = (
	"BHK", "carpet area", "RERA", "possession", "maintenance", "floor rise", "stamp duty", "registration",
	"booking amount", "payment plan", "resale", "site visit", "sea facing", "ready to move", "square foot",
	"parking", "loan approval", "brochure", "WhatsApp", "NRI", "Bandra West", "Andheri East", "Powai",
	"Goregaon", "Worli",
)  # fmt: skip

SYSTEM_PROMPT = (
	"You are the voice assistant of a real estate agency in Mumbai, speaking on a phone call. "
	"Answer the caller's last line in one or two short spoken sentences, in Roman Hinglish (Hindi written "
	"in English letters, the way people speak in Mumbai). Use only the facts in the lead context. Say "
	"numbers as words the way a person says them aloud. If asked, say plainly that you are an AI "
	"assistant. Never pressure the caller."
)

# (caller line, lead context, reference reply). The first reply is a draft of the AI disclosure line;
# SOS-N21 sets the final one. The 20 replies are also the text each text to speech provider speaks.
REPLIES = (
	("Hello, kaun bol raha hai?", "Lead: Rahul Mehta, asked about a 2 BHK in Bandra West. This is the first line of the call.", "Namaste, main ek real estate agency ki AI assistant bol rahi hoon, koi insaan nahin. Kya main aapse do minute baat kar sakti hoon?"),
	("Carpet area kitna hai aur parking kitni milti hai?", "Project Sea Crest, Bandra West: 2 BHK carpet area 780 sq ft, one covered parking included.", "2 BHK ka carpet area sat sau assi square feet hai, aur ek covered parking price mein shamil hai."),
	("Possession December 2027 ka hai, lekin RERA number kya hai?", "The RERA number is printed on the brochure; the agent can send it on WhatsApp. Possession is December 2027.", "RERA number brochure mein hai, main use abhi WhatsApp par bhej deti hoon. Possession December 2027 hi rakha gaya hai."),
	("Andheri East mein ready to move flat chahiye, price do crore pachaas lakh ke andar.", "Two ready to move 2 BHK units in Andheri East: 2.30 crore and 2.45 crore.", "Andheri East mein do ready to move 2 BHK hain, ek do crore tees lakh ka aur ek do crore paintalis lakh ka. Dono aapke budget mein hain."),
	("Main kal shaam chhe baje site visit ke liye aa sakta hoon.", "Site visits run from 10 am to 7 pm. Sales executive Anita is free tomorrow evening.", "Bilkul, kal shaam chhe baje ke liye site visit pakki kar deti hoon. Anita ji aapko gate par milengi."),
	("Maintenance charge har mahine kitna padega?", "Maintenance is Rs 4 per sq ft per month. The unit is 780 sq ft.", "Maintenance chaar rupaye per square foot per mahina hai, matlab lagbhag teen hazaar ek sau bees rupaye mahina."),
	("Loan approval ke liye mujhe bank ka contact number chahiye.", "The sales team shares the tie-up bank manager's contact on WhatsApp. The agent does not read it out.", "Main hamare tie-up bank ke manager ka contact abhi WhatsApp par bhej deti hoon, woh loan approval mein madad karenge."),
	("Aap WhatsApp pe brochure bhej dijiye, number nau aath saat chhe paanch chaar teen do ek zero hai.", "The caller gave a WhatsApp number. Ask them to repeat it digit by digit to confirm it.", "Zaroor, main brochure bhej rahi hoon. Number ek baar dobara bata dijiye, main ek ek digit confirm kar leti hoon."),
	("Sea facing wala flat available hai kya, ya sirf city view?", "Sea facing units are on floors 12 and above. Lower floors have a city view.", "Sea facing flat barahvin manzil se upar available hain, neeche ki manzilon par city view milta hai."),
	("Mera naam Rahul Mehta hai, main NRI hoon aur Dubai mein rehta hoon.", "NRI buyers are welcome. Payment is accepted from NRE accounts. A video site visit can be arranged.", "Rahul ji, namaste. NRI buyers ke liye hum video site visit aur NRE account se payment ki suvidha dete hain."),
	("Booking amount kitna hoga, aur payment plan kya hai?", "Booking amount is 10 percent. The rest is paid in stages linked to construction.", "Booking amount das percent hai, aur baaki payment construction ke stages ke hisaab se hoti hai."),
	("Resale flat hai ya developer se seedha?", "All units are sold directly by the developer. There is no resale unit.", "Yeh flat seedha developer se hai, resale nahin hai."),
	("Floor rise charge alag se lagega kya?", "Floor rise is Rs 50 per sq ft for each floor above the 5th floor.", "Haan, paanchvi manzil ke upar har floor par pachaas rupaye per square foot floor rise charge lagta hai."),
	("Mujhe abhi baat nahi karni, kal subah gyarah baje call kijiye.", "The caller asked for a call back tomorrow at 11 am. Record it and do not push.", "Koi baat nahin, main kal subah gyarah baje dobara call karungi. Aapka samay dene ke liye dhanyavaad."),
	("Stamp duty aur registration milake total kitna padega?", "Stamp duty and registration come to about 6 percent of the agreement value plus Rs 30,000. The agreement value is 3 crore.", "Aapke teen crore ke flat par stamp duty aur registration milake lagbhag atharah lakh tees hazaar rupaye padenge."),
	("Powai ya Goregaon, dono mein se kaunsa better rahega investment ke liye?", "Do not give investment advice. Offer the rental yield and price growth figures from the company's data sheet.", "Main investment ki salaah nahin de sakti, lekin dono jagah ke rental yield aur price growth ke aankde aapko bhej sakti hoon."),
	("Worli mein ek tower hai jahan mujhe 3 BHK chahiye.", "Worli tower: 3 BHK units from 6.5 crore.", "Worli ke tower mein 3 BHK saade chhe crore se shuru hote hain. Kya main floor plan bhej doon?"),
	("Kya aap AI ho ya insaan?", "Always say truthfully that you are an AI assistant, and offer a human sales executive.", "Main ek AI assistant hoon, insaan nahin. Agar aap chahein toh main aapko hamare sales executive se jod sakti hoon."),
	("Thoda dheere boliye, line mein awaaz kat rahi hai.", "The line is poor. Slow down and offer to call back.", "Maaf kijiye, main dheere bolti hoon. Agar awaaz abhi bhi kat rahi ho, toh main dobara call kar sakti hoon."),
	("Rate per square foot kitna chal raha hai is area mein, around 45 hazaar?", "This project's rate is Rs 46,500 per sq ft. The area average is about Rs 45,000.", "Is project ka rate chhiyalis hazaar paanch sau rupaye per square foot hai, aur is area ka average lagbhag paintalis hazaar hai."),
)  # fmt: skip

TTS_PROVIDERS = ("sarvam-bulbul-v3", "elevenlabs")
STT_PROVIDERS = ("sarvam-saaras-v3", "deepgram-nova-3")

BASELINE_DIR = Path.home() / "iespl-baseline"
APP_DOCS = Path(__file__).resolve().parents[3] / "docs" / "bakeoff"

# SOS-N21B: the voice language model comparison. Sarvam and Claude Haiku 5.5 answer the AI disclosure
# line and the handover cases, with the same system prompt, so the two are rated on the same text.
HAIKU_MODEL = "claude-haiku-5-5"
SARVAM_MODEL_FILE = "sarvam-llm-model.txt"
TEST_COMPANY = "Test Realty"
HANDOVER_TAG = "[HANDOVER]"
DISCLOSURE_FIELD_JSON = (
	Path(__file__).resolve().parents[2]
	/ "sellos"
	/ "doctype"
	/ "voice_agent_settings"
	/ "voice_agent_settings.json"
)


def default_disclosure(company=TEST_COMPANY):
	"""The default AI disclosure line of SOS-N21C (read from the DocType, so there is one copy), with the
	company name in place of {company}."""
	doctype = json.loads(DISCLOSURE_FIELD_JSON.read_text(encoding="utf-8"))
	field = next(f for f in doctype["fields"] if f["fieldname"] == "disclosure_line")
	return field["default"].replace("{company}", company)


VOICE_SYSTEM_PROMPT = (
	SYSTEM_PROMPT
	+ " When a call connects, open with exactly the AI disclosure line you are given, word for word, even though it is longer than two sentences. "
	"When the caller wants to talk to a person, at any moment and even while you are speaking, or you "
	f"cannot help or the caller is confused, reply only {HANDOVER_TAG} and nothing else."
)


def voice_cases(company=TEST_COMPANY):
	"""(label, caller line, lead context, reference reply): the disclosure line, then the handover cases."""
	line = default_disclosure(company)
	return (
		(
			"Disclosure line",
			"Hello?",
			f"The call has just connected. This is the first line. Open with exactly this AI disclosure line: {line}",
			line,
		),
		(
			"Handover during the disclosure line",
			"Ruko, mujhe kisi insaan se baat karni hai.",
			f"The agent was in the middle of saying the AI disclosure line: {line} The caller spoke over it.",
			HANDOVER_TAG,
		),
		(
			"Handover in the middle of a reply",
			"Ek minute, mujhe human agent se baat karwa dijiye.",
			"The agent was explaining that a 2 BHK in Bandra West has a carpet area of 780 sq ft when the caller interrupted.",
			HANDOVER_TAG,
		),
		(
			"Confused caller",
			"Kya? Mujhe kuch samajh nahi aa raha, yeh kis baare mein call hai?",
			"The caller has asked twice what the call is about. They sound lost and the agent cannot make it clearer.",
			HANDOVER_TAG,
		),
	)
