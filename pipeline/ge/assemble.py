"""Cut generated clips to the song's beat, add hook text, AI label and end card, mux the song.

usage: python -m ge.assemble --plan plan.json --song song.flac --clips clips/ --out final.mp4
Needs ffmpeg on PATH. librosa is optional (falls back to even cuts).
"""
import argparse
import json
import pathlib
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
W, H, FPS = 1080, 1920, 24
INK, CREAM, SUN, MOSS = (42, 36, 32), (246, 241, 228), (242, 193, 78), (47, 93, 58)


# ------------------------------------------------------------------ text graphics
def font(size, weight=800, soft=100):
    f = ImageFont.truetype(str(ASSETS / "fonts/Fraunces.ttf"), size)
    axes = {a["name"].lower() if isinstance(a["name"], str) else a["name"].decode().lower(): a
            for a in f.get_variation_axes()}
    vals = []
    for a in f.get_variation_axes():
        n = (a["name"] if isinstance(a["name"], str) else a["name"].decode()).lower()
        vals.append({"weight": weight, "optical size": 144, "softness": soft, "wonky": 1}.get(n, a["default"]))
    f.set_variation_by_axes(vals)
    return f


def mono(size):
    return ImageFont.truetype(str(ASSETS / "fonts/SpaceMono-Bold.ttf"), size)


def wrap(draw, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= max_w:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def hook_png(text, path):
    """Big hook text on a cream sticker, upper third."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(104)
    lines = wrap(d, text, f, W - 220)
    lh = 112
    box_h = lh * len(lines) + 70
    top = 300
    widest = max(d.textlength(l, font=f) for l in lines)
    x0 = (W - widest) / 2 - 50
    d.rounded_rectangle([x0 + 10, top + 12, W - x0 + 10, top + box_h + 12], 40, fill=INK)
    d.rounded_rectangle([x0, top, W - x0, top + box_h], 40, fill=CREAM, outline=INK, width=8)
    for i, l in enumerate(lines):
        d.text((W / 2, top + 35 + i * lh + lh / 2), l, font=f, fill=INK, anchor="mm")
    im.save(path)


def label_png(text, path):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = mono(30)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle([40, 150, 40 + tw + 36, 150 + 54], 27, fill=(42, 36, 32, 200))
    d.text((58, 150 + 27), text, font=f, fill=CREAM, anchor="lm")
    im.save(path)


def endcard_png(line1, line2, path):
    im = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(im)
    em = Image.open(ASSETS / "emblem.png").convert("RGBA").resize((560, 560), Image.LANCZOS)
    im.paste(em, ((W - 560) // 2, 380), em)
    d.text((W / 2, 1080), "Try Solarpunk", font=font(120), fill=INK, anchor="mm")
    f = font(70, weight=700)
    for i, l in enumerate(wrap(d, line1, f, W - 200)):
        d.text((W / 2, 1250 + i * 84), l, font=f, fill=MOSS, anchor="mm")
    d.rounded_rectangle([W / 2 - 250, 1500, W / 2 + 250, 1600], 50, fill=SUN, outline=INK, width=6)
    d.text((W / 2, 1550), line2.upper(), font=mono(44), fill=INK, anchor="mm")
    # checker stripe like the brand banner
    for i in range(0, W, 90):
        d.rectangle([i, H - 60, i + 45, H], fill=(155, 197, 61))
        d.rectangle([i + 45, H - 60, i + 90, H], fill=MOSS)
    im.save(path)


# ------------------------------------------------------------------ timing
def cut_points(song, n, total, endcard):
    """Return n shot durations that sum to (total - endcard), each cut on a beat when possible."""
    body = total - endcard
    even = [body / n] * n
    try:
        import librosa
        y, sr = librosa.load(song, sr=22050, mono=True, duration=total)
        _, beats = librosa.beat.beat_track(y=y, sr=sr)
        bt = librosa.frames_to_time(beats, sr=sr)
    except Exception:
        return even
    if len(bt) < n * 2:
        return even
    targets = [body * (i + 1) / n for i in range(n - 1)]
    cuts, last = [], 0.0
    for t in targets:
        cand = [b for b in bt if b > last + 2.0]
        b = min(cand, key=lambda b: abs(b - t)) if cand else t
        b = b if abs(b - t) < 1.2 else t
        cuts.append(b)
        last = b
    edges = [0.0] + cuts + [body]
    durs = [round(edges[i + 1] - edges[i], 3) for i in range(n)]
    return durs


def run(cmd):
    print("+", " ".join(str(c) for c in cmd)[:300])
    subprocess.run(cmd, check=True)


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


# ------------------------------------------------------------------ main
def assemble(plan, song, clips, out, target=45, endcard=3.0, ai_label="AI-generated"):
    clips = sorted(pathlib.Path(clips).glob("shot_*.mp4"))
    n = len(clips)
    assert n, "no clips"
    total = min(probe_duration(song), target + endcard)
    durs = cut_points(song, n, total, endcard)
    tmp = pathlib.Path(tempfile.mkdtemp())

    parts = []
    for i, (clip, d) in enumerate(zip(clips, durs)):
        cd = probe_duration(clip)
        speed = max(1.0, d / cd)  # if the beat gap is longer than the clip, slow it a touch
        p = tmp / f"p{i:02d}.mp4"
        vf = (f"setpts={speed:.4f}*PTS,scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},fps={FPS},format=yuv420p")
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-t", f"{d:.3f}", "-vf", vf, "-an",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", p])
        parts.append(p)

    endcard_png(plan["endcard"]["line1"], plan["endcard"].get("line2", "link in bio"), tmp / "end.png")
    end = tmp / "end.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", tmp / "end.png", "-t", f"{endcard}",
         "-vf", f"fps={FPS},format=yuv420p,zoompan=z='1+0.0008*on':d=1:s={W}x{H}:fps={FPS}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", end])
    parts.append(end)

    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    body = tmp / "body.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", body])

    hook_png(plan["hook_text"], tmp / "hook.png")
    label_png(ai_label, tmp / "label.png")
    fade_start = max(0.0, total - 1.5)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", body, "-i", tmp / "hook.png", "-i", tmp / "label.png",
         "-i", song,
         "-filter_complex",
         f"[0:v][1:v]overlay=0:0:enable='between(t,0.2,3.2)'[v1];[v1][2:v]overlay=0:0[v];"
         f"[3:a]atrim=0:{total:.3f},afade=t=in:d=0.05,afade=t=out:st={fade_start:.3f}:d=1.5,"
         f"loudnorm=I=-14:TP=-1.5:LRA=11[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", "-t", f"{total:.3f}", out])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--song", required=True)
    ap.add_argument("--clips", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target", type=float, default=45)
    a = ap.parse_args()
    assemble(json.loads(pathlib.Path(a.plan).read_text()), a.song, a.clips, a.out, a.target)
    print("wrote", a.out)
