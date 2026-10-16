"""Rent a GPU pod on RunPod, run worker/job.sh on it for a batch of plans, fetch the videos, delete the pod.

REST API: https://rest.runpod.io/v1  (key: env RUNPOD_API_KEY, else ~/.runpod/config.toml from `flash login`)
The pod reads HF_TOKEN from the RunPod secret `hf_token`, so the token never passes through here.
Every exit path deletes the pod, and the pod deletes itself KEEP_MIN minutes after finishing.
"""
import json
import os
import pathlib
import secrets
import subprocess
import time
import urllib.error
import urllib.request

from ge import box

API = "https://rest.runpod.io/v1"
# Every card that can run the batch, with seconds per clip (768x1344, 121 frames). Values measured on a
# real run are kept in gpu_speeds.json and override these; the rest are guesses from bf16 throughput.
# 32 GB cards (5090, 5000 Ada, PRO 4500) are left out: without offload they run out of memory by ~0.2 GB,
# and offload speed depends on the host (2 min a clip on one 3090, 7.5 on a PRO 4500).
SEC_PER_CLIP = {
    "NVIDIA RTX A6000": 50, "NVIDIA A40": 50,
    "NVIDIA L40": 42, "NVIDIA RTX 6000 Ada Generation": 36, "NVIDIA L40S": 35,
    "NVIDIA RTX PRO 5000 Blackwell": 32,
    "NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition": 28,
    "NVIDIA RTX PRO 6000 Blackwell Server Edition": 25, "NVIDIA RTX PRO 6000 Blackwell Workstation Edition": 25,
    "NVIDIA A100-SXM4-40GB": 40, "NVIDIA A100 80GB PCIe": 35, "NVIDIA A100-SXM4-80GB": 33,
    "NVIDIA GeForce RTX 3090": 121,  # 24 GB, CPU offload (job.sh turns it on)
}
SETUP_MIN = 14  # installs, downloads, model loads: paid at the same rate on every card
VIDEO_MIN = 2   # per video: song, lyric timing, edit (measured: 7 videos took 82 min on an A40 at 50 s a clip)
SPEEDS = pathlib.Path(__file__).resolve().parents[1] / "gpu_speeds.json"


