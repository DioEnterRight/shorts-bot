import math

from pipeline import allocation as al

S = dict(al.DEFAULTS)


def recs(lang, views, age=5):
    return [{"language": lang, "age_days": age, "views": {"yt": v}} for v in views]


def test_balanced_without_data():
    shares, diag = al.language_shares([], ["en", "hi"], S)
    assert shares == {"en": 0.5, "hi": 0.5}
    assert "not enough" in diag["reason"]


def test_balanced_when_one_language_lacks_data():
    shares, _ = al.language_shares(recs("en", [100] * 10) + recs("hi", [5000] * 2), ["en", "hi"], S)
    assert shares == {"en": 0.5, "hi": 0.5}


def test_better_language_gains_share_but_respects_cap():
    shares, _ = al.language_shares(recs("en", [100] * 12) + recs("hi", [3000] * 12), ["en", "hi"], S)
    assert shares["hi"] > 0.5
    assert shares["hi"] <= 0.8 + 1e-9 and shares["en"] >= 0.2 - 1e-9
    assert math.isclose(sum(shares.values()), 1.0)


def test_floor_holds_for_huge_gap():
    shares, _ = al.language_shares(recs("en", [1] * 40) + recs("hi", [10**7] * 40), ["en", "hi"],
                                   {**S, "confidence_k": 0})
    assert math.isclose(shares["en"], 0.2) and math.isclose(shares["hi"], 0.8)


def test_one_viral_video_does_not_flip_the_split():
    en = recs("en", [500] * 8)
    hi = recs("hi", [300] * 7 + [5_000_000])
    shares, _ = al.language_shares(en + hi, ["en", "hi"], S)
    assert shares["en"] >= shares["hi"]


def test_young_videos_ignored_and_age_adjusted():
    s = {**S, "min_age_days": 2}
    assert al.video_value({"views": {"yt": 100}}, 1.0, s) is None
    young, old = al.video_value({"views": {"yt": 100}}, 2.0, s), al.video_value({"views": {"yt": 100}}, 20.0, s)
    assert young > old  # same views reached faster = better


def test_day7_snapshot_preferred():
    r = {"views": {"yt": 9999}, "views_day7": {"yt": 100}}
    assert al.video_value(r, 25, S) == al.video_value({"views": {"yt": 100}}, 7, S)


def test_missing_metrics_do_not_crash():
    rows = [{"language": "en", "age_days": 5, "views": {}}, {"language": "hi", "age_days": 5, "views": None}]
    shares, _ = al.language_shares(rows, ["en", "hi"], S)
    assert shares == {"en": 0.5, "hi": 0.5}


def test_smoothing_moves_gradually():
    data = recs("en", [100] * 12) + recs("hi", [3000] * 12)
    target, _ = al.language_shares(data, ["en", "hi"], {**S, "smoothing": 1.0})
    step, _ = al.language_shares(data, ["en", "hi"], S, previous={"en": 0.5, "hi": 0.5})
    assert 0.5 < step["hi"] < target["hi"]


def test_clamp_shares_three_options():
    out = al.clamp_shares({"a": 0.98, "b": 0.01, "c": 0.01}, 0.2)
    assert math.isclose(sum(out.values()), 1) and out["b"] == 0.2 and out["c"] == 0.2


def simulate(shares, n, floor=0.2):
    seq = []
    for _ in range(n):
        seq.append(al.pick(shares, seq, floor=floor))
    return seq


def test_pick_is_deterministic_and_matches_shares():
    a, b = simulate({"en": 0.8, "hi": 0.2}, 100), simulate({"en": 0.8, "hi": 0.2}, 100)
    assert a == b
    assert 18 <= a.count("hi") <= 22


def test_floor_guarantees_regular_slots_for_weaker_language():
    seq = simulate({"en": 0.8, "hi": 0.2}, 60)
    gaps, last = [], -1
    for i, x in enumerate(seq):
        if x == "hi":
            gaps.append(i - last)
            last = i
    assert max(gaps) <= 5


def test_balanced_alternates():
    assert simulate({"en": 0.5, "hi": 0.5}, 6) == ["en", "hi", "en", "hi", "en", "hi"]


def test_pick_forces_language_missing_from_history():
    # 4 English videos in a row (e.g. before Hindi existed): Hindi must come next
    assert al.pick({"en": 0.8, "hi": 0.2}, ["en"] * 4, floor=0.2) == "hi"


def test_theme_mix_keeps_explainers_majority():
    shares = {"explainer": 0.8, "story": 0.13, "roblox_story": 0.07}
    seq = []
    for _ in range(200):
        seq.append(al.pick(shares, seq, window=20))
    assert 0.75 <= seq.count("explainer") / 200 <= 0.85
    assert seq.count("roblox_story") >= 8 and seq.count("story") >= 20


# ---------------- weekly quota ----------------
import datetime as _dt

from pipeline.common import IST


def _t(y, m, d, h=10):
    return _dt.datetime(y, m, d, h, tzinfo=IST)


def test_weekly_one_hindi_from_wednesday():
    from pipeline.allocation import weekly_pick
    q = {"hi": 1}
    mon, wed, thu, sun = _t(2026, 11, 16), _t(2026, 11, 18), _t(2026, 11, 19), _t(2026, 11, 22)
    assert weekly_pick([], mon, "en", q, "wed") == "en"                    # before quota day
    assert weekly_pick([(mon, "en"), (mon, "en")], wed, "en", q, "wed") == "hi"
    made = [(mon, "en"), (wed, "hi")]
    assert weekly_pick(made, thu, "en", q, "wed") == "en"                  # quota met
    assert weekly_pick(made, sun, "en", q, "wed") == "en"
    last_week = [(_t(2026, 11, 11), "hi")]
    assert weekly_pick(last_week, thu, "en", q, "wed") == "hi"             # last week's doesn't count
    # simulate a whole week, 1 video/day: exactly one Hindi
    made = []
    for d in range(16, 23):
        lang = weekly_pick(made, _t(2026, 11, d), "en", q, "wed")
        made.append((_t(2026, 11, d), lang))
    assert [l for _, l in made].count("hi") == 1


def test_choose_slot_weekly(cfg):
    from pipeline import produce
    cfg["allocation"].update(mode="weekly", main="en", weekly_quota={"hi": 1}, quota_day="mon")
    lang, _ = produce.choose_slot(cfg, {"videos": []}, {})
    assert lang == "hi"
    hist = {"videos": [{"created": produce.now_ist().isoformat(), "language": "hi", "status": "queued"}]}
    assert produce.choose_slot(cfg, hist, {})[0] == "en"
