"""Cut generated clips to the song's beat, add hook text, lyric captions and end card, mux the song.

usage: python -m ge.assemble --plan plan.json --song song.flac --clips clips/ --out final.mp4 [--words words.json]
Needs ffmpeg on PATH. librosa is optional (falls back to even cuts). words.json comes from ge.lyrics;
with it the song's instrumental intro is trimmed and the lyrics are burned in TikTok style.
No AI label is burned in: TikTok adds its own when the AI-generated toggle is on.
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
# Edit dynamics (the owner found the first quality pass still too calm): each cut lands with a quick zoom
# punch that settles in PUNCH_S, then the frame keeps drifting (in, out, in...) by DRIFT; shots that open
# a chorus flash white. Digital moves over on-twos animation, like a stop-motion music video.
PUNCH, PUNCH_S, DRIFT, FLASH_S = 0.08, 0.22, 0.06, 0.16
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


def caption_chunks(lines, body):
    """Split each sung line into chunks of up to 3 words: [(start, end, words)], words = [(word, start)]."""
    words = [[w for w in l if w["e"] - w["s"] > 0.02 and w["s"] < body - 0.3] for l in lines]
    chunks = []
    for l in words:
        cur = []
        for w in l:
            if cur and (len(cur) == 3 or len(" ".join(x["w"] for x in cur + [w])) > 18):
                chunks.append(cur)
                cur = []
            cur.append(w)
        if cur:
            chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        nxt = chunks[i + 1][0]["s"] if i + 1 < len(chunks) else body
        out.append((c[0]["s"], min(nxt, c[-1]["e"] + 0.6, body), [(w["w"], w["s"]) for w in c]))
    return out


def caption_png(words, active, tilt, path, cy=1120):
    """One caption state: the chunk's words, the sung one in sun yellow and a touch bigger, slightly tilted."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f, fa, max_w, lh = font(100, weight=900), font(114, weight=900), 780, 132
    sp = d.textlength(" ", font=f)
    rows, cur, cur_w = [], [], 0
    for i, w in enumerate(words):
        ww = d.textlength(w, font=fa if i == active else f)
        if cur and cur_w + sp + ww > max_w:
            rows.append((cur, cur_w))
            cur, cur_w = [], 0
        cur_w += (sp if cur else 0) + ww
        cur.append((i, w, ww))
    rows.append((cur, cur_w))
    top = cy - lh * len(rows) / 2
    for r, (row, rw) in enumerate(rows):
        x = (W - rw) / 2
        for i, w, ww in row:
            d.text((x, top + r * lh + lh / 2), w, font=fa if i == active else f, anchor="lm",
                   fill=SUN if i == active else CREAM, stroke_width=10, stroke_fill=INK)
            x += ww + sp
    im.rotate(tilt, center=(W / 2, cy), resample=Image.BICUBIC).save(path)


def caption_track(lines, body, tmp, keep_clear=(0, 0)):
    """Write an ffmpeg concat list of caption states (blank between lines) and return its path.
    Captions overlapping keep_clear (the product shot) move below the product so they don't cover it."""
    blank = tmp / "cap_blank.png"
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
    entries, t = [], 0.0
    for k, (start, end, words) in enumerate(caption_chunks(lines, body)):
        if start > t:
            entries.append((blank, start - t))
        starts = [s for _, s in words] + [end]
        for i in range(len(words)):
            a, b = max(starts[i], start), min(starts[i + 1], end)
            if b - a > 0.01:
                png = tmp / f"cap_{k:03d}_{i}.png"
                caption_png([w for w, _ in words], i, (-2.5, 2, -1.5, 3)[k % 4], png,
                            cy=1480 if start < keep_clear[1] and end > keep_clear[0] else 1120)
                entries.append((png, b - a))
        t = end
    entries.append((blank, max(0.1, body - t) + 5))
    lst = tmp / "captions.txt"
    lst.write_text("".join(f"file '{p}'\nduration {dur:.3f}\n" for p, dur in entries) + f"file '{blank}'\n")
    return lst


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
def cut_points(song, n, total, endcard, offset=0.0):
    """Return n shot durations that sum to (total - endcard), each cut on a beat when possible."""
    body = total - endcard
    even = [body / n] * n
    try:
        import librosa
        y, sr = librosa.load(song, sr=22050, mono=True, offset=offset, duration=total)
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
def chorus_lines(lyrics):
    """Indexes (in sung lines) of the first line of every chorus."""
    out, idx, section = [], 0, ""
    for l in lyrics.splitlines():
        l = l.strip()
        if l.startswith("["):
            section = l.lower()
            first = True
        elif l:
            if "chorus" in section and first:
                out.append(idx)
            first = False
            idx += 1
    return out


