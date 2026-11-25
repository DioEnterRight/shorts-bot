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


def test_plan_problems_name_the_beat_and_the_fix(vdir, plan):
    bad = copy.deepcopy(plan)
    bad["cast"]["extra"] = "goldman"                                    # same character twice
    bad["beats"][0]["people"][0]["at"] = "middle"                       # unknown slot
    bad["beats"][1]["camera"][1]["at"] = "word:zebra"                   # not a word of that beat
    bad["beats"][2]["camera"][0]["size"] = "EWS"                        # too wide indoors
    bad["beats"][3]["people"][0]["acts"][0][1] = "dance"                # unknown action
    bad["beats"][11]["props"][1]["model"] = "dungeon/unicorn"           # unknown model
    files, problems, _ = planc.compile_plan(bad, vdir)
    assert files is None
    text = "\n".join(problems)
    for needle in ("cast extra", "beat 1 person 1: unknown slot 'middle'", "beat 2 camera 2: \"zebra\" is not a word",
                   "beat 3 camera 1: EWS does not fit", "beat 4 person 1 act 1: unknown action 'dance'", "unknown model"):
        assert needle in text, needle


def test_wrong_beat_count_is_one_clear_problem(vdir, plan):
    files, problems, _ = planc.compile_plan({**plan, "beats": plan["beats"][:-1]}, vdir)
    assert files is None and problems == [f"the plan has 11 beats, the script has 12: one beat per script line"]


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


def test_gate_report_becomes_director_problems(tmp_path, monkeypatch):
    (tmp_path / "keymap.json").write_text(json.dumps({"b01": [[1, 1], [1, 2]], "b03": [[3, 1], [4, 1], [4, 2]]}))
    out = ("FAIL   OCCL b032              x 29  f64-120  man face behind youngwoman\n"
           "FAIL   LOGIC b04              x  3  f200-210  PP man/kid\nwarn   EDGE b010   x 2  f1-2  edge\n\nGATES: FAIL  hard=32")
    monkeypatch.setattr(studio, "run", lambda *a, **k: type("R", (), {"stdout": out, "stderr": "", "returncode": 1})())
    ok, _, problems = studio.gates("x", tmp_path)
    assert not ok and len(problems) == 2
    assert problems[0].startswith("beat 4 camera 2 (2.1-4.0 s): OCCL x29") and "other angle" in problems[0]
    assert problems[1].startswith("beat 4 (6.7-7.0 s): LOGIC x3")


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
        ok, report, problems = studio.gates(vid, vdir)
        assert ok, problems
    finally:
        import shutil
        shutil.rmtree(vdir, ignore_errors=True)
