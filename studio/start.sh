#!/usr/bin/env bash
# Open Claude Code with the Studio wired in, then the page in the browser.
# -c continues the last conversation in this folder; pass --new for a fresh one.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d studio/node_modules ] || (cd studio && npm install --silent)
(sleep 6 && open http://localhost:8790) &
args=(--dangerously-load-development-channels server:studio)
if [ "${1:-}" = "--new" ]; then exec claude "${args[@]}"; else exec claude -c "${args[@]}"; fi
