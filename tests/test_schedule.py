"""Daily slots from config.yaml schedule: what to make, what to post when."""
import datetime as dt

import pytest

from pipeline import schedule
from pipeline.common import IST

CFG = {"languages": {"enabled": ["en", "hi"]},
       "schedule": [{"time": "19:00", "language": "en"}, {"time": "09:00", "language": "hi"}, {"time": "14:00", "language": "en"}]}
at = lambda h, m=0: dt.datetime(2026, 11, 26, h, m, tzinfo=IST)


def test_slots_sorted_and_validated():
    assert schedule.slots(CFG) == [("09:00", "hi"), ("14:00", "en"), ("19:00", "en")]
    for bad in ({"time": "9:00", "language": "hi"}, {"time": "25:00", "language": "en"}, {"time": "09:00", "language": "fr"}):
        with pytest.raises(ValueError):
            schedule.slots({**CFG, "schedule": [bad]})
    with pytest.raises(ValueError):
        schedule.slots({**CFG, "schedule": []})


def test_make_tops_up_one_day_per_language():
    assert schedule.to_make(CFG, []) == ["hi", "en", "en"]
    assert schedule.to_make(CFG, [{"language": "en"}]) == ["hi", "en"]
    assert schedule.to_make(CFG, [{"language": "hi"}, {"language": "en"}, {"language": "en"}, {"language": "en"}]) == []


def test_due_slot_and_catch_up():
    assert schedule.due(CFG, set(), at(8, 59)) is None
    assert schedule.due(CFG, set(), at(9, 7)) == ("2026-11-26 09:00", "hi")
    assert schedule.due(CFG, {"2026-11-26 09:00"}, at(13, 37)) is None
    assert schedule.due(CFG, set(), at(11, 37)) == ("2026-11-26 09:00", "hi")         # late (up to 3 h) is still posted
    assert schedule.due(CFG, set(), at(14, 7)) == ("2026-11-26 14:00", "en")          # older than 3 h: skipped, video waits
    assert schedule.due(CFG, {"2026-11-25 19:00"}, at(0, 7)) is None                   # yesterday never comes back


def test_work_now_sees_half_posted_videos():
    h = {"videos": [{"status": "queued", "slot": "2026-11-26 09:00"}]}
    assert schedule.work_now(CFG, h, at(9, 37)) is True
    h = {"videos": [{"status": "published", "slot": "2026-11-26 09:00"}]}
    assert schedule.work_now(CFG, h, at(9, 37)) is False and schedule.work_now(CFG, h, at(14, 7)) is True
    assert schedule.work_now(CFG, {"videos": [], "missed_slots": ["2026-11-26 09:00"]}, at(9, 37)) is False
