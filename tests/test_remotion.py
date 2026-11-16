"""Remotion handoff + voice engine tests. Offline: edge-tts and the render are mocked;
the optional slow test asks the real Remotion project to accept the props (zod schema)."""
import json
import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

from pipeline import brain, languages, remotion_render, voice
from pipeline.common import ROOT


def fake_timeline(script, wps=2.6):
    """Word times like the voice step makes, without any audio."""
    t, out = 0.15, []
    for sc in script["scenes"]:
        words = sc["line"].split()
        dur = len(words) / wps
        step = dur / len(words)
        out.append({"start": t, "end": t + dur,
                    "words": [{"word": w, "start": t + i * step, "end": t + (i + 1) * step} for i, w in enumerate(words)]})
        t += dur + 0.08
    return out, t


def props_for(cfg, sample, code, style, tmp_path):
    lp = languages.profile(cfg, code)
    script = brain.validate(sample(code), cfg, lp, "explainer")
    timeline, vlen = fake_timeline(script)
    assets = []
    for i in range(len(script["scenes"])):
        p = tmp_path / f"a{i}.png"
        p.write_bytes(b"png")
        assets.append(p)
    props = remotion_render.build_props(cfg, script, assets if style == "explainer" else [None] * len(assets),
                                        timeline, vlen + 0.7, lp, style)
    return props, assets, script


@pytest.mark.parametrize("code", ["en", "hi"])
@pytest.mark.parametrize("style", ["explainer", "blocky"])
def test_props_valid_and_in_sync(cfg, sample, tmp_path, code, style):
    props, _, script = props_for(cfg, sample, code, style, tmp_path)
    remotion_render.validate_props(props)
    assert len(props["scenes"]) == len(script["scenes"])
    words = sum(len(sc["line"].split()) for sc in script["scenes"])
    assert len(props["captions"]) == words
    assert props["captions"][1]["text"].startswith(" ")      # @remotion/captions word separator
    if code == "hi":
        assert any(any("ऀ" <= ch <= "ॿ" for ch in c["text"]) for c in props["captions"])
    json.dumps(props, ensure_ascii=False)                     # serialisable as-is


def test_validate_catches_drift(cfg, sample, tmp_path):
    props, _, _ = props_for(cfg, sample, "en", "explainer", tmp_path)
    props["scenes"][2]["durationInFrames"] += 3
    with pytest.raises(ValueError, match="audio would drift"):
        remotion_render.validate_props(props)


def test_validate_catches_missing_picture(cfg, sample, tmp_path):
    props, assets, _ = props_for(cfg, sample, "en", "explainer", tmp_path)
    pub = remotion_render.stage_public(props, assets, _wav(tmp_path), tmp_path)
    (pub / props["scenes"][0]["media"]).unlink()
    with pytest.raises(ValueError, match="missing scene_00"):
        remotion_render.validate_props(props, pub)


def _wav(tmp_path):
    p = tmp_path / "mix.wav"
    sf.write(p, np.zeros(4800, dtype=np.float32), 48000)
    return p


# ---------------- word alignment (clean-room) ----------------

def test_align_exact_match():
    marks = [(0.0, 0.2, "Your"), (0.2, 0.5, "brain"), (0.5, 0.9, "overheats")]
    assert voice.align_words("Your brain overheats!".split(), marks, 1.0) == [(0.0, 0.2), (0.2, 0.5), (0.5, 0.9)]


def test_align_number_spoken_as_words():
    words = "It hits 37°C fast".split()
    marks = [(0, .2, "It"), (.2, .4, "hits"), (.4, .7, "thirty"), (.7, .9, "seven"), (.9, 1.2, "degrees"),
             (1.2, 1.5, "Celsius"), (1.5, 1.8, "fast")]
    spans = voice.align_words(words, marks, 2.0)
    assert spans[2] == (0.4, 1.5) and spans[3] == (1.5, 1.8)


def test_align_hindi_and_missing_marks_stay_monotonic():
    words = "दिमाग़ बहुत hot हो जाता है".split()
    marks = [(0.0, 0.4, "दिमाग़"), (0.9, 1.1, "हो"), (1.4, 1.6, "है")]
    spans = voice.align_words(words, marks, 1.8)
    starts = [s for s, _ in spans]
    assert starts == sorted(starts) and spans[-1][1] <= 1.8
    assert spans[0] == (0.0, 0.4) and spans[3][0] == 0.9


# ---------------- voice engine choice ----------------

def test_edge_failure_falls_back_to_kokoro(cfg, monkeypatch, tmp_path):
    cfg["voice"]["engine"] = "edge"
    lp = languages.profile(cfg, "hi")
    monkeypatch.setattr(voice, "_synthesize_edge", lambda *a: (_ for _ in ()).throw(RuntimeError("429 rate limited")))
    monkeypatch.setattr(voice, "_synthesize_kokoro", lambda *a: ("k.wav", [], 1.0))
    assert voice.synthesize(cfg, {"scenes": []}, lp, tmp_path)[-1] == "kokoro"


