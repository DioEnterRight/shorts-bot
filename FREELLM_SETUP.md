# FreeLLMAPI: the free judge (and optional director)

Claude writes the idea, the script and the shot plan. Your **FreeLLMAPI** (free models only) scores the preview's
contact sheets (`.claude/skills/animated-shorts-kit/references/10_JUDGE.md`) with a vision model. With
`studio.director: freellm` it also writes and repairs the shot plan (`references/09_PLAN_FORMAT.md`) for free.
Without the secret the judge is skipped (Claude still directs).

You can do every step on your phone (GitHub app or github.com in the browser).

## Step 1: the secret `FREELLMAPI_KEYS` (skip if you already added it)

Same kind of secret as in roblox-stories-bot (paste the same text if you still have it).

1. github.com/DioEnterRight/shorts-bot > **Settings** > **Secrets and variables** > **Actions** > **New repository secret**
2. Name: `FREELLMAPI_KEYS`
3. Value: a JSON list, one line per provider key:
   ```
   [
     {"platform": "google", "key": "AIza..."},
     {"platform": "groq", "key": "gsk_..."},
     {"platform": "openrouter", "key": "sk-or-v1-..."},
     {"platform": "nvidia", "key": "nvapi-..."}
   ]
   ```

| Provider | Where to get the key | Stay free |
|---|---|---|
| `google` (Gemini: strongest free models, and **vision** for the judge) | aistudio.google.com > Get API key | Use a project that shows **Free tier**. Never click "Set up billing" on it |
| `groq` | console.groq.com/keys | Free plan has no card, so it can't charge |
| `openrouter` (`:free` models) | openrouter.ai/settings/keys | FreeLLMAPI only calls `:free` models |
| `nvidia` | build.nvidia.com > Get API key | Free credits; when they run out, requests fail, nothing is charged |

The judge needs a vision-capable model (the `google` key). Without one the judge is skipped and v1 is used.
`[Likely]` The keys are shared with roblox-stories-bot, so both bots draw from the same daily limits.

## Step 2: test the keys (one tiny request, makes no video)

**Actions** > **Test FreeLLMAPI** > **Run workflow**. It should end green with `FreeLLMAPI OK.`
If red, the last lines say what is wrong (bad JSON in the secret, a key rejected, no model ready).

## How a Short uses it (normal: 3-8 requests)
1. Director: one shot plan for all beats (`studio.director: freellm`).
2. Repairs: the kit's gates (faces cut, people in walls, camera inside a shelf…) are sent back, up to `studio.repair_rounds`.
3. Judge: the preview's contact sheets (one frame every 0.5 s) are scored; under `studio.good_enough` one fix round
   makes v2, and v2 is kept only if it scores higher.

## Free-tier safety
- Only free keys go in the secret. Nothing in this path can reach a paid API.
- Max **16 requests per video** (`freellm.max_calls_per_video`).
- Max **30M tokens per month** (`freellm.monthly_token_cap`, counted in `data/freellm_usage.json` because the
  container starts fresh every run). After the cap, Claude directs until next month.

## Knobs (`config.yaml`)
| Setting | What it does |
|---|---|
| `freellm.models` | Tried in order; `auto:smart` = the most capable ready model with failover. Pin one: `["gemini-2.5-pro", "auto:smart"]` |
| `studio.director` | `freellm` or `claude` |
| `studio.repair_rounds` | Rounds of gate problems sent back before the Short falls back to the emergency 2D engine |
| `studio.judge` / `studio.good_enough` | Judge on/off; score at which the fix round is skipped |
