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

base_branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo 'main')

cleanup() {
	local exit_code=$?
	if ((exit_code != 0)); then
		log "${red}Error occurred. Cleaning up...${nc}"
		if [[ $(git branch --show-current) != "$base_branch" ]]; then
			log "Returning to ${green}$base_branch${nc}..."
			git checkout -f "$base_branch"
		fi
	fi
}
trap cleanup EXIT

git fetch origin "$base_branch" 2>/dev/null

unpushed=$(git log "origin/$base_branch..HEAD" --oneline)
if [[ -z "$unpushed" ]]; then
	log "${green}No unpushed commits. Nothing to do.${nc}"
	exit 0
fi

branch_name="logseq-updates-$(date +%Y%m%d)"
log "Moving unpushed commits to ${yellow}$branch_name${nc}..."

git checkout -b "$branch_name" || exit 1
git branch -f "$base_branch" "origin/$base_branch" || exit 1

log "Pushing ${yellow}$branch_name${nc}..."
git push -u origin "$branch_name" || exit 1

log 'Creating Pull Request...'
gh pr create --fill || exit 1

log "Switching back to ${green}$base_branch${nc}..."
git checkout "$base_branch" || exit 1

log "${green}Done!${nc}"
