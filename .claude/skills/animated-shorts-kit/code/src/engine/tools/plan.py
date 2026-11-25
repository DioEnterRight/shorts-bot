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
# building parts are the sets' job, not props: as props they float as slabs (a lone wall, a window, a road tile)
MAX_MODEL_SCENES = 2   # one model in at most 2 scenes: the same crate in every shot reads as lazy
NOT_PROPS = re.compile(r'/(wall|floor|road|base|building|pillar|door|stairs|rubble|extractorhood|towelrail|kitchencounter|kitchencabinet)')
MODEL_INDEX = {k: v for k, v in json.loads((CODE / 'public' / 'models' / 'index.json').read_text()).items() if not NOT_PROPS.search(k)}


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


def scenes(spots):
    """beat -> scene id: a new scene starts whenever the spot changes (that is a cut)"""
    out, n = [], -1
    for i, sp in enumerate(spots):
        n += i == 0 or sp != spots[i - 1]
        out.append(f'{sp}#{n}')
    return out


def _live(p, keys=True):
    """a prop's old-frame window in TS: from its scene's first beat to the next scene"""
    a, b = p['live']
    f0, f1 = f"S('{a}')", f"S('{b}')" if b else '1e9'
    return f'f0: {f0}, f1: {f1}' if keys else f'{f0}, {f1}'


class Plan:
    def __init__(self, plan, beats, waivers=None):
        self.plan, self.beats, self.waivers = plan, beats, waivers or []
        self.problems, self.warnings = [], []
        self.cast = {}
        self.scene = scenes([b.get('spot') for b in plan['beats']])   # beat -> scene id (a run of beats at one spot)
        self.people_at = {}      # (scene, slot) -> prop owner: a prop stays for its scene
        self.props = []          # [{name, model, p, ry, s, size}]
        self.sfx = []            # [[seconds, name]]
        self.keyref = []         # (beat, camera key) of every emitted K(), in order
        self.keymap = {}         # take name -> [[beat, camera key], ...]: gates report keys as <take><index>

    # ---------- helpers ----------
    def scene_span(self, sc):
        """[first beat name, beat name after the scene or None]: the old-frame window a scene's props exist in"""
        idx = [i for i, s in enumerate(self.scene) if s == sc]
        return [beat_name(idx[0]), beat_name(idx[-1] + 1) if idx[-1] + 1 < len(self.scene) else None]

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
        """props belong to their scene (the run of beats at one spot): from its first beat to the cut away"""
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
                turn, az = float(pr.get('turn', 0)), SPOTS[spot]['az']   # turn is camera-relative: 0 faces the camera
                hw, hd = _prop_extent(model, float(pr.get('scale', 1)), turn)
                lim = BACK_HALF if slot.startswith('back') else (MAX_PROP_HALF, MAX_PROP_HALF)
                if hw > lim[0] + 0.01 or hd > lim[1] + 0.01:
                    self.bad(where, f'{model} is {2 * max(hw, hd):.1f} m wide: put it in a back slot or lower its scale')
                ww, wd = _prop_extent(model, float(pr.get('scale', 1)), turn + az)
                h = MODEL_SIZE.get(model, (1, 1, 1))[1] * k_
                w, d = ww * 2, wd * 2   # world-axis footprint
                if (self.scene[bi], slot) in self.people_at:
                    self.bad(where, f'slot {slot} at {spot} already holds {self.people_at[(self.scene[bi], slot)]}'); continue
                self.people_at[(self.scene[bi], slot)] = 'prop ' + name
                names.add(name)
                self.props.append({'name': name, 'model': model, 'p': self.place(spot, slot), 'ry': math.radians(turn + az),
                                   's': float(pr.get('scale', 1)), 'size': (w, h, d), 'beat': bi,
                                   'live': self.scene_span(self.scene[bi])})

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
            owner = used.get(slot) or self.people_at.get((self.scene[bi], slot))
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
        ms = ',\n  '.join(f"{{name: '{p['model']}', p: {p['p']}, ry: {round(p['ry'], 3)}, s: {p['s']}, {_live(p)}}}" for p in self.props)
        return f"""// GENERATED by engine/tools/plan.py from plan.json: edit the plan, not this file.
import React from 'react';
import * as THREE from 'three';
import type {{Tod}} from '../../engine/look/look';
import {{useMats, Set, type Mats}} from '../../engine/kits/grocery/store';
import {{Town, StreetClock}} from '../../engine/kits/downtown/town';
import {{Models, type ModelP}} from '../../engine/kits/models/Model';
import {{S}} from '../../engine/core/clock';
import type {{Stage}} from './stage';
export const AUDIO: {{voice: string | null; bed: string | null}} = {{voice: null, bed: null}};   // the pipeline mixes the sound after the render
export const useSetData = () => useMats();
const MODELS: (ModelP & {{f0: number; f1: number}})[] = [   // f0-f1: old frames of the prop's scene
  {ms}
];
type P = {{d: Mats; f: number; st: Stage; cam: THREE.Vector3; vel: (THREE.Vector3 | null)[]; tod: Tod}};
export const SetBefore: React.FC<P> = ({{d, f, st, tod}}) => (<>
  <Set m={{d}} f={{f}} /><Town tod={{tod}} /><StreetClock hours={{st.clock}} /><Models list={{MODELS.filter((m) => f >= m.f0 && f < m.f1)}} />
</>);
export const SetAfter: React.FC<P> = () => null;
"""

    def _solids(self):
        boxes = ',\n  '.join(f"[{p['p'][0] - p['size'][0] / 2:.3f}, {p['p'][0] + p['size'][0] / 2:.3f}, 0, {p['size'][1]:.3f}, "
                             f"{p['p'][2] - p['size'][2] / 2:.3f}, {p['p'][2] + p['size'][2] / 2:.3f}, 'prop {p['name']}', [{_live(p, False)}]]" for p in self.props)
        return f"""// GENERATED by engine/tools/plan.py from plan.json: solids for the checkers (town + the plan's props) and gate waivers.
import {{townSolids}} from '../../engine/kits/downtown/townData';
import {{storeSolids}} from '../../engine/kits/grocery/storeData';
import {{S}} from '../../engine/core/clock';
type Box = [number, number, number, number, number, number, string, [number, number]?];   // optional: old-frame window (a scene's prop)
const PROP_SOLIDS: Box[] = [
  {boxes}
];
export const SOLIDS: Box[] = [...townSolids(), ...storeSolids(), ...PROP_SOLIDS];
export const LOGIC_SOLIDS: Box[] = [...townSolids(), ...storeSolids()].filter((b) => b[2] < 1.0 && !b[6].startsWith('far car')).concat(PROP_SOLIDS);
export const GATE_WAIVERS: {{key: string; kind: string; why: string}}[] = {json.dumps(self.waivers)};
"""


