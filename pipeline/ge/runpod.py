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
import urllib.request

from ge import box

API = "https://rest.runpod.io/v1"
GPU_PREFERENCE = ["NVIDIA L40S", "NVIDIA RTX 6000 Ada Generation", "NVIDIA RTX A6000", "NVIDIA A40"]


def _key():
    if os.environ.get("RUNPOD_API_KEY"):
        return os.environ["RUNPOD_API_KEY"]
    import tomllib
    cfg = pathlib.Path.home() / ".runpod" / "config.toml"
    key = tomllib.loads(cfg.read_text()).get("apikey") if cfg.exists() else None
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


def run_job(cfg, plans, repo_url, dest, log=print):
    g = cfg["gpu"]
    token = secrets.token_urlsafe(16)
    start = ("apt-get update -qq && apt-get install -y -qq git >/dev/null; "
             "rm -rf /workspace/repo && git clone --depth 1 \"$GE_REPO\" /workspace/repo && "
             "bash /workspace/repo/pipeline/worker/job.sh")
    body = {
        "name": f"ge-{plans[0]['slug']}-x{len(plans)}"[:60],
        "imageName": g["image"],
        "gpuTypeIds": GPU_PREFERENCE,
        "gpuCount": 1,
        "cloudType": g.get("cloud", "COMMUNITY"),
        "containerDiskInGb": 40,
        "volumeInGb": g["disk_gb"],
        "volumeMountPath": "/workspace",
        "ports": ["8080/http"],
        "env": {"OUT_TOKEN": token, "GE_REPO": repo_url, "KEEP_MIN": "40",
                "HF_TOKEN": "{{ RUNPOD_SECRET_hf_token }}",
                "PLANS_B64": box.pack_plans(plans)},
        "dockerStartCmd": ["bash", "-c", start],
    }
    pod = _req("POST", "/pods", body)
    pid = pod["id"]
    base = f"https://{pid}-8080.proxy.runpod.net/{token}"
    log(f"pod {pid} ({pod.get('machine', {}).get('gpuDisplayName', 'GPU')}) - status: {base}/status.log")
    try:
        slugs = box.watch(base, time.time() + g["max_runtime_minutes"] * 60, log)
        return box.fetch(base, slugs, dest, log), {"gpu_name": pod.get("machine", {}).get("gpuDisplayName"),
                                             "dph_total": pod.get("costPerHr")}
    finally:
        try:
            _req("DELETE", f"/pods/{pid}")
            log(f"deleted pod {pid}")
        except Exception as e:  # noqa: BLE001
            log(f"WARNING: could not delete pod {pid}: {e} (it removes itself after KEEP_MIN)")
