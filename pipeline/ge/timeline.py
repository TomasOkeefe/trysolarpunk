"""Decide the edit before rendering: where the song starts, and when each shot starts and how long it runs.

usage: python -m ge.timeline --plan plan.json --song song.flac [--words words.json] --out timeline.json

Knowing the cuts first means each clip is rendered at exactly its length (no slowed-down filler) and
a singing shot can be rendered against the very stretch of vocals it will play over.
A shot with "line": k starts on sung line k (0-based, the lines of ge.lyrics); shots without one
share the time between their anchored neighbours, cut on a beat when one is near.
Output times are in video seconds (song time minus "offset"); "frames" is the clip length to render.
"""
import argparse
import json
import math
import pathlib
import subprocess

FPS = 24
LEAD = 0.15        # a line's shot starts this much before its first word
MIN_SHOT = 1.0     # seconds
MIN_FRAMES = 33    # LTX frame counts are 8k+1


def song_seconds(song):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(song)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def beats(song, offset, total):
    try:
        import librosa
        y, sr = librosa.load(str(song), sr=22050, mono=True, offset=offset, duration=total)
        _, b = librosa.beat.beat_track(y=y, sr=sr)
        return list(librosa.frames_to_time(b, sr=sr))
    except Exception:  # noqa: BLE001
        return []


def frames_for(seconds):
    n = math.ceil(seconds * FPS) + 2  # a little spare so the cut never runs past the clip
    return max(MIN_FRAMES, 8 * math.ceil((n - 1) / 8) + 1)


def plan_timeline(plan, song_len, words=None, beat_times=None, target=52.0, endcard=3.0):
    lines = [l for l in (words or []) if l]
    offset = max(0.0, min(w["s"] for l in lines for w in l) - 0.8) if lines else 0.0
    total = min(song_len - offset, target + endcard)
    body = total - endcard
    shots = plan["shots"]
    n = len(shots)

    # anchors: shot index -> start time; shot 0 always opens the video
    anchors = {0: 0.0}
    last = 0.0
    for i, s in enumerate(shots):
        k = s.get("line")
        if i == 0 or k is None or not lines or not 0 <= k < len(lines):
            continue
        t = lines[k][0]["s"] - offset - LEAD
        if last + MIN_SHOT * (i - max(anchors)) <= t <= body - MIN_SHOT * (n - i):
            anchors[i] = t
            last = t
    anchors[n] = body

    bt = beat_times or []
    starts = [0.0] * (n + 1)
    idx = sorted(anchors)
    for a, b in zip(idx, idx[1:]):
        ta, tb = anchors[a], anchors[b]
        starts[a] = ta
        for j in range(a + 1, b):
            t = ta + (tb - ta) * (j - a) / (b - a)
            near = [x for x in bt if abs(x - t) < 0.4 and x - starts[j - 1] >= MIN_SHOT and tb - x >= MIN_SHOT]
            starts[j] = min(near, key=lambda x: abs(x - t)) if near else t
    starts[n] = body

    out = []
    for i in range(n):
        dur = round(starts[i + 1] - starts[i], 3)
        out.append({"start": round(starts[i], 3), "dur": dur, "frames": frames_for(dur),
                    "sing": bool(shots[i].get("sing")) and i in anchors})
    return {"offset": round(offset, 3), "total": round(total, 3), "endcard": endcard, "shots": out}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--song", required=True)
    ap.add_argument("--words")
    ap.add_argument("--out", required=True)
    ap.add_argument("--target", type=float)
    a = ap.parse_args()
    plan = json.loads(pathlib.Path(a.plan).read_text())
    words = json.loads(pathlib.Path(a.words).read_text()) if a.words and pathlib.Path(a.words).exists() else None
    target = a.target or plan.get("target_seconds", 52.0)
    first = plan_timeline(plan, song_seconds(a.song), words, None, target)
    tl = plan_timeline(plan, song_seconds(a.song), words, beats(a.song, first["offset"], first["total"]), target)
    pathlib.Path(a.out).write_text(json.dumps(tl, indent=1))
    print(f"{len(tl['shots'])} shots over {tl['total'] - tl['endcard']:.1f}s, "
          f"{sum(s['sing'] for s in tl['shots'])} singing, {sum(s['frames'] for s in tl['shots'])} frames")
