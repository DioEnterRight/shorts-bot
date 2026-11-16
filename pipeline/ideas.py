"""IDEA ENGINE: research -> several candidate ideas -> drop near-duplicates -> pick the best.

Near-duplicates are caught locally (no API) by comparing every idea's plain-English core
question ("canonical_en", always English so a Hindi idea is compared with English ones):
  score = max(content-word overlap, character-trigram cosine)
Content words are lower-cased, stop-words removed, lightly stemmed and mapped through a small
synonym table ("tummy" -> "stomach"), so "Why does your stomach growl?" and
"What makes your tummy rumble when hungry" are recognised as the same idea.

data/ideas.json keeps every idea the bot picked (versioned), so history survives forever even
after videos are cleaned up.
"""
import datetime as dt
import json
import math
import re
from collections import Counter

from .common import DATA, ROOT, log, now_ist, read_json, write_json

PATH = DATA / "ideas.json"
VERSION = 1

STOP = set("""a an the of to in on for at by with from into about over under is are was were be been being am do does
did doing have has had having it its this that these those there here what why how when where which who whom whose
you your yours we our us i me my he she they them their his her him can could would should will shall may might must
if then than so very really just even actually ever never not no yes and or but as up down out off again more most
some any all each every one get gets got getting make makes made making happen happens happened happening thing things
really much many way ways like""".split())

SYNONYMS = {
    "tummy": "stomach", "belly": "stomach", "gut": "stomach", "rumble": "growl", "rumbling": "growl",
    "growling": "growl", "hungry": "hunger", "starving": "hunger", "brains": "brain", "mind": "brain",
    "sneezing": "sneeze", "yawning": "yawn", "hiccup": "hiccups", "goose": "goosebumps",
    "bumps": "goosebumps", "skin": "skin", "earth": "planet", "world": "planet", "sleeping": "sleep",
    "asleep": "sleep", "dreams": "dream", "dreaming": "dream", "cold": "cold", "freeze": "freeze",
    "frozen": "freeze", "freezing": "freeze", "wrinkly": "wrinkle", "prune": "wrinkle", "pruney": "wrinkle",
    "crying": "cry", "tears": "cry", "eyes": "eye", "kids": "child", "children": "child", "people": "human",
    "humans": "human", "body": "body", "bodies": "body",
}


