"""YouTube publishing safety controller (ported from FlatFrameDocs/flatframe/yt_guard.py).

Two separate limits:
  A. API project quota: Google's default (checked Nov 2026) is a separate bucket of 100 videos.insert calls per day,
     reset at midnight Pacific. Every insert CALL is counted per Pacific day; `quotaExceeded` pauses until the reset.
  B. Channel daily upload limit: set by YouTube per channel, not exposed by the API. Our own cap
     (publish.youtube_channel_daily_cap, successful uploads per ROLLING 24 h). `uploadLimitExceeded` is final:
     no retry, publishing paused >= 24 h, a GitHub issue, never another route around it.

Before each upload the ledger is reconciled with the authenticated channel's uploads playlist, so uploads made by hand or
by any other repository on the same channel count too, and the ledger refuses a channel it does not belong to.
State: data/youtube_ledger.json (saved with the rest of the bot state). There is no force option.
"""
import datetime as dt
import json

from . import common

LEDGER = "youtube_ledger.json"
DEFAULTS = {"youtube_channel_daily_cap": 1, "youtube_api_daily_insert_cap": 100, "youtube_pause_hours": 24,
            "youtube_require_quota_clearance": True, "youtube_channel_id": ""}


def _utc(t):
    if isinstance(t, str):
        t = dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc)


def _iso(t):
    return _utc(t).isoformat(timespec="seconds")


def pacific(t):
    t = _utc(t)

    def nth_sunday(month, n):
        d = dt.date(t.year, month, 1)
        d += dt.timedelta(days=(6 - d.weekday()) % 7)
        return d + dt.timedelta(weeks=n - 1)
    start = dt.datetime.combine(nth_sunday(3, 2), dt.time(10), tzinfo=dt.timezone.utc)
    end = dt.datetime.combine(nth_sunday(11, 1), dt.time(9), tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone(dt.timedelta(hours=-7 if start <= t < end else -8)))


def quota_day(t):
    return pacific(t).date().isoformat()


def next_quota_reset(t, minutes=10):
    day = pacific(t).date() + dt.timedelta(days=1)
    guess = dt.datetime.combine(day, dt.time(0, minutes), tzinfo=pacific(t).tzinfo)
    return _utc(dt.datetime.combine(day, dt.time(0, minutes), tzinfo=pacific(guess).tzinfo))


def empty_ledger():
    return {"version": 1, "channel_id": None, "uploads": [], "insert_calls": [], "attempts": [], "rejected": [],
            "errors": [], "pause": None, "pending": None, "last_reconcile": None}


def load():
    led = common.read_json(common.DATA / LEDGER, empty_ledger())
    for k, v in empty_ledger().items():
        led.setdefault(k, v)
    return led


def save(led):
    common.write_json(common.DATA / LEDGER, led)


