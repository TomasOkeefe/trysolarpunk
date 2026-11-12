"""Build a LoRA dataset from a reference shoot whose clips all start from the master frames.

  python3 moss_dataset.py plans/reference/moss-ref-shoot.json ../videos/raw/moss-ref-shoot ../videos/lora/moss2-data

Every 121-frame clip gives two 49-frame pieces (frames 24-72 and 72-120): the first second is left
out so that no two pieces open on the very same master frame. Shorter clips give one piece. A shot's
"caption" (what happens, without the style words) becomes the piece's caption; shots marked
"skip": true (judged bad after the shoot) are left out. The original turnaround clip the master
frames came from is added too.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PIECE = 49


def frames_of(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_frames", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return int(r.stdout.strip() or 0)


def cut(src, start, dst):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf",
                    f"select='between(n\\,{start}\\,{start + PIECE - 1})',setpts=N/24/TB", "-r", "24", "-an",
                    "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(dst)], check=True)


def main():
    plan = json.loads(pathlib.Path(sys.argv[1]).read_text())
    raw, out = pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
    (out / "clips").mkdir(parents=True, exist_ok=True)
    data = []
    for i, shot in enumerate(plan["shots"]):
        src = raw / "clips" / f"shot_{i:02d}.mp4"
        if shot.get("skip") or not shot.get("caption") or not src.exists():
            continue
        n = frames_of(src)
        starts = [24, 72] if n >= 121 else [max(0, n - PIECE)]
        for k, s in enumerate(shot.get("pieces", starts)):
            name = f"clips/{shot.get('tag', f'shot{i:02d}')}_{k}.mp4"
            cut(src, s, out / name)
            data.append({"video": name, "caption": shot["caption"]})
    master = ROOT.parent / "videos" / "lora" / "moss-data"
    if (master / "clips" / "moss_00.mp4").exists():
        old = {d["video"]: d["caption"] for d in json.loads((master / "dataset.json").read_text())}
        subprocess.run(["cp", str(master / "clips" / "moss_00.mp4"), str(out / "clips" / "turnaround.mp4")], check=True)
        data.append({"video": "clips/turnaround.mp4", "caption": old["clips/moss_00.mp4"]})
    (out / "dataset.json").write_text(json.dumps(data, indent=1))
    print(len(data), "clips in", out)


if __name__ == "__main__":
    main()
