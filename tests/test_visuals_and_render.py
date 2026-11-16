import json
import subprocess

import numpy as np
import pytest
from PIL import Image

from pipeline import brain, edit, languages, qc
from pipeline.visuals import build_prompt, cloudflare_klein, mascot_path

from .conftest import models_present


@pytest.fixture
def en_script(cfg, sample):
    return brain.validate(sample("en"), cfg, languages.profile(cfg, "en"))


# ---------------- prompts / art direction ----------------
def test_prompts_are_stylised_and_scene_specific(cfg, en_script):
    prompts = [build_prompt(cfg, en_script, sc) for sc in en_script["scenes"]]
    assert len(set(prompts)) == len(prompts)
    for p, sc in zip(prompts, en_script["scenes"]):
        assert "Stylized 3D animated" in p and "not photorealistic" in p
        assert "[GUY]" not in p
        assert cfg["visuals"]["shots"][sc["shot"]] in p
    assert "realistic smooth CGI" not in " ".join(prompts)


def test_theme_overrides_look(cfg, en_script):
    story = dict(en_script, theme="roblox_story")
    p = build_prompt(cfg, story, en_script["scenes"][0])
    assert "blocky" in p and "cube-shaped head" in p
    assert mascot_path(cfg, story) != mascot_path(cfg, en_script)


# ---------------- provider fallback ----------------
def test_klein_falls_back_then_fills_gaps(cfg, en_script, tmp_path, monkeypatch):
    from pipeline.visuals import cloudflare_flux
    monkeypatch.setenv("CF_ACCOUNT_ID", "acc")
    monkeypatch.setenv("CF_API_TOKEN", "tok-for-test")
    monkeypatch.setattr(cloudflare_klein, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(cloudflare_klein, "ensure_mascot", lambda *a: Image.new("RGB", (64, 64)))
    refs_seen = []

    def klein(prompt, account, token, w, h, seed, refs=()):
        refs_seen.append(len(refs))
        if "bubbling" in prompt or "sugar" in prompt:
            raise RuntimeError("refused")
        return Image.new("RGB", (w, h), (len(refs_seen) * 20 % 255, 0, 0))

    def flux(prompt, account, token, seed, steps=8):
        if "bubbling" in prompt:
            raise RuntimeError("down")
        return Image.new("RGB", (100, 100), (0, 255, 0))
    monkeypatch.setattr(cloudflare_klein, "_call", klein)
    monkeypatch.setattr(cloudflare_flux, "image", flux)
    paths = cloudflare_klein.generate(cfg, en_script, tmp_path)
    assert len(paths) == len(en_script["scenes"]) and all(p is not None for p in paths)
    assert paths[3] in (paths[2], paths[4])  # scene 4 failed on both models -> re-uses a neighbour
    # character scenes got the character sheet as a reference; cutaways/diagrams got none
    for sc, n_refs in zip(en_script["scenes"], refs_seen):
        assert (n_refs > 0) == bool(sc["character"])


def test_klein_stops_on_quota(cfg, en_script, tmp_path, monkeypatch):
    from pipeline.visuals import FatalProviderError
    monkeypatch.setenv("CF_ACCOUNT_ID", "acc")
    monkeypatch.setenv("CF_API_TOKEN", "tok-for-test")
    monkeypatch.setattr(cloudflare_klein, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(cloudflare_klein, "ensure_mascot", lambda *a: Image.new("RGB", (64, 64)))

    def quota(*a, **k):
        raise FatalProviderError("limit")
    monkeypatch.setattr(cloudflare_klein, "_call", quota)
    with pytest.raises(FatalProviderError):
        cloudflare_klein.generate(cfg, en_script, tmp_path)


def test_too_many_failures_abort():
    with pytest.raises(RuntimeError, match="half-empty"):
        cloudflare_klein.fill_gaps(["a", None, None, None], 0.75)


def test_cache_avoids_second_call(tmp_path, monkeypatch):
    monkeypatch.setattr(cloudflare_klein, "CACHE", tmp_path)
    n = {"calls": 0}

    def call(*a, **k):
        n["calls"] += 1
        return Image.new("RGB", (8, 8))
    monkeypatch.setattr(cloudflare_klein, "_call", call)
    for _ in range(2):
        cloudflare_klein.cached_call("p", "a", "t", 8, 8, 1, (b"ref",))
    assert n["calls"] == 1


# ---------------- render plan ----------------
def test_plan_keeps_total_frames_and_bounds_transitions(en_script):
    tl, t = [], 0.15
    for sc in en_script["scenes"]:
        tl.append({"start": t, "end": t + 2.5, "words": []})
        t += 2.6
    n, h = edit.plan(en_script, tl, t + 0.7, 30)
    assert sum(n) == round((t + 0.7) * 30)
    assert h[0] == 0 and h[-1] == 0
    for i in range(1, len(n)):
        assert h[i] <= n[i - 1] // 3 and h[i] <= n[i] // 3
        if en_script["scenes"][i]["transition"] == "cut":
            assert h[i] == 0


@pytest.mark.parametrize("kind", ["fade", "whip", "zoom", "cut"])
def test_blend_shapes(kind):
    a = np.zeros((edit.H, edit.W, 3), np.uint8)
    b = np.full((edit.H, edit.W, 3), 255, np.uint8)
    mid = edit.blend(kind, a, b, 0.5)
    assert mid.shape == a.shape and mid.dtype == np.uint8
    assert edit.blend(kind, a, b, 0.999).mean() > 200


def test_overlay_label_renders_devanagari():
    lab = edit.overlay_label("ग्रेलिन", "hi")
    assert lab.mode == "RGBA" and lab.width > 100


# ---------------- QC ----------------
def test_qc_rejects_wrong_format(tmp_path):
    bad = tmp_path / "bad.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=720x1280:r=25:d=12",
                    "-f", "lavfi", "-i", "sine=f=440:d=12", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(bad)], check=True)
    with pytest.raises(RuntimeError) as e:
        qc.check(bad)
    assert "1080x1920" in str(e.value) and "frame rate" in str(e.value)


