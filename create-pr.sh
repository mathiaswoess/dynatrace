#!/usr/bin/env bash

repo_dir=$(cd -- "${BASH_SOURCE[0]%/*}" && pwd) || exit 1
cd -- "$repo_dir" || exit 1

if [[ -t 1 ]]; then
	green='\033[0;32m'
	yellow='\033[0;33m'
	red='\033[0;31m'
	nc='\033[0m'
else
	green=''
	yellow=''
	red=''
	nc=''
fi

log() {
	printf '%b\n' "$1"
}

git fetch origin main 2>/dev/null

git add -A
if ! git diff --cached --quiet; then
	log "Committing staged changes..."
	git commit -m "chore: auto-commit $(date +%Y-%m-%d)" || exit 1
fi

if git diff --quiet origin/main..HEAD; then
	log "${green}No changes since origin/main. Nothing to do.${nc}"
	exit 0
fi

branch_name="updates-$(date +%Y%m%d)"
log "Creating branch ${yellow}$branch_name${nc}..."
git branch "$branch_name" || exit 1

log "Pushing ${yellow}$branch_name${nc}..."
git push -u origin "$branch_name" || exit 1

log 'Creating Pull Request...'
gh pr create --fill --head "$branch_name" || exit 1

git branch -d "$branch_name"

log "${green}Done!${nc}"
