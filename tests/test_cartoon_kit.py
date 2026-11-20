"""cartoon-audio-short skill kit: files present, vendored libs, and the 50 % level lock in mix.py."""
import importlib.util
import os
import shutil
import subprocess
import wave

import numpy as np
import pytest

from pipeline.common import ROOT

SKILL = ROOT / ".claude" / "skills" / "cartoon-audio-short"
KIT = SKILL / "kit"


def test_skill_and_kit_files():
    assert SKILL.joinpath("SKILL.md").read_text(encoding="utf-8").startswith("---\nname: cartoon-audio-short")
    for f in ("engine/main.js", "engine/roman.js", "tools/setup.sh", "tools/render.mjs", "tools/render_all.sh",
              "tools/mix.py", "tools/finish.sh", "tools/timing.py", "example/soldier/story.js",
              "vendor/three.module.js", "vendor/toon.ts", "vendor/LICENSE-three", "vendor/LICENSE-claude-animated-shorts",
              "CREDITS.md"):
        assert (KIT / f).exists(), f
    assert "executablePath: process.env.CHROME" in (KIT / "tools/render.mjs").read_text(encoding="utf-8")
    assert "music * duck" not in (KIT / "example/soldier/audio.py").read_text(encoding="utf-8")


def _wav(path, x, sr=48000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((x * 32767).astype(np.int16).tobytes())


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_mix_locks_music_and_sfx_at_half_the_voice(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location("kitmix", KIT / "tools" / "mix.py")
    mix = importlib.util.module_from_spec(spec); spec.loader.exec_module(mix)
    sr = 48000; t = np.arange(sr * 3) / sr
    voice = 0.3 * np.sin(2 * np.pi * 220 * t) * (t % 1 < .7)       # speech with pauses
    music = 0.9 * np.sin(2 * np.pi * 110 * t)
    sfx = np.zeros_like(t); sfx[sr:sr + 2000] = 0.95                 # one loud hit
    for n, x in (("v.wav", voice), ("m.wav", music), ("s.wav", sfx)):
        _wav(tmp_path / n, x)
    out = tmp_path / "mix_raw.wav"
    mix.main(str(tmp_path / "v.wav"), str(tmp_path / "m.wav"), str(tmp_path / "s.wav"), str(out))
    line = capsys.readouterr().out
    assert "music -6.0 dB vs voice" in line
    peak = float(line.split("peak ")[1].split("x")[0]); assert peak <= 0.7 + 1e-6
    assert out.exists() and wave.open(str(out)).getframerate() == sr


def test_render_all_script_is_valid_bash():
    subprocess.run(["bash", "-n", str(KIT / "tools/render_all.sh")], check=True)
    subprocess.run(["bash", "-n", str(KIT / "tools/finish.sh")], check=True)
    subprocess.run(["bash", "-n", str(KIT / "tools/setup.sh")], check=True)


def test_model_library_is_complete_and_cc0():
    import json
    models = KIT / "models"
    index = json.loads((models / "index.json").read_text(encoding="utf-8"))
    assert len(index) > 300 and all((models / f).exists() for f in index.values())
    assert {"city/building_A", "dungeon/chest_gold", "dungeon/coin_stack_large", "furniture/couch"} <= set(index)
    assert "CC0" in (models / "LICENSE-KayKit-CC0.txt").read_text(encoding="utf-8")
    cat = (models / "CATALOG.md").read_text(encoding="utf-8")
    assert "city 5" in cat and "chest_gold" in cat and len(cat) < 12000   # small enough to read every run


def test_engine_loads_models_and_cheat_sheet_points_at_them():
    main = (KIT / "engine" / "main.js").read_text(encoding="utf-8")
    assert "import { GLTFLoader } from './lib/GLTFLoader.js'" in main and "async function model(" in main
    assert "from './three.module.js'" in (KIT / "vendor" / "GLTFLoader.js").read_text(encoding="utf-8")
    api = (KIT / "API.md").read_text(encoding="utf-8")
    assert "Never open" in api and "await model(" in api
    setup = (KIT / "tools" / "setup.sh").read_text(encoding="utf-8")
    assert 'cp -r "$KIT/models"' in setup and 'cp "$KIT/API.md"' in setup and "GLTFLoader.js" in setup


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_finish_turns_full_range_jpeg_frames_into_tv_range_yuv420p(tmp_path):
    from PIL import Image
    (tmp_path / "frames").mkdir(); (tmp_path / "out").mkdir()
    for i in range(12):   # yuvj420p (full-range) JPEGs, like Chrome's toDataURL frames
        Image.new("RGB", (108, 192), (20 * i, 120, 255 - 20 * i)).save(tmp_path / "frames" / f"f{i:04d}.jpg", quality=90)
    sr = 48000; t = np.arange(int(sr * .4)) / sr
    _wav(tmp_path / "mix_raw.wav", 0.3 * np.sin(2 * np.pi * 220 * t))
    for f in ("finish.sh", "frames_rgb.py"):
        shutil.copy(KIT / "tools" / f, tmp_path / f)
    subprocess.run(["bash", "finish.sh", "final"], cwd=tmp_path, check=True, capture_output=True)
    got = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=pix_fmt",
                          "-of", "csv=p=0", str(tmp_path / "out" / "final.mp4")], capture_output=True, text=True).stdout.strip()
    assert got == "yuv420p"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_finish_survives_a_failing_qa_contact_sheet(tmp_path):
    """The runner's newer ffmpeg refused the contact-sheet JPEG and that killed a good 3D encode: QA must never be fatal."""
    from PIL import Image
    (tmp_path / "frames").mkdir(); (tmp_path / "out").mkdir(); (tmp_path / "bin").mkdir()
    for i in range(2):
        Image.new("RGB", (108, 192), (90, 120, 200)).save(tmp_path / "frames" / f"f{i:04d}.jpg")
    sr = 48000; t = np.arange(int(sr * .4)) / sr
    _wav(tmp_path / "mix_raw.wav", 0.3 * np.sin(2 * np.pi * 220 * t))
    for f in ("finish.sh", "frames_rgb.py"):
        shutil.copy(KIT / "tools" / f, tmp_path / f)
    real = shutil.which("ffmpeg")
    shim = tmp_path / "bin" / "ffmpeg"   # fails exactly the contact-sheet command, like the runner's ffmpeg did
    shim.write_text(f'#!/bin/bash\ncase "$*" in *tile=*) exit 234;; esac\nexec {real} "$@"\n')
    shim.chmod(0o755)
    env = dict(os.environ, PATH=f"{tmp_path / 'bin'}:{os.environ['PATH']}")
    subprocess.run(["bash", "finish.sh", "final"], cwd=tmp_path, check=True, capture_output=True, env=env)
    assert (tmp_path / "out" / "final.mp4").exists()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_mix_levels_can_be_set_below_the_voice(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location("kitmix", KIT / "tools" / "mix.py")
    mix = importlib.util.module_from_spec(spec); spec.loader.exec_module(mix)
    sr = 48000; t = np.arange(sr * 3) / sr
    for n, x in (("v.wav", 0.3 * np.sin(2 * np.pi * 220 * t) * (t % 1 < .7)), ("m.wav", 0.9 * np.sin(2 * np.pi * 110 * t)),
                 ("s.wav", 0.2 * np.sin(2 * np.pi * 880 * t) * (t % 1 < .1))):
        _wav(tmp_path / n, x)
    mix.main(str(tmp_path / "v.wav"), str(tmp_path / "m.wav"), str(tmp_path / "s.wav"), str(tmp_path / "o.wav"), music_db=-20, sfx_db=-13)
    line = capsys.readouterr().out
    assert "music -20.0 dB vs voice" in line and "sfx -13.0 dB vs voice" in line


def _frames_rgb():
    spec = importlib.util.spec_from_file_location("frames_rgb", KIT / "tools" / "frames_rgb.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_caption_chunks_follow_the_spoken_words():
    fr = _frames_rgb()
    words = [{"w": w, "s": s, "e": s + .2} for w, s in (("One", 0), ("man", .3), ("sold", .6), ("the", 1.0), ("tower", 1.3))]
    chunks = fr.caption_chunks(words)
    assert [c[2] for c in chunks] == [["One", "man", "sold"], ["the", "tower"]]
    assert fr.caption_at(chunks, .1) == (["One", "man", "sold"], 0)
    assert fr.caption_at(chunks, .7) == (["One", "man", "sold"], 2)
    assert fr.caption_at(chunks, 1.35) == (["the", "tower"], 1)
    assert fr.caption_at(chunks, 5.0) is None


def test_caption_is_drawn_at_the_lower_third_and_fails_fast_without_inputs(tmp_path):
    from PIL import Image
    fr = _frames_rgb()
    font = ROOT / "toon2d" / "fonts" / "Kalam-Bold.ttf"
    im = Image.new("RGB", (1080, 1920), (40, 60, 120))
    fr.draw_caption(im, ["Hello", "rich", "world"], 1, str(font))
    ys = [y for y in range(1920) for x in range(0, 1080, 6) if im.getpixel((x, y)) != (40, 60, 120)]
    assert ys and 0.6 * 1920 < min(ys) and max(ys) < 0.9 * 1920       # inside the Shorts-safe lower third
    assert any(im.getpixel((x, y)) == fr.LIME for y in range(1400, 1700, 2) for x in range(0, 1080, 2))   # current word is lime
    Image.new("RGB", (64, 64)).save(tmp_path / "f0000.jpg")
    env = dict(__import__("os").environ, CAPTIONS="1")
    r = subprocess.run(["python3", str(KIT / "tools" / "frames_rgb.py"), str(tmp_path), "1"], cwd=tmp_path, env=env, capture_output=True)
    assert r.returncode != 0 and b"missing" in r.stderr


def test_mood_and_music_come_from_the_2d_engine(tmp_path):
    import soundfile as sf
    from pipeline import cartoon3d
    assert cartoon3d.mood_of({"mood": " Tense "}) == "tense" and cartoon3d.mood_of({"mood": "polka"}) == "mystery" and cartoon3d.mood_of({}) == "mystery"
    cartoon3d._music(tmp_path, "upbeat", 2.0)
    x, sr = sf.read(tmp_path / "music.wav")
    assert sr == 48000 and abs(len(x) - 96000) <= 1 and abs(x).max() > 0.01
