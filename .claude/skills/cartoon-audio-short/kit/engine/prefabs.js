// Hand-built story objects for storyboard-compiled videos (money, crime, heists, explainers). Primitives + toon material, so the
// ink pass outlines them like the KayKit models. Every builder returns a THREE.Group with its origin on the ground at its centre,
// sized for the 2.25 m cartoon cards. Text objects draw short text (Latin or Devanagari, Kalam font) onto a canvas texture.
// The list of names + sizes for the storyboard prompt lives in pipeline/storyboard3d.py (PREFABS); keep the two in sync.
import * as THREE from './lib/three.module.js';

let toon;   // set by init() with the engine's toon material factory
export const init = (toonFn) => { toon = toonFn; };

const C = {
  bill: '#8fbf7a', billDark: '#4f7d46', band: '#e9d9a6', gold: '#f2c14e', goldDark: '#c48f1f', steel: '#8d96a3', steelDark: '#565e69',
  white: '#f4f1ea', ink: '#1b1a1f', red: '#c8373a', leather: '#6b3f24', paper: '#f3ecd8', cork: '#b98a55', blue: '#3d6fb6', sky: '#9fc4ea',
  canopy: ['#d9473f', '#f2efe6'], pine: '#3e6b3a', trunk: '#6a4a32', rock: '#8a8f99', snow: '#f4f6fa', screen: '#22303f', glass: '#9fd0ea',
};
const mat = (color, extra = {}) => toon({ color, ...extra });
const mesh = (geo, m, x = 0, y = 0, z = 0, parent) => { const o = new THREE.Mesh(geo, m); o.position.set(x, y, z); o.castShadow = o.receiveShadow = true; parent.add(o); return o; };
const box = (w, h, d) => new THREE.BoxGeometry(w, h, d);
const cyl = (rt, rb, h, s = 20) => new THREE.CylinderGeometry(rt, rb, h, s);

/** text on a canvas -> texture. lines: array of strings; style: {bg, fg, font} */
function textTex(lines, { w = 1024, h = 512, bg = C.paper, fg = C.ink, border = true, size = 0 } = {}) {
  const cv = document.createElement('canvas'); cv.width = w; cv.height = h; const g = cv.getContext('2d');
  g.fillStyle = bg; g.fillRect(0, 0, w, h);
  if (border) { g.strokeStyle = fg; g.lineWidth = h * 0.035; g.strokeRect(h * 0.04, h * 0.04, w - h * 0.08, h - h * 0.08); }
  g.fillStyle = fg; g.textAlign = 'center'; g.textBaseline = 'middle';
  const n = lines.length;
  lines.forEach((t, i) => {
    let px = size || Math.floor(h / (n + 0.9));
    g.font = `bold ${px}px Kalam, sans-serif`;
    while (g.measureText(t).width > w * 0.88 && px > 12) { px -= 4; g.font = `bold ${px}px Kalam, sans-serif`; }
    g.fillText(t, w / 2, h * (i + 0.5 + 0.2) / (n + 0.4));
  });
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
}
const textPanel = (lines, w, h, opts, parent, y, z = 0, side = THREE.FrontSide) => {
  const m = new THREE.MeshBasicMaterial({ map: textTex(lines, { w: 1024, h: Math.round(1024 * h / w), ...opts }), side, toneMapped: false });
  const o = new THREE.Mesh(new THREE.PlaneGeometry(w, h), m); o.position.set(0, y, z); parent.add(o); return o;
};
const split = (text, max = 3) => String(text || '').split('|').map((s) => s.trim()).filter(Boolean).slice(0, max);

