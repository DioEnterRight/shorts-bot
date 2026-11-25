"""POST VIDEO: runs every 30 min; posts the video of the slot that is due (config.yaml `schedule:`, see schedule.py).

  python -m pipeline.publish          # post the due slot, if any (the scheduled runs)
  python -m pipeline.publish --now    # post the oldest ready video right now (the manual button)

Per-platform state lives on each history entry and is saved after EVERY step, so a crash
or a re-run never posts the same video twice:

  ig_state: posted | manual_notified            (absent = still to do)
  yt_state: posted | private | manual_notified  (absent = still to do)

A video leaves the queue (status=published) once every enabled platform reached a final state.
"""
import datetime as dt
import json
import os
import sys

from . import instagram, schedule, youtube
from .common import OUT, load_config, load_history, log, now_ist, parse_time, run, save_history

IG_DONE = {"posted", "manual_notified"}
YT_DONE = {"posted", "private", "manual_notified"}


def cleanup_old_releases(history, keep_days=14):
    cutoff = now_ist() - dt.timedelta(days=keep_days)
    for v in history["videos"]:
        if v.get("status") == "published" and not v.get("release_deleted"):
            if parse_time(v.get("published_at", v["created"])) < cutoff:
                res = run(["gh", "release", "delete", v["tag"], "--yes", "--cleanup-tag"], check=False)
                if res.returncode == 0:
                    v["release_deleted"] = True


def open_issue_once(title, body):
    """Create a GitHub issue unless an open one with the same title exists (no daily spam)."""
    res = run(["gh", "issue", "list", "--state", "open", "--search", f'"{title}" in:title',
               "--json", "title"], check=False, capture=True)
    if res.returncode == 0:
        try:
            if any(i.get("title") == title for i in json.loads(res.stdout or "[]")):
                log(f"Issue already open: {title}")
                return
        except ValueError:
            pass
    run(["gh", "issue", "create", "--title", title, "--body", body], check=False)


def post_instagram(v, meta, video, cfg, history):
    p = cfg["publish"]
    max_attempts = int(p.get("instagram_max_attempts", 2))
    try:
        existing = instagram.find_existing(meta["caption"])
        if existing:
            log(f"Instagram already has this video ({existing}); recording it instead of re-posting")
            v["ig_media_id"], v["ig_state"] = existing, "posted"
            return None
        url = (f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/releases/download/{v['tag']}/final.mp4"
               if os.environ.get("GITHUB_REPOSITORY") else None)
        v["ig_media_id"], v["ig_link"] = instagram.publish(video, meta["caption"], video_url=url,
                                                           ai_label=meta.get("ai_label_instagram", True))
        v["ig_state"] = "posted"
        return None
    except Exception as e:  # noqa: BLE001
        v["ig_attempts"] = v.get("ig_attempts", 0) + 1
        if v["ig_attempts"] >= max_attempts:
            instagram.notify_manual(meta, v["tag"])
            v["ig_state"] = "manual_notified"
            return f"Instagram failed {v['ig_attempts']}x, manual post requested: {e}"
        return f"Instagram failed (attempt {v['ig_attempts']}/{max_attempts}, will retry next run): {e}"
    finally:
        save_history(history)


