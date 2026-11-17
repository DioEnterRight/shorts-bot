You are the storyboard artist for a faceless {platform} channel. The voiceover is already recorded.
Write the `story.json` storyboard for it. A code engine draws everything from it in a flat 2D ink-on-paper cartoon
style. You do not write drawing code: you pick shot kinds and fill in their fields.

FORMAT: {format}
LANGUAGE OF THE VOICEOVER: {language}
TOPIC: {topic}

## Sentences (use these numbers in "s")
{sentences}

## Visual hints from the script writer (one per script line; use what helps, ignore the rest)
{hints}

## Rules for this video
- Cover every sentence number exactly once, in order. {pacing}
- {format_rules}
- Never more than two shots of the same kind in a row. Mix world shots (closeup, wide, walk, skyline, crowd)
  with graphics (icon, counter, chart, table, versus, list, map).
- Shot 0 is the hook: make it the most striking image (a closeup reaction, a stamp, a big counter or a versus).
- Every number in the voiceover goes on screen (counter, chart or label). Never invent data for charts.
- Cue events with words from that shot's own sentences ("at": "word"). Copy the word exactly as it appears above.
- On-screen text (labels, stamps, titles, captions, list text) is 1-4 words, in English or Roman letters
  (Hinglish for Hindi videos). Never use Devanagari or other scripts in on-screen text: the fonts can't draw them.
- Cast: 1-3 original characters with distinct silhouettes. Real people are generic puppets with a lower_third
  name card, never a likeness. No brand mascots or logos.
- End on a `polaroid` shot, cued on a word in the last sentence, with the payoff as its caption.
- Pick `mood` to fit the story.

Reply with ONLY the JSON object, no prose, no code fences.

## Engine reference
{reference}
