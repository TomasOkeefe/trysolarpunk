"""Render shots only (no song, no edit) and download the raw clips: reference footage, e.g. a
character photo shoot for LoRA training.

  python shoot.py plans/moss-shoot.json [--frames 49]

The plan needs only slug, style and shots (any number). Clips land in ../videos/raw/<slug>/.
Rents the cheapest card in stock, like run.py. Push code first.
"""
import argparse
import json
import pathlib
import tarfile
import time
import urllib.request

import yaml

import run
from ge import box, concept, runpod

ROOT = pathlib.Path(__file__).resolve().parent


def collect(base, slugs, dest, log):
    got = []
    for s in slugs:
        tar = dest / f"{s}.tar"
        box.download(f"{base}/{s}/raw.tar", tar)
        with tarfile.open(tar) as t:
            t.extractall(dest / s, filter="data")
        tar.unlink()
        got.append(s)
    box.download(f"{base}/job.log", dest / "job.log")
    return got


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--frames", type=int, default=49, help="frames per clip (8k+1); 49 is ~2 s; a shot's own \"frames\" wins")
    ap.add_argument("--provider", choices=["runpod", "modal"], default="runpod",
                    help="modal runs this folder's code as it is (no push needed)")
    ap.add_argument("--lora", nargs=2, metavar=("URL", "STRENGTH"),
                    help="use this LoRA instead of the one in config.yaml (to try a new checkpoint; on Modal a "
                         "file:///work/... URL reads it straight from the work volume)")
    ap.add_argument("--no-lora", action="store_true", help="render without any character LoRA")
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    plan = concept.expand(json.loads(pathlib.Path(a.plan).read_text()), cfg.get("characters", {}), cfg.get("loras"))
    if a.lora:
        plan["loras"] = [{"url": a.lora[0], "strength": float(a.lora[1])}]
    if a.no_lora:
        plan.pop("loras", None)
    style = plan.get("style", cfg["video"].get("style", ""))
    plan["style"] = cfg.get("styles", {}).get(style, style)
    dest = ROOT.parent / "videos" / "raw"
    dest.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
    env = {"CLIPS_ONLY": "1", "GEN_FRAMES": str(a.frames)}
    if a.provider == "modal":
        from ge import modal_runner
        got, info = modal_runner.run_job(cfg, [plan], dest, log, extra_env=env, raw_only=True)
    else:
        run.assert_code_pushed()
        got, info = runpod.run_job(cfg, [plan], run.REPO_URL, dest, log, collect=collect,
                                   extra={"env": {**env, "KEEP_MIN": "15"}})
    hours = info.get("hours", 0)
    print(f"{len(plan['shots'])} clips in {dest / plan['slug']}, {hours * 60:.0f} min, about ${hours * (info.get('dph_total') or 0):.2f}")
