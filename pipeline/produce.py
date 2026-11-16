"""MAKE VIDEO: slot (language + theme) -> idea -> script -> pictures -> voice -> captions
-> sound -> edit -> check -> queue.

  python -m pipeline.produce --test                 # offline test: sample script + test cards, no keys
  python -m pipeline.produce --test --language hi   # same, Hindi sample
  python -m pipeline.produce --release              # real run: Claude + Cloudflare, uploads to GitHub Releases
"""
import argparse
import json
import shutil
import sys

from . import allocation, analytics, audio, brain, captions, edit, ideas, languages, qc, remotion_render, voice
from .common import DATA, OUT, load_config, load_history, log, now_ist, run, save_history, slugify, stable_seed
from .visuals import get_provider


def recent_sequence(history, key, default):
    made = [v for v in history["videos"] if v.get("status") != "discarded"]
    made.sort(key=lambda v: v.get("created", ""))
    return [v.get(key, default) for v in made]


def choose_slot(cfg, history, stats, language=None, theme=None):
    """Which language and theme the next video gets (deterministic, see allocation.py)."""
    s = allocation.settings(cfg)
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
    """Platform AI-disclosure flags, decided from what the video actually contains."""
    d = cfg.get("disclosure") or {}
    photoreal = bool(d.get("photorealistic_visuals", False))
    yt = d.get("youtube_synthetic", "auto")
    return {"synthetic_youtube": photoreal if yt == "auto" else bool(yt),
            "ai_label_instagram": bool(d.get("instagram_ai_label", True))}


def make_script(cfg, history, stats, lp, theme, test, provider_name):
    if test:
        return brain.sample_script(cfg, lp, theme), None
    if provider_name.startswith("higgsfield"):
        from .visuals import higgsfield
        ticket = higgsfield.ticket_script()  # the Higgsfield routine may have written it already
        if ticket:
            tlp = languages.profile(cfg, ticket.get("language", lp["code"]))
            return brain.validate(ticket, cfg, tlp, ticket.get("theme", theme)), None
    perf = brain.performance_summary(stats, lp["code"])
    idea = ideas.generate(cfg, history, theme, lp, perf, brain.call_claude, brain.extract_json)
    return brain.write_script(cfg, idea, lp, theme, perf), idea


def produce_one(cfg, history, stats, test, provider_override=None, language=None, theme=None):
    stamp = now_ist().strftime("%Y%m%d-%H%M%S")
    provider_name = provider_override or ("placeholder" if test else cfg["visuals"]["provider"])
    language, theme = choose_slot(cfg, history, stats, language, theme)
    lp = languages.profile(cfg, language)
    log(f"Slot: language={language} theme={theme} visuals={provider_name}")
    script, idea = make_script(cfg, history, stats, lp, theme, test, provider_name)
    lp = languages.profile(cfg, script["language"])
    vid_id = f"{stamp}-{script['language']}-{slugify(script['topic'], 28)}"
    work = OUT / vid_id
    work.mkdir(parents=True, exist_ok=True)
    (work / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"=== Making {vid_id} ===")

    if provider_name == "higgsfield_full":
        from .visuals import higgsfield
        src, ticket = higgsfield.fetch_full(work)
        final = edit.finish_external(cfg, src, work)
        script["title"] = ticket.get("title", script["title"])
        script["description"] = ticket.get("description", script["description"])
    else:
        engine = cfg["render"]["engine"]
        style = cfg["themes"][theme].get("render_style", "explainer") if engine == "remotion" else "explainer"
        if style == "blocky":   # drawn entirely in code: no pictures to generate
            assets = [None] * len(script["scenes"])
        else:
            assets = get_provider(provider_name).generate(cfg, script, work)
        voice_path, timeline, vlen, voice_engine = voice.synthesize(cfg, script, lp, work, allow_edge=not test)
        script["voice_engine"] = voice_engine
        total = vlen + 0.7
        seed = stable_seed(vid_id)
        if engine == "remotion":
            mix_path = audio.mix(cfg, script, timeline, [], voice_path, total, work, seed, with_sfx=False)
            final = remotion_render.render(cfg, script, assets, timeline, total, lp, style, mix_path, work)
        elif engine == "ffmpeg":
            cap_path, cap_times = captions.build(cfg, script, timeline, total, lp, work)
            mix_path = audio.mix(cfg, script, timeline, cap_times, voice_path, total, work, seed)
            final = edit.render(cfg, script, assets, timeline, total, cap_path, mix_path, work)
        else:
            raise ValueError(f"render.engine must be remotion or ffmpeg, not {engine!r}")
        (work / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False), encoding="utf-8")

    duration = qc.check(final, fps=cfg["video"]["fps"])
    if final.name != "final.mp4":
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
        "visuals": provider_name, "render": cfg["render"]["engine"],
        "voice_engine": script.get("voice_engine"), **disclosure(cfg),
    }
    (work / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return work, meta, script, idea


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="offline test (sample script, no Claude/keys)")
    ap.add_argument("--release", action="store_true", help="queue result as a GitHub Release")
    ap.add_argument("--count", type=int, default=0, help="force how many to make")
    ap.add_argument("--provider", default=None,
                    help="override visuals provider (e.g. higgsfield_test to demo the Higgsfield path offline)")
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
        work, meta, script, idea = produce_one(cfg, history, stats, args.test, args.provider,
                                               args.language, args.theme)
        made += 1
        if args.release:
            tag = f"vid-{meta['id']}"
            run(["gh", "release", "create", tag, work / "final.mp4", work / "meta.json",
                 "--title", meta["title"][:100], "--notes", meta["caption"][:2000]])
            history["videos"].append({**{k: meta[k] for k in (
                "id", "title", "topic", "canonical_en", "language", "theme", "category", "hook_type",
                "hook_line", "duration", "visuals")},
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
