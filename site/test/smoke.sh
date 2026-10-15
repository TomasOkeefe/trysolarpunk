#!/usr/bin/env bash
# End-to-end checks of POST /api/join against a running site.
# Usage: test/smoke.sh http://localhost:8788
set -uo pipefail
BASE="${1:?usage: test/smoke.sh <base-url>}"
TS=$(date +%s)
fail=0

check() { # name expected actual
  if [[ "$2" == "$3" ]]; then echo "ok   $1"; else echo "FAIL $1: expected '$2', got '$3'"; fail=1; fi
}
post_json() {
  curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/join" -H 'content-type: application/json' -d "$1"
}

# JSON bodies built up front: macOS bash 3.2 brace-expands {..,..} inside nested "$(...)".
good="{\"email\":\"smoke+$TS@example.com\",\"product\":\"hibernator\",\"source\":\"smoke\"}"
dupe="{\"email\":\" SMOKE+$TS@Example.com \",\"product\":\"hibernator\"}"
badproduct="{\"email\":\"smoke+$TS@example.com\",\"product\":\"toaster\"}"
bot="{\"email\":\"smoke+bot$TS@example.com\",\"product\":\"eyelid\",\"website\":\"x\"}"

check "good signup"        200 "$(post_json "$good")"
check "duplicate is quiet" 200 "$(post_json "$dupe")"
check "bad email"          400 "$(post_json '{"email":"nope","product":"eyelid"}')"
check "bad product"        400 "$(post_json "$badproduct")"
check "honeypot"           200 "$(post_json "$bot")"
check "broken json"        400 "$(post_json '{"email":')"
check "json null"          400 "$(post_json 'null')"
check "empty form body"    "303 $BASE/?error=1#join-error" \
  "$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -X POST "$BASE/api/join")"
check "form post redirects" "303 $BASE/merch?joined=1#joined" \
  "$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -X POST "$BASE/api/join" \
      --data-urlencode "email=smoke+form$TS@example.com" -d product=merch)"
check "form error redirects" "303 $BASE/merch?error=1#join-error" \
  "$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -X POST "$BASE/api/join" \
      -d email=nope -d product=merch)"

echo "stamp $TS"
exit $fail
