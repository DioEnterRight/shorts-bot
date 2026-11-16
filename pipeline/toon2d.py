"""2D cartoon engine (toon2d/): Claude writes one story.json storyboard, the skia engine draws and mixes it.

Vertical 9:16 for Shorts, 16:9 for the weekly long video. Claude never writes drawing code here, so a video
costs one short text-only Claude call. Timing comes from our own voice timeline (no speech model needed),
and mouths follow pipeline/visemes.py instead of loudness.
"""
import json
import os
import re
import shutil
import sys
import tempfile

from . import visemes
from .common import ROOT, log, run

ENGINE_DIR = ROOT / "toon2d"
sys.path.insert(0, str(ROOT))
from toon2d.engine.timing import norm  # noqa: E402  (pure helper: no drawing imports)

FPS = 30
END = re.compile(r"[.!?।…]+[\"”’)]*$")
HOST = {"skin": "tan", "outfit": "hoodie", "color": "#2F7A5A", "shirt": "#E8E0D0", "hair": "curly", "hair_col": "#1C1B22"}


# ---------------- timing ----------------
def timing_from_timeline(timeline, duration):
    """Our voice timeline (lines of timed words) -> the engine's timing.json (sentences of timed words).
    Each script line is split at sentence ends so shots can cut between sentences."""
    sents, cur = [], []

    def close():
        if not cur:
            return
        words = [dict(w=w["word"], n=norm(w["word"]), t=round(w["start"], 3)) for w in cur]
        sents.append(dict(i=len(sents), text=" ".join(w["word"] for w in cur),
                          start=round(max(0.0, cur[0]["start"] - 0.06), 3), end=round(cur[-1]["end"], 3), words=words))
        cur.clear()

    for line in timeline:
        for w in line["words"]:
            cur.append(w)
            if END.search(w["word"]):
                close()
        close()
    if not sents:
        raise ValueError("Voice timeline has no words")
    return dict(duration=round(duration, 3), method="tts", matched=1.0, sentences=sents)


# ---------------- storyboard ----------------
def _reference():
    return (ENGINE_DIR / "reference" / "story-format.md").read_text(encoding="utf-8")


def build_prompt(script, timing, aspect, language):
    vertical = aspect == "9:16"
    sentences = "\n".join(f"{s['i']}: {s['text']}" for s in timing["sentences"])
    hints = "\n".join(f"- {sc.get('visual', '')} | emphasis: {sc.get('emphasis', '')} | overlay: {sc.get('overlay', '')}"
                      for sc in script["scenes"])
    if vertical:
        fmt = "VERTICAL 9:16 YouTube Short / Instagram Reel (1080x1920), 25-60 seconds."
        rules = ("Vertical frame: leave out every x and y (labels, stamps, chars, props, places): the engine lays "
                 "vertical shots out itself. Keep wide shots to 1-2 characters. No silent title cards (no shot without s). "
                 "Burned-in captions are added automatically, so labels are for key words and numbers only.")
        pacing = "One shot per sentence (or two short sentences); about 2-5 seconds each."
        platform = "YouTube Shorts / Instagram Reels"
    else:
        fmt = "LANDSCAPE 16:9 long YouTube video (1920x1080)."
        rules = ("Follow the pacing rules in the reference (shot length, chapters, re-hooks). "
                 "Chapter cards are silent title shots without s.")
        pacing = "About one shot per 3-8 seconds."
        platform = "YouTube"
    text = (ROOT / "prompts" / "toon2d_story.md").read_text(encoding="utf-8")
    for k, v in dict(platform=platform, format=fmt, language=language, topic=script["topic"], sentences=sentences,
                     hints=hints, pacing=pacing, format_rules=rules, reference=_reference()).items():
        text = text.replace("{" + k + "}", v)
    return text


def auto_story(script, timing):
    """Deterministic storyboard (test mode, or when Claude's storyboards keep failing the plan check)."""
    n = len(timing["sentences"])
    words_of = [s["words"] for s in timing["sentences"]]
    kinds = [("closeup", "home"), ("wide", "office"), ("walk", "street"), ("closeup", "office"), ("wide", "home")]
    emph = [str(sc.get("emphasis") or "").strip() for sc in script["scenes"]]
    shots = []
    for i in range(n):
        kind, set_ = kinds[i % len(kinds)]
        sh = {"kind": kind, "s": [i], "set": set_, "time": "night" if i % 2 == 0 else "day"}
        if kind == "closeup":
            sh.update(who="host", emotion=["shocked", "thinking", "smug", "excited"][i % 4])
        else:
            sh["chars"] = [{"id": "host", "emotion": "confident", "pose": ["explain", "present", "point"][i % 3]}]
        pick = next((e for e in emph if e and any(w["n"] == norm(e.split()[0]) for w in words_of[i])), None)
        if pick:
            sh["labels"] = [{"text": pick.upper()[:24], "at": pick.split()[0]}]
        shots.append(sh)
    if words_of[-1]:
        last = " ".join(w["w"] for w in words_of[-1][-4:]).strip(" .!?")
        shots[-1]["polaroid"] = {"at": words_of[-1][-1]["w"], "who": "host", "caption": last.upper()[:28]}
    return {"title": "final", "mood": "upbeat", "cast": {"host": HOST}, "shots": shots}


