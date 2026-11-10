"""The MariaDB provisioner account's password, from one place (SOS-SETUP-22).

Tenant sites are created and dropped with a narrow MariaDB account, never root. Its name is in
SELLOS_DB_PROVISIONER_USER (default sellos_provisioner). Its password comes from
get_provisioner_password(): the environment variable SELLOS_DB_PROVISIONER_PASSWORD when it is set,
otherwise, on macOS, the login Keychain item with the service name sellos_provisioner, stored once with

    security add-generic-password -a "$USER" -s sellos_provisioner -w

The value is never logged or printed, never put in an exception or a traceback, and never on a
visible command line. It reaches bench only through a child process's environment (child_env).
"""

import os
import shutil
import subprocess
import sys

PASSWORD_ENV = "SELLOS_DB_PROVISIONER_PASSWORD"
USER_ENV = "SELLOS_DB_PROVISIONER_USER"
DEFAULT_USER = "sellos_provisioner"
KEYCHAIN_SERVICE = "sellos_provisioner"
STORE_COMMAND = 'security add-generic-password -a "$USER" -s sellos_provisioner -w'


class ProvisionerPasswordMissing(RuntimeError):
	"""The provisioner password could not be found. The message never holds a secret."""


def provisioner_user():
	return os.environ.get(USER_ENV) or DEFAULT_USER


def get_provisioner_password():
	"""The provisioner password. Raises ProvisionerPasswordMissing, with no value in it, if it is not found."""
	value = os.environ.get(PASSWORD_ENV)
	if value:
		return value
	if sys.platform != "darwin":
		raise ProvisionerPasswordMissing(
			f"{PASSWORD_ENV} is not set, and the Keychain is only read on macOS. Set {PASSWORD_ENV} in the "
			"environment the loop is started in."
		)
	security = shutil.which("security")
	if not security:
		raise ProvisionerPasswordMissing(
			f"{PASSWORD_ENV} is not set and the macOS security command was not found."
		)
	failure = None
	try:
		result = subprocess.run(
			[security, "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
			stdin=subprocess.DEVNULL,
			capture_output=True,
			text=True,
			timeout=30,
			check=False,
		)
	except (OSError, subprocess.SubprocessError):
		# The exception may carry the command's output. Drop it and say only what failed.
		failure = "the security command could not be run"
		result = None
	if result is not None:
		value = result.stdout.rstrip("\n")
		if result.returncode == 0 and value:
			return value
		failure = f"the security command exited {result.returncode}"
	raise ProvisionerPasswordMissing(
		f"{PASSWORD_ENV} is not set and the Keychain item {KEYCHAIN_SERVICE} could not be read "
		f"({failure}). Store it once with: {STORE_COMMAND}"
	)


def child_env(password, base=None):
	"""A copy of the environment for a child process, with the password in it and nowhere else."""
	env = dict(os.environ if base is None else base)
	env[PASSWORD_ENV] = password
	env[USER_ENV] = provisioner_user()
	return env
