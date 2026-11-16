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

To go back to free mode: set `visuals.provider: cloudflare_klein`.

## Routine prompt (copy all of it)

```
You produce today's video assets for the shorts-bot repo.

1. Read config.yaml, prompts/script.md, prompts/lang_en.md, prompts/lang_hi.md, data/history.json,
   data/ideas.json and data/playbook.md.
2. Pick the language: look at data/analytics.json -> allocation.language.shares and the languages of the
   last videos in data/history.json; pick the language that is furthest behind its share.
   Pick ONE original idea that is not similar to anything in data/ideas.json or history.json.
3. Follow prompts/script.md (with the matching prompts/lang_*.md rules) exactly to write today's
   script JSON (verify facts with web search). Add "language": "en" or "hi" and "theme": "explainer"
   to the JSON.
4. Read config.yaml -> visuals.provider.
   - If "higgsfield_clips": for EACH scene, generate one 9:16 video clip in Higgsfield
     (use a cheap fast video model, 3-5 seconds, no audio). Prompt = config visuals.art_style +
     the matching visuals.shots entry + the scene's "visual" and "background" ([GUY] replaced by
     config visuals.mascot). Stylised animation only, never photoreal. Keep total credits under 120.
   - If "higgsfield_full": use Higgsfield's faceless video tool to make ONE finished 9:16 video
     (narration + captions + music) from the script lines, 30-45 seconds.
5. Write inbox/YYYYMMDD.json (today's date, India time) with EITHER a url OR a committed file path:
   - higgsfield_clips: {"script": <script JSON>, "scenes": [{"url": "<clip url>"}, ...]}
                       or commit the clips into inbox/clips/ and use {"path": "inbox/clips/scene0.mp4"}
   - higgsfield_full:  {"script": <script JSON>, "final_url": "<video url>",
                        "title": "<title>", "description": "<description>"}
                       (or "final_path": "inbox/final.mp4" if you commit the file)
6. Commit and push to main with message "higgsfield: assets YYYYMMDD".
If Higgsfield fails or credits run out, write nothing — the bot will report the error,
and you can switch config back to cloudflare_klein.
```
