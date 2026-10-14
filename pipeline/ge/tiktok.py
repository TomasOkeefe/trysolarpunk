"""Upload a video with TikTok's Content Posting API.

mode "draft":  sends the video to the creator's TikTok inbox. Works before TikTok's audit.
               You open TikTok, paste the caption, toggle "AI-generated content", and post.
mode "direct": publishes straight to the profile with caption + AIGC label. TikTok only allows
               this publicly after your developer app passes their Content Posting audit;
               before that, direct posts are forced to private.

Env: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN
"""
import json
import os
import pathlib
import time
import urllib.parse
import urllib.request

API = "https://open.tiktokapis.com/v2"


def _post(url, body, token=None, form=False):
    data = urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()
    headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json; charset=UTF-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method="POST")) as r:
        return json.loads(r.read())


def access_token():
    r = _post(f"{API}/oauth/token/", {
        "client_key": os.environ["TIKTOK_CLIENT_KEY"], "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
        "grant_type": "refresh_token", "refresh_token": os.environ["TIKTOK_REFRESH_TOKEN"]}, form=True)
    if "access_token" not in r:
        raise RuntimeError(f"TikTok token refresh failed: {r}")
    if r.get("refresh_token") and r["refresh_token"] != os.environ["TIKTOK_REFRESH_TOKEN"]:
        # refresh tokens rotate; surface the new one so the workflow can store it
        pathlib.Path("out").mkdir(exist_ok=True)
        pathlib.Path("out/new_refresh_token").write_text(r["refresh_token"])
    return r["access_token"]


def upload(video, plan, mode="draft"):
    tok = access_token()
    size = pathlib.Path(video).stat().st_size
    source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}
    if mode == "direct":
        caption = f"{plan['caption']} {' '.join(plan['hashtags'])}"[:2200]
        info = _post(f"{API}/post/publish/creator_info/query/", {}, tok)["data"]
        privacy = "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in info["privacy_level_options"] else "SELF_ONLY"
        body = {"post_info": {"title": caption, "privacy_level": privacy, "is_aigc": True,
                              "disable_comment": False, "disable_duet": False, "disable_stitch": False},
                "source_info": source}
        r = _post(f"{API}/post/publish/video/init/", body, tok)
    else:
        r = _post(f"{API}/post/publish/inbox/video/init/", {"source_info": source}, tok)
    if r.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok init failed: {r}")
    up, pid = r["data"]["upload_url"], r["data"]["publish_id"]
    req = urllib.request.Request(up, data=pathlib.Path(video).read_bytes(), method="PUT", headers={
        "Content-Type": "video/mp4", "Content-Length": str(size), "Content-Range": f"bytes 0-{size - 1}/{size}"})
    urllib.request.urlopen(req).read()
    for _ in range(30):
        time.sleep(10)
        s = _post(f"{API}/post/publish/status/fetch/", {"publish_id": pid}, tok)["data"]
        if s.get("status") in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
            return s
        if s.get("status") == "FAILED":
            raise RuntimeError(f"TikTok processing failed: {s}")
    return s
