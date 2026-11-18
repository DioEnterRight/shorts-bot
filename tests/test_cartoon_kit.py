"""cartoon-audio-short skill kit: files present, vendored libs, and the 50 % level lock in mix.py."""
import importlib.util
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
