"""Brain: Claude Code (your subscription) writes the script + storyboard for the chosen idea."""
import json
import re

from . import languages
from .common import DATA, ROOT, env, load_config, log, norm_text, now_ist, run

MIN_SCENES, MAX_SCENES = 6, 16


# ---------------- performance summary (from data/analytics.json) ----------------
def score(rec):
    """One number per video so Claude can see winners/losers."""
    m = rec.get("metrics", {})
    views = m.get("ig_views", 0) + m.get("yt_views", 0)
    eng = m.get("ig_shares", 0) * 20 + m.get("ig_saves", 0) * 10 + m.get("ig_likes", 0) + m.get("yt_likes", 0)
    return views + eng + m.get("yt_avg_view_pct", 0) * 5


def performance_summary(analytics, language=None):
    rated = [r for r in analytics.get("videos", {}).values() if r.get("metrics")]
    if language:
        same = [r for r in rated if r.get("language") == language]
        rated = same if len(same) >= 3 else rated
    if len(rated) < 3:
        return "No data yet."
    rated.sort(key=score, reverse=True)

    def row(r):
        m = r["metrics"]
        return (f"- [{r.get('language', 'en')}/{r.get('theme', 'explainer')}] {r.get('topic')} | "
                f"hook={r.get('hook_type')} | {r.get('duration') or 0:.0f}s | IG views={m.get('ig_views', 0)} "
                f"shares={m.get('ig_shares', 0)} saves={m.get('ig_saves', 0)} "
                f"avg_watch={m.get('ig_avg_watch_ms', 0)}ms | YT views={m.get('yt_views', 0)} "
                f"avg%={m.get('yt_avg_view_pct', 0)} | first line: \"{r.get('hook_line', '')}\"")

    best = "\n".join(row(r) for r in rated[:5])
    worst = "\n".join(row(r) for r in rated[-5:]) if len(rated) > 5 else "(not enough yet)"
    return f"BEST:\n{best}\nWORST:\n{worst}"


# ---------------- Claude ----------------
def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("No JSON object in Claude's reply")
    return json.loads(text[start:end + 1])


def claude_model_args(effort=None, model=None):
    """Model flags from config.yaml `claude:` (pinned so runs don't depend on the account default)."""
    cc = load_config().get("claude", {})
    args = ["--model", model or cc.get("model", "opus")]
    if cc.get("fallback_model"):
        args += ["--fallback-model", cc["fallback_model"]]
    if effort or cc.get("effort"):
        args += ["--effort", effort or cc["effort"]]
    return args


def call_claude(prompt, tools="WebSearch,WebFetch", max_turns=20, effort=None, cwd=None, timeout=None, model=None):
    env("CLAUDE_CODE_OAUTH_TOKEN", required=True)
    res = run(["claude", "-p", prompt, "--output-format", "json", *claude_model_args(effort, model),
               "--allowedTools", tools, "--max-turns", str(max_turns)],
              capture=True, check=False, cwd=cwd, timeout=timeout)
    if res.returncode != 0:
        print(res.stdout[-3000:], res.stderr[-3000:])
        raise RuntimeError("Claude Code call failed (check CLAUDE_CODE_OAUTH_TOKEN or usage limits)")
    wrapper = json.loads(res.stdout)
    if wrapper.get("is_error"):
        raise RuntimeError(f"Claude returned an error: {wrapper.get('result', '')[:500]}")
    return wrapper.get("result", "")


# ---------------- validation ----------------
def word_budget(cfg, lp):
    target = cfg["video"]["target_seconds"]
    wps = float(lp.get("words_per_second", 2.7)) * float(lp["speed"])
    return int(target * wps * 0.8), int(target * wps * 1.15)


