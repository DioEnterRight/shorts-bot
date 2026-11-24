// Per-frame logic for storyboard-compiled videos (pipeline/storyboard3d.py writes web/data.js). Pure functions of the frame f.
import { DATA } from './data.js';
export { DATA };
export const FPS = DATA.fps, TOTAL = DATA.total, DECK = 0;
export const SHOTS = DATA.shots, LIGHTS = DATA.lights;

const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const smooth = (t) => { t = clamp(t); return t * t * t * (t * (t * 6 - 15) + 10); };
const easeOut = (t) => 1 - Math.pow(1 - clamp(t), 3);
const lerp = (a, b, t) => a + (b - a) * t;
const lerp3 = (a, b, t) => a.map((v, i) => lerp(v, b[i], t));
const q = (x, d = 2) => Math.round(x * 10 ** d) / 10 ** d;
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const blinkAt = (f, seed) => { const per = 38 + (seed * 17) % 31, ph = (f + seed * 13) % per; return ph < 2 ? 0.5 : ph < 4 ? 1 : 0; };
/** bounce landing: 0 -> 1 with one small rebound */
const bounce = (t) => { t = clamp(t); return t < 0.7 ? easeOut(t / 0.7) : 1 - Math.sin((t - 0.7) / 0.3 * Math.PI) * 0.08; };
const overshoot = (t) => { t = clamp(t); const c = 1.9; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); };

export const shotAt = (f) => SHOTS.find((s) => f >= s.a && f <= s.b) || SHOTS[SHOTS.length - 1];
export const lightFor = (S) => ({ ...LIGHTS[S.light] });

/** camera keys: [{f, pos, look, fov}, ...] (2 or more). Smooth between keys, or linear for follow shots. */
export const camAt = (f) => {
  const S = shotAt(f), K = S.cam;
  let i = 0; while (i < K.length - 2 && f > K[i + 1].f) i++;
  const a = K[i], b = K[i + 1], u = clamp((f - a.f) / Math.max(1, b.f - a.f));
  const t = S.ease === 'linear' ? u : (K.length > 2 ? u * u * (3 - 2 * u) : smooth(u));
  return { pos: lerp3(a.pos, b.pos, t), look: lerp3(a.look, b.look, t), fov: lerp(a.fov, b.fov, t), roll: 0 };
};
/** focus pulls from S.focus to S.focus2 in the middle of the shot (rack focus) */
export const dofAt = (f) => {
  const S = shotAt(f), C = camAt(f);
  let d = dist(C.pos, S.focus);
  if (S.focus2) d = lerp(d, dist(C.pos, S.focus2), smooth((f - S.a) / Math.max(1, S.b - S.a) * 2.5 - 0.75));
  return { focus: d, cinf: S.cinf };
};
export const worldAt = (f) => ({ stage: shotAt(f).scene });

/** prop animation offsets at frame f. A = {type, f0, f1, ...} or null. */
export const propAt = (f, A) => {
  const o = { show: true, dx: 0, dy: 0, dz: 0, rx: 0, ry: 0, rz: 0, s: 1, k: 1 };
  if (!A) return o;
  const t = f - A.f0, span = Math.max(1, A.f1 - A.f0);
  const enter = (n) => clamp(t / n);
  switch (A.type) {
    case 'drop': o.show = t >= 0; o.dy = (1 - bounce(enter(16))) * 7; break;
    case 'pop': o.show = t >= 0; o.s = Math.max(0.001, overshoot(enter(14))); break;
    case 'rise': o.show = t >= 0; o.dy = -(1 - easeOut(enter(20))) * (A.h || 3); break;
    case 'slide_left': o.show = t >= 0; o.dx = -(1 - easeOut(enter(18))) * 7; break;
    case 'slide_right': o.show = t >= 0; o.dx = (1 - easeOut(enter(18))) * 7; break;
    case 'spin': o.ry = Math.max(0, t) * 0.045; break;
    case 'float': o.dy = 0.18 + Math.sin(f * 0.08) * 0.15; o.ry = Math.sin(f * 0.03) * 0.15; break;
    case 'shake': if (t >= 0) { o.dx = Math.sin(f * 2.3) * 0.05; o.rz = Math.sin(f * 1.7) * 0.03; } break;
    case 'grow': o.show = true; o.k = easeOut(enter(26)); break;
    case 'fly': { const u = clamp(t / span); o.dx = lerp(-A.dist, A.dist, u); o.dy = u * 2.5; o.rz = 0.05; break; }
    case 'fall': { const u = clamp(t / span); o.dy = (1 - u * (0.6 + 0.4 * u)) * A.h; o.rz = Math.sin(f * 0.07) * 0.08; o.dx = Math.sin(f * 0.035) * 0.6; break; }
    default: break;
  }
  return o;
};

export const actorsAt = (f, T) => {
  const S = shotAt(f), tint = LIGHTS[S.light].tint || '#ffffff';
  return S.cast.map((c, i) => {
    const r = c.react && f >= c.react.f ? c.react : null;
    const o = { expr: r ? r.expr : c.expr, L: r ? r.L : c.L, R: c.R, facing: c.facing, look: c.look, seed: c.seed, blink: blinkAt(f, c.seed),
      bob: q(Math.sin(f * 0.11 + c.seed) * 0.012 + 0.012, 3), headTilt: q(Math.sin(f * 0.07 + c.seed * 2) * 1.6, 1) };
    let x = c.x;
    if (c.enter) x += (1 - easeOut((f - c.enter.f) / 18)) * c.enter.from * 6;
    if (r && f - r.f < 6) o.bob = q(o.bob + (6 - (f - r.f)) * 0.012, 3);   // small hop on the reaction (anticipation)
    return { key: JSON.stringify([c.outfit, o]), draw: (p) => T.romanFront(p, c.outfit, o), x, y: 0, z: c.z, tint, order: 2 + i };
  });
};
export const fxAt = () => [];
