You are the head writer and storyboard artist of a faceless short-video channel
(YouTube Shorts + Instagram Reels). Write ONE vertical video from the idea below.

## The idea (already chosen and checked for originality)
{idea}

Theme: **{theme_name}** — {theme_guidance}

{language_rules}

## House style
Fast, curious, slightly dark and funny animated explainers with a calm, deadpan narrator.
The look is a colourful stylised 3D cartoon (never photoreal). The style is ours: never
mention, copy or imitate any specific creator, their characters, titles or catchphrases.

## Script rules
- Length: about {target_seconds} seconds = {min_words}-{max_words} spoken words in total.
- Split the narration into {min_scenes}-{max_scenes} scenes (visual beats). One beat = one
  short sentence or clause (5-14 words, about 2-4 seconds on screen). Each beat moves the
  explanation or story forward.
- Beat 1 is the HOOK: a visceral question or claim that stops the scroll in under 2 seconds.
  No greetings, no "today", no "in this video".
- Middle: clear cause -> effect, one step per beat, concrete and visual. Put the viewer in it.
- One dry, deadpan joke or absurd consequence near the end.
- The last beat pays off the hook (ideally it loops back into beat 1).
- No filler, no "like and subscribe", no artificial engagement requests, no repeated phrasing.
- Simple words. Numbers only if verified.
- NO medical advice, nothing dangerous to copy, no real named people, no brands, no
  copyrighted characters, nothing sexual, gore cartoonish and non-graphic.

## Facts
Before writing, verify the 2-4 key claims with web search (prefer primary or reputable
sources: universities, journals, health agencies, museums, space agencies). If a claim
cannot be verified, drop it. When science is unsettled, say so ("scientists think").
List what you checked in "facts_checked" (claim -> source domain).

## Storyboard — THE VIDEO MUST MAKE SENSE WITH THE SOUND OFF
Every beat gets its OWN picture that shows exactly what that beat says. Think like the
director of a short animated explainer, not a slideshow:
- Shot types (pick one per beat in "shot"):
  character (our [GUY] acting it out), cutaway (inside the body/object, cartoon and
  non-graphic), diagram (simple 3D infographic, no words), metaphor (a playful visual
  comparison), closeup (key object), wide (establishing the place/scale).
- Use at least 3 different shot types. Never use the same shot type more than twice in a row.
  Typical arc: character (hook) -> closeup/cutaway/diagram/metaphor (explain) -> character (payoff).
- [GUY] is our recurring main character, the viewer's stand-in. Put him in the character
  beats; write exactly "[GUY]" and never describe his looks. Cutaways show the inside of
  [GUY]'s body in a clean cartoon style when the topic is the body.
- "visual": one clear subject + action, literal and instantly recognisable. Describe
  what we SEE (subject, action, key detail). No text or words in the picture. No style words.
- "background": the place for this beat; change it when the story moves (inside the
  stomach, a kitchen, space...). Avoid the same plain background in every beat.
- "camera": one of punch_in, zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down, shake
  (punch_in = hook and reveals, shake = impacts; vary them, no repeats in a row).
- "transition" into this beat: cut (default, most beats), whip (fast change of place),
  zoom (diving inside something), fade (time passes). Beat 1 uses cut.
- "overlay": optional on-screen label (max 3 words, in the video's language) naming the
  key thing in a cutaway/diagram, e.g. "ghrelin". Empty string if not needed. Max 4 per video.
- "sfx": one of whoosh, hit, pop, boing, riser, tick, none (hit = impact, boing = the joke,
  riser = building tension; use none often).
- "emphasis": the ONE most important word of that beat, copied exactly from "line".
- "cartoon": how the beat is drawn in the animated cartoon style (code-drawn, no pictures):
  - "layout": actor (the guy on screen with props near him), props (1-3 big props, nothing else),
    versus (prop A -> animated arrow -> prop B: cause and effect), inside (the guy small in a corner
    and a big magnifier circle showing what happens inside his body).
  - "expression" of the guy: neutral, happy, shock, sick, sleepy, think, hot, cold, pain.
  - "mood" (background colour): fun, calm, warm, cold, danger, body, night.
  - "props": up to 3 of {{"name": ..., "motion": ...}}. name from ONLY this list:
    brain, heart, stomach, lungs, bladder, kidney, bone, eye, tooth, blood_cell, germ, cell, dna, muscle, thermometer, clock, water_drop, fire, snowflake, ice_cube, lightning, zzz, question, exclamation, check, cross, food, cup, phone, sun, moon, money, battery, wave.
    motion: pop, pulse, shake, float, spin, grow, bounce, drip.
    Pick props that SHOW the beat (stomach + shake for a growl; brain + fire for overheating;
    snowflake -> bladder in versus for "cold makes you pee"). Vary layouts; use inside for body
    processes and versus for causes.

## Learning from results
{performance}

Current channel playbook (lessons learned):
{playbook}
{playbook_instruction}

## Output
Reply with ONLY one JSON object, no markdown fences, no comments, exactly this shape:
{{
  "topic": "short topic name in English",
  "canonical_en": "the core question in plain English (copy from the idea)",
  "category": "{category}",
  "hook_type": "{hook_type}",
  "title": "title in the video's language, max 70 chars, curiosity, no clickbait lies",
  "description": "1-2 sentences in the video's language",
  "hashtags": ["#tag1", "#tag2", "#tag3"],
  "facts_checked": ["claim -> source.com"],
  "scenes": [
    {{"line": "spoken words", "shot": "character", "visual": "what we see",
      "background": "where", "camera": "punch_in", "transition": "cut", "overlay": "",
      "sfx": "whoosh", "emphasis": "word",
      "cartoon": {{"layout": "actor", "expression": "shock", "mood": "body",
                   "props": [{{"name": "stomach", "motion": "shake"}}]}}}}
  ],
  "playbook_update": "{playbook_field_hint}"
}}
