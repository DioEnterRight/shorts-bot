"""POST VIDEO: takes the oldest ready video and posts it."""
import datetime as dt
import json
import sys

from . import instagram, youtube
from .common import OUT, env, load_config, load_history, log, now_ist, run, save_history


def cleanup_old_releases(history, keep_days=14):
    cutoff = now_ist() - dt.timedelta(days=keep_days)
    for v in history["videos"]:
        if v.get("status") == "published" and not v.get("release_deleted"):
            when = dt.datetime.fromisoformat(v.get("published_at", v["created"]))
            if when < cutoff:
                res = run(["gh", "release", "delete", v["tag"], "--yes", "--cleanup-tag"], check=False)
                if res.returncode == 0:
                    v["release_deleted"] = True


def main():
    cfg = load_config()
    if cfg.get("paused"):
        log("Paused in config.yaml — not posting.")
        return
    history = load_history()
    queued = [v for v in history["videos"] if v.get("status") == "queued"]
    if not queued:
        run(["gh", "issue", "create", "--title", f"⚠️ No video ready on {now_ist():%d %b}",
             "--body", "The bot had nothing to post today. Check the latest 'Make video' run under the Actions tab."],
            check=False)
        sys.exit("No video ready to post.")
    v = sorted(queued, key=lambda x: x["created"])[0]
    log(f"Posting {v['id']}")
    work = OUT / v["id"]
    work.mkdir(parents=True, exist_ok=True)
    run(["gh", "release", "download", v["tag"], "-p", "final.mp4", "-p", "meta.json", "-D", work, "--clobber"])
    meta = json.loads((work / "meta.json").read_text())
    video = work / "final.mp4"
    errors = []
    p = cfg["publish"]

    if p.get("instagram") and not v.get("ig_media_id"):
        try:
            v["ig_media_id"], v["ig_link"] = instagram.publish(video, meta["caption"])
        except Exception as e:  # noqa: BLE001
            errors.append(f"Instagram: {e}")

    mode = p.get("youtube_mode", "manual")
    if mode != "off" and not v.get("yt_done"):
        try:
            if mode == "api":
                v["yt_video_id"] = youtube.upload(video, meta)
            else:
                youtube.notify_manual(meta, v["tag"])
            v["yt_done"] = True
        except Exception as e:  # noqa: BLE001
            errors.append(f"YouTube: {e}")

    ig_ok = (not p.get("instagram")) or v.get("ig_media_id")
    yt_ok = mode == "off" or v.get("yt_done")
    if ig_ok and yt_ok:
        v["status"] = "published"
        v["published_at"] = now_ist().isoformat(timespec="minutes")
    cleanup_old_releases(history)
    save_history(history)
    if errors:
        for e in errors:
            log(f"ERROR {e}")
        sys.exit(1)
    log("All posted.")


if __name__ == "__main__":
    main()
