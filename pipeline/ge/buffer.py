"""Post finished videos to TikTok through Buffer, so nobody has to open TikTok.

  python3 -m ge.buffer queue ../videos/2026-10-17-day-one-infinite-stroll.mp4 ...
  python3 -m ge.buffer queue --per-day 2 ../videos/*.mp4   # ignore plan dates: 2 a day from today
  python3 -m ge.buffer status     # scheduled / sent / failed; frees R2 space once a video is sent
  python3 -m ge.buffer report     # views and comment counts, last 7 days

Buffer's TikTok app passed TikTok's audit, so its posts go public with the AI-generated label on.
(Our own TikTok app never could: TikTok rejects tools that only post to your own account.)
Buffer takes a video URL, not a file, so each video goes to the public R2 bucket first and is
deleted from it once Buffer has sent the post.

Free-tier guards, because R2 has no spending cap: at most MAX_OBJECTS files and MAX_BYTES in the
bucket, MAX_FILE a video, Standard storage only, plus a 30-day expiry rule on the bucket itself.
Buffer's free plan holds 10 scheduled posts a channel; queue stops there.
posts.json maps each video to its Buffer post and R2 key, so a video is never posted twice.

Buffer login: `buffer init` (the owner's API key, in ~/.config/buffer). R2: wrangler's login.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import secrets
import subprocess
import sys
import urllib.request
import zoneinfo

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT.parent / "site"  # wrangler is installed here
POSTS = ROOT / "posts.json"
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())["posting"]

MAX_FILE = 50e6        # a 52 s video is 10-26 MB
MAX_BYTES = 1e9        # 10% of R2's free 10 GB
MAX_OBJECTS = 40       # ~5 weeks of videos; sent ones are deleted
BUFFER_FREE_QUEUE = 10


def sh(*cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode:
        raise RuntimeError(f"{' '.join(cmd[:4])} failed ({r.returncode}): {(r.stderr or r.stdout).strip()[-500:]}")
    return r.stdout


def buffer(*args, payload=None):
    cmd = ["buffer", *args, "--output", "json", "--quiet"]
    if payload is not None:
        cmd += ["--json", json.dumps(payload)]
    return json.loads(sh(*cmd))


def wrangler(*args):
    return sh("npx", "wrangler", *args, cwd=SITE)


def r2_objects():
    """{key: bytes} for every file in the bucket. wrangler can't list a bucket and its bucket info
    lags behind uploads, so this asks the Cloudflare API with wrangler's login."""
    token = wrangler("auth", "token").strip().splitlines()[-1]
    url = (f"https://api.cloudflare.com/client/v4/accounts/{CFG['cloudflare_account']}"
           f"/r2/buckets/{CFG['bucket']}/objects?per_page=1000")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "User-Agent": "trysolarpunk"})
    with urllib.request.urlopen(req) as r:
        body = json.loads(r.read())
    if not body["success"] or body.get("result_info", {}).get("is_truncated"):
        raise RuntimeError(f"R2 listing failed: {body.get('errors') or 'truncated'}")
    return {o["key"]: int(o["size"]) for o in body["result"]}


def check_r2_room(new_bytes):
    objs = r2_objects()
    count, size = len(objs), sum(objs.values())
    if count + 1 > MAX_OBJECTS or size + new_bytes > MAX_BYTES:
        sys.exit(f"R2 guard: bucket has {count} files, {size / 1e6:.0f} MB; limit {MAX_OBJECTS} files, "
                 f"{MAX_BYTES / 1e6:.0f} MB. Run `python3 -m ge.buffer status` to free sent videos.")
    info = json.loads(wrangler("r2", "bucket", "info", CFG["bucket"], "--json"))
    if info["default_storage_class"] != "Standard":
        sys.exit(f"R2 bucket storage class is {info['default_storage_class']}; only Standard is free")


def load():
    return json.loads(POSTS.read_text()) if POSTS.exists() else {}


def save(posts):
    POSTS.write_text(json.dumps(posts, indent=2) + "\n")


def at(date, hhmm):
    return dt.datetime.combine(date, dt.time(*map(int, hhmm.split(":"))), zoneinfo.ZoneInfo(CFG["timezone"]))


def future(when):
    return when > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15)


def due_at(date):
    """The plan's date at Buffer's first posting slot that day, or None (next free queue slot) if past."""
    sched = buffer("channels", "get", "--id", CFG["channel_id"], "--fields", "postingSchedule.day,postingSchedule.times")
    day = date.strftime("%a").lower()
    times = next((s["times"] for s in sched["postingSchedule"] if s["day"] == day and not s.get("paused")), [])
    when = at(date, times[0] if times else CFG["default_time"])
    return when if future(when) else None


def spread(start, per_day, count):
    """count future posting times, per_day a day (config daily_times) from start on."""
    if per_day > len(CFG["daily_times"]):
        sys.exit(f"--per-day {per_day}: config.yaml posting.daily_times has only {len(CFG['daily_times'])} times")
    out, day = [], start
    while len(out) < count:
        out += [w for w in (at(day, t) for t in sorted(CFG["daily_times"][:per_day])) if future(w)][:count - len(out)]
        day += dt.timedelta(days=1)
    return out


def scheduled_count():
    r = buffer("posts", "list", "--fields", "items.id,pageInfo.hasNextPage",
               payload={"organizationId": CFG["organization_id"],
                        "filter": {"channelIds": [CFG["channel_id"]], "status": ["scheduled"]}})
    return len(r["items"]) + (100 if r["pageInfo"]["hasNextPage"] else 0)


