import json

import pytest

from pipeline import ideas

DUPES = [
    ("Why does your stomach growl?", "What makes your tummy rumble when hungry"),
    ("Why you get goosebumps", "Why do we get goosebumps when cold"),
    ("Why you get brain freeze", "What causes brain freeze from ice cream"),
    ("Why your fingers wrinkle in water", "Why do fingers get pruney in the bath"),
]
DIFFERENT = [
    ("Why your fingers wrinkle in water", "Why your stomach doesn't digest itself"),
    ("Why you get hiccups", "Why do onions make you cry"),
    ("How hot is the core of the Earth", "Why is the sky blue"),
    ("Why do cats purr", "Why do dogs wag their tails"),
    ("What happens if you swallow chewing gum", "What happens if you swallow a whole bee"),
]


@pytest.mark.parametrize("a,b", DUPES)
def test_near_duplicates_detected(a, b):
    assert ideas.similarity(a, b) >= 0.5


@pytest.mark.parametrize("a,b", DIFFERENT)
def test_different_ideas_pass(a, b):
    assert ideas.similarity(a, b) < 0.5


def cand(text, **scores):
    return {"canonical_en": text, "hook": "h", "payoff": "p", "fact_status": "documented", "scores": {"curiosity": 5, "originality": 5, "visual": 5,
                                                          "clarity": 5, **scores}}


def test_choose_skips_history_and_internal_duplicates_and_ranks():
    past = ["Why you get goosebumps"]
    c = [cand("Why do we get goosebumps when scared", curiosity=10),
         cand("Why do octopuses have three hearts", originality=9),
         cand("Why does an octopus have 3 hearts", originality=10),
         cand("How do noise cancelling headphones erase sound", curiosity=6)]
    best, rejected = ideas.choose(c, past, 0.5)
    assert best["canonical_en"] == "Why do octopuses have three hearts"
    assert {r[0]["canonical_en"] for r in rejected} == {"Why do we get goosebumps when scared",
                                                        "Why does an octopus have 3 hearts"}


def test_choose_rejects_incomplete():
    best, rejected = ideas.choose([{"canonical_en": "", "hook": "x"}, {"canonical_en": "x"},
                                   {"canonical_en": "y", "hook": "h", "payoff": "p", "fact_status": "rumour"}], [], 0.5)
    assert best is None and len(rejected) == 3


def test_hindi_video_compared_by_english_core(tmp_state):
    hist = {"videos": [{"status": "published", "language": "en", "topic": "Why your stomach growls",
                        "canonical_en": "Why does your stomach growl?"}]}
    past = ideas.past_ideas(hist, ideas.load(), "hi", across_languages=True)
    best, _ = ideas.choose([cand("What makes your tummy rumble when hungry")], past, 0.5)
    assert best is None
    past_same_lang = ideas.past_ideas(hist, ideas.load(), "hi", across_languages=False)
    assert ideas.choose([cand("What makes your tummy rumble when hungry")], past_same_lang, 0.5)[0]


def test_discarded_videos_do_not_block_ideas(tmp_state):
    hist = {"videos": [{"status": "discarded", "topic": "Why cats purr"}]}
    assert ideas.past_ideas(hist, ideas.load()) == []


def test_ledger_roundtrip(tmp_state):
    led = ideas.load()
    ideas.record(led, cand("Why the moon looks bigger near the horizon"), "hi", "explainer", "vid1")
    ideas.save(led)
    again = ideas.load()
    assert again["version"] == 1 and again["ideas"][0]["language"] == "hi"


def test_generate_retries_after_duplicates(tmp_state, cfg):
    hist = {"videos": [{"status": "published", "topic": "Why you get goosebumps"}]}
    replies = [json.dumps({"ideas": [cand("Why do we get goosebumps")]}),
               json.dumps({"ideas": [cand("Why do flamingos stand on one leg")]})]
    prompts = []

    def fake_claude(p):
        prompts.append(p)
        return replies.pop(0)

    from pipeline import brain
    lp = {"code": "en", "name": "English"}
    best = ideas.generate(cfg, hist, "explainer", lp, "No data yet.", fake_claude, brain.extract_json)
    assert best["canonical_en"] == "Why do flamingos stand on one leg"
    assert "rejected" in prompts[1] and "goosebumps" in prompts[0]


def test_generate_gives_up_cleanly(tmp_state, cfg):
    from pipeline import brain
    with pytest.raises(RuntimeError):
        ideas.generate(cfg, {"videos": []}, "explainer", {"code": "en", "name": "English"}, "",
                       lambda p: "not json", brain.extract_json)


def test_ideas_prompt_mentions_theme_language_and_history(cfg):
    p = ideas.build_prompt(cfg, "roblox_story", {"code": "hi", "name": "Hindi (natural Hinglish)"},
                           ["Why you get hiccups"], "No data yet.")
    assert "roblox_story" in p and "Hinglish" in p and "Why you get hiccups" in p


def test_prompts_carry_the_story_shape(cfg):
    p = ideas.build_prompt(cfg, "explainer", {"code": "en", "name": "English"}, [], "No data yet.")
    assert "paradox stated as fact" in p and '"fact_status"' in p and '"twist": 1-10' in p
    script = (ideas.ROOT / "prompts" / "script.md").read_text(encoding="utf-8")
    for step in ("HOOK", "SETTING", "ESCALATION", "PIVOT", "TWIST / PAYOFF"):
        assert step in script
