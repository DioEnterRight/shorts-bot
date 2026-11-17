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
