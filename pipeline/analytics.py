"""STATS: pulls views/likes/shares/watch-time for recent videos into data/history.json.
Claude reads these every morning to decide what to make next."""
import datetime as dt

from . import instagram, youtube
from .common import env, load_history, log, now_ist, save_history


def main():
    history = load_history()
    cutoff = now_ist() - dt.timedelta(days=30)
    # YouTube Developer Policies III.E.4: don't keep YouTube data older than 30 days unrefreshed.
    # Old videos keep only their aggregate stats (allowed for authorized analytics); the YouTube video ID is removed.
    for v in history["videos"]:
        if v.get("published_at") and dt.datetime.fromisoformat(v["published_at"]) <= cutoff:
            v.pop("yt_video_id", None)
    recent = [v for v in history["videos"] if v.get("status") == "published"
              and dt.datetime.fromisoformat(v["published_at"]) > cutoff]
    if not recent:
        log("No published videos in the last 30 days yet.")
        return
    if env("IG_PAGE_TOKEN"):
        for v in recent:
            if v.get("ig_media_id"):
                try:
                    v.setdefault("metrics", {}).update(instagram.insights(v["ig_media_id"]))
                except Exception as e:  # noqa: BLE001
                    log(f"IG stats failed for {v['id']}: {e}")
    try:
        yt = youtube.stats(recent)
        for v in recent:
            if v.get("yt_video_id") in yt:
                v.setdefault("metrics", {}).update(yt[v["yt_video_id"]])
    except Exception as e:  # noqa: BLE001
        log(f"YouTube stats skipped: {e}")
        if "invalid_grant" in str(e):
            # Access was revoked in Google security settings -> delete stored YouTube data (Developer Policies III.D)
            for v in history["videos"]:
                v.pop("yt_video_id", None)
                for k in [k for k in v.get("metrics", {}) if k.startswith("yt_")]:
                    v["metrics"].pop(k)
            log("YouTube access revoked: stored YouTube data deleted.")
    for v in recent:
        if v.get("metrics"):
            age = (now_ist() - dt.datetime.fromisoformat(v["published_at"])).days
            v["metrics_age_days"] = age
            if age >= 7 and "metrics_day7" not in v:
                v["metrics_day7"] = dict(v["metrics"])
    save_history(history)
    log(f"Stats updated for {len(recent)} video(s).")


if __name__ == "__main__":
    main()
