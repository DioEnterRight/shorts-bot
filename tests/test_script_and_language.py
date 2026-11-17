import pytest

from pipeline import brain, languages, voice


@pytest.fixture
def lps(cfg):
    return {c: languages.profile(cfg, c) for c in ("en", "hi")}


@pytest.mark.parametrize("code", ["en", "hi"])
def test_samples_validate(cfg, sample, lps, code):
    s = brain.validate(sample(code), cfg, lps[code])
    assert s["language"] == code and 8 <= len(s["scenes"]) <= 13
    assert all(set(sc) == {"line", "visual", "overlay", "emphasis"} for sc in s["scenes"])


def test_hindi_emphasis_with_matras_kept(cfg, sample, lps):
    s = brain.validate(sample("hi"), cfg, lps["hi"])
    assert s["scenes"][0]["emphasis"] == "गुड़गुड़"
    assert s["scenes"][-1]["emphasis"] == "सफ़ाई"


def test_rejects_same_picture_twice(cfg, sample, lps):
    s = sample("en")
    s["scenes"][2]["visual"] = s["scenes"][1]["visual"]
    with pytest.raises(ValueError, match="same visual"):
        brain.validate(s, cfg, lps["en"])


def test_rejects_wrong_language(cfg, sample, lps):
    with pytest.raises(ValueError, match="not in Hindi"):
        brain.validate(sample("en"), cfg, lps["hi"])
    with pytest.raises(ValueError, match="not in English"):
        brain.validate(sample("hi"), cfg, lps["en"])


def test_script_ok_accepts_hinglish():
    assert languages.script_ok("जब आपका stomach खाली होता है तो brain को signal जाता है", "hi")
    assert not languages.script_ok("When your stomach is empty", "hi")


def test_overlays_capped_and_trimmed(cfg, sample, lps):
    s = sample("en")
    for sc in s["scenes"]:
        sc["overlay"] = "one two three four five"
    s = brain.validate(s, cfg, lps["en"])
    labels = [sc["overlay"] for sc in s["scenes"] if sc["overlay"]]
    assert len(labels) == 4 and all(lab == "one two three" for lab in labels)


def test_script_prompt_has_language_rules(cfg, lps):
    idea = {"canonical_en": "Why do we yawn?", "hook": "h"}
    p = brain.build_prompt(cfg, idea, lps["hi"], "explainer", "No data yet.")
    assert "Hinglish" in p and "Latin letters" in p and "Why do we yawn?" in p
    p_en = brain.build_prompt(cfg, idea, lps["en"], "explainer", "No data yet.")
    assert "Language: English" in p_en and "Hinglish" not in p_en


class FakeTok:
    def phonemize(self, text, lang):
        return "ˌaːpkˌaː (en)stˈʌmək(hi) ɔːɾ (en-us)bɹˈeɪn(hi)"


class FakeKokoro:
    tokenizer = FakeTok()


def test_language_switch_markers_removed():
    out = voice.phonemes_for(FakeKokoro(), "आपका stomach और brain", "hi")
    assert "(" not in out and "stˈʌmək" in out and "bɹˈeɪn" in out


def test_hindi_routes_through_phonemes(lps):
    calls = {}

    class K(FakeKokoro):
        def create(self, text, **kw):
            calls.update(kw, text=text)
            return [0.0], 24000
    voice.speak(K(), "आपका stomach", lps["hi"])
    assert calls["is_phonemes"] is True and calls["voice"] == lps["hi"]["voice"]
    voice.speak(K(), "Your stomach", lps["en"])
    assert calls.get("lang") == "en-us"
