"""THE video engine: the animated-shorts-kit skill (.claude/skills/animated-shorts-kit), run on GitHub Actions.

The kit's method, automated (references/01_WORKFLOW.md, 05_AGENT_TEAM.md, 06_CHECKS.md):
  1. timeline.ts from the real voice (exact TTS word timings, no speech recognition)
  2. DIRECTOR: a model writes the shot plan (references/09_PLAN_FORMAT.md); plan.py compiles it onto the kit engine
  3. CHECKS: plan problems + the kit's hard gates; failures go back to the director (repair rounds). No render until 0.
  4. WATCH + JUDGE: render a preview, contact sheets every 0.5 s (sheet.py), a judge scores it; one fix round; the
     version with the higher overall score wins (numbers, not opinions). Every version is kept in <work>/versions/.
  5. Final 1080x1920 render, sound mix (sound.py), done.
Any exception -> produce.py makes that Short with the emergency 2D engine (toon2d).
"""
import base64
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

from . import freellm, sound
from .common import KIT, log, run

CODE = KIT / "code"
TOOLS = CODE / "src" / "engine" / "tools"
FPS = 30


def _plan_module():
    spec = importlib.util.spec_from_file_location("kit_plan", TOOLS / "plan.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


planc = _plan_module()


# ---------------------------------------------------------------- 1. timeline
def caption_timeline(script, timeline):
    """the voice timeline with the words the screen shows: for Hindi the Roman Hinglish "caption" of each line laid on
    that line's voice timings (1:1 when the counts match, else spread by word length); otherwise unchanged."""
    out = []
    for sc, line in zip(script["scenes"], timeline):
        tts = [(w["word"], w["start"], w["end"]) for w in line["words"]]
        cap, words = (sc.get("caption") or "").split(), []
        if not cap or not tts:
            words = tts
        elif len(cap) == len(tts):
            words = [(c, s, e) for c, (_, s, e) in zip(cap, tts)]
        else:
            a, b = tts[0][1], tts[-1][2]
            tot, t = sum(len(c) + 1 for c in cap), a
            for c in cap:
                d = (b - a) * (len(c) + 1) / tot
                words.append((c, t, t + d * 0.9))
                t += d
        out.append({**line, "words": [{"word": w, "start": round(s, 3), "end": round(e, 3)} for w, s, e in words]})
    return out


def caption_words(script, timeline):
    """flat [{w, s, e}] for the kit's words.json"""
    return [{"w": w["word"], "s": w["start"], "e": w["end"]} for line in caption_timeline(script, timeline) for w in line["words"]]


def setup_video(vid, script, timeline, voice_wav):
    """src/videos/<vid>/timeline.ts from the voice. -> video dir. The picture ends 0.4 s after the last word (kit: 0.1-0.5)."""
    vdir = CODE / "src" / "videos" / vid
    shutil.rmtree(vdir, ignore_errors=True)
    vdir.mkdir(parents=True)
    if len(timeline) != len(script["scenes"]):
        raise RuntimeError(f"voice has {len(timeline)} lines, script {len(script['scenes'])}")
    words = caption_words(script, timeline)
    (vdir / "words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    (vdir / "script.txt").write_text("\n".join(f"[{planc.beat_name(i)}] {sc.get('caption') or sc['line']}"
                                               for i, sc in enumerate(script["scenes"])), encoding="utf-8")
    end = words[-1]["e"] + 0.4
    run(["ffmpeg", "-v", "error", "-y", "-i", str(voice_wav), "-af", f"apad=whole_dur={end}", "-t", f"{end:.3f}",
         "-ar", "48000", "-ac", "1", str(vdir / "voice.wav")])
    run([sys.executable, str(TOOLS / "timeline.py"), str(vdir / "script.txt"), str(vdir / "words.json"), str(vdir / "voice.wav"),
         str(vdir / "timeline.ts")])
    return vdir


