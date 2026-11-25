# Reference code — a working mini studio (Three.js + @react-three/fiber + Remotion, TypeScript)
Tested: installs, type-checks, passes the checkers and renders the example video.

## Run it
1. Install Node.js 22 (LTS).
2. `npm ci` → `VIDEO=01_example npm run gates` → `npm run still` (one frame) → `npm run preview` (video).
   Mac: double-click `render.command` does the same.
3. Edit live: `npm run studio`.
In shorts-bot the bot renders on the GitHub Actions runner: headless Chrome with CPU WebGL (`--gl=swangle`), about
0.3 s/frame for the 540x960 preview and 0.75 s/frame for 1080x1920 on 2 CPUs (measured), so cloud rendering is fine here.

## Make your own video
Automatic / any model: write a shot plan (`references/09_PLAN_FORMAT.md`), then
`python3 src/engine/tools/plan.py plan.json src/videos/<id>` writes stage.ts, takes.ts, set.tsx, solids.ts, look.ts.
By hand: copy `src/videos/01_example` to `src/videos/02_my_story`, then edit:
timeline.ts (words + shots; generated from your voice with `src/engine/tools/timeline.py`), stage.ts (who stands where),
takes.ts (camera), set.tsx (which sets/props), look.ts (story mood). Then run render.command and pick it.

| path | what |
|---|---|
| src/engine/chars/charparts.ts | 20 characters (LOOKS, SHAPES), body parts, faces, 16 expressions |
| src/engine/chars/rig.tsx | character rig: poses, walk, grips (cart handle), carrying, gaze, mouth |
| src/engine/kits/grocery/store.tsx | grocery interior + shop front + shopping cart + extras |
| src/engine/kits/downtown/* | 1930s street block (28 shops), cars, parking meters, street clock |
| src/engine/look/draw.ts | procedural textures (brick, tiles, wallpaper, signs, labels, coins, clock…) |
| src/engine/look/look.ts | BASIC look: flat toon ramp, one light rig, plain sky |
| src/engine/render/Video.tsx | BASIC render: lights + set + characters + captions |
| src/engine/core/* | clock (shots/words → frames), staging (paths, cars, seats, auto-gaze) |
| src/engine/camera/* | framing solver + continuous camera "takes" |
| src/engine/check/* | logic checker, framing checker, hard gates |
| src/engine/kits/grocery/storeData.ts | grocery + workshop solids for the checkers |
| src/engine/kits/models/Model.tsx | KayKit CC0 models (public/models) re-shaded with the toon ramp |
| src/engine/tools/* | timeline.py (voice words → timeline), plan.py (shot plan → story files), sheet.py (contact sheets), align.py, sbs.py |

Not included: the premium look (ink outlines on sets, grading, AO, bloom, depth of field) — that is a separate kit.
