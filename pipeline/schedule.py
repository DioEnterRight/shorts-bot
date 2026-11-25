"""Upload slots from config.yaml `schedule:` (India time). Pure functions, no I/O.

  schedule:
    every_minutes: 60            # one upload every 60 min = 24 a day
    first: "00:30"               # first upload of the day
    language: en                 # every upload is in this language...
    language_at: {"09:30": hi}   # ...except these times
    make_ahead: 2                # keep the next 2 uploads ready
    make_per_run: 1              # each (hourly) Make run makes at most this many

Making: each Make run makes the languages of the next `make_ahead` slots that no ready video covers yet.
Posting: the Post workflow runs every 30 min and posts the slot that is due (up to one slot interval late, max 3 h).
A video is tied to its slot (v["slot"] = "YYYY-MM-DD HH:MM") the moment it is picked, so retries never double-post.
"""
import datetime as dt
import re

TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def _hm(t, what):
    if not TIME.fullmatch(str(t)):
        raise ValueError(f"schedule {what}: time must look like \"09:30\" (24h, India time), got {t!r}")
    return int(t[:2]) * 60 + int(t[3:])


def settings(cfg):
    s = cfg.get("schedule")
    if not isinstance(s, dict):
        raise ValueError("config.yaml schedule: must be the every_minutes / first / language block (see GUIDE.md)")
    every = int(s.get("every_minutes", 60))
    if not 15 <= every <= 1440:
        raise ValueError("schedule every_minutes must be 15-1440")
    return s, every


def slots(cfg):
    """-> [(\"HH:MM\", language)] of one day, sorted. Fails fast on a typo."""
    s, every = settings(cfg)
    enabled = cfg["languages"]["enabled"]
    first = _hm(s.get("first", "00:30"), "first")
    lang = s.get("language", "en")
    special = {str(k): v for k, v in (s.get("language_at") or {}).items()}
    for t, l in [("language", lang)] + list(special.items()):
        if l not in enabled:
            raise ValueError(f"schedule {t}: language must be one of {enabled}, got {l!r}")
    out = []
    m = first % every
    while m < 1440:
        t = f"{m // 60:02d}:{m % 60:02d}"
        out.append((t, special.pop(t, lang)))
        m += every
    if special:
        raise ValueError(f"schedule language_at {sorted(special)}: not upload times (they are {first // 60:02d}:{first % 60:02d} + every {every} min)")
    return out


def late(cfg):
    """how late a slot may still be posted: one slot interval, at most 3 h"""
    return dt.timedelta(minutes=min(180, settings(cfg)[1]))


def upcoming(cfg, now, n):
    """the next n slots still ahead of now: [(slot id, language)]"""
    out, day = [], now.date()
    while len(out) < n:
        for t, lang in slots(cfg):
            start = dt.datetime.combine(day, dt.time(int(t[:2]), int(t[3:])), tzinfo=now.tzinfo)
            if start > now and len(out) < n:
                out.append((f"{day:%Y-%m-%d} {t}", lang))
        day += dt.timedelta(days=1)
    return out


def to_make(cfg, queued, now):
    """languages to make now: the next `make_ahead` slots, minus what ready videos already cover, at most `make_per_run`"""
    s, _ = settings(cfg)
    have = {}
    for v in queued:
        have[v.get("language", "en")] = have.get(v.get("language", "en"), 0) + 1
    need = []
    for _, lang in upcoming(cfg, now, int(s.get("make_ahead", 2))):
        if have.get(lang, 0) > 0:
            have[lang] -= 1
        else:
            need.append(lang)
    return need[:int(s.get("make_per_run", 1))]


def due(cfg, done, now):
    """-> (slot id, language) of the earliest slot whose time has come (at most late() ago) and that is not done, else
    None. done = slot ids already used ("YYYY-MM-DD HH:MM"). Looks at yesterday too (slots just after midnight)."""
    for day in (now.date() - dt.timedelta(days=1), now.date()):
        for t, lang in slots(cfg):
            start = dt.datetime.combine(day, dt.time(int(t[:2]), int(t[3:])), tzinfo=now.tzinfo)
            sid = f"{day:%Y-%m-%d} {t}"
            if start <= now < start + late(cfg) and sid not in done:
                return sid, lang
    return None


def work_now(cfg, history, now):
    """True when a Post run has something to do: a half-posted video to finish, or a due slot."""
    if any(v.get("status") == "queued" and v.get("slot") for v in history["videos"]):
        return True
    done = {v.get("slot") for v in history["videos"]} | set(history.get("missed_slots", []))
    return due(cfg, done, now) is not None


def make_now(cfg, history, now):
    """True when a Make run has a video to make"""
    return bool(to_make(cfg, [v for v in history["videos"] if v.get("status") == "queued"], now))


if __name__ == "__main__":   # workflow gates, cheap (only pyyaml): post -> due=true|false, make -> make=true|false stats=true|false
    import os
    import sys
    from .common import load_config, load_history, now_ist
    cfg, now = load_config(), now_ist()
    if sys.argv[1:] == ["make"]:
        out = {"make": not cfg.get("paused") and make_now(cfg, load_history(), now), "stats": now.hour in (4, 5)}
    else:
        out = {"due": not cfg.get("paused") and work_now(cfg, load_history(), now)}
    for k, v in out.items():
        print(f"{k}={'true' if v else 'false'}")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"{k}={'true' if v else 'false'}\n")
