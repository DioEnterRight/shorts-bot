"""FreeLLMAPI 3D builder: storyboard validation/compile, OpenAI-compatible client (mock server), full render path with a fake free model."""
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from pipeline import cartoon3d, freellm, storyboard3d as sb
from pipeline.common import load_config

MODELS = sb.parse_catalog()
ROSTER = [{"name": "Vic", "look": "man_suit", "skin": "tan"}, {"name": "mark", "look": "man_blue", "skin": "light"}]
GOOD = {"plan": ["x"], "cast": ROSTER, "scenes": [{"ground": "street", "wall": "none", "light": "day",
        "props": [{"model": "city/building_A", "at": "back"}, {"model": "city/streetlight", "at": "mid_right"}],
        "cast": [{"who": "vic", "expr": "grin", "arm": "point", "at": "center"}], "camera": "medium", "sfx": "pop"}]}


def scene(**kw):
    return dict(GOOD["scenes"][0], **kw)


def board(*scenes, cast=ROSTER):
    return {"plan": ["p"] * len(scenes), "cast": cast, "scenes": list(scenes)}


def test_catalog_and_prompt_list_real_models():
    assert len(MODELS) == 324 and "city/building_A" in MODELS
    cat = sb.catalog_text()
    assert "city (name height_m)" in cat and "chest_gold" in cat
    msgs = sb.build_messages({"title": "T", "scenes": [{"line": "Hello there.", "visual": "a man waves"}]}, [(0, 59)])
    p = msgs[1]["content"]
    assert msgs[0]["role"] == "system" and "exactly 1 entries" in p and "Hello there." in p and "a man waves" in p
    assert "chest_gold" in p and '"who"' in p
    r = sb.review_messages({"title": "T", "scenes": [{"line": "Hello there."}]}, [(0, 59)], GOOD)[1]["content"]
    assert "strict art director" in r and "city/streetlight" in r


def test_the_prompt_example_is_itself_a_valid_storyboard():
    clean, problems = sb.normalize(sb.EXAMPLE, 2, MODELS)
    assert problems == [] and clean[0]["cast"][0]["look"] == "worker"


def test_cast_roster_keeps_characters_consistent():
    clean, problems = sb.normalize(board(scene(), scene(ground="tile", cast=[{"who": "Mark", "expr": "shock"}, {"who": "ghost"}])), 2, MODELS)
    assert clean[0]["cast"][0]["look"] == "man_suit" and clean[0]["cast"][0]["skin"] == "tan"
    assert clean[1]["cast"][0]["look"] == "man_blue" and any("ghost" in p for p in problems)
    _, problems = sb.normalize(board(scene(), cast=[{"name": "a", "look": "boss"}, {"name": "b", "look": "boss"}]), 1, MODELS)
    assert any("same look" in p for p in problems)


def test_normalize_is_tolerant_but_reports_every_problem():
    bad = board(scene(ground="lava", light="neon", props=[{"model": "nope/x"}, {"model": "city/bench", "at": "nowhere"}, {"model": "city/bush"}],
                      cast=[{"who": "vic", "expr": "grin!!", "arm": "hand"}], camera="drone", sfx="boing"), cast=[{"name": "vic", "look": "alien"}])
    clean, problems = sb.normalize(bad, 1, MODELS)
    c = clean[0]
    assert (c["ground"], c["light"], c["camera"], c["sfx"]) == ("street", "day", "medium", "")
    assert [p["model"] for p in c["props"]] == ["city/bench", "city/bush"] and c["cast"][0]["look"] in sb.LOOKS
    for word in ("lava", "neon", "nope/x", "nowhere", "alien", "drone", "boing", "hand"):
        assert any(word in p for p in problems), word


def test_normalize_flags_wrong_scene_count_repeats_and_empty_props():
    clean, problems = sb.normalize(board(scene(), scene()), 3, MODELS)
    assert len(clean) == 3 and any("exactly 3 scenes" in p for p in problems) and any("repeats the set" in p for p in problems)
    assert not sb.fatal(problems, 3)
    _, problems = sb.normalize(board(scene()), 6, MODELS)
    assert sb.fatal(problems, 6)
    _, problems = sb.normalize(board(scene(props=[{"model": "city/bush"}])), 1, MODELS)
    assert any("add 2-6 props" in p for p in problems)
    with pytest.raises(ValueError):
        sb.normalize({"nope": 1}, 1, MODELS)


