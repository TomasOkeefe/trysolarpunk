# Waitlist Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A four-page waitlist site at trysolarpunk.pages.dev that stores signups per product in Cloudflare D1.

**Architecture:** Static HTML/CSS plus one small JS file in `site/public/`, served by Cloudflare Pages. One Pages Function (`site/functions/api/join.js`) validates signups with a pure module (`site/lib/signup.js`) and writes to a D1 table. `site/list.sh` reads the numbers back.

**Tech Stack:** Cloudflare Pages + Pages Functions + D1, wrangler 4.151.0, Node 22 (`node --test`, no other deps), bash + curl for smoke tests, cwebp for images.

**Spec:** `docs/superpowers/specs/2026-10-15-waitlist-site-design.md`

## Global Constraints

- $0: Cloudflare free tier, address `trysolarpunk.pages.dev`.
- Mobile first (TikTok in-app browser). Every page works at 375 px wide.
- Each page under 200 KB (HTML + CSS + JS + its images; Google Fonts not counted).
- Fonts: Fraunces (headings) and Space Mono (body, labels), from Google Fonts.
- Palette: moss `#2F5D3A`, sprout `#9BC53D`, sun `#F2C14E`, cream `#F6F1E4`, clay `#D9764A`, ink `#2A2420`.
- Copy voice: warm, a little unhinged, never preachy, never shames phone use. No em dashes anywhere.
- Products: exactly `hibernator`, `eyelid`, `merch`.
- `POST /api/join` and the `signups` table are a contract phase 2 keeps. Don't change their shape.
- The repo is public: never commit signup data or CSV exports.
- Run all wrangler commands from `site/` via `npx wrangler` (resolves to the pinned local copy).

## Review Focus

1. Same person, different casing or spaces (`" Me@X.com "` vs `me@x.com`): one row, quiet success. Test in Task 1 and Task 2 smoke.
2. Double tap on "Join" in a slow in-app browser: button disabled while pending, and a repeat insert is a quiet 200. Covered by the `join.js` disable logic (Task 3) and the duplicate smoke check (Task 2).
3. Junk bodies (broken JSON, empty body, JSON `null`, an array): 400, never 500. Tests in Task 1 (array) and Task 2 smoke (broken JSON, empty, null).
4. Weird `?v=` values (uppercase, spaces, emoji, 500 chars): cleaned and stored, never rejected. Test in Task 1.
5. No connection when submitting: one-line error, email stays in the box, button re-enabled. Manual check in Task 3 step 6.

---

### Task 1: Signup validation module

**Files:**
- Create: `site/package.json`
- Create: `site/lib/signup.js`
- Create: `site/test/signup.test.js`
- Modify: `.gitignore`

**Interfaces:**
- Produces:
  - `PRODUCTS: string[]` = `['hibernator', 'eyelid', 'merch']`
  - `cleanSource(raw: unknown): string` lowercase `[a-z0-9-]`, max 64, no leading/trailing `-`
  - `pickSource(raw: unknown, referer: string | null, ownHost: string): string`
  - `parseSignup(fields: object, referer: string | null, ownHost: string)` returns one of
    `{ ok: true, bot: true, product: string | null }`,
    `{ ok: true, email: string, product: string, source: string }`,
    `{ ok: false, status: 400, error: string, product: string | null }`

- [ ] **Step 1: Branch, package.json, gitignore**

```bash
cd /Users/tomasokeefe/Developer/try-solarpunk && git switch -c waitlist-site
```

`site/package.json`:

```json
{
  "name": "trysolarpunk-site",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "node --test test/",
    "dev": "wrangler pages dev",
    "deploy": "wrangler pages deploy --branch main"
  },
  "devDependencies": {
    "wrangler": "4.151.0"
  }
}
```

Append to `.gitignore`:

```
site/node_modules/
site/.wrangler/
```

Run: `cd site && npm install`
Expected: installs wrangler, creates `package-lock.json`.

- [ ] **Step 2: Write the failing tests**

`site/test/signup.test.js`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PRODUCTS, cleanSource, pickSource, parseSignup } from '../lib/signup.js';

const HOST = 'trysolarpunk.pages.dev';

test('products are fixed', () => {
  assert.deepEqual(PRODUCTS, ['hibernator', 'eyelid', 'merch']);
});

test('good signup is normalized', () => {
  assert.deepEqual(
    parseSignup({ email: '  Me@Example.COM ', product: 'eyelid', source: 'phone-nap' }, null, HOST),
    { ok: true, email: 'me@example.com', product: 'eyelid', source: 'phone-nap' },
  );
});

