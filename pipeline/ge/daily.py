"""Daily housekeeping for the TikTok account, run by launchd (com.trysolarpunk.daily, 10:00).

- Refreshes post status and deletes sent videos from R2 (ge.buffer status).
- Watches Buffer's API changelog for comment or DM endpoints and notifies once when one appears,
  so comment replies can be automated the day Buffer ships them.
- Mondays: one notification with last week's posts, views and comment counts. Weekly on purpose:
  the owner is quitting the feed, not swapping it for a stats feed.

State (changelog lines already seen) lives in daily_state.json, gitignored.
"""
import datetime as dt
import json
import pathlib
import re
import subprocess
import traceback
import urllib.request

from ge import buffer

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / "daily_state.json"
CHANGELOG = "https://developers.buffer.com/changelog.md"
WATCH = re.compile(r"`(Query|Mutation)\.\w*(comment|engagement|repl|conversation|message|inbox)\w*`.*was added", re.I)


def notify(msg):
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Try Solarpunk"'], capture_output=True)


def new_comment_api(state):
    req = urllib.request.Request(CHANGELOG, headers={"User-Agent": "trysolarpunk"})
    with urllib.request.urlopen(req, timeout=60) as r:
        hits = [line.strip() for line in r.read().decode().splitlines() if WATCH.search(line)]
    seen = state.setdefault("seen", [])
    new = [h for h in hits if h not in seen]
    seen += new
    return new


def main():
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    log = lambda m: print(f"[{dt.datetime.now():%Y-%m-%d %H:%M}] {m}", flush=True)
    try:
        buffer.status()
    except Exception:
        log(traceback.format_exc())
        notify("Daily check: Buffer status failed, see /tmp/trysolarpunk-daily.log")
    try:
        new = new_comment_api(state)
        if new:
            log("Buffer API added:\n" + "\n".join(new))
            notify(f"Buffer's API can now do comments/DMs ({len(new)} new). Ask Claude to automate replies.")
    except Exception:
        log(traceback.format_exc())
    if dt.date.today().weekday() == 0 and state.get("reported") != str(dt.date.today()):
        try:
            rows = buffer.report(7)
            top = max(rows, key=lambda x: x["comments"], default=None)
            msg = (f"Last week: {len(rows)} posts, {sum(x['views'] for x in rows)} views, "
                   f"{sum(x['comments'] for x in rows)} comments")
            if top and top["comments"]:
                msg += f". Most talked about: {top['name']}"
            log(msg)
            notify(msg)
            state["reported"] = str(dt.date.today())
        except Exception:
            log(traceback.format_exc())
    STATE.write_text(json.dumps(state, indent=1) + "\n")


if __name__ == "__main__":
    main()
