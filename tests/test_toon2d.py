"""toon2d engine wiring: timing conversion, storyboard prompt/fallback, plan check, vertical render. Offline."""
import json
import os
import subprocess
import sys

import pytest

from pipeline import toon2d
from pipeline.common import ROOT, load_config

TL = [
    {"start": 0.15, "end": 2.0, "words": [
        {"word": "A", "start": 0.15, "end": 0.3}, {"word": "man", "start": 0.3, "end": 0.6},
        {"word": "sold", "start": 0.6, "end": 0.9}, {"word": "it.", "start": 0.9, "end": 1.2},
        {"word": "Twice!", "start": 1.4, "end": 2.0}]},
    {"start": 2.3, "end": 4.0, "words": [
        {"word": "पैसा", "start": 2.3, "end": 2.8}, {"word": "गया।", "start": 2.8, "end": 3.3},
        {"word": "Wow", "start": 3.4, "end": 4.0}]},
]
SCRIPT = {"topic": "test", "scenes": [{"line": "A man sold it. Twice!", "emphasis": "sold"},
                                      {"line": "पैसा गया। Wow", "emphasis": "Wow"}]}


def test_timing_splits_lines_into_sentences():
    T = toon2d.timing_from_timeline(TL, 4.5)
    assert [s["text"] for s in T["sentences"]] == ["A man sold it.", "Twice!", "पैसा गया।", "Wow"]
    assert [s["i"] for s in T["sentences"]] == [0, 1, 2, 3]
    assert T["sentences"][2]["words"][0]["n"]          # Hindi words keep letters for cue matching
    assert T["duration"] == 4.5 and all(s["start"] <= s["end"] for s in T["sentences"])


def test_prompt_has_sentences_rules_and_reference():
    T = toon2d.timing_from_timeline(TL, 4.5)
    p = toon2d.build_prompt(SCRIPT, T, "9:16", "en")
    assert "0: A man sold it." in p and "3: Wow" in p and "VERTICAL 9:16" in p
    assert "leave out every x and y" in p and "## Shot kinds" in p and "{" + "sentences}" not in p
    assert "LANDSCAPE 16:9" in toon2d.build_prompt(SCRIPT, T, "16:9", "en")


def test_auto_story_covers_every_sentence_and_ends_on_polaroid():
    T = toon2d.timing_from_timeline(TL, 4.5)
    st = toon2d.auto_story(SCRIPT, T)
    assert [s["s"] for s in st["shots"]] == [[0], [1], [2], [3]]
    assert "polaroid" in st["shots"][-1] and st["cast"]["host"]
    assert st["shots"][0]["labels"][0]["at"] == "sold"


def test_config_and_engine_files():
    cfg = load_config()
    assert cfg["toon2d"]["model"] and cfg["toon2d"]["captions"] is True
    for f in ("engine/kit.py", "engine/shots.py", "fonts/Kalam-Bold.ttf", "CREDITS.md", "reference/story-format.md"):
        assert (ROOT / "toon2d" / f).exists(), f
    assert "ReachMora" in (ROOT / "toon2d" / "CREDITS.md").read_text(encoding="utf-8")


def test_viseme_track_maps_to_output_frames():
    pytest.importorskip("skia")
    sys.path.insert(0, str(ROOT / "toon2d"))
    from engine.render import Env

    class TL_:
        total_frames = 60
        T = {"duration": 2.0}
        def voice_segments(self): return [(0.0, 2.0, 0.0)]
    out = Env.from_visemes(TL_(), [[0, "X"], [10, "D"], [20, "E"], [30, "A"]])
    assert out[5] == "closed" and out[15] == "open" and out[25] == "o" and out[40] == "closed"


