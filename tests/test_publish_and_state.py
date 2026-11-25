import datetime as dt
import json
import sys

import pytest

from pipeline import analytics, common, instagram, publish, youtube


# ---------------- atomic state ----------------
def test_write_json_is_atomic(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    common.write_json(p, {"a": 1})

    class Boom:
        pass
    with pytest.raises(TypeError):
        common.write_json(p, {"bad": Boom()})
    assert json.loads(p.read_text()) == {"a": 1}
    assert [f.name for f in tmp_path.iterdir()] == ["s.json"]  # no temp leftovers


def test_history_v1_migration():
    h = common.migrate_history({"videos": [
        {"id": "a", "yt_done": True, "yt_video_id": None, "ig_media_id": "1"},
        {"id": "b", "yt_done": True, "yt_video_id": "X"},
        {"id": "c", "status": "queued"}]})
    a, b, c = h["videos"]
    assert a["yt_state"] == "manual_notified" and a["ig_state"] == "posted" and "yt_done" not in a
    assert b["yt_state"] == "posted" and c["language"] == "en" and c["theme"] == "explainer"
    assert h["version"] == common.HISTORY_VERSION


def test_secrets_redacted(monkeypatch, capsys):
    monkeypatch.setenv("IG_PAGE_TOKEN", "SUPERSECRETTOKEN123")
    common.log("calling https://x?access_token=SUPERSECRETTOKEN123")
    assert "SUPERSECRET" not in capsys.readouterr().out


# ---------------- publish ----------------
@pytest.fixture
def world(tmp_state, monkeypatch, tmp_path):
    """A queued video, fake platforms, fake gh."""
    common.save_history({"videos": [{"id": "v1", "tag": "vid-v1", "status": "queued", "created": "2026-11-16T04:00",
                                     "title": "T", "language": "hi"}]})
    out = tmp_path / "out"
    monkeypatch.setattr(publish, "OUT", out)
    calls = {"issues": [], "ig_publish": 0, "yt_upload": 0, "notify_ig": 0, "notify_yt": 0}

    def fake_run(cmd, check=True, capture=False, **kw):
        cmd = [str(c) for c in cmd]
        if cmd[:3] == ["gh", "release", "download"]:
            d = out / cmd[3].removeprefix("vid-")
            d.mkdir(parents=True, exist_ok=True)
            (d / "final.mp4").write_bytes(b"x")
            (d / "meta.json").write_text(json.dumps({"title": "T", "description": "D", "hashtags": ["#a"],
                                                     "caption": "T\n\nD", "language": "hi",
                                                     "synthetic_youtube": False, "ai_label_instagram": True}))
        if cmd[:3] == ["gh", "issue", "create"]:
            calls["issues"].append(cmd[cmd.index("--title") + 1])

        class R:
            returncode, stdout, stderr = 0, "[]", ""
        return R()
    monkeypatch.setattr(publish, "run", fake_run)
    monkeypatch.setattr(instagram, "find_existing", lambda caption: None)
    monkeypatch.setattr(youtube, "find_existing", lambda title: None)
    monkeypatch.setattr(instagram, "notify_manual", lambda m, t: calls.__setitem__("notify_ig", calls["notify_ig"] + 1))
    monkeypatch.setattr(youtube, "notify_manual", lambda m, t: calls.__setitem__("notify_yt", calls["notify_yt"] + 1))
    cfg = common.load_config()
    cfg["paused"] = False
    cfg["publish"].update({"instagram": True, "youtube_mode": "api", "instagram_max_attempts": 2})
    slot = (common.now_ist() - dt.timedelta(minutes=1)).strftime("%H:%M")
    cfg["schedule"] = [{"time": slot, "language": "hi"}]   # due right now
    monkeypatch.setattr(publish, "load_config", lambda: cfg)
    return calls


def video():
    return common.load_history()["videos"][0]


def ig_ok(calls):
    def f(path, caption, video_url=None, ai_label=True):
        calls["ig_publish"] += 1
        assert ai_label is True
        return "IG1", "link"
    return f


def yt_ok(calls, privacy="public"):
    def f(path, meta):
        calls["yt_upload"] += 1
        assert meta["synthetic_youtube"] is False
        return "YT1", privacy
    return f


def test_happy_path(world, monkeypatch):
    monkeypatch.setattr(instagram, "publish", ig_ok(world))
    monkeypatch.setattr(youtube, "upload", yt_ok(world))
    publish.main()
    v = video()
    assert v["status"] == "published" and v["ig_state"] == "posted" and v["yt_state"] == "posted"
    assert v["slot"].startswith(common.now_ist().strftime("%Y-%m-%d"))
    publish.main()   # second run: today's slot is done -> nothing happens, nothing re-posted
    assert world["ig_publish"] == 1 and world["yt_upload"] == 1


def test_youtube_failure_does_not_repost_instagram(world, monkeypatch):
    monkeypatch.setattr(instagram, "publish", ig_ok(world))

    def yt_boom(path, meta):
        raise RuntimeError("quota")
    monkeypatch.setattr(youtube, "upload", yt_boom)
    with pytest.raises(SystemExit):
        publish.main()
    assert video()["status"] == "queued" and video()["ig_state"] == "posted"
    monkeypatch.setattr(youtube, "upload", yt_ok(world))
    publish.main()
    assert world["ig_publish"] == 1 and video()["status"] == "published"


def test_instagram_retries_then_single_manual_notice(world, monkeypatch):
    def ig_boom(*a, **k):
        raise RuntimeError("meta down")
    monkeypatch.setattr(instagram, "publish", ig_boom)
    monkeypatch.setattr(youtube, "upload", yt_ok(world))
    with pytest.raises(SystemExit):
        publish.main()
    assert video()["ig_attempts"] == 1 and world["notify_ig"] == 0 and video()["status"] == "queued"
    with pytest.raises(SystemExit):
        publish.main()
    assert video()["ig_state"] == "manual_notified" and world["notify_ig"] == 1
    assert video()["status"] == "published" and world["yt_upload"] == 1


def test_private_youtube_upload_is_not_treated_as_posted(world, monkeypatch):
    monkeypatch.setattr(instagram, "publish", ig_ok(world))
    monkeypatch.setattr(youtube, "upload", yt_ok(world, privacy="private"))
    with pytest.raises(SystemExit):
        publish.main()
    v = video()
    assert v["yt_state"] == "private" and v["yt_video_id"] == "YT1"
    assert any("private" in t for t in world["issues"])
    assert v["status"] == "published"  # re-uploading would only make another locked copy


def test_lost_state_does_not_double_post(world, monkeypatch):
    monkeypatch.setattr(instagram, "find_existing", lambda caption: "IG_OLD")
    monkeypatch.setattr(youtube, "find_existing", lambda title: "YT_OLD")
    monkeypatch.setattr(instagram, "publish", ig_ok(world))
    monkeypatch.setattr(youtube, "upload", yt_ok(world))
    publish.main()
    assert world["ig_publish"] == 0 and world["yt_upload"] == 0
    assert video()["ig_media_id"] == "IG_OLD" and video()["yt_video_id"] == "YT_OLD"


def test_state_saved_even_if_youtube_crashes_process(world, monkeypatch):
    monkeypatch.setattr(instagram, "publish", ig_ok(world))

    def yt_kill(path, meta):
        raise KeyboardInterrupt  # simulates the runner dying mid-upload
    monkeypatch.setattr(youtube, "upload", yt_kill)
    with pytest.raises(KeyboardInterrupt):
        publish.main()
    assert video()["ig_state"] == "posted"  # already on disk before YouTube started


def test_manual_youtube_mode(world, monkeypatch):
    monkeypatch.setattr(instagram, "publish", ig_ok(world))
    publish.load_config()["publish"]["youtube_mode"] = "manual"
    publish.main()
    assert video()["yt_state"] == "manual_notified" and world["notify_yt"] == 1


def test_no_video_is_one_red_run_and_one_issue(world, monkeypatch):
    common.save_history({"videos": []})
    with pytest.raises(SystemExit):
        publish.main()
    publish.main()   # the missed slot is recorded: later runs stay quiet
    assert len(world["issues"]) == 1 and common.load_history()["missed_slots"]


def test_slot_language_and_manual_button(world, monkeypatch):
    monkeypatch.setattr(instagram, "publish", ig_ok(world))
    monkeypatch.setattr(youtube, "upload", yt_ok(world))
    h = common.load_history()
    h["videos"].insert(0, {"id": "e1", "tag": "vid-e1", "status": "queued", "created": "2026-11-15T04:00", "language": "en"})
    common.save_history(h)
    publish.main()   # the hi slot takes the hi video, not the older English one
    assert [v.get("status") for v in common.load_history()["videos"]] == ["queued", "published"]
    monkeypatch.setattr(sys, "argv", ["publish", "--now"])
    publish.main()   # manual button: oldest ready one, no slot needed
    assert common.load_history()["videos"][0]["slot"].endswith("manual")


# ---------------- analytics ----------------
def test_analytics_migrates_and_survives_api_failures(tmp_state, monkeypatch, cfg):
    common.save_history({"videos": [
        {"id": "a", "status": "published", "published_at": "2026-11-01T19:00+05:30", "language": "en",
         "topic": "x", "ig_media_id": "1", "metrics": {"ig_views": 50}},
        {"id": "b", "status": "queued", "created": "2026-11-16T04:00"}]})
    monkeypatch.setenv("IG_PAGE_TOKEN", "tok-for-test")

    def boom(*a, **k):
        raise RuntimeError("permission missing")
    monkeypatch.setattr(instagram, "insights", boom)
    monkeypatch.setattr(youtube, "stats", boom)
    analytics.main()
    a = json.loads((tmp_state / "analytics.json").read_text())
    assert a["version"] == 1 and a["videos"]["a"]["metrics"]["ig_views"] == 50
    assert a["videos"]["a"]["views"] == {"ig": 50} and a["videos"]["a"]["language"] == "en"
    assert "metrics" not in common.load_history()["videos"][0]


def test_analytics_saves_when_nothing_published(tmp_state, monkeypatch, cfg):
    common.save_history({"videos": []})
    analytics.main()
    assert (tmp_state / "analytics.json").exists()


def test_private_youtube_views_excluded():
    assert analytics._views({"yt_views": 3, "yt_privacy": "private", "ig_views": 9}) == {"ig": 9}


def test_disclosure_follows_content(cfg):
    from pipeline.produce import disclosure
    assert disclosure(cfg) == {"synthetic_youtube": False, "ai_label_instagram": True}
    cfg["disclosure"]["youtube_synthetic"] = True
    assert disclosure(cfg)["synthetic_youtube"] is True


def test_no_secret_values_in_repo_files():
    root = common.ROOT
    for p in list((root / "pipeline").rglob("*.py")) + list((root / ".github").rglob("*.yml")):
        txt = p.read_text(encoding="utf-8")
        assert "EAAB" not in txt and "ya29." not in txt and "sk-ant-" not in txt, p


def test_release_upload_retries_github_hiccups(monkeypatch):
    from pipeline import produce
    calls = []

    def fake_run(cmd, check=True, **kw):
        calls.append(cmd[:3])
        if cmd[:3] == ["gh", "release", "create"] and sum(c == ["gh", "release", "create"] for c in calls) < 3:
            raise RuntimeError("Command failed (1): HTTP 502: Error creating policy")
    monkeypatch.setattr(produce, "run", fake_run)
    monkeypatch.setattr(produce.time, "sleep", lambda s: None)
    produce.upload_release("vid-x", ["a.mp4"], "t", "n")
    assert calls.count(["gh", "release", "create"]) == 3 and calls.count(["gh", "release", "delete"]) == 2


def test_one_failed_video_does_not_cost_the_others(monkeypatch, tmp_state):
    from pipeline import produce
    made = []

    def fake_one(cfg, history, stats, test, language, theme=None):
        if language == "hi":
            raise RuntimeError("HTTP 502")
        made.append(language)
        return tmp_state, {"id": "x"}, {}, None
    monkeypatch.setattr(produce, "produce_one", fake_one)
    monkeypatch.setattr(produce, "queue", lambda *a: None)
    monkeypatch.setattr(produce.analytics, "load", lambda: {})
    monkeypatch.setattr(produce.schedule, "to_make", lambda cfg, q: ["hi", "en", "en"])
    monkeypatch.setattr(sys, "argv", ["produce", "--release"])
    with pytest.raises(SystemExit, match="1 video"):
        produce.main()
    assert made == ["en", "en"]
