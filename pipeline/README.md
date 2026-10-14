# Try Solarpunk: daily TikTok pipeline

One video a day, fully generated, for about $30–40/month on RunPod (less once models are cached on a volume).

```
Claude writes the plan ──► rented GPU (RunPod) ──────────────────────────► TikTok
(song, 9 shots, caption)   YuE2 song → LTX-2.5 clips → beat-cut edit          draft in your inbox
                           (+ hook text, AI label, end card)                  (or direct post after audit)
```

| Step | Where | What |
|---|---|---|
| Plan | `ge/concept.py` | Claude API writes lyrics, style, 9 shot prompts, hook, caption. Rotates products, avoids repeats (`history.jsonl`). |
| Song | `worker/gen_song.py` | YuE2-3B, ~45 s, verse + chorus. Free to monetize per the YuE2 license. |
| Clips | `worker/gen_clips.py` | LTX-2.5 distilled, 768×1344, 5 s each. The product shot uses our render as its first frame so the product looks right. |
| Edit | `ge/assemble.py` | Cuts on the beat (librosa), hook sticker for 3 s, "AI-generated" label, end card, loudness to −14 LUFS, 1080×1920. |
| Post | `ge/tiktok.py` | Content Posting API. `draft` until TikTok audits the app, then `direct` (caption + AIGC flag automatic). |

The GPU box destroys itself 40 minutes after finishing (or failing), and the orchestrator destroys it
as soon as the video is downloaded, so a crash can't leave a GPU billing.

## One-time setup (about 30 minutes)

1. **GitHub**: the repo root is the `try-solarpunk` folder (public, so the GPU box can clone it; STLs stay local).
   The workflow lives at `.github/workflows/daily.yml` in the repo root. Actions → enable.
2. **RunPod**: add credit. Settings → API Keys → create a key → repo secret `RUNPOD_API_KEY`.
3. **Hugging Face**: accept the terms at https://huggingface.co/Lightricks/LTX-2.5, create a *Read* token,
   and save it in RunPod → Secrets as `hf_token` (the pod reads it there).
4. **Anthropic API**: console.anthropic.com key → repo secret `ANTHROPIC_API_KEY` (a plan costs ~1¢).
5. **TikTok developer app** (developers.tiktok.com): add *Login Kit* + *Content Posting API*,
   scopes `video.upload` (drafts) and `video.publish` (direct). Authorize @trysolarpunk once and store
   `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN` as repo secrets.
   Skip this and the workflow still makes the video; download it from the run's artifacts.
6. Submit the app for TikTok's Content Posting audit (2–6 weeks), then set `tiktok.mode: direct`.

Run once by hand: Actions → daily-video → Run workflow. After that it runs every morning.

## Costs (1 video/day)

| Item | Monthly |
|---|---|
| GPU, ~60–75 min/day on a RunPod L40S at $1.09/h | $30–40 |
| Claude API (plan) | under $1 |
| GitHub Actions (public repo) | $0 |
| TikTok, Fourthwall | $0 |

Model downloads (~75 GB) happen on each fresh box and are included in the GPU time above.
If that gets slow, rent a box with a persistent Vast volume and point `MODELS` at it.

## Day-to-day

- Hand-write a plan any time: copy `plans/2026-10-14-face-to-the-wall.json`, run the workflow with its path
  (e.g. `plans/my-plan.json`, relative to `pipeline/`).
- Change the voice, products, size or GPU budget in `config.yaml`.
- Every video carries an on-screen "AI-generated" label; switch on TikTok's AI-generated toggle when posting drafts.
