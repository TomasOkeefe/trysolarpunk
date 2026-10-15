"""Render a batch of plans in one RunPod GPU session and save the videos to ../videos/.

  python run.py plans/a.json plans/b.json ...
  python run.py --wait 24 plans/*.json     # wait up to 24 h for a card near the best price, then render

--wait only rents a card whose estimated batch cost is within 15% of the cheapest card RunPod lists
(--max-cost to set it yourself); after the wait it takes the cheapest in stock. Run it detached with
caffeinate so it survives closing Claude Code and keeps the Mac awake (see the make-videos skill).

Blocks until the box is done (about 10 min setup + ~1 min per clip), then deletes it.
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

from ge import concept, runpod

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
    secs = sorted(int(x) for x in re.findall(r"shot \d+ done in (\d+)s", text))
    return (gpu.group(1).strip() if gpu else None), (secs[len(secs) // 2] if secs else None)


def notify(msg):
    """macOS notification, so a detached overnight run reports back."""
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Try Solarpunk"'],
                   capture_output=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--wait", type=float, default=0, help="hours to wait for a cheap card")
    ap.add_argument("--max-cost", type=float, help="batch dollars worth renting at while waiting")
    a = ap.parse_args()
    files = a.files
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    images = {p["id"]: p.get("image") for p in cfg["products"]}
    plans = []
    for f in files:
        plan = concept.validate(concept.expand(json.loads(pathlib.Path(f).read_text()), cfg.get("characters", {})),
                                cfg["video"]["shots"])
        plan["image"] = images.get(plan["product"])  # first frame of the product shot (None: text only)
        style = plan.get("style", cfg["video"].get("style", ""))
        plan["style"] = cfg.get("styles", {}).get(style, style)  # a style name, or literal style text
        plan["anim_fps"] = cfg["video"].get("anim_fps")
        plans.append(plan)
    assert_code_pushed()

    log = lambda m: print(f"[{time.strftime('%a %H:%M:%S')}] {m}", flush=True)
    VIDEOS.mkdir(exist_ok=True)
    max_cost = a.max_cost
    if a.wait and max_cost is None:
        best = runpod.best_case(sum(len(p["shots"]) for p in plans))
        max_cost = round(best["cost"] * 1.15, 2)
        log(f"best possible: ${best['cost']:.2f} on {best['cloud'].lower()} {best['gpu'].replace('NVIDIA ', '')}; "
            f"will rent at <= ${max_cost:.2f}")
    try:
        done, info = runpod.run_job(cfg, plans, REPO_URL, VIDEOS, log, wait_hours=a.wait, max_cost=max_cost)
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
                                "gpu": gpu, "dph": info.get("dph_total"), "sec_per_clip": sec}) + "\n")
            print(f"ok      videos/{name}.mp4")
    print(f"{len(done)}/{len(plans)} videos, {hours * 60:.0f} min on {gpu} ({sec}s a clip), about ${cost:.2f}")
    notify(f"{len(done)}/{len(plans)} videos ready in videos/, about ${cost:.2f}")
    if not done:
        sys.exit(1)


if __name__ == "__main__":
    main()
