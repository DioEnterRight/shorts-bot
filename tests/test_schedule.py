"""Upload slots from config.yaml schedule: what to make, what to post when."""
import datetime as dt

import pytest

from pipeline import schedule

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
CFG = {"languages": {"enabled": ["en", "hi"]},
       "schedule": {"every_minutes": 60, "first": "00:30", "language": "en", "language_at": {"09:30": "hi"},
                    "make_ahead": 2, "make_per_run": 1}}


def at(h, m, day=26):
    return dt.datetime(2026, 11, day, h, m, tzinfo=IST)


def test_slots():
    s = schedule.slots(CFG)
    assert len(s) == 24 and s[:2] == [("00:30", "en"), ("01:30", "en")] and s[9] == ("09:30", "hi")
    three = {**CFG, "schedule": {"every_minutes": 300, "first": "09:00", "language": "en", "language_at": {"09:00": "hi"}}}
    assert schedule.slots(three) == [("04:00", "en"), ("09:00", "hi"), ("14:00", "en"), ("19:00", "en")]


@pytest.mark.parametrize("bad", [{"every_minutes": 5}, {"first": "9:00"}, {"language": "fr"},
                                 {"language_at": {"09:00": "hi"}}, {"language_at": {"09:30": "fr"}}])
def test_bad_schedule_fails_fast(bad):
    with pytest.raises(ValueError):
        schedule.slots({**CFG, "schedule": {**CFG["schedule"], **bad}})
    with pytest.raises(ValueError):
        schedule.slots({**CFG, "schedule": [{"time": "09:00", "language": "hi"}]})   # the old list format


def test_to_make_keeps_next_uploads_ready():
    assert schedule.to_make(CFG, [], at(7, 50)) == ["en"]                      # next: 08:30 en, 09:30 hi
    assert schedule.to_make(CFG, [{"language": "en"}], at(7, 50)) == ["hi"]
    assert schedule.to_make(CFG, [{"language": "en"}, {"language": "hi"}], at(7, 50)) == []
    big = {**CFG, "schedule": {**CFG["schedule"], "make_per_run": 3}}
    assert schedule.to_make(big, [], at(8, 50)) == ["hi", "en"]
    assert schedule.to_make(big, [], at(23, 50)) == ["en", "en"]                 # wraps past midnight


def test_due():
    assert schedule.due(CFG, set(), at(9, 20)) == ("2026-11-26 08:30", "en")    # still inside its hour
    assert schedule.due(CFG, set(), at(9, 37)) == ("2026-11-26 09:30", "hi")
    assert schedule.due(CFG, {"2026-11-26 09:30"}, at(10, 7)) is None
    assert schedule.due(CFG, set(), at(0, 7)) == ("2026-11-25 23:30", "en")     # yesterday's last slot
    daily = {**CFG, "schedule": {"every_minutes": 1440, "first": "09:00", "language": "hi"}}
    assert schedule.due(daily, set(), at(11, 37)) == ("2026-11-26 09:00", "hi")  # late (up to 3 h) is still posted
    assert schedule.due(daily, set(), at(12, 7)) is None


def test_work_now():
    h = {"videos": [{"status": "queued", "slot": None}]}
    assert schedule.work_now(CFG, h, at(9, 37)) is True
    h = {"videos": [{"status": "published", "slot": "2026-11-26 09:30"}, {"status": "queued", "slot": None}]}
    assert schedule.work_now(CFG, h, at(9, 37)) is False and schedule.work_now(CFG, h, at(10, 37)) is True


def test_make_gate():
    assert schedule.make_now(CFG, {"videos": []}, at(7, 50)) is True
    ready = {"videos": [{"status": "queued", "language": "en"}, {"status": "queued", "language": "hi"}]}
    assert schedule.make_now(CFG, ready, at(7, 50)) is False
