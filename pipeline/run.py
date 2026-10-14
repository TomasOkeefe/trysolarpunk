"""Daily run: plan -> GPU (song + clips + edit) -> TikTok.

  python run.py                    # full run, plan written by Claude
  python run.py --plan plans/x.json  # use a hand-written plan
  python run.py --dry-plan         # only write and print today's plan (no GPU, no TikTok)

Env: ANTHROPIC_API_KEY, RUNPOD_API_KEY (or VAST_API_KEY + HF_TOKEN), GE_REPO_URL,
     TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN (optional: skip upload if unset)
"""
import argparse
import datetime as dt
import json
import os
import pathlib

import yaml

from ge import concept, runpod, tiktok, vast

ROOT = pathlib.Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan")
    ap.add_argument("--dry-plan", action="store_true")
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())

    plan = json.loads(pathlib.Path(a.plan).read_text()) if a.plan else concept.write_plan(cfg)
    plan = concept.validate(plan, cfg["video"]["shots"])
    plan_file = ROOT / "plans" / f"{plan.get('date', dt.date.today().isoformat())}-{plan['slug']}.json"
    plan_file.write_text(json.dumps(plan, indent=2))
    print(json.dumps(plan, indent=2))
    if a.dry_plan:
        return

    gpu = runpod if cfg["gpu"].get("provider", "runpod") == "runpod" else vast
    video, offer = gpu.run_job(cfg, plan, os.environ["GE_REPO_URL"])
    result = {"date": plan.get("date"), "slug": plan["slug"], "product": plan["product"],
              "gpu": offer.get("gpu_name"), "dph": offer.get("dph_total")}

    if os.environ.get("TIKTOK_REFRESH_TOKEN"):
        status = tiktok.upload(video, plan, cfg["tiktok"]["mode"])
        result["tiktok"] = status.get("status")
    with open(ROOT / "history.jsonl", "a") as f:
        f.write(json.dumps(result) + "\n")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(f"## {plan['song']['title']}\n\n**Caption to paste:**\n\n"
                    f"{plan['caption']} {' '.join(plan['hashtags'])}\n\n"
                    f"Remember to switch on *AI-generated content* when posting.\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
