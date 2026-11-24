"""Reel director: story objects, directed shots, cue timing, fitted framing, visual QC loop and the final inspector."""
import json
import math
import re
import subprocess

import pytest

from pipeline import cartoon3d, freellm, reel_qc, storyboard3d as sb
from pipeline.common import ROOT, load_config
from tests.test_storyboard3d import FakeLLM, MODELS, cfg_for

LINES = ["He opened the briefcase and the cash fell out.", "The agent read the serial number and smiled."]
WORDS = [[{"word": w, "start": round(i * 0.3, 2), "end": round(i * 0.3 + 0.25, 2)} for i, w in enumerate(LINES[0].split())],
         [{"word": w, "start": round(3.0 + i * 0.3, 2), "end": round(3.25 + i * 0.3, 2)} for i, w in enumerate(LINES[1].split())]]
BOARD = {"story": {"hook": "h", "turn": "t", "payoff": "p"}, "plan": ["a", "b"],
         "cast": [{"name": "cooper", "look": "man_suit", "skin": "light"}, {"name": "agent", "look": "clerk", "skin": "tan"}],
         "scenes": [
             {"ground": "carpet", "wall": "grey", "light": "indoor", "shot": "medium", "move": "push_in", "focus": "cooper",
              "props": [{"prefab": "briefcase", "at": "mid_right", "open": True, "hero": True},
                        {"prefab": "cash_pile", "at": "near_right", "anim": "drop", "cue": "cash"},
                        {"prefab": "label", "at": "mid_left", "text": "$200,000"}],
              "cast": [{"who": "cooper", "expr": "stern", "arm": "point", "react": {"expr": "grin", "arm": "thumb", "cue": "fell"}}]},
             {"ground": "tile", "wall": "blue", "light": "indoor", "shot": "insert", "move": "rack_focus", "focus": "hero",
              "props": [{"prefab": "banknote", "at": "near_left", "text": "$20|L 0714 0771 B", "hero": True},
                        {"prefab": "document", "at": "mid_right", "text": "FBI|SERIALS"}],
              "cast": [{"who": "agent", "expr": "squint", "arm": "cheek", "react": {"expr": "smile", "arm": "thumb", "cue": "smiled"}}]}]}


def compiled(board=BOARD, total=200):
    clean, problems = sb.normalize(board, 2, MODELS, LINES)
    spans = sb.spans_from_timeline([{"words": w} for w in WORDS], total)
    return clean, problems, spans, sb.compile_data(clean, spans, total, 30, WORDS)


def test_prefab_list_matches_the_engine():
    js = (sb.KIT / "engine" / "prefabs.js").read_text()
    block = js[js.index("export const BUILDERS = {"):js.index("};", js.index("export const BUILDERS = {"))]
    names = {it.split(":")[0].strip() for it in block.split("{", 1)[1].split(",") if it.strip()}
    assert names == set(sb.PREFABS) == set(sb.PREFAB_W), names ^ set(sb.PREFABS)


def test_director_rules_are_enforced():
    bad = json.loads(json.dumps(BOARD))
    s0, s1 = bad["scenes"]
    s0["props"][1]["cue"] = "dragon"                                     # cue not in the line
    s0["props"].append({"prefab": "jet", "anim": "fly"})                 # fly outside the sky
    s0["props"].append({"prefab": "safe", "text": "OPEN"})               # text on a non-text object
    s0["props"][2]["text"] = "A" * 50                                    # too long
    s1["shot"], s1["move"] = "over_shoulder", "follow"                   # 1 person, nothing moving
    clean, problems = sb.normalize(bad, 2, MODELS, LINES)
    joined = " | ".join(problems)
    for needle in ("cue 'dragon'", "anim 'fly' needs ground 'sky'", "can't show text", "longer than 34", "over_shoulder needs 2", "move 'follow' needs"):
        assert needle in joined, needle
    assert clean[1]["shot"] == "medium" and clean[1]["move"] == "track" and len(clean[0]["props"][2]["opts"]["text"]) == 34
    sky = json.loads(json.dumps(BOARD)); sky["scenes"][0]["ground"] = "sky"
    clean, problems = sb.normalize(sky, 2, MODELS, LINES)
    assert clean[0]["cast"] == [] and any("sky" in p for p in problems)
    rep = json.loads(json.dumps(BOARD)); rep["scenes"][1].update(shot="medium", move="push_in")
    assert any("same shot and move" in p for p in sb.normalize(rep, 2, MODELS, LINES)[1])