// ---------------------------------------------------------------- money
function cashStack(g) {
  mesh(box(0.66, 0.22, 0.3), mat(C.bill), 0, 0.11, 0, g);
  mesh(box(0.14, 0.235, 0.315), mat(C.band), 0, 0.11, 0, g);
  mesh(box(0.62, 0.01, 0.26), mat(C.billDark), 0, 0.225, 0, g);
}
function cashPile(g) {
  const spots = [[0, 0, 0, 0], [0.7, 0, 0.05, 0.2], [-0.68, 0, -0.04, -0.15], [0.35, 0.22, 0.02, 0.4], [-0.3, 0.22, 0, -0.3], [0.02, 0.44, 0.01, 0.1], [0.4, 0, 0.42, 1.3], [-0.38, 0, 0.4, 1.7]];
  for (const [x, y, z, r] of spots) { const s = new THREE.Group(); cashStack(s); s.position.set(x, y, z); s.rotation.y = r; g.add(s); }
}
function moneyBag(g) {
  const b = mesh(new THREE.SphereGeometry(0.42, 24, 18), mat('#c9a66b'), 0, 0.42, 0, g); b.scale.set(1, 1.08, 0.9);
  mesh(cyl(0.12, 0.2, 0.22), mat('#c9a66b'), 0, 0.92, 0, g);
  mesh(new THREE.TorusGeometry(0.15, 0.035, 8, 20), mat('#8a5a2b'), 0, 0.86, 0, g).rotation.x = Math.PI / 2;
  textPanel(['$'], 0.42, 0.42, { bg: '#c9a66b', fg: '#2c5e2a', border: false }, g, 0.44, 0.37);
}
function banknote(g, o) {   // big hero bill standing up, with the given serial / value text
  const [a = '$20', b = 'L 0 7 1 4 0 7 7 1 B'] = split(o.text, 2);
  mesh(box(1.9, 0.86, 0.03), mat(C.bill), 0, 0.9, 0, g);
  textPanel([a, b], 1.8, 0.78, { bg: '#cfe5bd', fg: '#2c5e2a' }, g, 0.9, 0.017);
  mesh(box(0.08, 0.5, 0.08), mat(C.steelDark), 0, 0.25, -0.05, g);
}
function goldBars(g) {
  const bar = (x, y, z, r) => { const m = mesh(new THREE.CylinderGeometry(0.17, 0.24, 0.12, 4), mat(C.gold), x, y, z, g); m.rotation.y = Math.PI / 4 + r; m.scale.set(1.9, 1, 0.8); };
  [[-0.38, 0.06, 0], [0.38, 0.06, 0], [0, 0.06, 0.34], [0, 0.06, -0.34], [-0.19, 0.18, 0.1], [0.19, 0.18, -0.1], [0, 0.3, 0]].forEach(([x, y, z], i) => bar(x, y, z, i * 0.05));
}
function briefcase(g, o) {
  mesh(box(0.9, 0.62, 0.22), mat(C.leather), 0, 0.31, 0, g);
  mesh(box(0.92, 0.04, 0.24), mat('#4a2a16'), 0, 0.5, 0, g);
  const h = mesh(new THREE.TorusGeometry(0.11, 0.025, 8, 16, Math.PI), mat(C.ink), 0, 0.62, 0, g);
  [-0.3, 0.3].forEach((x) => mesh(box(0.08, 0.06, 0.03), mat(C.gold), x, 0.52, 0.12, g));
  if (o.open) { const s = new THREE.Group(); cashStack(s); s.position.set(-0.16, 0.62, 0); g.add(s); const s2 = new THREE.Group(); cashStack(s2); s2.position.set(0.18, 0.62, 0.02); g.add(s2); }
  void h;
}
function safe(g) {
  mesh(box(1.1, 1.3, 1.0), mat(C.steelDark), 0, 0.65, 0, g);
  mesh(box(0.92, 1.12, 0.05), mat(C.steel), 0, 0.65, 0.51, g);
  const d = mesh(cyl(0.16, 0.16, 0.08), mat(C.white), 0.1, 0.8, 0.56, g); d.rotation.x = Math.PI / 2;
  const hd = mesh(box(0.05, 0.34, 0.05), mat(C.ink), 0.1, 0.45, 0.57, g); hd.rotation.z = 0.8;
  [-0.35, 0.35].forEach((x) => mesh(box(0.16, 0.12, 0.9), mat(C.ink), x, 0.06, 0, g));
}
function vaultDoor(g) {
  mesh(box(5, 5, 0.6), mat('#6f747c'), 0, 2.5, -0.3, g);
  const d = mesh(cyl(1.9, 1.9, 0.5, 40), mat(C.steel), 0, 2.4, 0.15, g); d.rotation.x = Math.PI / 2;
  const r = mesh(new THREE.TorusGeometry(1.9, 0.12, 10, 40), mat(C.steelDark), 0, 2.4, 0.42, g); void r;
  const hub = mesh(cyl(0.35, 0.35, 0.3, 24), mat(C.steelDark), 0, 2.4, 0.5, g); hub.rotation.x = Math.PI / 2;
  for (let i = 0; i < 3; i++) { const s = mesh(box(1.8, 0.12, 0.12), mat(C.gold), 0, 2.4, 0.62, g); s.rotation.z = i * Math.PI / 3; }
  for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2; mesh(cyl(0.08, 0.08, 0.1, 10), mat(C.steelDark), Math.cos(a) * 1.6, 2.4 + Math.sin(a) * 1.6, 0.42, g).rotation.x = Math.PI / 2; }
}
function bank(g, o) {
  const name = split(o.text, 1)[0] || 'BANK';
  mesh(box(12, 0.6, 5), mat('#d8d2c4'), 0, 0.3, 0, g);
  mesh(box(11, 7.5, 4), mat('#e9e2d1'), 0, 4.35, -0.5, g);
  for (let i = 0; i < 6; i++) mesh(cyl(0.38, 0.42, 6.4, 18), mat(C.white), -4.5 + i * 1.8, 3.8, 2.0, g);
  const roof = mesh(new THREE.CylinderGeometry(0.01, 7.4, 2.3, 3), mat('#d8d2c4'), 0, 8.4, 1.1, g); roof.rotation.set(Math.PI / 2, 0, 0); roof.scale.set(1, 0.42, 1);
  mesh(box(11.4, 0.6, 2.2), mat('#cfc7b6'), 0, 7.3, 1.4, g);
  textPanel([name], 6, 0.9, { bg: '#e9e2d1', fg: '#3a352c', border: false }, g, 7.3, 2.52);
  mesh(box(2, 3.2, 0.2), mat('#4a3426'), 0, 2.2, 1.55, g);
}
// ---------------------------------------------------------------- crime / investigation
function jet(g, o) {   // 1960s airliner with a rear airstair (727-style)
  const body = mat(C.white), stripe = mat(o.color || C.blue), dark = mat('#3a3f48');
  const f = mesh(cyl(1.05, 1.05, 17, 28), body, 0, 0, 0, g); f.rotation.z = Math.PI / 2;
  const nose = mesh(new THREE.SphereGeometry(1.05, 28, 16, 0, Math.PI * 2, 0, Math.PI / 2), body, 8.5, 0, 0, g); nose.rotation.z = -Math.PI / 2; nose.scale.set(1, 1.8, 1);
  const tail = mesh(new THREE.ConeGeometry(1.05, 4.5, 28), body, -10.7, 0.35, 0, g); tail.rotation.z = Math.PI / 2;
  const st = mesh(cyl(1.07, 1.07, 17.2, 28, 1), stripe, 0, -0.1, 0, g); st.rotation.z = Math.PI / 2; st.scale.set(1, 1, 1); st.geometry = new THREE.CylinderGeometry(1.07, 1.07, 17.2, 28, 1, true, Math.PI * 0.42, Math.PI * 0.16);
  const wing = new THREE.Shape(); wing.moveTo(0, 0); wing.lineTo(-3.2, 8.5); wing.lineTo(-4.6, 8.5); wing.lineTo(-3.6, 0); wing.closePath();
  const wg = new THREE.ExtrudeGeometry(wing, { depth: 0.18, bevelEnabled: false });
  [1, -1].forEach((s) => { const w = mesh(wg, body, 1.2, -0.5, 0, g); w.rotation.x = s * Math.PI / 2; w.position.z = s > 0 ? 0 : 0; w.scale.z = 1; });
  const fin = new THREE.Shape(); fin.moveTo(0, 0); fin.lineTo(-2.6, 3.6); fin.lineTo(-3.8, 3.6); fin.lineTo(-3.4, 0); fin.closePath();
  mesh(new THREE.ExtrudeGeometry(fin, { depth: 0.16, bevelEnabled: false }), stripe, -9, 0.8, -0.08, g);
  const tp = mesh(box(1.6, 0.12, 5.2), body, -12.3, 4.3, 0, g); void tp;
  [-0.9, 0.9].forEach((z) => { const e = mesh(cyl(0.55, 0.55, 2.6, 18), dark, -8.2, 1.1, z * 1.35, g); e.rotation.z = Math.PI / 2; });
  for (let i = 0; i < 12; i++) mesh(box(0.32, 0.36, 0.05), mat(C.screen), 6 - i * 1.15, 0.38, 1.03, g);
  for (let i = 0; i < 12; i++) mesh(box(0.32, 0.36, 0.05), mat(C.screen), 6 - i * 1.15, 0.38, -1.03, g);
  mesh(box(0.9, 0.4, 2.0), mat(C.screen), 8.9, 0.6, 0, g);
  if (o.stairs !== false) { const s = mesh(box(3.2, 0.12, 0.9), mat(C.steelDark), -12.4, -1.2, 0, g); s.rotation.z = 0.42; }
  g.children.forEach((c) => { c.position.y += 2.2; });   // wheels height: sits above ground
  [[6.5, 0], [-1, 1.4], [-1, -1.4]].forEach(([x, z]) => { mesh(cyl(0.08, 0.08, 1.2, 8), dark, x, 0.9, z, g); const w = mesh(cyl(0.35, 0.35, 0.25, 16), mat(C.ink), x, 0.35, z, g); w.rotation.x = Math.PI / 2; });
}
function parachute(g, o) {   // canopy + lines + a tiny jumper silhouette; origin at the jumper's feet
  const cols = o.color ? [o.color, C.white] : C.canopy;
  for (let i = 0; i < 8; i++) {
    const seg = new THREE.SphereGeometry(2.2, 6, 10, i * Math.PI / 4, Math.PI / 4, 0, Math.PI / 2.4);
    const m = mesh(seg, mat(cols[i % 2], { side: THREE.DoubleSide }), 0, 4.4, 0, g); m.scale.y = 0.55;
  }
  const lineM = mat('#3a3540');
  for (let i = 0; i < 8; i++) {   // suspension lines as thin rods so they read on a phone
    const a = i * Math.PI / 4, top = new THREE.Vector3(Math.cos(a) * 2.05, 4.4, Math.sin(a) * 2.05), bot = new THREE.Vector3(0, 1.4, 0);
    const len = top.distanceTo(bot), r = mesh(cyl(0.025, 0.025, len, 5), lineM, 0, 0, 0, g);
    r.position.copy(top).add(bot).multiplyScalar(0.5); r.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), top.clone().sub(bot).normalize());
  }
  mesh(box(0.38, 0.62, 0.22), mat('#2b2b33'), 0, 1.05, 0, g);
  mesh(new THREE.SphereGeometry(0.16, 12, 10), mat('#e0b48c'), 0, 1.5, 0, g);
  [-0.1, 0.1].forEach((x) => mesh(box(0.12, 0.7, 0.12), mat('#2b2b33'), x, 0.42, 0, g));
}
function newspaper(g, o) {
  const [h1 = 'BREAKING NEWS', h2 = ''] = split(o.text, 2);
  const p = new THREE.Group(); g.add(p);
  mesh(box(1.5, 2.0, 0.03), mat(C.paper), 0, 1.0, 0, p);
  textPanel(['THE DAILY TIMES'], 1.4, 0.26, { bg: C.paper, fg: C.ink, border: false }, p, 1.82, 0.017);
  textPanel(h2 ? [h1, h2] : [h1], 1.4, 0.6, { bg: C.paper, fg: C.ink, border: false }, p, 1.36, 0.017);
  for (let i = 0; i < 7; i++) mesh(box(0.6, 0.04, 0.005), mat('#9b968a'), -0.35, 0.92 - i * 0.12, 0.018, p);
  mesh(box(0.6, 0.78, 0.005), mat('#b9b3a3'), 0.36, 0.56, 0.018, p);
  p.rotation.x = -0.12;
}
function documentProp(g0, o) {
  const g = new THREE.Group(); g0.add(g);   // tilt lives on an inner group: the engine owns the outer transform
  const lines = split(o.text, 3); const [t = 'CONFIDENTIAL', ...rest] = lines;
  mesh(box(1.2, 1.6, 0.03), mat(C.paper), 0, 0.8, 0, g);
  textPanel([t, ...rest], 1.1, 0.7, { bg: C.paper, fg: o.color || C.red }, g, 1.2, 0.017);
  for (let i = 0; i < 5; i++) mesh(box(0.9, 0.035, 0.005), mat('#9b968a'), 0, 0.68 - i * 0.11, 0.018, g);
  g.rotation.x = -0.1;
}
function sign(g, o) {   // board on two posts; up to 3 lines of text
  const lines = split(o.text, 3); if (!lines.length) lines.push('?');
  const h = 0.55 + lines.length * 0.42;
  mesh(box(3.2, h + 0.16, 0.12), mat('#5a3a24'), 0, 1.2 + h / 2, -0.07, g);
  textPanel(lines, 3.0, h, { bg: o.color || '#f6eedb', fg: C.ink }, g, 1.2 + h / 2, 0.0);
  [-1.2, 1.2].forEach((x) => mesh(box(0.14, 1.3, 0.14), mat('#5a3a24'), x, 0.6, -0.07, g));
}
function label(g, o) {   // floating headline card (numbers, dates, names), no posts
  const lines = split(o.text, 2); if (!lines.length) lines.push('?');
  textPanel(lines, 3.4, 0.6 + lines.length * 0.5, { bg: o.color || '#fff6dc', fg: C.ink }, g, 2.6, 0, THREE.DoubleSide);
}
function magnifier(g) {
  const ring = mesh(new THREE.TorusGeometry(0.42, 0.07, 12, 32), mat(C.ink), 0, 1.25, 0, g); void ring;
  mesh(new THREE.CircleGeometry(0.4, 32), mat(C.glass, { transparent: true, opacity: 0.45 }), 0, 1.25, 0, g);
  const h = mesh(cyl(0.07, 0.08, 0.8, 12), mat(C.leather), 0.42, 0.62, 0, g); h.rotation.z = 0.75;
}
function phone(g, o) {
  mesh(box(0.7, 1.4, 0.1), mat(C.ink), 0, 0.75, 0, g);
  const lines = split(o.text, 2);
  if (lines.length) textPanel(lines, 0.6, 1.2, { bg: '#e9f2ff', fg: C.ink, border: false }, g, 0.75, 0.052);
  else mesh(box(0.6, 1.25, 0.02), mat(C.screen), 0, 0.75, 0.05, g);
}
function laptop(g, o) {
  mesh(box(1.1, 0.05, 0.75), mat(C.steel), 0, 0.03, 0, g);
  const lid = new THREE.Group(); lid.position.set(0, 0.05, -0.37); lid.rotation.x = -0.25; g.add(lid);
  mesh(box(1.1, 0.72, 0.04), mat(C.steel), 0, 0.36, 0, lid);
  const lines = split(o.text, 2);
  if (lines.length) textPanel(lines, 1.0, 0.62, { bg: '#e9f2ff', fg: C.ink, border: false }, lid, 0.36, 0.022);
  else mesh(box(1.0, 0.62, 0.01), mat(C.screen), 0, 0.36, 0.022, lid);
}
function evidenceBoard(g, o) {   // cork board with photos, notes and red string
  mesh(box(3.6, 2.4, 0.1), mat(C.cork), 0, 1.9, 0, g);
  mesh(box(3.8, 2.6, 0.06), mat('#5a3a24'), 0, 1.9, -0.06, g);
  const pins = [[-1.2, 2.5], [0.2, 2.6], [1.25, 2.3], [-0.7, 1.3], [0.9, 1.25]];
  const notes = split(o.text, 3);
  pins.forEach(([x, y], i) => {
    const n = notes[i];
    if (n) textPanel([n], 0.95, 0.5, { bg: '#fff3a8', fg: C.ink, border: false }, g, y, 0.06).position.x = x;
    else mesh(box(0.7, 0.55, 0.01), mat(i % 2 ? '#d7d2c6' : '#a9b6c2'), x, y, 0.06, g);
    mesh(new THREE.SphereGeometry(0.05, 8, 6), mat(C.red), x, y + 0.24, 0.1, g);
  });
  const lm = new THREE.LineBasicMaterial({ color: C.red });
  [[0, 1], [1, 2], [0, 3], [3, 4], [2, 4]].forEach(([a, b]) => g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(
    [new THREE.Vector3(pins[a][0], pins[a][1] + 0.24, 0.11), new THREE.Vector3(pins[b][0], pins[b][1] + 0.24, 0.11)]), lm)));
}
function chart(g, o) {   // bar chart; bars grow with the "grow" animation (userData.grow)
  const up = o.trend !== 'down';
  mesh(box(3.2, 0.1, 0.6), mat('#4a4f5a'), 0, 0.05, 0, g);
  const bars = [];
  for (let i = 0; i < 5; i++) {
    const h = up ? 0.5 + i * 0.5 : 2.5 - i * 0.48;
    const b = mesh(box(0.42, 1, 0.42), mat(i === 4 ? (up ? '#3f9b4b' : C.red) : '#7f93ad'), -1.2 + i * 0.6, 0.1, 0, g);
    b.geometry.translate(0, 0.5, 0); b.userData.h = h; b.scale.y = h; bars.push(b);
  }
  g.userData.grow = (k) => bars.forEach((b, i) => { b.scale.y = Math.max(0.001, b.userData.h * Math.min(1, Math.max(0, k * 1.6 - i * 0.15))); });
}
function arrow(g0, o) {
  const g = new THREE.Group(); g0.add(g);
  const m = mat(o.color || C.red);
  mesh(box(0.35, 1.6, 0.25), m, 0, 0.8, 0, g);
  const h = mesh(new THREE.ConeGeometry(0.55, 0.8, 4), m, 0, 2.0, 0, g); h.rotation.y = Math.PI / 4;
  if (o.trend === 'down') g.rotation.z = Math.PI, g.position.y = 2.4;
}
function question(g) {
  const m = mat(C.gold);
  const t = mesh(new THREE.TorusGeometry(0.45, 0.14, 12, 24, Math.PI * 1.4), m, 0, 1.9, 0, g); t.rotation.z = -Math.PI * 0.4;
  mesh(cyl(0.14, 0.14, 0.45, 14), m, 0, 1.25, 0, g);
  mesh(new THREE.SphereGeometry(0.17, 14, 10), m, 0, 0.75, 0, g);
}
function clock(g) {
  const f = mesh(cyl(0.7, 0.7, 0.12, 36), mat(C.white), 0, 1.6, 0, g); f.rotation.x = Math.PI / 2;
  const r = mesh(new THREE.TorusGeometry(0.7, 0.07, 10, 36), mat(C.ink), 0, 1.6, 0.04, g); void r;
  const hh = mesh(box(0.06, 0.38, 0.03), mat(C.ink), 0, 1.76, 0.08, g); hh.geometry.translate(0, 0, 0);
  const mh = mesh(box(0.04, 0.55, 0.03), mat(C.red), 0.12, 1.75, 0.09, g); mh.rotation.z = -0.5;
  g.userData.hands = [hh, mh];
}
// ---------------------------------------------------------------- nature / sky
function pineTree(g, s = 1, x = 0, z = 0) {
  mesh(cyl(0.18 * s, 0.25 * s, 1.4 * s, 8), mat(C.trunk), x, 0.7 * s, z, g);
  [[1.7, 1.9, 1.6], [1.35, 1.6, 2.7], [0.95, 1.3, 3.6]].forEach(([r, h, y]) => mesh(new THREE.ConeGeometry(r * s, h * s, 9), mat(C.pine), x, y * s, z, g));
}
function forest(g) {
  [[0, 0, 1.3], [-3.2, -1.5, 1.1], [3.4, -1, 1.2], [-1.6, -4, 1.4], [1.8, -4.5, 1], [-5.4, -3.5, 1.2], [5.6, -3.8, 1.3], [0.2, -7, 1.5], [-3.8, -7.5, 1.1], [4, -7.6, 1.2]]
    .forEach(([x, z, s]) => pineTree(g, s, x, z));
}
function mountain(g) {
  const m = mesh(new THREE.ConeGeometry(14, 16, 7), mat(C.rock), 0, 8, 0, g); m.rotation.y = 0.4;
  const s = mesh(new THREE.ConeGeometry(4.6, 5.3, 7), mat(C.snow), 0, 13.4, 0, g); s.rotation.y = 0.4;
  const m2 = mesh(new THREE.ConeGeometry(9, 10, 6), mat('#7c8794'), -11, 5, -4, g); void m2;
}
function cloud(g) {
  [[0, 0, 0, 1.6], [1.6, -0.2, 0.2, 1.2], [-1.5, -0.3, 0, 1.1], [0.6, 0.7, -0.2, 1.1], [-0.6, 0.5, 0.3, 1]]
    .forEach(([x, y, z, r]) => mesh(new THREE.SphereGeometry(r, 14, 10), mat('#ffffff'), x, 2 + y, z, g));
}
function river(g) {
  const w = mesh(new THREE.PlaneGeometry(6, 60), mat('#4f8fc0'), 0, 0.03, 0, g); w.rotation.x = -Math.PI / 2; w.castShadow = false;
  [[-3.2, 0], [3.2, 0]].forEach(([x]) => { const b = mesh(new THREE.PlaneGeometry(0.8, 60), mat('#c9b48a'), x, 0.035, 0, g); b.rotation.x = -Math.PI / 2; b.castShadow = false; });
}

export const BUILDERS = {
  cash_stack: cashStack, cash_pile: cashPile, money_bag: moneyBag, banknote, gold_bars: goldBars, briefcase, safe, vault_door: vaultDoor,
  bank, jet, parachute, newspaper, document: documentProp, sign, label, magnifier, phone, laptop, evidence_board: evidenceBoard, chart,
  arrow, question, clock, pine_tree: (g) => pineTree(g), forest, mountain, cloud, river,
};

/** -> THREE.Group for prefab `name` (o: {text, color, open, trend, stairs}). */
export function make(name, o = {}) {
  const b = BUILDERS[name];
  if (!b) throw new Error(`unknown prefab '${name}'`);
  const g = new THREE.Group(); b(g, o); return g;
}
