"""Decides WHICH language and WHICH theme the next video gets. Pure functions, no I/O.

Language shares come from recent performance (data/analytics.json):
  1. each published video gets a value = log(age-adjusted views), per platform, averaged
     - log() stops one viral video from dominating, the age factor makes a 2-day-old
       video comparable with a 10-day-old one; day-7 snapshots are preferred when they exist
  2. a language's score is the MEDIAN value of its recent videos (robust to outliers)
  3. scores -> shares with a softmax, shrunk toward equal while there is little data,
     smoothed against yesterday's shares, then clamped to [floor, 1 - floor]
  4. too little data -> equal shares

Picking is deterministic (no dice): whichever option is furthest behind its target share in
the recent sequence goes next, and any option missing from the last ceil(1/floor) videos is
forced, so the weaker language always keeps getting published.
"""
import math

DEFAULTS = {"floor": 0.2, "min_videos": 4, "min_age_days": 2, "window_days": 30,
            "sensitivity": 1.5, "confidence_k": 6, "smoothing": 0.35, "half_life_days": 2.5}


def settings(cfg):
    return {**DEFAULTS, **(cfg.get("allocation") or {})}


def maturity(age_days, half_life):
    """Rough share of a Short's eventual views it has after age_days (most views come early)."""
    return 1 - math.exp(-max(age_days, 0) / half_life)


def video_value(rec, age_days, s):
    """log of age-adjusted views, averaged over the platforms that have numbers. None if not usable."""
    if age_days < s["min_age_days"]:
        return None
    snap = rec.get("views_day7") if age_days >= 7 else None
    views = snap or rec.get("views") or {}
    age = 7 if snap else age_days
    vals = [math.log1p(v / maturity(age, s["half_life_days"]))
            for k, v in views.items() if k in ("yt", "ig") and isinstance(v, (int, float)) and v >= 0]
    return sum(vals) / len(vals) if vals else None


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def clamp_shares(shares, floor):
    """Every option gets at least `floor`; the rest is shared in proportion. Sums to 1."""
    keys = list(shares)
    floor = min(floor, 1 / len(keys))
    fixed = {}
    while True:
        free = [k for k in keys if k not in fixed]
        budget = 1 - sum(fixed.values())
        tot = sum(shares[k] for k in free) or 1
        out = {k: budget * shares[k] / tot for k in free}
        low = [k for k in free if out[k] < floor]
        if not low:
            return {**fixed, **out}
        for k in low:
            fixed[k] = floor


def language_shares(records, languages, s, previous=None):
    """records: [{"language", "age_days", "views": {"yt": n, "ig": n}, "views_day7": {...}?}].
    Returns (shares, diagnostics)."""
    equal = {lang: 1 / len(languages) for lang in languages}
    if len(languages) == 1:
        return equal, {"reason": "single language"}
    vals = {lang: [] for lang in languages}
    for r in records:
        if r.get("language") in vals and r["age_days"] <= s["window_days"]:
            v = video_value(r, r["age_days"], s)
            if v is not None:
                vals[r["language"]].append(v)
    counts = {k: len(v) for k, v in vals.items()}
    if min(counts.values()) < s["min_videos"]:
        return equal, {"reason": f"not enough data yet (need {s['min_videos']} per language)", "counts": counts}
    scores = {k: _median(v) for k, v in vals.items()}
    top = max(scores.values())
    raw = {k: math.exp(s["sensitivity"] * (sc - top)) for k, sc in scores.items()}
    tot = sum(raw.values())
    raw = {k: v / tot for k, v in raw.items()}
    conf = min(counts.values()) / (min(counts.values()) + s["confidence_k"])
    target = {k: equal[k] + conf * (raw[k] - equal[k]) for k in languages}
    if previous and set(previous) == set(languages):
        target = {k: previous[k] + s["smoothing"] * (target[k] - previous[k]) for k in languages}
    shares = clamp_shares(target, s["floor"])
    return shares, {"reason": "performance", "counts": counts, "median_log_views": scores,
                    "confidence": round(conf, 3)}


def pick(shares, recent, floor=None, window=10):
    """Deterministic choice. recent = past picks, oldest first."""
    order = list(shares)
    if floor:
        horizon = math.ceil(1 / floor)
        tail = recent[-(horizon - 1):] if horizon > 1 else []
        missing = [k for k in order if shares[k] > 0 and k not in tail]
        if missing and len(recent) >= horizon - 1:
            # the one absent the longest goes first
            def last_seen(k):
                return max([i for i, x in enumerate(recent) if x == k], default=-1)
            return min(missing, key=lambda k: (last_seen(k), order.index(k)))
    win = recent[-window:]
    n = len(win)
    deficit = {k: shares[k] * (n + 1) - win.count(k) for k in order}
    return max(order, key=lambda k: (round(deficit[k], 9), shares[k], -order.index(k)))


# ---------------- weekly quota (config allocation.mode: weekly) ----------------
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def weekly_pick(made, now, main, quota, day):
    """Language for the next video under a fixed weekly plan.

    made: [(created datetime, language)] of videos already made (any status except discarded).
    main: the default language (English). quota: {"hi": 1} = videos per Mon-Sun week (IST).
    day: earliest weekday for the quota videos ("wed"), so they don't all land on Monday.
    A quota language is picked once its day has come and it is still short this week;
    if several are short, the one furthest behind goes first.
    """
    week_start = (now - _days(now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    this_week = [lang for t, lang in made if t >= week_start]
    if now.weekday() < DAYS.index(day):
        return main
    short = {lang: n - this_week.count(lang) for lang, n in quota.items() if this_week.count(lang) < n}
    if not short:
        return main
    return max(sorted(short), key=lambda lang: short[lang])


def _days(n):
    import datetime as dt
    return dt.timedelta(days=n)
