# Free 3D builder (FreeLLMAPI): setup

What changes: Claude still picks the idea and writes the script. The **3D world** (sets, props, characters,
emotions per scene) is planned by your **FreeLLMAPI** instead of Claude Opus. That cuts about $5 of Claude usage
per 3D Short to $0. The look stays the same: same cartoon cards, cuts every ~3 s, captions, mood music, SFX and
renderer. If anything goes wrong, that Short is made in 2D as before.

You can do every step on your phone (GitHub app or github.com in the browser).

---

## Step 1: Merge the update

Merge the pull request (or the bundle) that adds `FREELLM_SETUP.md`. Your own settings (post time, schedule,
secrets) are not touched.

## Step 2: Add the secret `FREELLMAPI_KEYS`

This is the **same kind of secret as in roblox-stories-bot**. If you still have that JSON text, paste the same text.
GitHub never shows a saved secret again, so if you lost it, build it again from your provider keys.

1. github.com/DioEnterRight/shorts-bot > **Settings** > **Secrets and variables** > **Actions** > **New repository secret**
2. Name: `FREELLMAPI_KEYS`
3. Value: a JSON list, one line per provider key. Example with 4 providers:
   ```
   [
     {"platform": "google", "key": "AIza..."},
     {"platform": "groq", "key": "gsk_..."},
     {"platform": "openrouter", "key": "sk-or-v1-..."},
     {"platform": "nvidia", "key": "nvapi-..."}
   ]
   ```
4. **Add secret**.

More providers = more strong models to pick from and more quota. For the best storyboards, these matter most:

| Provider | Where to get the key | Stay free |
|---|---|---|
| `google` (Gemini, the strongest free models) | aistudio.google.com > Get API key | Use a project that shows **Free tier**. Never click "Set up billing" on it: with billing, Gemini usage is charged |
| `groq` (fast, GPT-OSS 120B, Llama, Qwen) | console.groq.com/keys | Free plan has no card, so it can't charge |
| `openrouter` (many `:free` models) | openrouter.ai/settings/keys | FreeLLMAPI only calls `:free` models. Free limit is 50 requests/day (1,000/day after a one-time $10 top-up) |
| `nvidia` (NIM catalog) | build.nvidia.com > Get API key | Free credits; when they run out, requests fail, nothing is charged |

`[Likely]` These keys **are shared with roblox-stories-bot**, so both bots draw from the same daily limits. That's
fine: one 3D Short uses about 3-6 requests.

## Step 3: Test the keys (costs one tiny request, makes no video)

**Actions** > **Test FreeLLMAPI** > **Run workflow**. After ~2 minutes it should end green with:

```
FreeLLMAPI ready models: N (e.g. ...)
FreeLLMAPI auto:smart -> <provider>/<model>: in=.. out=..
FreeLLMAPI OK.
```

If it is red, the last red lines say which part is wrong (bad JSON in the secret, a key rejected, no model ready).

## Step 4: Switch the 3D builder on

Edit `config.yaml` on GitHub (pencil icon), find the `cartoon3d:` block and change one word:

```
  builder: freellm
```

Commit. The next scheduled run uses it. To run it now: **Actions** > **Make video** > **Run workflow** with "test"
**unticked**. That makes one real video and queues it; it goes out at your normal post time.

In the **Make the video** step of that run, look for:

- `FreeLLMAPI auto:smart -> google/gemini-...`: which free model planned your video
- `art-director review accepted`: the second, quality pass worked
- no line with `making this Short in 2D`

To go back to Claude building the 3D world: `builder: claude`.

---

## How the quality is pushed up

1. **Claude writes the idea and script** (unchanged). Its per-scene "picture idea" goes to the free model.
2. **`auto:smart`**: FreeLLMAPI picks the most capable model that is ready at that moment and moves to the next one
   when a provider is rate-limited. No fixed model that might disappear next week.
3. **The free model only plans the picture**, in a small JSON storyboard (set, props from the real 3D model list,
   characters, emotion, camera feel). Code does the rest (camera moves, cuts, lights), so a weaker model can't
   break the video.
4. **Recurring cast list**: characters are named once with a fixed look, so the same person looks the same in
   every scene.
5. **Code check + fix-ups**: unknown props, wrong values or missing scenes go back to the model (up to 2 times).
6. **Art-director review**: a second pass checks every scene against the narration and fixes weak ones. It is
   kept only if it is at least as clean as the draft.
7. **Reel director skill** (`.claude/skills/reel-director/`): the model directs like a filmmaker (story purpose per scene,
   hand-built story objects such as jets, parachutes, banknotes with serial numbers, evidence boards, labels with the key
   number, reveals timed to the spoken word, reaction beats, a camera shot + move chosen for each scene's purpose).
8. **Visual QC on real pixels**: one still per scene goes to a free **vision** model, weak scenes are rewritten, re-rendered and
   re-checked; the fix stays only if it scores better. After the render, an inspector checks the MP4 (black/frozen frames,
   loudness, captions, sync, shot variety) and writes a score out of 100 into the run's job summary. Critical defects make
   that Short 2D. A vision-capable key (the `google` Gemini key) is needed for the visual review; without one it is skipped
   and the report says "not inspected".

## Free-tier safety (never pays, never runs away)

- Only free keys go in the secret (table above). The bot itself has no paid API anywhere in this path.
- Max **16 requests per video** (`freellm.max_calls_per_video`); a normal video uses 4-8.
- Max **30M tokens per month** (`freellm.monthly_token_cap`). Usage is saved in `data/freellm_usage.json` (calls,
  tokens, which models). After the cap, 3D Shorts are made in 2D until next month. This ledger is needed because the
  FreeLLMAPI container starts fresh in every run and forgets its own counters.
- `claude_rescue: false` (default): when the free builder fails, the Short is made in 2D. Claude is not called.
- Rate limits: FreeLLMAPI fails over between providers; the bot waits and retries, and stops early on
  "quota used up".

## Knobs in `config.yaml` (`freellm:`)

| Setting | Default | What it does |
|---|---|---|
| `models` | `["auto:smart"]` | Tried in order. To pin a favourite: `["gemini-2.5-pro", "auto:smart"]` (exact ids are in the Test FreeLLMAPI log) |
| `review` | `true` | The art-director second pass (1-3 extra requests) |
| `repair_rounds` | `2` | Fix-up rounds when code finds mistakes |
| `max_calls_per_video` | `16` | Hard request cap per video |
| `monthly_token_cap` | `30000000` | Monthly token cap |
| `reel_qc.visual_review` | `true` | Vision check of one still per scene + fix of weak scenes (2-5 extra requests) |
| `reel_qc.max_fix_scenes` | `4` | Most scenes rewritten per video |

Experiment `[Guessing]`: `models: ["fusion", "auto:smart"]` makes FreeLLMAPI ask a panel of ~4 models and a judge
for every request. It might plan better, but it uses about 5x the quota and its JSON is less predictable.
Try it only after the normal setup works.
