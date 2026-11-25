# shorts-bot — the complete guide

Everything you need to run the Cons & Coins bot, change it to your taste, and switch which AI does which job.
Almost every setting lives in **`config.yaml`**. Edit it on GitHub (pencil icon → Commit) or in your clone and push;
the next run uses it. No workflow file needs editing for normal changes.

---

## 1. What happens every day

| Time (India) | Workflow | What it does |
|---|---|---|
| every hour (:13) | **Make video** | Keeps the next `schedule.make_ahead` uploads ready: makes one video (right language) if they are not covered yet. ~45–70 min each. |
| every 30 min | **Post video** | If a `schedule:` slot's time has come, posts that slot's video (right language) to Instagram + YouTube. Otherwise stops in seconds. Never waits for a Make run. |
| Sundays | (inside Make) | Claude rewrites `data/playbook.md` from real view stats. |

**How one video is made**
1. **Idea** — Claude researches ~8 ideas on the web and drops anything too close to an old video. The best is used, the other good ones wait in a backlog (`data/ideas.json`, 7 days) so the next videos need no brainstorm call.
2. **Script** — Claude writes and fact-checks it with the kit's story formula (45–65 s, hook in the first line, one line = one picture).
3. **Voice** — edge-tts (Kokoro if edge fails), with exact word timings.
4. **Director** — Claude (Sonnet, one cheap tool-free call ~10k tokens) writes the *shot plan*: who stands where, what they do, which props tell each line, where the camera goes and on which word it lands. (Or a free FreeLLMAPI model, see §5.)
5. **Checks + repairs** — the kit tests every frame (faces cut off, people inside walls, the camera inside a shelf…).
   Repairs go cheapest first: code fixes the director's small mistakes, then tries camera variations itself, then the
   director gets what is left, then **Claude Opus takes over** if that can't finish.
6. **Preview + judge** — a small preview renders, a contact sheet (one frame every 0.5 s) is scored 1–10 by a free FreeLLMAPI vision model. Under 8 → one fix round; the higher score wins.
7. **Final** — 1080×1920 render on GitHub's computer, music + sound effects mixed at −14 LUFS, quality check, saved to **Releases**.
8. Only if Claude's rescue also fails is the video drawn by the old flat 2D engine, so the slot never stays empty.

---

## 2. One-time setup (check once)

**Settings → Secrets and variables → Actions → Repository secrets**

| Secret | Needed for | How to get it |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | ideas + scripts (always) | run `claude setup-token` on your PC, paste the token |
| `FREELLMAPI_KEYS` | free director + judge | see `FREELLM_SETUP.md` (optional if Claude directs) |
| `IG_USER_ID`, `IG_PAGE_TOKEN` | Instagram posting | Meta app (already set up) |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | YouTube upload + stats | `tools/youtube_auth.py` |

**Settings → Actions → General → Workflow permissions → "Read and write"** (the bot saves its memory in `data/`).

First time after a big change: **Actions → Make video → Run workflow** with **test mode ticked**. It makes the sample
story without keys and attaches the video + contact sheets to the run. Untick it for a real video.

---

## 3. The buttons (Actions tab)

| Button | Use it when |
|---|---|
| **Make video** | You want videos now. `test mode` = sample, posts nothing. `language` = `auto` (what the schedule needs), or force `en` / `hi` for one extra video. |
| **Post video** | Post the oldest ready video right now, outside the schedule. |
| **Throw away ready videos** | You don't like what's waiting; the next Make run builds fresh ones. |
| **Test FreeLLMAPI** | Check the free-model keys (makes nothing). |

Every Make run has a **versions** download at the bottom of the run page: contact sheets, shot plan, check report and
judge scores for every version. Open the `sheet_*.jpg` files to see the whole video at a glance. You are the final judge.

---

## 4. Your preferences — where to change what

### Uploads: times, how many, which language
```yaml
schedule:
  every_minutes: 60          # one upload every hour = 24 a day
  first: "00:30"             # first upload of the day; the rest follow every_minutes
  language: en               # every upload is in this language...
  language_at: {"09:30": hi} # ...except these times
  make_ahead: 2              # keep the next 2 uploads ready
  make_per_run: 1            # each hourly Make run makes at most 1
```
- India time, 24-hour, always two digits (`"07:30"`, not `"7:30"` — the bot stops with a clear error on a typo).
- **Fewer a day:** `every_minutes: 120` = 12 a day, `240` = 6, `480` = 3, `1440` = 1. **More Hindi:** add times to
  `language_at`, e.g. `{"09:30": hi, "21:30": hi}` (each must be one of the upload times). **All Hindi:** `language: hi`.
