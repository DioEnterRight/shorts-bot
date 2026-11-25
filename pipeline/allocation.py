"""Decides WHICH theme the next video gets (languages come from config.yaml `schedule:`). Pure functions, no I/O.

Picking is deterministic (no dice): whichever theme is furthest behind its target share in the recent sequence
goes next, and a theme missing from the last ceil(1/floor) videos is forced.
"""
import math


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
