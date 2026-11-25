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
    models, pack = [], None   # MODELS.md minus building parts (they are not props)
    for line in (KIT / "library/environments/MODELS.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"## (\w+) \(", line)
        pack = m.group(1) if m else pack
        if pack and not line.startswith("#") and re.search(r"\w+ [\d.]+x", line):
            line = ", ".join(e for e in line.split(", ") if f"{pack}/{e.split(' ')[0]}" in planc.MODEL_INDEX)
        models.append(line)
    models = "\n".join(models)
    return "\n\n".join([
        (KIT / "references/09_PLAN_FORMAT.md").read_text(encoding="utf-8"),
        "## Camera rules (03_CAMERA_GRAMMAR.md)\n" + _section("references/03_CAMERA_GRAMMAR.md", "5. Rules for our camera"),
        "## Picture rules (02_STORY_FORMULA.md)\n" + _section("references/02_STORY_FORMULA.md", "Picture"),
        "## Characters (cast ids)\n" + chars,
        "## Spots\n" + spots,
        "## Actions\n" + ", ".join(planc.ACTS) + "\n\n## Expressions\n" + ", ".join(planc.EXPR),
        models,
    ])


def _ask(cfg, messages, director, budget, call_claude, work):
    """one director call. director = ("freellm", None) or ("claude", model). -> parsed JSON (raises on failure)"""
    who, model = director
    if who == "freellm":
        return freellm.extract_json(freellm.chat(cfg, messages, budget))
    system = next(m["content"] for m in messages if m["role"] == "system")
    ask = "\n\n".join(m["content"] for m in messages if m["role"] != "system")
    return freellm.extract_json(call_claude(ask, max_turns=1, effort=cfg["studio"].get("claude_effort", "medium"),
                                            model=model, system=system))


def direct(cfg, script, beats, director, budget, call_claude, work, plan=None, notes=None):
    """first draft (plan None) or a corrected full plan from notes (problems / judge fixes)."""
    ask = (f"Short: \"{script['title']}\" (narration language: {script['language']}; the words below are what the "
           f"captions show, use them for word: times)\n\n{beat_table(script, beats)}\n\n")
    if plan is None:
        ask += "Write the shot plan for these beats. Reply with ONLY the plan JSON."
    else:
        ask += ("Your plan (small mistakes were already repaired by the compiler):\n" + json.dumps(plan, ensure_ascii=False)
                + "\n\nFix these points and keep everything else:\n" + "\n".join("- " + n for n in notes)
                + "\n\nReply with ONLY the full corrected plan JSON.")
    return _ask(cfg, [{"role": "system", "content": director_brief()}, {"role": "user", "content": ask}], director, budget,
                call_claude, work)


def directors(cfg, budget, call_claude):
    """the escalation chain: [(director, repair rounds)]. studio.director first (freellm or claude), then Claude's rescue model."""
    st, chain = cfg["studio"], []
    if budget is not None and st.get("director", "claude") == "freellm":
        chain.append((("freellm", None), int(st.get("repair_rounds", 3))))
    if call_claude is not None:
        if st.get("director") == "claude":
            chain.append((("claude", st.get("claude_model", "sonnet")), int(st.get("repair_rounds", 3))))
        if st.get("rescue", True) and (not chain or chain[-1][0] != ("claude", st.get("rescue_model", "opus"))):
            chain.append((("claude", st.get("rescue_model", "opus")), int(st.get("rescue_rounds", 2))))
    return chain


# ---------------------------------------------------------------- 3. checks
def _env(vid):
    return dict(os.environ, VIDEO=vid)


def gates(vid, vdir):
    """the kit's hard gates (06_CHECKS). -> (passed, report, failures [{kind, key, beat, cam, n, f0, f1, msg, text}])"""
    res = run(["npx", "tsx", "--tsconfig", f"src/videos/{vid}/tsconfig.json", "src/engine/check/gates.ts"],
              cwd=CODE, env=_env(vid), capture=True, check=False, timeout=900)
    out = (res.stdout or "") + (res.stderr or "")
    if "GATES:" not in out:
        last = out.strip().splitlines()[-1][:300] if out.strip() else "no output"
        return False, out[-3000:], [{"kind": "RUN", "key": "", "beat": None, "cam": None, "n": 0, "f0": 0, "f1": 0, "msg": last,
                                     "text": f"the plan does not run: {last}"}]
    keymap = json.loads((vdir / "keymap.json").read_text())
    fails = []
    for line in out.splitlines():
        m = re.match(r"FAIL\s+(\w+)\s+(\S+)\s+x\s*(\d+)\s+f(\d+)-(\d+)\s+(.*)", line)
        if not m:
            continue
        kind, key, n, f0, f1, msg = m.groups()
        when = f"{int(f0) / FPS:.1f}-{int(f1) / FPS:.1f} s"
        beat = cam = None
        take, idx = key[:3], key[3:].rstrip("~")
        if take in keymap and idx.isdigit() and int(idx) < len(keymap[take]):
            beat, cam = keymap[take][int(idx)]
            where = f"beat {beat} camera {cam} ({when})"
        elif re.fullmatch(r"b\d\d", key):
            beat = int(key[1:])
            where = f"beat {beat} ({when})"
        else:
            where = when
        fails.append({"kind": kind, "key": key, "beat": beat, "cam": cam, "n": int(n), "f0": int(f0), "f1": int(f1), "msg": msg,
                      "text": f"{where}: {kind} x{n}: {msg} ({GATE_HELP.get(kind, '')})"})
    return res.returncode == 0, out, fails


GATE_HELP = {"LOGIC": "people overlap or stand in something: move them to other slots",
             "FLOOR": "someone floats or sinks", "CAMIN": "the camera is inside a wall/prop: smaller size, other angle or height",
             "CAMFACE": "the camera is too close to a face: bigger size", "CROP": "a face is cut by the frame: bigger size or other angle",
             "OCCL": "the subject is hidden behind something: other angle", "FGBLOCK": "someone in front covers the subject: other angle or slots"}

# deterministic camera repairs, tried in order, each from the director's original key:
# (size steps, angle add, angle x, height add, fov add, solo) - solo = frame only the first subject
_T = lambda ds=0, da=0, ax=1, dh=0, df=0, solo=False: (ds, da, ax, dh, df, solo)
CAM_TRIES = {
    "CAMIN":   [_T(-1), _T(df=12), _T(ax=0.4), _T(dh=10), _T(-1, df=12), _T(-1, ax=0.3, dh=8, df=10), _T(-2, ax=0.3, dh=6, df=12)],
    "CROP":    [_T(1), _T(ax=0.3), _T(1, ax=0.3, dh=4), _T(2), _T(1, df=-8)],
    "CAMFACE": [_T(1), _T(2), _T(1, ax=0.5, dh=6)],
    "OCCL":    [_T(da=25), _T(da=-25), _T(dh=12), _T(da=45, dh=6), _T(da=-45, dh=6), _T(1, ax=0.3, dh=15)],
    "FGBLOCK": [_T(da=25), _T(da=-25), _T(dh=15), _T(-1), _T(da=45, dh=10), _T(da=-45, dh=10)],
    "FLOOR":   [],
}
CAM_FALLBACK = [_T(solo=True), _T(-1, df=12, solo=True), _T(ax=0.3, dh=12, df=15), _T(-1, ax=0, dh=6, df=15, solo=True),
                _T(da=30, dh=10), _T(da=-30, dh=10), _T(1, ax=0, dh=20)]
WALLS = ("wall", "facade", "door", "bldg", "shelf", "island")          # hidden by these = the camera is outside / behind them
LOW = ("counter", "pyramid", "bench", "prop", "car", "meter", "mailbox", "hydrant", "bin", "lamp", "clock")          # hidden by these = look over them, or move the person
OVER = [_T(dh=12), _T(dh=22), _T(da=30, dh=12), _T(da=-30, dh=12)]


def _cam_tries(f):
    """-> (list name, variations) for one gate failure"""
    if f["kind"] == "OCCL" and any(w in f["msg"] for w in LOW):
        return "over", OVER
    kind = "CAMIN" if f["kind"] == "OCCL" and any(w in f["msg"] for w in WALLS) else f["kind"]
    return kind, CAM_TRIES.get(kind, []) + CAM_FALLBACK


def _move_person(plan, beat, person, tries, bn):
    """a walk is dropped first; then the person steps to the nearest slot not tried yet. -> True when moved"""
    w = person.pop("walk", None)
    if w:   # stand where the walk was going
        person["at"] = w["to"]
        return True
    k = tries.setdefault(("slot", bn, person["role"]), [person["at"]])
    props = {pr["at"] for b in plan["beats"] if b["spot"] == beat["spot"] for pr in b.get("props", [])}
    taken = {p["at"] for p in beat["people"]} | {p.get("walk", {}).get("to") for p in beat["people"]} | props | set(k)
    nxt = planc._nearest_free(k[0], taken)
    if nxt:
        k.append(nxt)
        person["at"] = nxt
    return bool(nxt)


def autofix(plan, fails, tries, spots, timing=None):
    """change only what failed (hill-climbing, per camera key): each failing key keeps its best state so far (fewest
    failing frames) and the next variation for its main failure is tried on top of that. When a key's variations are
    used up, the person who is hidden / cut moves to another slot. People standing in something or in each other move.
    tries persists across rounds. -> True when something changed."""
    changed = False
    sizes = planc.SIZES
    cast_of = {who: role for role, who in plan["cast"].items()}
    per_key, moved = {}, set()
    for f in fails:
        if f["beat"] is None or f["beat"] > len(plan["beats"]):
            continue
        beat = plan["beats"][f["beat"] - 1]
        if f["kind"] == "LOGIC":
            m = re.match(r"(PP|PS|PCAR|PT|PM)\s+([A-Za-z0-9_]+)(?:\(bg\))?(?:/([A-Za-z0-9_]+))?", f["msg"])
            if not m:
                continue
            who = m.group(3) if m.group(1) == "PP" and m.group(3) in cast_of else m.group(2)
            person = next((p for p in beat["people"] if p["role"] == cast_of.get(who)), None)
            if person and (f["beat"], person["role"]) not in moved:
                moved.add((f["beat"], person["role"]))
                changed |= _move_person(plan, beat, person, tries, f["beat"])
            continue
        if f["cam"] is not None and f["cam"] <= len(beat["camera"]):
            per_key.setdefault((f["beat"], f["cam"]), []).append(f)
    for (bn, cn), fl in per_key.items():
        beat, key = plan["beats"][bn - 1], plan["beats"][bn - 1]["camera"][cn - 1]
        frames = sum(f["n"] for f in fl)
        prev = plan["beats"][bn - 2] if bn > 1 else None
        if (timing and cn == 1 and key["at"] == "start" and prev and prev["spot"] == beat["spot"] and not beat.get("cut")
                and min(f["f0"] for f in fl) / FPS < timing[bn - 1]["start"] + 0.7 and ("cut", bn) not in tries):
            tries[("cut", bn)] = True   # the camera is still travelling when the new beat's subject appears: cut there
            beat["cut"] = True
            changed = True
            continue
        state = {k: key[k] for k in ("size", "angle", "height", "fov", "on")}
        best = tries.get(("best", bn, cn))
        if best is None or frames < best[0]:
            best = tries[("best", bn, cn)] = (frames, state)
        main = max(fl, key=lambda f: f["n"])
        lname, opts = _cam_tries(main)
        nk = ("n", bn, cn, lname)
        n = tries.get(nk, 0)
        if n >= len(opts):   # every variation tried: move the person who is hidden / cut / in the way
            who = main["msg"].split()[0].split("(")[0]
            if who.startswith("prop:") and len(key["on"]) > 1 and ("unprop", bn, cn) not in tries:
                tries[("unprop", bn, cn)] = True   # a prop that stays hidden: frame the people instead
                key["on"] = [x for x in key["on"] if not x.startswith("prop:")] or key["on"]
                for k_ in [k_ for k_ in tries if k_[1:3] == (bn, cn) and k_[0] in ("n", "best")]:
                    del tries[k_]
                changed = True
                continue
            if who.startswith("prop:") and ("unprop", bn, cn) not in tries and beat["people"]:
                tries[("unprop", bn, cn)] = True
                key["on"] = [beat["people"][0]["role"]]
                for k_ in [k_ for k_ in tries if k_[1:3] == (bn, cn) and k_[0] in ("n", "best")]:
                    del tries[k_]
                changed = True
                continue
            person = next((p for p in beat["people"] if plan["cast"].get(p["role"]) == who), None)
            if person and _move_person(plan, beat, person, tries, bn):
                for k_ in [k_ for k_ in tries if k_[1:3] == (bn, cn)]:
                    del tries[k_]
                changed = True
            continue
        tries[nk] = n + 1
        ds, da, ax, dh, df, solo = opts[n]
        base = best[1]
        mx = sizes.index(spots[beat["spot"]]["max"])
        key["on"] = base["on"][:1] if solo else base["on"]
        key["size"] = sizes[max(0, min(mx, sizes.index(base["size"]) + ds))]
        key["angle"] = max(-75, min(75, base["angle"] * ax + da))
        key["height"] = max(-10, min(45, base["height"] + dh))
        key["fov"] = max(25, min(60, base["fov"] + df))
        changed = True
    return changed


def solve(cfg, vid, vdir, plan, label):
    """compile + gates + deterministic repairs + waivers for 1-2 checked-frame glitches. No model calls.
    -> dict(ok, plan, files, fails, problems, warnings, report)"""
    st = cfg["studio"]
    best, tries, waivers = None, {}, []
    timing = planc.read_timeline(vdir)
    for r in range(int(st.get("autofix_rounds", 24)) + 1):
        files, problems, warnings = planc.compile_plan(plan, vdir, waivers)
        if not files:
            return {"ok": False, "plan": plan, "files": None, "fails": [], "problems": problems, "warnings": warnings, "report": ""}
        plan = json.loads(files["plan.json"])   # the working copy autofix changes
        planc.write(files, vdir)
        ok, report, fails = gates(vid, vdir)
        cur = {"ok": ok, "plan": json.loads(files["plan.json"]), "files": files, "fails": fails, "problems": [], "warnings": warnings, "report": report}
        frames = sum(f["n"] for f in fails)
        if best is None or ok or frames < sum(f["n"] for f in best["fails"]):
            best = cur
        if ok:
            break
        small = int(st.get("waive_max", 2))
        tiny = [f for f in fails if f["n"] <= small and f["kind"] != "RUN"
                and not any(w["key"] == f["key"] and w["kind"] == f["kind"] for w in waivers)]
        if tiny:   # a glitch of a frame or two is invisible: waive it the kit's way (with the reason) and keep fixing the rest
            waivers += [{"key": f["key"], "kind": f["kind"], "why": f"auto: {f['n']} checked frame(s) of {f['msg']}"} for f in tiny]
            log(f"studio: {label}: waiving {len(tiny)} glitch(es) of <= {small} checked frames")
            fails = [f for f in fails if f not in tiny]
            if not fails:
                continue
        if r == int(st.get("autofix_rounds", 24)) or not autofix(plan, fails, tries, planc.SPOTS, timing):
            break
        log(f"studio: {label} autofix {r + 1}: {len(fails)} gate failure(s), {frames} frames")
    if not best["ok"] and best is not cur:
        planc.write(best["files"], vdir)
    return best


def build(cfg, script, beats, vid, vdir, budget, call_claude, plan, label, work, offline=False):
    """plan (or None: the first director drafts it) -> a plan whose files pass the gates.
    Free director rounds, then Claude rescue rounds; every round is saved in <work>/versions/<label>/rounds/."""
    rd = Path(work) / "versions" / label / "rounds"
    rd.mkdir(parents=True, exist_ok=True)
    chain = [] if offline else directors(cfg, budget, call_claude)
    n = 0

    def attempt(p, who):
        nonlocal n
        n += 1
        res = solve(cfg, vid, vdir, p, label)
        (rd / f"round_{n:02d}.json").write_text(json.dumps(
            {"director": who, "ok": res["ok"], "problems": res["problems"], "gate_failures": [f["text"] for f in res["fails"]],
             "fixes": [w for w in res["warnings"] if w.startswith("FIX ")], "plan": res["plan"]}, indent=1, ensure_ascii=False),
            encoding="utf-8")
        nfix = sum(1 for w in res["warnings"] if w.startswith("FIX "))
        log(f"studio: {label} round {n} ({who}): " + ("PASS" if res["ok"] else
            f"{len(res['problems'])} plan problem(s), {len(res['fails'])} gate failure(s)") + f", {nfix} auto-fixes")
        return res

    if offline:
        res = attempt(plan, "sample")
        if res["ok"]:
            return res
        raise RuntimeError(f"studio: {label} sample plan fails: {(res['problems'] + [f['text'] for f in res['fails']])[:5]}")
    last = None
    for director, rounds in chain:
        who = director[0] + (f":{director[1]}" if director[1] else "")
        try:
            if plan is None:
                plan = direct(cfg, script, beats, director, budget, call_claude, work)
            elif last is not None:   # a new director starts by fixing the best failed plan so far
                plan = direct(cfg, script, beats, director, budget, call_claude, work, last["plan"],
                              last["problems"][:25] + [f["text"] for f in last["fails"][:25]])
            for r in range(rounds + 1):
                last = attempt(plan, who)
                if last["ok"]:
                    return last
                if r == rounds:
                    break
                notes = last["problems"][:25] + [f["text"] for f in last["fails"][:25]]
                plan = direct(cfg, script, beats, director, budget, call_claude, work, last["plan"], notes)
        except (RuntimeError, ValueError) as e:
            log(f"studio: {label}: director {who} failed ({str(e)[:200]})", "WARN")
        if last is not None:
            plan = last["plan"]   # the next director starts from the best plan so far
        log(f"studio: {label}: escalating past {who}", "WARN")
    issues = (last["problems"] + [f["text"] for f in last["fails"]])[:5] if last else ["no director could write a plan"]
    raise RuntimeError(f"studio: {label} still fails the checks: {issues}")


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
    """05_AGENT_TEAM judge on the contact sheets: FreeLLMAPI vision (free), or Claude reading the sheet images when
    studio.claude_judge is on. -> {"scores": {...}, "fix": [...]} or None when it is off or no model answers."""
    st = cfg["studio"]
    if not st.get("judge", True) or (budget is None and (call_claude is None or not st.get("claude_judge", False))):
        return None   # no free vision model: skip it unless claude_judge (Claude reading 8 images costs many tokens)
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
    budget = None   # FreeLLMAPI: directs when studio.director is freellm, and judges (free vision) either way
    if not offline and freellm.configured(cfg):
        try:
            budget = freellm.Budget(cfg)
        except RuntimeError as e:
            log(f"studio: {e}; Claude directs this one", "WARN")
    versions = work / "versions"
    timeout = int(st.get("render_timeout_minutes", 150)) * 60

    def version(n, plan, notes=None):
        d = versions / f"v{n}"
        d.mkdir(parents=True, exist_ok=True)
        if notes is not None:   # the judge's fixes go to the best director available, then the same checks
            director = directors(cfg, budget, call_claude)[0][0]
            plan = direct(cfg, script, beats, director, budget, call_claude, work, plan, notes)
        res = build(cfg, script, beats, vid, vdir, budget, call_claude, plan, f"v{n}", work, offline)
        (d / "plan.json").write_text(json.dumps(res["plan"], indent=1, ensure_ascii=False), encoding="utf-8")
        (d / "gates.txt").write_text(res["report"] + "\n" + "\n".join("WARNING " + w for w in res["warnings"]), encoding="utf-8")
        preview = render(vid, "Preview", d / "preview.mp4", timeout)
        sheets = watch(preview, d)
        motion = (d / "motion.txt").read_text() if (d / "motion.txt").exists() else ""
        verdict = None if offline else judge(cfg, script, beats, sheets, motion, budget, call_claude)
        if verdict:
            (d / "judge.json").write_text(json.dumps(verdict, indent=1, ensure_ascii=False), encoding="utf-8")
            log(f"studio: v{n} judge {verdict['scores']}")
        return {"n": n, "plan": res["plan"], "files": res["files"], "verdict": verdict}

    best = version(1, plan)
    if best["verdict"] and best["verdict"]["scores"]["overall"] < float(st.get("good_enough", 8)) and best["verdict"].get("fix"):
        notes = [f"beat {f.get('beat')}: {f.get('issue')} -> {f.get('change', '')}" for f in best["verdict"]["fix"][:8]]
        try:
            v2 = version(2, best["plan"], notes)
            if v2["verdict"] and v2["verdict"]["scores"]["overall"] > best["verdict"]["scores"]["overall"]:
                best = v2
        except (RuntimeError, ValueError) as e:
            log(f"studio: fix round failed ({str(e)[:200]}); keeping v1", "WARN")
    log(f"studio: final = v{best['n']}")
    planc.write(best["files"], vdir)
    picture = render(vid, "Video", work / "picture.mp4", timeout)
    sfx = json.loads(best["files"]["sfx.json"])
    out = sound.finish(picture, vdir / "voice.wav", sfx, script.get("mood", "mystery"), cfg, work / "studio_final.mp4")
    (work / "plan.json").write_text(json.dumps(best["plan"], indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(vdir, ignore_errors=True)
    return out
