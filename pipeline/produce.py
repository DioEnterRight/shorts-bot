"""MAKE VIDEO: script -> pictures -> voice -> captions -> sound -> edit -> check -> queue.

  python -m pipeline.produce --test      # offline test: sample script + test cards, no keys
  python -m pipeline.produce --release   # real run: Claude + Cloudflare, uploads to GitHub Releases
"""
import argparse
import json
import random
import shutil
import sys

from . import audio, brain, captions, edit, qc, voice
from .common import DATA, OUT, load_config, load_history, log, now_ist, run, save_history, slugify
from .visuals import get_provider


def produce_one(cfg, history, test):
    stamp = now_ist().strftime("%Y%m%d-%H%M%S")
    provider_name = "placeholder" if test else cfg["visuals"]["provider"]
    script = None
    if provider_name.startswith("higgsfield"):
        from .visuals import higgsfield
        script = higgsfield.ticket_script()  # the Higgsfield routine may have written it already
        if script:
            script = brain.validate(script, cfg)
    if not script:
        script = brain.make_script(cfg, history, test=test)
    vid_id = f"{stamp}-{slugify(script['topic'], 30)}"
    work = OUT / vid_id
    work.mkdir(parents=True, exist_ok=True)
    (work / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False))
    log(f"=== Making {vid_id} ===")

    if provider_name == "higgsfield_full":
        from .visuals import higgsfield
        src, ticket = higgsfield.fetch_full(work)
        final = edit.finish_external(cfg, src, work)
        script["title"] = ticket.get("title", script["title"])
        script["description"] = ticket.get("description", script["description"])
    else:
        assets = get_provider(provider_name).generate(cfg, script, work)
        voice_path, timeline, vlen = voice.synthesize(cfg, script, work)
        total = vlen + 0.7
        cap_path, cap_times = captions.build(cfg, script, timeline, total, work)
        seed = random.randint(0, 10_000_000)
        mix_path = audio.mix(cfg, script, timeline, cap_times, voice_path, total, work, seed)
        final = edit.render(cfg, script, assets, timeline, total, cap_path, mix_path, work)

    duration = qc.check(final)
    if final.name != "final.mp4":
        shutil.move(final, work / "final.mp4")
        final = work / "final.mp4"

    caption = f"{script['title']}\n\n{script['description']}\n\n{' '.join(script['hashtags'])}".strip()
    meta = {
        "id": vid_id, "title": script["title"], "description": script["description"],
        "hashtags": script["hashtags"], "caption": caption, "duration": round(duration, 2),
        "topic": script["topic"], "category": script.get("category"),
        "hook_type": script.get("hook_type"), "experiment": script.get("experiment", False),
        "hook_line": script["scenes"][0]["line"], "facts_checked": script.get("facts_checked", []),
        "visuals": provider_name,
    }
    (work / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return work, meta, script


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="offline test, no keys needed")
    ap.add_argument("--release", action="store_true", help="queue result as a GitHub Release")
    ap.add_argument("--count", type=int, default=0, help="force how many to make")
    args = ap.parse_args()

    cfg = load_config()
    if cfg.get("paused") and not args.test:
        log("Paused in config.yaml — nothing to do.")
        return
    history = load_history()
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
        work, meta, script = produce_one(cfg, history, args.test)
        made += 1
        if args.release:
            tag = f"vid-{meta['id']}"
            run(["gh", "release", "create", tag, work / "final.mp4", work / "meta.json",
                 "--title", meta["title"][:100], "--notes", meta["caption"][:2000]])
            history["videos"].append({**{k: meta[k] for k in (
                "id", "title", "topic", "category", "hook_type", "experiment", "hook_line", "duration", "visuals")},
                "tag": tag, "status": "queued", "created": now_ist().isoformat(timespec="minutes")})
            if script.get("playbook_update", "").strip():
                (DATA / "playbook.md").write_text(script["playbook_update"].strip() + "\n", encoding="utf-8")
                log("Playbook updated")
            save_history(history)
        log(f"Done: {work / 'final.mp4'}")
    log(f"Made {made} video(s).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        log(f"FAILED: {e}")
        sys.exit(1)
