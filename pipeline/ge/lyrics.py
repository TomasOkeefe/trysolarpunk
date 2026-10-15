"""Time the plan's lyrics against the song, for the burned-in TikTok-style captions.

usage: python -m ge.lyrics --song song.flac --plan plan.json --out words.json
Needs stable-ts, plus demucs to align against the isolated vocals (much better on music).
Output: one list of {"w", "s", "e"} words (seconds) per sung line.
"""
import argparse
import json
import pathlib


def lines(lyrics):
    return [l.strip() for l in lyrics.splitlines() if l.strip() and not l.strip().startswith("[")]


def align(song, lyrics, model="medium"):
    import stable_whisper
    m = stable_whisper.load_model(model)
    text = "\n".join(lines(lyrics))
    try:
        res = m.align(str(song), text, language="en", original_split=True, denoiser="demucs")
    except Exception as e:  # noqa: BLE001
        print(f"demucs failed ({type(e).__name__}: {e}); aligning against the full mix", flush=True)
        res = m.align(str(song), text, language="en", original_split=True)
    return [[{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for w in seg.words if w.word.strip()]
            for seg in res.segments]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--song", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="medium")
    a = ap.parse_args()
    words = align(a.song, json.loads(pathlib.Path(a.plan).read_text())["song"]["lyrics"], a.model)
    pathlib.Path(a.out).write_text(json.dumps(words))
    print(f"timed {sum(map(len, words))} words in {len(words)} lines")