- One Make run makes one video (~45–70 min). Runs never overlap, so a Make run that takes over an hour makes fewer
  than 24 a day: if posts start going out late or get skipped, use `every_minutes: 90` or `120`.
- A slot can post up to one slot interval late (max 3 h). After that its video waits for the next slot of the same language.
- If a Hindi slot has no Hindi video ready, the oldest English one is posted instead (and the log says so).

### Video length and talking speed
| Want | Change |
|---|---|
| Longer / shorter videos | `video.target_seconds` (kit range 45–65) |
| Faster / slower narrator | `languages.en.edge_rate` / `languages.hi.edge_rate` (e.g. `"+0%"` calm, `"+10%"`, `"+18%"` fast). Check "Speaking pace" in the Make log. Also set `words_per_second` to the pace you hear (it sets the script length) |
| Script fits the speed | `words_per_second` (kit: 3.3–3.8). Raise it together with `edge_rate`, or videos come out longer than `target_seconds` |

### Voices
| Want | Change |
|---|---|
| Other English voice | `languages.en.edge_voice` — `en-US-AndrewNeural`, `en-US-GuyNeural`, `en-US-ChristopherNeural` |
| Other Hindi voice | `languages.hi.edge_voice` — `hi-IN-MadhurNeural` (male), `hi-IN-SwaraNeural` (female) |
| Backup voice (only if edge-tts is down) | `voice` under each language (Kokoro names in the comments) |

### What the videos are about
| Want | Change |
|---|---|
| Topics of the channel | `channel.niche` (the topic menu Claude picks from) |
| More explainers vs. true stories | `themes.explainer.share` / `themes.story.share` (any numbers; they are turned into percentages) |
| A new kind of video | add a theme with `share` + `guidance` (one paragraph describing it) |
| How many ideas Claude compares | `ideas.candidates` |
| Allow more similar topics | `ideas.similarity_threshold` (higher = more allowed) |

### Hindi videos (Hinglish)
- The **voice** reads natural spoken Hindi: Devanagari with everyday English words in Latin letters (so the Hindi voice pronounces it right).
- The **captions** on screen are **Hinglish in Roman letters** ("aapka stomach khaali hote hi brain ko signal bhejta hai"). Claude writes them for every line; a script without them is sent back automatically.
- The title + description are catchy Hinglish and may mix Devanagari and English. Rules live in `prompts/lang_hi.md`; edit that file to change the Hindi style (e.g. "titles in Roman letters only").

### Look and sound
| Want | Change |
|---|---|
| Music louder / quieter | `studio.music_db` (−13 = 13 dB under the voice; kit range −10 to −15) |
| Sound effects louder / quieter | `studio.sfx_db` |
| Characters, places, props, camera style | the head skill (`.claude/skills/animated-shorts-kit/`) — ask Claude Code to change it there, never per video |

### Quality vs. cost
| Want | Change |
|---|---|
| Fewer bad videos falling back to 2D | `studio.rescue_rounds` (2 → 3), `studio.autofix_rounds` (24 → 32) |
| Always the best director (more Claude usage) | `studio.director: claude` + `studio.claude_model: opus` |
| Stricter judge (more fix rounds) | `studio.good_enough` (8 → 9) |
| Faster, cheaper runs | `studio.judge: false` (skips the score + fix round) |
| Claude script quality vs. usage | `claude.model` (`opus` best, `sonnet` cheaper), `claude.effort` (`high` / `medium`) |

### Posting
| Want | Change |
|---|---|
| Stop everything for a while | `paused: true` (Make and Post both do nothing) |
| YouTube by hand (no API) | `publish.youtube_mode: manual` (you get the file + title to upload yourself) |
| No YouTube at all | `publish.youtube_mode: off` |
| No Instagram | `publish.instagram: false` |
| Instagram "AI info" label | `disclosure.instagram_ai_label` |
| Fewer hashtags | `publish.hashtags_max` |

---

## 5. Switching AIs: FreeLLMAPI ↔ Claude

Who does what today:

