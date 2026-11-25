#!/usr/bin/env python3
"""git merge driver for data/*.json: Make and Post run at the same time and both save bot state.
Three-way merge of JSON: dicts key by key, lists of {"id": ...} by id, other lists as sets (adds + removals kept),
numbers that both sides changed add up (usage counters), any other clash takes the incoming side.
Usage (set by tools/save_state.sh): merge_state.py %O %A %B   -> result written to %A, exit 0.
"""
import json
import sys

GONE = object()


def merge(o, a, b):
    if a == b:
        return a
    if a == o:
        return b
    if b == o:
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        o = o if isinstance(o, dict) else {}
        out = {}
        for k in list(a) + [k for k in b if k not in a]:
            v = merge(o.get(k, GONE), a.get(k, GONE), b.get(k, GONE))
            if v is not GONE:
                out[k] = v
        return out
    if isinstance(a, list) and isinstance(b, list):
        o = o if isinstance(o, list) else []
        if all(isinstance(x, dict) and "id" in x for x in a + b):
            oi, bi = {x["id"]: x for x in o}, {x["id"]: x for x in b}
            out = []
            for x in a:
                if x["id"] in bi:
                    out.append(merge(oi.get(x["id"], GONE), x, bi[x["id"]]))
                elif x["id"] not in oi:
                    out.append(x)            # new on this side
            ai = {x["id"] for x in a}
            return out + [x for x in b if x["id"] not in ai and x["id"] not in oi]
        return [x for x in a if not (x in o and x not in b)] + [x for x in b if x not in a and x not in o]
    if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (o, a, b)):
        return a + b - o                     # both sides counted (freellm_usage)
    return b


def main(base, ours, theirs):
    load = lambda p: json.loads(open(p, encoding="utf-8").read() or "null")
    out = merge(load(base), load(ours), load(theirs))
    with open(ours, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    main(*sys.argv[1:4])