def _stem(w):
    for suf in ("ing", "ies", "es", "ed", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def content_words(text):
    out = set()
    for w in re.findall(r"[a-z]+", (text or "").lower()):
        if w in STOP or len(w) < 3:
            continue
        w = SYNONYMS.get(w, w)
        out.add(SYNONYMS.get(_stem(w), _stem(w)))
    return out


def _trigrams(text):
    t = " ".join(sorted(content_words(text)))
    t = f"  {t}  "
    return Counter(t[i:i + 3] for i in range(len(t) - 2))


def similarity(a, b):
    """0..1 — how much two ideas are the same idea."""
    wa, wb = content_words(a), content_words(b)
    if not wa or not wb:
        return 0.0
    overlap = len(wa & wb) / min(len(wa), len(wb))   # containment: a reworded subset still counts
    jacc = len(wa & wb) / len(wa | wb)
    ta, tb = _trigrams(a), _trigrams(b)
    dot = sum(ta[k] * tb[k] for k in ta)
    cos = dot / (math.sqrt(sum(v * v for v in ta.values())) * math.sqrt(sum(v * v for v in tb.values())) or 1)
    return max(0.5 * overlap + 0.5 * jacc, cos)


# ---------------- ledger ----------------
def load():
    led = read_json(PATH, {})
    led.setdefault("version", VERSION)
    led.setdefault("ideas", [])
    return led


def save(led):
    led["version"] = VERSION
    write_json(PATH, led)


def past_ideas(history, ledger, language=None, across_languages=True):
    """Every earlier idea as (language, text) — ledger entries plus older videos' topics/titles."""
    out = [(i.get("language", "en"), i["canonical_en"]) for i in ledger["ideas"] if i.get("canonical_en")]
    for v in history["videos"]:
        if v.get("status") == "discarded":
            continue
        for key in ("canonical_en", "topic"):
            if v.get(key):
                out.append((v.get("language", "en"), v[key]))
    if not across_languages and language:
        out = [x for x in out if x[0] == language]
    return [t for _, t in out]


def is_duplicate(text, past, threshold):
    best = max(((similarity(text, p), p) for p in past), default=(0.0, None))
    return best[0] >= threshold, best


def rank_key(idea):
    s = idea.get("scores") or {}
    vals = [float(s.get(k, 5)) for k in ("curiosity", "originality", "visual", "clarity")]
    return sum(vals) + 0.5 * float(s.get("originality", 5))


def choose(candidates, past, threshold):
    """Returns (best idea or None, rejected [(idea, reason)])."""
    kept, rejected = [], []
    for idea in candidates:
        text = idea.get("canonical_en", "").strip()
        if not text or not idea.get("hook"):
            rejected.append((idea, "incomplete"))
            continue
        dup, (score, match) = is_duplicate(text, past + [k["canonical_en"] for k in kept], threshold)
        if dup:
            rejected.append((idea, f"too close ({score:.2f}) to: {match}"))
            continue
        kept.append(idea)
    kept.sort(key=rank_key, reverse=True)
    return (kept[0] if kept else None), rejected


def record(ledger, idea, language, theme, video_id, status="produced"):
    ledger["ideas"].append({
        "canonical_en": idea["canonical_en"], "question": idea.get("question"), "hook": idea.get("hook"),
        "angle": idea.get("angle"), "language": language, "theme": theme, "video_id": video_id,
        "status": status, "created": now_ist().isoformat(timespec="minutes")})


# ---------------- Claude call ----------------
def build_prompt(cfg, theme, lp, past, performance):
    tpl = (ROOT / "prompts" / "ideas.md").read_text(encoding="utf-8")
    recent = past[-150:]
    return tpl.format(
        count=int(cfg.get("ideas", {}).get("candidates", 8)),
        theme_name=theme, theme_guidance=cfg["themes"][theme]["guidance"].strip(),
        language_name=lp["name"], niche=cfg["channel"]["niche"].strip(),
        today=dt.date.today().isoformat(),
        avoid_list="\n".join(f"- {t}" for t in recent) or "(nothing yet)",
        performance=performance)


def generate(cfg, history, theme, lp, performance, call_claude, extract_json):
    """Ask Claude for candidates, drop duplicates, return the best idea."""
    icfg = cfg.get("ideas", {})
    threshold = float(icfg.get("similarity_threshold", 0.5))
    ledger = load()
    past = past_ideas(history, ledger, lp["code"], icfg.get("dedupe_across_languages", True))
    prompt = build_prompt(cfg, theme, lp, past, performance)
    rejected_all = []
    for attempt in range(1, 3):
        log(f"Brainstorming ideas ({theme}, {lp['code']}) attempt {attempt}")
        extra = ""
        if rejected_all:
            extra = ("\n\nThese ideas were rejected as repeats or incomplete; pitch completely different ones:\n"
                     + "\n".join(f"- {i.get('canonical_en', '?')} ({why})" for i, why in rejected_all))
        try:
            reply = extract_json(call_claude(prompt + extra))
        except (ValueError, json.JSONDecodeError) as e:
            log(f"  Claude's idea reply was not valid JSON ({str(e)[:80]}); asking again", "WARN")
            rejected_all.append(({"canonical_en": "(unreadable reply)"}, str(e)[:100]))
            continue
        best, rejected = choose(reply.get("ideas", []), past, threshold)
        for idea, why in rejected:
            log(f"  rejected: {idea.get('canonical_en', '?')} -> {why}")
        rejected_all += rejected
        if best:
            log(f"Idea: {best['canonical_en']}  (angle: {best.get('angle', '')[:80]})")
            return best
    raise RuntimeError("No original idea survived the duplicate filter")