| Job | Today | Can switch? |
|---|---|---|
| Ideas (web research) | Claude | No — needs web search to check facts and originality; FreeLLMAPI has none |
| Script + fact-check | Claude | No — same reason |
| Director (shot plan) + repairs | Claude Sonnet (one tool-free call, ~10k tokens) | Yes |
| Judge (scores the preview) | FreeLLMAPI vision (free) | — (Claude only with `studio.claude_judge: true`) |
| Emergency 2D storyboard | Claude (`toon2d.model`) | — |

### Claude director (the default: better props, placing and sizes)
```yaml
studio:
  director: claude
  claude_model: sonnet      # or opus for the best plans (more of your Claude limit)
  claude_effort: medium     # low saves tokens, high thinks more
```
Each call sends only the kit's director brief + the beats (no tools, no Claude Code system prompt): `[Likely]` ~6k
tokens in, ~4k out. Usually 1–2 calls a video (the code repairs most problems for free). Keep the `FREELLMAPI_KEYS`
secret: FreeLLMAPI still judges the preview for free. Without it the judge is skipped (unless `studio.claude_judge: true`).

### Claude → FreeLLMAPI director (free, weaker plans)
```yaml
studio:
  director: freellm
```
Needs the `FREELLMAPI_KEYS` secret (`FREELLM_SETUP.md`). If the free model can't pass the checks, Claude Opus rescues.

### Automatic switches (you do nothing)
- Free model can't pass the checks after `studio.repair_rounds` → Claude (`studio.rescue_model`, Opus) takes over for
  `studio.rescue_rounds` more rounds. Turn it off with `studio.rescue: false` (then it goes straight to 2D).
- FreeLLMAPI not running (no secret, keys broken) or its monthly cap reached → Claude directs, the judge is skipped.
- Too many requests for one video (`freellm.max_calls_per_video`) → that video falls back to the 2D engine.

### FreeLLMAPI knobs
| Want | Change |
|---|---|
| Pin a favourite model | `freellm.models: ["gemini-2.5-pro", "auto:smart"]` |
| Allow more requests per video | `freellm.max_calls_per_video` |
| Monthly limit | `freellm.monthly_token_cap` |

---

## 6. When something goes wrong

| You see | Do this |
|---|---|
| A GitHub issue "No video ready" | Open the latest **Make video** run, read the red step. Fix, then press **Make video** |
| Make log: `studio failed` / `still fails the checks` | That video was made by the 2D engine (even Claude's rescue failed). The **versions** download has every round (`rounds/round_NN.json`): the plan, what code fixed, what the checks still found |
| Hindi voice: `edge-tts attempt … failed` | Microsoft throttling; the bot waits and retries 6× per line. If it still falls back to Kokoro, raise `voice.edge_pause` (1.5 → 3) |
| Videos feel slow / fast | §4 talking speed |
| Hindi captions in Devanagari | Only happens in old videos made before this change |
| `Claude Code call failed` | `claude setup-token` again → update `CLAUDE_CODE_OAUTH_TOKEN` |
| `Could not push bot state` | Settings → Actions → General → Workflow permissions → **Read and write** |
| `YouTube API uploads are staying private` | YouTube API audit not approved yet → `publish.youtube_mode: manual` |
| A slot was skipped | Its video was not ready in time (Make runs over an hour): raise `schedule.every_minutes` |
| Same prop in every shot / floating blue slabs | Old videos only: props now live in their own scene, one model in ≤ 2 scenes, building parts are not props |

---

## 7. Testing on your PC (optional — everything runs in the cloud anyway)

Needs Python 3.12, Node 22, ffmpeg and Chrome.
```powershell
cd C:\Users\Asus\shorts-bot
pip install -r requirements.txt pytest
python -m pipeline.fetch_models
cd .claude\skills\animated-shorts-kit\code; npm ci; cd ..\..\..\..
python -m pytest -q -m "not slow"          # seconds: checks code + config
python -m pipeline.produce --test          # sample video in out\ (~30-60 min on a laptop)
```
Never run without `--test` on your PC: that would make real videos and change `data/`.

---

## 8. Changing the bot itself

Ask Claude Code in this repo. Every AI reads `AGENTS.md` → the head skill `.claude/skills/animated-shorts-kit/SKILL.md`
(story formula, characters, sets, camera, shot plan, checks, judge, and `references/08_OUR_PIPELINE.md` for how this
repo works). Improvements go into the skill, so every future video gets them.
