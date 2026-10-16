"""Decide the edit before rendering: the song as it will play, and when each shot starts and how long it runs.

usage: python -m ge.timeline --plan plan.json --song song.flac [--vocals vocals.wav] [--words words.json] --out timeline.json

1. The song: YuE often leaves a long instrumental break between the choruses (20 s on 2026-10-16),
   which pushed the second verse and last chorus out of the video. Breaks in the vocals longer than
   MAX_GAP are cut down, out on a beat and back in a whole number of bars later, so the rhythm holds.
   The video starts just before the first sung word and ends when the singing does (at most MAX_BODY).
   Writes song_edit.flac (+ vocals_edit.wav, words_edit.json) next to --out, all starting at 0.
2. The cuts: knowing them first means each clip is rendered at exactly its length (no slowed-down
   filler) and a singing shot is rendered against the very stretch of vocals it plays over.
   A shot with "line": k starts on sung line k (0-based, the lines of ge.lyrics); shots without one
   share the time between their anchored neighbours, cut on a beat when one is near.
Times in the output are in video seconds; "frames" is the clip length to render.
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
MAX_FRAMES = 145   # ~6 s: attention grows with the square of the length (a 44 s shot took 417 s and ran
                   # out of memory on 2026-10-16); a longer cut plays its clip a little slower instead
MAX_GAP = 3.0      # longer silences in the vocals get cut
MAX_BODY = 72.0    # seconds before the end card (a full 16-line song; write tight lines to stay near 55)
PRE_ROLL = 0.8     # music before the first word
TAIL = 1.5         # music after the last word


def song_seconds(song):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(song)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def beats(song):
    try:
        import librosa
        y, sr = librosa.load(str(song), sr=22050, mono=True)
        _, b = librosa.beat.beat_track(y=y, sr=sr)
        return [float(t) for t in librosa.frames_to_time(b, sr=sr)]
    except Exception:  # noqa: BLE001
        return []


def quiet_runs(vocals, min_len=MAX_GAP):
    """(start, end) stretches where the isolated vocals are silent for at least min_len seconds."""
    import librosa
    import numpy as np
    y, sr = librosa.load(str(vocals), sr=22050, mono=True)
    hop = 512
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    loud = rms > 0.08 * np.percentile(rms, 95)
    t = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)
    runs, start = [], None
    for ti, lo in zip(t, loud):
        if not lo and start is None:
            start = ti
        elif lo and start is not None:
            if ti - start >= min_len:
                runs.append((float(start), float(ti)))
            start = None
    if start is not None and t[-1] - start >= min_len:  # silent to the end: the outro
        runs.append((float(start), float(t[-1])))
    return runs


def merge(spans):
    """Overlapping (start, end) spans joined into one."""
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def keep_segments(first, last, gaps, beat_times):
    """Song stretches to keep: first..last minus each long gap, cut on a beat and resumed whole bars later."""
    segs, cur = [], first
    for qa, qb in gaps:
        if qa <= first or qb >= last:
            continue  # intro and outro are trimmed by first/last already
        out_i = next((j for j, b in enumerate(beat_times) if b >= qa + 0.4), None)
        if out_i is None:
            continue
        ins = [beat_times[j] for j in range(out_i + 8, len(beat_times), 4) if beat_times[j] <= qb - 0.4]
        if not ins:
            continue
        segs.append((cur, beat_times[out_i]))
        cur = ins[-1]
    segs.append((cur, last))
    return [(round(a, 3), round(b, 3)) for a, b in segs]


def to_edit(t, segs):
    """Song time -> edited time (a time inside a removed stretch lands on the cut)."""
    acc = 0.0
    for a, b in segs:
        if t < a:
            return acc
        if t <= b:
            return acc + t - a
        acc += b - a
    return acc


def splice(src, segs, dst):
    """Write the kept stretches of src as one file, with 30 ms crossfades at the cuts."""
    parts = "".join(f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS[s{i}];" for i, (a, b) in enumerate(segs))
    chain, last = "", "s0"
    for i in range(1, len(segs)):
        chain += f"[{last}][s{i}]acrossfade=d=0.03[x{i}];"
        last = f"x{i}"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-filter_complex", (parts + chain).rstrip(";"),
                    "-map", f"[{last}]", str(dst)], check=True)


def frames_for(seconds):
    n = math.ceil(seconds * FPS) + 2  # a little spare so the cut never runs past the clip
    return min(MAX_FRAMES, max(MIN_FRAMES, 8 * math.ceil((n - 1) / 8) + 1))


def plan_cuts(plan, body, lines, beat_times=None, endcard=3.0):
    """Shot starts and lengths over `body` seconds. `lines` are word lists in video time."""
    shots = plan["shots"]
    n = len(shots)
    anchors = {0: 0.0}
    last = 0.0
    for i, s in enumerate(shots):
        k = s.get("line")
        if i == 0 or k is None or not lines or not 0 <= k < len(lines):
            continue
        t = lines[k][0]["s"] - LEAD
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
        sing = bool(shots[i].get("sing")) and i in anchors
        # "speed" (shot, else plan): render that much more motion and play it faster; lip sync stays 1x
        speed = 1.0 if sing else float(shots[i].get("speed", plan.get("speed", 1.0)))
        out.append({"start": round(starts[i], 3), "dur": dur, "frames": frames_for(dur * speed),
                    "sing": sing, "speed": speed})
    return out


def build(plan, song, out, vocals=None, words=None, endcard=3.0):
    out = pathlib.Path(out)
    lines = [l for l in (words or []) if l]
    length = song_seconds(song)
    bt = beats(song)
    if lines:
        first = max(0.0, min(w["s"] for l in lines for w in l) - PRE_ROLL)
        last_word = max(w["e"] for l in lines for w in l)
    else:
        first, last_word = 0.0, length
    gaps = quiet_runs(vocals) if vocals else []
    if gaps and gaps[-1][1] >= length - 0.5:  # the vocals know when the singing stopped
        last_word = min(last_word, gaps[-1][0])
    # a choir humming through a break hides it from quiet_runs (2026-10-16: a 17 s break between "back to"
    # and "you" pushed the last chorus out of the video), so long gaps between sung words count too
    words_flat = sorted((w for l in lines for w in l), key=lambda w: w["s"])
    gaps = merge(gaps + [(a["e"], b["s"]) for a, b in zip(words_flat, words_flat[1:]) if b["s"] - a["e"] > MAX_GAP])
    segs = keep_segments(first, min(length, last_word + TAIL), gaps, bt)
    edit_len = sum(b - a for a, b in segs)
    body = min(edit_len, plan.get("max_seconds") or MAX_BODY)  # max_seconds: short tests, or a slow song that needs longer

    lines_e = [[{**w, "s": round(to_edit(w["s"], segs), 3), "e": round(to_edit(w["e"], segs), 3)} for w in l] for l in lines]
    # a line that starts too late for the video is dropped (its shots fall back to even cuts)
    lines_e = [l for l in lines_e if l[0]["s"] < body - 1.0]
    beats_e = sorted({round(to_edit(b, segs), 3) for b in bt if any(a <= b <= c for a, c in segs)})

    splice(song, segs, out.parent / "song_edit.flac")
    if vocals:
        splice(vocals, segs, out.parent / "vocals_edit.wav")
    (out.parent / "words_edit.json").write_text(json.dumps(lines_e))
    tl = {"offset": 0.0, "total": round(body + endcard, 3), "endcard": endcard, "song": "song_edit.flac",
          "segments": segs, "shots": plan_cuts(plan, body, lines_e, beats_e, endcard)}
    out.write_text(json.dumps(tl, indent=1))
    return tl


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--song", required=True)
    ap.add_argument("--vocals")
    ap.add_argument("--words")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    plan = json.loads(pathlib.Path(a.plan).read_text())
    words = json.loads(pathlib.Path(a.words).read_text()) if a.words and pathlib.Path(a.words).exists() else None
    vocals = a.vocals if a.vocals and pathlib.Path(a.vocals).exists() else None
    tl = build(plan, a.song, a.out, vocals, words)
    cut = sum(b - a for a, b in zip([s[1] for s in tl["segments"][:-1]], [s[0] for s in tl["segments"][1:]]))
    print(f"{len(tl['shots'])} shots over {tl['total'] - tl['endcard']:.1f}s ({cut:.1f}s of breaks cut), "
          f"{sum(s['sing'] for s in tl['shots'])} singing, {sum(s['frames'] for s in tl['shots'])} frames")
