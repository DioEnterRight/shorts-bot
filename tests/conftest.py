import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import common  # noqa: E402


@pytest.fixture
def cfg():
    return common.load_config()


@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    """Point every state file at a temp dir so tests never touch data/."""
    from pipeline import analytics, ideas
    monkeypatch.setattr(common, "DATA", tmp_path)
    monkeypatch.setattr(common, "HISTORY", tmp_path / "history.json")
    monkeypatch.setattr(analytics, "PATH", tmp_path / "analytics.json")
    monkeypatch.setattr(ideas, "PATH", tmp_path / "ideas.json")
    return tmp_path


@pytest.fixture
def sample(cfg):
    def load(code):
        return json.loads((ROOT / "prompts" / f"sample_script_{code}.json").read_text(encoding="utf-8"))
    return load


def models_present():
    return (ROOT / "models" / "kokoro.onnx").exists() and (ROOT / "models" / "voices.bin").exists()
