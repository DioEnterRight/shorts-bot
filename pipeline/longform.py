"""Weekly long video (English, 16:9, YouTube only): the week's best Short, expanded and drawn by toon2d.

    python -m pipeline.longform            # make + upload (Sunday workflow)
    python -m pipeline.longform --test     # offline: sample script, Kokoro, auto storyboard, no upload
    python -m pipeline.longform --no-upload
"""
import argparse
import json
import re
import sys
from datetime import timedelta

from . import analytics, brain, languages, qc, toon2d, voice
from .produce import disclosure
from .common import OUT, ROOT, load_config, load_history, log, now_ist, run, save_history, slugify

SENT = re.compile(r"(?<=[.!?])[\"”’)]*\s+")


def pick_source(history, stats, now, done_topics):
    """Best English Short of the last 7 days (analytics score), else the newest English Short not done yet."""
    week_ago = (now - timedelta(days=7)).isoformat(timespec="minutes")
    cands = [v for v in history["videos"] if v.get("language") == "en" and v.get("status") in ("published", "queued")
             and v.get("topic") not in done_topics]
    if not cands:
        raise RuntimeError("No English Short to expand yet (none published or queued that isn't already a long video)")
    recs = stats.get("videos", {})
    recent = [v for v in cands if v.get("created", "") >= week_ago]
    rated = [v for v in recent if recs.get(v["id"], {}).get("metrics")]
    if rated:
        return max(rated, key=lambda v: brain.score(recs[v["id"]]))
    return max(recent or cands, key=lambda v: v.get("created", ""))


def sentences(text):
    return [s.strip() for s in SENT.split(text.strip()) if s.strip()]


def to_script(longs, src):
    """Long script JSON -> pipeline script (one scene per sentence) + chapter outline for the storyboard."""
    scenes, outline = [], []
    for ch in longs["chapters"]:
        start = len(scenes)
        for para in ch["paragraphs"]:
            scenes += [{"line": s} for s in sentences(para)]
        outline.append(f"Chapter '{ch['title']}': about sentences {start}-{len(scenes) - 1}")
    if len(scenes) < 20:
        raise ValueError(f"Long script too short ({len(scenes)} sentences)")
    return {"topic": src["topic"], "title": longs["title"], "description": longs["description"],
            "hashtags": longs["hashtags"][:10], "facts_checked": longs.get("facts_checked", []),
            "language": "en", "scenes": scenes, "outline": outline}


def write_long_script(cfg, src):
    lc = cfg["longform"]
    minutes = int(lc.get("minutes", 5))
    prompt = (ROOT / "prompts" / "longform_script.md").read_text(encoding="utf-8")
    for k, v in dict(minutes=str(minutes), words=str(minutes * 150), chapters=str(max(2, minutes // 2)),
                     topic=src["topic"], title=src.get("title", ""), hook=src.get("hook_line", ""),
                     category=str(src.get("category", ""))).items():
        prompt = prompt.replace("{" + k + "}", v)
    err = None
    for attempt in range(1, 3):
        log(f"Asking Claude for the long script (attempt {attempt})")
        reply = brain.call_claude(prompt if not err else prompt + f"\n\nYour last reply was invalid ({err}). JSON only.",
                                  tools="WebSearch,WebFetch", max_turns=int(lc.get("max_turns", 30)),
                                  effort=lc.get("effort", "high"), model=lc.get("model"), timeout=1800)
        try:
            return to_script(brain.extract_json(reply), src)
        except Exception as e:  # noqa: BLE001
            err = str(e)[:200]
            log(f"Long script invalid: {err}", "WARN")
    raise RuntimeError(f"Claude could not write the long script: {err}")


def sample(src):
    path = ROOT / "toon2d" / "examples" / "marshmallow" / "script.txt"
    text = path.read_text(encoding="utf-8")
    longs = {"title": "The Marshmallow Test and Your Money", "description": "Test video.", "hashtags": ["#test"],
             "chapters": [{"title": "All", "paragraphs": [ln for ln in text.splitlines() if ln.strip()]}]}
    return to_script(longs, src)


def make(cfg, test=False, upload=True):
    history = load_history()
    stats = analytics.load()
    done = {x.get("topic") for x in history.setdefault("longform", [])}
    if test:
        src = {"topic": "marshmallow test", "id": "test"}
        script = sample(src)
    else:
        src = pick_source(history, stats, now_ist(), done)
        log(f"Long video from Short: {src['topic']}")
        script = write_long_script(cfg, src)
    lp = languages.profile(cfg, "en")
    vid = f"{now_ist():%Y%m%d}-long-{slugify(script['topic'], 28)}"
    work = OUT / vid
    work.mkdir(parents=True, exist_ok=True)
    (work / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
    script.setdefault("theme", "explainer")
    voice_path, timeline, vlen, engine = voice.synthesize(cfg, script, lp, work, allow_edge=not test)
    log(f"Speaking pace: {voice.pace_wpm(timeline):.0f} wpm ({engine}; target 130-145)")
    # the storyboard sees the chapter outline instead of per-line visual hints
    sb_script = dict(script, scenes=[{"visual": o} for o in script["outline"]])
    sample = json.loads((ROOT / "toon2d" / "examples" / "marshmallow" / "story.json").read_text(encoding="utf-8")) if test else None
    final, source = toon2d.render(cfg, sb_script, timeline, voice_path, vlen + 0.7, work, "en",
                                  brain.call_claude, brain.extract_json, use_claude=not test, aspect="16:9", sample=sample)
    dur = qc.check(final, min_s=60, max_s=60 * 20, size=(1920, 1080))
    meta = {"id": vid, "title": script["title"], "description": script["description"],
            "hashtags": script["hashtags"], "language": "en", "duration": round(dur, 2),
            "source_short": src.get("id"), "topic": script["topic"], "storyboard": source, "voice_engine": engine,
            "facts_checked": script["facts_checked"], **disclosure(cfg)}
    (work / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"Long video ready: {final} ({dur / 60:.1f} min, storyboard={source})")
    if test or not upload:
        return final, meta
    from . import youtube
    privacy = cfg["longform"].get("privacy", "private")
    yt_id, status = youtube.upload(final, meta, short=False, privacy=privacy)
    tag = f"long-{vid}"
    run(["gh", "release", "create", tag, final, work / "meta.json", "--title", meta["title"][:100],
         "--notes", f"Weekly long video. YouTube: https://youtu.be/{yt_id} ({status})"])
    history["longform"].append({"id": vid, "topic": script["topic"], "source_short": src.get("id"), "yt_id": yt_id,
                                "privacy": status, "tag": tag, "created": now_ist().isoformat(timespec="minutes")})
    save_history(history)
    return final, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="offline: sample script, Kokoro, auto storyboard, no upload")
    ap.add_argument("--no-upload", action="store_true")
    a = ap.parse_args()
    cfg = load_config()
    if not cfg.get("longform", {}).get("enabled", False) and not a.test:
        log("longform.enabled is false in config.yaml: nothing to do.")
        return
    make(cfg, test=a.test, upload=not a.no_upload)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        log(f"FAILED: {e}", "ERROR")
        sys.exit(1)
