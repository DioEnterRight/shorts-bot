"""Mixed 3D + 2D Shorts: Claude (Opus) builds a new world, cast, poses, cameras and sound cues for every video with
the cartoon-audio-short skill (.claude/skills/cartoon-audio-short), then three.js in headless Chrome renders it.

Claude only writes the code (story.js, world, cast, audio cue table) and checks one or two contact sheets; the
pipeline does the full render, the level-locked mix and the encode. Any failure -> the caller falls back to toon2d.
Test mode renders the kit's own example ("The Soldier Who Never Left") with a Kokoro voice, without Claude.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import freellm, storyboard3d
from .common import ROOT, log, run

KIT = ROOT / ".claude" / "skills" / "cartoon-audio-short" / "kit"
SKILL = KIT.parent / "SKILL.md"
EXAMPLE_STORY = KIT / "example" / "soldier" / "story.js"
FPS = 30
SOLDIER = ("A Roman soldier stood guard at a bridge for thirty years, refusing to leave his post. "
           "Even when the empire collapsed, he stayed. People called him crazy. "
           "But when workers finally removed his helmet, they discovered a message carved inside: The bridge is not safe. "
           "Beneath it, the wooden supports had been slowly rotting for centuries.")


def timing_files(timeline, duration, work_dir):
    """Our exact TTS word timings -> the kit's work/words.json + work/phrases.json (no speech recognition)."""
    words = [{"w": w["word"], "s": round(w["start"], 3), "e": round(w["end"], 3)} for line in timeline for w in line["words"]]
    if not words:
        raise ValueError("Voice timeline has no words")
    phrases, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[,.;:!?।][\"”’)]*$", w["w"]):
            phrases.append({"text": " ".join(x["w"] for x in cur), "s": cur[0]["s"], "e": cur[-1]["e"]}); cur = []
    if cur:
        phrases.append({"text": " ".join(x["w"] for x in cur), "s": cur[0]["s"], "e": cur[-1]["e"]})
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "words.json").write_text(json.dumps(words, indent=1, ensure_ascii=False), encoding="utf-8")
    frames = int(round(duration * FPS))
    (work_dir / "phrases.json").write_text(json.dumps({"duration": round(duration, 3), "frames30": frames, "source": "tts",
                                                       "segments": [], "phrases": phrases}, indent=1, ensure_ascii=False),
                                           encoding="utf-8")
    return frames


def build_prompt(script, frames, language):
    lines = "\n".join(f"{i + 1}. {sc['line']}   [show: {sc.get('visual', '')}]" for i, sc in enumerate(script["scenes"]))
    return f"""Make the picture for a vertical cartoon Short with the cartoon-audio-short skill.
Read {SKILL} and follow Stage 4 (4.2 to 4.7). Stages 1-3 are done and the voiceover is final.
Token budget matters: read API.md (engine cheat sheet) and web/models/CATALOG.md (3D models) instead of the engine
sources. Never open web/lib/*, web/toon.js or web/toonbase.js. Use real models via model() for buildings, vehicles,
furniture, food, money and props; primitives for terrain and custom set pieces.

This folder is the project, already set up by setup.sh: voice.mp3, script.txt, web/ (engine + the soldier example
as a starting point to rewrite), and work/words.json + work/phrases.json with EXACT word timings (do not run
timing.py). Total frames: {frames} at 30 fps. Chrome: use the CHROME environment variable (already set).

Title: {script['title']}
Language of the voice: {language} (any on-screen text in English / Roman letters)
Script, one line per beat, with what each beat should show:
{lines}

Do:
- work/PLAN.md, then rewrite web/story.js (export TOTAL = {frames}), the world in web/main.js, the cast in
  web/roman.js (rebuild web/toon.js), motion, and the SFX cue table in audio.py (no music: the pipeline adds a
  mood-matched bed itself, so skip every music line). Build a NEW world, cast and poses
  for this story: original characters only, no real named living people, no logos or brand mascots.
- Change the background, camera angle and character pose or cast every 3-4 seconds so every point is shown.
- Steady, smooth, unhurried motion: no whip pans, no jittery shakes, no fast-forward or time-lapse jumps.
- Look check: at most 2 rounds of `node render.mjs stills/a "<frames>"` + `python3 sheet.py`, fix what is wrong.
- Captions are burned in by the pipeline: keep the bottom 30% of the frame free of important action.
- Do NOT render all frames, do NOT run mix.py or finish.sh (the pipeline does that after you).
When everything is written and the last contact sheet looks right, reply with one word: DONE"""


