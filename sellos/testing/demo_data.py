"""The content of the demo companies' inventory, deals, partners and WhatsApp conversations.

Pure data, no Frappe import, so a unit test can check it without a bench (sellos/testing/test_demo_data.py).
sellos/testing/demo.py turns it into records through the production APIs. Every developer, project and
person here is made up. Phone numbers are never written here: demo.py takes them from sellos.tests.phones.
Prices are in rupees; areas are carpet area in square feet.
"""

# One entry per company word (sellos.testing.demo.COMPANIES). `leads` indexes refer to that company's
# own lead rows (demo.COMPANIES[i]["leads"]).
MARKET = {
	"skyline": {
		"developers": (
			("Meridian Habitat Developers", "Rakesh Bhatia", "sales@meridianhabitat.example.com"),
			("Shreyas Landmark Realty", "Nandini Karnik", "sales@shreyaslandmark.example.com"),
		),
		# project name, developer index, RERA number, locality, city, status, rate per sq ft, units
		# Each unit: number, configuration, floor, carpet area, parking.
		"projects": (
			{
				"name": "Meridian Skyline Residences",
				"developer": 0,
				"rera": "P51800031001",
				"locality": "Andheri West",
				"city": "Mumbai",
				"status": "Under construction",
				"possession": "2028-06-30",
				"rate": 31000,
				"tower": ("Tower A", 10, ((1001, 1004), (1101, 1104), (1201, 1204)), 640, "2 BHK"),
				"three_bhk": ("1004", "1104", "1204"),
				"amenities": ("Swimming pool", "Gym", "Clubhouse", "Children's play area"),
			},
			{
				"name": "Powai Lakeview Heights",
				"developer": 0,
				"rera": "P51800031002",
				"locality": "Powai",
				"city": "Mumbai",
				"status": "Ready to move",
				"rate": 27500,
				"units": (
					("PL-1201", "2 BHK", 12, 650, 1),
					("PL-1202", "2 BHK", 12, 668, 1),
					("PL-1403", "3 BHK", 14, 905, 2),
					("PL-1504", "3 BHK", 15, 930, 2),
				),
			},
			{
				"name": "Worli Sea Crest",
				"developer": 1,
				"rera": "P51800031003",
				"locality": "Worli",
				"city": "Mumbai",
				"status": "Under construction",
				"rate": 56000,
				"units": (
					("W-2301", "3 BHK", 23, 1180, 2),
					("W-2401", "3 BHK", 24, 1195, 2),
					("W-2501", "4 BHK", 25, 1620, 3),
				),
			},
			{
				"name": "Thane Greens Phase 2",
				"developer": 1,
				"rera": "P51800031004",
				"locality": "Thane West",
				"city": "Thane",
				"status": "Under construction",
				"rate": 16500,
				"units": (
					("TG-0701", "1 BHK", 7, 410, 1),
					("TG-0802", "2 BHK", 8, 640, 1),
					("TG-0903", "2 BHK", 9, 655, 1),
					("TG-1004", "3 BHK", 10, 860, 2),
				),
			},
		),
		"properties": (
			{
				"title": "2 BHK resale, Linking Road, Bandra West",
				"property_type": "Apartment",
				"city": "Mumbai",
				"locality": "Bandra West",
				"configuration": "2 BHK",
				"carpet_area": 780,
				"floor": 7,
				"parking": 1,
				"asking_price": 29500000,
			},
			{
				"title": "1 BHK resale, Sector 17, Vashi",
				"property_type": "Apartment",
				"city": "Navi Mumbai",
				"locality": "Vashi",
				"configuration": "1 BHK",
				"carpet_area": 430,
				"floor": 4,
				"parking": 0,
				"asking_price": 9800000,
			},
		),
		# The unit held for a lead, and the unit blocked by the company.
		"hold": {"project": 1, "unit": "PL-1201", "lead": 0},
		"block": {"project": 2, "unit": "W-2501", "reason": "Developer reserved it for a launch partner"},
		"partner": {
			"firm": "Kothari & Rao Property Consultants",
			"person": "Chitra Kothari",
			"pan": "AAKFK4521M",
			"rera": "A51800034567",
		},
		"other_firms": (
			("Sai Shakti Estate Agents", "invited", "contact@saishakti"),
			("Bandra Bay Realty Partners", "pending", "contact@bandrabay"),
		),
		# Buyers the partner registers: name, project of interest, note, what the Company Admin does.
		"registrations": (
			("Mrunal Joshi", "Powai Lakeview Heights", "Wants a 3 BHK, budget 2.4 crore", "approve"),
			("Gaurav Sethi", "Meridian Skyline Residences", "Investor, asks for a payment plan", "wait"),
			("Pankaj Dalal", "Thane Greens Phase 2", "Is not looking now", "reject"),
		),
		# Deals: lead index, project index and unit (or property index), price, days ago, the partner's share
		# of the commission split, what happens to the partner payout (due, approved, paid, none), and
		# whether the split is approved.
		"deals": (
			{
				"lead": 8,
				"project": 2,
				"unit": "W-2301",
				"price": 69500000,
				"days": 21,
				"partner": 40,
				"payout": "paid",
				"approved": True,
			},
			{
				"lead": 7,
				"project": 1,
				"unit": "PL-1202",
				"price": 18500000,
				"days": 9,
				"partner": 25,
				"payout": "approved",
				"approved": True,
			},
			{
				"lead": 6,
				"project": 3,
				"unit": "TG-0903",
				"price": 11200000,
				"days": 4,
				"partner": 20,
				"payout": "due",
				"approved": True,
			},
			{
				"lead": 5,
				"property": 0,
				"price": 29500000,
				"days": 1,
				"partner": 0,
				"payout": "none",
				"approved": False,
			},
		),
		"sellers": (
			{
				"name": "Dr. Suresh Naik",
				"email": "suresh.naik@example.com",
				"city": "Mumbai",
				"property": {
					"title": "3 BHK, Hiranandani Gardens, Powai",
					"city": "Mumbai",
					"locality": "Powai",
					"configuration": "3 BHK",
					"carpet_area": 1150,
					"floor": 9,
					"parking": 2,
				},
				"stage": "Seller Valuation shared",
				"mandate": ("Exclusive", 6, 1.5, False),
			},
			{
				"name": "Meenal Kapadia",
				"email": "meenal.kapadia@example.com",
				"city": "Mumbai",
				"property": {
					"title": "2 BHK, Lokhandwala Complex, Andheri West",
					"city": "Mumbai",
					"locality": "Andheri West",
					"configuration": "2 BHK",
					"carpet_area": 720,
					"floor": 5,
					"parking": 1,
				},
				"stage": "Seller Qualified",
				"mandate": ("Open", 12, 2.0, True),
			},
		),
		"enquiries": (("Tanvi Parekh", None), ("Harsh Vora", "Website")),
		"visit_projects": ("Worli Sea Crest", "Thane Greens Phase 2", "Powai Lakeview Heights"),
		"whatsapp": {
			"template": "site_visit_reminder",
			"customers": (
				{
					"name": "Pooja Bhatt",
					"script": (
						("in", "Hi, Powai wale Lakeview Heights me 2 BHK available hai kya?"),
						(
							"out",
							"Namaste Pooja ji! Haan, 2 BHK 650 sq ft carpet ready to move hai. Main brochure bhej deti hoon.",
						),
						("in", "Haan please bhejiye. Budget around 1.8 crore hai."),
						(
							"out",
							"Brochure aur price sheet bhej di hai. Kya aap Saturday site visit pe aana chahenge?",
						),
						("in", "Saturday 11 baje theek hai"),
					),
				},
				{
					"name": "Amit Trivedi",
					"script": (
						("in", "START"),
						("in", "Mujhe Thane me 3 BHK chahiye, possession next year tak. Kya options hain?"),
						("out", "Thane Greens Phase 2 me 3 BHK, 860 sq ft, 2028 possession. Details bhejun?"),
					),
				},
				{
					"name": "Deepak Menon",
					"script": (
						("in", "Booking amount kitna hoga? Aur loan ke liye kisi bank se tie-up hai?"),
						(
							"handoff",
							"Customer asks about booking amount and home loan tie-ups, please call him.",
						),
					),
				},
				{
					"name": "Sneha Pillai",
					"script": (
						("in", "Hi, Worli Sea Crest ka brochure bhejo please"),
						("out", "Sure Sneha ji, brochure attach kar rahi hoon."),
						("in", "STOP"),
					),
				},
				{
					"name": "Rahul Desai",
					"script": (
						("in", "Kal ka site visit thoda late kar sakte hain? 5 baje ke baad free hoon"),
						("template", ("Rahul", "5.30 pm tomorrow")),
					),
				},
			),
		},
	},
	"greenfield": {
		"developers": (
			("Orchid Landmarks Pvt Ltd", "Anil Dhumal", "sales@orchidlandmarks.example.com"),
			("Sahyadri Habitat Builders", "Rekha Phadke", "sales@sahyadrihabitat.example.com"),
		),
		"projects": (
			{
				"name": "Baner Orchid Heights",
				"developer": 0,
				"rera": "P52100041001",
				"locality": "Baner",
				"city": "Pune",
				"status": "Under construction",
				"possession": "2028-03-31",
				"rate": 11800,
				"tower": ("Tower B", 8, ((801, 804), (901, 904), (1001, 1004)), 690, "2 BHK"),
				"three_bhk": ("804", "904", "1004"),
				"amenities": ("Swimming pool", "Gym", "Clubhouse", "Jogging track"),
			},
			{
				"name": "Kharadi Riverside Residences",
				"developer": 0,
				"rera": "P52100041002",
				"locality": "Kharadi",
				"city": "Pune",
				"status": "Ready to move",
				"rate": 10900,
				"units": (
					("KR-0603", "2 BHK", 6, 680, 1),
					("KR-0704", "2 BHK", 7, 695, 1),
					("KR-0905", "3 BHK", 9, 940, 2),
				),
			},
			{
				"name": "Hinjewadi Greenview",
				"developer": 1,
				"rera": "P52100041003",
				"locality": "Hinjewadi Phase 2",
				"city": "Pune",
				"status": "Under construction",
				"rate": 8400,
				"units": (
					("HG-0402", "1 BHK", 4, 440, 1),
					("HG-0503", "2 BHK", 5, 620, 1),
					("HG-0604", "2 BHK", 6, 635, 1),
				),
			},
			{
				"name": "Wakad Lotus Park",
				"developer": 1,
				"rera": "P52100041004",
				"locality": "Wakad",
				"city": "Pune",
				"status": "Under construction",
				"rate": 9800,
				"units": (
					("WL-0301", "2 BHK", 3, 660, 1),
					("WL-0402", "3 BHK", 4, 880, 2),
				),
			},
		),
		"properties": (
			{
				"title": "2 BHK resale, Aundh Road, Aundh",
				"property_type": "Apartment",
				"city": "Pune",
				"locality": "Aundh",
				"configuration": "2 BHK",
				"carpet_area": 760,
				"floor": 6,
				"parking": 1,
				"asking_price": 11800000,
			},
			{
				"title": "3 BHK resale, Kothrud",
				"property_type": "Apartment",
				"city": "Pune",
				"locality": "Kothrud",
				"configuration": "3 BHK",
				"carpet_area": 1020,
				"floor": 3,
				"parking": 1,
				"asking_price": 17500000,
			},
		),
		"hold": {"project": 1, "unit": "KR-0704", "lead": 0},
		"block": {"project": 0, "unit": "1004", "reason": "Reserved by the developer for a corporate buyer"},
		"partner": {
			"firm": "Deccan Property Advisors",
			"person": "Chitra Deshmukh",
			"pan": "AAKFD7788P",
			"rera": "A52100034567",
		},
		"other_firms": (
			("Shivneri Estate Consultants", "invited", "contact@shivneri"),
			("Kothrud Key Realty", "pending", "contact@kothrudkey"),
		),
		"registrations": (
			("Mandar Kulkarni", "Kharadi Riverside Residences", "Wants a 3 BHK, budget 1.4 crore", "approve"),
			("Isha Bapat", "Baner Orchid Heights", "Investor, asks for a payment plan", "wait"),
			("Vinay Ranade", "Wakad Lotus Park", "Is not looking now", "reject"),
		),
		"deals": (
			{
				"lead": 8,
				"project": 1,
				"unit": "KR-0905",
				"price": 10600000,
				"days": 21,
				"partner": 40,
				"payout": "paid",
				"approved": True,
			},
			{
				"lead": 7,
				"project": 0,
				"unit": "801",
				"price": 8400000,
				"days": 9,
				"partner": 25,
				"payout": "approved",
				"approved": True,
			},
			{
				"lead": 6,
				"project": 2,
				"unit": "HG-0604",
				"price": 5500000,
				"days": 4,
				"partner": 20,
				"payout": "due",
				"approved": True,
			},
			{
				"lead": 5,
				"property": 0,
				"price": 11800000,
				"days": 1,
				"partner": 0,
				"payout": "none",
				"approved": False,
			},
		),
		"sellers": (
			{
				"name": "Prakash Gokhale",
				"email": "prakash.gokhale@example.com",
				"city": "Pune",
				"property": {
					"title": "3 BHK, Pashan-Sus Road, Pashan",
					"city": "Pune",
					"locality": "Pashan",
					"configuration": "3 BHK",
					"carpet_area": 1080,
					"floor": 8,
					"parking": 2,
				},
				"stage": "Seller Valuation shared",
				"mandate": ("Exclusive", 6, 1.5, False),
			},
			{
				"name": "Sunanda Apte",
				"email": "sunanda.apte@example.com",
				"city": "Pune",
				"property": {
					"title": "2 BHK, Model Colony, Shivajinagar",
					"city": "Pune",
					"locality": "Shivajinagar",
					"configuration": "2 BHK",
					"carpet_area": 700,
					"floor": 2,
					"parking": 1,
				},
				"stage": "Seller Qualified",
				"mandate": ("Open", 12, 2.0, True),
			},
		),
		"enquiries": (("Janhavi Sathe", None), ("Omkar Phadnis", "Website")),
		"visit_projects": ("Kharadi Riverside Residences", "Baner Orchid Heights", "Hinjewadi Greenview"),
		"whatsapp": {
			"template": "site_visit_reminder",
			"customers": (
				{
					"name": "Aarti Kale",
					"script": (
						("in", "Namaskar, Baner madhe 2 BHK available aahe ka?"),
						(
							"out",
							"Namaskar Aarti tai! Ho, Baner Orchid Heights madhe 2 BHK, 690 sq ft carpet aahe. Brochure pathvte.",
						),
						("in", "Ho pathva. Budget 90 lakh paryant aahe."),
						(
							"out",
							"Brochure ani price sheet pathavli aahe. Shanivari site visit sathi yeu shakta ka?",
						),
						("in", "Shanivari 11 vajta chalel"),
					),
				},
				{
					"name": "Nilesh Sawant",
					"script": (
						("in", "START"),
						("in", "Hinjewadi madhe 2 BHK pahije, IT park javal. Options kay aahet?"),
						(
							"out",
							"Hinjewadi Greenview madhe 2 BHK, 620 sq ft, possession 2027. Details pathvu ka?",
						),
					),
				},
				{
					"name": "Vaishali Mane",
					"script": (
						("in", "Booking amount kiti lagel? Home loan sathi bank tie-up aahe ka?"),
						(
							"handoff",
							"Customer asks about booking amount and home loan tie-ups, please call her.",
						),
					),
				},
				{
					"name": "Sachin Jadhav",
					"script": (
						("in", "Kharadi cha brochure pathva please"),
						("out", "Nakki Sachin sir, brochure attach karto."),
						("in", "STOP"),
					),
				},
				{
					"name": "Rutuja Bhide",
					"script": (
						("in", "Udyacha site visit thoda late karta yeil ka? 5 nantar free aahe"),
						("template", ("Rutuja", "5.30 pm tomorrow")),
					),
				},
			),
		},
	},
}

# Seeds for sellos.tests.phones.in_mobile, one range per kind, so no number is used twice on a site.
PHONE_SEEDS = {
	"partner": 8200,  # firms and registrations: 8200 to 8219
	"enquiry": 8230,
	"seller": 8240,
	"whatsapp": 8260,  # 8260 to 8279
}

# Words that mark a record as a test fixture. None of them may appear in the demo's own content.
FORBIDDEN_WORDS = ("regression", "gate ", "test ", "lorem")