# ---------------------------------------------------------------- normalizer
# The director is a language model: it misspells names, reuses slots, puts keys 0.4 s apart. Everything that has ONE
# obvious repair is repaired here and reported as a FIX (the plan stays the director's; only mistakes change). What is
# left for the director are real staging choices, which the kit's gates judge.
import copy
import difflib

FREE_ORDER = ['center', 'left', 'right', 'far_left', 'far_right', 'back', 'back_left', 'back_right', 'front_left', 'front_right']


def _closest(word, options, cutoff=0.55):
    w = str(word or '').strip().lower()
    if w in options:
        return w
    m = difflib.get_close_matches(w, list(options), n=1, cutoff=cutoff)
    return m[0] if m else None


def _nearest_free(want, taken, allowed=None):
    """the free slot closest to `want` (by stage distance)"""
    wx, wz = SLOTS.get(want, (0, 0))
    free = [k for k in (allowed or SLOTS) if k not in taken]
    return min(free, key=lambda k: (math.hypot(SLOTS[k][0] - wx, SLOTS[k][1] - wz), FREE_ORDER.index(k))) if free else None


def _model(name):
    name = str(name or '').strip().replace(' ', '_')
    if NOT_PROPS.search('/' + name.split('/')[-1].lower()):
        return None   # a building part: dropped, never fuzzy-matched to something else
    if name in MODEL_INDEX:
        return name
    low = {k.lower(): k for k in MODEL_INDEX}
    if name.lower() in low:
        return low[name.lower()]
    name = name.lower()
    m = _closest(name, MODEL_INDEX, 0.6)
    if m:
        return m
    base = {k.split('/')[1]: k for k in MODEL_INDEX}
    m = _closest(name.split('/')[-1], base, 0.6)
    return base[m] if m else None