def _check_story(project, frames):
    story = (project / "web" / "story.js").read_text(encoding="utf-8")
    if story == EXAMPLE_STORY.read_text(encoding="utf-8"):
        raise RuntimeError("cartoon3d: story.js was not rewritten")
    m = re.search(r"TOTAL\s*=\s*(\d+)", story)
    if not m or abs(int(m.group(1)) - frames) > 2:
        raise RuntimeError(f"cartoon3d: story.js TOTAL is {m.group(1) if m else 'missing'}, expected {frames}")


def _env():
    return dict(os.environ, CHROME=os.environ.get("CHROME", "/usr/bin/google-chrome"))


def preflight(project):
    """Render 2 frames of the kit example and encode them exactly like finish.sh, before Claude spends tokens.
    A broken Chrome/ffmpeg toolchain then fails in seconds instead of after the Claude build and an hour of render."""
    ff = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    osname = next((l.split("=", 1)[1].strip('"') for l in Path("/etc/os-release").read_text().splitlines()
                   if l.startswith("PRETTY_NAME=")), "unknown OS") if Path("/etc/os-release").exists() else "unknown OS"
    log(f"cartoon3d toolchain: {osname}; {ff}")
    pre = project / "preflight"
    (pre / "frames").mkdir(parents=True); (pre / "out").mkdir()
    run(["node", "render.mjs", str(pre / "frames"), "0-1", "1"], cwd=project, env=_env(), timeout=300)
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=0.5", "-ar", "48000", str(pre / "mix_raw.wav")])
    for f in ("finish.sh", "frames_rgb.py"):
        shutil.copy(project / f, pre / f)
    shutil.copytree(project / "fonts", pre / "fonts")
    (pre / "work").mkdir()
    (pre / "work" / "words.json").write_text(json.dumps([{"w": "Caption", "s": 0.0, "e": 0.03}, {"w": "check", "s": 0.03, "e": 0.06}]), encoding="utf-8")
    run(["bash", "finish.sh", "final"], cwd=pre, env=dict(os.environ, CAPTIONS="1"), timeout=300)
    shutil.rmtree(pre)


MOODS = ("mystery", "upbeat", "dramatic", "calm", "tense")


def mood_of(script):
    m = str(script.get("mood", "")).strip().lower()
    return m if m in MOODS else "mystery"


def _music(project, mood, seconds):
    """Replace the kit's brass-march stem with the 2D engine's mood bed (same synths the 2D Shorts use)."""
    code = ("import sys, soundfile as sf; from engine.audio import music_bed, SR; "
            "m = music_bed(float(sys.argv[2]), sys.argv[1], [])[:int(float(sys.argv[2]) * SR)]; sf.write(sys.argv[3], m, SR)")
    run([sys.executable, "-c", code, mood, str(seconds), str(project / "music.wav")], cwd=ROOT / "toon2d", timeout=300)


def _sfx(project, events, seconds):
    """sfx.wav from [[t, name], ...] with the 2D engine's synthesized effects (silence when there are none)."""
    code = ("import sys, json, numpy as np, soundfile as sf; from engine import audio as A; "
            "ev = json.loads(sys.argv[1]); buf = np.zeros((int(float(sys.argv[2]) * A.SR), 2)); "
            "[A.place(buf, A.SFX[n](), t, 0.8) for t, n in ev]; sf.write(sys.argv[3], buf.astype(np.float32), A.SR)")
    run([sys.executable, "-c", code, json.dumps(events), str(seconds), str(project / "sfx.wav")], cwd=ROOT / "toon2d", timeout=300)


