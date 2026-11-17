# shorts-bot

Daily faceless Shorts/Reels bot (English, one Hindi a week) plus a weekly English long video. Python
orchestrates (`pipeline/`): Claude Code writes ideas and scripts, then one storyboard (`story.json`) per
video, and the toon2d engine (`toon2d/`, Python + skia) draws it: 1080x1920 Shorts, 1920x1080 long videos,
on GitHub Actions CPU runners. `pipeline/publish.py` posts. Read README.md for the full flow.

- toon2d: `pipeline/toon2d.py` (timing, storyboard prompt + plan check + fallback, render). Engine changes
  for vertical frames are marked `shorts-bot` in `toon2d/engine`. Storyboard format: `toon2d/reference/story-format.md`.
- Special 3D-world shorts are made by hand with the `cartoon-audio-short` skill, never by the bot.
- Tests: `python -m pytest -q -m "not slow"` (offline). `-m slow` renders with ffmpeg + skia.
- Never post, push or touch `data/` while testing. Prefer the simplest change; fail fast.
- ponytail skills: use them when maintaining the Python pipeline.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. When the answer is under a Markdown heading, `graphify section "<heading>"` prints that section's text, so the .md need not be opened. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
