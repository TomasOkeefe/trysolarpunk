"""Time the plan's lyrics against the song, for the burned-in TikTok-style captions.

usage: python -m ge.lyrics --song song.flac --plan plan.json --out words.json [--vocals-out vocals.wav]
Needs stable-ts, plus demucs to align against the isolated vocals (much better on music).
Output: one list of {"w", "s", "e"} words (seconds) per sung line. With --vocals-out the isolated
vocals are kept too: singing shots are rendered against them (LTX audio-to-video lip sync).
"""
import argparse
import json
import pathlib


def lines(lyrics):
    return [l.strip() for l in lyrics.splitlines() if l.strip() and not l.strip().startswith("[")]


def separate(song, out):
    """Write the song's isolated vocals to `out` (demucs htdemucs, two stems)."""
    import shutil
    import tempfile
    from demucs.separate import main as demucs
    tmp = pathlib.Path(tempfile.mkdtemp())
    demucs(["-n", "htdemucs", "--two-stems", "vocals", "-o", str(tmp), str(song)])
    shutil.move(next(tmp.glob("htdemucs/*/vocals.wav")), out)


def align(song, lyrics, model="medium", vocals=None):
    import stable_whisper
    m = stable_whisper.load_model(model)
    text = "\n".join(lines(lyrics))
    if vocals:
        res = m.align(str(vocals), text, language="en", original_split=True)
        return [[{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for w in seg.words if w.word.strip()]
                for seg in res.segments]
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
    ap.add_argument("--vocals-out", help="also keep the isolated vocals here (and align against them)")
    a = ap.parse_args()
    vocals = None
    if a.vocals_out:
        try:
            separate(a.song, a.vocals_out)
            vocals = a.vocals_out
        except Exception as e:  # noqa: BLE001
            print(f"vocal separation failed ({type(e).__name__}: {e}); singing shots get the full mix", flush=True)
    words = align(a.song, json.loads(pathlib.Path(a.plan).read_text())["song"]["lyrics"], a.model, vocals)
    pathlib.Path(a.out).write_text(json.dumps(words))
    print(f"timed {sum(map(len, words))} words in {len(words)} lines")
