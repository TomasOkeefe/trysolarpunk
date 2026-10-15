"""Log RunPod stock for the GPUs we rent, to learn when community cloud has capacity.

  python -m ge.availability            # print now
  python -m ge.availability --log      # append one line per GPU to availability.jsonl (run by launchd every 30 min)
  python -m ge.availability --summary  # stock by hour of day (New York time)
"""
import datetime as dt
import json
import pathlib
import sys
import urllib.request
from zoneinfo import ZoneInfo

from ge import box, runpod  # noqa: F401  (box installs the User-Agent RunPod's Cloudflare wants)

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOG = ROOT / "availability.jsonl"
GPUS = list(runpod.SEC_PER_CLIP)  # every card the pipeline can rent
RANK = {"High": 3, "Medium": 2, "Low": 1}


def stock():
    q = "query { %s }" % " ".join(
        f'g{i}: gpuTypes(input:{{id:"{g}"}}) {{ id '
        f'c: lowestPrice(input:{{gpuCount:1, secureCloud:false}}) {{ stockStatus uninterruptablePrice }} '
        f's: lowestPrice(input:{{gpuCount:1, secureCloud:true}}) {{ stockStatus uninterruptablePrice }} }}'
        for i, g in enumerate(GPUS))
    req = urllib.request.Request("https://api.runpod.io/graphql", data=json.dumps({"query": q}).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {runpod._key()}"})
    data = json.loads(urllib.request.urlopen(req, timeout=60).read())["data"]
    return [{"gpu": v[0]["id"], "community": v[0]["c"]["stockStatus"], "secure": v[0]["s"]["stockStatus"],
             "c_price": v[0]["c"]["uninterruptablePrice"]} for v in data.values() if v]


if __name__ == "__main__":
    now = dt.datetime.now(dt.timezone.utc)
    rows = stock() if "--summary" not in sys.argv else []
    if "--log" in sys.argv:
        with open(LOG, "a") as f:
            for r in rows:
                f.write(json.dumps({"t": now.isoformat(timespec="minutes"), **r}) + "\n")
    elif "--summary" in sys.argv:
        hours = {}
        for l in LOG.read_text().splitlines():
            r = json.loads(l)
            h = dt.datetime.fromisoformat(r["t"]).astimezone(ZoneInfo("America/New_York")).hour
            hours.setdefault((r["gpu"], h), []).append(RANK.get(r["community"], 0))
        for g in GPUS:
            cells = [f"{sum(v) / len(v):.1f}" if (v := hours.get((g, h))) else " - " for h in range(24)]
            print(f"{g.replace('NVIDIA ', '')[:18]:18} " + " ".join(cells))
        print("community stock by NY hour 0-23 (3 High, 2 Medium, 1 Low, 0 none)")
    else:
        for r in rows:
            print(f"{r['gpu']:28} community {r['community']}  secure {r['secure']}  ${r['c_price']}")