def test_reveals_and_reactions_land_on_their_words():
    clean, problems, spans, data = compiled()
    assert problems == []
    drop = data["scenes"][0]["props"][1]["anim"]
    cash_t = next(w["start"] for w in WORDS[0] if w["word"] == "cash")
    assert drop["type"] == "drop" and abs(drop["f0"] - (round(cash_t * 30) - 2)) <= 1
    react = data["shots"][0]["cast"][0]["react"]
    assert abs(react["f"] - (round(next(w["start"] for w in WORDS[0] if w["word"] == "fell") * 30) - 2)) <= 1
    assert data["scenes"][1]["props"][0]["opts"]["text"] == "$20|L 0714 0771 B"


def test_shots_cover_every_frame_and_never_repeat():
    _, _, _, data = compiled(total=420)
    shots = data["shots"]
    assert shots[0]["a"] == 0 and shots[-1]["b"] == 419 and all(shots[i]["b"] + 1 == shots[i + 1]["a"] for i in range(len(shots) - 1))
    pairs = [(s["kind"], s["move"]) for s in shots]
    assert all(pairs[i] != pairs[i + 1] for i in range(len(pairs) - 1)) and len({p[0] for p in pairs}) >= 3
    assert all(s["b"] - s["a"] + 1 <= sb.MAX_SHOT_FRAMES + 1 for s in shots)
    rack = next(s for s in shots if s["move"] == "rack_focus")
    assert rack["focus2"] != rack["focus"]


def _in_view(key, pt):
    """Is point pt inside the 9:16 view of camera key? (angles against the half fovs)"""
    pos, look, fov = key["pos"], key["look"], key["fov"]
    f = [look[i] - pos[i] for i in range(3)]; n = math.sqrt(sum(v * v for v in f)); f = [v / n for v in f]
    r = [f[2], 0, -f[0]]; rn = math.hypot(r[0], r[2]); r = [r[0] / rn, 0, r[2] / rn]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    d = [pt[i] - pos[i] for i in range(3)]
    z = sum(d[i] * f[i] for i in range(3))
    x, y = sum(d[i] * r[i] for i in range(3)), sum(d[i] * u[i] for i in range(3))
    tv = math.tan(math.radians(fov) / 2)
    return z > 0 and abs(y / z) <= tv and abs(x / z) <= tv * 9 / 16


def test_medium_shot_frames_the_person_the_hero_and_the_info_card():
    _, _, _, data = compiled()
    s = data["shots"][0]
    assert s["kind"] == "medium"
    props = data["scenes"][0]["props"]
    cooper = s["cast"][0]
    for pt in ([cooper["x"], 2.0, cooper["z"]], [cooper["x"], 0.2, cooper["z"]], [props[0]["x"], 0.4, props[0]["z"]], [props[2]["x"], 2.6, props[2]["z"]]):
        assert _in_view(s["cam"][0], pt), pt


