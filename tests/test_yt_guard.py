"""YouTube safety controller: rolling cap, uploadLimitExceeded pause (no retry), quota pause, cross-repo reconciliation."""
import datetime as dt
import json

import pytest

from pipeline import common, publish, yt_guard

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 26, 12, 0, tzinfo=UTC)


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA", tmp_path)
    monkeypatch.setattr(common, "HISTORY", tmp_path / "history.json")
    return tmp_path


class LimitError(Exception):
    def __init__(self, reason="uploadLimitExceeded", status=400):
        self.resp = type("R", (), {"status": status})()
        self.content = json.dumps({"error": {"errors": [{"reason": reason}]}}).encode()


def test_rolling_cap_and_pause(cfg, state):
    cfg["publish"]["youtube_channel_daily_cap"] = 1
    led = yt_guard.empty_ledger()
    led["uploads"].append({"ts": (NOW - dt.timedelta(hours=23)).isoformat(), "video_id": "x", "local_id": "a"})
    assert not yt_guard.Guard(cfg, led, NOW).clearance({"id": "b"})[0]
    assert yt_guard.Guard(cfg, led, NOW + dt.timedelta(hours=2)).clearance({"id": "b"})[0]
    g = yt_guard.Guard(cfg, yt_guard.empty_ledger(), NOW)
    g.begin({"id": "b"})
    pause = g.failure({"id": "b"}, "upload_limit", "uploadLimitExceeded")
    assert yt_guard._utc(pause["until"]) - NOW >= dt.timedelta(hours=24)


def test_quota_pause_until_pacific_midnight(cfg, state):
    g = yt_guard.Guard(cfg, yt_guard.empty_ledger(), NOW)
    g.begin({"id": "b"})
    assert g.failure({"id": "b"}, "quota", "quotaExceeded")["until"].startswith("2026-11-27T08:10")


def test_classify():
    assert yt_guard.classify(LimitError()) == "upload_limit"
    assert yt_guard.classify(LimitError("quotaExceeded", 403)) == "quota"


def test_other_repo_uploads_count(cfg, state):
    cfg["publish"]["youtube_channel_daily_cap"] = 1
    g = yt_guard.Guard(cfg, yt_guard.empty_ledger(), NOW)
    g.reconcile("UC" + "x" * 22, [{"video_id": "o", "title": "posted elsewhere", "published_at": "2026-11-26T09:00:00Z"}], {"videos": []})
    assert not g.clearance({"id": "b"})[0]
    with pytest.raises(PermissionError):
        g.reconcile("UC" + "y" * 22, [], {"videos": []})


def test_upload_limit_is_never_retried(cfg, state, monkeypatch):
    cfg["publish"]["youtube_mode"] = "api"
    calls = {"upload": 0, "issues": []}
    monkeypatch.setattr(publish.youtube, "_client", lambda: object())
    monkeypatch.setattr(publish.youtube, "channel_state", lambda yt: ("UC" + "x" * 22, []))
    monkeypatch.setattr(publish, "open_issue_once", lambda t, b: calls["issues"].append(t))

    def boom(video, meta):
        calls["upload"] += 1
        raise LimitError()
    monkeypatch.setattr(publish.youtube, "upload", boom)
    hist = {"videos": [{"id": f"v{i}", "tag": "t", "title": f"Video {i}"} for i in range(4)]}
    meta = {"title": "Video 0", "description": "", "hashtags": []}
    err = publish.post_youtube(hist["videos"][0], meta, "f.mp4", cfg, hist)
    assert "upload_limit" in err and calls["upload"] == 1 and calls["issues"]
    assert hist["videos"][0]["yt_state"] == "skipped_limit"
    for v in hist["videos"][1:]:
        publish.post_youtube(v, dict(meta, title=v["title"]), "f.mp4", cfg, hist)
        assert v["yt_state"] == "skipped_limit"
    assert calls["upload"] == 1
    assert yt_guard.load()["pause"]["reason"] == "uploadLimitExceeded"
