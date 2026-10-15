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


def expand(plan, characters):
    """Replace {name} in shot prompts with the character's fixed description."""
    for s in plan["shots"]:
        p = s["prompt"]
        for name in re.findall(r"\{(\w+)\}", p):
            assert name in characters, f"unknown character {{{name}}}"
            p = p.replace("{" + name + "}", characters[name])
        s["prompt"] = p[:1].upper() + p[1:]
    return plan


def validate(plan, shots):
    assert re.fullmatch(r"[a-z0-9-]{3,60}", plan["slug"]), "bad slug"
    dt.date.fromisoformat(plan["date"])
    assert plan["product"] in PRODUCTS, f"product must be one of {PRODUCTS}"
    assert len(plan["hook_text"].split()) <= 7, "hook_text max 7 words"
    assert "[Verse]" in plan["song"]["lyrics"] and "[Chorus]" in plan["song"]["lyrics"]
    assert plan["song"]["title"] and plan["song"]["style"]
    assert len(plan["shots"]) == shots, f"need {shots} shots"
    assert all(s["prompt"].strip() for s in plan["shots"]), "empty shot prompt"
    assert sum(1 for s in plan["shots"] if s.get("product_image")) == 1, "need exactly one product shot"
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
            validate(expand(plan, cfg.get("characters", {})), cfg["video"]["shots"])
            slugs.append(plan["slug"])
            print(f"ok  {f}")
        assert len(set(slugs)) == len(slugs), "duplicate slugs"
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