def test_compile_cuts_long_scenes_and_covers_every_frame():
    clean, _ = sb.normalize(board(scene(), scene(props=[{"model": "city/building_C", "at": "back"}], camera="close"),
                                  scene(cast=[], camera="wide", props=[{"model": "city/building_B", "at": "back"}])), 3, MODELS)
    tl = [{"words": [{"start": s}]} for s in (0, 5.0, 9.0)]
    spans = sb.spans_from_timeline(tl, 450)
    assert spans[0][0] == 0 and spans[-1][1] == 449 and all(spans[i][1] + 1 == spans[i + 1][0] for i in range(2))
    d = sb.compile_data(clean, spans, 450)
    shots = d["shots"]
    assert shots[0]["a"] == 0 and shots[-1]["b"] == 449
    assert all(shots[i]["b"] + 1 == shots[i + 1]["a"] for i in range(len(shots) - 1))
    assert all(s["b"] - s["a"] + 1 <= sb.MAX_SHOT_FRAMES + 1 for s in shots) and len(shots) >= 5
    assert all(shots[i]["cam"][0]["pos"] != shots[i + 1]["cam"][0]["pos"] for i in range(len(shots) - 1))
    assert sb.sfx_events(clean, spans) == [[0.0, "pop"], [5.0, "pop"], [9.0, "pop"]]
    json.dumps(d)


def test_spans_reject_a_last_scene_that_starts_too_late():
    with pytest.raises(ValueError, match="too late"):
        sb.spans_from_timeline([{"words": [{"start": 0}]}, {"words": [{"start": 1.2}]}], 36)


def test_extract_json_handles_fences_chatter_and_cut_off_replies():
    assert freellm.extract_json('Sure!\n```json\n{"a": {"b": "}"}}\n```\nbye') == {"a": {"b": "}"}}
    assert freellm.extract_json('<think>maybe {"no": 1}</think>{"a": "q\\"}"}') == {"a": 'q"}'}
    with pytest.raises(ValueError):
        freellm.extract_json("no json here")
    with pytest.raises(ValueError):
        freellm.extract_json('{"a": [1, 2')


class FakeLLM:
    """An OpenAI-compatible /chat/completions server. replies: list of (status, text); the last one repeats."""
    def __init__(self, replies):
        self.replies, self.seen, self.auth = list(replies), [], []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.seen.append(body); outer.auth.append(self.headers.get("Authorization"))
                status, text = outer.replies[min(len(outer.seen) - 1, len(outer.replies) - 1)]
                self.send_response(status); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps({"choices": [{"message": {"content": text}}]} if status == 200 else {"error": "x"}).encode())

            def log_message(self, *a):
                pass
        self.srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}/v1"

    def close(self):
        self.srv.shutdown()


def cfg_for(url, monkeypatch, **freellm_cfg):
    monkeypatch.setenv("FREELLM_BASE_URL", url)
    monkeypatch.setenv("FREELLM_API_KEY", "sk-test-123")
    monkeypatch.setattr(freellm.time, "sleep", lambda s: None)
    cfg = load_config()
    cfg["freellm"].update(freellm_cfg)
    return cfg


MSG = [{"role": "user", "content": "hi"}]


def test_client_sends_key_and_json_mode_retries_and_records_usage(tmp_state, monkeypatch):
    srv = FakeLLM([(429, ""), (503, ""), (200, "hello")])
    try:
        cfg = cfg_for(srv.url, monkeypatch)
        assert freellm.configured(cfg)
        assert freellm.chat(cfg, MSG, freellm.Budget(cfg)) == "hello"
        assert len(srv.seen) == 3 and srv.seen[0]["model"] == "auto:smart" and set(srv.auth) == {"Bearer sk-test-123"}
        assert srv.seen[0]["response_format"] == {"type": "json_object"}
        assert freellm.month_usage()["calls"] == 1
    finally:
        srv.close()


def test_client_moves_to_the_next_model_on_quota_exceeded_or_auth_errors(tmp_state, monkeypatch):
    srv = FakeLLM([(200, "from second")])
    pinned = []
    try:
        cfg = cfg_for(srv.url, monkeypatch, models=["pinned-model", "auto:smart"])
        orig = freellm._post
        def post(f, model, messages, json_mode):
            if model == "pinned-model":
                pinned.append(1)
                raise freellm.urllib.error.HTTPError(f["base_url"], 429, "x", {}, __import__("io").BytesIO(b'{"error":{"code":"quota_exceeded"}}'))
            return orig(f, model, messages, json_mode)
        monkeypatch.setattr(freellm, "_post", post)
        assert freellm.chat(cfg, MSG, freellm.Budget(cfg)) == "from second"
        assert pinned == [1] and len(srv.seen) == 1 and srv.seen[0]["model"] == "auto:smart"   # used-up model: no retries
    finally:
        srv.close()
    srv = FakeLLM([(401, "")])
    try:
        with pytest.raises(RuntimeError, match="HTTP 401") as e:
            freellm.chat(cfg_for(srv.url, monkeypatch), MSG, freellm.Budget(load_config()))
        assert len(srv.seen) == 1 and "sk-test-123" not in str(e.value)
    finally:
        srv.close()


