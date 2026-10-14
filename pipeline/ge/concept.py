"""Write today's video plan (song + shot list + caption) with the Claude API.

The plan is plain JSON so a human (or Claude in chat) can also write one by hand:
see plans/ for examples. Output schema is validated before anything is spent on GPUs.
"""
import datetime as dt
import json
import os
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL = os.environ.get("GE_CONCEPT_MODEL", "claude-sonnet-5-5")

SCHEMA_HINT = {
    "slug": "kebab-case-unique-id",
    "product": "hibernator | eyelid | merch",
    "hook_text": "max 7 words, shown big for the first 3 s",
    "song": {
        "title": "short title",
        "style": "genre, instruments, vocal character, language English, tempo in BPM",
        "lyrics": "[Verse]\\n4 lines\\n\\n[Chorus]\\n4 lines",
    },
    "shots": [{"prompt": "one flowing paragraph, <=120 words", "product_image": False}],
    "endcard": {"line1": "max 6 words", "line2": "link in bio"},
    "caption": "TikTok caption, max 150 chars, no hashtags",
    "hashtags": ["#touchgrass", "..."],
}

RULES = """
Rules:
- Original lyrics only. Never quote or imitate a real song, artist, or band; never name one in the style.
- The song is short: exactly one [Verse] of 4 lines and one [Chorus] of 4 lines (about 45 s).
- Exactly {shots} shots. Each prompt is a single cinematic paragraph for a text-to-video model:
  start with the main action, then subject details, setting, camera move, light and colour.
  Solarpunk everyday life: gardens on rooftops, bikes, shared meals, sunlight, people looking up.
  No readable text, no logos, no phone screens showing apps, no real or famous people.
- Exactly one shot has "product_image": true. It shows the product: {visual}.
  Its prompt describes gentle motion around that object (a hand placing a phone in it, light shifting).
- Shot 1 must be a strong visual hook. The last shot should feel like a deep breath.
- The joke is on the feed, never on the viewer. No shaming, no doom.
- Caption: playful, under 150 characters, mention the product by name once.
- 4 to 6 hashtags, lowercase, relevant (touchgrass, digitalminimalism, solarpunk, screentime...).
Return ONLY the JSON object.
"""


def _history(n=14):
    f = ROOT / "history.jsonl"
    if not f.exists():
        return []
    lines = f.read_text().strip().splitlines()[-n:]
    return [json.loads(l) for l in lines if l.strip()]


def pick_product(cfg):
    hist = _history(len(cfg["products"]))
    recent = [h.get("product") for h in hist]
    weights = {"hibernator": 3, "eyelid": 2, "merch": 1}  # Hibernator is the hero product
    scored = sorted(cfg["products"], key=lambda p: (recent.count(p["id"]) / weights.get(p["id"], 1)))
    return scored[0]


def validate(plan, shots):
    assert re.fullmatch(r"[a-z0-9-]{3,60}", plan["slug"]), "bad slug"
    assert plan["product"] in ("hibernator", "eyelid", "merch")
    assert "[Verse]" in plan["song"]["lyrics"] and "[Chorus]" in plan["song"]["lyrics"]
    assert len(plan["shots"]) == shots, f"need {shots} shots"
    assert sum(1 for s in plan["shots"] if s.get("product_image")) == 1, "need exactly one product shot"
    assert len(plan["caption"]) <= 150
    return plan


def write_plan(cfg, date=None):
    import anthropic  # imported here so the rest of the pipeline works without it

    date = date or dt.date.today().isoformat()
    product = pick_product(cfg)
    recent = [f'{h.get("slug")} ({h.get("product")})' for h in _history()]
    shots = cfg["video"]["shots"]
    system = (f"You write short TikTok music videos for {cfg['brand']['name']}, "
              f"\"{cfg['brand']['tagline']}\". Voice: {cfg['brand']['voice']}")
    user = (f"Today is {date}. Write today's video selling: {product['name']} - {product['pitch']}\n"
            f"Recent videos to NOT repeat: {recent or 'none yet'}\n"
            f"JSON shape: {json.dumps(SCHEMA_HINT)}\n"
            + RULES.format(shots=shots, visual=product.get("visual", product["name"])))
    client = anthropic.Anthropic()
    for attempt in range(3):
        msg = client.messages.create(model=MODEL, max_tokens=3000, system=system,
                                     messages=[{"role": "user", "content": user}])
        text = msg.content[0].text
        text = text[text.find("{"): text.rfind("}") + 1]
        try:
            plan = validate(json.loads(text), shots)
            plan["product"] = product["id"]
            plan["date"] = date
            return plan
        except Exception as e:  # ask again with the error
            user += f"\n\nYour last answer was invalid ({e}). Return valid JSON only."
    raise RuntimeError("could not get a valid plan")


if __name__ == "__main__":
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    print(json.dumps(write_plan(cfg), indent=2))