def beat_table(script, beats):
    rows = []
    for i, (sc, b) in enumerate(zip(script["scenes"], beats)):
        rows.append(f"beat {i + 1} ({b['start']:.1f}-{b['end']:.1f} s, {b['end'] - b['start']:.1f} s)\n  says: {sc['line']}\n"
                    f"  words: {' '.join(w[0] for w in b['words'])}\n  show: {sc.get('visual', '')}")
    return "\n".join(rows)


# ---------------------------------------------------------------- 2. director
def _section(path, heading):
    """one '## heading' section of a reference file (the skill stays the single source of the rules)"""
    text = (KIT / path).read_text(encoding="utf-8")
    m = re.search(r"^## " + re.escape(heading) + r".*?$(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def director_brief():
    chars = "\n".join(l for l in (KIT / "library/characters/CHARACTERS.md").read_text().splitlines() if l.startswith("| ") and "`" in l)
    spots = "\n".join(f"- {k}: {v['what']} (widest shot {v['max']})" for k, v in planc.SPOTS.items())
    models = (KIT / "library/environments/MODELS.md").read_text(encoding="utf-8")
    return "\n\n".join([
        (KIT / "references/09_PLAN_FORMAT.md").read_text(encoding="utf-8"),
        "## Camera rules (03_CAMERA_GRAMMAR.md)\n" + _section("references/03_CAMERA_GRAMMAR.md", "5. Rules for our camera"),
        "## Picture rules (02_STORY_FORMULA.md)\n" + _section("references/02_STORY_FORMULA.md", "Picture"),
        "## Characters (cast ids)\n" + chars,
        "## Spots\n" + spots,
        "## Actions\n" + ", ".join(planc.ACTS) + "\n\n## Expressions\n" + ", ".join(planc.EXPR),
        models,
    ])


def _ask(cfg, messages, budget, call_claude):
    """the director/judge model: FreeLLMAPI when it runs, else Claude (studio.director). -> parsed JSON"""
    if budget is not None:
        return freellm.extract_json(freellm.chat(cfg, messages, budget))
    if call_claude is None:
        raise RuntimeError("no director model: FreeLLMAPI is not running and Claude is not available")
    text = "\n\n".join(m["content"] if isinstance(m["content"], str) else m["content"][0]["text"] for m in messages)
    return freellm.extract_json(call_claude(text, tools="", max_turns=2, effort="medium", model=cfg["studio"].get("claude_model")))


def direct(cfg, script, beats, budget, call_claude, plan=None, notes=None):
    """first draft (plan None) or a corrected full plan from notes (problems / judge fixes)."""
    sys_msg = director_brief()
    ask = (f"Short: \"{script['title']}\" (narration language: {script['language']}; on-screen text in English)\n\n"
           f"{beat_table(script, beats)}\n\n")
    if plan is None:
        ask += "Write the shot plan for these beats. Reply with ONLY the plan JSON."
    else:
        ask += ("Your plan:\n" + json.dumps(plan, ensure_ascii=False) + "\n\nFix these points and keep everything else:\n"
                + "\n".join("- " + n for n in notes) + "\n\nReply with ONLY the full corrected plan JSON.")
    return _ask(cfg, [{"role": "system", "content": sys_msg}, {"role": "user", "content": ask}], budget, call_claude)


# ---------------------------------------------------------------- 3. checks
def _env(vid):
    return dict(os.environ, VIDEO=vid)


def gates(vid, vdir):
    """the kit's hard gates (06_CHECKS). -> (passed, report lines, problems for the director)"""
    res = run(["npx", "tsx", "--tsconfig", f"src/videos/{vid}/tsconfig.json", "src/engine/check/gates.ts"],
              cwd=CODE, env=_env(vid), capture=True, check=False, timeout=900)
    out = (res.stdout or "") + (res.stderr or "")
    if "GATES:" not in out:
        return False, out[-3000:], [f"the plan does not run: {out.strip().splitlines()[-1][:300] if out.strip() else 'no output'}"]
    keymap = json.loads((vdir / "keymap.json").read_text())
    problems = []
    for line in out.splitlines():
        m = re.match(r"FAIL\s+(\w+)\s+(\S+)\s+x\s*(\d+)\s+f(\d+)-(\d+)\s+(.*)", line)
        if not m:
            continue
        kind, key, n, f0, f1, msg = m.groups()
        where = f"{int(f0) / FPS:.1f}-{int(f1) / FPS:.1f} s"
        take, idx = key[:3], key[3:].rstrip("~")
        if take in keymap and idx.isdigit() and int(idx) < len(keymap[take]):
            b, c = keymap[take][int(idx)]
            where = f"beat {b} camera {c} ({where})"
        elif re.fullmatch(r"b\d\d", key):
            where = f"beat {int(key[1:])} ({where})"
        problems.append(f"{where}: {kind} x{n}: {msg} ({GATE_HELP.get(kind, '')})")
    return res.returncode == 0, out, problems


GATE_HELP = {"LOGIC": "people overlap or stand in something: move them to other slots",
             "FLOOR": "someone floats or sinks", "CAMIN": "the camera is inside a wall/prop: smaller size, other angle or height",
             "CAMFACE": "the camera is too close to a face: bigger size", "CROP": "a face is cut by the frame: bigger size or other angle",
             "OCCL": "the subject is hidden behind something: other angle", "FGBLOCK": "someone in front covers the subject: other angle or slots"}


def compile_checked(cfg, script, beats, vid, vdir, budget, call_claude, plan, label, repair=True):
    """plan -> compiled + gates green, with up to studio.repair_rounds director repairs. -> (plan, files, warnings, report)"""
    rounds = int(cfg["studio"].get("repair_rounds", 3)) if repair else 0
    for r in range(rounds + 1):
        files, problems, warnings = planc.compile_plan(plan, vdir)
        if files:
            planc.write(files, vdir)
            ok, report, problems = gates(vid, vdir)
            if ok:
                log(f"studio: {label} passes the gates" + (f" ({len(warnings)} warnings)" if warnings else ""))
                return plan, files, warnings, report
        log(f"studio: {label} round {r + 1}: {len(problems)} problem(s): {problems[:3]}", "WARN")
        if r == rounds:
            break
        plan = direct(cfg, script, beats, budget, call_claude, plan, problems[:25] + warnings[:5])
    raise RuntimeError(f"studio: {label} still fails the checks: {problems[:5]}")


# ---------------------------------------------------------------- 4. watch + judge
def render(vid, comp, out, timeout):
    """Remotion headless render (CPU WebGL). comp: Preview (540x960) or Video (1080x1920)."""
    args = ["npx", "remotion", "render", "src/index.ts", comp, str(out), "--codec", "h264", "--gl=swangle",
            "--color-space=bt709",   # -> yuv420p TV range (the default writes full-range yuvj420p, which QC/Instagram reject)
            f"--concurrency={max(1, os.cpu_count() or 2)}", "--log=error"]
    chrome = os.environ.get("CHROME", "/usr/bin/google-chrome")
    if Path(chrome).exists():
        args.append(f"--browser-executable={chrome}")
    run(args, cwd=CODE, env=_env(vid), timeout=timeout)
    if not Path(out).exists():
        raise RuntimeError(f"studio: Remotion wrote no {comp} video")
    return Path(out)


def watch(video, outdir):
    """the kit's 'watch the WHOLE preview': contact sheets every 0.5 s + motion.txt (CUT / POP / FREEZE)"""
    run([sys.executable, str(TOOLS / "sheet.py"), str(video), str(outdir), "0.5"], timeout=900)
    return sorted(Path(outdir).glob("sheet_*.jpg"))


def judge(cfg, script, beats, sheets, motion, budget, call_claude=None):
    """05_AGENT_TEAM judge on the contact sheets, by the same model family that directs (FreeLLMAPI vision, or Claude
    reading the sheet images). -> {"scores": {...}, "fix": [...]} or None when it is off or no model answers."""
    if not cfg["studio"].get("judge", True) or (budget is None and call_claude is None):
        return None
    brief = (KIT / "references/10_JUDGE.md").read_text(encoding="utf-8")
    text = f"{brief}\n\nShort: \"{script['title']}\"\n{beat_table(script, beats)}\n\nmotion.txt:\n{motion[:3000]}"
    try:
        if budget is None:
            paths = "\n".join(str(s.resolve()) for s in sheets[:8])
            res = freellm.extract_json(call_claude(f"{text}\n\nThe contact sheets (open each with the Read tool):\n{paths}",
                                                   tools="Read", max_turns=12, effort="medium",
                                                   model=cfg["studio"].get("claude_model")))
        else:
            content = [{"type": "text", "text": text}] + [
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(s.read_bytes()).decode()}}
                for s in sheets[:8]]
            res = freellm.extract_json(freellm.chat(cfg, [{"role": "user", "content": content}], budget))
        overall = float(res["scores"]["overall"])
    except (RuntimeError, ValueError, KeyError, TypeError) as e:
        log(f"studio: judge skipped ({str(e)[:200]})", "WARN")
        return None
    res["scores"]["overall"] = overall
    return res


