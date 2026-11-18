"""cartoon3d wiring: timing files for the kit, prompt, story checks and the 2D fallback. Offline, no Chrome."""
import json

import pytest

from pipeline import cartoon3d, produce
from pipeline.common import load_config

TL = [{"words": [{"word": "A", "start": .15, "end": .3}, {"word": "man", "start": .3, "end": .6},
                 {"word": "sold,", "start": .6, "end": .9}, {"word": "twice.", "start": 1.0, "end": 1.5}]},
      {"words": [{"word": "Wow!", "start": 1.8, "end": 2.2}]}]
SCRIPT = {"title": "T", "scenes": [{"line": "A man sold, twice.", "visual": "a man selling a tower"},
                                   {"line": "Wow!", "visual": "crowd gasps"}]}


def test_timing_files_match_the_kit_format(tmp_path):
    frames = cartoon3d.timing_files(TL, 2.6, tmp_path)
    words = json.loads((tmp_path / "words.json").read_text())
    ph = json.loads((tmp_path / "phrases.json").read_text())
    assert frames == 78 and ph["frames30"] == 78 and words[0] == {"w": "A", "s": .15, "e": .3}
    assert [p["text"] for p in ph["phrases"]] == ["A man sold,", "twice.", "Wow!"]


def test_prompt_points_at_the_skill_and_the_rules():
    p = cartoon3d.build_prompt(SCRIPT, 78, "en")
    assert str(cartoon3d.SKILL) in p and "TOTAL = 78" in p and "a man selling a tower" in p
    assert "no whip pans" in p and "every 3-4 seconds" in p and "Do NOT render all frames" in p


def test_story_check_rejects_untouched_or_wrong_length(tmp_path):
    (tmp_path / "web").mkdir()
    story = tmp_path / "web" / "story.js"
    story.write_text(cartoon3d.EXAMPLE_STORY.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(RuntimeError, match="not rewritten"):
        cartoon3d._check_story(tmp_path, 592)
    story.write_text("export const FPS = 30, TOTAL = 500, DECK = 6;", encoding="utf-8")
    with pytest.raises(RuntimeError, match="expected 78"):
        cartoon3d._check_story(tmp_path, 78)
    story.write_text("export const FPS = 30, TOTAL = 79, DECK = 6;", encoding="utf-8")
    cartoon3d._check_story(tmp_path, 78)


def test_failed_3d_falls_back_to_2d(tmp_state, monkeypatch, tmp_path):
    cfg = load_config()
    assert cfg["video"]["style"] == "cartoon3d"
    monkeypatch.setattr(produce, "OUT", tmp_path / "out")
    monkeypatch.setattr(produce.voice, "synthesize", lambda *a, **k: (tmp_path / "v.wav", [{"start": 0, "end": 1, "words": []}], 30.0, "kokoro"))
    monkeypatch.setattr(produce.cartoon3d, "render", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("chrome died")))
    fake = tmp_path / "f.mp4"; fake.write_bytes(b"x")
    calls = {}
    monkeypatch.setattr(produce.toon2d, "render", lambda *a, **k: calls.setdefault("2d", (fake, "claude")))
    monkeypatch.setattr(produce.qc, "check", lambda *a, **k: 30.0)
    monkeypatch.setattr(produce, "make_script", lambda *a, **k: (dict(SCRIPT, topic="t", description="d", hashtags=[],
                                                                       language="en", theme="explainer"), None))
    work, meta, *_ = produce.produce_one(cfg, {"videos": []}, {"allocation": {}}, test=False, language="en", theme="explainer")
    assert "2d" in calls and meta["storyboard"] == "claude"


def test_3d_file_failing_qc_falls_back_to_2d(tmp_state, monkeypatch, tmp_path):
    cfg = load_config()
    monkeypatch.setattr(produce, "OUT", tmp_path / "out")
    monkeypatch.setattr(produce.voice, "synthesize", lambda *a, **k: (tmp_path / "v.wav", [{"start": 0, "end": 1, "words": []}], 30.0, "edge"))
    bad3d = tmp_path / "3d.mp4"; bad3d.write_bytes(b"3d")
    good2d = tmp_path / "2d.mp4"; good2d.write_bytes(b"2d")
    monkeypatch.setattr(produce.cartoon3d, "render", lambda *a, **k: bad3d)
    monkeypatch.setattr(produce.toon2d, "render", lambda *a, **k: (good2d, "claude"))

    def qc(path, **k):
        if path == bad3d:
            raise RuntimeError("Quality check failed: video codec h264/yuvj420p")
        return 30.0
    monkeypatch.setattr(produce.qc, "check", qc)
    monkeypatch.setattr(produce, "make_script", lambda *a, **k: (dict(SCRIPT, topic="t", description="d", hashtags=[],
                                                                       language="en", theme="explainer"), None))
    work, meta, *_ = produce.produce_one(cfg, {"videos": []}, {"allocation": {}}, test=False, language="en", theme="explainer")
    assert meta["storyboard"] == "claude" and (work / "final.mp4").read_bytes() == b"2d"
