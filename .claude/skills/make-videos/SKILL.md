---
name: make-videos
description: Make Try Solarpunk TikTok videos end to end. Use when the user asks to make, render or batch videos ("make 7 videos", "make this week's videos", "render a video about X").
---

# Make videos

You write the plans yourself (no Claude API call), then one command renders them all on a
rented GPU and saves them to `videos/`. Do not watch the GPU: run the render in the background
and wait for the completion notice. Spend tokens on the writing, not the waiting.

## 1. Lineup

```bash
cd pipeline && python3 -m ge.concept next 7    # or the number the user asked for
```

Prints the date, product and product-shot description for each video, recent slugs to avoid,
and the number of shots per video. Follow that lineup unless the user asked for something else.

## 2. Write one plan per video

Save each as `pipeline/plans/<date>-<slug>.json`. Shape (see `plans/2026-10-14-face-to-the-wall.json`):

```json
{
  "slug": "kebab-case-unique", "date": "YYYY-MM-DD", "product": "hibernator | eyelid | merch",
  "hook_text": "max 7 words, shown big for the first 3 s",
  "song": {"title": "...", "style": "genre, instruments, vocal character, English, tempo in BPM",
           "lyrics": "[Verse]\n4 lines\n\n[Chorus]\n4 lines"},
  "shots": [{"prompt": "one cinematic paragraph, <=120 words", "product_image": false}],
  "endcard": {"line1": "max 6 words", "line2": "link in bio"},
  "caption": "max 150 chars, no hashtags", "hashtags": ["#touchgrass", "..."]
}
```

Writing rules:
- Voice: warm, a little unhinged, never preachy. Deeply online people who want out, laughing at
  ourselves. Solarpunk hope, not doom. The joke is on the feed, never on the viewer. Never shame
  anyone for using their phone. No real people, brands, politicians, songs, artists or bands
  (not even in the song style).
- Song: exactly one [Verse] of 4 lines and one [Chorus] of 4 lines (about 45 s). Original lyrics.
  Give every video in a batch its own genre, setting and joke; no two hooks alike.
- Style: each plan picks `"style"` from `config.yaml` `styles` (claymation, felt, printed); it is
  prepended to every shot except the product shot, so don't describe the art style in prompts.
  Write subjects that suit it (simple shapes, one clear action). Rotate styles across a batch.
  The owner liked claymation and felt, disliked hand-drawn 2D ("feels corporate").
- Captions: the lyrics are burned in word by word, so keep lines short and singable, no stage directions.
- Shots: exactly the count `next` printed. Each prompt starts with the main action, then subject
  details, setting, camera move, light and colour. Solarpunk everyday life: rooftop gardens,
  bikes, shared meals, sunlight, people looking up. No readable text, logos, phone screens
  showing apps, or famous people. Avoid crowds of small repeated objects (LTX invents props,
  e.g. a floating chain of tomatoes); prefer one clear subject and simple motion.
- Exactly one shot has `"product_image": true`, showing the product exactly as `next` describes it,
  with gentle motion (a hand placing a phone in it, light shifting). For hibernator and eyelid the
  render in `assets/` becomes that shot's first frame, so describe what is in that photo.
- Shot 1 is a strong visual hook. The last shot feels like a deep breath.
- Caption: playful, mentions the product by name once. 4 to 6 lowercase hashtags.

## 3. Check, then render

Cheap GPUs come and go. `run.py` prints every card in stock with its estimated batch cost and rents
the cheapest. If the cheapest option is well above about $0.40 for 7 videos and the user isn't in a
hurry, say so and suggest the best hour from `python3 -m ge.availability --summary`.

```bash
cd pipeline && python3 -m ge.concept check plans/<new files>
```

Then render, one of two ways:

- **Now** (the user wants the videos today): `python3 -u run.py plans/<new files> > ../videos/run.log 2>&1`
  with Bash run_in_background, then immediately arm a Monitor on `videos/run.log` that prints each new
  line, says STALL if the log is silent for 15 min, and exits when `run.py` exits. A background Bash
  task only wakes you when it exits, so without the Monitor a hung pod is invisible.
- **Cheapest** (the default when there's no rush): wait up to 24 h for a card near the best price,
  detached so it survives closing Claude Code, with the Mac kept awake:
  `cd pipeline && nohup caffeinate -i python3 -u run.py --wait 24 plans/<new files> > ../videos/run.log 2>&1 &`
  It checks stock every 2 min (free) and rents only a card within 15% of the best listed batch cost
  (about $0.40 for 7 videos); after 24 h it takes the cheapest in stock. A macOS notification says when
  the videos are ready or the run failed. Tell the user the Mac must stay on (lid closed on battery
  still sleeps). Don't babysit the wait: check `videos/run.log` when the user is back, and only arm
  the Monitor once a line says "rented".

`run.py` itself aborts and deletes the pod after 20 min without a stage change (each finished clip is
a change), and the pod fails fast if LTX can't see the GPU.

`run.py` refuses to start if pipeline code is unpushed (the GPU box clones it from GitHub);
commit and push code changes first. Plans don't need pushing. It rents one GPU, renders the
whole batch, downloads `videos/<date>-<slug>.mp4` plus a `.txt` caption, deletes the GPU and
prints the cost. Expect about 10 min of setup plus about 1 min per clip.

## 4. After

- Report: videos made, failures, minutes and dollars (one short list).
- If something failed, read `videos/job.log` (grep for FAILED or Traceback) before guessing.
- Commit `pipeline/plans/` and `pipeline/history.jsonl` and push.
- Posting is manual for now: the user posts from the TikTok app with the `.txt` caption and the
  AI-generated toggle on.
