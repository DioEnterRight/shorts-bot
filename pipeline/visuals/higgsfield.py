"""<<< HIGGSFIELD SWAP SLOT >>>

Higgsfield has no free API key for your web plan; it is driven from Claude via the
Higgsfield MCP connector (spends your plan credits). So the hand-off works like this:

  1. A Claude Code Routine (claude.ai/code/routines) with the Higgsfield connector runs
     ~1 hour before the 'Make video' workflow. Use the prompt in tools/higgsfield_routine_prompt.md.
  2. That routine reads the latest script request, generates the clips in Higgsfield,
     and commits a file  inbox/<YYYYMMDD>.json  to this repo:

       higgsfield_clips:  {"scenes": [{"url": "https://...mp4"}, ...]}   one clip per scene
       higgsfield_full:   {"final_url": "https://...mp4", "title": "...", "description": "..."}

  3. This module downloads those files. Everything else (voice, captions, music,
     posting) keeps working exactly the same in 'higgsfield_clips' mode.

To switch: set visuals.provider in config.yaml. To switch back: 'cloudflare_flux'.
"""
import json

import requests

from ..common import ROOT, log, now_ist

INBOX = ROOT / "inbox"


def _ticket():
    p = INBOX / f"{now_ist():%Y%m%d}.json"
    if not p.exists():
        raise RuntimeError(
            f"Higgsfield mode is on, but {p.relative_to(ROOT)} was not found. "
            "Either the Higgsfield routine has not run yet, or switch visuals.provider "
            "back to cloudflare_flux in config.yaml.")
    return json.loads(p.read_text())


def ticket_script():
    """The routine can also write the script itself (same JSON shape as prompts/sample_script.json)."""
    p = INBOX / f"{now_ist():%Y%m%d}.json"
    if p.exists():
        return json.loads(p.read_text()).get("script")
    return None


def _fetch(url_or_path, dest):
    """Accept an https URL, OR a path to a clip the routine committed into the repo
    (e.g. "inbox/clips/scene0.mp4"). Both end up as a local file the editor can use."""
    import shutil
    if str(url_or_path).startswith(("http://", "https://")):
        with requests.get(url_or_path, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        return dest
    local = (ROOT / url_or_path).resolve()
    if not str(local).startswith(str(ROOT.resolve())) or not local.exists():
        raise RuntimeError(f"Higgsfield clip not found or outside repo: {url_or_path}")
    shutil.copy(local, dest)
    return dest


def generate(cfg, script, workdir):
    """higgsfield_clips: one clip per scene."""
    ticket = _ticket()
    clips = ticket.get("scenes", [])
    if len(clips) < len(script["scenes"]):
        raise RuntimeError("Higgsfield ticket has fewer clips than scenes")
    out = []
    for i, c in enumerate(clips[: len(script["scenes"])]):
        log(f"Fetching Higgsfield clip {i + 1}")
        out.append(_fetch(c.get("url") or c.get("path"), workdir / f"scene_{i:02d}.mp4"))
    return out


def fetch_full(workdir):
    """higgsfield_full: a finished video made entirely in Higgsfield."""
    ticket = _ticket()
    if not (ticket.get("final_url") or ticket.get("final_path")):
        raise RuntimeError("Higgsfield ticket has no final_url / final_path")
    path = _fetch(ticket.get("final_url") or ticket.get("final_path"), workdir / "final.mp4")
    return path, ticket
