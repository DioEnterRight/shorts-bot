"""Bespoke scenes: Claude (Opus) writes new Remotion code for every scene of every video.

Flow (inside remotion_render.render, style "bespoke"):
  1. brief.json: each scene's line, word frames, hints, duration -> remotion/src/generated/
  2. Claude Code writes src/generated/SceneN.tsx using only the design kit (remotion/src/kit),
     typechecks, renders a contact sheet (tools/sheet.mjs), looks at it and fixes (max 2 rounds).
  3. Hard gates here, whatever Claude says: allowed imports, banned patterns, tsc, and a crash test
     render of every scene. A scene that fails any gate falls back to the cartoon template, so a
     video always ships.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import brain
from .common import ROOT, log

REMOTION = ROOT / "remotion"
GEN = REMOTION / "src" / "generated"
SKILL = ROOT / ".claude" / "skills" / "shortsbot-scene-kit" / "SKILL.md"
INDEX_HEADER = '''import type React from "react";

// Written per video by pipeline/scenegen.py (Claude). Keys are scene component names ("Scene1"...).
// Empty in git: any scene without generated code falls back to the cartoon template.
'''
ALLOWED_IMPORTS = {"react", "remotion", "../kit"}
BANNED = [r"Math\.random", r"\bDate\b", r"setTimeout", r"setInterval", r"requestAnimationFrame",
          r"\btransition\s*:", r"\banimation\s*:", r"@keyframes", r"\bfetch\s*\(", r"useEffect",
          r"dangerouslySetInnerHTML", r"\beval\s*\(", r"\brequire\s*\(", r"process\.env", r"\bimport\s*\("]


def reset():
    """Remove any generated scenes and write an empty registry."""
    for p in GEN.glob("Scene*.tsx"):
        p.unlink()
    for p in ("brief.json",):
        (GEN / p).unlink(missing_ok=True)
    write_index([])


def write_index(names):
    lines = [INDEX_HEADER] + [f'import {n} from "./{n}";' for n in names]
    body = ", ".join(names)
    lines.append(f"\nexport const GENERATED: Record<string, React.FC> = {{ {body} }};\n")
    (GEN / "index.ts").write_text("\n".join(lines), encoding="utf-8")


def brief(script, props):
    fps = props["fps"]
    scenes, start = [], 0
    for i, (sc, ps) in enumerate(zip(script["scenes"], props["scenes"])):
        if i:
            start += props["scenes"][i - 1]["durationInFrames"] - ps["transitionFrames"]
        words = [{"text": c["text"].strip(), "from": round(c["startMs"] / 1000 * fps) - start,
                  "to": round(c["endMs"] / 1000 * fps) - start} for c in props["captions"]]
        words = [w for w in words if 0 <= w["from"] < ps["durationInFrames"]]
        scenes.append({
            "component": f"Scene{i + 1}", "durationInFrames": ps["durationInFrames"],
            "preFrames": ps["transitionFrames"] // 2, "line": sc["line"], "words": words,
            "emphasis": sc.get("emphasis", ""), "overlay_label": sc.get("overlay", ""),
            "storyboard_hint": sc.get("visual", ""), "shot": sc.get("shot", ""),
        })
    return {"topic": script.get("topic"), "title": script.get("title"), "language": script["language"],
            "fps": fps, "scenes": scenes}


def _prompt(b, props_path, public_dir, rounds):
    kit = SKILL.read_text(encoding="utf-8").split("---", 2)[2]
    return f"""You are the motion designer of a faceless explainer channel (YouTube Shorts / Reels).
Write a NEW animated scene for every scene of today's video, in this Remotion project
(current directory). Viewers must understand the idea from the picture alone, and this video
must look different from a template: design each scene for its own idea.

{kit}

## Today's video (also in src/generated/brief.json)
```json
{json.dumps(b, ensure_ascii=False, indent=1)}
```

## Do this
1. Plan in one line per scene: the single idea, the visual metaphor, what moves on which word.
2. Write src/generated/Scene1.tsx ... Scene{len(b['scenes'])}.tsx (default export each). Do not edit
   anything outside src/generated/. Do not write src/generated/index.ts (the bot writes it).
3. Review loop, max {rounds} rounds:
   `npx tsc --noEmit`, then
   `node tools/sheet.mjs --props {props_path} --public-dir {public_dir}`, then Read out/sheet.png and
   out/sheet.json. Fix the worst problems. Stop after {rounds} rounds.
