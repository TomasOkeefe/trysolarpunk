#!/usr/bin/env bash
# What a phone downloads before the page is usable: HTML, CSS, the main script and the two
# preloaded fonts. Product images load lazily and the 3D meadow loads after first paint, so they
# don't count. Run after a build: test/weight.sh
set -uo pipefail
cd "$(dirname "$0")/../dist" || { echo "FAIL no dist/, run npm run build"; exit 1; }
BUDGET=420000
fail=0
for page in index.html shop.html hibernator.html about.html; do
  [[ -f "$page" ]] || { echo "FAIL $page missing"; fail=1; continue; }
  css=$(grep -oE 'href="/assets/[^"]+\.css"' "$page" | sed -E 's/href="\///; s/"$//')
  js=$(grep -oE 'src="/assets/[^"]+\.js"' "$page" | sed -E 's/src="\///; s/"$//')
  # static imports of the entry (chunks it pulls in before running)
  chunks=$(grep -oE 'from"\./c-[A-Z0-9]+\.js"' "$js" | sed -E 's/from"\.\///; s/"$//' | sort -u | sed 's|^|assets/|')
  files=("$page" $css $js $chunks fonts/fraunces.woff2 fonts/dmsans.woff2)
  bytes=0
  for f in "${files[@]}"; do bytes=$((bytes + $(gzip -c "$f" | wc -c))); done
  if (( bytes < BUDGET )); then echo "ok   $page $((bytes / 1000)) kB gzipped"; else echo "FAIL $page $((bytes / 1000)) kB gzipped (budget $((BUDGET / 1000)))"; fail=1; fi
done
three=$(ls assets/c-*.js | xargs grep -l "WebGLRenderer" | head -1)
[[ -n "$three" ]] && echo "     meadow chunk $(( $(gzip -c "$three" | wc -c) / 1000 )) kB gzipped, loaded after first paint"
exit $fail
