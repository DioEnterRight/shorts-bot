# shorts-bot Remotion kit

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
