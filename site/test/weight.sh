#!/usr/bin/env bash
# Each page plus the files it loads must stay under 200 KB.
set -uo pipefail
cd "$(dirname "$0")/../public"
fail=0
for page in index hibernator eyelid merch; do
  [[ -f "$page.html" ]] || { echo "FAIL $page.html missing"; fail=1; continue; }
  files=("$page.html" style.css join.js img/emblem.svg)
  while read -r src; do files+=("$src"); done < <(grep -oE 'src="/img/[^"]+"' "$page.html" | sed -E 's|src="/||; s|"$||')
  missing=0
  for f in "${files[@]}"; do [[ -f "$f" ]] || { echo "FAIL $page needs missing $f"; missing=1; }; done
  (( missing )) && { fail=1; continue; }
  bytes=$(cat "${files[@]}" | wc -c | tr -d ' ')
  if (( bytes < 200000 )); then echo "ok   $page $bytes bytes"; else echo "FAIL $page $bytes bytes"; fail=1; fi
done
exit $fail