def test_per_video_and_monthly_caps(tmp_state, monkeypatch):
    srv = FakeLLM([(503, "")])
    try:
        cfg = cfg_for(srv.url, monkeypatch, max_calls_per_video=2)
        with pytest.raises(RuntimeError, match="per-video request cap"):
            freellm.chat(cfg, MSG, freellm.Budget(cfg))
        assert len(srv.seen) == 2
    finally:
        srv.close()
    cfg["freellm"]["monthly_token_cap"] = 100
    freellm._record("x/y", {"prompt_tokens": 90, "completion_tokens": 20})
    with pytest.raises(RuntimeError, match="monthly cap reached"):
        freellm.Budget(cfg)


def test_unconfigured_free_builder_fails_fast(monkeypatch, tmp_path):
    monkeypatch.delenv("FREELLM_BASE_URL", raising=False)
    monkeypatch.delenv("FREELLM_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FREELLMAPI_KEYS"):
        cartoon3d.render_free(load_config(), {"title": "T", "scenes": []}, [], tmp_path / "v.wav", 1.0, tmp_path)


def test_review_is_kept_only_when_not_worse(tmp_state, monkeypatch):
    spans = [(0, 59)]
    script = {"title": "T", "scenes": [{"line": "Hi.", "visual": "wave"}]}
    better = board(scene(props=[{"model": "city/building_A", "at": "back"}, {"model": "city/bench", "at": "mid_left"}]))
    worse = board(scene(props=[{"model": "nope/x"}, {"model": "city/bench"}, {"model": "city/bush"}], ground="lava"))
    for review, expect in ((better, "city/bench"), (worse, "city/streetlight")):
        srv = FakeLLM([(200, json.dumps(GOOD)), (200, json.dumps(review))])
        try:
            clean, raw = cartoon3d.free_storyboard(cfg_for(srv.url, monkeypatch, repair_rounds=0), script, spans)
            assert [p["model"] for p in clean[0]["props"]][1] == expect and len(srv.seen) == 2
        finally:
            srv.close()


def test_render_dispatch_and_optional_claude_rescue(monkeypatch, tmp_path):
    cfg = load_config()
    cfg["cartoon3d"]["builder"] = "freellm"
    boom = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("free model down"))
    monkeypatch.setattr(cartoon3d, "render_free", boom)
    with pytest.raises(RuntimeError, match="free model down"):    # default: no Claude spend, the caller falls back to 2D
        cartoon3d.render(cfg, {"scenes": []}, [], tmp_path / "v", 1.0, tmp_path, "en", lambda *a, **k: "x")
    cfg["cartoon3d"]["claude_rescue"] = True
    monkeypatch.setattr(cartoon3d, "_setup", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("reached the Claude path")))
    with pytest.raises(RuntimeError, match="reached the Claude path"):
        cartoon3d.render(cfg, {"scenes": []}, [], tmp_path / "v", 1.0, tmp_path, "en", lambda *a, **k: "x")


@pytest.mark.slow
def test_free_builder_end_to_end_with_a_fake_free_model(tmp_state, monkeypatch, tmp_path):
    """Real setup, preflight, repair loop, Chrome stills + frames, SFX, music, captions, encode. Only the LLM is fake."""
    wav = tmp_path / "voice.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=180:d=1.2", "-ar", "24000", str(wav)], check=True)
    tl = [{"words": [{"word": "Hello", "start": .1, "end": .5}, {"word": "world.", "start": .5, "end": 1.1}]}]
    first = json.dumps(board(scene(props=[{"model": "nope/x"}]), scene()))   # wrong count + unknown model + too few props
    srv = FakeLLM([(200, "<think>plan</think>Here you go:\n```json\n" + first + "\n```"), (200, json.dumps(GOOD))])
    try:
        cfg = cfg_for(srv.url, monkeypatch)
        script = {"title": "T", "mood": "upbeat", "scenes": [{"line": "Hello world.", "visual": "a man waves"}]}
        out = cartoon3d.render_free(cfg, script, tl, wav, 1.2, tmp_path / "work")
        assert len(srv.seen) == 3 and "Fix these problems" in srv.seen[1]["messages"][-1]["content"]
        assert "strict art director" in srv.seen[2]["messages"][-1]["content"]
        assert "nope/x" in srv.seen[1]["messages"][-1]["content"]
    finally:
        srv.close()
    got = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=pix_fmt,width,height,nb_frames",
                          "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    assert got == "1080,1920,yuv420p,36", got
    used = json.loads((tmp_path / "work" / "cartoon3d_work" / "storyboard.json").read_text())["used"]
    assert used[0]["props"][0]["model"] == "city/building_A" and used[0]["cast"][0]["look"] == "man_suit"
