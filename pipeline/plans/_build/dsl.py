"""Tiny helper for writing plans as Python: S(line, prompt, ...) rows -> plans/<date>-<slug>.json."""
import json
import pathlib

OUT = pathlib.Path(__file__).resolve().parents[1]


def S(line, prompt, sing=False, product=False, frame=None, view=None, props=None):
    s = {"prompt": prompt}
    if line is not None:
        s["line"] = line
    if sing:
        s["sing"] = True
    if product:
        s["product_image"] = True
    if frame is not None:
        s["frame"] = frame
    if view:
        s["view"] = view
    if props is not None:
        s["props"] = props
    return s


def save(plan):
    assert len(plan["shots"]) == 32, len(plan["shots"])
    p = OUT / f"{plan['date']}-{plan['slug']}.json"
    p.write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n")
    print("wrote", p.name)
