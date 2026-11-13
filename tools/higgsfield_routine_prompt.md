# Higgsfield swap — Claude Code Routine prompt

Use this when you have Higgsfield again.

## One-time setup
1. claude.ai → Settings → Connectors → add custom connector `https://mcp.higgsfield.ai/mcp` → sign in to Higgsfield.
2. claude.ai/code/routines → **New routine**
   - Repository: your `shorts-bot` repo (allow pushing to main)
   - Connectors: keep **Higgsfield** only
   - Schedule: daily **03:00 India time** (one hour before "Make video")
   - Prompt: paste everything in the box below
3. In `config.yaml` set `visuals.provider` to `higgsfield_clips` (Higgsfield pictures/motion, our voice +
   captions + sound) or `higgsfield_full` (Higgsfield makes the whole video). Commit.

To go back to free mode: set `visuals.provider: cloudflare_flux`.

## Routine prompt (copy all of it)

```
You produce today's video assets for the shorts-bot repo.

1. Read config.yaml, prompts/brain.md, data/history.json and data/playbook.md.
2. Follow prompts/brain.md exactly to write today's script JSON (verify facts with web search).
3. Read config.yaml -> visuals.provider.
   - If "higgsfield_clips": for EACH scene, generate one 9:16 video clip in Higgsfield
     (use a cheap fast video model, 5 seconds, no audio). Prompt = config visuals.style_prefix +
     the scene's "visual" ([GUY] replaced by config visuals.mascot). Keep total credits under 120.
   - If "higgsfield_full": use Higgsfield's faceless video tool to make ONE finished 9:16 video
     (narration + captions + music) from the script lines, 30-45 seconds.
4. Write inbox/YYYYMMDD.json (today's date, India time) with:
   - higgsfield_clips: {"script": <script JSON>, "scenes": [{"url": "<clip url>"}, ...]}
   - higgsfield_full:  {"script": <script JSON>, "final_url": "<video url>",
                        "title": "<title>", "description": "<description>"}
5. Commit and push to main with message "higgsfield: assets YYYYMMDD".
If Higgsfield fails or credits run out, write nothing — the bot will report the error,
and you can switch config back to cloudflare_flux.
```
