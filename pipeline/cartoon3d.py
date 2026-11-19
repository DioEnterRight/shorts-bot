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
import tempfile
from pathlib import Path

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
  web/roman.js (rebuild web/toon.js), motion, and the cue table in audio.py. Build a NEW world, cast and poses
  for this story: original characters only, no real named living people, no logos or brand mascots.
- Change the background, camera angle and character pose or cast every 3-4 seconds so every point is shown.
- Steady, smooth, unhurried motion: no whip pans, no jittery shakes, no fast-forward or time-lapse jumps.
- Look check: at most 2 rounds of `node render.mjs stills/a "<frames>"` + `python3 sheet.py`, fix what is wrong.
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
    run(["bash", "finish.sh", "final"], cwd=pre, timeout=300)
    shutil.rmtree(pre)


def _finish(project, frames, timeout):
    try:
        run(["bash", "render_all.sh", str(frames)], cwd=project, env=_env(), timeout=timeout)
    except Exception as e:   # a crashed Chrome or a timeout: keep the frames already made, render only the rest
        log(f"cartoon3d: render failed ({e}); resuming once", "WARN")
        run(["bash", "render_all.sh", str(frames)], cwd=project, env=dict(_env(), RESUME="1"), timeout=timeout)
    run(["python3", "audio.py"], cwd=project, timeout=600)
    run(["python3", "mix.py", "voice.mp3", "music.wav", "sfx.wav"], cwd=project, timeout=600)
    run(["bash", "finish.sh", "final"], cwd=project, timeout=1200)
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


def render(cfg, script, timeline, voice_path, duration, work, language, call_claude):
    """Returns the finished mp4 path. Raises on any failure (the caller falls back to toon2d)."""
    c3 = cfg["cartoon3d"]
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
    out = _finish(project, frames, int(c3.get("render_timeout_minutes", 150)) * 60)
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
    return _finish(project, total, int(cfg["cartoon3d"].get("render_timeout_minutes", 150)) * 60)