def queue(video, when="plan"):
    """when: a datetime, or \"plan\" for the plan's date at Buffer's first slot that day."""
    video = pathlib.Path(video).resolve()
    name, posts = video.stem, load()
    if name in posts:
        print(f"skip    {name}: already queued as post {posts[name]['post_id']}")
        return
    caption = video.with_suffix(".txt").read_text().strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})-", name)
    if not m:
        sys.exit(f"{name}: expected a YYYY-MM-DD- prefix")
    size = video.stat().st_size
    if size > MAX_FILE:
        sys.exit(f"{name}: {size / 1e6:.0f} MB is over the {MAX_FILE / 1e6:.0f} MB guard")
    if scheduled_count() >= BUFFER_FREE_QUEUE:
        sys.exit(f"Buffer's free queue is full ({BUFFER_FREE_QUEUE} scheduled); wait for some to send")
    check_r2_room(size)

    if when == "plan":
        when = due_at(dt.date.fromisoformat(m.group(1)))
    key = f"{name}-{secrets.token_hex(6)}.mp4"  # unguessable, so nobody else can run up reads
    post = {"channelId": CFG["channel_id"], "schedulingType": "automatic", "text": caption,
            "assets": [{"video": {"url": f"{CFG['public_url']}/{key}", "metadata": {"thumbnailOffset": 1000}}}],
            "metadata": {"tiktok": {"isAiGenerated": True}}}
    post |= {"mode": "customScheduled", "dueAt": when.isoformat()} if when else {"mode": "addToQueue"}
    buffer("posts", "create", "--dry-run", payload=post)

    wrangler("r2", "object", "put", f"{CFG['bucket']}/{key}", "--file", str(video), "--remote",
             "--content-type", "video/mp4")
    try:
        r = buffer("posts", "create", "--fields", "post.id,post.status,post.dueAt", payload=post)
        if "post" not in r:
            raise RuntimeError(f"Buffer refused the post: {r}")
    except Exception:
        wrangler("r2", "object", "delete", f"{CFG['bucket']}/{key}", "--remote")
        raise
    posts[name] = {"post_id": r["post"]["id"], "key": key, "due_at": r["post"].get("dueAt"), "status": "scheduled"}
    save(posts)
    print(f"queued  {name}  {r['post'].get('dueAt') or 'next free slot'}  post {r['post']['id']}")


def status():
    posts = load()
    for name, p in sorted(posts.items()):
        if p["status"] != "sent":
            try:
                r = buffer("posts", "get", "--id", p["post_id"], "--fields", "status,dueAt,sentAt,externalLink,error.message")
            except RuntimeError as e:
                r = {"status": "missing", "error": {"message": str(e)[-200:]}}
            p.update(status=r["status"], due_at=r.get("dueAt"), sent_at=r.get("sentAt"), link=r.get("externalLink"))
            if r.get("error"):
                p["error"] = r["error"].get("message")
            if r["status"] in ("sent", "missing") and p.get("key"):
                wrangler("r2", "object", "delete", f"{CFG['bucket']}/{p['key']}", "--remote")
                p["key"] = None
        print(f"{p['status']:<10} {name}  {p.get('sent_at') or p.get('due_at') or ''}  {p.get('link') or p.get('error') or ''}")
    save(posts)
    needed = {p["key"] for p in posts.values() if p.get("key")}
    for key in r2_objects().keys() - needed:  # leftovers from a crash or a deleted post
        wrangler("r2", "object", "delete", f"{CFG['bucket']}/{key}", "--remote")
        print(f"removed stray R2 file {key}")


def report(days=7):
    """Views, comments and likes of the posts sent in the last `days` days, from Buffer's metrics
    (refreshed about once a day). Comment text isn't in Buffer's API yet, only counts."""
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
    r = buffer("posts", "list", "--fields", "items.id,items.text,items.sentAt,items.metrics.type,items.metrics.value,"
               "items.metricsUpdatedAt,pageInfo.hasNextPage",
               payload={"organizationId": CFG["organization_id"], "filter": {
                   "channelIds": [CFG["channel_id"]], "status": ["sent"], "dueAt": {"start": since}}})
    names = {p["post_id"]: n for n, p in load().items()}
    rows = []
    for it in r["items"]:
        m = {x["type"]: x["value"] for x in it.get("metrics") or []}
        rows.append({"name": names.get(it["id"], it["text"][:40]), "sent": it["sentAt"], "views": m.get("views", 0),
                     "comments": m.get("comments", 0), "likes": m.get("reactions", 0), "updated": it.get("metricsUpdatedAt")})
    if r["pageInfo"]["hasNextPage"]:
        print(f"note: more than {len(rows)} posts in {days} days; report shows the first page only")
    return sorted(rows, key=lambda x: x["sent"] or "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("queue", help="upload videos and schedule them on Buffer")
    q.add_argument("videos", nargs="+")
    q.add_argument("--per-day", type=int, help="ignore plan dates: post in file order, this many a day")
    q.add_argument("--start", type=dt.date.fromisoformat, default=dt.date.today(), help="first day for --per-day")
    sub.add_parser("status", help="show post status; delete sent videos from R2")
    rp = sub.add_parser("report", help="views and comment counts of recent posts")
    rp.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    if a.cmd == "queue":
        videos = sorted(a.videos, key=lambda v: pathlib.Path(v).name)
        times = spread(a.start, a.per_day, len(videos)) if a.per_day else ["plan"] * len(videos)
        for v, when in zip(videos, times):
            queue(v, when)
    elif a.cmd == "report":
        rows = report(a.days)
        for x in rows:
            print(f"{x['views']:>7} views {x['comments']:>4} comments {x['likes']:>5} likes  {x['name']}")
        print(f"{sum(x['views'] for x in rows)} views, {sum(x['comments'] for x in rows)} comments, {len(rows)} posts "
              f"in {a.days} days (metrics refresh daily)")
    else:
        status()


if __name__ == "__main__":
    main()
