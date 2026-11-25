#!/usr/bin/env python3
"""ENGINE tool: a JSON shot plan -> the story files of one video (stage.ts, takes.ts, set.tsx, solids.ts, look.ts).
usage: python3 plan.py <plan.json> <src/videos/<id>>        (timeline.ts must already be there: see timeline.py)
  -> prints PROBLEMS (must be fixed) and WARNINGS (kit rules a good plan follows); writes the files when there are no problems.

The plan is the director's shot list in data form (references/09_PLAN_FORMAT.md), so any model can write a video without
writing code. It compiles 1:1 onto the kit's own API: people = PersonP + seq(), camera = continuous TAKES of K() keys
(03_CAMERA_GRAMMAR), sets = kits/grocery + kits/downtown + KayKit models. The kit's gates (06_CHECKS) still decide."""
import json, math, pathlib, re, sys, unicodedata

CODE = pathlib.Path(__file__).resolve().parents[3]          # .../code
SKILL = CODE.parent                                          # .../animated-shorts-kit
ENGINE = CODE / 'src' / 'engine'

SIZES = ['ECU', 'CU', 'MCU', 'MS', 'FS', 'WS', 'EWS']
MOVES = ['arc', 'pullpush', 'pan', 'dolly', 'whip']
SFX = ['whoosh', 'pop', 'thud', 'tick', 'shutter', 'scribble', 'boom', 'ding', 'paper', 'step', 'sting']
# stage slots, in metres relative to the spot: x = to the right of frame, z = toward the camera
SLOTS = {'center': (0, 0), 'left': (-1.1, 0), 'right': (1.1, 0), 'far_left': (-2.2, 0), 'far_right': (2.2, 0),
         'back': (0, -1.0), 'back_left': (-0.75, -1.0), 'back_right': (0.75, -1.0),
         'front_left': (-0.8, 0.9), 'front_right': (0.8, 0.9)}
MAX_PROP_HALF = 0.75     # a prop bigger than this (half width, m) only fits a back slot
PACK_SCALE = {'city': 3.3, 'furniture': 0.45, 'restaurant': 0.45, 'dungeon': 0.33}   # = engine/kits/models/Model.tsx


def _union(path, name):
    """string-union members of `export type <name> = 'a' | 'b' ...` in a TS file (the engine stays the single source)"""
    src = (ENGINE / path).read_text(encoding='utf-8')
    m = re.search(r'export type ' + name + r' = (.*?);', src, re.S)
    return re.findall(r"'(\w+)'", m.group(1))


ACTS = _union('chars/rig.tsx', 'ActName')
WHO = _union('chars/charparts.ts', 'Who')
EXPR = _union('chars/charparts.ts', 'Expr')
SPOTS = {k: v for k, v in json.loads((SKILL / 'library' / 'environments' / 'spots.json').read_text()).items() if not k.startswith('_')}
MODEL_INDEX = json.loads((CODE / 'public' / 'models' / 'index.json').read_text())


def _model_sizes():
    out, pack = {}, None
    for line in (CODE / 'public' / 'models' / 'CATALOG.md').read_text().splitlines():
        m = re.match(r'## (\w+)', line)
        if m:
            pack = m.group(1); continue
        if pack and line.strip() and not line.startswith('#'):
            for name, w, h, d in re.findall(r'(\w+) ([\d.]+)x([\d.]+)x([\d.]+)', line):
                out[f'{pack}/{name}'] = (float(w), float(h), float(d))
    return out


MODEL_SIZE = _model_sizes()


def norm(s):
    return ''.join(c for c in s.lower() if c == "'" or unicodedata.category(c)[0] in 'LMN')


