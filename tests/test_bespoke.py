"""Bespoke scene generation: visemes, scene gates, brief, model pinning. Offline (no Claude call)."""
import json

import pytest

from pipeline import brain, remotion_render, scenegen, visemes
from tests.test_remotion import props_for


def test_visemes_close_on_pauses_and_hold():
    tl = [{"words": [{"word": "Your", "start": 0.2, "end": 0.45}, {"word": "brain", "start": 0.45, "end": 0.8},
                     {"word": "overheats.", "start": 1.3, "end": 1.9}]}]
    t = visemes.track(tl, 30)
    frames = [f for f, _ in t]
    assert frames == sorted(set(frames))
    assert all(b - a >= visemes.MIN_HOLD for a, b in zip(frames, frames[1:]))
    gap = [s for f, s in t if 24 <= f <= 38]          # 0.8s..1.3s pause -> mouth closed
    assert gap == ["X"] and t[-1][1] == "X"
    assert {s for _, s in t} <= set("XABCDEFGH")


def test_visemes_hindi():
    assert visemes.word_units("मम्मी")[0] == "A"
    assert "C" in visemes.word_units("दिमाग़") and "D" in visemes.word_units("दिमाग़")


GOOD = '''import React from "react";
import { useCurrentFrame } from "remotion";
import { Stage, Bean } from "../kit";
export default function Scene2() { const f = useCurrentFrame(); return <Stage><Bean size={300 + f} /></Stage>; }
'''


@pytest.mark.parametrize("bad,why", [
    (GOOD.replace('"../kit"', '"lodash"'), "imports not allowed"),
    (GOOD.replace("300 + f", "300 + Math.random()"), "banned"),
    (GOOD.replace("<Stage>", "<Stage><div style={{transition: 'all 1s'}} />"), "banned"),
    (GOOD.replace("function Scene2", "function Other"), "export default"),
])
def test_gate_file(tmp_path, bad, why):
    p = tmp_path / "Scene2.tsx"
    p.write_text(GOOD)
    assert scenegen._gate_file(p) is None
    p.write_text(bad)
    assert why in scenegen._gate_file(p)


def test_brief_words_are_local_and_inside(cfg, sample, tmp_path):
    props, _, script = props_for(cfg, sample, "hi", "bespoke", tmp_path)
    remotion_render.validate_props(props)
    assert len(props["visemes"]) > 20 and props["scenes"][0]["component"] == "Scene1"
    b = scenegen.brief(script, props)
    assert [s["component"] for s in b["scenes"]] == [f"Scene{i + 1}" for i in range(len(script["scenes"]))]
    for s in b["scenes"]:
        assert s["words"] and all(0 <= w["from"] < s["durationInFrames"] for w in s["words"])
    assert b["scenes"][0]["words"][0]["text"] == script["scenes"][0]["line"].split()[0]
    json.dumps(b, ensure_ascii=False)


def test_no_token_means_cartoon_fallback(cfg, sample, tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("SCENEGEN_PREWRITTEN", raising=False)
    props, _, script = props_for(cfg, sample, "en", "bespoke", tmp_path)
    out = scenegen.generate(cfg, script, props, tmp_path / "p.json", tmp_path, None)
    assert all(s["component"] is None for s in out["scenes"])


def test_index_written_matches_names():
    scenegen.write_index(["Scene1", "Scene3"])
    src = (scenegen.GEN / "index.ts").read_text()
    assert 'import Scene3 from "./Scene3";' in src and "{ Scene1, Scene3 }" in src
    scenegen.write_index([])
    assert "{  }" in (scenegen.GEN / "index.ts").read_text()


def test_claude_pinned_to_opus():
    args = brain.claude_model_args()
    assert args[:2] == ["--model", "opus"] and "--fallback-model" in args
