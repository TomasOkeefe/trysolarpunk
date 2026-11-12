"""Train a character LoRA on rented GPU: upload the dataset to a GitHub release, train with LTX's
trainer on our distilled LTX-2.5 transformer, download every checkpoint.

  python train_lora.py DATASET_DIR --name moss --trigger m0ss [--steps 1500]

DATASET_DIR holds dataset.json ([{"video": "clips/x.mp4", "caption": "..."}]) and the clips.
Checkpoints (every 250 steps) land in ../videos/lora/<name>/. The release is on the public repo.
"""
import argparse
import pathlib
import subprocess
import tarfile
import time
import urllib.request

import yaml

import run
from ge import box, runpod

ROOT = pathlib.Path(__file__).resolve().parent
REPO = "TomasOkeefe/trysolarpunk"
# 80 GB+ cards train in bf16; 48 GB cards fall back to int8 (lora_config.py), slower
TIERS = [  # cheapest first; Blackwell PRO 6000s (96 GB) are also faster than A100s
    ("SECURE", ["NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition"]),          # $0.50/h
    ("COMMUNITY", ["NVIDIA A100 80GB PCIe", "NVIDIA A100-SXM4-80GB"]),               # $1.19-1.39
    ("COMMUNITY", ["NVIDIA H100 80GB HBM3", "NVIDIA H100 PCIe"]),                     # $2.69, ~2.5x faster: cheapest total
    ("COMMUNITY", ["NVIDIA RTX PRO 6000 Blackwell Workstation Edition"]),             # $1.69, 1.5 s/step (measured)
    ("SECURE", ["NVIDIA A100 80GB PCIe", "NVIDIA A100-SXM4-80GB"]),
    ("COMMUNITY", ["NVIDIA RTX A6000", "NVIDIA A40"]),
    ("SECURE", ["NVIDIA RTX A6000", "NVIDIA A40"]),
]


def gh(*a):
    return subprocess.run(["gh", *a, "-R", REPO], capture_output=True, text=True)


def upload(tag, path):
    if gh("release", "view", tag).returncode != 0:
        gh("release", "create", tag, "--title", tag, "--notes", "Character LoRA training data and weights.")
    r = gh("release", "upload", tag, str(path), "--clobber")
    if r.returncode != 0:
        raise SystemExit(f"upload failed: {r.stderr}")
    return f"https://github.com/{REPO}/releases/download/{tag}/{path.name}"


def collect_into(dest):
    def collect(base, slugs, _dest, log):
        token_root = base.rsplit("/", 1)[1]
        files = urllib.request.urlopen(f"{base}/lora/files.txt", timeout=60).read().decode().split()
        got = []
        for f in files:
            rel = f.split(f"/{token_root}/", 1)[1]
            out = dest / pathlib.Path(rel).name
            log(f"downloading {rel}")
            box.download(f"{base}/{rel}", out)
            got.append(out.name)
        for name in ("train.log", "job.log"):
            try:
                box.download(f"{base}/{name}", dest / name)
            except Exception:  # noqa: BLE001
                pass
        return got
    return collect


def train_on_modal(a, tar, dest, log):
    """Train on Modal: the dataset travels on the ge-work volume, checkpoints come back from it.
    --small runs on the cheap L40S (int8, slow): a few-step smoke test of the whole path."""
    import modal
    import modal_app
    from ge import box, modal_runner
    with modal_app.work.batch_upload(force=True) as up:
        up.put_file(str(tar), f"/data/{tar.name}")
    run_id = time.strftime("%Y%m%d-%H%M%S-") + f"train-{a.name}"
    env = {"TRAIN_DATA_URL": f"file:///work/data/{tar.name}", "TRAIN_TRIGGER": a.trigger,
           "TRAIN_STEPS": str(a.steps), "TRAIN_BUCKETS": a.buckets}
    fn = modal_app.train_small if a.small else modal_app.train
    started = time.time()
    with modal.enable_output():
        with modal_app.app.run(detach=True):
            call = fn.spawn(run_id, box.pack_plans([{"slug": f"train-{a.name}", "shots": []}]), env)
    log(f"modal training {run_id} (call {call.object_id}) started")
    out, last, finished = f"runs/{run_id}/out/out", None, False
    while not finished:
        try:
            call.get(timeout=60)
            finished = True
        except TimeoutError:
            pass
        try:
            stage = modal_runner._read(modal_app.work, f"{out}/STAGE").decode().strip()
        except Exception:  # noqa: BLE001  (not written yet)
            stage = "starting"
        if stage != last:
            log(f"stage: {stage}")
            last = stage
    got = []
    try:
        files = modal_runner._read(modal_app.work, f"{out}/lora/files.txt").decode().split()
    except Exception:  # noqa: BLE001
        files = []
    for f in files:
        rel = f.split("/work/", 1)[1]
        log(f"downloading {pathlib.Path(rel).name}")
        (dest / pathlib.Path(rel).name).write_bytes(modal_runner._read(modal_app.work, rel))
        got.append(pathlib.Path(rel).name)
    for name in ("train.log", "job.log"):
        try:
            (dest / name).write_bytes(modal_runner._read(modal_app.work, f"{out}/{name}"))
        except Exception:  # noqa: BLE001
            pass
    hours = (time.time() - started) / 3600
    return got, {"hours": hours, "dph_total": 1.95 if a.small else 3.95}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--name", required=True)
    ap.add_argument("--trigger", required=True)
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--buckets", default="512x896x49")
    ap.add_argument("--provider", choices=["runpod", "modal"], default="runpod",
                    help="modal runs this folder's code as it is (no push needed), on an H100 or A100-80GB")
    ap.add_argument("--small", action="store_true", help="modal only: the cheap L40S, for a few-step smoke test")
    a = ap.parse_args()
    log = lambda m: print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
    src = pathlib.Path(a.dataset)
    tar = src.parent / f"{a.name}-dataset.tar"
    with tarfile.open(tar, "w") as t:
        t.add(src / "dataset.json", "dataset.json")
        t.add(src / "clips", "clips")
    if a.provider == "modal":
        dest = ROOT.parent / "videos" / "lora" / a.name
        dest.mkdir(parents=True, exist_ok=True)
        got, info = train_on_modal(a, tar, dest, log)
        hours = info["hours"]
        print(f"{len(got)} checkpoints in {dest}, {hours * 60:.0f} min, at most ${hours * info['dph_total']:.2f}")
        raise SystemExit(0 if got else 1)
    run.assert_code_pushed()
    url = upload(f"{a.name}-lora", tar)
    log(f"dataset uploaded: {url}")
    dest = ROOT.parent / "videos" / "lora" / a.name
    dest.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    cfg["gpu"]["max_runtime_minutes"] = 240
    plan = {"slug": f"train-{a.name}", "shots": []}
    got, info = runpod.run_job(cfg, [plan], run.REPO_URL, dest, log, tiers=TIERS, collect=collect_into(dest),
                               extra={"env": {"TRAIN_DATA_URL": url, "TRAIN_TRIGGER": a.trigger,
                                              "TRAIN_STEPS": str(a.steps), "TRAIN_BUCKETS": a.buckets,
                                              "KEEP_MIN": "20"}})
    hours = info.get("hours", 0)
    print(f"{len(got)} checkpoints in {dest}, {hours * 60:.0f} min, about ${hours * (info.get('dph_total') or 0):.2f}")
