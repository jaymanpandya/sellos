"""Marathi to English for registration text (SOS-P3-03).

`to_english(text)` keeps anything that is not Devanagari, translates the words and phrases in the glossary
below (document types, property words, well known places) and transliterates every other Devanagari word by
rule. The rule is simple on purpose: long and short vowels are written the same (a, i, u), the inherent vowel
at the end of a word is dropped (गणेश is Ganesh), and the ones inside a word are kept. An unknown name is
therefore a good first reading, not always the spelling people use, which is what the review list is for.
"""

from __future__ import annotations

import re

# Multi word phrases first, then single words. Keys are matched on whole words.
PHRASES = {
	"विक्री करारनामा": "Agreement for Sale",
	"विकसन करारनामा": "Development Agreement",
	"भाडे करारनामा": "Leave and Licence Agreement",
	"कुलमुखत्यारपत्र": "Power of Attorney",
	"पुणे शहर": "Pune City",
	"पिंपरी चिंचवड": "Pimpri Chinchwad",
	"सदनिका क्र": "Flat No",
	"सदनिका क्रमांक": "Flat No",
	"सर्वे नंबर": "Survey No",
}
WORDS = {
	# documents
	"खरेदीखत": "Sale Deed", "बक्षीसपत्र": "Gift Deed", "गहाणखत": "Mortgage Deed",
	"भाडेपट्टा": "Lease Deed", "करारनामा": "Agreement", "हस्तांतरण": "Transfer",
	"मुखत्यारपत्र": "Power of Attorney", "वाटणीपत्र": "Partition Deed",
	# property
	"सदनिका": "Flat", "दुकान": "Shop", "गाळा": "Commercial Unit", "कार्यालय": "Office",
	"बंगला": "Bungalow", "जमीन": "Land", "भूखंड": "Plot", "इमारत": "Building",
	"मजला": "Floor", "पार्किंग": "Parking", "अपार्टमेंट": "Apartment", "अपार्टमेंट्स": "Apartments",
	"रेसिडेन्सी": "Residency", "हाइट्स": "Heights", "टॉवर": "Tower", "प्लाझा": "Plaza",
	"सोसायटी": "Society", "गृहनिर्माण": "Housing", "संस्था": "Society", "नगर": "Nagar",
	"रस्ता": "Road", "रोड": "Road", "पेठ": "Peth", "गाव": "Village", "मौजे": "Mauje",
	"तालुका": "Taluka", "जिल्हा": "District", "क्र": "No", "क्रमांक": "No", "नंबर": "No",
	"मधील": "in", "येथील": "at",
	# offices and districts
	"सह": "Joint", "दुय्यम": "Sub", "निबंधक": "Registrar", "पुणे": "Pune", "मुंबई": "Mumbai", "ठाणे": "Thane", "नाशिक": "Nashik", "नागपूर": "Nagpur",
	"औरंगाबाद": "Aurangabad", "कोल्हापूर": "Kolhapur", "सातारा": "Satara", "सोलापूर": "Solapur",
	"रायगड": "Raigad", "पालघर": "Palghar", "अहमदनगर": "Ahmednagar",
	"हवेली": "Haveli", "मुळशी": "Mulshi", "मावळ": "Maval", "भोर": "Bhor", "शिरूर": "Shirur",
	# places in and around Pune and Mumbai
	"कोथरूड": "Kothrud", "हडपसर": "Hadapsar", "बाणेर": "Baner", "औंध": "Aundh", "वाकड": "Wakad",
	"हिंजवडी": "Hinjewadi", "विमाननगर": "Viman Nagar", "कल्याणीनगर": "Kalyani Nagar",
	"कोरेगाव": "Koregaon", "येरवडा": "Yerawada", "खराडी": "Kharadi", "वानवडी": "Wanowrie",
	"कात्रज": "Katraj", "धायरी": "Dhayari", "पिंपरी": "Pimpri", "चिंचवड": "Chinchwad",
	"भोसरी": "Bhosari", "सिंहगड": "Sinhagad", "शिवाजीनगर": "Shivajinagar", "सहकारनगर": "Sahakarnagar",
	"अंधेरी": "Andheri", "बोरिवली": "Borivali", "दादर": "Dadar", "वरळी": "Worli", "कुर्ला": "Kurla",
	"मुलुंड": "Mulund", "घाटकोपर": "Ghatkopar", "वांद्रे": "Bandra", "पवई": "Powai", "चेंबूर": "Chembur",
	"डोंबिवली": "Dombivli", "कल्याण": "Kalyan", "वसई": "Vasai", "विरार": "Virar",
	# letters used in building names
	"ए": "A", "बी": "B", "सी": "C", "डी": "D", "ई": "E",
}  # fmt: skip

_TOKEN = re.compile(r"[ऀ-ॿ]+|[^ऀ-ॿ]+")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

_CONSONANTS = {
	"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh",
	"ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d",
	"ध": "dh", "न": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r",
	"ल": "l", "ळ": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h",
}  # fmt: skip
_INDEPENDENT = {
	"अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ए": "e", "ऐ": "ai", "ओ": "o",
	"औ": "au", "ऑ": "o", "ऋ": "ru",
}  # fmt: skip
_MATRAS = {
	"ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
	"ॉ": "o", "ृ": "ru", "ॅ": "e",
}  # fmt: skip
_VIRAMA, _NUKTA = "्", "़"
_VISARGA = "\u0903"  # the sign after a vowel that reads as h
_LABIAL = set("पफबभम")


def transliterate(word: str) -> str:
	"""One Devanagari word as Latin letters, by rule."""
	word = word.replace("ज्ञ", "dny").replace(_NUKTA, "")
	out = []
	i = 0
	while i < len(word):
		ch = word[i]
		nxt = word[i + 1] if i + 1 < len(word) else ""
		if ch == "d" and word[i : i + 3] == "dny":
			out.append("dny")
			i += 3
			if i < len(word) and word[i] in _MATRAS:
				out.append(_MATRAS[word[i]])
				i += 1
			elif i < len(word) and word[i] == _VIRAMA:
				i += 1
			elif i < len(word):
				out.append("a")
		elif ch in _CONSONANTS:
			out.append(_CONSONANTS[ch])
			if nxt in _MATRAS:
				out.append(_MATRAS[nxt])
				i += 1
			elif nxt == _VIRAMA:
				i += 1
			elif i + 1 < len(word):  # the inherent vowel is dropped only at the end of the word
				out.append("a")
		elif ch in _INDEPENDENT:
			out.append(_INDEPENDENT[ch])
		elif ch in ("ं", "ँ"):
			out.append("m" if nxt and nxt in _LABIAL else "n")
		elif ch == _VISARGA:
			out.append("h")
		elif ch in _MATRAS:
			out.append(_MATRAS[ch])
		i += 1
	return "".join(out)


def _word(token: str) -> str:
	if token in WORDS:
		return WORDS[token]
	return transliterate(token).capitalize()


def to_english(text: str) -> str:
	"""English for `text`. Text with no Devanagari is returned as it is."""
	if not text or not _DEVANAGARI.search(text):
		return text
	for phrase, english in PHRASES.items():
		text = re.sub(rf"(?<![ऀ-ॿ]){re.escape(phrase)}(?![ऀ-ॿ])", english, text)
	parts = [_word(t) if _DEVANAGARI.match(t) else t for t in _TOKEN.findall(text)]
	return " ".join("".join(parts).split())
