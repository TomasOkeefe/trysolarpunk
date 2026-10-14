"""GPU worker: write the song with YuE2.  usage: python gen_song.py plan.json out_dir [candidates]"""
import json
import pathlib
import sys

from yue2 import YuE2Pipeline

plan = json.loads(pathlib.Path(sys.argv[1]).read_text())
out = pathlib.Path(sys.argv[2])
candidates = int(sys.argv[3]) if len(sys.argv) > 3 else 1
seed0 = abs(hash(plan["slug"])) % 900000 + 100000

with YuE2Pipeline.from_pretrained("m-a-p/YuE2-3B", device="cuda") as pipe:
    for c in range(candidates):
        req = {"style": plan["song"]["style"], "lyrics": plan["song"]["lyrics"], "cot": "full", "seed": seed0 + c}
        song = pipe(**req)
        d = out / f"song_{c}"
        song.save_artifacts(str(d))
        print(f"candidate {c}: {d}/audio.flac truncated={song.truncated}", flush=True)
