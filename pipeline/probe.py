"""Try a cheaper GPU: render 2 shots per LTX offload mode, report seconds per clip and peak VRAM.

  python probe.py "NVIDIA GeForce RTX 3090" ["NVIDIA RTX A5000" ...]   [--modes "none cpu"] [--secure]

No songs or edit, so it costs only setup (~10 min) plus the clips. Results land in
../videos/probe-<time>/ (probe.txt, per-mode logs, the clips). Push code first, like run.py.
"""
import argparse
import json
import os
import pathlib
import time
import urllib.request

import yaml

import run
from ge import concept, runpod

ROOT = pathlib.Path(__file__).resolve().parent


def collect(base, slugs, dest, log):
    """Pull probe.txt, the per-mode logs and the probe clips."""
    got = []
    for name in ["probe.txt", "job.log"] + [f"probe_{m}.log" for m in MODES]:
        try:
            urllib.request.urlretrieve(f"{base}/{name}", dest / name)
            got.append(name)
        except Exception as e:  # noqa: BLE001
            log(f"no {name}: {e}")
    for m in MODES:
        for i in range(2):
            try:
                urllib.request.urlretrieve(f"{base}/probe/{m}_shot_{i:02d}.mp4", dest / f"{m}_shot_{i:02d}.mp4")
                got.append(f"{m}_shot_{i:02d}.mp4")
            except Exception:  # noqa: BLE001
                pass
    return got


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("gpus", nargs="+")
    ap.add_argument("--modes", default="none cpu")
    ap.add_argument("--secure", action="store_true")
    ap.add_argument("--min-ram", type=int, default=48, help="GB of host RAM per GPU (offload cpu needs ~36)")
    a = ap.parse_args()
    MODES = a.modes.split()
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    cfg["gpu"]["max_runtime_minutes"] = 75
    plan = json.loads((ROOT / "plans/2026-10-17-style-test.json").read_text())
    plan["image"] = next(p["image"] for p in cfg["products"] if p["id"] == plan["product"])
    # shots 0 and 3 (claymation + the product shot) so both the plain and the image path are tested
    plan["shots"] = [plan["shots"][0], plan["shots"][3]]
    run.assert_code_pushed()
    dest = ROOT.parent / "videos" / f"probe-{time.strftime('%m%d-%H%M')}"
    dest.mkdir(parents=True)
    log = lambda m: print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
    t0 = time.time()
    got, info = runpod.run_job(cfg, [plan], run.REPO_URL, dest, log,
                               tiers=[("SECURE" if a.secure else "COMMUNITY", a.gpus)],
                               extra={"env": {"PROBE_MODES": a.modes, "KEEP_MIN": "10"}, "minRAMPerGPU": a.min_ram},
                               collect=collect)
    mins = (time.time() - t0) / 60
    print((dest / "probe.txt").read_text() if (dest / "probe.txt").exists() else "no probe.txt")
    print(f"{mins:.0f} min at ${info.get('dph_total')}/h, about ${mins / 60 * (info.get('dph_total') or 0):.2f}; files in {dest}")