def test_follow_shot_tracks_the_flying_jet_and_insert_never_frames_a_jet():
    board = {"cast": [], "scenes": [
        {"ground": "sky", "light": "night", "shot": "insert", "move": "follow", "props": [{"prefab": "jet", "anim": "fly", "hero": True}, {"prefab": "cloud", "at": "back"}]},
        {"ground": "dirt", "light": "day", "shot": "low", "move": "tilt_up", "props": [{"prefab": "jet", "at": "back"}, {"prefab": "sign", "at": "mid_left", "text": "AIRPORT"}]}]}
    clean, problems = sb.normalize(board, 2, MODELS, LINES)
    spans = sb.spans_from_timeline([{"words": w} for w in WORDS], 200)
    data = sb.compile_data(clean, spans, 200, 30, WORDS)
    s = data["shots"][0]
    assert s["kind"] == "wide" and s["move"] == "follow" and s["ease"] == "linear" and len(s["cam"]) > 3
    A = data["scenes"][0]["props"][0]["anim"]
    for k in s["cam"]:
        dx, _ = sb._prop_offset(k["f"], A)
        assert _in_view(k, [dx, 2.5 + (k["f"] - A["f0"]) / (A["f1"] - A["f0"]) * 2.5, 0])


def test_review_parsing_and_weak_scene_choice():
    r = reel_qc.parse_review({"scenes": [{"n": 1, "score": 12, "shows_line": True}, {"n": "2", "score": 4, "shows_line": True, "issue": "tiny cash"},
                                         {"n": 3, "score": 7, "shows_line": False, "fix": "bigger"}], "storytelling": "8", "camera": None}, 4)
    assert [s["score"] for s in r["scenes"]] == [10.0, 4.0, 7.0, None] and r["storytelling"] == 8.0 and r["camera"] is None
    assert [w["n"] for w in reel_qc.weak_scenes(r)] == [2, 3]
    assert reel_qc.review_mean(r) == pytest.approx(7.0) and reel_qc.review_mean(r, [2]) == 4.0


def _still(path, colour):
    from PIL import Image
    Image.new("RGB", (1080, 1920), colour).save(path)
    return path


@pytest.mark.parametrize("second, kept", [(9, "fixed"), (3, "draft")])
def test_visual_fix_is_kept_only_when_the_rerender_scores_better(monkeypatch, tmp_path, second, kept):
    clean, _, spans, _ = compiled()
    fixed = json.loads(json.dumps(BOARD)); fixed["scenes"][1]["props"][1] = {"prefab": "magnifier", "at": "mid_right", "size": 1.5}
    reviews = iter([reel_qc.parse_review({"scenes": [{"n": 1, "score": 8, "shows_line": True}, {"n": 2, "score": 4, "shows_line": False, "issue": "x"}]}, 2),
                    reel_qc.parse_review({"scenes": [{"n": 1, "score": 8, "shows_line": True}, {"n": 2, "score": second, "shows_line": True}]}, 2)])
    monkeypatch.setattr(reel_qc, "preview_review", lambda *a, **k: next(reviews))
    monkeypatch.setattr(cartoon3d, "_scene_stills", lambda project, frames, name: [_still(tmp_path / f"{name}{i}.jpg", "gray") for i in range(len(frames))])
    monkeypatch.setattr(cartoon3d, "_ask", lambda *a, **k: (None, fixed, []))
    monkeypatch.setattr(sb, "write_project", lambda *a, **k: None)
    script = {"title": "T", "scenes": [{"line": LINES[0]}, {"line": LINES[1]}]}
    data, scenes, raw, review = cartoon3d.visual_pass(load_config(), None, tmp_path, script, spans, 200, WORDS, clean, BOARD)
    used = [p.get("prefab") for p in scenes[1]["props"]]
    assert ("magnifier" in used) == (kept == "fixed")
    assert raw["scenes"][0] == BOARD["scenes"][0]                       # good scenes are never touched