# ---------------- end-to-end offline render ----------------
@pytest.mark.slow
@pytest.mark.skipif(not models_present(), reason="Kokoro model not downloaded (python -m pipeline.fetch_models)")
@pytest.mark.parametrize("lang", ["hi", "en"])
def test_offline_end_to_end(lang, tmp_state, monkeypatch, tmp_path):
    from pipeline import produce
    monkeypatch.setattr(produce, "OUT", tmp_path / "out")
    cfg = produce.load_config()
    stats = {"allocation": {}}
    work, meta, script, _ = produce.produce_one(cfg, {"videos": []}, stats, test=True, language=lang)
    final = work / "final.mp4"
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                                      "-show_format", str(final)], capture_output=True, text=True).stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert (v["width"], v["height"], v["avg_frame_rate"]) == (1080, 1920, "30/1")
    assert abs(float(v["duration"]) - float(a["duration"])) < 0.15
    assert meta["language"] == lang and meta["scenes"] == len(script["scenes"])
    # each scene starts right before its narration line (audio/picture sync)
    tl = json.loads((work / "timeline.json").read_text())
    assert len(tl) == len(script["scenes"]) and all(x["end"] > x["start"] for x in tl)
    ass = (work / "captions.ass").read_text(encoding="utf-8")
    if lang == "hi":
        assert "Noto Sans Devanagari" in ass
    # scene pictures really differ from each other
    frames = []
    for line in tl[:4]:
        out = tmp_path / f"f{len(frames)}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{line['start'] + 0.4:.2f}", "-i", str(final),
                        "-frames:v", "1", str(out)], check=True)
        frames.append(np.asarray(Image.open(out).convert("L").resize((54, 96)), np.float32))
    diffs = [np.abs(frames[i] - frames[i + 1]).mean() for i in range(3)]
    assert min(diffs) > 5
