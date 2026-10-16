"""Plan helpers. Claude (in the Claude Code session) writes the plans; this keeps them honest.

  python -m ge.concept next 7            # which product goes on which day, plus recent slugs to avoid
  python -m ge.concept check plans/*.json  # validate plans before any GPU money is spent

The writing rules live in .claude/skills/make-videos/SKILL.md; plans/ has examples.
"""
import datetime as dt
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRODUCTS = ("hibernator", "eyelid", "merch")


def history(n=14):
    f = ROOT / "history.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text().strip().splitlines()[-n:] if l.strip()]


def pick_products(cfg, n):
    recent = [h.get("product") for h in history(len(cfg["products"]))]
    weights = {"hibernator": 3, "eyelid": 2, "merch": 1}  # Hibernator is the hero product
    picks = []
    for _ in range(n):
        p = min(cfg["products"], key=lambda p: (recent + picks).count(p["id"]) / weights.get(p["id"], 1))
        picks.append(p["id"])
    by_id = {p["id"]: p for p in cfg["products"]}
    return [by_id[i] for i in picks]


def expand(plan, characters, loras=None):
    """Replace {name} in shot prompts with the character's fixed description. A character with a
    trained LoRA (config.yaml loras) gets its trigger word in front, and the plan lists the LoRA."""
    loras, used = loras or {}, {}
    for s in plan["shots"]:
        p = s["prompt"]
        for name in re.findall(r"\{(\w+)\}", p):
            assert name in characters, f"unknown character {{{name}}}"
            desc = characters[name]
            if name in loras:
                desc = f"{loras[name]['trigger']} {desc}"
                used[name] = loras[name]
            p = p.replace("{" + name + "}", desc)
        triggered = any(p.startswith(l["trigger"]) for l in loras.values())
        s["prompt"] = p if triggered else p[:1].upper() + p[1:]
    if used:
        plan["loras"] = [{"url": l["url"], "strength": l.get("strength", 1.0)} for l in used.values()]
    return plan


def validate(plan, shots):
    assert re.fullmatch(r"[a-z0-9-]{3,60}", plan["slug"]), "bad slug"
    dt.date.fromisoformat(plan["date"])
    assert plan["product"] in PRODUCTS, f"product must be one of {PRODUCTS}"
    assert len(plan["hook_text"].split()) <= 7, "hook_text max 7 words"
    assert "[Verse]" in plan["song"]["lyrics"] and "[Chorus]" in plan["song"]["lyrics"]
    sung = [l for l in plan["song"]["lyrics"].splitlines() if l.strip() and not l.strip().startswith("[")]
    # 8 lines sing in ~20-35 s once the intro is trimmed: too short for 9 shots
    assert len(sung) >= 14, f"song needs verse, chorus, verse, chorus (~16 lines), has {len(sung)}"
    assert plan["song"]["title"] and plan["song"]["style"]
    assert 12 <= len(plan["shots"]) <= 40, f"need 12-40 shots (default {shots})"
    assert all(s["prompt"].strip() for s in plan["shots"]), "empty shot prompt"
    assert sum(1 for s in plan["shots"] if s.get("product_image")) == 1, "need exactly one product shot"
    # line-locked cuts (ge.timeline): "line" is the 0-based sung line a shot starts on
    anchored = [(i, s["line"]) for i, s in enumerate(plan["shots"]) if s.get("line") is not None]
    assert all(isinstance(k, int) and 0 <= k < len(sung) for _, k in anchored), f"line must be 0..{len(sung) - 1}"
    ks = [k for _, k in anchored]
    assert ks == sorted(set(ks)), "shot lines must increase"
    assert all(k >= i // 3 for i, k in anchored), "too many shots before their line (each shot needs >= ~1 s)"
    singing = [s for s in plan["shots"] if s.get("sing")]
    assert all(s.get("line") is not None and not s.get("product_image") for s in singing), "a sing shot needs a line, not the product"
    assert len(singing) <= 6, "max 6 singing shots"
    assert sum("static" in s["prompt"].lower() for s in plan["shots"]) <= 3, "max 3 static shots: move the camera"
    assert plan["endcard"]["line1"]
    assert len(plan["caption"]) <= 150, "caption max 150 chars"
    assert 3 <= len(plan["hashtags"]) <= 6
    return plan


def main():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "next":
        n = int(rest[0]) if rest else 7
        start = dt.date.today() + dt.timedelta(days=1)
        for i, p in enumerate(pick_products(cfg, n)):
            print(f"{start + dt.timedelta(days=i)}  {p['id']:<10}  {p['pitch']}  | product shot: {p.get('visual')}")
        print("recent (don't repeat):", ", ".join(h["slug"] for h in history()) or "none")
        print(f"shots per video: {cfg['video']['shots']}")
    elif cmd == "check":
        slugs = []
        for f in rest:
            plan = json.loads(pathlib.Path(f).read_text())
            validate(expand(plan, cfg.get("characters", {}), cfg.get("loras")), cfg["video"]["shots"])
            slugs.append(plan["slug"])
            print(f"ok  {f}")
        assert len(set(slugs)) == len(slugs), "duplicate slugs"
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