@pytest.mark.slow
def test_vertical_plan_and_stills(tmp_path):
    pytest.importorskip("skia")
    T = toon2d.timing_from_timeline(TL, 4.5)
    (tmp_path / "timing.json").write_text(json.dumps(T), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "4.5",
                    str(tmp_path / "voice.wav")], check=True)
    st = toon2d.auto_story(SCRIPT, T)
    st["shots"][1] = {"kind": "counter", "s": [1], "value": {"to": 2, "at": "Twice"}, "caption": "two sales"}
    (tmp_path / "story.json").write_text(json.dumps(st), encoding="utf-8")
    assert toon2d._serious(toon2d.check(tmp_path, "9:16")) == []
    env = dict(os.environ, RM_ASPECT="9:16", RM_CAPTIONS="1")
    subprocess.run([sys.executable, "-m", "engine", "stills", str(tmp_path)], cwd=ROOT / "toon2d", env=env, check=True)
    from PIL import Image
    w, h = Image.open(tmp_path / "work" / "sheet_1.jpg").size
    assert w == 6 * 216 and h == 384 + 34   # one row of six portrait tiles
    st["shots"][1]["kind"] = "nope"
    (tmp_path / "story.json").write_text(json.dumps(st), encoding="utf-8")
    assert any("unknown kind" in p for p in toon2d.check(tmp_path, "9:16"))


# ---------------- weekly long video ----------------
def test_longform_picks_best_recent_english_short():
    from datetime import datetime, timedelta, timezone
    from pipeline import longform
    now = datetime(2026, 11, 22, 10, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    d = lambda days: (now - timedelta(days=days)).isoformat(timespec="minutes")  # noqa: E731
    hist = {"videos": [
        {"id": "a", "topic": "old", "language": "en", "status": "published", "created": d(20)},
        {"id": "b", "topic": "hiccups", "language": "en", "status": "published", "created": d(3)},
        {"id": "c", "topic": "meteors", "language": "en", "status": "published", "created": d(2)},
        {"id": "h", "topic": "hindi", "language": "hi", "status": "published", "created": d(1)},
        {"id": "x", "topic": "gone", "language": "en", "status": "discarded", "created": d(1)}]}
    stats = {"videos": {"b": {"metrics": {"yt_views": 9000}}, "c": {"metrics": {"yt_views": 100}}}}
    assert longform.pick_source(hist, stats, now, set())["id"] == "b"          # best by analytics
    assert longform.pick_source(hist, {"videos": {}}, now, set())["id"] == "c"  # newest without data
    assert longform.pick_source(hist, stats, now, {"hiccups"})["id"] == "c"     # never the same topic twice
    with pytest.raises(RuntimeError):
        longform.pick_source({"videos": hist["videos"][3:]}, stats, now, set())


def test_longform_script_is_one_scene_per_sentence():
    from pipeline import longform
    longs = {"title": "T", "description": "D", "hashtags": ["#a"] * 12,
             "chapters": [{"title": "One", "paragraphs": ["First one. Second one! Third?"] * 4},
                          {"title": "Two", "paragraphs": ["Fourth one. Fifth one."] * 5}]}
    s = longform.to_script(longs, {"topic": "x"})
    assert len(s["scenes"]) == 22 and s["scenes"][1]["line"] == "Second one!"
    assert s["outline"][1].startswith("Chapter 'Two': about sentences 12-21") and len(s["hashtags"]) == 10
    with pytest.raises(ValueError):
        longform.to_script({**longs, "chapters": longs["chapters"][:1]}, {"topic": "x"})


def test_long_workflow_and_config():
    import yaml
    wf = yaml.safe_load((ROOT / ".github/workflows/long-video.yml").read_text())
    assert wf["concurrency"]["group"] == "shorts-bot"
    run_step = next(s for s in wf["jobs"]["long"]["steps"] if s.get("name", "").startswith("Make"))
    assert "pipeline.longform" in run_step["run"] and "YT_REFRESH_TOKEN" in run_step["env"]
    lc = load_config()["longform"]
    assert lc["privacy"] in ("private", "unlisted", "public") and 3 <= lc["minutes"] <= 15


class _Res:
    def __init__(self, rc, out): self.returncode, self.stdout, self.stderr = rc, out, ""


def test_check_raises_on_broken_install_but_reports_story_errors(monkeypatch, tmp_path):
    monkeypatch.setattr(toon2d, "run", lambda *a, **k: _Res(1, "Traceback (most recent call last):\nImportError: libEGL.so.1: cannot open"))
    with pytest.raises(RuntimeError, match="engine crashed: ImportError"):
        toon2d.check(tmp_path, "9:16")
    monkeypatch.setattr(toon2d, "run", lambda *a, **k: _Res(1, "Traceback (most recent call last):\nTypeError: can only concatenate str"))
    assert toon2d.check(tmp_path, "9:16") == ["TypeError: can only concatenate str"]   # goes to the repair round


def test_broken_install_skips_claude_retries(monkeypatch, tmp_path):
    T = toon2d.timing_from_timeline(TL, 4.5)
    calls = []
    monkeypatch.setattr(toon2d, "check", lambda *a: (_ for _ in ()).throw(RuntimeError("toon2d engine crashed: ImportError")))
    with pytest.raises(RuntimeError, match="engine crashed"):
        toon2d.storyboard(load_config(), SCRIPT, T, tmp_path, "9:16", "en",
                          lambda *a, **k: calls.append(1) or '{"cast":{},"shots":[]}', json.loads, use_claude=True)
    assert calls == [1]   # one Claude call, no second attempt on a crash


def test_render_falls_back_to_auto_story_when_claude_story_crashes(monkeypatch, tmp_path):
    cmds = []

    def fake_run(cmd, **k):
        cmds.append(cmd[3])
        if cmd[3] == "render" and cmds.count("render") == 1:
            raise RuntimeError("Command failed (1): TypeError")
        if cmd[3] == "final":
            (tmp_path / "toon2d" / "out").mkdir(parents=True, exist_ok=True)
            (tmp_path / "toon2d" / "out" / "final.mp4").write_bytes(b"x")
    monkeypatch.setattr(toon2d, "run", fake_run)
    monkeypatch.setattr(toon2d, "storyboard", lambda *a, **k: ({"shots": []}, "claude"))
    voice = tmp_path / "voice.wav"; voice.write_bytes(b"")
    out, source = toon2d.render(load_config(), SCRIPT, TL, voice, 4.5, tmp_path, "en", None, None)
    assert source == "auto" and cmds == ["render", "render", "audio", "final"]
    assert json.loads((tmp_path / "toon2d" / "story.json").read_text(encoding="utf-8"))["cast"]["host"]


@pytest.mark.parametrize("lang", ["en", "hi"])
def test_sample_storyboards_pass_the_plan_check(lang, tmp_path):
    pytest.importorskip("skia")
    script = json.loads((ROOT / "prompts" / f"sample_script_{lang}.json").read_text(encoding="utf-8"))
    tl, t = [], .2
    for sc in script["scenes"]:
        words = []
        for w in sc["line"].split():
            words.append({"word": w, "start": t, "end": t + .28}); t += .3
        tl.append({"words": words}); t += .3
    (tmp_path / "timing.json").write_text(json.dumps(toon2d.timing_from_timeline(tl, t), ensure_ascii=False), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", str(t),
                    str(tmp_path / "voice.wav")], check=True)
    (tmp_path / "story.json").write_text((ROOT / "prompts" / f"sample_story_{lang}.json").read_text(encoding="utf-8"),
                                         encoding="utf-8")
    assert toon2d.check(tmp_path, "9:16") == []    # no warnings at all: every sentence covered, every cue found


