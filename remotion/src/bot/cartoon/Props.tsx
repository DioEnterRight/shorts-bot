import React from "react";

// Hand-drawn-style SVG props for code-made explainers. Each fits a 200x200 box, thick dark outline,
// flat colour + one highlight (the glossy "toy" look). Animation is applied by the caller.
// Keep this list in sync with PROPS in pipeline/cartoon.py and prompts/script.md.
const O = "#22140c"; // outline
const W = 7;
const shine = (cx: number, cy: number, rx = 18, ry = 10) => <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="#fff" opacity={0.55} transform={`rotate(-25 ${cx} ${cy})`} />;

const P: Record<string, React.FC> = {
  brain: () => (<g><path d="M45 120 C15 110 20 60 55 58 C60 25 105 22 100 50 C110 22 160 28 150 62 C185 65 185 115 155 122 C150 160 110 165 100 140 C90 165 50 160 45 120Z" fill="#ff9ec4" stroke={O} strokeWidth={W} /><path d="M100 50 V140 M65 80 q20 10 0 30 M135 80 q-20 10 0 30" fill="none" stroke={O} strokeWidth={5} strokeLinecap="round" />{shine(70, 70)}</g>),
  heart: () => (<g><path d="M100 170 C30 120 20 70 55 50 C80 36 100 55 100 70 C100 55 120 36 145 50 C180 70 170 120 100 170Z" fill="#ff3b5c" stroke={O} strokeWidth={W} />{shine(65, 70)}</g>),
  stomach: () => (<g><path d="M70 30 C70 60 40 70 40 110 C40 160 110 175 145 150 C175 128 165 85 130 90 C110 92 105 70 105 30Z" fill="#ff8fa3" stroke={O} strokeWidth={W} /><path d="M70 120 q30 15 60 0" fill="none" stroke={O} strokeWidth={5} />{shine(70, 100)}</g>),
  lungs: () => (<g><path d="M100 30 V90" stroke={O} strokeWidth={W} /><path d="M95 80 C60 60 30 90 35 140 C40 170 90 170 95 140Z" fill="#ff8fab" stroke={O} strokeWidth={W} /><path d="M105 80 C140 60 170 90 165 140 C160 170 110 170 105 140Z" fill="#ff8fab" stroke={O} strokeWidth={W} />{shine(55, 110, 12, 8)}{shine(145, 110, 12, 8)}</g>),
  bladder: () => (<g><path d="M100 40 C150 40 165 90 150 130 C140 160 60 160 50 130 C35 90 50 40 100 40Z" fill="#ffd166" stroke={O} strokeWidth={W} /><path d="M90 158 h20 v25 h-20z" fill="#ffd166" stroke={O} strokeWidth={6} />{shine(75, 70)}</g>),
  kidney: () => (<g><path d="M110 30 C40 30 30 110 60 150 C85 180 130 170 120 130 C112 105 140 100 140 75 C140 50 130 30 110 30Z" fill="#c9184a" stroke={O} strokeWidth={W} />{shine(75, 65)}</g>),
  bone: () => (<g><path d="M55 65 a18 18 0 1 1 25 -20 L125 120 a18 18 0 1 1 20 25 a18 18 0 1 1 -25 20 L75 90 a18 18 0 1 1 -20 -25Z" fill="#fff8e7" stroke={O} strokeWidth={W} /></g>),
  eye: () => (<g><path d="M20 100 Q100 30 180 100 Q100 170 20 100Z" fill="#fff" stroke={O} strokeWidth={W} /><circle cx="100" cy="100" r="34" fill="#3a86ff" stroke={O} strokeWidth={6} /><circle cx="100" cy="100" r="15" fill={O} /><circle cx="90" cy="88" r="7" fill="#fff" /></g>),
  tooth: () => (<g><path d="M50 50 C50 20 150 20 150 50 C150 90 140 100 135 165 C130 180 115 175 112 150 C108 125 92 125 88 150 C85 175 70 180 65 165 C60 100 50 90 50 50Z" fill="#fff" stroke={O} strokeWidth={W} />{shine(75, 55)}</g>),
  blood_cell: () => (<g><ellipse cx="100" cy="100" rx="75" ry="60" fill="#e63946" stroke={O} strokeWidth={W} /><ellipse cx="100" cy="100" rx="35" ry="25" fill="#b5172a" />{shine(65, 70)}</g>),
  germ: () => (<g>{Array.from({ length: 10 }).map((_, i) => { const a = (i / 10) * Math.PI * 2; return <line key={i} x1={100 + Math.cos(a) * 55} y1={100 + Math.sin(a) * 55} x2={100 + Math.cos(a) * 82} y2={100 + Math.sin(a) * 82} stroke={O} strokeWidth={6} strokeLinecap="round" />; })}<circle cx="100" cy="100" r="58" fill="#80ed99" stroke={O} strokeWidth={W} /><circle cx="80" cy="92" r="9" fill={O} /><circle cx="120" cy="92" r="9" fill={O} /><path d="M78 122 q22 -14 44 0" fill="none" stroke={O} strokeWidth={6} /></g>),
  cell: () => (<g><circle cx="100" cy="100" r="78" fill="#a0e7e5" stroke={O} strokeWidth={W} opacity={0.95} /><circle cx="110" cy="95" r="28" fill="#7b2cbf" stroke={O} strokeWidth={5} /><ellipse cx="65" cy="130" rx="14" ry="8" fill="#ffb703" /><ellipse cx="140" cy="140" rx="10" ry="6" fill="#ffb703" />{shine(60, 60)}</g>),
  dna: () => (<g>{Array.from({ length: 7 }).map((_, i) => { const y = 25 + i * 25; const x = Math.sin(i * 0.9) * 45; return <g key={i}><line x1={100 - x} y1={y} x2={100 + x} y2={y} stroke={O} strokeWidth={5} /><circle cx={100 - x} cy={y} r="11" fill="#ff006e" stroke={O} strokeWidth={4} /><circle cx={100 + x} cy={y} r="11" fill="#3a86ff" stroke={O} strokeWidth={4} /></g>; })}</g>),
  muscle: () => (<g><path d="M30 130 C30 80 70 50 105 70 C120 40 170 50 165 95 C160 130 120 150 80 150 C55 150 30 150 30 130Z" fill="#f4a261" stroke={O} strokeWidth={W} />{shine(120, 70)}</g>),
  thermometer: () => (<g><rect x="80" y="20" width="40" height="120" rx="20" fill="#fff" stroke={O} strokeWidth={W} /><rect x="92" y="60" width="16" height="90" fill="#e63946" /><circle cx="100" cy="155" r="30" fill="#e63946" stroke={O} strokeWidth={W} /></g>),
  clock: () => (<g><circle cx="100" cy="100" r="78" fill="#fff" stroke={O} strokeWidth={W} /><line x1="100" y1="100" x2="100" y2="50" stroke={O} strokeWidth={8} strokeLinecap="round" /><line x1="100" y1="100" x2="140" y2="110" stroke="#e63946" strokeWidth={6} strokeLinecap="round" /><circle cx="100" cy="100" r="8" fill={O} /></g>),
  water_drop: () => (<g><path d="M100 20 C130 70 160 100 160 130 C160 165 130 185 100 185 C70 185 40 165 40 130 C40 100 70 70 100 20Z" fill="#4cc9f0" stroke={O} strokeWidth={W} />{shine(75, 120)}</g>),
  fire: () => (<g><path d="M100 185 C45 185 35 130 60 95 C65 120 80 120 80 105 C80 70 100 50 105 20 C130 60 170 90 160 140 C155 170 130 185 100 185Z" fill="#ff7b00" stroke={O} strokeWidth={W} /><path d="M100 180 C75 180 70 150 85 130 C90 145 100 140 100 125 C115 140 130 160 100 180Z" fill="#ffd60a" /></g>),
  snowflake: () => (<g stroke="#4cc9f0" strokeWidth={12} strokeLinecap="round">{[0, 60, 120].map((r) => <line key={r} x1="100" y1="25" x2="100" y2="175" transform={`rotate(${r} 100 100)`} />)}<circle cx="100" cy="100" r="16" fill="#fff" stroke={O} strokeWidth={5} /></g>),
  ice_cube: () => (<g><path d="M40 70 L100 40 L160 70 L160 140 L100 170 L40 140Z" fill="#bde0fe" stroke={O} strokeWidth={W} /><path d="M40 70 L100 100 L160 70 M100 100 V170" fill="none" stroke={O} strokeWidth={5} />{shine(70, 80)}</g>),
  lightning: () => (<path d="M115 15 L50 110 H95 L80 185 L155 80 H108Z" fill="#ffd60a" stroke={O} strokeWidth={W} strokeLinejoin="round" />),
  zzz: () => (<g fill="#7b2cbf" stroke={O} strokeWidth={4} fontFamily="Anton, sans-serif" fontWeight={900}><text x="40" y="160" fontSize="80">Z</text><text x="95" y="110" fontSize="60">Z</text><text x="140" y="70" fontSize="44">Z</text></g>),
  question: () => (<text x="100" y="170" textAnchor="middle" fontSize="190" fontFamily="Anton, sans-serif" fill="#ffd60a" stroke={O} strokeWidth={8} paintOrder="stroke">?</text>),
  exclamation: () => (<text x="100" y="170" textAnchor="middle" fontSize="190" fontFamily="Anton, sans-serif" fill="#ff3b5c" stroke={O} strokeWidth={8} paintOrder="stroke">!</text>),
  check: () => (<g><circle cx="100" cy="100" r="78" fill="#38b000" stroke={O} strokeWidth={W} /><path d="M60 102 L90 132 L145 72" fill="none" stroke="#fff" strokeWidth={18} strokeLinecap="round" strokeLinejoin="round" /></g>),
  cross: () => (<g><circle cx="100" cy="100" r="78" fill="#e63946" stroke={O} strokeWidth={W} /><path d="M68 68 L132 132 M132 68 L68 132" stroke="#fff" strokeWidth={18} strokeLinecap="round" /></g>),
  food: () => (<g><path d="M35 95 C35 40 165 40 165 95Z" fill="#e9a23b" stroke={O} strokeWidth={W} /><rect x="30" y="95" width="140" height="18" rx="9" fill="#38b000" stroke={O} strokeWidth={5} /><rect x="35" y="113" width="130" height="24" rx="10" fill="#6f1d1b" stroke={O} strokeWidth={5} /><path d="M35 137 H165 C165 165 35 165 35 137Z" fill="#e9a23b" stroke={O} strokeWidth={W} /></g>),
  cup: () => (<g><path d="M45 60 H145 L135 170 H55Z" fill="#fff" stroke={O} strokeWidth={W} /><path d="M145 85 C185 85 185 135 140 135" fill="none" stroke={O} strokeWidth={W} /><path d="M80 45 q10 -15 0 -30 M110 45 q10 -15 0 -30" fill="none" stroke="#adb5bd" strokeWidth={6} strokeLinecap="round" /></g>),
  phone: () => (<g><rect x="55" y="20" width="90" height="160" rx="16" fill="#2b2d42" stroke={O} strokeWidth={W} /><rect x="65" y="38" width="70" height="115" rx="6" fill="#4cc9f0" /><circle cx="100" cy="166" r="6" fill="#fff" /></g>),
  sun: () => (<g>{Array.from({ length: 8 }).map((_, i) => <line key={i} x1="100" y1="12" x2="100" y2="38" stroke="#ffb703" strokeWidth={10} strokeLinecap="round" transform={`rotate(${i * 45} 100 100)`} />)}<circle cx="100" cy="100" r="52" fill="#ffd60a" stroke={O} strokeWidth={W} /></g>),
  moon: () => (<path d="M125 25 C70 30 45 80 60 125 C75 170 130 185 165 150 C120 155 85 115 95 70 C100 50 110 35 125 25Z" fill="#ffe66d" stroke={O} strokeWidth={W} />),
  money: () => (<g><rect x="25" y="55" width="150" height="90" rx="10" fill="#80ed99" stroke={O} strokeWidth={W} /><circle cx="100" cy="100" r="26" fill="#38b000" stroke={O} strokeWidth={5} /><text x="100" y="114" textAnchor="middle" fontSize="40" fontWeight={900} fill="#fff">$</text></g>),
  battery: () => (<g><rect x="35" y="55" width="120" height="90" rx="12" fill="#fff" stroke={O} strokeWidth={W} /><rect x="155" y="82" width="15" height="36" rx="4" fill={O} /><rect x="47" y="67" width="40" height="66" rx="6" fill="#e63946" /></g>),
  wave: () => (<path d="M10 120 C40 80 70 80 100 120 C130 160 160 160 190 120 V190 H10Z" fill="#4cc9f0" stroke={O} strokeWidth={W} />),
};

export const PROP_NAMES = Object.keys(P);

export const Prop: React.FC<{ name: string; size: number }> = ({ name, size }) => {
  const C = P[name] ?? P.question;
  return (
    <svg viewBox="0 0 200 200" width={size} height={size} style={{ overflow: "visible", filter: "drop-shadow(0 14px 0 rgba(0,0,0,.18))" }}>
      <C />
    </svg>
  );
};