def motion_filter(i, d, flash, PUNCH=PUNCH, PUNCH_S=PUNCH_S, DRIFT=DRIFT, FLASH_S=FLASH_S):
    """Zoom punch at the cut, then a slow drift (alternating in and out), plus a white flash."""
    settle = f"{PUNCH}*pow(max(0,1-t/{PUNCH_S}),2)"
    drift = f"{DRIFT}*min(t/{max(d, 0.5):.3f},1)" if i % 2 == 0 else f"{DRIFT}*(1-min(t/{max(d, 0.5):.3f},1))"
    z = f"(1+{settle}+{drift})"
    vf = (f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame:flags=bicubic,"
          f"crop={W}:{H}")
    if flash:
        vf += f",fade=t=in:st=0:d={FLASH_S}:color=white"
    return vf


def assemble(plan, song, clips, out, target=45, endcard=3.0, words=None, anim_fps=None, timeline=None,
             dynamic=True):
    clips = sorted(pathlib.Path(clips).glob("shot_*.mp4"))
    n = len(clips)
    assert n, "no clips"
    # start the song just before the first sung word, so the vocals (and the chorus) land in the video
    lines = [l for l in (words or []) if l]
    if timeline and len(timeline["shots"]) == n:  # cuts planned before rendering (ge.timeline)
        offset, total, endcard = timeline["offset"], timeline["total"], timeline["endcard"]
        durs = [s["dur"] for s in timeline["shots"]]
    else:
        offset = max(0.0, min(w["s"] for l in lines for w in l) - 0.8) if lines else 0.0
        total = min(probe_duration(song) - offset, target + endcard)
        durs = cut_points(song, n, total, endcard, offset)
    lines = [[{**w, "s": w["s"] - offset, "e": w["e"] - offset} for w in l] for l in lines]
    tmp = pathlib.Path(tempfile.mkdtemp())

    parts = []
    step = f"fps={anim_fps}," if anim_fps else ""  # hold frames ("on twos") for a hand-animated feel
    flash_at = set()
    edit = {k.upper(): v for k, v in (plan.get("edit") or {}).items()}  # e.g. {"punch": 0.15, "drift": 0.12}
    if dynamic and timeline:  # the shots anchored on a chorus's first line
        firsts = set(chorus_lines(plan["song"]["lyrics"]))
        flash_at = {i for i, s in enumerate(plan["shots"]) if s.get("line") in firsts and i > 0}
    for i, (clip, d) in enumerate(zip(clips, durs)):
        cd = probe_duration(clip)
        fast = (timeline["shots"][i].get("speed", 1.0) if timeline and i < len(timeline["shots"]) else 1.0)
        # faster than real time when the timeline asked (snappier motion), slower only to fill a gap
        speed = max(1.0, d / cd) if fast == 1.0 else 1 / fast
        p = tmp / f"p{i:02d}.mp4"
        vf = (f"setpts={speed:.4f}*PTS,scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},{step}fps={FPS},"
              + (motion_filter(i, d, i in flash_at, **edit) + "," if dynamic else "") + "format=yuv420p")
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
    prod = next((i for i, s in enumerate(plan["shots"]) if s.get("product_image")), None)
    clear = (sum(durs[:prod]), sum(durs[:prod + 1])) if prod is not None and prod < len(durs) else (0, 0)
    caps = caption_track(lines, total - endcard, tmp, clear)
    fade_start = max(0.0, total - 1.5)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", body, "-i", tmp / "hook.png",
         "-f", "concat", "-safe", "0", "-i", caps, "-i", song,
         "-filter_complex",
         f"[0:v][1:v]overlay=0:0:enable='between(t,0.2,3.2)'[v1];"
         f"[2:v]fps={FPS},format=rgba[c];[v1][c]overlay=0:0:eof_action=pass[v];"
         f"[3:a]atrim={offset:.3f}:{offset + total:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.05,"
         f"afade=t=out:st={fade_start:.3f}:d=1.5,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", "-t", f"{total:.3f}", out])
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--song", required=True)
    ap.add_argument("--clips", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--words", help="lyric timings from ge.lyrics (optional)")
    ap.add_argument("--timeline", help="cut plan from ge.timeline (optional)")
    ap.add_argument("--target", type=float, default=45)
    ap.add_argument("--anim-fps", type=int, help="hold frames at this rate, e.g. 12")
    ap.add_argument("--calm", action="store_true", help="no zoom punches, drift or flashes")
    a = ap.parse_args()
    words = json.loads(pathlib.Path(a.words).read_text()) if a.words and pathlib.Path(a.words).exists() else None
    plan = json.loads(pathlib.Path(a.plan).read_text())
    plan_anim = plan.get("anim_fps")  # stamped from config.yaml by run.py
    tl = json.loads(pathlib.Path(a.timeline).read_text()) if a.timeline and pathlib.Path(a.timeline).exists() else None
    assemble(plan, a.song, a.clips, a.out, plan.get("target_seconds", a.target),
             words=words, anim_fps=a.anim_fps or plan_anim, timeline=tl, dynamic=not a.calm)
    print("wrote", a.out)
