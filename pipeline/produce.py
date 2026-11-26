"""MAKE VIDEO: slot (language + theme) -> idea -> script -> voice -> animated-shorts-kit studio -> check -> queue.

  python -m pipeline.produce --test                 # offline test: sample script + sample shot plan, Kokoro, no keys
  python -m pipeline.produce --test --language hi   # same, Hindi sample
  python -m pipeline.produce --release              # real run: Claude, queued as a GitHub Release
"""
import argparse
import json
import shutil
import sys
import time

from . import allocation, analytics, brain, branding, ideas, languages, qc, schedule, studio, toon2d, voice
from .common import DATA, OUT, ROOT, load_config, load_history, log, now_ist, run, save_history, slugify


def recent_sequence(history, key, default):
    made = [v for v in history["videos"] if v.get("status") != "discarded"]
    made.sort(key=lambda v: v.get("created", ""))
    return [v.get(key, default) for v in made]


def choose_theme(cfg, history):
    """Which theme the next video gets (deterministic shares from config.yaml themes, see allocation.py)."""
    tshares = {k: float(t.get("share", 0)) for k, t in cfg["themes"].items() if float(t.get("share", 0)) > 0}
    tot = sum(tshares.values())
    return allocation.pick({k: v / tot for k, v in tshares.items()}, recent_sequence(history, "theme", "explainer"), window=20)


def disclosure(cfg):
    """Platform AI-disclosure flags. The video is a 2D cartoon (not photoreal); the voice is synthetic."""
    d = cfg.get("disclosure") or {}
    return {"synthetic_youtube": bool(d.get("youtube_synthetic", False)),
            "ai_label_instagram": bool(d.get("instagram_ai_label", True))}


def make_script(cfg, history, stats, lp, theme, test):
    if test:
        return brain.sample_script(cfg, lp, theme), None
    perf = brain.performance_summary(stats, lp["code"])
    idea = ideas.generate(cfg, history, theme, lp, perf, brain.call_claude, brain.extract_json)
    return brain.write_script(cfg, idea, lp, theme, perf), idea


