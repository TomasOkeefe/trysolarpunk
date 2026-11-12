"""Draw first frames for shots with the image-editing model on Modal (modal_app.first_frames).

  python3 first_frames.py --fetch                      # one-time: download the model (CPU, cheap)
  python3 first_frames.py jobs.json [--modes fast,full]

jobs.json: [{"name", "refs": ["moss/front.jpg", ...] (under assets/), "prompt", "seed"}].
Frames land in assets/moss/ff/<name>_<mode>.png, ready to use as a shot's "image".
"""
import argparse
import json
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parent

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="?")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--modes", default="fast")
    a = ap.parse_args()
    import modal
    import modal_app
    from ge import modal_runner
    with modal.enable_output():
        with modal_app.app.run():
            if a.fetch:
                print(modal_app.fetch_edit_model.remote())
            else:
                jobs = json.loads(pathlib.Path(a.jobs).read_text())
                run_id = time.strftime("%Y%m%d-%H%M%S")
                t = time.time()
                done = modal_app.first_frames.remote(run_id, jobs, a.modes.split(","))
                dest = ROOT / "assets" / "moss" / "ff"
                dest.mkdir(parents=True, exist_ok=True)
                for p in done:
                    (dest / pathlib.Path(p).name).write_bytes(modal_runner._read(modal_app.work, p))
                print(f"{len(done)} frames in {dest}, {(time.time() - t) / 60:.0f} min")
