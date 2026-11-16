---
name: shortsbot-scene-kit
description: Write bespoke animated scenes for shorts-bot videos with the channel's Remotion design kit (remotion/src/kit). Use when generating or fixing remotion/src/generated/Scene*.tsx for a video.
---

# shorts-bot scene kit

Every video gets NEW scene code. The kit keeps the brand consistent; your composition makes each
video unique and understandable. One scene = one idea the viewer gets in one second.

## File rules (hard - the bot rejects scenes that break them)
- One file per scene: `src/generated/SceneN.tsx` with `export default function SceneN() {...}`.
- Imports ONLY from `"react"`, `"remotion"` and `"../kit"`. No other packages, no assets, no fetch.
- Everything is a pure function of `useCurrentFrame()`. Never: `Math.random`, `Date`, `setTimeout`,
  CSS `transition`/`animation`/`@keyframes`, `useEffect` timers. Use `rand(n)` for randomness.
- Canvas 1080x1920. Keep content inside x 70..1010, y 180..1400. Below y 1400 the captions run - leave it clear.
- Local frame 0 is where the scene's slot starts; the previous scene is still transitioning out for
  `preFrames` frames. Start your first entrance at `preFrames` (from `useScene()`).
- No narration text on screen (captions already show it). On-screen text = labels/numbers, max 5 words.

## Timing: sync motion to the words
- `useScene()` -> `{ durationInFrames, preFrames, words: [{text, from, to}], line, language, emphasis }`
  (word frames are local to this scene).
- `useWordAt("heat")` -> local frame where that word is spoken. Make the thing appear ON its word.
- `prog(f, a, b, ease.out)` 0..1 tween; `sp(f, at, "pop")` spring (kinds settle|pop|heavy|elastic - elastic once per video).
- Stagger items ~6-8 frames; exits are half as long as entrances (`<Exit>` uses ease-in).
- Hold anything readable >= 30 frames after it lands. Nothing important appears in the last 6 frames.

## Components (from "../kit")
- `<Stage from to pattern="dots|grid|rays|none">` background (never flat/still). Colours: `C.*` tokens only
  (ink, paper, accent, hot, cool, good, bad, purple, skin, body, night, sky, muted).
- `<Camera move="push|pull|pan_left|pan_right|shake|still">` wraps content for a subtle move.
- `<At x y w h>` absolute placement by centre point. `<Pop at kind idle="float|pulse|wobble|spin">` entrance.
- `<Bean pose emotion size lookX talking>` the mascot. Mouth is lip-synced automatically.
  pose: idle, point_left, point_right, point_up, shrug, think, wave, cheer, facepalm, hold.
  emotion: neutral, happy, shock, worried, sick, sleepy, smug, hot, cold.
  He ACTS the beat: points at what he explains, shrugs at myths, reacts on the twist. Not in every scene.
- `<Headline text at accent maxLines maxSize width>` big title, words rise in (auto-fits). Use sparingly.
- `<Tag text at bg color size rotate>` sticker label. `<Counter to from at dur prefix suffix decimals size>`.
- `<Icon name size color fill stroke>` any lucide icon by PascalCase name (Flame, Snowflake, Brain,
  HeartPulse, Bug, Droplet, Droplets, Clock, Zap, Moon, Sun, Utensils, Coffee, Pill, Dna, Microscope,
  Thermometer, Wind, Battery, Smartphone, TrendingUp, TrendingDown, Ban, Check, X, Skull, Sparkles...).
- `<Prop name size>` hand-drawn glossy organs/objects: brain, heart, stomach, lungs, bladder, kidney,
  bone, eye, tooth, blood_cell, germ, cell, dna, muscle, thermometer, clock, water_drop, fire,
  snowflake, ice_cube, lightning, zzz, question, exclamation, check, cross, food, cup, phone, sun,
  moon, money, battery, wave.
- `<Arrow x1 y1 x2 y2 at dur curve color width flow>` self-drawing arrow (canvas coords). `flow` = moving dashes.
- `<Ring x y r at color>` hand-drawn circle around something. `<Burst x y at color n>` impact particles.
- `<Meter value label at color width>` gauge. `<Bars items=[{label,value,color}] at>` chart.
- `<Split left right at leftBg rightBg>` side-by-side comparison panels.

## What makes it good (the channel's taste)
- Show the mechanism, don't decorate: cause -> arrow -> effect, a meter filling, a number counting,
  a zoom into the body, before/after split. Ask "could a viewer with sound off get the idea?"
- One focal point per frame. Big shapes (200-500 px). Thick ink outlines. One accent colour per scene.
- Vary the composition scene to scene (never the same layout twice in a row). Persistent objects
  that travel across scenes feel designed.
- Scene 1 is the hook: motion in frame 0, the most surprising visual of the video.
- Last scene: a payoff/punchline visual, Bean reacting.

## Example
```tsx
import React from "react";
import { useCurrentFrame } from "remotion";
import { Stage, Camera, At, Pop, Bean, Prop, Arrow, Meter, Tag, useScene, useWordAt, prog } from "../kit";

export default function Scene3() {
  const f = useCurrentFrame();
  const { preFrames } = useScene();
  const cold = useWordAt("cold", preFrames);
  const kidney = useWordAt("kidney", cold + 15);
  return (
    <Stage from="#d6ecff" to="#3fa7ff" pattern="dots">
      <Camera move="push">
        <At x={260} y={560}><Pop at={cold} idle="wobble"><Prop name="snowflake" size={300} /></Pop></At>
        <Arrow x1={420} y1={560} x2={660} y2={560} at={cold + 10} />
        <At x={820} y={560}><Pop at={kidney} idle="pulse"><Prop name="kidney" size={300} /></Pop></At>
        <At x={540} y={880}><Meter value={0.85} label="Urine ↑" at={kidney + 8} /></At>
        <At x={540} y={1180}><Bean pose="point_up" emotion="cold" size={380} /></At>
      </Camera>
    </Stage>
  );
}
```

## Review loop (always)
1. `npx tsc --noEmit` - fix every error in your files.
2. `node tools/sheet.mjs --props <props> --public-dir <dir>` - then Read `out/sheet.png`.
   2 tiles per scene (early, late), labelled S<n>. Also read `out/sheet.json` for crashed scenes.
3. Check: idea readable at phone size? collisions/clipping? anything in the caption zone or off-canvas?
   empty/static tiles? same layout twice in a row? Bean blocking the key visual?
4. Fix the worst 3 problems, repeat. Max 2 review rounds, then stop.
