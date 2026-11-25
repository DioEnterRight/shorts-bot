"""The head skill (animated-shorts-kit): its files, the shot-plan compiler, the director brief and the kit's gates."""
import copy
import json
import re
import subprocess

import pytest

from pipeline import studio
from pipeline.common import KIT, ROOT

planc = studio.planc


def _timeline(tmp_path, script):
    """a real timeline.ts (kit's timeline.py) from fake word timings at the kit pace (3.5 words/s)"""
    words, t = [], 0.15
    for sc in script["scenes"]:
        for w in sc["line"].split():
            words.append({"w": w, "s": round(t, 3), "e": round(t + 0.25, 3)}); t += 0.286
        t += 0.2
    (tmp_path / "words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "script.txt").write_text("\n".join(f"[{planc.beat_name(i)}] {sc['line']}" for i, sc in enumerate(script["scenes"])),
                                         encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{t + 0.4:.2f}",
                    str(tmp_path / "voice.wav")], check=True)
    subprocess.run(["python3", str(studio.TOOLS / "timeline.py"), str(tmp_path / "script.txt"), str(tmp_path / "words.json"),
                    str(tmp_path / "voice.wav"), str(tmp_path / "timeline.ts")], check=True, capture_output=True)
    return tmp_path


@pytest.fixture
def plan():
    return json.loads((ROOT / "prompts" / "sample_plan.json").read_text(encoding="utf-8"))


@pytest.fixture(params=["en", "hi"])
def vdir(request, tmp_path, sample):
    return _timeline(tmp_path, sample(request.param))


def test_skill_is_the_single_head_skill():
    skills = sorted(p.name for p in (ROOT / ".claude" / "skills").iterdir())
    assert skills == ["animated-shorts-kit"]
    text = (KIT / "SKILL.md").read_text(encoding="utf-8")
    front = re.match(r"---\nname: (.+)\ndescription: (.+)\n---\n", text)
    assert front and front.group(1) == "animated-shorts-kit" and len(front.group(2)) <= 1024
    for ref in re.findall(r"`(references/[\w.]+|library/\w+/|code/CODE_README.md)`", text):
        assert (KIT / ref).exists(), ref
    for f in ("AGENTS.md", "CLAUDE.md"):
        assert ".claude/skills/animated-shorts-kit/SKILL.md" in (ROOT / f).read_text(encoding="utf-8")


def test_sample_plan_compiles_in_both_languages(vdir, plan):
    files, problems, warnings = planc.compile_plan(plan, vdir)
    assert problems == [] and files
    assert set(files) >= {"stage.ts", "takes.ts", "set.tsx", "solids.ts", "look.ts", "tsconfig.json", "keymap.json", "sfx.json"}
    km = json.loads(files["keymap.json"])
    assert sum(len(v) for v in km.values()) == sum(len(b["camera"]) for b in plan["beats"])
    assert "dungeon/chest_gold" in files["set.tsx"] and "prop gold" in files["solids.ts"]
    assert all(0 <= t <= 60 and n in planc.SFX for t, n in json.loads(files["sfx.json"]))


def test_director_mistakes_are_repaired_not_rejected(vdir, plan):
    """every mistake type the free models made on 25 Nov 2026 gets a FIX, not a rejected plan"""
    bad = copy.deepcopy(plan)
    b = bad["beats"]
    bad["cast"]["extra"] = "goldman"                                          # same character twice
    b[0]["people"][0]["at"] = "middle"                                        # unknown slot
    b[1]["camera"][1]["at"] = "word:zebra"                                    # not a word of that beat
    b[2]["camera"][0]["size"] = "EWS"                                         # too wide indoors
    b[3]["people"][0]["acts"][0][1] = "dance"                                 # unknown action
    b[1]["props"] = [{"name": "car", "model": "city/car_sedan", "at": "right"},
                     {"name": "bills", "model": "dungeon/coin_stack_large", "at": "center"}]   # big prop, slot of a person
    b[3]["props"] = [{"name": "bills", "model": "coin_stack_small", "at": "center"}]           # dup name, short model name
    b[4]["people"][0]["look"] = "right"                                       # a slot as look
    b[4]["sfx"] = [["start", "clock_tick"]]                                   # unknown sound
    b[5]["camera"][1]["on"] = ["prop:clock"]                                  # prop that does not exist
    b[0]["camera"].append({"at": 1.7, "on": ["hero"], "size": "MCU"})         # keys too close
    files, problems, warnings = planc.compile_plan(bad, vdir)
    assert problems == [] and files
    fixes = "\n".join(w for w in warnings if w.startswith("FIX "))
    for needle in ("cast extra", "beat 1 person 1: slot 'middle'", "beat 2 camera 2: 'zebra' is not said", "EWS does not fit",
                   "'dance'", "city/car_sedan is too big", "name 'bills' -> bills_2", "model 'coin_stack_small' -> dungeon/coin_stack_small",
                   "look 'right' -> auto", "sound 'clock_tick' -> tick", "'prop:clock' is not a prop here",
                   "under 0.8 s after the previous one"):
        assert needle in fixes, needle
    clean = json.loads(files["plan.json"])
    assert clean["cast"]["extra"] != "goldman" and clean["beats"][0]["people"][0]["at"] in planc.SLOTS


