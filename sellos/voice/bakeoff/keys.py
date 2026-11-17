"""The four bake-off keys, from the macOS Keychain only (SOS-N21A).

get_secret(name) is built like get_provisioner_password() in sellos.provisioning.credentials. It accepts
only the four names below. Store a key once with

    security add-generic-password -a "$USER" -s <name> -w

A key goes only into the request to its provider (transport.py). Nothing prints, logs or writes one, and
no exception message holds one. The Keychain is read by a helper in sellos.provisioning, the only
package that runs commands (SOS-P1-02).
"""

from sellos.provisioning import credentials

SARVAM = "sellos_sarvam_key"
DEEPGRAM = "sellos_deepgram_key"
ELEVENLABS = "sellos_elevenlabs_key"
ANTHROPIC = "sellos_anthropic_key"
ALLOWED_NAMES = (SARVAM, DEEPGRAM, ELEVENLABS, ANTHROPIC)


class UnknownSecretName(ValueError):
	"""A name outside the four bake-off keys was asked for."""


class SecretMissing(RuntimeError):
	"""A key could not be read. The message says how to store it and never holds a value."""


def store_command(name):
	return f'security add-generic-password -a "$USER" -s {name} -w'


def get_secret(name):
	"""The key stored under `name`. Raises UnknownSecretName or SecretMissing, with no value in either."""
	if name not in ALLOWED_NAMES:
		raise UnknownSecretName(f"{name!r} is not a bake-off key. The keys are: {', '.join(ALLOWED_NAMES)}.")
	value, failure = credentials.read_keychain_item(name)
	if value is None:
		raise SecretMissing(
			f"The Keychain item {name} could not be read ({failure}). Store it once with: {store_command(name)}"
		)
	return value


def missing_keys(names):
	"""The names among `names` that cannot be read. The values are dropped at once."""
	missing = []
	for name in names:
		try:
			get_secret(name)
		except SecretMissing:
			missing.append(name)
	return missing
