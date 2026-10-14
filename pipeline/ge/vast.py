"""Rent a GPU on Vast.ai, run worker/job.sh on it, fetch the video, then destroy it.

Uses the official `vastai` CLI (pip install vastai) with VAST_API_KEY from the environment.
Every exit path destroys the instance, and the box also self-destructs (see job.sh), so a
crashed orchestrator can't leave a GPU billing overnight.
"""
import base64
import json
import os
import secrets
import shlex
import subprocess
import time
import urllib.request


def _vast(*args):
    cmd = ["vastai", *args, "--api-key", os.environ["VAST_API_KEY"], "--raw"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"vastai {args[0]} failed: {r.stderr.strip() or r.stdout.strip()}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return r.stdout


def cheapest_offer(cfg):
    g = cfg["gpu"]
    q = (f"gpu_ram>={g['min_vram_gb']} num_gpus=1 reliability>{g['min_reliability']} "
         f"dph<{g['max_dollars_per_hour']} disk_space>={g['disk_gb']} cpu_ram>=64 "
         f"inet_down>=500 cuda_vers>=12.8 rentable=true verified=true")
    offers = _vast("search", "offers", q, "-o", "dph")
    if not offers:
        raise RuntimeError("no GPU offers match config.gpu right now")
    return offers[0]


def run_job(cfg, plan, repo_url, log=print):
    offer = cheapest_offer(cfg)
    log(f"renting offer {offer['id']}: {offer.get('gpu_name')} at ${offer.get('dph_total', 0):.3f}/h")
    token = secrets.token_urlsafe(16)
    plan_b64 = base64.b64encode(json.dumps(plan).encode()).decode()
    env = (f"-p 8080:8080 -e OUT_TOKEN={token} -e GE_REPO={repo_url} -e KEEP_MIN=40 "
           f"-e HF_TOKEN={os.environ['HF_TOKEN']} -e PLAN_B64={plan_b64}")
    onstart = ("mkdir -p /workspace && git clone --depth 1 \"$GE_REPO\" /workspace/repo && "
               "nohup bash /workspace/repo/pipeline/worker/job.sh >/workspace/onstart.log 2>&1 &")
    res = _vast("create", "instance", str(offer["id"]), "--image", cfg["gpu"]["image"],
                "--disk", str(cfg["gpu"]["disk_gb"]), "--env", env, "--onstart-cmd", onstart, "--direct")
    iid = res["new_contract"]
    deadline = time.time() + cfg["gpu"]["max_runtime_minutes"] * 60
    base = None
    try:
        while time.time() < deadline:
            time.sleep(30)
            inst = _vast("show", "instance", str(iid))
            if not base:
                ports = (inst.get("ports") or {}).get("8080/tcp")
                if inst.get("public_ipaddr") and ports:
                    base = f"http://{inst['public_ipaddr'].strip()}:{ports[0]['HostPort']}/{token}"
                    log(f"status: {base}/status.log")
                continue
            try:
                stage = urllib.request.urlopen(f"{base}/STAGE", timeout=10).read().decode().strip()
            except Exception:
                continue
            log(f"stage: {stage}")
            if stage.startswith("FAILED"):
                tail = urllib.request.urlopen(f"{base}/job.log", timeout=20).read().decode()[-3000:]
                raise RuntimeError(f"{stage}\n{tail}")
            if stage == "DONE":
                os.makedirs("out", exist_ok=True)
                for name in ("final.mp4", "song.flac", "plan.json"):
                    urllib.request.urlretrieve(f"{base}/{name}", f"out/{name}")
                return "out/final.mp4", offer
        raise TimeoutError("GPU job exceeded max_runtime_minutes")
    finally:
        try:
            _vast("destroy", "instance", str(iid))
            log(f"destroyed instance {iid}")
        except Exception as e:  # noqa: BLE001
            log(f"WARNING: could not destroy instance {iid}: {e} (it self-destructs after KEEP_MIN)")
