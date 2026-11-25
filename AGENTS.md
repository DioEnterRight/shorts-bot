# shorts-bot — read this first (any AI: Claude, FreeLLMAPI models, others)

Everything about making the videos lives in ONE head skill:
**`.claude/skills/animated-shorts-kit/SKILL.md`** — read it, then the reference it points to for your job.

| your job | read |
|---|---|
| pitch ideas / write a script | `references/02_STORY_FORMULA.md` (+ `prompts/ideas.md`, `prompts/script.md`) |
| direct a video (shot plan JSON) | `references/09_PLAN_FORMAT.md`, `references/03_CAMERA_GRAMMAR.md`, `library/` |
| judge a preview | `references/10_JUDGE.md`, `references/06_CHECKS.md` |
| change the bot (Python, workflows, config) | `references/08_OUR_PIPELINE.md`, `README.md` |
| change the engine (characters, sets, camera) | `code/CODE_README.md`, `references/04_SHAPE_GUIDE.md` |

Repo rules: prefer the simplest change; fail fast; tests `python -m pytest -q -m "not slow"`; never post, push or touch
`data/` while testing; no tool ads or self-attribution in commit messages.