def _finish(project, frames, timeout, cfg, mood="mystery", sfx_events=None):
    t2 = cfg["toon2d"]
    try:
        run(["bash", "render_all.sh", str(frames)], cwd=project, env=_env(), timeout=timeout)
    except Exception as e:   # a crashed Chrome or a timeout: keep the frames already made, render only the rest
        log(f"cartoon3d: render failed ({e}); resuming once", "WARN")
        run(["bash", "render_all.sh", str(frames)], cwd=project, env=dict(_env(), RESUME="1"), timeout=timeout)
    if sfx_events is None:
        run(["python3", "audio.py"], cwd=project, timeout=600)   # Claude's build: its own cue table writes sfx.wav
    else:
        _sfx(project, sfx_events, frames / FPS)
    _music(project, mood, frames / FPS)
    run(["python3", "mix.py", "voice.mp3", "music.wav", "sfx.wav",
         "--music-db", str(t2.get("music_db", -20)), "--sfx-db", str(t2.get("sfx_db", -13))], cwd=project, timeout=600)
    run(["bash", "finish.sh", "final"], cwd=project, env=dict(os.environ, CAPTIONS="1" if t2.get("captions", True) else "0"), timeout=1200)
    out = project / "out" / "final.mp4"
    if not out.exists():
        raise RuntimeError("cartoon3d: finish.sh produced no video")
    return out


def _setup(project, voice_path):
    run(["bash", str(KIT / "tools" / "setup.sh"), str(project)], timeout=600)
    skills = project / ".claude" / "skills"   # project skills Claude can load on demand (only names cost tokens)
    for name in ("cartoon-audio-short", "threejs"):
        shutil.copytree(ROOT / ".claude" / "skills" / name, skills / name, ignore=shutil.ignore_patterns("models", "kit"))
    run(["ffmpeg", "-v", "error", "-y", "-i", str(voice_path), "-ar", "48000", "-ac", "1", str(project / "voice.mp3")])
    (project / "fonts").mkdir()
    shutil.copy(ROOT / "toon2d" / "fonts" / "Kalam-Bold.ttf", project / "fonts" / "Kalam-Bold.ttf")   # caption font (OFL, see toon2d/CREDITS.md)


def _stills_ok(project, frames):
    """Render 3 frames of the generated world and make sure they are real pictures (page errors exit non-zero in render.mjs)."""
    from PIL import Image, ImageStat
    d = project / "stills_check"
    spec = ",".join(str(int(frames * k)) for k in (0.1, 0.5, 0.9))
    run(["node", "render.mjs", str(d), spec, "1"], cwd=project, env=_env(), timeout=600)
    for f in sorted(d.glob("*.jpg")):
        if max(ImageStat.Stat(Image.open(f).convert("L")).stddev) < 6:
            raise RuntimeError(f"generated world renders a blank picture ({f.name})")
    shutil.rmtree(d)


def _ask(cfg, budget, msgs, n, models):
    """One storyboard request plus up to freellm.repair_rounds fix-ups. -> (clean scenes, raw storyboard, problems)."""
    rounds = int(cfg.get("freellm", {}).get("repair_rounds", 2))
    best = None
    for attempt in range(rounds + 1):
        reply = freellm.chat(cfg, msgs, budget)
        try:
            raw = freellm.extract_json(reply)
            clean, problems = storyboard3d.normalize(raw, n, models)
        except ValueError as e:
            raw, clean, problems = None, None, [f"your reply was not usable: {e}"]
        log(f"cartoon3d: storyboard attempt {attempt + 1}: {len(problems)} problem(s)" + (f" - {problems[0]}" if problems else ""))
        if clean and not storyboard3d.fatal(problems, n) and (best is None or len(problems) < len(best[2])):
            best = (clean, raw, problems)
        if clean and not problems:
            break
        if attempt < rounds:
            msgs = msgs + [{"role": "assistant", "content": reply},
                           {"role": "user", "content": "Fix these problems and reply with the complete corrected JSON object only:\n- " + "\n- ".join(problems)}]
    if best is None:
        raise RuntimeError("cartoon3d: the free model did not give a usable storyboard")
    return best


def free_storyboard(cfg, script, spans, fps=FPS):
    """Draft -> fix-ups -> art-director review. The review is kept only when it is at least as clean as the draft."""
    budget = freellm.Budget(cfg)
    models, n = storyboard3d.parse_catalog(), len(spans)
    clean, raw, problems = _ask(cfg, budget, storyboard3d.build_messages(script, spans, fps), n, models)
    if cfg.get("freellm", {}).get("review", True):
        try:
            c2, r2, p2 = _ask(cfg, budget, storyboard3d.review_messages(script, spans, raw, fps), n, models)
            if len(p2) <= len(problems):
                clean, raw, problems = c2, r2, p2
                log("cartoon3d: art-director review accepted")
            else:
                log("cartoon3d: review came back worse; keeping the draft", "WARN")
        except RuntimeError as e:   # budget or provider trouble: the checked draft is still good
            log(f"cartoon3d: review skipped ({str(e)[:200]})", "WARN")
    if problems:
        log(f"cartoon3d: using the storyboard with {len(problems)} small fix(es) made by code: {problems[:3]}", "WARN")
    return clean, raw


