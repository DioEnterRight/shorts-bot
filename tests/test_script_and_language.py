import pytest

from pipeline import brain, captions, languages, voice


@pytest.fixture
def lps(cfg):
    return {c: languages.profile(cfg, c) for c in ("en", "hi")}


@pytest.mark.parametrize("code", ["en", "hi"])
def test_samples_validate(cfg, sample, lps, code):
    s = brain.validate(sample(code), cfg, lps[code])
    assert s["language"] == code and 8 <= len(s["scenes"]) <= 13
    assert len({sc["shot"] for sc in s["scenes"]}) >= 3
    assert all(sc["camera"] in brain.CAMERAS and sc["transition"] in brain.TRANSITIONS for sc in s["scenes"])
    assert s["scenes"][0]["transition"] == "cut"


def test_hindi_emphasis_with_matras_kept(cfg, sample, lps):
    s = brain.validate(sample("hi"), cfg, lps["hi"])
    assert s["scenes"][0]["emphasis"] == "गुड़गुड़"
    assert s["scenes"][-1]["emphasis"] == "सफ़ाई"


def test_rejects_same_picture_twice(cfg, sample, lps):
    s = sample("en")
    s["scenes"][2]["visual"] = s["scenes"][1]["visual"]
    with pytest.raises(ValueError, match="same visual"):
        brain.validate(s, cfg, lps["en"])


def test_rejects_single_shot_type(cfg, sample, lps):
    s = sample("en")
    for sc in s["scenes"]:
        sc["shot"] = "character"
    with pytest.raises(ValueError, match="shot types"):
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


# ---------------- captions ----------------
def test_clean_word_keeps_devanagari_marks():
    assert captions.clean_word("दिमाग़,", False) == "दिमाग़"
    assert captions.clean_word("भूख", False) == "भूख"
    assert captions.clean_word("don't!", True) == "DON'T!"


def fake_timeline(script):
    t, out = 0.2, []
    for sc in script["scenes"]:
        words = [{"word": w, "start": t + j * 0.3, "end": t + j * 0.3 + 0.28} for j, w in enumerate(sc["line"].split())]
        out.append({"start": t, "end": words[-1]["end"], "words": words})
        t = words[-1]["end"] + 0.1
    return out


def test_hindi_captions_switch_font_for_english_words(cfg, sample, lps, tmp_path):
    s = brain.validate(sample("hi"), cfg, lps["hi"])
    path, times = captions.build(cfg, s, fake_timeline(s), 40, lps["hi"], tmp_path)
    ass = path.read_text(encoding="utf-8")
    assert "Style: Pop,Noto Sans Devanagari," in ass
    assert r"{\fnNoto Sans}stomach{\fnNoto Sans Devanagari}" in ass
    assert "गुड़गुड़" in ass and "STOMACH" not in ass
    assert times == sorted(times)


def test_english_captions_uppercase(cfg, sample, lps, tmp_path):
    s = brain.validate(sample("en"), cfg, lps["en"])
    ass = captions.build(cfg, s, fake_timeline(s), 40, lps["en"], tmp_path)[0].read_text(encoding="utf-8")
    assert "Style: Pop,Anton," in ass and "SWALLOW" in ass


def test_long_words_shrink_to_fit(cfg, lps, tmp_path):
    s = {"scenes": [{"line": "Supercalifragilisticexpialidocious", "emphasis": ""}]}
    tl = fake_timeline(s)
    ass = captions.build(cfg, s, tl, 5, lps["en"], tmp_path)[0].read_text(encoding="utf-8")
    scale = int(ass.split(r"\t(0,90,\fscx")[1].split("\\")[0])
    width = captions.text_width(["SUPERCALIFRAGILISTICEXPIALIDOCIOUS"], lps["en"], lps["en"]["caption_font_size"])
    assert scale < 100 and width * scale / 100 <= cfg["captions"]["max_width"] + 2


def test_chunks_never_exceed_width(cfg, lps):
    words = [{"word": w} for w in "प्रतिक्रियाओं वैज्ञानिकों अंतर्राष्ट्रीय stomach".split()]
    for grp in captions.chunk_words(words, 3, lps["hi"], lps["hi"]["caption_font_size"], 900):
        if len(grp) > 1:
            assert captions.text_width([g["word"] for g in grp], lps["hi"], lps["hi"]["caption_font_size"]) <= 900


# ---------------- voice ----------------
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
