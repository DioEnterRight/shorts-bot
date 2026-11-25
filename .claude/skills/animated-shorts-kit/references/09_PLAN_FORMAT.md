# The shot plan — how any model directs a video without writing code
The director's shot list (05_AGENT_TEAM) as JSON. `code/src/engine/tools/plan.py` compiles it 1:1 onto the kit:
people → `stage.ts` (PersonP + `seq()`), camera → continuous `TAKES` of `K()` keys (`takes.ts`), props → KayKit models
(`set.tsx`, `solids.ts`). Then the kit's gates (06_CHECKS) run. Every problem comes back to you as "beat N camera M: …".

You are the DIRECTOR. You get the script as beats (one beat = one script line, with its exact words and seconds).
Reply with ONLY the plan JSON.

The compiler repairs small mistakes itself (a misspelled name or word, a taken slot, keys too close, a size too wide
for the spot) and reports them as FIX lines; then code tries camera variations on any key the gates reject. You only
hear about what is left — put your effort into the story: who is where, what they do, what the camera shows on which word.

## Shape
```json
{
  "cast": {"hero": "goldman", "boss": "banker"},
  "beats": [
    {
      "spot": "bank",
      "why": "hook: the strange action",
      "people": [
        {"role": "hero", "at": "left", "look": "cam",
         "acts": [["start", "idle", "smirk"], ["word:laughed", "shrug", "smug"]],
         "walk": {"to": "center", "start": "word:walked", "seconds": 1.5}},
        {"role": "boss", "at": "right", "look": "hero", "acts": [["start", "cross", "angry"]]}
      ],
      "props": [{"name": "gold", "model": "dungeon/chest_gold", "at": "back_right", "turn": -20, "scale": 1}],
      "camera": [
        {"at": "start", "on": ["hero", "boss"], "size": "FS", "angle": 15, "height": 6},
        {"at": "word:laughed", "on": ["boss"], "size": "MCU", "angle": -20, "height": 3, "move": "arc", "push": 1.08}
      ],
      "sfx": [["word:laughed", "pop"]],
      "cut": false, "flash": false, "hit": null
    }
  ]
}
```
Exactly one beat per script line, in order.

## Fields
| field | values |
|---|---|
| `cast` | role → character id (library/characters). One character per role, never the same id twice. Costume = identity: pick ids whose look fits the role (banker, cop, rancher…). |
| `spot` | a place from the spot list (`library/environments/spots.json`). Same spot as the previous beat = the camera keeps travelling in one take; a new spot = a cut. |
| `people[].at` | slot: `center`, `left`, `right`, `far_left`, `far_right`, `back`, `back_left`, `back_right`, `front_left`, `front_right` (left/right = screen side; back = 1 m further from camera; front = 0.9 m closer). One person or prop per slot at a spot. |
| `people[].acts` | `[time, action, expression]` in time order. Actions: idle walk talk push point cross flex shrug slump bounce cheer tired tiredWalk wink lookSide think present proud eureka pull wave. Expressions: neutral happy fake sad smirk worried surprised closed wink angry smug tired proud rage grin shock (rage/grin/shock = peaks only). |
| `people[].look` | `"cam"` (talks to the viewer: hook, "you see", the wink), a role in the same beat, or `"auto"` (looks at the nearest person). |
| `people[].walk` | optional: `{"to": slot, "start": time, "seconds": 0.6-4}` — walks from `at` to `to`. |
| `people[].talk` | optional `true`: the mouth moves (quoted lines). |
| `props[]` | `{"name": "chest", "model": "<pack/model>", "at": slot, "turn": degrees, "scale": 1}`. Models: `library/environments/MODELS.md`. A prop belongs to its **scene** (the run of beats at one spot): it is there from the scene's first beat until the camera cuts to another spot. Need it again later? Declare it again in that scene. Big props (> 1.5 m) only in back slots. |
| `camera[]` | keys of the take. `on`: what to frame — roles, `"arms:<role>"` (gesture framing), `"hand:<role>"`, `"prop:<name>"`. `size`: ECU CU MCU MS FS WS EWS (not wider than the spot allows). `angle`: -75..75 degrees around the subject (0 = straight on, + = camera swings right). `height`: -10..45 degrees (4 = eye level, 8-15 = looking down, negative = low angle hero shot). Optional: `fov` 25-60 (default 40), `push` 1.0-1.2 (creep-in, default 1.05), `move` arc / pullpush / pan / dolly / whip (how the camera travels INTO this key, default arc), `roll` degrees (drama only). |
| time | `"start"` (beat start), `"word:<word>"` (when that word is spoken; `"word:it#2"` = its 2nd time in the beat) or seconds from the beat start (`1.5`). Words must be words of THAT beat. |
| `sfx` | `[time, sound]`: whoosh pop thud tick shutter scribble boom ding paper step sting. Few and meaningful (a reveal, an impact, the twist). |
| `cut` | `true` = hard cut even at the same spot (time jump, punchline). |
| `flash` | `true` = a white flash at the beat start (time jump, "next morning"). |
| `hit` | a time: a short camera kick on an impact (rare; calm channel). |

## Rules that make it good (from 02 / 03 / 06)
1. **Illustrate every line literally.** The picture shows what the words say: the joke lives in the props and the acting.
2. **One camera travels, it rarely cuts.** Stay at one spot for several beats so the camera keeps moving between people (push-in on the speaker, pull-back + arc to the next). Change spot only at a place or time change or a punchline. Aim for a cut every ~4 s on average, never under 3.
3. **Never hold still.** A beat longer than 3.5 s gets at least two camera keys; land each move ON the important word (`"at": "word:<noun or verb>"`). Keys are at least 0.8 s apart.
4. **Push-in is the default move** (~half of all moves), pull-back for reveals (~a quarter), then tilt/arc/pan.
5. **Vary sizes**: hook MS/MCU → FS/WS reveal → two-shot → MCU reaction → close on the key prop. Groups of 3+ people: FS, not WS (WS makes them tiny).
6. **Frame props with a person** (`"on": ["hero", "prop:gold"]`) unless the prop IS the hero object; a prop alone at MS fills the frame.
7. **Continuity inside a take**: a person who stays at the same spot keeps the slot where they ended (after a walk, their new slot). Add new people in free slots, not on top of others.
8. **Faces**: nobody in front of the subject (front slots block people behind them), no face cut by the frame, camera never inside walls — indoors (grocery_inside, workshop) stay at MS/MCU for groups, FS only for one person.
9. **Hook beat**: the strangest image of the story, framed MS or MCU, someone looks at the camera or does the strange action.
10. **Last beat**: the payoff lands on the final word (a push-in, a sting, the twist prop).
11. Cartoon magic is fine (a chair becomes a cart). Original characters only; no real logos.
12. **Props tell the line, nothing else.** 0-3 per scene, each the object the words name (money → coins/gold, a deal → a desk and papers, a heist → a safe or chest). No filler: no crate, plate or barrel unless the line is about it. One model in at most 2 scenes of the video; vary them. Scale 1 is the right size next to a person — change it only for a joke (giant coin).
