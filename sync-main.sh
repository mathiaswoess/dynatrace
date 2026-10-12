#!/usr/bin/env bash
# Rebase main onto origin/main once the pending PR is merged.
# Exit codes: 0 = synced or nothing pending, 2 = PR still open, 1 = error.

repo_dir=$(cd -- "${BASH_SOURCE[0]%/*}" && pwd) || exit 1
cd -- "$repo_dir" || exit 1

state=$(git rev-parse --git-path pending-pr) || exit 1
[[ -f $state ]] || exit 0
pr=$(<"$state")

info=$(gh pr view "$pr" --json state,headRefOid -q '[.state, .headRefOid] | join(" ")') || exit 1
read -r pr_state pr_head <<<"$info"

case $pr_state in
	OPEN)
		echo "PR $pr is still open." >&2
		exit 2
		;;
	CLOSED)
		echo "PR $pr was closed without merging, dropping it." >&2
		rm -f -- "$state"
		exit 0
		;;
	MERGED) ;;
	*)
		echo "Unexpected PR state: $pr_state" >&2
		exit 1
		;;
esac

if ! git merge-base --is-ancestor "$pr_head" main; then
	echo "$pr_head is not an ancestor of main, refusing to rebase." >&2
	exit 1
fi

git fetch origin main || exit 1
git rebase --onto origin/main "$pr_head" main || exit 1
rm -f -- "$state"
