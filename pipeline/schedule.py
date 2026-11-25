"""Daily upload slots from config.yaml `schedule:` (India time). Pure functions, no I/O.

  schedule:
    - {time: "09:00", language: hi}
    - {time: "14:00", language: en}

Making: the daily Make run tops the queue up to one day of slots, per language, in slot order.
Posting: the Post workflow runs every 30 min; each run posts the earliest slot of today that is due and not done.
A video is tied to its slot (v["slot"] = "YYYY-MM-DD HH:MM") the moment it is picked, so retries never double-post.
"""
import datetime as dt
import re

LATE = dt.timedelta(hours=3)   # a slot can still be posted this long after its time (late Make run, GitHub delay)


def slots(cfg):
    """-> [(\"HH:MM\", language)] sorted by time. Fails fast on a typo."""
    out = []
    for i, s in enumerate(cfg.get("schedule") or []):
        t, lang = str(s.get("time", "")), s.get("language")
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t):
            raise ValueError(f"schedule line {i + 1}: time must look like \"09:00\" (24h, India time), got {t!r}")
        if lang not in cfg["languages"]["enabled"]:
            raise ValueError(f"schedule line {i + 1}: language must be one of {cfg['languages']['enabled']}, got {lang!r}")
        out.append((t, lang))
    if not out:
        raise ValueError("config.yaml needs at least one line under schedule:")
    return sorted(out)


def to_make(cfg, queued):
    """languages to make now (in slot order) so the queue holds one day of slots"""
    have = {}
    for v in queued:
        have[v.get("language", "en")] = have.get(v.get("language", "en"), 0) + 1
    out = []
    for _, lang in slots(cfg):
        if have.get(lang, 0) > 0:
            have[lang] -= 1
        else:
            out.append(lang)
    return out


def due(cfg, done, now):
    """-> (slot id, language) of the earliest slot today whose time has come (at most LATE ago) and that is not done,
    else None. done = slot ids already used ("YYYY-MM-DD HH:MM")."""
    day = now.strftime("%Y-%m-%d")
    for t, lang in slots(cfg):
        sid, start = f"{day} {t}", now.replace(hour=int(t[:2]), minute=int(t[3:]), second=0, microsecond=0)
        if start <= now < start + LATE and sid not in done:
            return sid, lang
    return None


def work_now(cfg, history, now):
    """True when a Post run has something to do: a half-posted video to finish, or a due slot."""
    if any(v.get("status") == "queued" and v.get("slot") for v in history["videos"]):
        return True
    done = {v.get("slot") for v in history["videos"]} | set(history.get("missed_slots", []))
    return due(cfg, done, now) is not None


if __name__ == "__main__":   # Post workflow gate: prints due=true|false (cheap: only pyyaml needed)
    import os
    from .common import load_config, load_history, now_ist
    cfg = load_config()
    go = not cfg.get("paused") and work_now(cfg, load_history(), now_ist())
    print(f"due={'true' if go else 'false'}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"due={'true' if go else 'false'}\n")
