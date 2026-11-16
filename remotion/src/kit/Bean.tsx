import React from "react";
import { useCurrentFrame } from "remotion";
import { useScene } from "./core";

// The channel mascot. Mouth follows real speech sounds (viseme track from the voice step):
// it closes at every pause, holds shapes for a few frames, and the body acts with gestures.
export type Pose = "idle" | "point_left" | "point_right" | "point_up" | "shrug" | "think" | "wave" | "cheer" | "facepalm" | "hold";
export type Emotion = "neutral" | "happy" | "shock" | "worried" | "sick" | "sleepy" | "smug" | "hot" | "cold";

const O = "#1d1a2f";
const SKIN: Record<Emotion, [string, string]> = {
  neutral: ["#ffe1b8", "#e7975e"], happy: ["#ffe1b8", "#e7975e"], shock: ["#ffe1b8", "#e7975e"],
  worried: ["#ffe1b8", "#df8e5a"], smug: ["#ffe1b8", "#e7975e"], sleepy: ["#ffe1b8", "#d9925c"],
  sick: ["#d8f3c0", "#8fbf6a"], hot: ["#ffc2a8", "#e5533d"], cold: ["#d6ecff", "#7aa9d6"],
};

// Preston Blair mouth set. X = rest (closed), A = m/b/p, B = most consonants, C = e/i,
// D = a (wide), E = o, F = u/oo, G = f/v, H = l/th.
const Mouth: React.FC<{ shape: string; emotion: Emotion }> = ({ shape, emotion }) => {
  const smile = emotion === "happy" || emotion === "smug";
  switch (shape) {
    case "A": return <path d="M168 330 q32 6 64 0" stroke={O} strokeWidth={9} fill="none" strokeLinecap="round" />;
    case "B": return <g><rect x="166" y="318" width="68" height="26" rx="13" fill="#5a1020" stroke={O} strokeWidth={7} /><rect x="174" y="320" width="52" height="8" rx="4" fill="#fff" /></g>;
    case "C": return <g><ellipse cx="200" cy="330" rx="40" ry="20" fill="#5a1020" stroke={O} strokeWidth={7} /><rect x="172" y="314" width="56" height="9" rx="4" fill="#fff" /></g>;
    case "D": return <g><ellipse cx="200" cy="338" rx="42" ry="40" fill="#5a1020" stroke={O} strokeWidth={7} /><ellipse cx="200" cy="358" rx="24" ry="13" fill="#ff7a90" /></g>;
    case "E": return <ellipse cx="200" cy="336" rx="28" ry="32" fill="#5a1020" stroke={O} strokeWidth={7} />;
    case "F": return <ellipse cx="200" cy="332" rx="16" ry="18" fill="#5a1020" stroke={O} strokeWidth={7} />;
    case "G": return <g><path d="M168 326 q32 14 64 0" fill="#5a1020" stroke={O} strokeWidth={7} /><rect x="178" y="318" width="44" height="9" rx="4" fill="#fff" /></g>;
    case "H": return <g><ellipse cx="200" cy="332" rx="34" ry="20" fill="#5a1020" stroke={O} strokeWidth={7} /><ellipse cx="200" cy="340" rx="16" ry="8" fill="#ff7a90" /></g>;
    default:
      if (emotion === "shock") return <ellipse cx="200" cy="336" rx="22" ry="26" fill="#5a1020" stroke={O} strokeWidth={7} />;
      if (emotion === "worried" || emotion === "sick") return <path d="M166 338 q34 -18 68 0" stroke={O} strokeWidth={9} fill="none" strokeLinecap="round" />;
      return <path d={smile ? "M160 322 q40 34 80 0" : "M168 328 q32 10 64 0"} stroke={O} strokeWidth={9} fill="none" strokeLinecap="round" />;
  }
};

/** Viseme at a global frame (track is sorted [frame, shape] change points). */
const visemeAt = (track: [number, string][], g: number) => {
  let lo = 0, hi = track.length - 1, ans = "X";
  while (lo <= hi) { const m = (lo + hi) >> 1; if (track[m][0] <= g) { ans = track[m][1]; lo = m + 1; } else hi = m - 1; }
  return ans;
};

// arm = [shoulder angle, elbow angle] in degrees, measured from hanging down, + is outward
const ARMS: Record<Pose, { l: [number, number]; r: [number, number] }> = {
  idle: { l: [12, 8], r: [12, 8] }, hold: { l: [40, 70], r: [40, 70] },
  point_left: { l: [95, 0], r: [12, 8] }, point_right: { l: [12, 8], r: [95, 0] },
  point_up: { l: [12, 8], r: [165, 0] }, shrug: { l: [70, -80], r: [70, -80] },
  think: { l: [12, 8], r: [60, 125] }, wave: { l: [12, 8], r: [150, 30] },
  cheer: { l: [160, 10], r: [160, 10] }, facepalm: { l: [12, 8], r: [55, 150] },
};