def test_test_mode_never_calls_edge(cfg, monkeypatch, tmp_path):
    cfg["voice"]["engine"] = "edge"
    lp = languages.profile(cfg, "en")
    monkeypatch.setattr(voice, "_synthesize_edge", lambda *a: pytest.fail("edge called in test mode"))
    monkeypatch.setattr(voice, "_synthesize_kokoro", lambda *a: ("k.wav", [], 1.0))
    assert voice.synthesize(cfg, {"scenes": []}, lp, tmp_path, allow_edge=False)[-1] == "kokoro"


def test_edge_path_builds_timeline(cfg, monkeypatch, tmp_path):
    """Mocked edge stream: audio with leading silence; marks get shifted to the trimmed audio."""
    cfg["voice"]["engine"] = "edge"
    lp = languages.profile(cfg, "en")
    sr = voice.SR
    tone = np.concatenate([np.zeros(int(0.5 * sr)), 0.3 * np.ones(int(1.0 * sr))]).astype(np.float32)
    marks = [(0.5, 0.9, "Hello"), (0.9, 1.5, "there")]
    monkeypatch.setattr(voice, "edge_line", lambda *a: (tone, marks))
    path, tl, secs, engine = voice.synthesize(cfg, {"scenes": [{"line": "Hello there"}]}, lp, tmp_path)
    assert engine == "edge" and path.exists()
    w = tl[0]["words"]
    assert abs(w[0]["start"] - (0.15 + 0.03)) < 0.01       # 0.15s breath + 30ms pad kept before the voice
    assert w[1]["end"] <= tl[0]["end"] + 1e-6


def test_edge_retries_then_raises(monkeypatch):
    calls = []

    def boom(*a):
        calls.append(1)
        raise ConnectionError("no route")
    monkeypatch.setattr(voice.asyncio, "run", lambda coro: (coro.close(), boom())[1])
    monkeypatch.setattr(voice.time, "sleep", lambda s: None)
    with pytest.raises(ConnectionError):
        voice.edge_line("hi", "en-US-AndrewNeural", "+0%", 3)
    assert len(calls) == 3


# ---------------- the real Remotion project accepts the props ----------------

@pytest.mark.slow
@pytest.mark.skipif(not (ROOT / "remotion" / "node_modules").exists() or not shutil.which("npx"),
                    reason="remotion/node_modules not installed")
@pytest.mark.parametrize("code,style", [("hi", "explainer"), ("en", "blocky"), ("hi", "cartoon"), ("en", "bespoke")])
def test_remotion_schema_accepts_props(cfg, sample, tmp_path, code, style):
    props, assets, _ = props_for(cfg, sample, code, style, tmp_path)
    pub = remotion_render.stage_public(props, assets, _wav(tmp_path), tmp_path)
    path = tmp_path / "props.json"
    path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    cmd = ["npx", "--no-install", "remotion", "compositions", "src/index.ts", f"--props={path}",
           f"--public-dir={pub}"]
    if b := remotion_render._browser():
        cmd.append(f"--browser-executable={b}")
    ok = subprocess.run(cmd, cwd=ROOT / "remotion", capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr[-2000:]
    assert "ShortsBot" in ok.stdout and f"{props['durationInFrames']}" in ok.stdout
    props["scenes"][0]["camera"] = "spin"                      # schema must reject a bad handoff
    path.write_text(json.dumps(props), encoding="utf-8")
    bad = subprocess.run(cmd, cwd=ROOT / "remotion", capture_output=True, text=True)
    assert bad.returncode != 0


# ---------------- cartoon storyboard ----------------

def test_cartoon_normalize_cleans_and_derives():
    from pipeline import cartoon
    sc = {"shot": "diagram", "cartoon": {"layout": "versus", "expression": "angry", "mood": "pink",
                                          "props": [{"name": "Virus", "motion": "wiggle"}, "dragon", {"name": "pee"}]}}
    c = cartoon.normalize(sc)
    assert c["props"] == [{"name": "germ", "motion": "pop"}, {"name": "bladder", "motion": "pop"}]
    assert c["layout"] == "versus" and c["expression"] == "neutral" and c["mood"] == "body"
    assert cartoon.normalize({"shot": "cutaway"})["layout"] == "inside"
    assert cartoon.normalize({"shot": "metaphor"})["props"][0]["name"] == "question"


def test_cartoon_catalog_matches_remotion():
    import re
    from pipeline import cartoon
    tsx = (ROOT / "remotion/src/bot/cartoon/Props.tsx").read_text()
    drawn = re.findall(r"^  ([a-z_]+): \(\) =>", tsx, re.M)
    assert drawn == cartoon.PROPS
    schema = (ROOT / "remotion/src/bot/schema.ts").read_text()
    for name, values in (("LAYOUTS", cartoon.LAYOUTS), ("MOTIONS", cartoon.MOTIONS), ("MOODS", cartoon.MOODS),
                         ("EXPRESSIONS", cartoon.EXPRESSIONS)):
        line = re.search(rf"export const {name} = \[([^\]]+)\]", schema).group(1)
        assert re.findall(r'"([a-z_]+)"', line) == values, name


def test_cartoon_props_valid(cfg, sample, tmp_path):
    props, _, _ = props_for(cfg, sample, "hi", "cartoon", tmp_path)
    remotion_render.validate_props(props)
    assert {s["cartoon"]["layout"] for s in props["scenes"]} >= {"actor", "inside", "versus"}