def validate(s, cfg, lp, theme="explainer"):
    """Normalise a script and reject ones that would make a bad video. Raises ValueError."""
    scenes = s.get("scenes") or []
    if not (MIN_SCENES <= len(scenes) <= MAX_SCENES):
        raise ValueError(f"Bad scene count: {len(scenes)} (want {MIN_SCENES}-{MAX_SCENES})")
    for i, sc in enumerate(scenes):
        sc["line"] = (sc.get("line") or "").strip()
        sc["visual"] = (sc.get("visual") or "").strip()
        if not sc["line"] or not sc["visual"]:
            raise ValueError(f"Scene {i + 1}: empty line or visual")
        sc["overlay"] = " ".join((sc.get("overlay") or "").split()[:3])[:28]
        if norm_text(sc.get("emphasis", "")) not in {norm_text(w) for w in sc["line"].split()}:
            sc["emphasis"] = ""
        for k in [k for k in sc if k not in ("line", "visual", "overlay", "emphasis")]:
            del sc[k]
    visuals = [norm_text(sc["visual"]) for sc in scenes]
    if any(a == b for a, b in zip(visuals, visuals[1:])):
        raise ValueError("Two consecutive scenes have the same visual")
    overlays = [sc for sc in scenes if sc["overlay"]]
    for sc in overlays[4:]:
        sc["overlay"] = ""
    text = " ".join(sc["line"] for sc in scenes)
    if not languages.script_ok(text, lp["code"]):
        raise ValueError(f"Narration is not in {lp['name']}")
    words = len(text.split())
    lo, hi = word_budget(cfg, lp)
    if not (min(30, lo) <= words <= max(200, hi)):
        raise ValueError(f"Bad word count: {words}")
    for k in ("topic", "title", "description"):
        if not s.get(k):
            raise ValueError(f"Missing {k}")
    s["title"] = s["title"][:95]
    tags = [t if t.startswith("#") else "#" + t for t in s.get("hashtags", [])]
    s["hashtags"] = [re.sub(r"[^#\w]", "", t) for t in tags][: cfg["publish"]["hashtags_max"]]
    s.setdefault("canonical_en", s["topic"])
    s.setdefault("category", "other")
    s.setdefault("hook_type", "other")
    s.setdefault("playbook_update", "")
    s["language"], s["theme"] = lp["code"], theme
    return s


# ---------------- script ----------------
def build_prompt(cfg, idea, lp, theme, performance):
    tpl = (ROOT / "prompts" / "script.md").read_text(encoding="utf-8")
    lo, hi = word_budget(cfg, lp)
    playbook_path = DATA / "playbook.md"
    playbook = playbook_path.read_text(encoding="utf-8") if playbook_path.exists() else "(empty)"
    sunday = now_ist().weekday() == 6
    shown = {k: idea.get(k) for k in ("canonical_en", "question", "hook", "angle", "why_care", "payoff",
                                      "visual_moments", "research_basis")}
    return tpl.format(
        idea=json.dumps(shown, ensure_ascii=False, indent=2),
        theme_name=theme, theme_guidance=cfg["themes"][theme]["guidance"].strip(),
        language_rules=languages.prompt_text(lp),
        target_seconds=cfg["video"]["target_seconds"], min_words=lo, max_words=hi,
        min_scenes=8, max_scenes=13,
        performance=performance, playbook=playbook,
        playbook_instruction=("Today is review day: in \"playbook_update\" write the FULL improved playbook "
                              "(max 25 bullet points, in English) based on the data above." if sunday else
                              "Leave \"playbook_update\" as an empty string today."),
        playbook_field_hint="full new playbook text on review day, otherwise empty string",
        category=idea.get("category", "other"), hook_type=idea.get("hook_type", "why"),
    )


def sample_script(cfg, lp, theme="explainer"):
    path = ROOT / "prompts" / f"sample_script_{lp['code']}.json"
    log(f"Test mode: using {path.name} (no Claude call)")
    return validate(json.loads(path.read_text(encoding="utf-8")), cfg, lp, theme)


def write_script(cfg, idea, lp, theme, performance):
    prompt = build_prompt(cfg, idea, lp, theme, performance)
    last_err = None
    for attempt in range(1, 4):
        try:
            log(f"Asking Claude for the script (attempt {attempt})")
            reply = call_claude(prompt if attempt == 1 else
                                prompt + f"\n\nYour previous reply was invalid ({last_err}). Reply with ONLY the JSON object.")
            script = validate(extract_json(reply), cfg, lp, theme)
            script["canonical_en"] = idea.get("canonical_en", script["canonical_en"])
            log(f"Topic: {script['topic']}  ({len(script['scenes'])} scenes)")
            return script
        except Exception as e:  # noqa: BLE001
            last_err = str(e)[:200]
            log(f"Script attempt failed: {last_err}", "WARN")
    raise RuntimeError(f"Claude could not produce a valid script: {last_err}")
