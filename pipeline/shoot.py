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
from ge import concept, runpod

ROOT = pathlib.Path(__file__).resolve().parent


def collect(base, slugs, dest, log):
    got = []
    for s in slugs:
        tar = dest / f"{s}.tar"
        urllib.request.urlretrieve(f"{base}/{s}/raw.tar", tar)
        with tarfile.open(tar) as t:
            t.extractall(dest / s, filter="data")
        tar.unlink()
        got.append(s)
    urllib.request.urlretrieve(f"{base}/job.log", dest / "job.log")
    return got


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--frames", type=int, default=49, help="frames per clip (8k+1); 49 is ~2 s")
    a = ap.parse_args()
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    plan = concept.expand(json.loads(pathlib.Path(a.plan).read_text()), cfg.get("characters", {}), cfg.get("loras"))
    style = plan.get("style", cfg["video"].get("style", ""))
    plan["style"] = cfg.get("styles", {}).get(style, style)
    run.assert_code_pushed()
    dest = ROOT.parent / "videos" / "raw"
    dest.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
    got, info = runpod.run_job(cfg, [plan], run.REPO_URL, dest, log, collect=collect,
                               extra={"env": {"CLIPS_ONLY": "1", "GEN_FRAMES": str(a.frames), "KEEP_MIN": "15"}})
    hours = info.get("hours", 0)
    print(f"{len(plan['shots'])} clips in {dest / plan['slug']}, {hours * 60:.0f} min, about ${hours * (info.get('dph_total') or 0):.2f}")