def render_free(cfg, script, timeline, voice_path, duration, work):
    """The free LLM only writes a JSON storyboard; code validates it, compiles it and renders it with the static engine."""
    c3 = cfg["cartoon3d"]
    if not freellm.configured(cfg):
        raise RuntimeError("cartoon3d builder=freellm but FreeLLMAPI is not running (FREELLMAPI_KEYS secret missing?)")
    if len(timeline) != len(script["scenes"]):
        raise RuntimeError("cartoon3d: voice timeline and script scenes do not match")
    project = Path(tempfile.mkdtemp(prefix="cartoon3d-"))
    _setup(project, voice_path)
    preflight(project)
    frames = timing_files(timeline, duration, project / "work")
    spans = storyboard3d.spans_from_timeline(timeline, frames, FPS)
    scenes, raw = free_storyboard(cfg, script, spans)
    data = storyboard3d.compile_data(scenes, spans, frames, FPS)
    storyboard3d.write_project(project, data)
    (work / "cartoon3d_work").mkdir(parents=True, exist_ok=True)
    (work / "cartoon3d_work" / "storyboard.json").write_text(json.dumps({"raw": raw, "used": scenes}, indent=1, ensure_ascii=False), encoding="utf-8")
    _stills_ok(project, frames)
    out = _finish(project, frames, int(c3.get("render_timeout_minutes", 150)) * 60, cfg, mood_of(script),
                  sfx_events=storyboard3d.sfx_events(scenes, spans, FPS))
    shutil.copytree(project / "work", work / "cartoon3d_work", dirs_exist_ok=True)
    return out


def render(cfg, script, timeline, voice_path, duration, work, language, call_claude):
    """Returns the finished mp4 path. Raises on any failure (the caller falls back to toon2d)."""
    c3 = cfg["cartoon3d"]
    if c3.get("builder", "claude") == "freellm":
        try:
            return render_free(cfg, script, timeline, voice_path, duration, work)
        except Exception as e:
            if not c3.get("claude_rescue", False):
                raise
            log(f"cartoon3d: free builder failed ({str(e)[:300]}); Claude builds this one", "WARN")
    project = Path(tempfile.mkdtemp(prefix="cartoon3d-"))   # outside the repo: no CLAUDE.md, skills or hooks loaded
    _setup(project, voice_path)
    preflight(project)
    (project / "script.txt").write_text("\n".join(sc["line"] for sc in script["scenes"]) + "\n", encoding="utf-8")
    frames = timing_files(timeline, duration, project / "work")
    log(f"cartoon3d: Claude builds the world for {frames} frames")
    reply = call_claude(build_prompt(script, frames, language), tools="Read,Write,Edit,Glob,Grep,Bash",
                        max_turns=int(c3.get("max_turns", 80)), effort=c3.get("effort", "high"), model=c3.get("model"),
                        cwd=str(project), timeout=int(c3.get("claude_timeout_minutes", 60)) * 60)
    if "DONE" not in reply:
        log(f"cartoon3d: Claude did not report DONE: {reply[-300:]}", "WARN")
    _check_story(project, frames)
    out = _finish(project, frames, int(c3.get("render_timeout_minutes", 150)) * 60, cfg, mood_of(script))
    shutil.copytree(project / "work", work / "cartoon3d_work", dirs_exist_ok=True)
    return out


def render_example(cfg, work, voice_fn):
    """Test mode: the kit's soldier example voiced by Kokoro (no Claude), to prove the 3D toolchain end to end."""
    project = Path(tempfile.mkdtemp(prefix="cartoon3d-test-"))
    total = int(re.search(r"TOTAL\s*=\s*(\d+)", EXAMPLE_STORY.read_text(encoding="utf-8")).group(1))
    voice_wav = work / "soldier_voice.wav"
    voice_fn(SOLDIER, voice_wav, total / FPS)
    _setup(project, voice_wav)
    preflight(project)   # same cheap check as a real run, so a TEST run proves it on the runner for free
    return _finish(project, total, int(cfg["cartoon3d"].get("render_timeout_minutes", 150)) * 60, cfg)