def classify(error):
    """HttpError -> 'upload_limit' | 'quota' | 'auth' | 'transient' | 'other'."""
    status = getattr(getattr(error, "resp", None), "status", None)
    content = getattr(error, "content", None)
    text = content.decode("utf-8", "replace") if isinstance(content, (bytes, bytearray)) else str(content or "")
    text = text or str(error)
    reasons = set()
    try:
        reasons = {e.get("reason") for e in json.loads(text).get("error", {}).get("errors", [])}
    except (ValueError, AttributeError):
        pass
    if "uploadLimitExceeded" in reasons or "uploadLimitExceeded" in text:
        return "upload_limit"
    if reasons & {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"} or "quotaExceeded" in text:
        return "quota"
    if status == 401:
        return "auth"
    if status in (500, 502, 503, 504):
        return "transient"
    return "other"


class Guard:
    def __init__(self, cfg, ledger=None, now=None, repo=""):
        self.p = {**DEFAULTS, **(cfg.get("publish") or {})}
        self.led = ledger if ledger is not None else load()
        self.now = _utc(now or dt.datetime.now(dt.timezone.utc))
        self.repo = repo

    def successes_24h(self):
        cut = self.now - dt.timedelta(hours=24)
        return [u for u in self.led["uploads"] if _utc(u["ts"]) > cut]

    def inserts_today(self):
        day = quota_day(self.now)
        return [c for c in self.led["insert_calls"] if quota_day(c["ts"]) == day]

    def paused(self):
        p = self.led.get("pause")
        return p if p and _utc(p["until"]) > self.now else None

    def clearance(self, video):
        reasons = []
        p = self.paused()
        if p:
            reasons.append(f"publishing paused until {p['until']} ({p['reason']})")
        n, cap = len(self.successes_24h()), int(self.p["youtube_channel_daily_cap"])
        if n >= cap:
            reasons.append(f"channel cap: {n} successful upload(s) in the last 24 h (cap {cap})")
        calls = len(self.inserts_today())
        if calls >= int(self.p["youtube_api_daily_insert_cap"]):
            reasons.append(f"API insert allowance used: {calls} call(s) this Pacific day")
        if self.p.get("youtube_require_quota_clearance"):
            day = quota_day(self.now)
            if any(e["kind"] == "quota" and quota_day(e["ts"]) == day for e in self.led["errors"]):
                reasons.append("quotaExceeded earlier this Pacific quota day")
        if any(u.get("local_id") == video.get("id") for u in self.led["uploads"]) or video.get("yt_video_id"):
            reasons.append("this video is already on YouTube")
        if self.led.get("pending"):
            reasons.append("an upload is still marked pending")
        return (not reasons), reasons

    def reconcile(self, channel_id, recent, history):
        want = self.p.get("youtube_channel_id") or ""
        if want and channel_id != want:
            raise PermissionError(f"authenticated channel {channel_id} is not publish.youtube_channel_id {want}")
        if self.led.get("channel_id") and self.led["channel_id"] != channel_id:
            raise PermissionError(f"YouTube credentials now point at {channel_id}, but this ledger belongs to {self.led['channel_id']}")
        self.led["channel_id"] = channel_id
        known = {u["video_id"] for u in self.led["uploads"]}
        key = lambda t: common.norm_text(str(t).lower().replace("#shorts", ""))
        titles = {key(v.get("title", "")): v for v in history["videos"]}
        for r in recent:
            if r["video_id"] in known:
                continue
            local = titles.get(key(r["title"]))
            pend = self.led.get("pending")
            if pend and local and local.get("id") == pend["local_id"]:
                self.led["pending"] = None
                local["yt_video_id"], local["yt_state"] = r["video_id"], "posted"
            self.led["uploads"].append({"ts": _iso(r["published_at"]), "video_id": r["video_id"],
                                        "local_id": local.get("id") if local else None,
                                        "source": "this-repo" if local else "channel (other repo or manual)"})
        pend = self.led.get("pending")
        if pend and self.now - _utc(pend["started"]) > dt.timedelta(hours=2):
            self.led["pending"] = None
        self.led["last_reconcile"] = _iso(self.now)

    def begin(self, video):
        self.led["pending"] = {"local_id": video["id"], "started": _iso(self.now), "repo": self.repo}
        self.led["insert_calls"].append({"ts": _iso(self.now), "local_id": video["id"]})
        self.led["attempts"].append({"ts": _iso(self.now), "local_id": video["id"], "result": "started"})

    def success(self, video, video_id):
        self.led["pending"] = None
        self.led["uploads"].append({"ts": _iso(self.now), "video_id": video_id, "local_id": video["id"], "source": "this-repo"})
        self.led["attempts"][-1]["result"] = "ok"

    def failure(self, video, kind, detail):
        self.led["pending"] = None
        if self.led["attempts"]:
            self.led["attempts"][-1]["result"] = kind
        self.led["errors"].append({"ts": _iso(self.now), "local_id": video["id"], "kind": kind, "detail": str(detail)[:500]})
        if kind == "upload_limit":
            hours = max(24, int(self.p["youtube_pause_hours"]))
            self.led["pause"] = {"until": _iso(self.now + dt.timedelta(hours=hours)), "reason": "uploadLimitExceeded",
                                 "set_at": _iso(self.now), "detail": str(detail)[:300]}
        elif kind == "quota":
            self.led["pause"] = {"until": _iso(next_quota_reset(self.now)), "reason": "quotaExceeded",
                                 "set_at": _iso(self.now), "detail": str(detail)[:300]}
        return self.led["pause"]

    def reject(self, video, reasons):
        self.led["rejected"] = (self.led["rejected"] + [{"ts": _iso(self.now), "local_id": video.get("id"), "reasons": reasons[:4]}])[-200:]

    def prune(self, days=30):
        cut = self.now - dt.timedelta(days=days)
        for k in ("uploads", "insert_calls", "attempts", "errors", "rejected"):
            self.led[k] = [x for x in self.led[k] if _utc(x["ts"]) > cut]
