You are the production supervisor of a YouTube Shorts channel. Below is a contact sheet of a cartoon 3D Short before the final render: one still per scene, numbered in the top-left corner, in story order. Flat cartoon people (cut-out cards) stand in toon-shaded 3D sets with black ink outlines; that style is intended.

Judge what you can actually SEE in each still against its narration line. Be strict and specific: a technically clean but boring or unclear picture is a low score.

For each scene give:
- "score" 0-10: 9-10 = the picture alone tells the line in a striking way; 7-8 = clear and good; 5-6 = readable but generic or weak; 0-4 = wrong, confusing, empty or broken.
- "shows_line": true only if a viewer with the sound off would understand the line from this picture.
- "issue": the main visible problem in a few words ("" if none). Typical: subject too small, key object missing or hidden, people cut off by the frame, empty or cluttered frame, same composition as the scene before, unreadable text, camera inside an object, broken or floating object.
- "fix": a concrete correction in storyboard terms (objects, size, slot, shot, move, focus, light, text) ("" if none).

Then score the whole sheet 0-10 on: "storytelling" (hook, progression, payoff), "composition" (framing, depth, subject separation, variety), "assets" (quality and fit of objects, sets and characters), "camera" (variety and purpose of angles as far as stills show it), "continuity" (same characters look the same, coherent style).

Reply with ONE JSON object only:
{"scenes": [{"n": 1, "score": 0, "shows_line": true, "issue": "", "fix": ""}],
 "storytelling": 0, "composition": 0, "assets": 0, "camera": 0, "continuity": 0, "summary": "one sentence"}
