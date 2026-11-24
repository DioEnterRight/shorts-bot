// Per-frame logic for storyboard-compiled videos (pipeline/storyboard3d.py writes web/data.js). Pure functions of the frame f.
import { DATA } from './data.js';
export { DATA };
export const FPS = DATA.fps, TOTAL = DATA.total, DECK = 0;
export const SHOTS = DATA.shots, LIGHTS = DATA.lights;

const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const smooth = (t) => { t = clamp(t); return t * t * t * (t * (t * 6 - 15) + 10); };
const lerp = (a, b, t) => a + (b - a) * t;
const lerp3 = (a, b, t) => a.map((v, i) => lerp(v, b[i], t));
const q = (x, d = 2) => Math.round(x * 10 ** d) / 10 ** d;
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const blinkAt = (f, seed) => { const per = 38 + (seed * 17) % 31, ph = (f + seed * 13) % per; return ph < 2 ? 0.5 : ph < 4 ? 1 : 0; };

export const shotAt = (f) => SHOTS.find((s) => f >= s.a && f <= s.b) || SHOTS[SHOTS.length - 1];
export const lightFor = (S) => ({ ...LIGHTS[S.light] });
export const camAt = (f) => {
  const S = shotAt(f), [a, b] = S.cam, t = smooth((f - S.a) / Math.max(1, S.b - S.a));
  return { pos: lerp3(a.pos, b.pos, t), look: lerp3(a.look, b.look, t), fov: lerp(a.fov, b.fov, t), roll: 0 };
};
export const dofAt = (f) => { const S = shotAt(f), C = camAt(f); return { focus: dist(C.pos, S.focus), cinf: S.cinf }; };
export const worldAt = (f) => ({ stage: shotAt(f).scene });

export const actorsAt = (f, T) => {
  const S = shotAt(f), tint = LIGHTS[S.light].tint || '#ffffff';
  return S.cast.map((c, i) => {
    const o = { expr: c.expr, L: c.L, R: c.R, facing: c.facing, look: c.look, seed: c.seed, blink: blinkAt(f, c.seed),
      bob: q(Math.sin(f * 0.11 + c.seed) * 0.012 + 0.012, 3), headTilt: q(Math.sin(f * 0.07 + c.seed * 2) * 1.6, 1) };
    return { key: JSON.stringify([c.outfit, o]), draw: (p) => T.romanFront(p, c.outfit, o), x: c.x, y: 0, z: c.z, tint, order: 2 + i };
  });
};
export const fxAt = () => [];