def options(n_clips, in_stock=True, n_videos=None):
    """Every (cloud, card) in stock right now (or listed at all), cheapest estimated batch cost first."""
    measured = {g: sorted(v)[len(v) // 2] for g, v in _speeds().items()}  # median of recent runs
    q = """query { gpuTypes { id securePrice communityPrice
      c: lowestPrice(input:{gpuCount:1, secureCloud:false}) { stockStatus uninterruptablePrice }
      s: lowestPrice(input:{gpuCount:1, secureCloud:true}) { stockStatus uninterruptablePrice } } }"""
    req = urllib.request.Request("https://api.runpod.io/graphql", data=json.dumps({"query": q}).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {_key()}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        gpus = json.loads(r.read())["data"]["gpuTypes"]
    out = []
    for g in gpus:
        if g["id"] not in SEC_PER_CLIP:
            continue
        sec = measured.get(g["id"], SEC_PER_CLIP[g["id"]])
        for cloud, k, list_price in (("COMMUNITY", "c", g["communityPrice"]), ("SECURE", "s", g["securePrice"])):
            lp = g[k] or {}
            price = lp.get("uninterruptablePrice") or list_price
            if (in_stock and not lp.get("stockStatus")) or not price:
                continue
            hours = (SETUP_MIN + VIDEO_MIN * (n_videos or round(n_clips / 9))) / 60 + n_clips * sec / 3600
            out.append({"cloud": cloud, "gpu": g["id"], "price": price, "stock": lp["stockStatus"],
                        "sec": sec, "measured": g["id"] in measured, "hours": hours, "cost": price * hours})
    return sorted(out, key=lambda o: o["cost"])


def _speeds():
    return json.loads(SPEEDS.read_text()) if SPEEDS.exists() else {}


def record_speed(gpu, sec):
    """Remember a measured seconds-per-clip (last 5 runs per card) so the next ranking uses it."""
    measured = _speeds()
    measured[gpu] = (measured.get(gpu, []) + [round(sec)])[-5:]
    SPEEDS.write_text(json.dumps(measured, indent=1, sort_keys=True) + "\n")


def _key():
    if os.environ.get("RUNPOD_API_KEY"):
        return os.environ["RUNPOD_API_KEY"]
    import tomllib
    cfg = pathlib.Path.home() / ".runpod" / "config.toml"
    conf = tomllib.loads(cfg.read_text()) if cfg.exists() else {}
    key = conf.get("apikey") or conf.get("default", {}).get("api_key")  # runpodctl vs flash login layout
    if not key:
        raise SystemExit("no RunPod key: run `flash login` once (or set RUNPOD_API_KEY)")
    return key


def _req(method, path, body=None):
    req = urllib.request.Request(f"{API}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {_key()}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def on_power():
    """True when the Mac is plugged in (caffeinate -s only keeps it awake on power)."""
    try:
        return "AC Power" in subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
    except Exception:  # noqa: BLE001  (not a Mac)
        return True


def best_case(n_clips):
    """Estimated batch cost on the cheapest card RunPod lists, in stock or not: the price worth waiting for."""
    return options(n_clips, in_stock=False)[0]


def _show(ranked, n, log):
    log(f"GPUs in stock for {n} clips, cheapest batch first:")
    for o in ranked[:10]:
        log(f"  ${o['cost']:.2f}  {o['cloud'].lower():9} {o['gpu'].replace('NVIDIA ', ''):34} ${o['price']}/h  "
            f"{o['sec']}s/clip{'' if o['measured'] else ' (guess)'}  stock {o['stock']}")


def _rent(body, tiers, log):
    for cloud, gpus in tiers:
        try:
            pod = _req("POST", "/pods", {**body, "cloudType": cloud, "gpuTypeIds": gpus, "gpuTypePriority": "custom"})
            log(f"rented {cloud.lower()} {' / '.join(x.replace('NVIDIA ', '') for x in gpus)} at ${pod.get('costPerHr')}/h")
            return pod
        except urllib.error.HTTPError as e:
            log(f"no {cloud.lower()} {' / '.join(x.replace('NVIDIA ', '') for x in gpus)} free "
                f"({e.code}: {e.read()[:150].decode(errors='replace').strip()})")
    return None


def run_job(cfg, plans, repo_url, dest, log=print, tiers=None, extra=None, collect=box.fetch,
            wait_hours=0, max_cost=None, exclude=(), only=()):
    """Rent the cheapest card in stock (or try `tiers`, [(cloud, [gpu ids])], in order), run the batch.
    wait_hours/max_cost: until the deadline, only rent a card whose estimated batch cost is <= max_cost,
    checking every 2 min (checks and refused rentals are free); after it, rent the cheapest in stock.
    extra: fields merged into the pod request (env merges into env); collect(base, slugs, dest, log)."""
    g = cfg["gpu"]
    token = secrets.token_urlsafe(16)
    start = ("apt-get update -qq && apt-get install -y -qq git >/dev/null; "
             "rm -rf /workspace/repo && git clone --depth 1 \"$GE_REPO\" /workspace/repo && "
             "bash /workspace/repo/pipeline/worker/job.sh")
    body = {
        "name": f"ge-{plans[0]['slug']}-x{len(plans)}"[:60],
        "imageName": g["image"],
        "gpuCount": 1,
        "allowedCudaVersions": ["13.0"],  # LTX's torch needs a CUDA 13 driver; older hosts fall back to CPU
        "minRAMPerGPU": 48,  # LTX's CPU offload (24 GB cards) keeps ~36 GB of weights in RAM
        "containerDiskInGb": 40,
        "volumeInGb": g["disk_gb"],
        "volumeMountPath": "/workspace",
        "ports": ["8080/http"],
        "env": {"OUT_TOKEN": token, "GE_REPO": repo_url, "KEEP_MIN": "40",
                "MAX_MIN": str(g["max_runtime_minutes"] + 20),
                "HF_TOKEN": "{{ RUNPOD_SECRET_hf_token }}",
                "PLANS_B64": box.pack_plans(plans)},
        "dockerStartCmd": ["bash", "-c", start],
    }
    extra = dict(extra or {})
    body["env"].update(extra.pop("env", {}))
    body.update(extra)
    if tiers is not None:
        pod = _rent(body, tiers, log)
    else:
        n = sum(len(p["shots"]) for p in plans)
        deadline, pod, quiet, waited = time.time() + wait_hours * 3600, None, log, False
        while pod is None:
            within = time.time() < deadline
            try:  # with `only`, try those cards even when RunPod's stock flag says none (a try is free)
                ranked = options(n, in_stock=not only)
            except Exception as e:  # noqa: BLE001  (network blip while waiting overnight)
                ranked = []
                quiet(f"stock check failed: {e}")
            ranked = [o for o in ranked if not any(x.lower() in o["gpu"].lower() for x in exclude)]
            if only:
                ranked = [o for o in ranked if any(c.upper() == o["cloud"] and g.lower() in o["gpu"].lower()
                                                   for c, g in only)]
            pick = [o for o in ranked if not (within and max_cost is not None) or o["cost"] <= max_cost]
            if wait_hours and not on_power():
                pick = []  # renting on battery: the laptop may sleep mid-render and lose the videos
                if not waited:
                    log("on battery: will only rent while the Mac is plugged in")
            if pick and not waited:
                _show(pick, n, log)
            pod = _rent(body, [(o["cloud"], [o["gpu"]]) for o in pick], quiet if waited else log)
            if pod is None:
                if not within:
                    raise SystemExit("no allowed GPU free; try again later (python3 -m ge.availability)")
                if not waited:
                    allowed = " / ".join(f"{c.lower()} {g}" for c, g in only) if only else f"a card at <= ${max_cost:.2f}"
                    log(f"waiting for {allowed} (until {time.strftime('%a %H:%M', time.localtime(deadline))}); "
                        "checking every 2 min")
                quiet, waited = (lambda m: None), True  # only report the round that rents
                time.sleep(120)
    t_rent = time.time()
    pid = pod["id"]
    base = f"https://{pid}-8080.proxy.runpod.net/{token}"
    log(f"pod {pid} ({pod.get('machine', {}).get('gpuDisplayName', 'GPU')}) - status: {base}/status.log")
    try:
        try:
            slugs = box.watch(base, time.time() + g["max_runtime_minutes"] * 60, log)
        except Exception:
            # keep the evidence: the pod is deleted right after this
            for name in ("job.log", "train.log"):
                try:
                    box.download(f"{base}/{name}", f"{dest}/{name}", 30)
                    log(f"saved {dest}/{name}")
                except Exception:  # noqa: BLE001
                    pass
            raise
        return collect(base, slugs, dest, log), {"dph_total": pod.get("costPerHr"),
                                                 "hours": (time.time() - t_rent) / 3600}
    finally:
        try:
            _req("DELETE", f"/pods/{pid}")
            log(f"deleted pod {pid}")
        except Exception as e:  # noqa: BLE001
            log(f"WARNING: could not delete pod {pid}: {e} (it removes itself after KEEP_MIN)")
