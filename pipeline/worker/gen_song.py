"""GPU worker: write every song in a batch with YuE2, loading the model once.

usage: python gen_song.py batch_dir      (batch_dir/<slug>/plan.json in, batch_dir/<slug>/song.flac out)
"""
import json
import pathlib
import shutil
import sys
import zlib

from yue2 import YuE2Pipeline

batch = pathlib.Path(sys.argv[1])

import torch

todo = [d for d in sorted(p.parent for p in batch.glob("*/plan.json")) if not (d / "song.flac").exists()]
if not todo:  # songs already there (a re-render or a smoke test): don't load the model
    sys.exit(0)
# YuE2 plans for 24 GiB by default, which is more than a 24 GB card really has
vram = torch.cuda.get_device_properties(0).total_memory / 2**30
with YuE2Pipeline.from_pretrained("m-a-p/YuE2-3B", device="cuda", memory_budget_gib=min(24, int(vram) - 4)) as pipe:
    for d in todo:
        plan = json.loads((d / "plan.json").read_text())
        try:
            song = pipe(style=plan["song"]["style"], lyrics=plan["song"]["lyrics"], cot="full",
                        seed=plan["song"].get("seed") or zlib.crc32(plan["slug"].encode()) % 900000 + 100000)
            song.save_artifacts(str(d / "yue"))
            shutil.copy(d / "yue" / "audio.flac", d / "song.flac")
            print(f"{plan['slug']}: song ready, truncated={song.truncated}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"{plan['slug']}: song FAILED: {type(e).__name__}: {e}", flush=True)
