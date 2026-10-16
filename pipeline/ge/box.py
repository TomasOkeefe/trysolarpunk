"""Talk to the GPU box: pack the plans for it, watch its progress, fetch the finished videos."""
import base64
import gzip
import json
import os
import threading
import time
import urllib.request

# RunPod sits behind Cloudflare, which rejects Python's default User-Agent (error 1010).
# This opener also covers urlretrieve and the REST calls in runpod.py.
_opener = urllib.request.build_opener()
_opener.addheaders = [("User-Agent", "trysolarpunk-pipeline/1.0")]
urllib.request.install_opener(_opener)


def pack_plans(plans):
    return base64.b64encode(gzip.compress(json.dumps(plans).encode())).decode()


def _deadline(fn, timeout):
    """Run fn with a hard deadline. urlopen's timeout is per socket read, so a proxy that trickles
    bytes can hang it for good (it froze the watchdog twice on 2026-10-15). Daemon thread, so a
    hung read can't keep the process from exiting either."""
    box = {}

    def work():
        try:
            box["v"] = fn()
        except BaseException as e:  # noqa: BLE001
            box["e"] = e
    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError(f"no answer within {timeout}s")
    if "e" in box:
        raise box["e"]
    return box.get("v")


def _get(url, timeout=20):
    return _deadline(lambda: urllib.request.urlopen(url, timeout=timeout).read().decode(), timeout * 2)


def download(url, path, timeout=900):
    """Save url to path, giving up after timeout seconds in total."""
    def go():
        with urllib.request.urlopen(url, timeout=60) as r, open(path, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    _deadline(go, timeout)


STALL_MINUTES = 20  # no stage change for this long (each finished clip is a change) means the box is stuck
BOOT_MINUTES = 10   # never answered at all: the container didn't start (a normal boot takes 1-3 min)
DARK_MINUTES = 6    # answered before, silent since: the host dropped off the network


def watch(base, deadline, log):
    """Poll the box's STAGE file until DONE. Returns the list of finished slugs.
    base is the box's output URL, or a function returning it (None until the box has an address).
    Raises on failure, stall, dark host, no boot and the deadline, so the caller always cleans up.
    Logs a heartbeat every 5 min and every minute the box is unreachable."""
    start = changed = seen = time.time()
    last, ever, get_base, beat = None, False, base if callable(base) else (lambda: base), time.time()
    tick = time.time()
    while time.time() < deadline:
        time.sleep(30)
        now = time.time()
        if now - tick > 180:  # this Mac slept: the box kept going, so don't count the gap against it
            gap = now - tick
            log(f"this computer was asleep for {gap / 60:.0f} min; resetting the watchdog timers")
            start, changed, seen, beat, deadline = now, now, now, now, deadline + gap
        tick = now
        if now - changed > STALL_MINUTES * 60:
            raise TimeoutError(f"stalled: stage '{last}' unchanged for {STALL_MINUTES} min")
        url = get_base()
        try:
            stage = _get(f"{url}/STAGE", timeout=10).strip() if url else None
        except Exception:  # noqa: BLE001
            stage = None
        if stage is None:
            if not ever and now - start > BOOT_MINUTES * 60:
                raise TimeoutError(f"box never answered in {BOOT_MINUTES} min (container didn't start)")
            if ever and now - seen > DARK_MINUTES * 60:
                raise TimeoutError(f"box unreachable for {DARK_MINUTES} min (host dropped off)")
            if ever and now - seen > 90:
                log(f"unreachable for {(now - seen) / 60:.0f} min (stage was '{last}')")
            elif not ever and now - beat > 120:
                log(f"booting ({(now - start) / 60:.0f} min)")
                beat = now
            continue
        ever, seen = True, now
        if stage != last:
            log(f"stage: {stage}")
            last, changed, beat = stage, now, now
        elif now - beat > 300:
            log(f"still: {stage}")
            beat = now
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
            download(f"{base}/{s}/final.mp4", f"{dest}/{s}.mp4")
            download(f"{base}/{s}/plan.json", f"{dest}/{s}.json", 60)
            got.append(s)
        except Exception as e:  # noqa: BLE001
            log(f"WARNING: could not download {s}: {e}")
            continue
        try:  # clips + song + lyric timings, so a re-edit (captions, cuts) runs locally for free
            os.makedirs(f"{dest}/raw", exist_ok=True)
            download(f"{base}/{s}/raw.tar", f"{dest}/raw/{s}.tar")
        except Exception as e:  # noqa: BLE001
            log(f"WARNING: no raw clips for {s}: {e}")
    try:
        download(f"{base}/job.log", f"{dest}/job.log", 60)
    except Exception:  # noqa: BLE001
        pass
    return got
