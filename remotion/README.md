# shorts-bot Remotion kit

## How the bot uses it

`pipeline/remotion_render.py` turns the script + voice timings into `remotion_props.json`, checks it,
and renders the `ShortsBot` composition (`src/bot/`). Python owns all timing; Remotion only draws.
The props are checked twice: in Python (`validate_props`) and by the zod schema (`src/bot/schema.ts`),
which stops the render on any mismatch.

- `explainer` style (explainer + story themes): the scene picture with an eased camera move,
  motion blur on punch-ins, remocn transitions (whip-pan, zoom-blur, iris, wave, fade),
  radial burst on "hit" moments, sticker labels (remocn marker) or counting numbers (remotion-bits).
- `blocky` style (roblox_story theme): a three.js toy world with original blocky characters
  (poses: talk, wave, think, walk, jump, shock). No AI pictures, so no Cloudflare credits.
- Captions: remocn word captions from the real word timings; Noto Sans Devanagari for Hindi.
- Sound: voice + music mixed in Python, sound effects (hit/pop/tick/whoosh) placed by Remotion.

Measured on a 2-core machine: ~2.5 min for a 38 s explainer, ~4.5 min for a 27 s blocky video.

Code-made video for shorts-bot. Render: `npm ci && npx remotion render src/index.ts <Composition> out.mp4`.
Config for 2-core CPU runners is in `remotion.config.ts` (software WebGL, concurrency 2).

## Vendored libraries (all MIT, licence file next to each)

| Folder | Source | What it gives |
|---|---|---|
| `src/library/shorts-skill/` | social-media-skills/remotion-shorts-skill | 9:16 kinetic text, safe zones, reading-speed timing |
| `src/library/vibe-motion/` | vibe-motion/remotion-code-motion-explainer | explainer shot library: causal diagrams, reveals, camera moves |
| `src/library/remocn/registry/` | Remocn/remocn (curated 40) | word captions, transitions, impacts, arrows, highlights |
| npm `remotion-bits` | av/remotion-bits | particles, 3D cards, staggered text |
| `public/sfx/` | remotion-shorts-skill (MIT, generated) | hit, pop, tick, whoosh |
| `public/fonts/` | Google Fonts (OFL) | Anton, Poppins, Inter, Noto Sans, Noto Sans Devanagari |

Removed on import: demo videos, WoopSocial posting code and docs, setup scripts, docs-site config
files, tests, and remocn components that need WebGPU (too slow or missing on CPU runners).
Small upstream type fixes: old `startFrom/endAt` props renamed to `trimBefore/trimAfter`,
invalid CSS `rotateX` moved into `transform`.

Not included: Vincentwei1021/anything2explainer (PolyForm Noncommercial licence).