def test_wrong_beat_count_is_repaired(vdir, plan):
    files, problems, warnings = planc.compile_plan({**plan, "beats": plan["beats"][:-1]}, vdir)
    assert files and not problems and any("beat 12 was missing" in w for w in warnings)
    files, problems, _ = planc.compile_plan({**plan, "beats": plan["beats"] + plan["beats"][:2]}, vdir)
    assert files and not problems


def test_garbage_plan_is_one_clear_problem(vdir):
    for junk in ({}, {"beats": []}, "nope", {"beats": "x"}):
        files, problems, _ = planc.compile_plan(junk, vdir)
        assert files is None and problems == ['the plan must be {"cast": {...}, "beats": [...]}']


def test_prop_turn_is_camera_relative():
    p = planc.Plan({"beats": []}, [])
    assert p.place("diner", "center") == [-9.25, 0, 19.9]
    assert planc._prop_extent("city/car_sedan", 1, 90) == pytest.approx(tuple(reversed(planc._prop_extent("city/car_sedan", 1, 0))))


def test_autofix_changes_only_failing_keys_and_climbs_from_the_best_state():
    plan = {"cast": {"a": "man", "b": "kid"}, "beats": [
        {"spot": "grocery_inside", "people": [{"role": "a", "at": "left"}, {"role": "b", "at": "right"}], "props": [],
         "camera": [{"at": "start", "on": ["a", "b"], "size": "FS", "angle": 0, "height": 4, "fov": 40},
                    {"at": 1.5, "on": ["a"], "size": "MS", "angle": 20, "height": 4, "fov": 40}]}]}
    tries = {}
    f = {"kind": "CAMIN", "key": "b011", "beat": 1, "cam": 2, "n": 9, "msg": "camera inside grocery wall"}
    assert studio.autofix(plan, [f], tries, planc.SPOTS)
    k0, k1 = plan["beats"][0]["camera"]
    assert k0["size"] == "FS" and k1["size"] == "MCU"                     # only the failing key, first CAMIN try = closer
    studio.autofix(plan, [dict(f, n=3)], tries, planc.SPOTS)                # better -> the next try builds on MCU
    assert k1["size"] == "MCU" and k1["fov"] == 52
    for _ in range(30):                                                     # tries used up -> the person moves
        studio.autofix(plan, [{"kind": "OCCL", "key": "b011", "beat": 1, "cam": 2, "n": 9, "msg": "man face behind grocery counter"}],
                       tries, planc.SPOTS)
    assert plan["beats"][0]["people"][0]["at"] != "left"


def test_logic_failures_move_the_person():
    plan = {"cast": {"a": "man", "b": "kid"}, "beats": [
        {"spot": "bank", "people": [{"role": "a", "at": "left", "walk": {"to": "far_right", "start": "start", "seconds": 2}},
                                    {"role": "b", "at": "right"}], "props": [], "camera": []}]}
    f = {"kind": "LOGIC", "key": "b01", "beat": 1, "cam": None, "n": 4, "msg": "PP kid/man"}
    assert studio.autofix(plan, [f], {}, planc.SPOTS)
    a = plan["beats"][0]["people"][0]
    assert "walk" not in a and a["at"] == "far_right"                      # the walk is dropped, he stands where he was going


def test_director_chain_escalates_to_claude():
    cfg = {"studio": {"director": "freellm", "repair_rounds": 3, "rescue": True, "rescue_model": "opus", "rescue_rounds": 2}}
    assert studio.directors(cfg, object(), lambda *a, **k: "") == [(("freellm", None), 3), (("claude", "opus"), 2)]
    assert studio.directors(cfg, None, lambda *a, **k: "") == [(("claude", "opus"), 2)]
    cfg["studio"].update(director="claude", claude_model="sonnet")
    assert studio.directors(cfg, None, lambda *a, **k: "") == [(("claude", "sonnet"), 3), (("claude", "opus"), 2)]
    assert studio.directors({"studio": {**cfg["studio"], "rescue": False}}, None, None) == []


def test_slots_turn_with_the_spot():
    p = planc.Plan({"beats": []}, [])
    assert p.place("bank", "right") == [23.5, 0, 6.4]                    # camera on +z: right = +x
    assert p.place("diner", "right") == [-10.35, 0, 19.9]                # camera on -z: right = -x
    assert p.place("street", "right") == [0.0, 0, 12.1]                  # camera down the street: right = -z


def test_director_brief_quotes_the_skill():
    b = studio.director_brief()
    for needle in ("# The shot plan", "Camera rules (03_CAMERA_GRAMMAR.md)", "Edit only at a location", "goldman", "bank:", "dungeon/chest_gold",
                   "eureka", "shock"):
        assert needle in b, needle
    assert len(b) < 40000   # fits any free model's context with room for the script


