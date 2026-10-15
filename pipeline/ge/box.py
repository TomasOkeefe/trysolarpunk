"""Talk to the GPU box: pack the plans for it, watch its progress, fetch the finished videos."""
import base64
import concurrent.futures
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


_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _get(url, timeout=20):
    """GET with a hard deadline. urlopen's timeout is per socket read, so a proxy that trickles
    bytes can hang it for good (it froze the stall watchdog on 2026-10-15)."""
    fut = _pool.submit(lambda: urllib.request.urlopen(url, timeout=timeout).read().decode())
    return fut.result(timeout=timeout * 2)


STALL_MINUTES = 20  # no stage change for this long (each finished clip is a change) means the box is stuck


def watch(base, deadline, log):
    """Poll the box's STAGE file until DONE. Returns the list of finished slugs.
    base is the box's output URL, or a function returning it (None until the box has an address).
    Raises on failure, on a stall and on the deadline, so the caller always exits and cleans up."""
    last, changed, get_base = None, time.time(), base if callable(base) else (lambda: base)
    while time.time() < deadline:
        time.sleep(30)
        if time.time() - changed > STALL_MINUTES * 60:
            raise TimeoutError(f"stalled: stage '{last}' unchanged for {STALL_MINUTES} min")
        url = get_base()
        if not url:
            continue
        try:
            stage = _get(f"{url}/STAGE", timeout=10).strip()
        except Exception:
            continue  # box still booting
        if stage != last:
            log(f"stage: {stage}")
            last, changed = stage, time.time()
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
            continue
        try:  # clips + song + lyric timings, so a re-edit (captions, cuts) runs locally for free
            os.makedirs(f"{dest}/raw", exist_ok=True)
            urllib.request.urlretrieve(f"{base}/{s}/raw.tar", f"{dest}/raw/{s}.tar")
        except Exception as e:  # noqa: BLE001
            log(f"WARNING: no raw clips for {s}: {e}")
    try:
        urllib.request.urlretrieve(f"{base}/job.log", f"{dest}/job.log")
    except Exception:  # noqa: BLE001
        pass
    return got
