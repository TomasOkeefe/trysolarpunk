"""Render a batch of plans in one RunPod GPU session and save the videos to ../videos/.

  python run.py plans/a.json plans/b.json ...

Blocks until the box is done (about 10 min setup + ~1 min per clip), then deletes it.
The box clones the code from GitHub, so pipeline code changes must be pushed first;
plans travel with the request and need no push.
RunPod key: RUNPOD_API_KEY or ~/.runpod/config.toml (written by `flash login`).
"""
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


def main():
    files = sys.argv[1:]
    if not files:
        sys.exit(__doc__)
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    images = {p["id"]: p.get("image") for p in cfg["products"]}
    plans = []
    for f in files:
        plan = concept.validate(json.loads(pathlib.Path(f).read_text()), cfg["video"]["shots"])
        plan["image"] = images.get(plan["product"])  # first frame of the product shot (None: text only)
        style = plan.get("style", cfg["video"].get("style", ""))
        plan["style"] = cfg.get("styles", {}).get(style, style)  # a style name, or literal style text
        plan["anim_fps"] = cfg["video"].get("anim_fps")
        plans.append(plan)
    assert_code_pushed()

    t0 = time.time()
    log = lambda m: print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
    VIDEOS.mkdir(exist_ok=True)
    done, info = runpod.run_job(cfg, plans, REPO_URL, VIDEOS, log)
    hours = (time.time() - t0) / 3600
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
    if not done:
        sys.exit(1)


if __name__ == "__main__":
    main()