def test_gate_report_becomes_failures(tmp_path, monkeypatch):
    (tmp_path / "keymap.json").write_text(json.dumps({"b01": [[1, 1], [1, 2]], "b03": [[3, 1], [4, 1], [4, 2]]}))
    out = ("FAIL   OCCL b032              x 29  f64-120  man face behind youngwoman\n"
           "FAIL   LOGIC b04              x  3  f200-210  PP man/kid\nwarn   EDGE b010   x 2  f1-2  edge\n\nGATES: FAIL  hard=32")
    monkeypatch.setattr(studio, "run", lambda *a, **k: type("R", (), {"stdout": out, "stderr": "", "returncode": 1})())
    ok, _, fails = studio.gates("x", tmp_path)
    assert not ok and len(fails) == 2
    assert fails[0]["text"].startswith("beat 4 camera 2 (2.1-4.0 s): OCCL x29") and "other angle" in fails[0]["text"]
    assert (fails[0]["beat"], fails[0]["cam"], fails[0]["n"]) == (4, 2, 29)
    assert fails[1]["text"].startswith("beat 4 (6.7-7.0 s): LOGIC x3") and fails[1]["cam"] is None


@pytest.mark.slow
@pytest.mark.skipif(not (studio.CODE / "node_modules" / "remotion").exists(), reason="run npm ci in the kit's code/ first")
def test_sample_plan_passes_the_kit_gates(tmp_path, sample, plan):
    vid = "zz_pytest_gates"
    vdir = studio.CODE / "src" / "videos" / vid
    try:
        vdir.mkdir(parents=True, exist_ok=True)
        _timeline(vdir, sample("en"))
        files, problems, _ = planc.compile_plan(plan, vdir)
        assert not problems
        planc.write(files, vdir)
        ok, report, fails = studio.gates(vid, vdir)
        assert ok, fails
    finally:
        import shutil
        shutil.rmtree(vdir, ignore_errors=True)


def test_hindi_captions_are_roman_hinglish_on_the_voice_timings():
    script = {"scenes": [{"line": "बात सच है", "caption": "baat sach hai"}, {"line": "ये भी", "caption": "ye bhi sach"}]}
    timeline = [{"words": [{"word": "बात", "start": 0.0, "end": 0.3}, {"word": "सच", "start": 0.35, "end": 0.6},
                           {"word": "है", "start": 0.65, "end": 0.9}]},
                {"words": [{"word": "ये", "start": 1.2, "end": 1.4}, {"word": "भी", "start": 1.45, "end": 1.8}]}]
    w = studio.caption_words(script, timeline)
    assert [x["w"] for x in w] == ["baat", "sach", "hai", "ye", "bhi", "sach"]
    assert w[1]["s"] == 0.35                                   # same count: exact voice timings
    assert w[3]["s"] == 1.2 and w[-1]["e"] <= 1.8               # other count: spread over the line
    assert [x["w"] for x in studio.caption_words({"scenes": [{"line": "hi there"}]},
                                                 [{"words": [{"word": "hi", "start": 0, "end": 1}]}])] == ["hi"]


def test_build_escalates_from_free_model_to_claude(tmp_path, monkeypatch):
    """free model: one 502, then plans that never pass -> Claude gets the best failed plan + its problems and wins"""
    cfg = {"studio": {"director": "freellm", "repair_rounds": 2, "rescue": True, "rescue_model": "opus", "rescue_rounds": 1}}
    seen = []

    def solve(cfg_, vid, vdir, plan, label):
        ok = plan.get("by") == "claude"
        return {"ok": ok, "plan": plan, "files": {}, "fails": [], "warnings": [],
                "problems": [] if ok else ["beat 1: still bad"], "report": ""}

    def direct(cfg_, script, beats, director, budget, call_claude, work, plan=None, notes=None):
        seen.append((director[0], plan is not None, bool(notes)))
        if director[0] == "freellm" and len(seen) == 1:
            raise RuntimeError("HTTP 502")
        return {"by": director[0]}

    monkeypatch.setattr(studio, "solve", solve)
    monkeypatch.setattr(studio, "direct", direct)
    with pytest.raises(RuntimeError, match="still fails"):   # free model only: 502 -> nothing to fall back on
        studio.build({"studio": {**cfg["studio"], "rescue": False}}, {}, [], "v", tmp_path, object(), None, None, "v1", tmp_path)
    seen.clear()
    monkeypatch.setattr(studio, "direct", direct)
    res = studio.build(cfg, {}, [], "v", tmp_path, object(), lambda *a, **k: "", {"by": "freellm"}, "v1", tmp_path)
    assert res["ok"] and res["plan"]["by"] == "claude"
    assert seen[-1] == ("claude", True, True)                 # Claude starts from the failed plan WITH its problems
    assert len(list((tmp_path / "versions" / "v1" / "rounds").glob("round_*.json"))) >= 2
