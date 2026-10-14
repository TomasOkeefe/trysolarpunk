"""Rent a GPU pod on RunPod, run worker/job.sh on it, fetch the video, then delete the pod.

REST API: https://rest.runpod.io/v1  (env RUNPOD_API_KEY)
The pod reads HF_TOKEN from the RunPod secret `hf_token`, so the token never passes through here.
Every exit path deletes the pod, and the pod deletes itself KEEP_MIN minutes after finishing.
"""
import base64
import json
import os
import secrets
import time
import urllib.request

API = "https://rest.runpod.io/v1"
GPU_PREFERENCE = ["NVIDIA L40S", "NVIDIA RTX 6000 Ada Generation", "NVIDIA RTX A6000", "NVIDIA A40"]


def _req(method, path, body=None):
    req = urllib.request.Request(f"{API}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {os.environ['RUNPOD_API_KEY']}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def run_job(cfg, plan, repo_url, log=print):
    g = cfg["gpu"]
    token = secrets.token_urlsafe(16)
    start = ("apt-get update -qq && apt-get install -y -qq git >/dev/null; "
             "rm -rf /workspace/repo && git clone --depth 1 \"$GE_REPO\" /workspace/repo && "
             "bash /workspace/repo/pipeline/worker/job.sh")
    body = {
        "name": f"ge-{plan['slug']}"[:60],
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
                "PLAN_B64": base64.b64encode(json.dumps(plan).encode()).decode()},
        "dockerStartCmd": ["bash", "-c", start],
    }
    pod = _req("POST", "/pods", body)
    pid = pod["id"]
    base = f"https://{pid}-8080.proxy.runpod.net/{token}"
    log(f"pod {pid} ({pod.get('machine', {}).get('gpuDisplayName', 'GPU')}) - status: {base}/status.log")
    deadline = time.time() + g["max_runtime_minutes"] * 60
    try:
        while time.time() < deadline:
            time.sleep(30)
            try:
                stage = urllib.request.urlopen(f"{base}/STAGE", timeout=10).read().decode().strip()
            except Exception:
                continue  # pod still booting
            log(f"stage: {stage}")
            if stage.startswith("FAILED"):
                tail = urllib.request.urlopen(f"{base}/job.log", timeout=20).read().decode()[-3000:]
                raise RuntimeError(f"{stage}\n{tail}")
            if stage == "DONE":
                os.makedirs("out", exist_ok=True)
                for name in ("final.mp4", "song.flac", "plan.json"):
                    urllib.request.urlretrieve(f"{base}/{name}", f"out/{name}")
                return "out/final.mp4", {"gpu_name": pod.get("machine", {}).get("gpuDisplayName"),
                                         "dph_total": pod.get("costPerHr")}
        raise TimeoutError("GPU job exceeded max_runtime_minutes")
    finally:
        try:
            _req("DELETE", f"/pods/{pid}")
            log(f"deleted pod {pid}")
        except Exception as e:  # noqa: BLE001
            log(f"WARNING: could not delete pod {pid}: {e} (it removes itself after KEEP_MIN)")
