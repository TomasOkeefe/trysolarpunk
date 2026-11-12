"""Put the master Moss into scene plates, as first frames for reference shoots.

  uv run --python 3.12 --with "rembg[cpu]" --with pillow --with pymatting python moss_scenes.py PLATES_DIR

PLATES_DIR holds <scene>.png stills of empty sets (768 x 1344). For every pairing in SCENES this
cuts Moss out of assets/moss/<view>.jpg, scales him, stands him on the plate's ground with a soft
contact shadow, and writes assets/moss/scene_<scene>.jpg. The video model then animates from that
frame and blends him into the set's light.
"""
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from rembg import new_session, remove

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "assets" / "moss"
# scene: (views, height of Moss as a share of the frame, x of his centre, y of his soles, tint strength).
# The first view names the file scene_<scene>.jpg; further views (for turns keyed on several frames)
# get scene_<scene>_<view>.jpg, standing on the same spot.
SCENES = {
    "garden": (["front"], 0.50, 0.50, 0.90, 0.10),
    "kitchen": (["threeq"], 0.50, 0.46, 0.90, 0.12),
    "street": (["side"], 0.46, 0.42, 0.90, 0.10),
    "rooftop": (["back3q"], 0.48, 0.50, 0.90, 0.10),
    "park": (["front", "side", "back"], 0.46, 0.46, 0.90, 0.10),
    "livingroom": (["threeq_m"], 0.50, 0.55, 0.92, 0.14),
    "dock": (["back"], 0.45, 0.50, 0.84, 0.14),
    "market": (["front", "side_m", "back"], 0.48, 0.50, 0.90, 0.10),
    "meadow": (["side_m"], 0.42, 0.58, 0.88, 0.08),
    "bedroom": (["front"], 0.48, 0.52, 0.92, 0.22),
    "forest": (["side"], 0.45, 0.45, 0.90, 0.12),
    "greenhouse": (["threeq"], 0.48, 0.50, 0.90, 0.08),
    # plain studio backdrops in other colours (made here, no plate needed)
    "sage": (["front"], 0.70, 0.50, 0.92, 0.0),
    "terracotta": (["threeq_m"], 0.70, 0.50, 0.92, 0.0),
    "sky": (["side"], 0.70, 0.50, 0.92, 0.0),
    "grey": (["back"], 0.70, 0.50, 0.92, 0.0),
}
BACKDROPS = {"sage": (196, 208, 178), "terracotta": (214, 138, 104), "sky": (176, 208, 226), "grey": (205, 204, 200)}
FACES = ("threeq", "side", "threeq_m")   # head-and-shoulders crops, like moss_masters.py's face.jpg


def backdrop(rgb, size=(768, 1344)):
    """A studio sweep in one colour: a little darker towards the top corners, lighter on the floor."""
    W, H = size
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    shade = 1.0 - 0.10 * ((x / W - 0.5) ** 2 * 2 + (1 - y / H) * 0.5) + 0.04 * np.clip((y / H - 0.75) * 4, 0, 1)
    return Image.fromarray((np.array(rgb, np.float32)[None, None] * shade[..., None]).clip(0, 255).astype(np.uint8))


def faces(sess):
    for view in FACES:
        full = remove(Image.open(OUT / f"{view}.jpg").convert("RGB"), session=sess)
        alpha = np.asarray(full.getchannel("A"), np.float32)
        W, H = full.size
        top = int(np.argmax(alpha.max(1) > 128))
        band = alpha[top:top + int(H * 0.25)]
        cx = float((band.sum(0) * np.arange(W)).sum() / max(band.sum(), 1))
        cw = int(W * 0.6)
        ch = int(cw * H / W)
        x0 = int(min(max(cx - cw / 2, 0), W - cw))
        y0 = max(0, top - int(H * 0.02))
        Image.open(OUT / f"{view}.jpg").crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.LANCZOS).save(
            OUT / f"face_{view}.jpg", quality=95)
        print("face", view)


def cutout(view, sess, cache={}):
    if view not in cache:
        img = remove(Image.open(OUT / f"{view}.jpg").convert("RGB"), session=sess, alpha_matting=True,
                     alpha_matting_foreground_threshold=240, alpha_matting_background_threshold=15,
                     alpha_matting_erode_size=4)
        cache[view] = img.crop(img.getbbox())
    return cache[view]


def main():
    plates = pathlib.Path(sys.argv[1])
    sess = new_session("isnet-general-use")
    faces(sess)
    for scene, (views, share, cx, foot, tint) in SCENES.items():
        src = plates / f"{scene}.png"
        if scene in BACKDROPS:
            bg = backdrop(BACKDROPS[scene])
        elif src.exists():
            bg = Image.open(src).convert("RGB")
        else:
            print("no plate for", scene)
            continue
        W, H = bg.size
        mean = np.asarray(bg.resize((8, 8)), np.float32).mean((0, 1))
        for k, view in enumerate(views):
            m = cutout(view, sess)
            h = int(H * share)
            w = int(m.width * h / m.height)
            m = m.resize((w, h), Image.LANCZOS)
            # lean his colours a little towards the set's light
            rgb = np.asarray(m.convert("RGB"), np.float32)
            rgb = rgb * (1 - tint) + rgb * (mean / max(mean.mean(), 1)) * tint
            m = Image.merge("RGBA", (*Image.fromarray(rgb.clip(0, 255).astype(np.uint8)).split(), m.getchannel("A")))
            x, y = int(W * cx - w / 2), int(H * foot - h)
            shadow = Image.new("L", (W, H), 0)
            ImageDraw.Draw(shadow).ellipse((x + w * 0.08, y + h * 0.93, x + w * 0.92, y + h * 1.03), fill=150)
            shadow = shadow.filter(ImageFilter.GaussianBlur(h * 0.035))
            out = Image.composite(Image.new("RGB", (W, H), (20, 16, 12)), bg, shadow)
            out.paste(m, (x, y), m)
            out.save(OUT / (f"scene_{scene}.jpg" if k == 0 else f"scene_{scene}_{view}.jpg"), quality=95)
            print("scene", scene, view)


if __name__ == "__main__":
    main()