test('honeypot is a silent success', () => {
  assert.deepEqual(
    parseSignup({ email: 'bot@x.com', product: 'merch', website: 'spam.biz' }, null, HOST),
    { ok: true, bot: true, product: 'merch' },
  );
  assert.deepEqual(
    parseSignup({ product: 'toaster', website: 'x' }, null, HOST),
    { ok: true, bot: true, product: null },
  );
});

test('unknown or missing product is a 400', () => {
  for (const product of ['toaster', '', undefined, 'Hibernator']) {
    const r = parseSignup({ email: 'a@b.co', product }, null, HOST);
    assert.equal(r.ok, false);
    assert.equal(r.status, 400);
    assert.equal(r.product, null);
  }
});

test('bad emails are a 400 that remembers the product', () => {
  const long = 'a'.repeat(250) + '@b.co';
  for (const email of ['', 'nope', 'a@b', '@b.co', 'a b@c.co', long, undefined]) {
    const r = parseSignup({ email, product: 'hibernator' }, null, HOST);
    assert.equal(r.ok, false, `accepted ${email}`);
    assert.equal(r.status, 400);
    assert.equal(r.product, 'hibernator');
  }
});

test('array or empty fields are a 400', () => {
  assert.equal(parseSignup([], null, HOST).status, 400);
  assert.equal(parseSignup({}, null, HOST).status, 400);
});

test('cleanSource cleans instead of rejecting', () => {
  assert.equal(cleanSource('Phone Nap!!'), 'phone-nap');
  assert.equal(cleanSource('  --x--  '), 'x');
  assert.equal(cleanSource('🐻 bear'), 'bear');
  assert.equal(cleanSource(null), '');
  assert.equal(cleanSource(undefined), '');
  const long = cleanSource('ab-'.repeat(200));
  assert.ok(long.length <= 64);
  assert.match(long, /^[a-z0-9][a-z0-9-]*[a-z0-9]$/);
});

test('pickSource prefers the explicit value', () => {
  assert.equal(pickSource('Video-1', `https://${HOST}/eyelid?v=other`, HOST), 'video-1');
});

test('pickSource falls back to ?v= on our own referer', () => {
  assert.equal(pickSource('', `https://${HOST}/eyelid?v=Phone-Nap`, HOST), 'phone-nap');
  assert.equal(pickSource('', `https://${HOST}/eyelid`, HOST), '');
});

test('pickSource uses a foreign referer host', () => {
  assert.equal(pickSource('', 'https://www.tiktok.com/@trysolarpunk', HOST), 'tiktok-com');
});

