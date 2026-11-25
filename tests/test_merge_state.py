"""data/*.json merge driver: Make and Post save bot state at the same time."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("merge_state", Path(__file__).parent.parent / "tools/merge_state.py")
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)


def test_post_and_make_both_kept():
    o = {"videos": [{"id": "v1", "status": "queued", "slot": None}], "missed_slots": []}
    post = {"videos": [{"id": "v1", "status": "published", "slot": "2026-11-26 09:30"}], "missed_slots": ["2026-11-26 08:30"]}
    make = {"videos": [{"id": "v1", "status": "queued", "slot": None}, {"id": "v2", "status": "queued", "slot": None}],
            "missed_slots": []}
    out = ms.merge(o, post, make)
    assert out["videos"] == [{"id": "v1", "status": "published", "slot": "2026-11-26 09:30"},
                             {"id": "v2", "status": "queued", "slot": None}]
    assert out["missed_slots"] == ["2026-11-26 08:30"]


def test_counters_add_and_removals_stay_removed():
    assert ms.merge({"calls": 5}, {"calls": 7}, {"calls": 6}) == {"calls": 8}
    o = {"videos": [{"id": "a"}, {"id": "b"}]}
    cleared = {"videos": [{"id": "a"}]}                       # Clear queue removed b
    posted = {"videos": [{"id": "a", "status": "published"}, {"id": "b"}]}
    assert ms.merge(o, cleared, posted) == {"videos": [{"id": "a", "status": "published"}]}
    assert ms.merge(["x"], ["x", "y"], ["z"]) == ["y", "z"]