def produce_one(cfg, history, stats, test, language, theme=None):
    stamp = now_ist().strftime("%Y%m%d-%H%M%S")
    theme = theme or choose_theme(cfg, history)
    lp = languages.profile(cfg, language)
    log(f"Slot: language={language} theme={theme}")
    script, idea = make_script(cfg, history, stats, lp, theme, test)
    script = branding.add_outro(cfg, script)   # last ~3 s: the main character says "Follow Cons and Coins, and @outrichguy"
    lp = languages.profile(cfg, script["language"])
    vid_id = f"{stamp}-{script['language']}-{slugify(script['topic'], 28)}"
    work = OUT / vid_id
    work.mkdir(parents=True, exist_ok=True)
    (work / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"=== Making {vid_id} ===")

    voice_path, timeline, vlen, voice_engine = voice.synthesize(cfg, script, lp, work, allow_edge=not test)
    log(f"Speaking pace: {voice.pace_wpm(timeline):.0f} wpm ({voice_engine}; target {float(lp['words_per_second']) * 60:.0f} = languages.{lp['code']}.words_per_second)")
    (work / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False), encoding="utf-8")
    try:   # the head skill's studio (animated-shorts-kit); test mode uses the hand-made sample shot plan
        plan = json.loads((ROOT / "prompts" / "sample_plan.json").read_text(encoding="utf-8")) if test else None
        final = studio.make(cfg, script, timeline, voice_path, work, call_claude=None if test else brain.call_claude, plan=plan)
        qc.check(final, fps=cfg["video"]["fps"])
        storyboard = "kit"
    except Exception as e:  # noqa: BLE001 - the day's Short still ships, drawn by the emergency 2D engine
        if test:
            raise
        log(f"studio failed ({str(e)[:300]}); making this Short with the emergency 2D engine", "WARN")
        final, storyboard = toon2d.render(cfg, script, studio.caption_timeline(script, timeline), voice_path, vlen + 0.7, work, lp["code"],
                                          brain.call_claude, brain.extract_json, use_claude=True)
    final = branding.apply(cfg, final, studio.caption_timeline(script, timeline), work / "branded.mp4")
    duration = qc.check(final, fps=cfg["video"]["fps"])
    shutil.move(final, work / "final.mp4")
    final = work / "final.mp4"

    caption = f"{script['title']}\n\n{script['description']}\n\n{' '.join(script['hashtags'])}".strip()
    meta = {
        "id": vid_id, "title": script["title"], "description": script["description"],
        "hashtags": script["hashtags"], "caption": caption, "duration": round(duration, 2),
        "language": script["language"], "theme": script["theme"],
        "topic": script["topic"], "canonical_en": script.get("canonical_en"), "category": script.get("category"),
        "hook_type": script.get("hook_type"), "hook_line": script["scenes"][0]["line"],
        "scenes": len(script["scenes"]), "facts_checked": script.get("facts_checked", []),
        "storyboard": storyboard, "voice_engine": voice_engine, **disclosure(cfg),
    }
    (work / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return work, meta, script, idea


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="offline test (sample script, no Claude/keys)")
    ap.add_argument("--release", action="store_true", help="queue result as a GitHub Release")
    ap.add_argument("--language", default=None, help="make one video in this language (en / hi); default: what the schedule needs")
    ap.add_argument("--theme", default=None, help="force a theme from config.yaml -> themes")
    args = ap.parse_args()

    cfg = load_config()
    if cfg.get("paused") and not args.test:
        log("Paused in config.yaml — nothing to do.")
        return
    if args.test and args.release:
        sys.exit("--test and --release cannot be combined")
    history = load_history()
    stats = analytics.load()
    queued = [v for v in history["videos"] if v.get("status") == "queued"]
    todo = [args.language or "en"] if args.test else [args.language] if args.language else schedule.to_make(cfg, queued, now_ist())
    if not todo:
        log(f"The next uploads are covered ({len(queued)} ready). Nothing to make now.")
        return
    log(f"Videos ready: {len(queued)}. Making {len(todo)}: {', '.join(todo)}")

    made, failed = 0, []
    for language in todo:
        try:   # one bad video (or a GitHub hiccup) must not cost the others
            work, meta, script, idea = produce_one(cfg, history, stats, args.test, language, args.theme)
            if args.release:
                queue(history, work, meta, script, idea)
            made += 1
            log(f"Done: {work / 'final.mp4'}")
        except Exception as e:  # noqa: BLE001
            if args.test:
                raise
            failed.append(language)
            log(f"FAILED ({language}): {str(e)[:400]}", "ERROR")
    log(f"Made {made} video(s)." + (f" Failed: {', '.join(failed)}." if failed else ""))
    if failed:
        sys.exit(f"{len(failed)} video(s) failed: see the log above")


def upload_release(tag, files, title, notes, tries=5):
    """GitHub Release with retries: uploads.github.com sometimes answers 502/500. A half-made release is deleted
    before the next try, so the tag never points at a release without its video."""
    for attempt in range(1, tries + 1):
        try:
            run(["gh", "release", "create", tag, *files, "--title", title, "--notes", notes])
            return
        except RuntimeError as e:
            if attempt == tries:
                raise
            wait = 20 * attempt
            log(f"GitHub release upload failed (try {attempt}/{tries}: {str(e)[-200:]}); retrying in {wait} s", "WARN")
            run(["gh", "release", "delete", tag, "--yes", "--cleanup-tag"], check=False)
            time.sleep(wait)


def queue(history, work, meta, script, idea):
    """the finished video -> GitHub Release (the queue) + history + idea ledger + playbook"""
    tag = f"vid-{meta['id']}"
    upload_release(tag, [work / "final.mp4", work / "meta.json"], meta["title"][:100], meta["caption"][:2000])
    history["videos"].append({**{k: meta[k] for k in (
        "id", "title", "topic", "canonical_en", "language", "theme", "category", "hook_type",
        "hook_line", "duration", "storyboard")},
        "tag": tag, "status": "queued", "created": now_ist().isoformat(timespec="minutes")})
    save_history(history)
    led = ideas.load()
    ideas.record(led, idea or {"canonical_en": meta["canonical_en"]}, meta["language"], meta["theme"], meta["id"])
    ideas.save(led)
    if script.get("playbook_update", "").strip():
        (DATA / "playbook.md").write_text(f"<!-- reviewed {now_ist():%Y-%m-%d} -->\n" + script["playbook_update"].strip() + "\n",
                                          encoding="utf-8")
        log("Playbook updated")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        log(f"FAILED: {e}", "ERROR")
        sys.exit(1)
