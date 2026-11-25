# shorts-bot

Daily animated Shorts/Reels bot for the Cons & Coins channel, fully on GitHub Actions.
The head skill for every video task is **`.claude/skills/animated-shorts-kit/SKILL.md`** (also listed in AGENTS.md):
story formula, characters, sets, camera grammar, shot-plan format, checks, judge, and this repo's pipeline (`references/08_OUR_PIPELINE.md`).

- Python orchestrates (`pipeline/`): Claude writes idea + script, the kit studio (`pipeline/studio.py`) directs, checks, renders, mixes.
- `toon2d/` is the emergency 2D engine only (used when the kit build fails).
- Tests: `python -m pytest -q -m "not slow"` (offline). `-m slow` = kit gates + full offline render (needs `npm ci` in the kit's `code/`).
- Never post, push or touch `data/` while testing. Prefer the simplest change; fail fast.
