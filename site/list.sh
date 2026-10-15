#!/usr/bin/env bash
# Waitlist numbers from D1. --csv dumps every signup (don't commit it, the repo is public).
# --local reads the wrangler pages dev database instead of the live one.
set -euo pipefail
cd "$(dirname "$0")"
where=--remote csv=0
for arg in "$@"; do
  case "$arg" in
    --local) where=--local ;;
    --csv) csv=1 ;;
    *) echo "usage: list.sh [--local] [--csv]" >&2; exit 2 ;;
  esac
done

q() { npx wrangler d1 execute trysolarpunk-waitlist "$where" --json --command "$1" 2>/dev/null; }
table() { python3 -c '
import json, sys
rows = json.load(sys.stdin)[0]["results"]
if not rows: print("  (none)"); sys.exit()
cols = list(rows[0])
w = [max(len(c), *(len(str(r[c])) for r in rows)) for c in cols]
print("  " + "  ".join(c.ljust(n) for c, n in zip(cols, w)))
for r in rows: print("  " + "  ".join(str(r[c]).ljust(n) for c, n in zip(cols, w)))
'; }

if (( csv )); then
  q "SELECT email, product, source, created_at FROM signups ORDER BY created_at" | python3 -c '
import csv, json, sys
w = csv.writer(sys.stdout)
w.writerow(["email", "product", "source", "created_at"])
for r in json.load(sys.stdin)[0]["results"]:
    w.writerow([r["email"], r["product"], r["source"], r["created_at"]])
'
  exit
fi

echo "Unique emails:"; q "SELECT COUNT(DISTINCT email) AS people, COUNT(*) AS signups FROM signups" | table
echo "By product:";    q "SELECT product, COUNT(*) AS n FROM signups GROUP BY product ORDER BY n DESC" | table
echo "By video:";      q "SELECT product, CASE source WHEN '' THEN '(direct)' ELSE source END AS source, COUNT(*) AS n FROM signups GROUP BY product, source ORDER BY n DESC" | table
