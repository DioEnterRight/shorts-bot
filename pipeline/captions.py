"""Bold pop-in captions (ASS subtitles burned into the video by ffmpeg).

Language aware:
  - English: Anton, UPPERCASE.
  - Hindi: Noto Sans Devanagari (needs libass + HarfBuzz shaping, which Ubuntu's ffmpeg has);
    English words inside a Hindi line switch to Noto Sans so they render too.
Every chunk is measured with the real font and shrunk if it would be wider than the safe area.
"""
import re
from functools import lru_cache

from PIL import ImageFont

from .common import ROOT, hex_to_ass, is_wordchar, norm_text
from .languages import is_latin_word

FONTS = ROOT / "assets" / "fonts"
KEEP_PUNCT = set("'?!%$-")


def _t(sec):
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def clean_word(word, uppercase):
    """Keep letters, digits, combining marks (Devanagari matras/virama/nukta) and a little punctuation."""
    w = "".join(ch for ch in word if is_wordchar(ch) or ch in KEEP_PUNCT)
    return w.upper() if uppercase else w


@lru_cache(maxsize=8)
def _font(filename, size):
    return ImageFont.truetype(str(FONTS / filename), size)


def _font_for(word, lp):
    if lp.get("caption_latin_font_file") and is_latin_word(word):
        return lp["caption_latin_font"], lp["caption_latin_font_file"]
    return lp["caption_font"], lp["caption_font_file"]


def text_width(words, lp, size):
    space = _font(lp["caption_font_file"], size).getlength(" ")
    return sum(_font(_font_for(w, lp)[1], size).getlength(w) for w in words) + space * (len(words) - 1)


def chunk_words(words, n, lp, size, max_width):
    """Group words into caption chunks: up to n words, break after punctuation, never too wide."""
    chunks, i = [], 0
    while i < len(words):
        group = [words[i]]
        while (len(group) < n and i + len(group) < len(words)
               and not re.search(r"[,.!?;:।]$", group[-1]["word"])):
            cand = group + [words[i + len(group)]]
            if text_width([clean_word(g["word"], lp["caption_uppercase"]) for g in cand], lp, size) > max_width:
                break
            group = cand
        chunks.append(group)
        i += len(group)
    return chunks


def build(cfg, script, timeline, total, lp, workdir):
    c = cfg["captions"]
    W, H = cfg["video"]["width"], cfg["video"]["height"]
    size = int(lp["caption_font_size"])
    max_width = int(c.get("max_width", W - 160))
    white, yellow = hex_to_ass(c["color"]), hex_to_ass(c["highlight"])
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,{lp['caption_font']},{size},{white},{white},&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,9,4,2,60,60,{c['position_from_bottom']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    n = max(1, int(c.get("words_per_chunk", 2)))
    chunks = []  # (start, text_with_tags, line_end, scale)
    for sc, line in zip(script["scenes"], timeline):
        emph = norm_text(sc.get("emphasis", ""))
        for group in chunk_words(line["words"], n, lp, size, max_width):
            parts, plain = [], []
            for g in group:
                txt = clean_word(g["word"], lp["caption_uppercase"])
                if not txt:
                    continue
                plain.append(txt)
                fontname = _font_for(txt, lp)[0]
                if fontname != lp["caption_font"]:
                    txt = f"{{\\fn{fontname}}}{txt}{{\\fn{lp['caption_font']}}}"
                if emph and norm_text(g["word"]) == emph:
                    txt = f"{{\\c{yellow}}}{txt}{{\\c{white}}}"
                parts.append(txt)
            if parts:
                scale = min(1.0, max_width / max(1.0, text_width(plain, lp, size)))
                chunks.append((group[0]["start"], " ".join(parts), line["end"], scale))
    events = []
    for j, (start, text, line_end, scale) in enumerate(chunks):
        nxt = chunks[j + 1][0] if j + 1 < len(chunks) else total
        end = min(nxt, line_end + 0.35) if nxt - line_end > 0.5 else nxt
        s100, s118 = round(100 * scale), round(118 * scale)
        pop = f"{{\\fscx{s118}\\fscy{s118}\\t(0,90,\\fscx{s100}\\fscy{s100})}}"
        events.append(f"Dialogue: 0,{_t(start)},{_t(end)},Pop,,0,0,0,,{pop}{text}")
    path = workdir / "captions.ass"
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return path, [c[0] for c in chunks]