def _prop_extent(model, scale, turn=0):
    """half width / half depth on the floor (metres), after scale and turn"""
    w, _, d = (v * PACK_SCALE[model.split('/')[0]] * scale / 2 for v in MODEL_SIZE.get(model, (1, 1, 1)))
    c, s_ = abs(math.cos(math.radians(turn))), abs(math.sin(math.radians(turn)))
    return c * w + s_ * d, s_ * w + c * d


def _prop_half(model, scale, turn=0):
    return max(_prop_extent(model, scale, turn))


BACK_HALF = (1.2, 0.6)   # what fits in a back slot (half width, half depth) without reaching the front row


def normalize(plan, beats):
    """-> (clean plan, fixes). Never raises on content; only a plan with no usable shape returns (None, [reason])."""
    fixes = []
    fix = lambda where, msg: fixes.append(f'{where}: {msg}')
    if isinstance(plan, list):
        plan = {'beats': plan}
    if not isinstance(plan, dict) or not isinstance(plan.get('beats'), list) or not plan['beats']:
        return None, ['the plan must be {"cast": {...}, "beats": [...]}']
    P = copy.deepcopy(plan)
    B = [b if isinstance(b, dict) else {} for b in P['beats']]
    n = len(beats)
    if len(B) > n:
        fix('beats', f'{len(B)} beats for {n} script lines: dropped the extra ones'); B = B[:n]
    while len(B) < n:
        fix('beats', f'beat {len(B) + 1} was missing: continues the previous beat')
        prev = copy.deepcopy(B[-1]) if B else {}
        B.append({'spot': prev.get('spot', 'street'), 'people': prev.get('people', []),
                  'camera': [{'at': 'start', 'on': [p['role'] for p in prev.get('people', []) if isinstance(p, dict) and p.get('role')][:1] or [], 'size': 'MS'}]})

    # ---- cast: roles -> unique, real characters
    cast, used = {}, set()
    for role, who in (P.get('cast') or {}).items() if isinstance(P.get('cast'), dict) else []:
        cast[str(role)] = who
    for b in B:   # roles used in beats but missing from the cast
        for p in b.get('people') or []:
            if isinstance(p, dict) and p.get('role') and p['role'] not in cast:
                cast[p['role']] = p['role']
    clean_cast = {}
    for role, who in cast.items():
        w = who if who in WHO else _closest(who, WHO)
        if w is None or w in used:
            w2 = next((x for x in WHO if x not in used), None)
            if w2 is None:
                fix(f'cast {role}', 'no characters left: role dropped'); continue
            fix(f'cast {role}', f'{who!r} {"is taken" if w in used else "is not a character"}: plays {w2}'); w = w2
        elif w != who:
            fix(f'cast {role}', f'{who!r} -> {w}')
        used.add(w); clean_cast[role] = w

    # ---- props first pass: which slots people use at each spot (people keep their slots, props move)
    spots_of = []
    for i, b in enumerate(B):
        sp = b.get('spot')
        s2 = sp if sp in SPOTS else _closest(sp, SPOTS, 0.5) or (spots_of[-1] if spots_of else 'street')
        if s2 != sp:
            fix(f'beat {i + 1}', f'spot {sp!r} -> {s2}')
        spots_of.append(s2)
    scene_of = scenes(spots_of)   # props live in one scene (a run of beats at one spot), not the whole video
    person_slots = {}
    for i, b in enumerate(B):
        for p in b.get('people') or []:
            if isinstance(p, dict):
                for k in (p.get('at'), (p.get('walk') or {}).get('to') if isinstance(p.get('walk'), dict) else None):
                    if k in SLOTS:
                        person_slots.setdefault(scene_of[i], set()).add(k)

    # props first (all beats): a prop stays for its whole scene, so people of every beat of that scene must see it
    prop_at, prop_names, props_of, renames, model_scenes = {}, set(), [], [], {}
    for i, b in enumerate(B):
        where0, spot = f'beat {i + 1}', spots_of[i]
        # props
        rename, props = {}, []
        for j, pr in enumerate(b.get('props') or []):
            if not isinstance(pr, dict):
                continue
            where = f'{where0} prop {j + 1}'
            model = _model(pr.get('model'))
            if not model:
                fix(where, f'unknown model {pr.get("model")!r}: dropped'); continue
            if model != pr.get('model'):
                fix(where, f'model {pr.get("model")!r} -> {model}')
            seen = model_scenes.setdefault(model, set())
            if scene_of[i] not in seen and len(seen) >= MAX_MODEL_SCENES:
                fix(where, f'{model} is already in {len(seen)} scenes: dropped (vary the props)'); continue
            seen.add(scene_of[i])
            raw = re.sub(r'[^a-z0-9_]', '_', str(pr.get('name') or model.split('/')[1]).lower()).strip('_') or 'prop'
            name = re.sub(r'^[^a-z]+', '', raw)[:18] or 'prop'
            base, c = name, 2
            while name in prop_names:
                name = f'{base}_{c}'; c += 1
            if name != pr.get('name'):
                fix(where, f'name {pr.get("name")!r} -> {name}')
            rename[str(pr.get('name'))] = name
            try:
                scale = min(3.0, max(0.2, float(pr.get('scale', 1))))
            except (TypeError, ValueError):
                scale = 1.0
            try:
                turn = float(pr.get('turn', 0))
            except (TypeError, ValueError):
                turn = 0
            want = pr.get('at') if pr.get('at') in SLOTS else 'back'
            taken = set(prop_at.get(scene_of[i], {})) | person_slots.get(scene_of[i], set())
            big = _prop_half(model, scale, turn) > MAX_PROP_HALF
            allowed = [k for k in SLOTS if k.startswith('back')] if big else None
            slot = want if want not in taken and (not big or want.startswith('back')) else _nearest_free(want, taken, allowed)
            if slot is None and big:
                slot = _nearest_free(want, taken)
            if slot is None:
                fix(where, f'no free slot left at {spot}: {name} dropped'); continue
            hw, hd = _prop_extent(model, scale, turn)
            lim = BACK_HALF if slot.startswith('back') else (MAX_PROP_HALF, MAX_PROP_HALF)
            if hw > lim[0] or hd > lim[1]:
                s0 = scale; scale = round(scale * min(lim[0] / hw, lim[1] / hd), 2)
                fix(where, f'{model} is too big for slot {slot}: scale {s0} -> {scale}')
            if slot != pr.get('at'):
                fix(where, f'slot {pr.get("at")!r} -> {slot}' + (' (taken)' if pr.get('at') in taken else ''))
            prop_at.setdefault(scene_of[i], {})[slot] = name
            prop_names.add(name)
            props.append({'name': name, 'model': model, 'at': slot, 'turn': turn, 'scale': scale})
        props_of.append(props)
        renames.append(rename)

    clean_beats = []
    for i, b in enumerate(B):
        where0, spot = f'beat {i + 1}', spots_of[i]
        b2 = {'spot': spot}
        for k in ('why',):
            if b.get(k):
                b2[k] = str(b[k])[:120]
        b2['cut'] = b.get('cut') is True
        b2['flash'] = b.get('flash') is True
        props, rename = props_of[i], renames[i]
        b2['props'] = props
        # people
        people, here = [], {}
        taken = set(prop_at.get(scene_of[i], {}))
        for j, p in enumerate(b.get('people') or []):
            if not isinstance(p, dict):
                continue
            where = f'{where0} person {j + 1}'
            role = p.get('role')
            if role not in clean_cast:
                fix(where, f'role {role!r} has no character: dropped'); continue
            if role in here:
                fix(where, f'{role} twice in one beat: second one dropped'); continue
            want = p.get('at') if p.get('at') in SLOTS else (_closest(p.get('at'), SLOTS, 0.5) or 'center')
            slot = want if want not in taken else _nearest_free(want, taken)
            if slot is None:
                fix(where, f'no free slot: {role} dropped'); continue
            if slot != p.get('at'):
                fix(where, f'slot {p.get("at")!r} -> {slot}')
            taken.add(slot)
            q = {'role': role, 'at': slot}
            acts = []
            for a in p.get('acts') or []:
                if isinstance(a, (list, tuple)) and len(a) in (2, 3):
                    act = a[1] if a[1] in ACTS else _closest(a[1], ACTS) or 'idle'
                    ex = (a[2] if len(a) == 3 else 'neutral')
                    ex = ex if ex in EXPR else _closest(ex, EXPR) or 'neutral'
                    if act != a[1] or (len(a) == 3 and ex != a[2]):
                        fix(where, f'act {list(a)} -> [{act}, {ex}]')
                    acts.append([_fix_time(a[0], beats[i], fix, where), act, ex])
            acts.sort(key=lambda a: _secs(a[0], beats[i]))
            q['acts'] = acts or [['start', 'idle', 'neutral']]
            q['look'] = p.get('look', 'auto')
            if p.get('talk'):
                q['talk'] = True
            w = p.get('walk')
            if isinstance(w, dict) and w.get('to'):
                to = w['to'] if w['to'] in SLOTS else _closest(w['to'], SLOTS, 0.5)
                if to is None or to in taken or to == slot:
                    fix(where, f'walk to {w.get("to")!r} is not possible here: dropped')
                else:
                    try:
                        secs = min(4.0, max(0.6, float(w.get('seconds', 1.5))))
                    except (TypeError, ValueError):
                        secs = 1.5
                    q['walk'] = {'to': to, 'start': _fix_time(w.get('start', 'start'), beats[i], fix, where), 'seconds': secs}
                    taken.add(to)
            here[role] = q
            people.append(q)
        for q in people:
            if q['look'] not in ('cam', 'auto') and q['look'] not in here:
                fix(f'{where0} {q["role"]}', f'look {q["look"]!r} -> auto'); q['look'] = 'auto'
        b2['people'] = people
        # camera
        mx = SIZES.index(SPOTS[spot]['max'])
        keys = []
        for j, c in enumerate(b.get('camera') or []):
            if not isinstance(c, dict):
                continue
            where = f'{where0} camera {j + 1}'
            on = []
            for s_ in c.get('on') or ([c['on']] if isinstance(c.get('on'), str) else []):
                s_ = str(s_)
                kind, _, arg = s_.rpartition(':') if ':' in s_ else ('', '', s_)
                if kind == 'prop':
                    arg = rename.get(arg, arg)
                    ok = arg if arg in prop_names else _closest(arg, prop_names, 0.6)
                    if ok and any(pp['name'] == ok for pp in props) or ok in prop_at.get(scene_of[i], {}).values():
                        on.append('prop:' + ok)
                    else:
                        fix(where, f'{s_!r} is not a prop here: dropped')
                elif arg in here or _closest(arg, here, 0.7):
                    r_ = arg if arg in here else _closest(arg, here, 0.7)
                    on.append((kind + ':' if kind in ('arms', 'hand') else '') + r_)
                else:
                    fix(where, f'{s_!r} is not on stage here: dropped')
            if not on:
                on = [p['role'] for p in people][:2] or [f'prop:{n_}' for n_ in prop_at.get(scene_of[i], {}).values()][:1]
                if not on:
                    fix(where, 'nothing to frame: key dropped'); continue
                fix(where, f'framing -> {on}')
            size = str(c.get('size', 'MS')).upper()
            size = size if size in SIZES else 'MS'
            if SIZES.index(size) > mx:
                fix(where, f'{size} does not fit at {spot}: {SPOTS[spot]["max"]}'); size = SIZES[mx]
            num = lambda k, d, lo, hi: min(hi, max(lo, float(c.get(k, d)) if isinstance(c.get(k, d), (int, float)) else d))
            k2 = {'at': _fix_time(c.get('at', 'start'), beats[i], fix, where), 'on': on, 'size': size,
                  'angle': num('angle', 0, -75, 75), 'height': num('height', 4, -10, 45), 'fov': num('fov', 40, 25, 60),
                  'push': num('push', 1.05, 1.0, 1.2)}
            mv = str(c.get('move', 'arc'))
            k2['move'] = mv if mv in MOVES else 'arc'
            if c.get('roll'):
                k2['roll'] = num('roll', 0, -20, 20)
            keys.append(k2)
        keys.sort(key=lambda k: _secs(k['at'], beats[i]))
        new_take = i == 0 or b2['cut'] or spot != spots_of[i - 1]
        kept = []
        for k in keys:
            t = _secs(k['at'], beats[i])
            if kept and t - _secs(kept[-1]['at'], beats[i]) < 0.8:
                fix(where0, f'camera key at {t - beats[i]["start"]:.1f} s is under 0.8 s after the previous one: dropped'); continue
            kept.append(k)
        if not kept:
            on = [p['role'] for p in people][:2] or [f'prop:{n_}' for n_ in prop_at.get(scene_of[i], {}).values()][:1]
            if on:
                fix(where0, 'no camera key: added one'); kept = [{'at': 'start', 'on': on, 'size': SIZES[min(3, mx)], 'angle': 10, 'height': 4,
                                                                 'fov': 40, 'push': 1.05, 'move': 'arc'}]
        if kept and new_take and kept[0]['at'] != 'start':
            fix(where0, 'a new take starts at "start"'); kept[0]['at'] = 'start'
        if kept and not new_take and kept[0]['at'] != 'start' and clean_beats and clean_beats[-1]['camera']:
            gone = [x for x in clean_beats[-1]['camera'][-1]['on'] if x.split(':')[-1] not in here and not x.startswith('prop:')]
            if gone:   # the camera would keep framing someone who left at the beat change
                fix(where0, f'{gone} left at the beat change: the first camera key moves to "start"'); kept[0]['at'] = 'start'
        b2['camera'] = kept
        if not kept:
            fix(where0, 'nothing to film: the beat continues the previous one')
            if clean_beats:
                b2 = copy.deepcopy(clean_beats[-1]); b2['props'] = []; b2['cut'] = b2['flash'] = False
                b2['camera'] = [dict(b2['camera'][-1], at='start')] if b2['camera'] else []
        # sound + hits
        sfx = []
        for s_ in b.get('sfx') or []:
            if isinstance(s_, (list, tuple)) and len(s_) == 2:
                nm = s_[1] if s_[1] in SFX else _closest(s_[1], SFX, 0.5)
                if nm and nm != s_[1]:
                    fix(where0, f'sound {s_[1]!r} -> {nm}')
                if nm:
                    sfx.append([_fix_time(s_[0], beats[i], fix, where0), nm]); continue
            fix(where0, f'sound {s_!r}: dropped')
        b2['sfx'] = sfx
        if b.get('hit'):
            b2['hit'] = _fix_time(b['hit'], beats[i], fix, where0)
        clean_beats.append(b2)
    return {'cast': clean_cast, 'beats': clean_beats}, fixes


