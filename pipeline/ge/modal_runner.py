"""Run a batch on Modal (see modal_app.py) with the same interface as runpod.run_job.

The GPU job runs detached in Modal's cloud, so it keeps going if this Mac sleeps; this side only
watches the STAGE file on the work volume and downloads the results. If the watcher dies, collect
later with `python3 run.py --collect` (the call id is kept in videos/modal_call.json).
"""
import json
import pathlib
import time
import uuid

GPU_PER_HOUR = 1.95  # L40S on Modal (Oct 2026); A100-80GB fallback is 2.50
STATE = pathlib.Path(__file__).resolve().parents[2] / "videos" / "modal_call.json"


def _read(work, path):
    return b"".join(work.read_file(path))


def run_job(cfg, plans, dest, log=print, extra_env=None):
    import modal
    from ge import box
    import modal_app
    run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    with modal.enable_output():
        with modal_app.app.run(detach=True):
            call = modal_app.render.spawn(run_id, box.pack_plans(plans), extra_env)
    STATE.write_text(json.dumps({"run_id": run_id, "call_id": call.object_id, "slugs": [p["slug"] for p in plans],
                                 "started": time.time()}))
    log(f"modal run {run_id} (call {call.object_id}) started")
    return watch_and_collect(run_id, call.object_id, dest, log, time.time(), cfg["gpu"]["max_runtime_minutes"])


def watch_and_collect(run_id, call_id, dest, log, started, max_minutes=240):
    import modal
    from modal_app import work
    call = modal.FunctionCall.from_id(call_id)
    out = f"runs/{run_id}/out/out"
    last, beat, tick = None, time.time(), time.time()
    done = None
    while done is None:
        try:
            done = call.get(timeout=60)
        except TimeoutError:
            pass
        now = time.time()
        if now - tick > 180:
            log(f"this computer was asleep for {(now - tick) / 60:.0f} min; the Modal job kept running")
        tick = now
        try:
            stage = _read(work, f"{out}/STAGE").decode().strip()
        except Exception:  # noqa: BLE001  (not written yet)
            stage = "starting"
        if stage != last:
            log(f"stage: {stage}")
            last, beat = stage, now
        elif now - beat > 300:
            log(f"still: {stage}")
            beat = now
        if now - started > (max_minutes + 30) * 60:
            call.cancel()
            raise TimeoutError("Modal job exceeded max_runtime_minutes; cancelled")
    hours = (time.time() - started) / 3600
    got = []
    dest = pathlib.Path(dest)
    (dest / "raw").mkdir(parents=True, exist_ok=True)
    for s in done:
        try:
            (dest / f"{s}.mp4").write_bytes(_read(work, f"{out}/{s}/final.mp4"))
            (dest / f"{s}.json").write_bytes(_read(work, f"{out}/{s}/plan.json"))
            got.append(s)
        except Exception as e:  # noqa: BLE001
            log(f"WARNING: could not download {s}: {e}")
            continue
        try:
            (dest / "raw" / f"{s}.tar").write_bytes(_read(work, f"{out}/{s}/raw.tar"))
        except Exception:  # noqa: BLE001
            pass
    try:
        (dest / "job.log").write_bytes(_read(work, f"{out}/job.log"))
    except Exception:  # noqa: BLE001
        pass
    STATE.unlink(missing_ok=True)
    return got, {"dph_total": GPU_PER_HOUR, "hours": hours, "provider": "modal"}
