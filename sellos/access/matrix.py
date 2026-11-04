"""The permission matrix (P1.05): the roles that may call each whitelisted sellos method.

This list is written by hand, apart from the `@sellos_api` declarations, so a change to who may call
a method has to be made in two places and a reviewer sees both. `test_permission_matrix.py` calls
every method here as every role, as an outsider and as a guest, and fails the build when:

* a declared method is missing from this list,
* this list names a method that does not exist,
* the two lists disagree about the roles, or
* a sellos method is whitelisted with no declaration.

Add one line per method, in the same commit that adds the method.
"""

# dotted method path -> the roles that may call it. Empty for now: no sellos API method exists yet.
MATRIX: dict[str, frozenset[str]] = {}
