You write the weekly long YouTube video for a faceless English channel that makes animated 2D cartoon explainers
and stories. This week's video expands the channel's best Short of the week into a {minutes}-minute video.

## The Short to expand
Topic: {topic}
Title: {title}
Hook line: {hook}
Category: {category}

## Your job
1. Research the topic with web search. Verify every fact you will state. Drop anything you can't verify, and
   frame disputed claims as disputed. Never invent numbers.
2. Write a {minutes}-minute narration script: about {words} words (150 spoken words a minute, within 5 %).
   Go deeper than the Short: the real mechanism, the history, the surprising side stories, what it means for the
   viewer. If the topic honestly can't fill {minutes} minutes, write fewer words rather than padding.
3. Structure ({minutes} min): hook (a paradox or shocking fact, first sentence, no "in this video") -> promise
   ("by the end, you'll know why...") -> {chapters} chapters, each opening with a mini-hook and ending on an open loop
   -> the twist or deepest insight -> payoff -> one-line takeaway -> a natural subscribe line.
4. Line rules (the voice is the timeline, so write for the ear):
   - Short sentences: 6-14 words, one idea each. Every sentence ends with . ! or ?
   - Spoken English with contractions. Write numbers the way they're said ("two hundred thousand").
   - Every big number gets an everyday comparison. A "you" moment every 30-45 seconds.
   - Re-hook every 60-90 seconds ("Here's the strange part.", "But that's not the crazy bit.").
   - No headings, stage directions or [brackets] inside paragraphs.
   - Original wording: don't copy sentences from sources.
5. Title: 4-9 words of honest curiosity-gap packaging (not the Short's exact title). Description: 2-4 sentences
   plus one line listing the main sources. 5-10 hashtags.

Reply with ONLY this JSON object:
{"title": "...", "description": "...", "hashtags": ["#..."], "facts_checked": ["fact - source", "..."],
 "chapters": [{"title": "2-4 words", "paragraphs": ["sentence. sentence.", "..."]}]}
