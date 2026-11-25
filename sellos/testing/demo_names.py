"""Names for the demo companies: pure data, no Frappe import (unit tested without a bench).

Everyone here is made up. A person is a plain name ("Kavya Menon"), never a name with a source or a label on it.
The pools are by community, because a Mumbai book of leads holds Gujarati, Marathi, Parsi, Punjabi, Jain, South
Indian and NRI names, and an Ahmedabad book is mainly Gujarati. `person(rng, region)` draws one by the region's
weights. Phone numbers are never written here: demo builders take them from sellos.tests.phones.
"""

# (first names for women, first names for men, surnames)
COMMUNITIES = {
	"gujarati": (
		(
			"Hetal",
			"Nisha",
			"Pooja",
			"Krupa",
			"Dhara",
			"Jigna",
			"Bhumi",
			"Riddhi",
			"Mansi",
			"Foram",
			"Kinjal",
			"Heena",
		),
		(
			"Jignesh",
			"Hardik",
			"Nirav",
			"Chirag",
			"Jaydeep",
			"Kunal",
			"Parth",
			"Dhaval",
			"Mitesh",
			"Bhavin",
			"Hiren",
			"Smit",
		),
		(
			"Patel",
			"Shah",
			"Mehta",
			"Desai",
			"Trivedi",
			"Joshi",
			"Parikh",
			"Thakkar",
			"Vyas",
			"Modi",
			"Dave",
			"Bhatt",
		),
	),
	"marathi": (
		("Sneha", "Pradnya", "Rutuja", "Aarti", "Manasi", "Vaishali", "Gauri", "Shruti", "Pallavi", "Sayali"),
		("Sandeep", "Amit", "Rahul", "Nilesh", "Swapnil", "Omkar", "Sachin", "Pratik", "Yogesh", "Mangesh"),
		(
			"Kulkarni",
			"Deshpande",
			"Joshi",
			"Patil",
			"Jadhav",
			"Sawant",
			"Gokhale",
			"Phadke",
			"Kadam",
			"Pawar",
		),
	),
	"parsi": (
		("Dina", "Roshan", "Zarine", "Freny", "Perin", "Shernaz", "Navaz", "Khorshed"),
		("Cyrus", "Darius", "Farhad", "Jehangir", "Kersi", "Rustom", "Zubin", "Burjor"),
		("Irani", "Mistry", "Wadia", "Engineer", "Contractor", "Dastur", "Sethna", "Bharucha"),
	),
	"punjabi": (
		("Simran", "Harleen", "Gurleen", "Manpreet", "Navneet", "Kiran", "Ritu", "Jasleen"),
		("Harpreet", "Gurpreet", "Amarjit", "Tejinder", "Navdeep", "Rajiv", "Sukhdev", "Karan"),
		("Sethi", "Chadha", "Bhatia", "Kapoor", "Ahluwalia", "Malhotra", "Grewal", "Sandhu"),
	),
	"jain": (
		("Kavita", "Anjali", "Sheetal", "Payal", "Ritika", "Nidhi", "Preeti", "Rashmi"),
		("Rajesh", "Mukesh", "Pankaj", "Manish", "Vimal", "Nikhil", "Sanjay", "Ashok"),
		("Jain", "Doshi", "Gandhi", "Sanghvi", "Kothari", "Nahar", "Lodha", "Bafna"),
	),
	"south_indian": (
		("Kavya", "Lakshmi", "Divya", "Meera", "Revathi", "Anitha", "Deepa", "Sowmya"),
		("Karthik", "Ramesh", "Suresh", "Venkat", "Arvind", "Naveen", "Murali", "Srinivas"),
		("Menon", "Nair", "Iyer", "Iyengar", "Reddy", "Pillai", "Rao", "Krishnan"),
	),
	"nri": (
		("Anika", "Tara", "Neha", "Sonia", "Priya", "Isha", "Maya", "Zoya"),
		("Rohan", "Aditya", "Vikram", "Arjun", "Sameer", "Dev", "Ishaan", "Kabir"),
		("Mehra", "Kapoor", "Bansal", "Chopra", "Malik", "Khanna", "Sinha", "Varma"),
	),
}

# The weights of each community in a region's book (they need not add to 100).
REGIONS = {
	"bom": {
		"city": "Mumbai",
		"state": "Maharashtra",
		"weights": {
			"gujarati": 24,
			"marathi": 22,
			"parsi": 6,
			"punjabi": 12,
			"jain": 12,
			"south_indian": 12,
			"nri": 12,
		},
	},
	"amd": {
		"city": "Ahmedabad",
		"state": "Gujarat",
		"weights": {"gujarati": 80, "jain": 8, "marathi": 4, "punjabi": 4, "nri": 4},
	},
}

# Staff, partners and the client sign in: fixed names, so docs/DEMO.md can list them.
STAFF = {
	"bom": {
		"admin": "Meera Gandhi",
		"manager": "Farhad Irani",
		"agents": ("Asha Kulkarni", "Bilal Shaikh", "Nikhil Jain", "Simran Sethi"),
		"partner": "Chitra Kothari",
		"client": "Kunal Doshi",
	},
	"amd": {
		"admin": "Hetal Parikh",
		"manager": "Jignesh Trivedi",
		"agents": ("Nirav Patel", "Dhara Shah", "Chirag Desai", "Bhumi Thakkar"),
		"partner": "Mitesh Vyas",
		"client": "Riddhi Modi",
	},
}


def person(rng, region, gender=None, community=None):
	"""A made up person drawn by the region's weights: {name, first, last, gender, community}."""
	weights = REGIONS[region]["weights"]
	community = community or rng.choices(list(weights), weights=list(weights.values()))[0]
	women, men, surnames = COMMUNITIES[community]
	gender = gender or rng.choice(("F", "M"))
	first = rng.choice(women if gender == "F" else men)
	last = rng.choice(surnames)
	return {"name": f"{first} {last}", "first": first, "last": last, "gender": gender, "community": community}


def people(rng, region, count, used=None):
	"""`count` different people for a region. Pass the same `used` set to every call of a company and no name is
	drawn twice across its leads, sellers, partners and conversations."""
	used = set() if used is None else used
	found = []
	while len(found) < count:
		p = person(rng, region)
		if p["name"] not in used:
			used.add(p["name"])
			found.append(p)
	return found
