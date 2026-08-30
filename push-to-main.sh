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

git add -A

if git diff --cached --quiet; then
	log "${green}No changes. Nothing to commit.${nc}"
	exit 0
fi

log "Committing changes..."
git commit -m "chore: auto-commit $(date +%Y-%m-%d)" || exit 1

log "Pushing to ${yellow}origin main${nc}..."
git push origin main || exit 1

log "${green}Done!${nc}"
