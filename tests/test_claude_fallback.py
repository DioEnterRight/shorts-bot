"""When Claude cannot answer, the same prompt goes to the free models (FreeLLMAPI)."""
import pytest

from pipeline import brain


def test_claude_failure_falls_back_to_free_models(monkeypatch):
    def down(*a, **k):
        raise RuntimeError("Claude Code call failed (usage limits)")
    seen = {}
    monkeypatch.setattr(brain, "_call_claude", down)
    monkeypatch.setattr(brain.freellm, "configured", lambda cfg: True)
    monkeypatch.setattr(brain.freellm, "Budget", lambda cfg: object())
    monkeypatch.setattr(brain.freellm, "chat", lambda cfg, msgs, budget: seen.setdefault("msgs", msgs) and '{"ok": true}')
    brain._FREE["budget"] = None
    assert brain.call_claude("write the script", system="be brief") == '{"ok": true}'
    assert seen["msgs"][0] == {"role": "system", "content": "be brief"} and seen["msgs"][1]["content"] == "write the script"


def test_no_fallback_when_switched_off(monkeypatch):
    monkeypatch.setattr(brain, "_call_claude", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("limit")))
    monkeypatch.setattr(brain, "load_config", lambda: {"claude_fallback_to_free": False})
    with pytest.raises(RuntimeError, match="limit"):
        brain.call_claude("x")


def test_missing_token_is_a_normal_failure_not_an_exit(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="not set"):
        brain._call_claude("x", None, 1, None, None, None, None, None)
