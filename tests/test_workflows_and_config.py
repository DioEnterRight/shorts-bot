import pathlib

import yaml

from pipeline import produce

ROOT = pathlib.Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"


def load(name):
    return yaml.safe_load((WF / name).read_text())


def steps(wf):
    return [s for job in wf["jobs"].values() for s in job["steps"]]


def test_workflows_parse_and_queue_apart():
    groups = {}
    for f in WF.glob("*.yml"):
        wf = yaml.safe_load(f.read_text())
        groups[f.name] = wf["concurrency"]["group"]
        assert wf["concurrency"]["cancel-in-progress"] is False, f
    # a long Make never blocks (or cancels) a Post; both save data/ through the JSON merge driver
    assert groups["make-video.yml"] == "shorts-make" and groups["post-video.yml"] == "shorts-post"


def test_state_push_failures_are_not_swallowed():
    for f in WF.glob("*.yml"):
        txt = f.read_text()
        assert "git push || true" not in txt and "pull --rebase -q || true" not in txt, f
        if yaml.safe_load(txt)["permissions"].get("contents") == "write":   # read-only checks save nothing
            assert "tools/save_state.sh" in txt, f
    script = (ROOT / "tools" / "save_state.sh").read_text()
    assert "set -euo pipefail" in script and "exit 1" in script


def test_language_selector():
    on = load("make-video.yml")[True]  # PyYAML reads the key `on` as True
    assert on["workflow_dispatch"]["inputs"]["language"]["options"] == ["auto", "en", "hi"]
    assert "provider" not in on["workflow_dispatch"]["inputs"]

def test_schedules():
    assert load("make-video.yml")[True]["schedule"][0]["cron"] == "13 * * * *"
    assert load("post-video.yml")[True]["schedule"][0]["cron"] == "7,37 * * * *"   # times live in config.yaml schedule


def test_idle_post_runs_stop_at_the_gate():
    st = steps(load("post-video.yml"))
    gate = [i for i, x in enumerate(st) if x.get("id") == "gate"][0]
    assert "pipeline.schedule" in st[gate]["run"]
    assert all(x.get("if") == "steps.gate.outputs.due == 'true'" for x in st[gate + 1:] if "save_state" not in x.get("run", ""))


def test_scheduled_run_is_never_test_mode():
    env = load("make-video.yml")["jobs"]["make"]["env"]
    assert env["TEST"].startswith("${{ github.event_name == 'workflow_dispatch' &&")


def test_save_steps_always_run():
    for name in ("make-video.yml", "post-video.yml", "clear-queue.yml"):
        save = [s for s in steps(load(name)) if "save_state.sh" in s.get("run", "")]
        assert save and "always()" in save[0].get("if", ""), name


def test_config_languages_and_themes(cfg):
    assert cfg["languages"]["enabled"] == ["en", "hi"]
    for code in cfg["languages"]["enabled"]:
        lp = cfg["languages"][code]
        assert (ROOT / lp["prompt"]).exists()
    shares = {k: t["share"] for k, t in cfg["themes"].items()}
    assert abs(sum(shares.values()) - 1) < 1e-6 and 0.75 <= shares["explainer"] <= 0.85


def test_daily_schedule(cfg):
    from pipeline import schedule
    s = schedule.slots(cfg)
    assert len(s) == 24 and s[0] == ("00:30", "en") and [t for t, l in s if l == "hi"] == ["09:30"]
    assert produce.choose_theme(cfg, {"videos": []}) == "explainer"


def test_make_video_installs_the_kit_studio_and_keeps_versions():
    wf = load("make-video.yml")
    st = steps(wf)
    kit = [x for x in st if x.get("working-directory") == ".claude/skills/animated-shorts-kit/code"]
    assert kit and "npm ci" in kit[0]["run"]
    assert any("requirements.txt" in x.get("run", "") for x in st)
    up = [x for x in st if x.get("with", {}).get("name") == "versions"]
    assert up and "always()" in up[0]["if"]
    text = (WF / "make-video.yml").read_text(encoding="utf-8")
    assert "playwright" not in text.lower() and "CF_API_TOKEN" not in text and not (WF / "long-video.yml").exists()


def test_render_and_voice_config(cfg):
    assert set(cfg) >= {"studio", "toon2d", "freellm", "voice", "claude"}
    assert not {"longform", "cartoon3d", "reel_qc", "render", "visuals", "captions", "audio"} & set(cfg)
    assert 45 <= cfg["video"]["target_seconds"] <= 65                     # kit story formula
    assert -15 <= cfg["studio"]["music_db"] <= -10                        # kit: bed 10-15 dB under the voice
    assert cfg["voice"]["engine"] in ("edge", "kokoro")
    for code in cfg["languages"]["enabled"]:
        assert cfg["languages"][code].get("edge_voice") and 2.3 <= cfg["languages"][code]["words_per_second"] <= 3.8
    assert all(set(t) == {"share", "guidance"} for t in cfg["themes"].values())
