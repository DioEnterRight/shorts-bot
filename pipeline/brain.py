"""Brain: Claude Code (your subscription) picks a topic and writes the script."""
import json
import re

from .common import ROOT, DATA, env, log, run

MOTIONS = {"punch_in", "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "shake"}
SFX = {"whoosh", "hit", "pop", "boing", "riser", "tick", "none"}


def score(v):
    """One number per video so Claude can see winners/losers."""
    m = v.get("metrics", {})
    views = m.get("ig_views", 0) + m.get("yt_views", 0)
    eng = m.get("ig_shares", 0) * 20 + m.get("ig_saves", 0) * 10 + m.get("ig_likes", 0) + m.get("yt_likes", 0)
    ret = m.get("yt_avg_view_pct", 0)
    return views + eng + ret * 5


def performance_summary(history):
    rated = [v for v in history["videos"] if v.get("metrics")]
    if len(rated) < 3:
        return "No data yet."
    rated.sort(key=score, reverse=True)

    def row(v):
        m = v["metrics"]
        return (f"- {v['topic']} | cat={v.get('category')} | hook={v.get('hook_type')} | "
                f"{v.get('duration', 0):.0f}s | IG views={m.get('ig_views', 0)} shares={m.get('ig_shares', 0)} "
                f"saves={m.get('ig_saves', 0)} avg_watch={m.get('ig_avg_watch_ms', 0)}ms | "
                f"YT views={m.get('yt_views', 0)} avg%={m.get('yt_avg_view_pct', 0)} | "
                f"first line: \"{v.get('hook_line', '')}\"")

    best = "\n".join(row(v) for v in rated[:5])
    worst = "\n".join(row(v) for v in rated[-5:]) if len(rated) > 5 else "(not enough yet)"
    return f"BEST:\n{best}\nWORST:\n{worst}"


def build_prompt(cfg, history):
    tpl = (ROOT / "prompts" / "brain.md").read_text(encoding="utf-8")
    target = cfg["video"]["target_seconds"]
    wps = 2.7 * cfg["voice"]["speed"]  # Kokoro speaks ~2.7 words/sec at speed 1.0
    topics = [v["topic"] for v in history["videos"]][-120:]
    playbook_path = DATA / "playbook.md"
    playbook = playbook_path.read_text(encoding="utf-8") if playbook_path.exists() else "(empty)"
    from .common import now_ist
    sunday = now_ist().weekday() == 6
    return tpl.format(
        target_seconds=target,
        min_words=int(target * wps * 0.85),
        max_words=int(target * wps * 1.1),
        performance=performance_summary(history),
        recent_topics="\n".join(f"- {t}" for t in topics) or "(none yet)",
        playbook=playbook,
        playbook_instruction=("Today is review day: in \"playbook_update\" write the FULL improved playbook "
                              "(max 25 bullet points) based on the data above." if sunday else
                              "Leave \"playbook_update\" as an empty string today."),
        playbook_field_hint="full new playbook text on review day, otherwise empty string",
        niche=cfg["channel"]["niche"].strip(),
    )


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("No JSON object in Claude's reply")
    return json.loads(text[start:end + 1])


def validate(s, cfg):
    scenes = s.get("scenes") or []
    if not (4 <= len(scenes) <= 12):
        raise ValueError(f"Bad scene count: {len(scenes)}")
    for sc in scenes:
        sc["line"] = sc.get("line", "").strip()
        sc["visual"] = sc.get("visual", "").strip()
        if not sc["line"] or not sc["visual"]:
            raise ValueError("Empty line or visual")
        if sc.get("motion") not in MOTIONS:
            sc["motion"] = "zoom_in"
        if sc.get("sfx") not in SFX:
            sc["sfx"] = "none"
        if sc.get("emphasis", "").lower() not in sc["line"].lower():
            sc["emphasis"] = ""
    words = sum(len(sc["line"].split()) for sc in scenes)
    if not (30 <= words <= 200):
        raise ValueError(f"Bad word count: {words}")
    for k in ("topic", "title", "description"):
        if not s.get(k):
            raise ValueError(f"Missing {k}")
    s["title"] = s["title"][:95]
    tags = [t if t.startswith("#") else "#" + t for t in s.get("hashtags", [])]
    s["hashtags"] = [re.sub(r"[^#\w]", "", t) for t in tags][: cfg["publish"]["hashtags_max"]]
    s.setdefault("category", "other")
    s.setdefault("hook_type", "other")
    s.setdefault("playbook_update", "")
    return s


def call_claude(prompt):
    env("CLAUDE_CODE_OAUTH_TOKEN", required=True)
    res = run(["claude", "-p", prompt, "--output-format", "json",
               "--allowedTools", "WebSearch,WebFetch", "--max-turns", "15"],
              capture=True, check=False)
    if res.returncode != 0:
        print(res.stdout[-3000:], res.stderr[-3000:])
        raise RuntimeError("Claude Code call failed (check CLAUDE_CODE_OAUTH_TOKEN or usage limits)")
    wrapper = json.loads(res.stdout)
    if wrapper.get("is_error"):
        raise RuntimeError(f"Claude returned an error: {wrapper.get('result', '')[:500]}")
    return wrapper.get("result", "")


def make_script(cfg, history, test=False):
    if test:
        log("Test mode: using sample script (no Claude call)")
        return validate(json.loads((ROOT / "prompts" / "sample_script.json").read_text()), cfg)
    prompt = build_prompt(cfg, history)
    last_err = None
    for attempt in range(1, 4):
        try:
            log(f"Asking Claude for today's script (attempt {attempt})")
            reply = call_claude(prompt if attempt == 1 else
                                prompt + f"\n\nYour previous reply was invalid ({last_err}). Reply with ONLY the JSON object.")
            script = validate(extract_json(reply), cfg)
            log(f"Topic: {script['topic']}")
            return script
        except Exception as e:  # noqa: BLE001
            last_err = str(e)[:200]
            log(f"Script attempt failed: {last_err}")
    raise RuntimeError(f"Claude could not produce a valid script: {last_err}")