# ---------------------------------------------------------------- the whole thing
def make(cfg, script, timeline, voice_wav, work, call_claude=None, plan=None):
    """-> finished mp4 (1080x1920, mixed sound). plan given = test mode (no model calls)."""
    st = cfg["studio"]
    vid = "v_" + work.name.replace("-", "_")
    vdir = setup_video(vid, script, timeline, voice_wav)
    beats = planc.read_timeline(vdir)
    offline = plan is not None
    budget = None   # None = Claude directs (studio.director: claude, no FreeLLMAPI running, or its monthly cap reached)
    if not offline and st.get("director", "freellm") == "freellm" and freellm.configured(cfg):
        try:
            budget = freellm.Budget(cfg)
        except RuntimeError as e:
            log(f"studio: {e}; Claude directs this one", "WARN")
    versions = work / "versions"
    timeout = int(st.get("render_timeout_minutes", 150)) * 60

    def version(n, plan, notes=None):
        d = versions / f"v{n}"
        d.mkdir(parents=True, exist_ok=True)
        if notes is not None:
            plan = direct(cfg, script, beats, budget, call_claude, plan, notes)
        plan, files, warnings, report = compile_checked(cfg, script, beats, vid, vdir, budget, call_claude, plan, f"v{n}",
                                                        repair=not offline)
        (d / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
        (d / "gates.txt").write_text(report + "\n" + "\n".join("WARNING " + w for w in warnings), encoding="utf-8")
        preview = render(vid, "Preview", d / "preview.mp4", timeout)
        sheets = watch(preview, d)
        motion = (d / "motion.txt").read_text() if (d / "motion.txt").exists() else ""
        verdict = None if offline else judge(cfg, script, beats, sheets, motion, budget, call_claude)
        if verdict:
            (d / "judge.json").write_text(json.dumps(verdict, indent=1, ensure_ascii=False), encoding="utf-8")
            log(f"studio: v{n} judge {verdict['scores']}")
        return {"n": n, "plan": plan, "files": files, "verdict": verdict}

    if plan is None:
        plan = direct(cfg, script, beats, budget, call_claude)
    best = version(1, plan)
    if best["verdict"] and best["verdict"]["scores"]["overall"] < float(st.get("good_enough", 8)) and best["verdict"].get("fix"):
        notes = [f"beat {f.get('beat')}: {f.get('issue')} -> {f.get('change', '')}" for f in best["verdict"]["fix"][:8]]
        try:
            v2 = version(2, best["plan"], notes)
            if v2["verdict"] and v2["verdict"]["scores"]["overall"] > best["verdict"]["scores"]["overall"]:
                best = v2
        except RuntimeError as e:
            log(f"studio: fix round failed ({str(e)[:200]}); keeping v1", "WARN")
    log(f"studio: final = v{best['n']}")
    planc.write(best["files"], vdir)
    picture = render(vid, "Video", work / "picture.mp4", timeout)
    sfx = json.loads(best["files"]["sfx.json"])
    out = sound.finish(picture, vdir / "voice.wav", sfx, script.get("mood", "mystery"), cfg, work / "studio_final.mp4")
    (work / "plan.json").write_text(json.dumps(best["plan"], indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(vdir, ignore_errors=True)
    return out