const Arm: React.FC<{ side: -1 | 1; shoulder: number; elbow: number; skin: string }> = ({ side, shoulder, elbow, skin }) => (
  <g transform={`translate(${200 + side * 104} 300) rotate(${-side * shoulder})`}>
    <rect x={-16} y={0} width={32} height={100} rx={16} fill={skin} stroke={O} strokeWidth={7} />
    <g transform={`translate(0 94) rotate(${-side * elbow})`}>
      <rect x={-15} y={-6} width={30} height={78} rx={15} fill={skin} stroke={O} strokeWidth={7} />
      <circle cx={0} cy={78} r={20} fill={skin} stroke={O} strokeWidth={7} />
    </g>
  </g>
);

export const Bean: React.FC<{
  pose?: Pose; emotion?: Emotion; size?: number; talking?: boolean; lookX?: number; style?: React.CSSProperties;
}> = ({ pose = "idle", emotion = "neutral", size = 520, talking = true, lookX = 0, style }) => {
  const f = useCurrentFrame();
  const s = useScene();
  const g = s.sceneStart + f;
  const shape = talking ? visemeAt(s.visemes, g) : "X";
  const t = g / 30;
  const [light, dark] = SKIN[emotion];
  const breathe = 1 + Math.sin(t * 2.2) * 0.012;
  // blink every ~3.3 s for 4 frames, deterministic
  const blink = g % 100 < 4 || emotion === "sleepy";
  const eyeRy = emotion === "shock" ? 34 : emotion === "happy" ? 20 : emotion === "smug" ? 16 : 27;
  const tilt = pose === "think" ? -6 : pose === "shrug" ? 5 : Math.sin(t * 0.9) * 1.5;
  const wave = pose === "wave" ? Math.sin(t * 10) * 18 : 0;
  const shiver = emotion === "cold" ? Math.sin(t * 60) * 3 : 0;
  const a = ARMS[pose];
  const id = `bean-${emotion}`;
  return (
    <svg viewBox="-40 40 480 500" width={size} height={size * 500 / 480} style={{ overflow: "visible", ...style }}>
      <defs>
        <radialGradient id={id} cx="35%" cy="28%" r="80%">
          <stop offset="0%" stopColor="#fff8ee" /><stop offset="50%" stopColor={light} /><stop offset="100%" stopColor={dark} />
        </radialGradient>
      </defs>
      <ellipse cx="200" cy="512" rx="118" ry="14" fill="rgba(0,0,0,.18)" />
      <g transform={`translate(${shiver} 0) translate(200 505) scale(${1 / breathe} ${breathe}) rotate(${tilt}) translate(-200 -505)`}>
        <rect x="88" y="100" width="224" height="405" rx="112" fill={`url(#${id})`} stroke={O} strokeWidth="9" />
        <ellipse cx="140" cy="160" rx="40" ry="22" fill="#fff" opacity={0.45} transform="rotate(-25 140 160)" />
        {/* brows */}
        <path d={emotion === "shock" ? "M122 150 q28 -24 52 -4 M226 146 q28 -20 52 4"
          : emotion === "worried" || emotion === "sick" ? "M122 158 q28 14 52 0 M226 158 q28 -14 52 0"
          : emotion === "smug" ? "M124 166 q26 -6 50 2 M226 156 q26 -14 50 -6"
          : pose === "think" ? "M122 166 q28 -8 52 0 M226 150 q28 -14 52 0" : "M126 162 q24 -10 48 0 M226 162 q24 -10 48 0"}
          fill="none" stroke={O} strokeWidth="8" strokeLinecap="round" />
        {blink ? (
          <path d="M126 215 q24 10 48 0 M226 215 q24 10 48 0" stroke={O} strokeWidth="7" fill="none" strokeLinecap="round" />
        ) : (
          <>
            <ellipse cx="150" cy="215" rx="27" ry={eyeRy} fill="#fff" stroke={O} strokeWidth="6" />
            <ellipse cx="250" cy="215" rx="27" ry={eyeRy} fill="#fff" stroke={O} strokeWidth="6" />
            <circle cx={152 + lookX * 10} cy="220" r={emotion === "shock" ? 9 : 12} fill={O} />
            <circle cx={252 + lookX * 10} cy="220" r={emotion === "shock" ? 9 : 12} fill={O} />
          </>
        )}
        <ellipse cx="122" cy="288" rx="20" ry="11" fill={emotion === "hot" ? "#ff4d4d" : "#ff8fa3"} opacity={emotion === "cold" ? 0.15 : 0.5} />
        <ellipse cx="278" cy="288" rx="20" ry="11" fill={emotion === "hot" ? "#ff4d4d" : "#ff8fa3"} opacity={emotion === "cold" ? 0.15 : 0.5} />
        <Mouth shape={shape} emotion={emotion} />
        {/* arms in front of the body so gestures always read */}
        <Arm side={-1} shoulder={a.l[0]} elbow={a.l[1]} skin={light} />
        <Arm side={1} shoulder={a.r[0] + wave} elbow={a.r[1]} skin={light} />
        {emotion === "hot" && [0, 1].map((i) => {
          const y = ((t * 140 + i * 120) % 220) + 120;
          return <path key={i} d={`M${318 + i * 10} ${y} q11 24 0 32 q-11 -8 0 -32z`} fill="#7fd6ff" stroke="#2a6a9a" strokeWidth="3" />;
        })}
      </g>
    </svg>
  );
};
