# Kit API cheat sheet (read this instead of the engine sources)

**Never open** `web/lib/*` (three.js, GLTFLoader), `web/toon.js` or `web/toonbase.js`: they are 60-1300 KB and
everything you need from them is below. Read `web/story.js` and the `// ---------- world ----------` part of
`web/main.js` (they are the example you rewrite), plus `web/roman.js` only if you add new outfits or props.

## story.js (all pure functions of the frame f)
- `export const FPS = 30, TOTAL = <frames>, DECK = <ground height>`
- `SHOTS = [{ id, a, b, light }]` frame ranges a..b, light in `LIGHTS` (day / golden / night presets: sun az/el, colours)
- `CAMS[id] = [{ f, pos:[x,y,z], look:[x,y,z], fov, path?:[[x,y,z]...] }]`; `camAt(f)` uses `camFromKeys(K, f, { kicks })`
- `dofAt(f)` -> `{ focus, cInf }` (cInf 8-14 px on close-ups, 0 on wides); `lightFor(f)`
- `worldAt(f)` -> numbers 0..1 that drive set pieces (collapse progress, door angle...)
- `actorsAt(f, T)` -> cards: `R(T, outfitKey, opts, [x, y, z], { tint, s, rot })`; `fxAt(f, T)` -> effect cards
- motion.js: `clamp lerp lerp3 ramp(f,a,b)`, easings `M.{smooth, easeOut, easeIn, back, anticip, spring}`, `spline(pts,u)`,
  `camFromKeys(K, f, {creep, kicks})`, `idle(f, seed)`, `blinkAt(f, seed)`, `walk(f, f0, speed, stride)`, `q(x)` (round)

## main.js world section
- `add(geo, mat, x, y, z, parent?, {cast})`, `box(w,h,d)`, `tbox(w,h,d,texelMetres)` (world-scaled UVs), THREE geometries
- materials `M.{plank, beam, beamDark, rot, rotB, stone, stoneMoss, grass, dirt, plaster, plaster2, roof, marble,
  marbleTop, trunk, cypress, pine, bush, hill, hillFar, mount, snow, iron, bronze, wood, door, window, red, banner}`;
  new ones: `toon({ color })` or `texM(P.<painter>(seed), repeatX, repeatY)`
- painters in paint.js (`P.`): `planks(seed) beam(seed) rotten(seed) stone(seed, hue) mossy(canvas, seed, amt) grass dirt plaster(seed, hue) roof marble banner helmetInside radial`, `tex(canvas, rx, ry)`, `rng(seed)` (flat style, dark seams)
- **`await model('pack/name', x, y, z, { scale, rotY, tint, parent })`**: KayKit CC0 models with toon shading + ink.
  Names and sizes: `web/models/CATALOG.md`. Scale: city 5, furniture 0.7, restaurant 0.7, dungeon 0.5.
  Prefer models for buildings, vehicles, furniture, food, coins, chests and props; use primitives for terrain,
  custom set pieces and anything that must animate in parts.
- Set pieces: pivoted `THREE.Group`s driven by `worldAt(f)` inside `drawActors`/per-frame state.

## Characters (2D cards, 2.25 m tall, origin at the soles)
- `romanFront(p, outfitKey | outfitObject, opts)` draws on a 600x1000 canvas, soles at y = 975.
  opts: `expr, blink, look, facing (-1..1), seed, L, R (arm poses), tilt, headTilt, bob, nohelmet, step, light`
- `OUTFITS` fields: `tunic cape skin helmet ('old'|true) armor spear shield hair beard brows toga dress stout cap apron`
  (add new outfits for modern people: suits = dark tunic + no armor, etc.)
- arm poses: `hang spear point up wave hip belly temple lift reach cheek shield cross thumb`
- expressions: `neutral stern grin laugh whistle nervous shock relief relief_open dazed pained smile smile_closed lick`
  plus `snore stubborn squint` (roman.js)
- Pen (for new props/effects on cards): `p.poly(pts, fill, ol)`, `p.ell(cx, cy, rx, ry, fill, ol)`,
  `p.line(pts, fill, w)`, `p.stroke(pts, w, colour)`, `p.arc(cx, cy, rx, ry, a0, a1, w, colour)`
- effect cards in roman.js: `fxZ fxLeaf fxDust fxDrip fxWood`; toonbase also has
  `fxNote fxBurst fxSplash fxPuff fxStars fxCreak fxRing fxSign fxCloud fxShadow fxContact fxPlank fxDrum fxBlob`
- After editing roman.js: `cat web/toonbase.js web/roman.js > web/toon.js`

## Commands
- stills: `node render.mjs stills/a "5,40,..."` then `python3 sheet.py stills/a stills/sheet_a.jpg` (read the sheet image)
- never run the full render, audio mix or finish.sh: the pipeline does