def check(project, aspect):
    """Run the engine's plan check. Returns a list of problems (empty = renderable)."""
    res = run([sys.executable, "-m", "engine", "plan", str(project)], capture=True, check=False,
              cwd=ENGINE_DIR, env=_env(aspect, captions=False))
    out = (res.stdout or "") + (res.stderr or "")
    lines = [ln.strip() for ln in out.splitlines() if ln.strip() and "Fontconfig" not in ln]
    problems = [ln for ln in lines if ln.startswith("WARNING")]
    if res.returncode != 0:  # a crash or SystemExit message is the last line
        problems.append(lines[-1] if lines else f"plan exited {res.returncode}")
    return problems


def _serious(problems):
    """Cue words that were not found only shift an event to 40% of its shot: everything else must be fixed."""
    return [p for p in problems if "not found in its sentences" not in p]


def storyboard(cfg, script, timing, project, aspect, language, call_claude, extract_json, use_claude):
    """Write project/story.json. Claude first (with one repair round), auto storyboard as the fallback."""
    tc = cfg.get("toon2d", {})
    story_path = project / "story.json"
    if use_claude:
        prompt = build_prompt(script, timing, aspect, language)
        msg = prompt
        for attempt in range(1, int(tc.get("story_attempts", 2)) + 1):
            try:
                log(f"Asking Claude for the storyboard (attempt {attempt})")
                # outside the repo: no CLAUDE.md, skills or hooks loaded into this small call
                reply = call_claude(msg, tools="Read", max_turns=3, effort=tc.get("effort", "medium"), model=tc.get("model"),
                                    cwd=tempfile.gettempdir(), timeout=900)
                story = extract_json(reply)
                story["title"] = "final"
                story_path.write_text(json.dumps(story, indent=1, ensure_ascii=False), encoding="utf-8")
                bad = _serious(check(project, aspect))
                if not bad:
                    log(f"Storyboard OK: {len(story.get('shots', []))} shots")
                    return story, "claude"
                log(f"Storyboard problems: {bad[:6]}", "WARN")
                msg = (prompt + "\n\nYour previous storyboard had these problems:\n" + "\n".join(bad[:20])
                       + "\n\nPrevious storyboard:\n" + json.dumps(story, ensure_ascii=False) + "\n\nReply with the fixed JSON only.")
            except Exception as e:  # noqa: BLE001 - one bad reply should not kill the video
                log(f"Storyboard attempt failed: {str(e)[:200]}", "WARN")
    story = auto_story(script, timing)
    story_path.write_text(json.dumps(story, indent=1, ensure_ascii=False), encoding="utf-8")
    bad = _serious(check(project, aspect))
    if bad:
        raise RuntimeError(f"Auto storyboard failed the plan check: {bad[:5]}")
    log("Using the automatic storyboard", "WARN" if use_claude else "INFO")
    return story, "auto"


# ---------------- render ----------------
def _env(aspect, captions, res=None):
    e = dict(os.environ, RM_ASPECT=aspect, RM_CAPTIONS="1" if captions else "0", PYTHONIOENCODING="utf-8")
    if res:
        e["RM_RES"] = str(res)
    return e


def render(cfg, script, timeline, voice_path, duration, work, language, call_claude, extract_json,
           use_claude=True, aspect="9:16"):
    """Storyboard + render + sound. Returns (final mp4 path, storyboard source 'claude'|'auto')."""
    tc = cfg.get("toon2d", {})
    project = work / ("toon2d" if aspect == "9:16" else "toon2d_long")
    project.mkdir(parents=True, exist_ok=True)
    shutil.copy(voice_path, project / ("voice" + voice_path.suffix))
    timing = timing_from_timeline(timeline, duration)
    (project / "timing.json").write_text(json.dumps(timing, indent=1, ensure_ascii=False), encoding="utf-8")
    (project / "visemes.json").write_text(json.dumps(visemes.track(timeline, FPS)), encoding="utf-8")
    story, source = storyboard(cfg, script, timing, project, aspect, language, call_claude, extract_json, use_claude)
    captions = bool(tc.get("captions", True)) if aspect == "9:16" else bool(tc.get("long_captions", False))
    env = _env(aspect, captions, tc.get("resolution"))
    timeout = int(tc.get("timeout_minutes", 40)) * 60
    for cmd in (["render"], ["audio", "--music-db", str(tc.get("music_db", -17))], ["final", "--title", "final"]):
        run([sys.executable, "-m", "engine", cmd[0], str(project), *cmd[1:]], cwd=ENGINE_DIR, env=env, timeout=timeout)
    out = project / "out" / ("final.mp4" if not tc.get("resolution") or int(tc["resolution"]) == 1080
                             else f"final_{tc['resolution']}p.mp4")
    if not out.exists():
        raise RuntimeError(f"toon2d render produced no file at {out}")
    return out, source
