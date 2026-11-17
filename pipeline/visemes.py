"""Mouth shapes for the mascot from word timings (clean-room, no external aligner).

Each word's letters are grouped into sound units and spread across the word's spoken time.
Shapes follow the Preston Blair set (toon2d maps them to open / mid / o / closed mouths):
  X rest/closed, A m/b/p, B most consonants, C e/i, D a (wide), E o, F u/oo, G f/v, H l/th.
The mouth closes (X) in any gap longer than GAP seconds, every shape holds at least MIN_HOLD
frames, and identical neighbours merge - so the guy talks like he is explaining, not yapping.
Works for English and Devanagari (Hindi/Hinglish).
"""
import re

GAP = 0.12
MIN_HOLD = 3   # frames

LATIN = [  # (regex, shape) tried in order on the lowercase word
    (r"oo|ou|ew|w|u", "F"), (r"o", "E"), (r"a", "D"), (r"ee|ea|e|i|y", "C"),
    (r"th|l", "H"), (r"ph|f|v", "G"), (r"m|b|p", "A"), (r"[a-z]", "B"),
]
DEV = {}
for ch in "आाऔौअ": DEV[ch] = "D"
for ch in "इईएऐिीेै": DEV[ch] = "C"
for ch in "ओो": DEV[ch] = "E"
for ch in "उऊुू": DEV[ch] = "F"
for ch in "मबपभ": DEV[ch] = "A"
for ch in "फव": DEV[ch] = "G"
for ch in "लथ": DEV[ch] = "H"


def word_units(word):
    """Sound units of one word -> list of shapes (consonant + vowel clusters)."""
    w = word.lower()
    if any("ऀ" <= ch <= "ॿ" for ch in w):
        out = []
        for ch in w:
            if ch in DEV:
                out.append(DEV[ch])
            elif "क" <= ch <= "ह":        # other consonants (inherent 'a' -> wide-ish)
                out.append("B")
            # halant, nukta, anusvara etc. add no new mouth shape
        return out or ["B"]
    w = re.sub(r"[^a-z]", "", w)
    out, i = [], 0
    while i < len(w):
        for pat, shape in LATIN:
            m = re.match(pat, w[i:])
            if m:
                out.append(shape)
                i += len(m.group(0))
                break
        else:
            i += 1
    # silent-ish trailing 'e' and doubled consonants read as one unit
    return [s for j, s in enumerate(out) if j == 0 or not (s == "B" and out[j - 1] == "B")] or ["B"]


def track(timeline, fps):
    """Viseme change points [[frame, shape], ...] for the whole video (global frames)."""
    events = [(0, "X")]
    words = [w for line in timeline for w in line["words"]]
    for k, w in enumerate(words):
        units = word_units(w["word"])
        a, b = w["start"], max(w["end"], w["start"] + 0.06)
        step = (b - a) / len(units)
        for j, shape in enumerate(units):
            events.append((round((a + j * step) * fps), shape))
        nxt = words[k + 1]["start"] if k + 1 < len(words) else None
        if nxt is None or nxt - b > GAP:
            events.append((round(b * fps), "X"))
    events.sort(key=lambda e: e[0])
    out = []
    for f, shape in events:                  # enforce min hold and merge repeats
        if out and shape == out[-1][1]:
            continue
        if out and f - out[-1][0] < MIN_HOLD:
            if shape == "X":                 # close a little later instead of skipping the close
                out.append([out[-1][0] + MIN_HOLD, "X"])
            else:                            # too fast to show: replace the previous shape
                out[-1][1] = shape
                if len(out) > 1 and out[-2][1] == shape:
                    out.pop()
            continue
        out.append([f, shape])
    return out
