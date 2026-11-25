---
name: animated-shorts-kit
description: HEAD SKILL of shorts-bot (Cons & Coins channel) for every AI that works on the videos - Claude or FreeLLMAPI's free models. Makes viral-style 2D-character / 3D-world animated story shorts (YouTube Shorts, Instagram Reels) with Three.js + Remotion on GitHub Actions. Use to plan, script, direct, build, check, judge or improve a Short - story formula, 20 characters, grocery + 1930s-downtown sets, 324 KayKit props, camera grammar, shot-plan format, agent team, logic/framing gates and the version workflow.
---

# Animated Shorts Kit — head skill of shorts-bot
A starter kit from a real 2-video project (a 1930s shopping-cart story and a parking-meter story), adapted to this repo:
the bot runs it every day on GitHub Actions for the **Cons & Coins** channel (money, scams, heists, business, psychology).
Every AI that touches a video follows this skill: Claude writes ideas and scripts, a free FreeLLMAPI model directs the
shot plan and judges previews, code compiles, checks, renders and mixes. The kit's own mechanics are unchanged.

## What is inside
| Folder | What | Read it when |
|---|---|---|
| `references/01_WORKFLOW.md` | The 4-step method + versions, render, checks | Always first |
| `references/02_STORY_FORMULA.md` | Hook, story arc, details, ending, captions, sound | Writing the idea / script |
| `references/03_CAMERA_GRAMMAR.md` | Measured camera rules (push-ins, travel instead of cutting, framing) | Planning shots |
| `references/04_SHAPE_GUIDE.md` | Character shapes, proportions, line weight | Building/editing characters |
| `references/05_AGENT_TEAM.md` | Ready prompts for the agent team, the director and the judge | Improving a version |
| `references/06_CHECKS.md` | Logic + framing checklists and hard gates | Before every render |
| `references/07_BASIC_LIGHT.md` | Simple light rules + basic look code | Lighting a scene |
| `references/08_OUR_PIPELINE.md` | **This repo**: who does what, the daily run, config, files, fallback | Working on shorts-bot |
| `references/09_PLAN_FORMAT.md` | **The shot plan**: the director's shot list as JSON, compiled onto the engine | Directing a video (any model) |
| `references/10_JUDGE.md` | The judge brief + its JSON reply | Scoring a preview |
| `library/characters/` | 20 characters (JSON + description) | Casting |
| `library/environments/` | Grocery store, workshop, downtown street, palette, **named spots** (`spots.json`), **KayKit props** (`MODELS.md`) | Building the set |
| `code/` | The studio (tested): characters/rig, sets, camera, checkers, render, plan compiler, KayKit loader | Building the video — read `code/CODE_README.md` |

## Two ways to use it
- **Automatic (the bot, any model):** `pipeline/studio.py` runs steps 3-6 below with no human: the director writes the
  shot plan (09), `code/src/engine/tools/plan.py` compiles it, the gates (06) send problems back for repair, a preview is
  rendered and judged (10), the better version wins, the final is rendered in the cloud and mixed.
- **By hand (Claude Code in this repo):** the kit's original way. Same steps; you may also write `stage.ts` / `takes.ts` /
  `set.tsx` directly for things the plan format cannot express, and put every improvement into the shared engine.

## How to work (user / bot)
1. Pick the story (Cons & Coins topics, 02 formula). Fact-check it with web search, and check nobody has already made the same short.
2. Write the script with `02_STORY_FORMULA.md` (45–65 s, one-sentence hook, no year/"once upon a time" opening). One script line = one beat.
3. Plan shots with `03_CAMERA_GRAMMAR.md`; cast from `library/characters`; pick spots and props from `library/environments`. Write it as a shot plan (`09_PLAN_FORMAT.md`).
4. Build with `code/` (see `code/CODE_README.md`): `plan.py` writes the story files into `src/videos/<id>/`. Missing pieces: write them in the same style (flat toon materials, dark ink outlines, white ball heads).
5. Run the checks in `06_CHECKS.md` with code, not by eye. Then render a preview — in this repo on the GitHub Actions runner (headless Chrome, CPU WebGL: ~0.3 s/frame preview, ~0.75 s/frame full HD on 2 CPUs).
6. Watch the WHOLE preview (contact sheets every ~0.5 s, `sheet.py`), fix, and keep every version (v1, v2, v3…) — the bot keeps them in `out/<video>/versions/`.
7. The user is the final judge: an agent checks everything word for word; cartoon magic (a chair becoming a cart) is fine.

## Not included
The premium light/colour layer (grading, light that tells the story, premium materials) is a separate kit. This kit has the basic version: `references/07_BASIC_LIGHT.md` + `code/src/engine/look/look.ts` + the palette in `library/environments/ENVIRONMENTS.md`.
