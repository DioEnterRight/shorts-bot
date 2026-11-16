"""STATS: pulls views/likes/shares/watch-time into data/analytics.json and recomputes the
language allocation. Missing permissions or API errors never stop video production.

data/analytics.json (versioned):
  videos[<id>]: video_id, language, topic, theme, published_at, last_update,
                views {yt, ig}, views_day7 {yt, ig}, metrics {...all platform numbers...}
  allocation.language: shares, diagnostics, computed_at
"""
from . import allocation, instagram, youtube
from .common import DATA, env, load_config, load_history, log, now_ist, parse_time, read_json, save_history, write_json

PATH = DATA / "analytics.json"
VERSION = 1


def load():
    a = read_json(PATH, {})
    a.setdefault("version", VERSION)
    a.setdefault("videos", {})
    a.setdefault("allocation", {})
    return a


def save(a):
    a["version"] = VERSION
    a["updated"] = now_ist().isoformat(timespec="minutes")
    write_json(PATH, a)


def _record(a, v):
    rec = a["videos"].setdefault(v["id"], {"video_id": v["id"]})
    rec.update({"language": v.get("language", "en"), "topic": v.get("topic"), "theme": v.get("theme", "explainer"),
                "title": v.get("title"), "hook_type": v.get("hook_type"), "hook_line": v.get("hook_line"),
                "duration": v.get("duration"), "published_at": v.get("published_at")})
    rec.setdefault("metrics", {})
    return rec


def migrate_from_history(a, history):
    """History v1 kept metrics inline; move them here once."""
    moved = 0
    for v in history["videos"]:
        if v.get("metrics"):
            rec = _record(a, v)
            rec["metrics"].update(v.pop("metrics"))
            if v.get("metrics_day7"):
                rec["metrics_day7"] = v.pop("metrics_day7")
            v.pop("metrics_age_days", None)
            moved += 1
    return moved


def _views(m):
    out = {}
    if "yt_views" in m and m.get("yt_privacy", "public") == "public":
        out["yt"] = m["yt_views"]
    if "ig_views" in m:
        out["ig"] = m["ig_views"]
    return out


def records_for_allocation(a, now):
    out = []
    for rec in a["videos"].values():
        if not rec.get("published_at"):
            continue
        age = (now - parse_time(rec["published_at"])).total_seconds() / 86400
        out.append({"language": rec.get("language", "en"), "age_days": age, "views": _views(rec.get("metrics", {})),
                    "views_day7": _views(rec["metrics_day7"]) if rec.get("metrics_day7") else None})
    return out


def update_allocation(a, cfg, now=None):
    now = now or now_ist()
    langs = list(cfg["languages"]["enabled"])
    s = allocation.settings(cfg)
    prev = (a["allocation"].get("language") or {}).get("shares")
    shares, diag = allocation.language_shares(records_for_allocation(a, now), langs, s, prev)
    a["allocation"]["language"] = {"shares": {k: round(v, 4) for k, v in shares.items()}, "diagnostics": diag,
                                   "computed_at": now.isoformat(timespec="minutes")}
    log(f"Language shares: {a['allocation']['language']['shares']} ({diag.get('reason')})")
    return shares


def collect(a, history):
    """Refresh metrics of every published video. Each source fails independently."""
    published = [v for v in history["videos"] if v.get("status") == "published"]
    if not published:
        log("No published videos yet.")
        return
    for v in published:
        _record(a, v)
    if env("IG_PAGE_TOKEN"):
        for v in published:
            if v.get("ig_media_id"):
                try:
                    a["videos"][v["id"]]["metrics"].update(instagram.insights(v["ig_media_id"]))
                except Exception as e:  # noqa: BLE001
                    log(f"IG stats failed for {v['id']}: {e}", "WARN")
    try:
        yt = youtube.stats(published)  # refreshed every run, so stored YouTube data never goes stale
        for v in published:
            if v.get("yt_video_id") in yt:
                a["videos"][v["id"]]["metrics"].update(yt[v["yt_video_id"]])
    except Exception as e:  # noqa: BLE001
        log(f"YouTube stats skipped: {e}", "WARN")
        if "invalid_grant" in str(e):
            # Access was revoked in Google security settings -> delete stored YouTube data (Developer Policies III.D)
            for v in history["videos"]:
                v.pop("yt_video_id", None)
            for rec in a["videos"].values():
                for key in ("metrics", "metrics_day7"):
                    for k in [k for k in (rec.get(key) or {}) if k.startswith("yt_")]:
                        rec[key].pop(k)
            log("YouTube access revoked: stored YouTube data deleted.", "WARN")
    now = now_ist()
    for v in published:
        rec = a["videos"][v["id"]]
        rec["last_update"] = now.isoformat(timespec="minutes")
        rec["views"] = _views(rec["metrics"])
        age = (now - parse_time(v["published_at"])).days
        if age >= 7 and "metrics_day7" not in rec and rec["metrics"]:
            rec["metrics_day7"] = dict(rec["metrics"])
            rec["views_day7"] = _views(rec["metrics_day7"])
    log(f"Stats updated for {len(published)} video(s).")


def main():
    cfg = load_config()
    history = load_history()
    a = load()
    if migrate_from_history(a, history):
        log("Moved metrics from history.json into analytics.json")
    try:
        collect(a, history)
    finally:
        update_allocation(a, cfg)
        save(a)
        save_history(history)


if __name__ == "__main__":
    main()
