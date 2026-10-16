# Try Solarpunk

AI-made TikTok channel (@trysolarpunk, the owner's existing account: keep its logo and bio)
selling 3D-printed anti-phone gear, made in NYC, via a Fourthwall store ("trysolarpunk").
Products: the Hibernator (moss green fridge brick for your phone, magnets + NFC), the Eyelid
(iPhone sleeve that covers the screen), anti-algorithm merch.

## Working with the owner
- Keep replies short. Never use em dashes.
- Claude runs things; the owner only does what needs a human (accounts, passwords, API keys,
  browser logins). Never ask for or handle keys; the owner adds secrets.
- Spend as close to $0 as possible. Don't babysit GPUs or drive browsers to wait on things:
  run long jobs in the background and act on the completion notice.
- Work from code and logs, not screenshots.

## Pipeline (`pipeline/`)
To make videos, use the `make-videos` skill. In short: Claude writes plans in
`pipeline/plans/`, `python3 run.py plans/...` renders a whole batch in one RunPod GPU session
(YuE2 songs, LTX-2.5 clips, lyric captions, ffmpeg edit; TikTok's own AI label set when posting), and videos land in `videos/` (gitignored).

- GPU: RunPod, prepaid credit. Before renting, `ge/runpod.py` checks live price and stock of every card that
  can run the batch (community and secure) and rents the cheapest estimated batch cost; measured
  seconds per clip go to `pipeline/gpu_speeds.json` after each run. Key in `~/.runpod/config.toml` (`flash login`).
  The pod reads the Hugging Face token from the RunPod secret `hf_token`.
  A launchd job (`~/Library/LaunchAgents/com.trysolarpunk.gpu-stock.plist`) logs RunPod stock every
  30 min to `pipeline/availability.jsonl`; `python3 -m ge.availability --summary` shows the best hours.
  Modal is the planned next provider once the RunPod credit is used (account exists, not set up).
- The pod clones github.com/TomasOkeefe/trysolarpunk, so push pipeline code before rendering.
- Moss, the recurring character: `{moss}` in a prompt expands to his description plus the trigger
  `m0ss`, and the batch loads his LoRA (`config.yaml` loras, weights on the `moss-lora` GitHub release).
  Retrain with `train_lora.py` (dataset in `videos/lora/moss-data`, ~$1.30 on a community PRO 6000).
- `worker/gen_clips.py` relies on private hooks of LTX-2 commit `be6d6d0` (pinned in `job.sh`).
- TikTok posting is automatic and the owner never opens TikTok (it's the habit they're quitting).
  `run.py` hands each video to `ge/buffer.py`: upload to the public R2 bucket `trysolarpunk-media`,
  then a Buffer post (free plan, `buffer` CLI, logged in via `buffer init`) on the plan's date with
  TikTok's AI label. `python3 -m ge.buffer status` shows posts and deletes sent videos from R2.
  Free-tier guards in `ge/buffer.py` (R2 has no spending cap): max 40 files / 1 GB in the bucket,
  Standard class only, 30-day expiry rule; Buffer's free queue holds 10 posts. Our own TikTok
  developer app can't work: TikTok's audit rejects tools that post only to your own account.
- Comments and DMs: no API can read or answer them yet (Buffer replies to TikTok comments only in
  its web app; DMs have no API). `python3 -m ge.buffer report` shows views and comment counts. The
  launchd job `com.trysolarpunk.daily` (10:00, log `/tmp/trysolarpunk-daily.log`) runs
  `ge/daily.py`: cleans R2, notifies once when Buffer's changelog adds comment/DM endpoints (then
  build replies), and sends a weekly stats notification on Mondays (weekly on purpose).

## Waitlist site (`site/`)
Live at https://trysolarpunk.pages.dev (Cloudflare Pages + D1 `trysolarpunk-waitlist`, free tier).
Pages: `/`, `/hibernator`, `/eyelid`, `/merch`. TikTok captions can't hold links, so the bio link
is the way in: set it to `/?v=<tag>` (e.g. a week's batch) and `?v=` follows visitors to the product
pages; with no `v` the referring site (e.g. `tiktok-com`) is saved. `site/list.sh` shows the numbers,
`--csv` dumps emails (never commit it). Deploy with `cd site && npm run deploy`; check with
`npm test` and `test/smoke.sh <url>`, then delete its rows: `npx wrangler d1 execute
trysolarpunk-waitlist --remote --command "DELETE FROM signups WHERE email LIKE 'smoke+%@example.com'"`.
`POST /api/join` and the `signups` table stay as they are for the phase 2 animated site
(spec: `docs/superpowers/specs/2026-10-15-waitlist-site-design.md`).

## Store notes
Fourthwall is still "Coming soon" with all 6 products hidden; it needs a ship-from address and
payout info before publishing. The tote has a thin margin at $24 (consider $28); stickers are $6.
CAD, STLs and `videos/` are gitignored.
