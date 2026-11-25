"""Theme picking (allocation.pick)."""
from pipeline import allocation as al


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
    shares = {"explainer": 0.8, "story": 0.13, "rare": 0.07}
    seq = []
    for _ in range(200):
        seq.append(al.pick(shares, seq, window=20))
    assert 0.75 <= seq.count("explainer") / 200 <= 0.85
    assert seq.count("rare") >= 8 and seq.count("story") >= 20


# ---------------- weekly quota ----------------
import datetime as _dt

from pipeline.common import IST


def _t(y, m, d, h=10):
    return _dt.datetime(y, m, d, h, tzinfo=IST)

