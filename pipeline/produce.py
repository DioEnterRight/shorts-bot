"""MAKE VIDEO: slot (language + theme) -> idea -> script -> voice -> toon2d storyboard + render -> check -> queue.

  python -m pipeline.produce --test                 # offline test: sample script, Kokoro, auto storyboard, no keys
  python -m pipeline.produce --test --language hi   # same, Hindi sample
  python -m pipeline.produce --release              # real run: Claude, queued as a GitHub Release
"""
import argparse
import json
import shutil
import sys

from . import allocation, analytics, brain, cartoon3d, ideas, languages, qc, toon2d, voice
from .common import DATA, OUT, ROOT, load_config, load_history, log, now_ist, parse_time, run, save_history, slugify


def recent_sequence(history, key, default):
    made = [v for v in history["videos"] if v.get("status") != "discarded"]
    made.sort(key=lambda v: v.get("created", ""))
    return [v.get(key, default) for v in made]


def choose_slot(cfg, history, stats, language=None, theme=None):
    """Which language and theme the next video gets (deterministic, see allocation.py)."""
    s = allocation.settings(cfg)
    alloc = cfg.get("allocation", {})
    if not language and alloc.get("mode") == "weekly":
        made = [(parse_time(v["created"]), v.get("language", "en")) for v in history["videos"]
                if v.get("status") != "discarded" and v.get("created")]
        language = allocation.weekly_pick(made, now_ist(), alloc["main"], alloc["weekly_quota"], alloc.get("quota_day", "wed"))
    if not language:
        shares = (stats.get("allocation", {}).get("language") or {}).get("shares")
        langs = languages.enabled(cfg)
        if not shares or set(shares) != set(langs):
            shares = {k: 1 / len(langs) for k in langs}
        language = allocation.pick(shares, recent_sequence(history, "language", "en"), floor=s["floor"])
    if not theme:
        tshares = {k: float(t.get("share", 0)) for k, t in cfg["themes"].items() if float(t.get("share", 0)) > 0}
        tot = sum(tshares.values())
        theme = allocation.pick({k: v / tot for k, v in tshares.items()},
                                recent_sequence(history, "theme", "explainer"), window=20)
    return language, theme


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


def produce_one(cfg, history, stats, test, language=None, theme=None):
    stamp = now_ist().strftime("%Y%m%d-%H%M%S")
    language, theme = choose_slot(cfg, history, stats, language, theme)
    lp = languages.profile(cfg, language)
    log(f"Slot: language={language} theme={theme}")
    script, idea = make_script(cfg, history, stats, lp, theme, test)
    lp = languages.profile(cfg, script["language"])
    vid_id = f"{stamp}-{script['language']}-{slugify(script['topic'], 28)}"
    work = OUT / vid_id
    work.mkdir(parents=True, exist_ok=True)
    (work / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"=== Making {vid_id} ===")

    voice_path, timeline, vlen, voice_engine = voice.synthesize(cfg, script, lp, work, allow_edge=not test)
    log(f"Speaking pace: {voice.pace_wpm(timeline):.0f} wpm ({voice_engine}; target 160-180)")
    (work / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False), encoding="utf-8")
    final = None
    if cfg["video"].get("style", "toon2d") == "cartoon3d":
        try:
            if test:   # the kit's own example story, voiced offline: proves the 3D toolchain without Claude
                en = languages.profile(cfg, "en")   # the example story is English
                final = cartoon3d.render_example(cfg, work, lambda t, p, s: voice.kokoro_fit(cfg, t, p, s, en))
                storyboard = "3d-example"
            else:
                final = cartoon3d.render(cfg, script, timeline, voice_path, vlen + 0.7, work, lp["code"], brain.call_claude)
                storyboard = "3d"
        except Exception as e:  # noqa: BLE001 - the day's Short still ships, in 2D
            log(f"cartoon3d failed ({str(e)[:300]}); making this Short in 2D", "WARN")
            final = None
    if final is None:
        sample = None
        if test:  # a hand-made storyboard for the sample script, so test videos look like real ones
            sample = json.loads((ROOT / "prompts" / f"sample_story_{lp['code']}.json").read_text(encoding="utf-8"))
        final, storyboard = toon2d.render(cfg, script, timeline, voice_path, vlen + 0.7, work, lp["code"],
                                          brain.call_claude, brain.extract_json, use_claude=not test, sample=sample)
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
    ap.add_argument("--count", type=int, default=0, help="force how many to make")
    ap.add_argument("--language", default=None, help="force a language (en / hi); default: learned split")
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
    need = args.count or max(0, int(cfg.get("buffer", 2)) - len(queued))
    if args.test:
        need = 1
    need = min(need, 3)
    if need == 0:
        log(f"Buffer already full ({len(queued)} ready). Nothing to make today.")
        return
    log(f"Videos ready: {len(queued)}. Making {need}.")

    made = 0
    for _ in range(need):
        work, meta, script, idea = produce_one(cfg, history, stats, args.test, args.language, args.theme)
        made += 1
        if args.release:
            tag = f"vid-{meta['id']}"
            run(["gh", "release", "create", tag, work / "final.mp4", work / "meta.json",
                 "--title", meta["title"][:100], "--notes", meta["caption"][:2000]])
            history["videos"].append({**{k: meta[k] for k in (
                "id", "title", "topic", "canonical_en", "language", "theme", "category", "hook_type",
                "hook_line", "duration", "storyboard")},
                "tag": tag, "status": "queued", "created": now_ist().isoformat(timespec="minutes")})
            save_history(history)
            led = ideas.load()
            ideas.record(led, idea or {"canonical_en": meta["canonical_en"]}, meta["language"], meta["theme"],
                         meta["id"])
            ideas.save(led)
            if script.get("playbook_update", "").strip():
                (DATA / "playbook.md").write_text(script["playbook_update"].strip() + "\n", encoding="utf-8")
                log("Playbook updated")
        log(f"Done: {work / 'final.mp4'}")
    log(f"Made {made} video(s).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        log(f"FAILED: {e}", "ERROR")
        sys.exit(1)
