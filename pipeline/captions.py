"""Bold pop-in captions (ASS subtitles burned into the video by ffmpeg)."""
import re

from .common import hex_to_ass


def _t(sec):
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _clean(word):
    w = re.sub(r"[^\w'?!%$-]", "", word)
    return w.upper()


def build(cfg, script, timeline, total, workdir):
    c = cfg["captions"]
    W, H = cfg["video"]["width"], cfg["video"]["height"]
    white, yellow = hex_to_ass(c["color"]), hex_to_ass(c["highlight"])
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,{c['font']},{c['font_size']},{white},{white},&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,9,4,2,60,60,{c['position_from_bottom']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    n = max(1, int(c.get("words_per_chunk", 2)))
    chunks = []  # (start, text_with_tags)
    for sc, line in zip(script["scenes"], timeline):
        emph = sc.get("emphasis", "").lower().strip(".,!?")
        words = line["words"]
        i = 0
        while i < len(words):
            group = [words[i]]
            # end chunk early after punctuation or long words
            while (len(group) < n and i + len(group) < len(words)
                   and not re.search(r"[,.!?;:]$", group[-1]["word"])
                   and sum(len(g["word"]) for g in group) + len(words[i + len(group)]["word"]) <= 14):
                group.append(words[i + len(group)])
            parts = []
            for g in group:
                txt = _clean(g["word"])
                if not txt:
                    continue
                if emph and re.sub(r"[^\w']", "", g["word"].lower()) == re.sub(r"[^\w']", "", emph):
                    parts.append(f"{{\\c{yellow}}}{txt}{{\\c{white}}}")
                else:
                    parts.append(txt)
            if parts:
                chunks.append((group[0]["start"], " ".join(parts), line["end"]))
            i += len(group)
    events = []
    pop = r"{\fscx118\fscy118\t(0,90,\fscx100\fscy100)}"
    for j, (start, text, line_end) in enumerate(chunks):
        nxt = chunks[j + 1][0] if j + 1 < len(chunks) else total
        end = min(nxt, line_end + 0.35) if nxt - line_end > 0.5 else nxt
        events.append(f"Dialogue: 0,{_t(start)},{_t(end)},Pop,,0,0,0,,{pop}{text}")
    path = workdir / "captions.ass"
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return path, [c[0] for c in chunks]
