"""Talk to the GPU box: pack the plans for it, watch its progress, fetch the finished videos."""
import base64
import gzip
import json
import os
import time
import urllib.request

# RunPod sits behind Cloudflare, which rejects Python's default User-Agent (error 1010).
# This opener also covers urlretrieve and the REST calls in runpod.py.
_opener = urllib.request.build_opener()
_opener.addheaders = [("User-Agent", "trysolarpunk-pipeline/1.0")]
urllib.request.install_opener(_opener)


def pack_plans(plans):
    return base64.b64encode(gzip.compress(json.dumps(plans).encode())).decode()


def _get(url, timeout=20):
    return urllib.request.urlopen(url, timeout=timeout).read().decode()


def watch(base, deadline, log):
    """Poll the box's STAGE file until DONE. Returns the list of finished slugs.
    base is the box's output URL, or a function returning it (None until the box has an address)."""
    last, get_base = None, base if callable(base) else (lambda: base)
    while time.time() < deadline:
        time.sleep(30)
        url = get_base()
        if not url:
            continue
        try:
            stage = _get(f"{url}/STAGE", timeout=10).strip()
        except Exception:
            continue  # box still booting
        if stage != last:
            log(f"stage: {stage}")
            last = stage
        if stage.startswith("FAILED"):
            raise RuntimeError(f"{stage}\n{_get(f'{url}/job.log')[-3000:]}")
        if stage == "DONE":
            return _get(f"{url}/done.txt").split()
    raise TimeoutError("GPU job exceeded max_runtime_minutes")


def fetch(base, slugs, dest, log):
    """Download dest/<slug>.mp4 (+ the plan) for every finished video, and the box's job.log."""
    os.makedirs(dest, exist_ok=True)
    got = []
    for s in slugs:
        try:
            urllib.request.urlretrieve(f"{base}/{s}/final.mp4", f"{dest}/{s}.mp4")
            urllib.request.urlretrieve(f"{base}/{s}/plan.json", f"{dest}/{s}.json")
            got.append(s)
        except Exception as e:  # noqa: BLE001
            log(f"WARNING: could not download {s}: {e}")
    try:
        urllib.request.urlretrieve(f"{base}/job.log", f"{dest}/job.log")
    except Exception:  # noqa: BLE001
        pass
    return got