When done, reply with one line per scene: what it shows."""


def _gate_file(path):
    src = path.read_text(encoding="utf-8")
    imports = re.findall(r"""^\s*import[^'"]*['"]([^'"]+)['"]""", src, re.M)
    bad = [m for m in imports if m not in ALLOWED_IMPORTS]
    if bad:
        return f"imports not allowed: {bad}"
    for pat in BANNED:
        if re.search(pat, src):
            return f"banned pattern {pat}"
    if not re.search(rf"export\s+default\s+function\s+{path.stem}\b", src):
        return "no `export default function` with the file's name"
    return None


def _tsc_bad_files():
    res = subprocess.run(["npx", "--no-install", "tsc", "--noEmit"], cwd=REMOTION, capture_output=True, text=True)
    bad = set(re.findall(r"src/generated/(Scene\d+)\.tsx", res.stdout))
    if res.returncode and not bad:
        raise RuntimeError("Remotion project fails typecheck outside generated scenes:\n" + res.stdout[-2000:])
    return bad


def gate(names, props_path, public_dir, browser):
    """Keep only scenes that pass every check. Returns the surviving component names."""
    ok = []
    for n in names:
        p = GEN / f"{n}.tsx"
        why = "missing" if not p.exists() else _gate_file(p)
        if why:
            log(f"  {n} rejected: {why}", "WARN")
            p.unlink(missing_ok=True)
        else:
            ok.append(n)
    write_index(ok)
    for _ in range(3):                       # typecheck, drop broken files, repeat
        bad = _tsc_bad_files() & set(ok)
        if not bad:
            break
        for n in bad:
            log(f"  {n} rejected: type errors", "WARN")
            (GEN / f"{n}.tsx").unlink()
        ok = [n for n in ok if n not in bad]
        write_index(ok)
    if not ok:
        return ok
    env = {"REMOTION_BROWSER": browser} if browser else {}
    res = subprocess.run(["node", "tools/sheet.mjs", "--props", str(props_path), "--public-dir", str(public_dir),
                          "--out", "out/gate.png", "--report", "out/gate.json"],
                         cwd=REMOTION, capture_output=True, text=True, env={**_env(), **env}, timeout=900)
    if res.returncode:
        raise RuntimeError("contact-sheet render failed:\n" + res.stderr[-2000:])
    failed = json.loads((REMOTION / "out" / "gate.json").read_text())["failedScenes"]
    crashed = {f"Scene{i}" for i in failed}
    for n in crashed & set(ok):
        log(f"  {n} rejected: crashed while rendering", "WARN")
        (GEN / f"{n}.tsx").unlink()
    ok = [n for n in ok if n not in crashed]
    write_index(ok)
    return ok


def _env():
    return dict(os.environ)


def generate(cfg, script, props, props_path, public_dir, browser):
    """Fill props["scenes"][i]["component"] with generated scene names (None = cartoon fallback)."""
    sg = cfg["scenegen"]
    if not os.environ.get("SCENEGEN_PREWRITTEN"):
        reset()
    b = brief(script, props)
    (GEN / "brief.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    names = [s["component"] for s in b["scenes"]]
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") and not os.environ.get("SCENEGEN_PREWRITTEN"):
        log("No Claude token (test mode): every scene uses the cartoon template")
        for s in props["scenes"]:
            s["component"] = None
        return props
    log(f"Claude is designing {len(names)} bespoke scenes")
    try:
        if os.environ.get("SCENEGEN_PREWRITTEN"):   # dev/test: scenes already written by hand
            raise RuntimeError("using pre-written scenes")
        reply = brain.call_claude(
            _prompt(b, props_path, public_dir, sg.get("review_rounds", 2)),
            tools="Read,Write,Edit,Glob,Bash(npx tsc:*),Bash(npx --no-install tsc:*),Bash(node tools/sheet.mjs:*)",
            max_turns=int(sg.get("max_turns", 90)), effort=sg.get("effort", "high"), cwd=REMOTION,
            timeout=int(sg.get("timeout_minutes", 25)) * 60)
        log("Claude's scene notes: " + reply.replace("\n", " | ")[:600])
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        log(f"Scene design stopped early ({str(e)[:200]}); keeping whatever scenes pass the gates", "WARN")
    ok = gate(names, props_path, public_dir, browser)
    log(f"Bespoke scenes kept: {len(ok)}/{len(names)}" + ("" if len(ok) == len(names) else " (rest use the cartoon template)"))
    for s, n in zip(props["scenes"], names):
        s["component"] = n if n in ok else None
    shutil.rmtree(REMOTION / "out", ignore_errors=True)
    return props
