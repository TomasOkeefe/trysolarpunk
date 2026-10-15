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
(YuE2 songs, LTX-2.5 clips, lyric captions, ffmpeg edit; TikTok's own AI label via the upload toggle), and videos land in `videos/` (gitignored).

- GPU: RunPod, prepaid credit. Before renting, `ge/runpod.py` checks live price and stock of every card that
  can run the batch (community and secure) and rents the cheapest estimated batch cost; measured
  seconds per clip go to `pipeline/gpu_speeds.json` after each run. Key in `~/.runpod/config.toml` (`flash login`).
  The pod reads the Hugging Face token from the RunPod secret `hf_token`.
  A launchd job (`~/Library/LaunchAgents/com.trysolarpunk.gpu-stock.plist`) logs RunPod stock every
  30 min to `pipeline/availability.jsonl`; `python3 -m ge.availability --summary` shows the best hours.
  Modal is the planned next provider once the RunPod credit is used (account exists, not set up).
- The pod clones github.com/TomasOkeefe/trysolarpunk, so push pipeline code before rendering.
- `worker/gen_clips.py` relies on private hooks of LTX-2 commit `be6d6d0` (pinned in `job.sh`).
- TikTok posting is manual for now (owner posts from the phone app; Jomo blocks TikTok in Chrome).
  Automatic drafts via the Content Posting API are a later step.

## Store notes
Fourthwall is still "Coming soon" with all 6 products hidden; it needs a ship-from address and
payout info before publishing. The tote has a thin margin at $24 (consider $28); stickers are $6.
CAD, STLs and `videos/` are gitignored.
