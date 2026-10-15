"""Rent a GPU pod on RunPod, run worker/job.sh on it for a batch of plans, fetch the videos, delete the pod.

REST API: https://rest.runpod.io/v1  (key: env RUNPOD_API_KEY, else ~/.runpod/config.toml from `flash login`)
The pod reads HF_TOKEN from the RunPod secret `hf_token`, so the token never passes through here.
Every exit path deletes the pod, and the pod deletes itself KEEP_MIN minutes after finishing.
"""
import json
import os
import pathlib
import secrets
import time
import urllib.error
import urllib.request

from ge import box

API = "https://rest.runpod.io/v1"
# Cheapest per clip first (Oct 2026 prices). Each tier is one create attempt; the first with a free
# CUDA 13 host wins. 48 GB cards render a clip in ~50 s; 24 GB cards need LTX's CPU offload (job.sh
# switches it on) and take ~2 min a clip (probe on a 3090, 2026-10-15), so they rank by cost per clip.
TIERS = [
    ("COMMUNITY", ["NVIDIA RTX A6000", "NVIDIA A40"]),                    # $0.33-0.35/h, ~0.5 cent a clip
    ("COMMUNITY", ["NVIDIA GeForce RTX 3090"]),                           # $0.22/h,      ~0.7 cent a clip
    ("SECURE", ["NVIDIA RTX A6000", "NVIDIA A40"]),                       # $0.59/h,      ~0.8 cent a clip
    ("COMMUNITY", ["NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L40S"]),  # $0.69-0.79
    ("SECURE", ["NVIDIA L40", "NVIDIA RTX 6000 Ada Generation", "NVIDIA L40S"]),     # $0.82-1.09
]


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


def _gpu_name(pid):
    """The GPU is only known once the pod is placed, so ask after the fact."""
    try:
        p = _req("GET", f"/pods/{pid}")
    except Exception:  # noqa: BLE001
        return None
    return (p.get("machine") or {}).get("gpuDisplayName") or (p.get("gpu") or {}).get("displayName") or p.get("gpuTypeId")


def run_job(cfg, plans, repo_url, dest, log=print, tiers=TIERS, extra=None, collect=box.fetch):
    """extra: fields merged into the pod request (env merges into env); collect(base, slugs, dest, log)."""
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
                "HF_TOKEN": "{{ RUNPOD_SECRET_hf_token }}",
                "PLANS_B64": box.pack_plans(plans)},
        "dockerStartCmd": ["bash", "-c", start],
    }
    extra = dict(extra or {})
    body["env"].update(extra.pop("env", {}))
    body.update(extra)
    pod = None
    for cloud, gpus in tiers:
        try:
            pod = _req("POST", "/pods", {**body, "cloudType": cloud, "gpuTypeIds": gpus, "gpuTypePriority": "custom"})
            log(f"rented {cloud.lower()} {' / '.join(x.replace('NVIDIA ', '') for x in gpus)} at ${pod.get('costPerHr')}/h")
            break
        except urllib.error.HTTPError as e:
            log(f"no {cloud.lower()} {' / '.join(x.replace('NVIDIA ', '') for x in gpus)} free "
                f"({e.code}: {e.read()[:150].decode(errors='replace').strip()})")
    if pod is None:
        raise SystemExit("no GPU available in any tier; try again later")
    pid = pod["id"]
    base = f"https://{pid}-8080.proxy.runpod.net/{token}"
    log(f"pod {pid} ({pod.get('machine', {}).get('gpuDisplayName', 'GPU')}) - status: {base}/status.log")
    try:
        slugs = box.watch(base, time.time() + g["max_runtime_minutes"] * 60, log)
        return collect(base, slugs, dest, log), {"gpu_name": _gpu_name(pid), "dph_total": pod.get("costPerHr")}
    finally:
        try:
            _req("DELETE", f"/pods/{pid}")
            log(f"deleted pod {pid}")
        except Exception as e:  # noqa: BLE001
            log(f"WARNING: could not delete pod {pid}: {e} (it removes itself after KEEP_MIN)")
