"""Render a batch of plans in one RunPod GPU session and save the videos to ../videos/.

  python run.py plans/a.json plans/b.json ...
  python run.py --wait 24 plans/*.json     # wait up to 24 h for a card near the best price, then render

--wait only rents a card whose estimated batch cost is within 15% of the cheapest card RunPod lists
(--max-cost to set it yourself); after the wait it takes the cheapest in stock. Run it detached with
caffeinate so it survives closing Claude Code and keeps the Mac awake (see the make-videos skill).

Blocks until the box is done (about 10 min setup + ~1 min per clip), then deletes it.
Then each new video is queued on Buffer for TikTok on its plan's date (ge/buffer.py); --no-post skips that.
The box clones the code from GitHub, so pipeline code changes must be pushed first;
plans travel with the request and need no push.
RunPod key: RUNPOD_API_KEY or ~/.runpod/config.toml (written by `flash login`).
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

import yaml

from ge import buffer, concept, runpod

ROOT = pathlib.Path(__file__).resolve().parent
VIDEOS = ROOT.parent / "videos"
REPO_URL = "https://github.com/TomasOkeefe/trysolarpunk"


def assert_code_pushed():
    git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True).stdout.strip()
    dirty = git("status", "--porcelain", "--", "worker", "ge", "assets", "config.yaml")
    git("fetch", "-q")
    ahead = git("rev-list", "--count", "@{u}..HEAD")
    if dirty or ahead not in ("", "0"):
        sys.exit(f"push the pipeline code first; the GPU box clones it from GitHub\n{dirty}\nunpushed commits: {ahead}")


def gpu_and_speed(job_log):
    """The card the box ran on and its median seconds per clip, from the box's job.log."""
    if not job_log.exists():
        return None, None
    text = job_log.read_text(errors="replace")
    gpu = re.search(r"== setup on (.+)", text)
    per = {}  # dfr renders each shot in two passes: a clip costs both
    for slug, shot, sec in re.findall(r"(\S+) shot (\d+) (?:pass \d )?done in (\d+)s", text):
        per[slug, shot] = per.get((slug, shot), 0) + int(sec)
    secs = sorted(per.values())
    return (gpu.group(1).strip() if gpu else None), (secs[len(secs) // 2] if secs else None)


def notify(msg):
    """macOS notification, so a detached overnight run reports back."""
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Try Solarpunk"'],
                   capture_output=True)


CHEAP_RUNPOD = [("community", "A6000"), ("community", "A40")]
MODAL_FREE_PER_MONTH = 30.0  # Modal Starter plan credits


def modal_spent_this_month():
    f, month = ROOT / "history.jsonl", time.strftime("%Y-%m")
    rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []
    return sum(r.get("cost", 0) for r in rows if r.get("provider") == "modal" and r.get("month") == month)


def modal_estimate(plans):
    from ge import modal_runner
    clips = sum(len(p["shots"]) for p in plans)
    return (6 + 2 * len(plans) + clips * 55 / 60) / 60 * modal_runner.GPU_PER_HOUR  # dfr: ~53 s a clip on an L40S


def render(a, cfg, plans, log, max_cost, only):
    """Pick where to render (see --provider) and run the batch there."""
    from ge import modal_runner
    if a.provider == "modal":
        return modal_runner.run_job(cfg, plans, VIDEOS, log)
    if a.provider == "runpod":
        return runpod.run_job(cfg, plans, REPO_URL, VIDEOS, log, wait_hours=a.wait, max_cost=max_cost,
                              exclude=a.exclude, only=only)
    try:  # auto: a cheap community card on RunPod if one is free this minute
        return runpod.run_job(cfg, plans, REPO_URL, VIDEOS, log, only=only or CHEAP_RUNPOD, exclude=a.exclude)
    except SystemExit as e:
        if "no allowed GPU" not in str(e):
            raise
    spent, est = modal_spent_this_month(), modal_estimate(plans)
    if spent + est <= MODAL_FREE_PER_MONTH:
        log(f"no cheap RunPod card free; Modal (free credits: ${spent:.2f} of ${MODAL_FREE_PER_MONTH:.0f} used "
            f"this month, this batch ~${est:.2f})")
        return modal_runner.run_job(cfg, plans, VIDEOS, log)
    log(f"Modal credits nearly used (${spent:.2f} this month); waiting for a cheap RunPod card")
    return runpod.run_job(cfg, plans, REPO_URL, VIDEOS, log, wait_hours=a.wait or 168, only=only or CHEAP_RUNPOD,
                          exclude=a.exclude)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--wait", type=float, default=0, help="hours to wait for a cheap card")
    ap.add_argument("--max-cost", type=float, help="batch dollars worth renting at while waiting")
    ap.add_argument("--exclude", action="append", default=[], help="skip GPUs whose name contains this (repeatable)")
    ap.add_argument("--only", action="append", default=[], metavar="CLOUD:GPU",
                    help="rent only these, e.g. community:A6000 (repeatable); with --wait, never anything else")
    ap.add_argument("--no-post", action="store_true", help="don't queue the videos on Buffer (tests)")
    ap.add_argument("--provider", choices=["auto", "runpod", "modal"], default="auto",
                    help="auto: a community A6000/A40 on RunPod if one is free right now, else Modal while this "
                         "month's free credits last, else wait for the cheap RunPod cards")
    a = ap.parse_args()
    files = a.files
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    images = {p["id"]: p.get("image") for p in cfg["products"]}
    plans = []
    for f in files:
        plan = concept.validate(concept.expand(json.loads(pathlib.Path(f).read_text()), cfg.get("characters", {}), cfg.get("loras")),
                                cfg["video"]["shots"])
        plan["image"] = images.get(plan["product"])  # first frame of the product shot (None: text only)
        style = plan.get("style", cfg["video"].get("style", ""))
        plan["style"] = cfg.get("styles", {}).get(style, style)  # a style name, or literal style text
        plan["anim_fps"] = cfg["video"].get("anim_fps")
        plan["target_seconds"] = cfg["video"].get("target_seconds", 45)
        plan.setdefault("speed", cfg["video"].get("speed", 1.0))
        plans.append(plan)
    assert_code_pushed()

    log = lambda m: print(f"[{time.strftime('%a %H:%M:%S')}] {m}", flush=True)
    VIDEOS.mkdir(exist_ok=True)
    max_cost = a.max_cost
    only = [tuple(x.split(":", 1)) for x in a.only]
    if a.wait and max_cost is None and not only:
        best = runpod.best_case(sum(len(p["shots"]) for p in plans))
        max_cost = round(best["cost"] * 1.15, 2)
        log(f"best possible: ${best['cost']:.2f} on {best['cloud'].lower()} {best['gpu'].replace('NVIDIA ', '')}; "
            f"will rent at <= ${max_cost:.2f}")
    try:
        done, info = render(a, cfg, plans, log, max_cost, only)
    except BaseException as e:
        notify(f"Render failed: {str(e)[:80]}")
        raise
    hours = info.get("hours", 0)
    cost = hours * (info.get("dph_total") or 0)
    gpu, sec = gpu_and_speed(VIDEOS / "job.log")
    if gpu and sec:
        runpod.record_speed(gpu, sec)

    with open(ROOT / "history.jsonl", "a") as h:
        for plan in plans:
            if plan["slug"] not in done:
                print(f"FAILED  {plan['date']}  {plan['slug']}  (see videos/job.log)")
                continue
            name = f"{plan['date']}-{plan['slug']}"
            (VIDEOS / f"{plan['slug']}.mp4").rename(VIDEOS / f"{name}.mp4")
            (VIDEOS / f"{plan['slug']}.json").unlink(missing_ok=True)
            (VIDEOS / f"{name}.txt").write_text(f"{plan['caption']} {' '.join(plan['hashtags'])}\n")
            h.write(json.dumps({"date": plan["date"], "slug": plan["slug"], "product": plan["product"],
                                "gpu": gpu, "dph": info.get("dph_total"), "sec_per_clip": sec,
                                "provider": info.get("provider", "runpod"), "month": time.strftime("%Y-%m"),
                                "cost": round(cost / max(1, len(done)), 3)}) + "\n")
            print(f"ok      videos/{name}.mp4")
    print(f"{len(done)}/{len(plans)} videos, {hours * 60:.0f} min on {gpu} ({sec}s a clip), about ${cost:.2f}")
    notify(f"{len(done)}/{len(plans)} videos ready in videos/, about ${cost:.2f}")
    if not a.no_post:
        for plan in plans:
            if plan["slug"] in done:
                try:
                    buffer.queue(VIDEOS / f"{plan['date']}-{plan['slug']}.mp4")
                except (Exception, SystemExit) as e:
                    print(f"NOT QUEUED  {plan['date']}-{plan['slug']}: {e}")
                    notify(f"Buffer queue failed: {str(e)[:80]}")
    if not done:
        sys.exit(1)


if __name__ == "__main__":
    main()
