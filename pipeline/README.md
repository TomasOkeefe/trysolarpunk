# Try Solarpunk: video pipeline

Open Claude Code in the repo and ask for videos ("make 7 videos"). Claude writes the plans,
one rented GPU renders the whole batch, and the videos land in `videos/`. The steps Claude
follows are in `.claude/skills/make-videos/SKILL.md`.

```
Claude writes plans ──► one RunPod GPU session ─────────────────────────────► videos/
(in the chat, free)     songs (YuE2) → all clips (LTX-2.5) → edits             <date>-<slug>.mp4
                        (hook text, lyric captions, end card, -14 LUFS)       + caption .txt
```

| Step | Where | What |
|---|---|---|
| Lineup | `ge/concept.py next` | Which product on which day (4 Hibernator, 2 Eyelid, 1 merch a week), recent slugs to avoid. |
| Check | `ge/concept.py check` | Validates plans before any GPU money is spent. |
| Render | `run.py` → `ge/runpod.py` → `worker/job.sh` | Rents a pod, waits, downloads the videos, deletes the pod, prints the cost. |
| Song | `worker/gen_song.py` | YuE2-3B, ~45 s, verse + chorus; one model load for the batch. Free to monetize per the YuE2 license. |
| Clips | `worker/gen_clips.py` | LTX-2.5 distilled, 768×1344, 5 s each, in the `style` from `config.yaml` (claymation by default). Gemma encodes every prompt once and is freed, then the transformer stays on the GPU for all clips. The product shot starts from our render. |
| Captions | `ge/lyrics.py` | Times the lyrics against the demucs-isolated vocals (stable-ts forced alignment). |
| Edit | `ge/assemble.py` | Trims the song's intro, beat cuts (librosa), frames held on twos, hook text for 3 s, TikTok-style lyric captions, end card, loudness. No burned-in AI label: TikTok adds its own when the AI-generated toggle is on. |

The orchestrator deletes the pod as soon as the videos are downloaded, and the pod deletes itself
40 minutes after finishing or failing, so a crash can't leave a GPU billing. One broken video
doesn't sink the batch.

## One-time setup (done)

- RunPod credit, and `flash login` on this Mac (saves the key to `~/.runpod/config.toml`).
- Hugging Face: LTX-2.5 terms accepted, read token saved in RunPod → Secrets as `hf_token`.

## Costs

Community L40S at about $1.10/h: about 10 min of setup plus about 1 min per clip, so a
7-video batch (63 clips) should be roughly 75 min, about $1.40, or $0.20 a video.
To be confirmed by the first batch. Planning costs nothing extra (Claude writes the plans in the chat).

## By hand

```bash
cd pipeline
python3 -m ge.concept next 7
python3 -m ge.concept check plans/2026-10-14-face-to-the-wall.json
python3 run.py plans/2026-10-14-face-to-the-wall.json
```

Change products, voice, sizes or the GPU in `config.yaml`. `ge/tiktok.py` (Content Posting API
drafts) is kept for later; posting is manual for now.