def test_variety_rules_flag_long_and_repeated_shots():
    T = toon2d.timing_from_timeline(TL, 4.5)     # sentences: 0.15-1.2, 1.4-2.0, 2.3-3.3, 3.4-4.0
    ok = {"shots": [{"kind": "closeup", "s": [0], "who": "a"}, {"kind": "wide", "s": [1], "chars": [{"id": "a"}]},
                    {"kind": "closeup", "s": [2, 3], "who": "a"}]}
    assert toon2d.variety_problems(ok, T) == []
    same = {"shots": [{"kind": "closeup", "s": [0], "who": "a", "set": "home"},
                      {"kind": "closeup", "s": [1], "who": "a", "set": "home"}]}
    assert "same kind, set and character" in toon2d.variety_problems(same, T)[0]
    T["sentences"][3]["end"] = 9.0
    long_ = {"shots": [{"kind": "wide", "s": [0, 1, 2, 3]}]}
    assert "give each sentence its own shot" in toon2d.variety_problems(long_, T)[0]


def test_calm_mode_and_quiet_mix_are_on_by_default():
    cfg = load_config()
    assert cfg["toon2d"]["calm"] is True and cfg["toon2d"]["music_db"] <= -20 and cfg["voice"]["gap_seconds"] >= 0.3
    assert toon2d._env("9:16", True, calm=True)["RM_CALM"] == "1"
    from pipeline import voice
    assert round(voice.pace_wpm([{"words": [{}] * 70, "end": 30.0}])) == 140
