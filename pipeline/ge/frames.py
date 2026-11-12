"""First frames for character shots.

A LoRA never held Moss exactly; a clip that starts from a picture of him does (tests, 2026-11-11). So
before the batch renders, an image-editing model (modal_app.first_frames) draws the opening still of
every Moss shot from his master pictures (assets/moss/, made by moss_masters.py), and LTX animates
from it (worker/gen_clips.py: a shot's "image").

In a plan, a shot that names {moss} or {moss_back} gets a first frame automatically:
- "frame": the opening still in a sentence ("He stands at the kerb looking at his phone, a deep puddle
  ahead. Full body."). Without it the shot's own prompt is used, minus its camera sentences. Write one
  whenever the shot has a payoff (a splash, a bonk): the frame is the moment before it.
- "view": which master pictures to draw from: front (default), threeq, side, side_m (his other side),
  back (default for {moss_back}), face (default for close-ups).
- "frame": false opts a shot out (he then renders from text alone and will drift).
"""
import re
import zlib

# one master picture per shot: given two (front and three-quarter), the model sometimes drew two of him
VIEWS = {v: [v] for v in ("front", "threeq", "threeq_m", "side", "side_m", "back", "back3q", "face")}
HIM = "this clay character"
HIM_BACK = "this clay character, seen from behind with his back to the camera,"
ONE = "There is only one of him in the scene. "
# with other people in the shot the model sometimes gave them his glasses, mustache and beanie
OTHERS = "Everyone else keeps their own face, hair and clothes and looks nothing like him. "
# "a picture of", "a frame from" and "in the picture" made the model draw a wooden picture frame round the image
EDGE = "The scene fills the whole image from edge to edge, with no border."
KEEP = ("Keep him exactly as in the reference image: the same round head with warm peach skin, round black glasses, "
        "bushy brown mustache, rosy cheeks, moss-green rib-knit beanie with a yellow pom-pom, mustard-yellow raincoat "
        "with buttons and pockets, and green rubber boots. " + ONE)
KEEP_BACK = ("We see the back of his moss-green rib-knit beanie with its yellow pom-pom, the back of his mustard-yellow "
             "raincoat and his green rubber boots, exactly as in the reference image. His face is not visible. " + ONE)
# for close-ups: naming his boots and pockets makes the model draw him full length
KEEP_FACE = ("Keep him exactly as in the reference image: the same round head with warm peach skin, round black glasses, "
             "bushy brown mustache, rosy cheeks and moss-green rib-knit beanie with a yellow pom-pom, and the collar of his "
             "mustard-yellow raincoat. " + ONE)
CLOSE_LEAD = "A close-up, from the chest up, his head filling most of the image. "
LOOK = ("A still from a handmade claymation stop-motion film shot on a real miniature set: matte plasticine with a few soft "
        "thumbprints, soft diffused warm light, gentle natural colours, no glossy highlights. " + EDGE)
CLOSE = re.compile(r"^(an? )?(extreme )?close-up", re.I)
# anyone or any creature in a shot: it is not a "props" shot (config.yaml props_styles)
SOMEONE = re.compile(
    r"\b(man|woman|men|women|grandma|grandpa|baker|postman|sailor|neighbou?rs?|child(ren)?|kids?|boys?|girls?|people|"
    r"person|crowd|friends?|hands?|thumb|fingers?|dogs?|cats?|ducks?|birds?|blackbird|robin|sparrows?|pigeons?|snails?|"
    r"bee|bumblebee|ladybird|spider|snowm[ae]n|scarecrow|fish|heron|gulls?|nose|face|feet|he|she|his|her|they)\b", re.I)


PEOPLE = re.compile(r"\b(man|woman|grandma|grandpa|baker|postman|sailor|neighbou?rs?|child(ren)?|kids?|boys?|girls?)\b", re.I)


def still_of(prompt):
    """A shot prompt as a still: drop the sentences about the camera's move."""
    # "The camera pushes in." and "Close-up, the camera tilts down." go; "... sings to the camera, ..." stays
    move = re.compile(r"(^|, )the camera\b", re.I)
    parts = [p for p in re.split(r"(?<=[.!?])\s+", prompt.strip()) if not (move.search(p) and "{moss" not in p)]
    return " ".join(parts) or prompt


def prepare(plan):
    """Give every Moss shot of a raw plan (before concept.expand) its "frame_job". Returns the jobs."""
    jobs = []
    for i, shot in enumerate(plan["shots"]):
        p = shot["prompt"]
        who = "moss_back" if "{moss_back}" in p else "moss" if "{moss}" in p else None
        if who is None and not shot.get("frame") and not shot.get("product_image"):
            shot.setdefault("props", not SOMEONE.search(p))  # nobody in it: the props style (set "props" to overrule)
        if shot.get("product_image") or shot.get("frame") is False or (who is None and not shot.get("frame")):
            continue
        text = shot.get("frame") or still_of(p)
        text = text.replace("{moss_back}", HIM_BACK).replace("{moss}", HIM)
        if HIM not in text:  # a hand-written frame says "He ...": name him once
            him = HIM_BACK if who == "moss_back" else HIM
            text = re.sub(r"^(A close-up of him|He)\b", lambda m: ("A close-up of " + him) if m.group(1) != "He" else him[:1].upper() + him[1:], text, count=1)
            if HIM not in text.lower():
                text = f"{him[:1].upper() + him[1:]} is in the scene. {text}"
        back = who == "moss_back" or shot.get("view") in ("back", "back3q")
        view = shot.get("view") or ("back" if back else "face" if CLOSE.match(text.strip()) or CLOSE.match(p.strip()) else "front")
        text = text[:1].upper() + text[1:]
        if view == "face":
            text = re.sub(r"^Close-up: ", "", text)
            text = CLOSE_LEAD + text[:1].upper() + text[1:]
        keep = KEEP_BACK if back else KEEP_FACE if view == "face" else KEEP
        if PEOPLE.search(text):
            keep += OTHERS
        job = {"name": f"{plan['slug']}_{i:02d}", "refs": [f"moss/{v}.jpg" for v in VIEWS[view]],
               "prompt": f"{text} {keep}{LOOK}",
               "seed": zlib.crc32(plan["slug"].encode()) % 100000 + i}
        shot["frame_job"] = job
        jobs.append(job)
    return jobs