def _secs(t, beat):
    if t in (None, 'start', 0):
        return beat['start']
    if isinstance(t, (int, float)):
        return beat['start'] + t
    m = re.fullmatch(r'word:(.+?)(?:#(\d+))?', str(t))
    hits = [x for x in beat['words'] if m and norm(x[0]) == norm(m.group(1))]
    k = int(m.group(2) or 1) if m else 1
    return hits[k - 1][1] if len(hits) >= k else beat['start']


def _fix_time(t, beat, fix, where):
    """any time the director wrote -> a valid one of THIS beat (fuzzy word match, clamped seconds)"""
    dur = beat['end'] - beat['start']
    if t in (None, 'start', 0, '0'):
        return 'start'
    if isinstance(t, (int, float)) or re.fullmatch(r'[\d.]+', str(t)):
        v = float(t)
        if not 0 <= v < dur:
            v2 = round(min(max(v, 0), max(0, dur - 0.3)), 2)
            fix(where, f'{v} s is outside the beat ({dur:.1f} s): {v2}'); v = v2
        return v
    m = re.fullmatch(r'\s*(?:word:)?\s*(.+?)(?:#(\d+))?\s*', str(t))
    w, k = m.group(1), int(m.group(2) or 1)
    words = [norm(x[0]) for x in beat['words']]
    if norm(w) in words:
        return f'word:{w}' + (f'#{k}' if k > 1 and words.count(norm(w)) >= k else '')
    best = difflib.get_close_matches(norm(w), words, n=1, cutoff=0.6)
    if best:
        orig = beat['words'][words.index(best[0])][0]
        fix(where, f'word {w!r} -> {orig!r}'); return f'word:{orig}'
    fix(where, f'{w!r} is not said in this beat: at the beat start'); return 'start'


def compile_plan(plan, vdir, waivers=None, repair=True):
    """-> (files or None, problems, warnings). Writes nothing. repair: run the normalizer first (its FIXES are warnings);
    files['plan.json'] is the plan that was compiled. waivers: [{key, kind, why}] for the kit's GATE_WAIVERS."""
    beats = read_timeline(vdir)
    fixes = []
    if repair:
        plan, fixes = normalize(plan, beats)
        if plan is None:
            return None, fixes, []
    p = Plan(plan, beats, waivers)
    files = p.compile()
    if files:
        files['plan.json'] = json.dumps(plan, indent=1, ensure_ascii=False)
    return files, p.problems, ['FIX ' + f for f in fixes] + p.warnings


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
