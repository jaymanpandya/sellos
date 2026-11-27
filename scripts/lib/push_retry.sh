# SOS-LOOP (27 November 2026): the loop's push survives a rejected (non fast forward) push.
# Interactive sessions push TASKS.md and docs commits to 1.0 while the loop works, so a rejection is
# normal, not a stop. On a rejection: git pull --rebase --autostash origin <branch>, then push again,
# up to three attempts. Only a real rebase conflict stops: the rebase is aborted so the repository is
# clean, the conflicted files are named in PUSH_ERROR, and the caller notifies. Never a force push.
# Needs BRANCH. On failure PUSH_ERROR holds git's output (or the conflict message).
PUSH_ERROR=""
PUSH_CONFLICT_FILES=""
PUSH_REBASE_ATTEMPTS="${SELLOS_PUSH_REBASE_ATTEMPTS:-3}"

# Rebase the branch onto origin. Returns 0 on success; 1 on a conflict (aborted, files named) or other failure.
rebase_onto_remote() {
	local out files
	PUSH_CONFLICT_FILES=""
	if out="$(git pull --rebase --autostash origin "$BRANCH" 2>&1)"; then
		printf '%s\n' "$out"
		return 0
	fi
	printf '%s\n' "$out"
	files="$(git diff --name-only --diff-filter=U 2>/dev/null || true)"
	git rebase --abort >/dev/null 2>&1 || true
	PUSH_CONFLICT_FILES="$files"
	PUSH_ERROR="The rebase onto origin/$BRANCH hit a conflict and was aborted; the repository is clean. Conflicted files: ${files:-unknown}. $out"
	return 1
}

# Push the branch. A failed try is retried after 10, 30 and 90 seconds. GitHub's own
# "fatal error in commit_refs" is a server fault, retried like a network error. A rejected push is
# fixed by rebase_onto_remote and pushed again (PUSH_REBASE_ATTEMPTS times). Nothing here ever resets
# a commit or forces a push.
push_with_retry() {
	local waits=(${SELLOS_PUSH_WAITS:-10 30 90}) attempt=0 rebases=0 out
	PUSH_ERROR=""
	while true; do
		if out="$(git push origin "$BRANCH" 2>&1)"; then
			printf '%s\n' "$out"
			return 0
		fi
		printf '%s\n' "$out"
		PUSH_ERROR="$out"
		if printf '%s\n' "$out" | grep -q "fatal error in commit_refs"; then
			echo "The push failed with \"fatal error in commit_refs\". That is an error on GitHub's side, not a rejected push. Retrying."
		elif printf '%s\n' "$out" | grep -q -E "\[rejected\]|\[remote rejected\]|non-fast-forward|fetch first"; then
			if [[ $rebases -ge $PUSH_REBASE_ATTEMPTS ]]; then
				echo "The remote still rejected the push after $rebases rebase attempts."
				return 1
			fi
			rebases=$((rebases + 1))
			echo "The remote rejected the push (another session pushed to $BRANCH). Rebase attempt $rebases of $PUSH_REBASE_ATTEMPTS."
			rebase_onto_remote || return 1
			continue
		fi
		if [[ $attempt -ge ${#waits[@]} ]]; then return 1; fi
		echo "Push failed. Trying again in ${waits[$attempt]} seconds."
		sleep "${waits[$attempt]}"
		attempt=$((attempt + 1))
	done
}
