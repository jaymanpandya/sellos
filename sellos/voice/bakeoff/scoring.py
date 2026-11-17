"""Word error rate and entity accuracy (SOS-N21A)."""

from sellos.voice.bakeoff.normalize import normalise

ENTITY_KINDS = ("numbers", "prices", "localities")


def edit_distance(reference, hypothesis):
	previous = list(range(len(hypothesis) + 1))
	for i, ref_word in enumerate(reference, start=1):
		current = [i]
		for j, hyp_word in enumerate(hypothesis, start=1):
			cost = 0 if ref_word == hyp_word else 1
			current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
		previous = current
	return previous[-1]


def word_error_rate(reference, hypothesis):
	"""Word edits over reference words, after normalising both sides. Empty reference: 0 or 1."""
	ref, hyp = normalise(reference), normalise(hypothesis)
	if not ref:
		return 0.0 if not hyp else 1.0
	return edit_distance(ref, hyp) / len(ref)


def _contains(tokens, wanted):
	n = len(wanted)
	return n > 0 and any(tokens[i : i + n] == wanted for i in range(len(tokens) - n + 1))


def entity_scores(entities, hypothesis):
	"""{kind: (found, total)} for numbers, prices and localities, each scored on its own.

	`entities` maps a kind to a list of entity strings. A number or a price is found when its figure is
	one of the hypothesis tokens ('3 crore' and 'teen crore' are both 30000000); a locality is found
	when its words appear in a row. A kind with no entity has total 0.
	"""
	tokens = normalise(hypothesis)
	scores = {}
	for kind in ENTITY_KINDS:
		wanted = [normalise(entity) for entity in entities.get(kind, ())]
		scores[kind] = (sum(1 for w in wanted if _contains(tokens, w)), len(wanted))
	return scores


def accuracy(found, total):
	"""found / total, or None when there was nothing to find."""
	return None if total == 0 else found / total