def _mp4(path, black=False, seconds=3):
    v = "color=c=black:s=1080x1920:r=30" if black else "testsrc2=s=1080x1920:r=30"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"{v}:d={seconds}", "-f", "lavfi", "-i", f"sine=f=220:d={seconds}",
                    "-af", "volume=0.25", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def test_inspector_scores_honestly_and_rejects_black_video(tmp_path):
    _, _, _, data = compiled()
    words = [[{"word": "a", "start": 0.2, "end": 0.5}], [{"word": "b", "start": 1.5, "end": 2.6}]]
    rep = reel_qc.inspect_final(_mp4(tmp_path / "ok.mp4"), data, words, None, captions=False)
    assert rep["critical"] == [] and rep["partial"] and rep["categories"]["story"] is None and rep["categories"]["captions"] is None
    assert rep["categories"]["technical"] == 10 and 0 < rep["score"] <= 100
    md = reel_qc.report_markdown(rep, "T")
    assert "not inspected" in md and "Score" in md
    bad = reel_qc.inspect_final(_mp4(tmp_path / "black.mp4", black=True), data, words, None, captions=True)
    assert any("black frames" in c for c in bad["critical"]) and any("captions" in c for c in bad["critical"])
    assert bad["verdict"].startswith("REJECTED")


@pytest.mark.slow
def test_free_builder_with_visual_qc_end_to_end(tmp_state, monkeypatch, tmp_path):
    """Real render path: director draft, review, vision review on real stills, fix of the weak scene, re-check, full render,
    final inspection. Only the LLM is fake."""
    wav = tmp_path / "voice.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=180:d=4.2", "-ar", "24000", str(wav)], check=True)
    tl = [{"words": WORDS[0][:4]}, {"words": [dict(w, start=w["start"] - 1.0, end=w["end"] - 1.0) for w in WORDS[1][:5]]}]
    lines = [" ".join(w["word"] for w in t["words"]) for t in tl]
    draft = json.loads(json.dumps(BOARD))
    draft["scenes"][0]["props"][1]["cue"] = "briefcase"; draft["scenes"][0]["cast"][0]["react"]["cue"] = "opened"
    draft["scenes"][1]["cast"][0]["react"]["cue"] = "serial"
    fixed = json.loads(json.dumps(draft)); fixed["scenes"][1]["props"].append({"prefab": "magnifier", "at": "mid_right", "size": 1.4})
    v1 = {"scenes": [{"n": 1, "score": 8, "shows_line": True}, {"n": 2, "score": 4, "shows_line": False, "issue": "serial unreadable", "fix": "add magnifier"}],
          "storytelling": 7, "composition": 6, "assets": 7, "camera": 7, "continuity": 8, "summary": "scene 2 weak"}
    v2 = dict(v1, scenes=[{"n": 1, "score": 8, "shows_line": True}, {"n": 2, "score": 8, "shows_line": True}], composition=8, summary="fixed")
    srv = FakeLLM([(200, json.dumps(draft)), (200, json.dumps(draft)), (200, json.dumps(v1)), (200, json.dumps(fixed)), (200, json.dumps(v2))])
    try:
        cfg = cfg_for(srv.url, monkeypatch)
        script = {"title": "Serials", "mood": "tense", "scenes": [{"line": lines[0], "visual": "cash"}, {"line": lines[1], "visual": "bill"}]}
        out = cartoon3d.render_free(cfg, script, tl, wav, 4.2, tmp_path / "work")
        assert len(srv.seen) == 5
        assert any(isinstance(m["content"], list) for m in srv.seen[2]["messages"])            # the vision request carries the image
        assert "Weak scenes" in srv.seen[3]["messages"][-1]["content"] and "scene 2" in srv.seen[3]["messages"][-1]["content"]
    finally:
        srv.close()
    used = json.loads((tmp_path / "work" / "cartoon3d_work" / "storyboard.json").read_text())["used"]
    assert "magnifier" in [p.get("prefab") for p in used[1]["props"]]
    rep = json.loads((tmp_path / "work" / "cartoon3d_work" / "quality_report.json").read_text())
    assert rep["critical"] == [] and rep["categories"]["captions"] == 10 and rep["review"]["summary"] == "fixed" and rep["score"] >= 60
    got = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height,pix_fmt", "-of", "csv=p=0", str(out)],
                         capture_output=True, text=True).stdout.strip()
    assert got == "1080,1920,yuv420p"