def read_timeline(vdir):
    """beats from the generated timeline.ts: [{name, start, end, words: [[w, s, e], ...]}]"""
    src = (pathlib.Path(vdir) / 'timeline.ts').read_text(encoding='utf-8')
    grab = lambda n: json.loads(re.search(r'export const ' + n + r'\b[^=]*= (.*);', src).group(1))
    words, real, end = grab('WORDS'), grab('SHOT_REAL'), float(re.search(r'END_REAL = ([\d.]+)', src).group(1))
    names = sorted(real, key=real.get)
    beats = []
    for i, n in enumerate(names):
        a, b = real[n], real[names[i + 1]] if i + 1 < len(names) else end
        beats.append({'name': n, 'start': a, 'end': b, 'words': [w for w in words if a - 0.01 <= w[1] < b - 0.01]})
    return beats


def beat_name(i):
    return f'b{i + 1:02d}'


class Plan:
    def __init__(self, plan, beats):
        self.plan, self.beats = plan, beats
        self.problems, self.warnings = [], []
        self.cast = {}
        self.people_at = {}      # spot -> {slot: owner} for the whole video (the world stays the same between beats)
        self.props = []          # [{name, model, p, ry, s, size}]
        self.sfx = []            # [[seconds, name]]
        self.keyref = []         # (beat, camera key) of every emitted K(), in order
        self.keymap = {}         # take name -> [[beat, camera key], ...]: gates report keys as <take><index>

    # ---------- helpers ----------
    def bad(self, where, msg):
        self.problems.append(f'{where}: {msg}')

    def warn(self, where, msg):
        self.warnings.append(f'{where}: {msg}')

    def place(self, spot, slot):
        s = SPOTS[spot]; x, z = SLOTS[slot]
        a = math.radians(s['az'])                       # camera side; screen right = (cos a, 0, -sin a), toward camera = (sin a, 0, cos a)
        return [round(s['p'][0] + x * math.cos(a) + z * math.sin(a), 3), 0, round(s['p'][2] - x * math.sin(a) + z * math.cos(a), 3)]

    def time(self, where, t, bi, kind):
        """'start' | 'word:X' | 'word:X#2' | seconds (number) -> TS expression.
        kind 'local' = frames since the beat start (staging), 'real' = voice seconds (camera)."""
        b, name = self.beats[bi], beat_name(bi)
        if t in (None, 'start', 0):
            return '0' if kind == 'local' else f'R.{name}'
        if isinstance(t, (int, float)):
            if not 0 <= t < b['end'] - b['start']:
                self.bad(where, f'{t} s is outside this beat (it lasts {b["end"] - b["start"]:.1f} s)')
            return str(round(t * 30)) if kind == 'local' else f'R.{name} + {round(t, 2)}'
        m = re.fullmatch(r'word:(.+?)(?:#(\d+))?', str(t).strip())
        if not m:
            self.bad(where, f'time {t!r} must be "start", "word:<a word of this beat>" or seconds'); return '0'
        w, n = m.group(1), int(m.group(2) or 1)
        hits = [x for x in b['words'] if norm(x[0]) == norm(w)]
        if len(hits) < n:
            self.bad(where, f'"{w}" is not a word of this beat (its words: {" ".join(x[0] for x in b["words"])})')
            return '0'
        if kind == 'local':
            return f"W('{name}', {json.dumps(w)})" if n == 1 else str(round((hits[n - 1][1] - b['start']) * 30))
        return f"T('{name}', {json.dumps(w)}{', ' + str(n) if n > 1 else ''})"

    def seconds(self, t, bi):
        """the same time in voice seconds (for sound cues)"""
        b = self.beats[bi]
        if t in (None, 'start', 0):
            return b['start']
        if isinstance(t, (int, float)):
            return b['start'] + t
        m = re.fullmatch(r'word:(.+?)(?:#(\d+))?', str(t).strip())
        hits = [x for x in b['words'] if m and norm(x[0]) == norm(m.group(1))]
        n = int(m.group(2) or 1) if m else 1
        return hits[n - 1][1] if len(hits) >= n else b['start']

    # ---------- passes ----------
    def check_cast(self):
        cast = self.plan.get('cast') or {}
        if not isinstance(cast, dict) or not cast:
            self.bad('cast', 'give a cast: {"role": "<character id>"}'); return
        seen = {}
        for role, who in cast.items():
            if who not in WHO:
                self.bad(f'cast {role}', f'unknown character {who!r} (choose from: {", ".join(WHO)})'); continue
            if who in seen:
                self.bad(f'cast {role}', f'{who} already plays {seen[who]}: every role needs its own character'); continue
            seen[who] = role
            self.cast[role] = who

    def check_props(self):
        """props are part of the world: placed once, they stay for the whole video"""
        names = set()
        for bi, beat in enumerate(self.plan['beats']):
            for k, pr in enumerate(beat.get('props') or []):
                where = f'beat {bi + 1} prop {k + 1}'
                name, model, slot, spot = pr.get('name', ''), pr.get('model', ''), pr.get('at', 'back'), beat.get('spot')
                if not re.fullmatch(r'[a-z][a-z0-9_]{0,20}', name or ''):
                    self.bad(where, 'name must be a short lowercase id like "chest"'); continue
                if name in names:
                    self.bad(where, f'prop name {name!r} is used twice'); continue
                if model not in MODEL_INDEX:
                    self.bad(where, f'unknown model {model!r} (see MODELS.md)'); continue
                if slot not in SLOTS or spot not in SPOTS:
                    continue   # reported by the beat pass
                k_ = PACK_SCALE[model.split('/')[0]] * float(pr.get('scale', 1))
                w, h, d = (v * k_ for v in MODEL_SIZE.get(model, (1, 1, 1)))
                if max(w, d) / 2 > MAX_PROP_HALF and not slot.startswith('back'):
                    self.bad(where, f'{model} is {max(w, d):.1f} m wide: put it in a back slot or lower its scale')
                if (spot, slot) in self.people_at:
                    self.bad(where, f'slot {slot} at {spot} already holds {self.people_at[(spot, slot)]}'); continue
                self.people_at[(spot, slot)] = 'prop ' + name
                names.add(name)
                self.props.append({'name': name, 'model': model, 'p': self.place(spot, slot), 'ry': math.radians(float(pr.get('turn', 0))),
                                   's': float(pr.get('scale', 1)), 'size': (w, h, d), 'beat': bi})

    def stage_beat(self, bi, beat):
        name, where0, out, here = beat_name(bi), f'beat {bi + 1}', [], {}
        spot = beat.get('spot')
        if spot not in SPOTS:
            self.bad(where0, f'unknown spot {spot!r} (choose from: {", ".join(SPOTS)})'); return out, here
        people = beat.get('people') or []
        if not people and not beat.get('props'):
            self.warn(where0, 'nobody and nothing to look at: give the camera a subject')
        used = {}
        for k, pp in enumerate(people):
            where = f'{where0} person {k + 1}'
            role, slot = pp.get('role'), pp.get('at', 'center')
            if role not in self.cast:
                self.bad(where, f'role {role!r} is not in the cast'); continue
            if role in here:
                self.bad(where, f'{role} appears twice in one beat'); continue
            if slot not in SLOTS:
                self.bad(where, f'unknown slot {slot!r} (choose from: {", ".join(SLOTS)})'); continue
            owner = used.get(slot) or (self.people_at.get((spot, slot)) if str(self.people_at.get((spot, slot), '')).startswith('prop') else None)
            if owner:
                self.bad(where, f'slot {slot} is taken by {owner}'); continue
            used[slot] = role
            p0 = self.place(spot, slot)
            here[role] = p0
            acts = pp.get('acts') or [['start', 'idle', 'neutral']]
            items, last = [], -1
            for j, a in enumerate(acts):
                if not isinstance(a, list) or len(a) not in (2, 3):
                    self.bad(f'{where} act {j + 1}', 'each act is ["<time>", "<action>", "<expression>"]'); continue
                act, expr = a[1], a[2] if len(a) == 3 else 'neutral'
                if act not in ACTS:
                    self.bad(f'{where} act {j + 1}', f'unknown action {act!r} (choose from: {", ".join(ACTS)})'); continue
                if expr not in EXPR:
                    self.bad(f'{where} act {j + 1}', f'unknown expression {expr!r} (choose from: {", ".join(EXPR)})'); continue
                t = self.time(f'{where} act {j + 1}', a[0], bi, 'local')
                tv = self.seconds(a[0], bi)
                if tv < last:
                    self.bad(f'{where} act {j + 1}', 'acts must be in time order')
                last = tv
                items.append(f"[{t}, '{act}', '{expr}']")
            q = f"seq(lf, [{', '.join(items) or "[0, 'idle', 'neutral']"}])"
            extra = []
            look = pp.get('look', 'auto')
            if look == 'cam':
                extra.append("gaze: 'cam'")
            elif look not in (None, 'auto'):
                if look not in (x.get('role') for x in people):
                    self.bad(where, f'look {look!r} must be "cam", "auto" or a role in this beat')
                else:
                    tgt = next(x for x in people if x.get('role') == look)
                    if tgt.get('at', 'center') in SLOTS:
                        tp = self.place(spot, tgt.get('at', 'center'))
                        extra.append(f'gaze: [{tp[0]}, 1, {tp[2]}]')
            if pp.get('talk'):
                extra.append('talk: true')
            ex = ''.join(', ' + e for e in extra)
            walk = pp.get('walk')
            if walk:
                to = walk.get('to')
                if to not in SLOTS:
                    self.bad(f'{where} walk', f'unknown slot {to!r}'); continue
                if to in used and used[to] != role:
                    self.bad(f'{where} walk', f'slot {to} is taken by {used[to]}'); continue
                p1, secs = self.place(spot, to), float(walk.get('seconds', 1.5))
                if not 0.6 <= secs <= 4:
                    self.bad(f'{where} walk', 'seconds must be 0.6-4')
                t0 = self.time(f'{where} walk', walk.get('start', 'start'), bi, 'local')
                used[to] = role
                here[role] = p1
                out.append(f"{{ const [p, w] = go(lf, {p0}, {p1}, {t0}, {round(secs * 30)}); P.push({{who: '{self.cast[role]}', p, ...walking({q}, w){ex}}}); }}")
            else:
                out.append(f"P.push({{who: '{self.cast[role]}', p: {p0}, ...{q}{ex}}});")
        return out, here

    def camera_beat(self, bi, beat, here, new_take):
        name, where0, keys = beat_name(bi), f'beat {bi + 1}', []
        spot = SPOTS.get(beat.get('spot'))
        cam = beat.get('camera') or []
        if not cam:
            self.bad(where0, 'needs at least one camera key'); return keys
        b = self.beats[bi]
        if b['end'] - b['start'] > 3.5 and len(cam) < 2:
            self.warn(where0, f'one camera key for {b["end"] - b["start"]:.1f} s: add a move on a word (kit: a move every ~2 s, never hold still)')
        props = {p['name'] for p in self.props}
        last = None
        for k, c in enumerate(cam):
            where = f'{where0} camera {k + 1}'
            at = c.get('at', 'start')
            if k == 0 and new_take and at not in (None, 'start', 0):
                self.bad(where, 'a new take (cut) starts at "start"'); at = 'start'
            subs = []
            for s in c.get('on') or []:
                kind, _, arg = s.rpartition(':') if ':' in s else ('', '', s)
                if kind in ('', 'arms', 'hand'):
                    if arg not in here:
                        self.bad(where, f'{arg!r} is not on stage in this beat'); continue
                    subs.append((kind + ':' if kind else '') + self.cast[arg])
                elif kind == 'prop':
                    if arg not in props:
                        self.bad(where, f'prop {arg!r} does not exist'); continue
                    subs.append('prop:' + arg)
                else:
                    self.bad(where, f'subject {s!r}: use a role, "arms:<role>", "hand:<role>" or "prop:<name>"')
            if not subs:
                self.bad(where, 'needs "on": [what the camera frames]'); continue
            size = c.get('size', 'MS')
            if size not in SIZES:
                self.bad(where, f'size must be one of {SIZES}'); continue
            if spot and SIZES.index(size) > SIZES.index(spot['max']):
                self.bad(where, f'{size} does not fit at {beat["spot"]} (widest: {spot["max"]})')
            ang, el, fov, push = float(c.get('angle', 0)), float(c.get('height', 4)), float(c.get('fov', 40)), float(c.get('push', 1.05))
            if not -75 <= ang <= 75: self.bad(where, 'angle must be -75..75')
            if not -10 <= el <= 45: self.bad(where, 'height must be -10..45')
            if not 25 <= fov <= 60: self.bad(where, 'fov must be 25..60')
            if not 1.0 <= push <= 1.2: self.bad(where, 'push must be 1.0..1.2')
            t = self.time(where, at, bi, 'real')
            tv = self.seconds(at, bi)
            opts = [f'push: {push}']
            if not (new_take and k == 0):
                mv = c.get('move', 'arc')
                if mv not in MOVES:
                    self.bad(where, f'move must be one of {MOVES}'); mv = 'arc'
                opts += [f"move: '{mv}'", 'lead: 0.3', f"dur: {0.3 if mv == 'whip' else 0.8}"]
                if last is not None and tv - last < 0.8:
                    self.bad(where, f'only {tv - last:.2f} s after the previous key: keys need 0.8 s (one move = 0.6-1 s)')
            if c.get('roll'):
                opts.append(f"roll: {float(c['roll'])}")
            if size in ('ECU',):
                opts.append('ecu: true')
            last = tv
            az = (spot['az'] if spot else 0) + ang
            sub = json.dumps(subs[0]) if len(subs) == 1 else json.dumps(subs)
            self.keyref.append((bi + 1, k + 1))
            keys.append(f"K({t}, {sub}, '{size}', {round(az, 1)}, {round(el, 1)}, {round(fov, 1)}, {{{', '.join(opts)}}})")
        return keys

    def compile(self):
        P = self.plan
        if not isinstance(P, dict) or not isinstance(P.get('beats'), list):
            return self._fail('the plan must be {"cast": {...}, "beats": [...]}')
        if len(P['beats']) != len(self.beats):
            return self._fail(f'the plan has {len(P["beats"])} beats, the script has {len(self.beats)}: one beat per script line')
        self.check_cast()
        self.check_props()
        cases, takes, flashes, kicks = [], [], [], []
        prev_spot = None
        for bi, beat in enumerate(P['beats']):
            name = beat_name(bi)
            lines, here = self.stage_beat(bi, beat)
            cases.append(f"    case '{name}': {{\n      " + '\n      '.join(lines) + '\n      break;\n    }')
            new_take = bi == 0 or beat.get('cut') is True or beat.get('spot') != prev_spot
            n0 = len(self.keyref)
            keys = self.camera_beat(bi, beat, here, new_take)
            if new_take:
                self.keymap[name] = []
            self.keymap[list(self.keymap)[-1]] += [list(r) for r in self.keyref[n0:]]
            if new_take:
                takes.append({'name': name, 'why': str(beat.get('why', ''))[:120], 'keys': keys})
            else:
                takes[-1]['keys'] += keys
            if beat.get('flash'):
                flashes.append(f'{{t: R.{name}, a: 1}}')
            if beat.get('hit'):
                kicks.append(f"{{t: {self.time(f'beat {bi + 1} hit', beat['hit'], bi, 'real')}, a: 1, z: 0.02}}")
            for j, s in enumerate(beat.get('sfx') or []):
                if not isinstance(s, list) or len(s) != 2 or s[1] not in SFX:
                    self.bad(f'beat {bi + 1} sfx {j + 1}', f'each sound is ["<time>", "<one of {", ".join(SFX)}>"]'); continue
                self.time(f'beat {bi + 1} sfx {j + 1}', s[0], bi, 'real')
                self.sfx.append([round(self.seconds(s[0], bi), 3), s[1]])
            prev_spot = beat.get('spot')
        n = len(takes)
        if n and (self.beats[-1]['end'] / n) < 3.0:
            self.warn('takes', f'{n} takes in {self.beats[-1]["end"]:.0f} s (average {self.beats[-1]["end"] / n:.1f} s): the kit aims for ~4 s, cut only on a place/time change or a punchline')
        if self.problems:
            return None
        return {'stage.ts': self._stage(cases), 'takes.ts': self._takes(takes, flashes, kicks), 'set.tsx': self._set(),
                'solids.ts': self._solids(), 'look.ts': (CODE / 'src/videos/_template/look.ts').read_text(),
                'tsconfig.json': (CODE / 'src/videos/_template/tsconfig.json').read_text(), 'ENGINE': 'engine v1\n',
                'sfx.json': json.dumps(self.sfx), 'keymap.json': json.dumps(self.keymap)}

    def _fail(self, msg):
        self.problems.append(msg); return None

    # ---------- writers ----------
    def _stage(self, cases):
        return f"""// GENERATED by engine/tools/plan.py from plan.json: edit the plan, not this file.
import {{TOTAL, shotAt, W, type V3}} from '../../engine/core/clock';
import {{autoGaze}} from '../../engine/core/staging';
import {{PersonP, seq}} from '../../engine/chars/rig';
import type {{CarP, MeterP, Things}} from '../../engine/kits/downtown/street';
import type {{CartP}} from '../../engine/kits/grocery/store';
export {{TOTAL, shotAt}};
export type Stage = {{people: PersonP[]; carts: CartP[]; extra: string[]; cars: CarP[]; meters: MeterP[]; things: Things; clock: number; nStoryCars: number}};
const sm = (u: number) => (u <= 0 ? 0 : u >= 1 ? 1 : u * u * (3 - 2 * u));
/** walk from a to b: starts at local frame f0, takes n frames -> [position, walking now] */
const go = (lf: number, a: V3, b: V3, f0: number, n: number): [V3, boolean] => {{ const u = sm((lf - f0) / n); return [[a[0] + (b[0] - a[0]) * u, 0, a[2] + (b[2] - a[2]) * u], lf > f0 && lf < f0 + n]; }};
const walking = (q: ReturnType<typeof seq>, w: boolean) => (w ? {{...q, act: 'walk' as const, from: undefined, k: 1}} : q);
export function stage(f: number): Stage {{
  const s = shotAt(f), lf = s.lf, P: PersonP[] = [];
  switch (s.name) {{
{chr(10).join(cases)}
  }}
  autoGaze(P, []);
  return {{people: P, carts: [], extra: [], cars: [], meters: [], things: {{}}, clock: 9 + f / 30 / 120, nStoryCars: 0}};
}}
"""

    def _takes(self, takes, flashes, kicks):
        props = ',\n  '.join(f"{p['name']}: [[{p['p'][0]}, {round(p['size'][1] / 2, 3)}, {p['p'][2]}], [{round(p['size'][0] / 2, 3)}, {round(p['size'][1] / 2, 3)}, {round(p['size'][2] / 2, 3)}]]"
                             for p in self.props)
        tk = ',\n  '.join(f"{{name: '{t['name']}', why: {json.dumps(t['why'])}, keys: [\n    " + ',\n    '.join(t['keys']) + ']}' for t in takes)
        return f"""// GENERATED by engine/tools/plan.py from plan.json: edit the plan, not this file.
import {{K, type Take, type Kick, type Whip, type Flash, type Props}} from '../../engine/camera/takes_api';
import {{T}} from '../../engine/core/clock';
import {{SHOT_REAL as R}} from './timeline';
export const PROPS: Props = {{
  {props}
}};
export const TAKES: Take[] = [
  {tk}
];
export const KICKS: Kick[] = [{', '.join(kicks)}];
export const WHIPS: Whip[] = [];
export const FLASHES: Flash[] = [{', '.join(flashes)}];
"""

    def _set(self):
        ms = ',\n  '.join(f"{{name: '{p['model']}', p: {p['p']}, ry: {round(p['ry'], 3)}, s: {p['s']}}}" for p in self.props)
        return f"""// GENERATED by engine/tools/plan.py from plan.json: edit the plan, not this file.
import React from 'react';
import * as THREE from 'three';
import type {{Tod}} from '../../engine/look/look';
import {{useMats, Set, type Mats}} from '../../engine/kits/grocery/store';
import {{Town, StreetClock}} from '../../engine/kits/downtown/town';
import {{Models, type ModelP}} from '../../engine/kits/models/Model';
import type {{Stage}} from './stage';
export const AUDIO: {{voice: string | null; bed: string | null}} = {{voice: null, bed: null}};   // the pipeline mixes the sound after the render
export const useSetData = () => useMats();
const MODELS: ModelP[] = [
  {ms}
];
type P = {{d: Mats; f: number; st: Stage; cam: THREE.Vector3; vel: (THREE.Vector3 | null)[]; tod: Tod}};
export const SetBefore: React.FC<P> = ({{d, f, st, tod}}) => (<>
  <Set m={{d}} f={{f}} /><Town tod={{tod}} /><StreetClock hours={{st.clock}} /><Models list={{MODELS}} />
</>);
export const SetAfter: React.FC<P> = () => null;
"""

    def _solids(self):
        boxes = ',\n  '.join(f"[{p['p'][0] - max(p['size'][0], p['size'][2]) / 2:.3f}, {p['p'][0] + max(p['size'][0], p['size'][2]) / 2:.3f}, 0, {p['size'][1]:.3f}, "
                             f"{p['p'][2] - max(p['size'][0], p['size'][2]) / 2:.3f}, {p['p'][2] + max(p['size'][0], p['size'][2]) / 2:.3f}, 'prop {p['name']}']" for p in self.props)
        return f"""// GENERATED by engine/tools/plan.py from plan.json: solids for the checkers (town + the plan's props) and gate waivers.
import {{townSolids}} from '../../engine/kits/downtown/townData';
import {{storeSolids}} from '../../engine/kits/grocery/storeData';
type Box = [number, number, number, number, number, number, string];
const PROP_SOLIDS: Box[] = [
  {boxes}
];
export const SOLIDS: Box[] = [...townSolids(), ...storeSolids(), ...PROP_SOLIDS];
export const LOGIC_SOLIDS: Box[] = [...townSolids(), ...storeSolids()].filter((b) => b[2] < 1.0 && !b[6].startsWith('far car')).concat(PROP_SOLIDS);
export const GATE_WAIVERS: {{key: string; kind: string; why: string}}[] = [];
"""


def compile_plan(plan, vdir):
    """-> (files or None, problems, warnings). Writes nothing."""
    p = Plan(plan, read_timeline(vdir))
    files = p.compile()
    return files, p.problems, p.warnings


def write(files, vdir):
    vdir = pathlib.Path(vdir)
    for name, text in files.items():
        (vdir / name).write_text(text, encoding='utf-8')
    (vdir / 'VERSION').write_text('v1\n')


if __name__ == '__main__':
    plan_path, vdir = sys.argv[1], sys.argv[2]
    files, problems, warnings = compile_plan(json.loads(pathlib.Path(plan_path).read_text(encoding='utf-8')), vdir)
    for w in warnings:
        print('WARNING', w)
    for q in problems:
        print('PROBLEM', q)
    if files:
        write(files, vdir)
        print('PLAN OK: wrote', ', '.join(files))
    sys.exit(1 if problems else 0)
