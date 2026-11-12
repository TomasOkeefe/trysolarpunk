"""Master frames of Moss for reference shoots: stills from the one turnaround clip every later clip
starts from (videos/lora/moss-data/clips/moss_00.mp4), with his skin warmed a little (owner, 2026-11-11).

  python3 moss_masters.py            # writes assets/moss/<view>.jpg (768 x 1344)

Views: front, threeq, side, back3q, back (he shows his right side), their mirrors (*_m, his left
side) and face (a head-and-shoulders crop of the front, enlarged).
"""
import colorsys
import pathlib
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent
CLIP = ROOT.parent / "videos" / "lora" / "moss-data" / "clips" / "moss_00.mp4"
OUT = ROOT / "assets" / "moss"
FRAMES = {"front": 1, "threeq": 13, "side": 25, "back3q": 37, "back": 49}   # 1-based frame of the clip
WARM = (1.0, 0.925, 0.84)   # multiply skin RGB: a touch darker and more peach


def skin_mask(rgb):
    """Soft mask of his skin: light peach, less yellow than the cream backdrop, far paler than the coat."""
    # judged on a blurred copy: video compression blocks otherwise flicker in and out of the mask
    soft = Image.fromarray(rgb.astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))
    a = np.asarray(soft, np.float32) / 255
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-6)
    hue = np.degrees(np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b)) % 360
    m = (hue > 6) & (hue < 32) & (sat > 0.12) & (sat < 0.52) & (mx > 0.5)
    img = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(9)).filter(ImageFilter.GaussianBlur(3))
    return np.asarray(img, np.float32)[..., None] / 255


def warm(img):
    rgb = np.asarray(img.convert("RGB"), np.float32)
    m = skin_mask(rgb)
    out = rgb * (1 - m) + rgb * np.array(WARM, np.float32) * m
    return Image.fromarray(out.clip(0, 255).astype(np.uint8)), m


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(CLIP), f"{tmp}/f_%02d.png"], check=True)
        for name, n in FRAMES.items():
            img, _ = warm(Image.open(f"{tmp}/f_{n:02d}.png"))
            img.save(OUT / f"{name}.jpg", quality=95)
            if name != "front" and name != "back":
                img.transpose(Image.FLIP_LEFT_RIGHT).save(OUT / f"{name}_m.jpg", quality=95)
    front = Image.open(OUT / "front.jpg")
    w, h = front.size
    cw = int(w * 0.6)
    ch = int(cw * h / w)
    x0, y0 = (w - cw) // 2 + int(w * 0.005), int(h * 0.205)
    front.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), Image.LANCZOS).save(OUT / "face.jpg", quality=95)
    print(sorted(p.name for p in OUT.glob("*.jpg")))


if __name__ == "__main__":
    main()
