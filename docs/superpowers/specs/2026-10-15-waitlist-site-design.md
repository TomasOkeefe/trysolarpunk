# Waitlist site: design

Date: 2026-10-15. Status: approved in chat, spec awaiting review.

## Goal

A waitlist site that TikTok viewers reach from the bio link or a video, sign up for a product in a
few seconds on their phone, and that leaves the owner with a list to email on launch day.
It stands in for the store while Fourthwall says "Coming soon".

Long-term goal: a showpiece animated site in the Awwwards style (scroll-driven motion, 3D,
the channel's AI clips). This spec is phase 1 only: ship a fast, plain version now, built so
phase 2 can replace the front end without touching the backend or the data.

## Constraints

- $0. Cloudflare free tier, free `trysolarpunk.pages.dev` address. A custom domain can be added later.
- The owner only runs `npx wrangler login` once. Claude builds, deploys and reads the list.
- Mobile first: almost all traffic comes from the TikTok in-app browser.
- Brand: Fraunces and Space Mono, colors and logo from `brand/`, photos from `store-photos/`.

## Pages

All in `site/public/`, plain HTML and CSS, one small shared JS file, no build step.

| URL | Content |
|---|---|
| `/` | Logo, "Gear for recovering scrollers", a card per product linking to its page, link to @trysolarpunk |
| `/hibernator` | Store photo, two-line pitch, email form for `hibernator` |
| `/eyelid` | Store photo, two-line pitch, email form for `eyelid` |
| `/merch` | Merch art, two-line pitch, email form for `merch` |

The form: one email field, a hidden honeypot field, a "Join the waitlist" button. On success it
swaps in place to "You're on the list". On error it shows a one-line message and keeps the email.
Works without JS too (normal form POST, the function redirects back with `?joined=1`).

Each page under 200 KB. Images resized and served as WebP/JPG from `site/public/img/`.

## Source tracking

A video links to `/hibernator?v=phone-nap`. The page sends `v` with the signup (falls back to
`document.referrer` host, else empty) so the owner can see which video drove signups.
`v` is capped at 64 chars, `[a-z0-9-]` only.

## Backend

One Pages Function, `site/functions/api/join.js`, `POST /api/join`.

Input (JSON or form-encoded): `email`, `product`, `source`, `website` (honeypot).

1. Honeypot filled: return 200 as if it worked, store nothing.
2. `product` not in `hibernator | eyelid | merch`: 400.
3. Email lowercased and trimmed, must match a simple `x@y.z` check and be under 254 chars: else 400.
4. `INSERT OR IGNORE` into D1, so repeats are a quiet success: 200.
5. D1 error: 500, logged.

D1 database `trysolarpunk-waitlist`, schema in `site/schema.sql`:

```sql
CREATE TABLE signups (
  email TEXT NOT NULL,
  product TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (email, product)
);
```

This endpoint and table are the contract phase 2 keeps.

No Turnstile for now. Add it if spam shows up in the list.

## Reading the list

`site/list.sh` (wrapping `wrangler d1 execute --remote`):
- default: signups per product, and per product per source, plus the total of unique emails
- `--csv`: all rows as CSV for launch day

## Testing

1. Local: `wrangler pages dev` with a local D1. Curl the function for: good signup, duplicate,
   bad email, bad product, honeypot. Check the rows. Submit the real form with and without JS.
2. Check every page at 375 px wide and on desktop.
3. Deploy, repeat the curl checks against `trysolarpunk.pages.dev`, delete the test rows.

## Out of scope (phase 1)

Sending the launch email, custom domain, analytics, Turnstile, the animated site.

## Phase 2 notes (not designed yet)

Own spec when we get there. Likely a Vite build with GSAP + Lenis (and maybe Three.js) for
scroll motion, reusing pipeline clips and product renders as hero media, deployed to the same
Pages project, posting to the same `/api/join`.