def post_youtube(v, meta, video, cfg, history):
    mode = cfg["publish"].get("youtube_mode", "manual")
    try:
        if mode == "manual":
            youtube.notify_manual(meta, v["tag"])
            v["yt_state"] = "manual_notified"
            return None
        existing = youtube.find_existing(meta["title"])
        if existing:
            log(f"YouTube already has this video ({existing}); recording it instead of re-uploading")
            v["yt_video_id"], v["yt_state"] = existing, "posted"
            return None
        vid, privacy = youtube.upload(video, meta)
        v["yt_video_id"] = vid
        if privacy == "public":
            v["yt_state"] = "posted"
            return None
        # Uploading again would only create another locked copy, so this is final. Tell the human once.
        v["yt_state"] = "private"
        open_issue_once("⚠️ YouTube API uploads are staying private",
                        f"Video `{vid}` was uploaded but YouTube kept it **{privacy}**. That happens while the "
                        "Google API audit is not approved. Make it public in YouTube Studio, and set "
                        "`publish → youtube_mode: manual` in config.yaml until the audit passes.")
        return f"YouTube kept {vid} {privacy} (not public)"
    except Exception as e:  # noqa: BLE001
        max_attempts = int(cfg["publish"].get("youtube_max_attempts", 2))
        v["yt_attempts"] = v.get("yt_attempts", 0) + 1
        if v["yt_attempts"] >= max_attempts:
            youtube.notify_manual(meta, v["tag"])
            v["yt_state"] = "manual_notified"
            return f"YouTube failed {v['yt_attempts']}x, manual upload requested: {e}"
        return f"YouTube failed (attempt {v['yt_attempts']}/{max_attempts}, will retry next run): {e}"
    finally:
        save_history(history)


def pick(cfg, history, now, force=False):
    """-> the video to post now, tied to its slot, or None when nothing is due."""
    queued = sorted((v for v in history["videos"] if v.get("status") == "queued"), key=lambda x: x["created"])
    busy = [v for v in queued if v.get("slot")]          # a slot whose posting failed half-way: finish it first
    if busy:
        return busy[0]
    if force:
        slot, lang = now.strftime("%Y-%m-%d %H:%M") + " manual", None
    else:
        hit = schedule.due(cfg, {v.get("slot") for v in history["videos"]} | set(history.get("missed_slots", [])), now)
        if not hit:
            log("No slot due right now.")
            return None
        slot, lang = hit
    same = [v for v in queued if lang is None or v.get("language", "en") == lang]
    if not same and queued:
        log(f"No {lang} video ready for {slot}; posting the oldest ready one instead", "WARN")
        same = queued
    if not same:
        history.setdefault("missed_slots", []).append(slot)
        history["missed_slots"] = history["missed_slots"][-30:]
        save_history(history)
        open_issue_once(f"⚠️ No video ready on {now:%d %b}",
                        f"Nothing was ready for the {slot} slot. Check the latest 'Make video' run under the Actions tab.")
        sys.exit(f"No video ready for {slot}.")
    v = same[0]
    v["slot"] = slot
    save_history(history)
    return v


def main():
    cfg = load_config()
    if cfg.get("paused"):
        log("Paused in config.yaml — not posting.")
        return
    history = load_history()
    v = pick(cfg, history, now_ist(), force="--now" in sys.argv)
    if v is None:
        return
    log(f"Posting {v['id']} [{v.get('language', 'en')}/{v.get('theme', 'explainer')}] for slot {v['slot']}")
    work = OUT / v["id"]
    work.mkdir(parents=True, exist_ok=True)
    run(["gh", "release", "download", v["tag"], "-p", "final.mp4", "-p", "meta.json", "-D", work, "--clobber"])
    meta = json.loads((work / "meta.json").read_text(encoding="utf-8"))
    video = work / "final.mp4"
    p = cfg["publish"]
    errors = []

    if p.get("instagram") and v.get("ig_state") not in IG_DONE:
        err = post_instagram(v, meta, video, cfg, history)
        if err:
            errors.append(err)

    mode = p.get("youtube_mode", "manual")
    if mode != "off" and v.get("yt_state") not in YT_DONE:
        err = post_youtube(v, meta, video, cfg, history)
        if err:
            errors.append(err)

    ig_ok = (not p.get("instagram")) or v.get("ig_state") in IG_DONE
    yt_ok = mode == "off" or v.get("yt_state") in YT_DONE
    if ig_ok and yt_ok:
        v["status"] = "published"
        v["published_at"] = now_ist().isoformat(timespec="minutes")
    cleanup_old_releases(history)
    save_history(history)
    if errors:
        for e in errors:
            log(e, "ERROR")
        sys.exit(1)
    log("All posted.")


if __name__ == "__main__":
    main()