test('pickSource survives junk referers', () => {
  assert.equal(pickSource('', 'not a url', HOST), '');
  assert.equal(pickSource('', null, HOST), '');
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd site && npm test`
Expected: FAIL, `Cannot find module '.../site/lib/signup.js'`.

- [ ] **Step 4: Write the implementation**

`site/lib/signup.js`:

```js
// Validation for POST /api/join, kept free of Cloudflare APIs so node --test can run it.
export const PRODUCTS = ['hibernator', 'eyelid', 'merch'];

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Which video (or site) a signup came from: lowercase letters, digits and dashes, max 64.
export function cleanSource(raw) {
  return String(raw ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64)
    .replace(/-+$/, '');
}

// Explicit source, else ?v= from our own page, else the referring site's host.
export function pickSource(raw, referer, ownHost) {
  const direct = cleanSource(raw);
  if (direct) return direct;
  let ref;
  try {
    ref = new URL(referer);
  } catch {
    return '';
  }
  if (ref.host === ownHost) return cleanSource(ref.searchParams.get('v'));
  return cleanSource(ref.host.replace(/^www\./, ''));
}

export function parseSignup(fields, referer, ownHost) {
  const product = PRODUCTS.includes(fields?.product) ? fields.product : null;
  if (fields?.website) return { ok: true, bot: true, product };
  if (!product) return { ok: false, status: 400, error: 'Unknown product.', product };
  const email = String(fields.email ?? '').trim().toLowerCase();
  if (email.length > 254 || !EMAIL.test(email)) {
    return { ok: false, status: 400, error: "That email doesn't look right.", product };
  }
  return { ok: true, email, product, source: pickSource(fields.source, referer, ownHost) };
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd site && npm test`
Expected: all 11 tests pass.

- [ ] **Step 6: Commit**

```bash
git add .gitignore site/package.json site/package-lock.json site/lib/signup.js site/test/signup.test.js
git commit -m "Waitlist: signup validation module and tests"
```

---

### Task 2: Join endpoint, D1 schema, local smoke test

**Files:**
- Create: `site/wrangler.jsonc`
- Create: `site/schema.sql`
- Create: `site/functions/api/join.js`
- Create: `site/test/smoke.sh`
- Create: `site/public/index.html` (one-line stub so `pages dev` has a build dir; Task 3 replaces it)

**Interfaces:**
- Consumes: `parseSignup(fields, referer, ownHost)` from `site/lib/signup.js` (Task 1).
- Produces:
  - `POST /api/join`, body JSON or form-encoded with `email`, `product`, `source`, `website`.
    - JSON request: `200 {"ok":true}` or `4xx/5xx {"ok":false,"error":"<message>"}`.
    - Form request: `303` to `/<product>?joined=1#joined` on success, `/<product>?error=1#join-error` on failure (`/` instead of `/<product>` if the product is unknown).
  - D1 binding `DB`, database `trysolarpunk-waitlist`, table `signups`.
  - `test/smoke.sh <base-url>`: exits 0 when all checks pass. Uses emails `smoke+...@example.com`.

- [ ] **Step 1: Create the D1 database and config**

Run: `cd site && npx wrangler d1 create trysolarpunk-waitlist`
Expected: prints a `database_id` UUID. Copy it into the config below.

`site/wrangler.jsonc`:

```jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "trysolarpunk",
  "pages_build_output_dir": "./public",
  "compatibility_date": "2026-10-01",
  "d1_databases": [
    {
      "binding": "DB",
      "database_name": "trysolarpunk-waitlist",
      "database_id": "<uuid printed by d1 create>"
    }
  ]
}
```

`site/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS signups (
  email TEXT NOT NULL,
  product TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (email, product)
);
```

`site/public/index.html`:

```html
<!doctype html><title>Try Solarpunk</title>
```

Run: `cd site && npx wrangler d1 execute trysolarpunk-waitlist --local --file schema.sql`
Expected: success, 1 command executed.

- [ ] **Step 2: Write the smoke test**

`site/test/smoke.sh` (then `chmod +x site/test/smoke.sh`):

```bash
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

check "good signup"        200 "$(post_json "{\"email\":\"smoke+$TS@example.com\",\"product\":\"hibernator\",\"source\":\"smoke\"}")"
check "duplicate is quiet" 200 "$(post_json "{\"email\":\" SMOKE+$TS@Example.com \",\"product\":\"hibernator\"}")"
check "bad email"          400 "$(post_json '{"email":"nope","product":"eyelid"}')"
check "bad product"        400 "$(post_json "{\"email\":\"smoke+$TS@example.com\",\"product\":\"toaster\"}")"
check "honeypot"           200 "$(post_json "{\"email\":\"smoke+bot$TS@example.com\",\"product\":\"eyelid\",\"website\":\"x\"}")"
check "broken json"        400 "$(post_json '{"email":')"
check "json null"          400 "$(post_json 'null')"
check "empty body"         400 "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/join")"
check "form post redirects" "303 $BASE/merch?joined=1#joined" \
  "$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -X POST "$BASE/api/join" \
      --data-urlencode "email=smoke+form$TS@example.com" -d product=merch)"
check "form error redirects" "303 $BASE/merch?error=1#join-error" \
  "$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -X POST "$BASE/api/join" \
      -d email=nope -d product=merch)"

echo "stamp $TS"
exit $fail
```

- [ ] **Step 3: Run it to verify it fails**

Run in the background: `cd site && npx wrangler pages dev --port 8788` (leave running for this task).
Run: `site/test/smoke.sh http://localhost:8788`
Expected: FAIL lines (no `/api/join` yet, POSTs get 405/404).

- [ ] **Step 4: Write the function**

`site/functions/api/join.js`:

```js
import { parseSignup } from '../../lib/signup.js';

const BROKEN = 'Something broke on our end. Try again in a minute.';

export async function onRequestPost({ request, env }) {
  const url = new URL(request.url);
  const isJson = (request.headers.get('content-type') || '').includes('application/json');

  let fields = null;
  try {
    fields = isJson ? await request.json() : Object.fromEntries(await request.formData());
  } catch {
    fields = null;
  }

  let result =
    fields && typeof fields === 'object'
      ? parseSignup(fields, request.headers.get('referer'), url.host)
      : { ok: false, status: 400, error: 'Bad request.', product: null };

  if (result.ok && !result.bot) {
    try {
      await env.DB.prepare('INSERT OR IGNORE INTO signups (email, product, source) VALUES (?, ?, ?)')
        .bind(result.email, result.product, result.source)
        .run();
    } catch (err) {
      console.error('join: insert failed', err);
      result = { ok: false, status: 500, error: BROKEN, product: result.product };
    }
  }

  if (isJson) {
    return Response.json(result.ok ? { ok: true } : { ok: false, error: result.error }, {
      status: result.ok ? 200 : result.status,
    });
  }
  const page = result.product ? `/${result.product}` : '/';
  const target = result.ok ? `${page}?joined=1#joined` : `${page}?error=1#join-error`;
  return new Response(null, { status: 303, headers: { Location: target } });
}
```

- [ ] **Step 5: Run the smoke test to verify it passes**

`pages dev` reloads on change. Run: `site/test/smoke.sh http://localhost:8788`
Expected: every line `ok`, exit 0, prints `stamp <TS>`.

Run: `cd site && npx wrangler d1 execute trysolarpunk-waitlist --local --command "SELECT * FROM signups"`
Expected: exactly 2 rows for that stamp: `smoke+<TS>@example.com | hibernator | smoke` and `smoke+form<TS>@example.com | merch | ''`. No `bot` row, no uppercase.

Run: `cd site && npm test`
Expected: still passes.

- [ ] **Step 6: Clean local test rows and commit**

Run: `cd site && npx wrangler d1 execute trysolarpunk-waitlist --local --command "DELETE FROM signups WHERE email LIKE 'smoke+%@example.com'"`

```bash
git add site/wrangler.jsonc site/schema.sql site/functions/api/join.js site/test/smoke.sh site/public/index.html
git commit -m "Waitlist: POST /api/join on Pages Functions + D1, smoke test"
```

---

### Task 3: Pages, styles and form script

**Files:**
- Create: `site/public/style.css`
- Create: `site/public/join.js`
- Create: `site/public/img/` (hibernator.jpg, eyelid.jpg, merch.webp, emblem.svg)
- Create: `site/public/hibernator.html`, `site/public/eyelid.html`, `site/public/merch.html`
- Modify: `site/public/index.html` (replace the stub)
- Create: `site/test/weight.sh`

**Interfaces:**
- Consumes: `POST /api/join` contract from Task 2 (JSON `{ok, error}`; form redirects to `#joined` / `#join-error`).
- Produces: pages at `/`, `/hibernator`, `/eyelid`, `/merch` (Pages serves `x.html` at `/x`). Each product form is `form.join[action="/api/join"]` with inputs `email`, `product` (hidden), `source` (hidden), `website` (honeypot).

- [ ] **Step 1: Images**

```bash
cd /Users/tomasokeefe/Developer/try-solarpunk
mkdir -p site/public/img
cp store-photos/hibernator/1_hib_fridge.jpg site/public/img/hibernator.jpg
cp store-photos/eyelid/1_eyelid_studio.jpg site/public/img/eyelid.jpg
cwebp -q 80 -resize 800 0 merch/print_stroll.png -o site/public/img/merch.webp
# emblem without the embedded C2PA metadata block
sed '/<metadata>/,/<\/metadata>/d' brand/emblem.svg > site/public/img/emblem.svg
ls -l site/public/img
```

Expected: hibernator.jpg and eyelid.jpg about 20 KB, merch.webp under 120 KB, emblem.svg a few KB. If `metadata` sat on the `<svg>` line and sed removed the root tag, open the file and fix by hand so it starts with `<svg ...>`.

- [ ] **Step 2: Write the weight check (failing)**

`site/test/weight.sh` (then `chmod +x`):

```bash
#!/usr/bin/env bash
# Each page plus the files it loads must stay under 200 KB.
set -uo pipefail
cd "$(dirname "$0")/../public"
fail=0
for page in index hibernator eyelid merch; do
  [[ -f "$page.html" ]] || { echo "FAIL $page.html missing"; fail=1; continue; }
  files=("$page.html" style.css join.js img/emblem.svg)
  while read -r src; do files+=("$src"); done < <(grep -oE 'src="/img/[^"]+"' "$page.html" | sed -E 's|src="/||; s|"$||')
  bytes=$(cat "${files[@]}" | wc -c | tr -d ' ')
  if (( bytes < 200000 )); then echo "ok   $page $bytes bytes"; else echo "FAIL $page $bytes bytes"; fail=1; fi
done
exit $fail
```

Run: `site/test/weight.sh`
Expected: FAIL (pages and style.css missing).

- [ ] **Step 3: Styles and script**

`site/public/style.css`:

```css
:root {
  --moss: #2F5D3A;
  --sprout: #9BC53D;
  --sun: #F2C14E;
  --cream: #F6F1E4;
  --clay: #D9764A;
  --ink: #2A2420;
  color-scheme: light;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--cream);
  color: var(--ink);
  font: 16px/1.55 "Space Mono", ui-monospace, monospace;
  -webkit-text-size-adjust: 100%;
}
main { max-width: 34rem; margin: 0 auto; padding: 1.25rem 1rem 3rem; }
a { color: var(--moss); }
h1, h2 { font-family: "Fraunces", Georgia, serif; font-weight: 700; line-height: 1.05; margin: 0 0 .75rem; }
h1 { font-size: clamp(2.3rem, 11vw, 3.4rem); letter-spacing: -.02em; }
h2 { font-size: 1.6rem; }
.top { display: flex; align-items: center; gap: .6rem; text-decoration: none; color: var(--ink); font-weight: 700; }
.top img { width: 2.6rem; height: 2.6rem; }
.lede { font-size: 1.05rem; margin: 0 0 1.5rem; }
.tag { display: inline-block; background: var(--sun); border: 2px solid var(--ink); border-radius: 99px; padding: .1rem .7rem; font-size: .8rem; margin: 1.5rem 0 .75rem; }
.photo { width: 100%; height: auto; aspect-ratio: 3 / 4; object-fit: cover; border: 3px solid var(--ink); border-radius: 1.25rem; display: block; margin: 0 0 1.25rem; background: #fff; }
.photo.art { aspect-ratio: auto; object-fit: contain; padding: 1rem; }

.cards { display: grid; gap: 1rem; padding: 0; list-style: none; margin: 1.5rem 0; }
.cards a { display: grid; grid-template-columns: 6rem 1fr; gap: 1rem; align-items: center; text-decoration: none; color: var(--ink); background: #fff; border: 3px solid var(--ink); border-radius: 1.25rem; padding: .75rem; box-shadow: 4px 4px 0 var(--ink); transition: transform .15s, box-shadow .15s; }
.cards a:hover, .cards a:focus-visible { transform: translate(-2px, -2px); box-shadow: 6px 6px 0 var(--ink); }
.cards img { width: 6rem; height: 6rem; object-fit: cover; border-radius: .75rem; }
.cards h2 { font-size: 1.35rem; margin: 0 0 .2rem; }
.cards p { margin: 0; font-size: .85rem; }

.join { background: var(--moss); color: var(--cream); border: 3px solid var(--ink); border-radius: 1.25rem; padding: 1.25rem; margin: 1.5rem 0; }
.join label { display: block; font-weight: 700; margin-bottom: .5rem; }
.join input[type=email] { width: 100%; font: inherit; font-size: 1rem; padding: .85rem 1rem; border: 3px solid var(--ink); border-radius: .85rem; background: var(--cream); color: var(--ink); }
.join button { width: 100%; margin-top: .75rem; font: inherit; font-weight: 700; font-size: 1.05rem; padding: .85rem 1rem; border: 3px solid var(--ink); border-radius: .85rem; background: var(--sun); color: var(--ink); cursor: pointer; }
.join button:disabled { opacity: .6; cursor: wait; }
.join .fine { font-size: .75rem; margin: .75rem 0 0; opacity: .85; }
.join .hp { position: absolute; left: -9999px; width: 1px; height: 1px; overflow: hidden; }
.join-msg { min-height: 1.2em; margin: .5rem 0 0; color: var(--sun); font-size: .85rem; }
.thanks, #join-error { display: none; }
.thanks h2 { color: var(--sun); }
.join.done .fields, .join:has(#joined:target) .fields { display: none; }
.join.done .thanks, #joined:target { display: block; }
#join-error:target { display: block; color: var(--sun); font-size: .85rem; margin: 0 0 .5rem; }

footer { font-size: .8rem; margin-top: 2.5rem; }
footer a { color: var(--ink); }
```

`site/public/join.js`:

```js
// Submits waitlist forms in place. Without JS the form posts normally and the server redirects.
for (const form of document.querySelectorAll('form.join')) {
  const msg = form.querySelector('.join-msg');
  const button = form.querySelector('button');
  form.elements.source.value = new URLSearchParams(location.search).get('v') || '';

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    button.disabled = true;
    msg.textContent = '';
    try {
      const res = await fetch(form.action, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        form.classList.add('done');
        return;
      }
      msg.textContent = data.error || 'Something broke on our end. Try again in a minute.';
    } catch {
      msg.textContent = 'No connection. Try again?';
    }
    button.disabled = false;
  });
}
```

- [ ] **Step 4: Pages**

`site/public/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Try Solarpunk</title>
  <meta name="description" content="Gear for recovering scrollers. 3D-printed in NYC. Join the waitlist.">
  <meta property="og:title" content="Try Solarpunk">
  <meta property="og:description" content="Gear for recovering scrollers. 3D-printed in NYC.">
  <meta property="og:image" content="/img/hibernator.jpg">
  <link rel="icon" href="/img/emblem.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,700&family=Space+Mono:wght@400;700&display=swap">
  <link rel="stylesheet" href="/style.css">
</head>
<body>
<main>
  <a class="top" href="/"><img src="/img/emblem.svg" alt="">Try Solarpunk</a>
  <span class="tag">Coming soon</span>
  <h1>Gear for recovering scrollers.</h1>
  <p class="lede">Little 3D-printed things, made in NYC, that help your phone take a nap. Pick one and we'll email you once, when it's ready.</p>
  <ul class="cards">
    <li><a href="/hibernator"><img src="/img/hibernator.jpg" alt="The Hibernator on a fridge door"><div><h2>The Hibernator</h2><p>A fridge brick your phone sleeps in.</p></div></a></li>
    <li><a href="/eyelid"><img src="/img/eyelid.jpg" alt="The Eyelid phone sleeve"><div><h2>The Eyelid</h2><p>A sleeve that closes your screen's eyes.</p></div></a></li>
    <li><a href="/merch"><img src="/img/merch.webp" alt="Infinite Stroll tee art"><div><h2>Merch</h2><p>Anti-algorithm tees, totes and stickers.</p></div></a></li>
  </ul>
  <footer>Made by humans and AI. Find us on TikTok: <a href="https://www.tiktok.com/@trysolarpunk">@trysolarpunk</a></footer>
</main>
</body>
</html>
```

`site/public/hibernator.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>The Hibernator · Try Solarpunk</title>
  <meta name="description" content="A moss green fridge brick your phone sleeps in. Join the waitlist.">
  <meta property="og:title" content="The Hibernator">
  <meta property="og:description" content="A fridge brick your phone sleeps in. Join the waitlist.">
  <meta property="og:image" content="/img/hibernator.jpg">
  <link rel="icon" href="/img/emblem.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,700&family=Space+Mono:wght@400;700&display=swap">
  <link rel="stylesheet" href="/style.css">
</head>
<body>
<main>
  <a class="top" href="/"><img src="/img/emblem.svg" alt="">Try Solarpunk</a>
  <span class="tag">Waitlist open</span>
  <h1>The Hibernator</h1>
  <p class="lede">A moss green brick that sticks to your fridge. Your phone goes in face to the wall. Tap the eye and Focus mode turns on. Goodnight, feed.</p>
  <img class="photo" src="/img/hibernator.jpg" alt="The Hibernator holding a phone on a fridge door" width="720" height="960">
  <form class="join" action="/api/join" method="post">
    <div class="fields">
      <p id="join-error">That didn't work. Check the email and try again.</p>
      <label for="email">Get one when they're printed</label>
      <input id="email" name="email" type="email" autocomplete="email" inputmode="email" placeholder="you@example.com" required>
      <input type="hidden" name="product" value="hibernator">
      <input type="hidden" name="source" value="">
      <div class="hp" aria-hidden="true"><label>Website <input name="website" tabindex="-1" autocomplete="off"></label></div>
      <button type="submit">Join the waitlist</button>
      <p class="join-msg" role="status"></p>
      <p class="fine">One email when it ships. No spam, no feed.</p>
    </div>
    <div class="thanks" id="joined">
      <h2>You're on the list.</h2>
      <p>Your phone has been notified. It's nervous.</p>
    </div>
  </form>
  <footer><a href="/">See everything</a> · <a href="https://www.tiktok.com/@trysolarpunk">@trysolarpunk</a></footer>
</main>
<script src="/join.js" defer></script>
</body>
</html>
```

`site/public/eyelid.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>The Eyelid · Try Solarpunk</title>
  <meta name="description" content="A sleeve that covers your whole screen. Join the waitlist.">
  <meta property="og:title" content="The Eyelid">
  <meta property="og:description" content="A sleeve that closes your screen's eyes. Join the waitlist.">
  <meta property="og:image" content="/img/eyelid.jpg">
  <link rel="icon" href="/img/emblem.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,700&family=Space+Mono:wght@400;700&display=swap">
  <link rel="stylesheet" href="/style.css">
</head>
<body>
<main>
  <a class="top" href="/"><img src="/img/emblem.svg" alt="">Try Solarpunk</a>
  <span class="tag">Waitlist open</span>
  <h1>The Eyelid</h1>
  <p class="lede">A terracotta sleeve that covers your whole screen, so notifications can't catch your eye. Your phone, eyes closed.</p>
  <img class="photo" src="/img/eyelid.jpg" alt="The Eyelid sleeve with a closed-eye emblem" width="720" height="960">
  <form class="join" action="/api/join" method="post">
    <div class="fields">
      <p id="join-error">That didn't work. Check the email and try again.</p>
      <label for="email">Get one when they're printed</label>
      <input id="email" name="email" type="email" autocomplete="email" inputmode="email" placeholder="you@example.com" required>
      <input type="hidden" name="product" value="eyelid">
      <input type="hidden" name="source" value="">
      <div class="hp" aria-hidden="true"><label>Website <input name="website" tabindex="-1" autocomplete="off"></label></div>
      <button type="submit">Join the waitlist</button>
      <p class="join-msg" role="status"></p>
      <p class="fine">One email when it ships. No spam, no feed.</p>
    </div>
    <div class="thanks" id="joined">
      <h2>You're on the list.</h2>
      <p>Your notifications are already sweating.</p>
    </div>
  </form>
  <footer><a href="/">See everything</a> · <a href="https://www.tiktok.com/@trysolarpunk">@trysolarpunk</a></footer>
</main>
<script src="/join.js" defer></script>
</body>
</html>
```

`site/public/merch.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Merch · Try Solarpunk</title>
  <meta name="description" content="Anti-algorithm tees, totes and stickers. Join the waitlist.">
  <meta property="og:title" content="Try Solarpunk merch">
  <meta property="og:description" content="No feed. No ads. No end. Join the waitlist.">
  <meta property="og:image" content="/img/merch.webp">
  <link rel="icon" href="/img/emblem.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,700&family=Space+Mono:wght@400;700&display=swap">
  <link rel="stylesheet" href="/style.css">
</head>
<body>
<main>
  <a class="top" href="/"><img src="/img/emblem.svg" alt="">Try Solarpunk</a>
  <span class="tag">Waitlist open</span>
  <h1>Anti-algorithm merch</h1>
  <p class="lede">The Infinite Stroll tee. No feed. No ads. No end. Plus totes and stickers for your laptop, which you will also put down sometimes.</p>
  <img class="photo art" src="/img/merch.webp" alt="Infinite Stroll art: rolling hills and a looping path" width="800" height="862">
  <form class="join" action="/api/join" method="post">
    <div class="fields">
      <p id="join-error">That didn't work. Check the email and try again.</p>
      <label for="email">Tell me when the merch drops</label>
      <input id="email" name="email" type="email" autocomplete="email" inputmode="email" placeholder="you@example.com" required>
      <input type="hidden" name="product" value="merch">
      <input type="hidden" name="source" value="">
      <div class="hp" aria-hidden="true"><label>Website <input name="website" tabindex="-1" autocomplete="off"></label></div>
      <button type="submit">Join the waitlist</button>
      <p class="join-msg" role="status"></p>
      <p class="fine">One email when it drops. No spam, no feed.</p>
    </div>
    <div class="thanks" id="joined">
      <h2>You're on the list.</h2>
      <p>The algorithm will never know.</p>
    </div>
  </form>
  <footer><a href="/">See everything</a> · <a href="https://www.tiktok.com/@trysolarpunk">@trysolarpunk</a></footer>
</main>
<script src="/join.js" defer></script>
</body>
</html>
```

Check `merch.webp`'s real size with `sips -g pixelWidth -g pixelHeight site/public/img/merch.webp` and set the `width`/`height` attributes on its `<img>` to match.

- [ ] **Step 5: Run the weight check to verify it passes**

Run: `site/test/weight.sh`
Expected: four `ok` lines, every page under 200000 bytes.

Run: `grep -rn "—" site/public && echo "FAIL em dash" || echo "ok no em dashes"`
Expected: `ok no em dashes`.

- [ ] **Step 6: Check it in a browser**

With `npx wrangler pages dev --port 8788` running in `site/`, use chrome-devtools MCP (`new_page`, `emulate`/`resize_page` to 375x812, `take_snapshot`, `take_screenshot`) on `/`, `/hibernator?v=test-video`, `/eyelid`, `/merch`:
- Nothing overflows horizontally at 375 px; the email box and button are full width; photos keep 3:4.
- On `/hibernator?v=test-video` submit `review+1@example.com`: button disables, then "You're on the list." replaces the form. The row in local D1 has `source = test-video`.
- Submit the same email again after reload: success again, still one row.
- No connection: stop `pages dev`, submit on `/eyelid`: "No connection. Try again?" appears, the email stays in the box, the button works again. Restart `pages dev`.
- No JS: disable JS (devtools `emulate` with JS off, or curl the form as in smoke.sh) and confirm `/merch?joined=1#joined` shows the thanks block and `/merch?error=1#join-error` shows the error line above the form.

Then: `cd site && npx wrangler d1 execute trysolarpunk-waitlist --local --command "DELETE FROM signups WHERE email LIKE 'review+%@example.com'"`

- [ ] **Step 7: Commit**

```bash
git add site/public site/test/weight.sh
git commit -m "Waitlist: home and product pages, form script, brand styles"
```

---

### Task 4: Reading the list

**Files:**
- Create: `site/list.sh`

**Interfaces:**
- Consumes: D1 `trysolarpunk-waitlist`, table `signups`.
- Produces: `site/list.sh [--local] [--csv]`. Default prints totals; `--csv` prints `email,product,source,created_at` rows to stdout; `--local` reads the local dev database instead of the live one.

- [ ] **Step 1: Write the script**

`site/list.sh` (then `chmod +x`):

```bash
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
```

- [ ] **Step 2: Test it against local data**

```bash
cd site
npx wrangler d1 execute trysolarpunk-waitlist --local --command "INSERT INTO signups (email, product, source) VALUES ('list+1@example.com','hibernator','phone-nap'),('list+1@example.com','eyelid',''),('list+2@example.com','hibernator','phone-nap')"
./list.sh --local
./list.sh --local --csv
```

Expected: `people 2, signups 3`; hibernator 2, eyelid 1; `hibernator phone-nap 2`, `eyelid (direct) 1`; CSV has a header and 3 rows. If `--json` output carries extra lines that break `json.load`, adjust `q` to keep only the JSON (verify with `npx wrangler d1 execute ... --json --command "SELECT 1"`).

Run: `./list.sh --bogus; echo $?`
Expected: usage line, `2`.

Then: `npx wrangler d1 execute trysolarpunk-waitlist --local --command "DELETE FROM signups WHERE email LIKE 'list+%@example.com'"`

- [ ] **Step 3: Commit**

```bash
git add site/list.sh
git commit -m "Waitlist: list.sh prints totals per product and video, --csv for launch"
```

---

### Task 5: Deploy and document

**Files:**
- Modify: `CLAUDE.md` (new "Waitlist site" section)
- Modify: `README.md` (folder table row)

**Interfaces:**
- Consumes: everything above.
- Produces: live site at `https://trysolarpunk.pages.dev` (or the address Cloudflare assigns if that name is taken; use it everywhere below and in the docs).

- [ ] **Step 1: Create the Pages project and the live table**

```bash
cd site
npx wrangler pages project create trysolarpunk --production-branch main
npx wrangler d1 execute trysolarpunk-waitlist --remote --file schema.sql
```

Expected: project created with a `*.pages.dev` address; schema applied remotely.

- [ ] **Step 2: Deploy**

Run: `cd site && npm run deploy`
Expected: upload of `public/` plus the compiled function, a deployment URL, and the production alias `https://trysolarpunk.pages.dev`.

- [ ] **Step 3: Smoke test live**

Run: `site/test/smoke.sh https://trysolarpunk.pages.dev`
Expected: every line `ok`.

Run: `curl -s -o /dev/null -w '%{http_code}\n' https://trysolarpunk.pages.dev/hibernator` for each of `/`, `/hibernator`, `/eyelid`, `/merch`, `/img/emblem.svg`
Expected: `200` each.

Run: `site/list.sh`
Expected: shows the smoke rows (proves the live binding works).

Then: `cd site && npx wrangler d1 execute trysolarpunk-waitlist --remote --command "DELETE FROM signups WHERE email LIKE 'smoke+%@example.com'"` and `site/list.sh` again shows `people 0`.

- [ ] **Step 4: Phone check**

chrome-devtools MCP at 375x812 on the live `/hibernator?v=live-check`: layout as in Task 3, submit `review+live@example.com`, see the thanks block, `site/list.sh` shows it with source `live-check`, then delete it with the same `DELETE ... LIKE 'review+%@example.com'` using `--remote`.

- [ ] **Step 5: Docs**

Add to `CLAUDE.md` after the Pipeline section:

```markdown
## Waitlist site (`site/`)
Live at https://trysolarpunk.pages.dev (Cloudflare Pages + D1 `trysolarpunk-waitlist`, free tier).
Pages: `/`, `/hibernator`, `/eyelid`, `/merch`. Link a video as `/hibernator?v=<plan-slug>` to see
which video drove signups. `site/list.sh` shows the numbers, `--csv` dumps emails (never commit it).
Deploy with `cd site && npm run deploy`; check with `npm test` and `test/smoke.sh <url>`.
`POST /api/join` and the `signups` table stay as they are for the phase 2 animated site
(spec: `docs/superpowers/specs/2026-10-15-waitlist-site-design.md`).
```

Add to the `README.md` folder table:

```markdown
| `site/` | The waitlist site (Cloudflare Pages + D1). See `CLAUDE.md` |
```

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "Waitlist site live on Cloudflare Pages; notes in CLAUDE.md"
```
