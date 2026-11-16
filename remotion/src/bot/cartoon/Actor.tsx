import React from "react";

// The channel's recurring guy: a glossy bean with big eyes. Expression changes eyes, brows, tint
// and extras (sweat, shiver, Zs). `talk` 0..1 opens the mouth; the scene drives it from word times.
export const EXPRESSIONS = ["neutral", "happy", "shock", "sick", "sleepy", "think", "hot", "cold", "pain"] as const;
export type Expression = (typeof EXPRESSIONS)[number];

const TINT: Record<Expression, [string, string]> = {
  neutral: ["#ffe1b8", "#e7975e"], happy: ["#ffe1b8", "#e7975e"], shock: ["#ffe1b8", "#e7975e"],
  think: ["#ffe1b8", "#e7975e"], sleepy: ["#ffe1b8", "#d9925c"], pain: ["#ffd0b8", "#e07a5f"],
  sick: ["#d8f3c0", "#8fbf6a"], hot: ["#ffc2a8", "#e5533d"], cold: ["#d6ecff", "#7aa9d6"],
};
const O = "#22140c";

export const Actor: React.FC<{ expression: Expression; talk: number; t: number; squash: number }> = ({ expression: e, talk, t, squash }) => {
  const [light, dark] = TINT[e];
  const shiver = e === "cold" ? Math.sin(t * 70) * 4 : 0;
  const blink = Math.sin(t * 2.3) > 0.985 || e === "sleepy" ? 0.15 : 1;
  const eyeH = (e === "shock" ? 34 : e === "happy" ? 18 : 26) * blink;
  const look = e === "think" ? -10 : Math.sin(t * 1.3) * 4;
  const mouthOpen = e === "shock" ? 0.8 + talk * 0.2 : talk;
  const id = `skin-${e}`;
  return (
    <svg viewBox="0 0 400 520" width={560} style={{ overflow: "visible", transform: `translateX(${shiver}px)` }}>
      <defs>
        <radialGradient id={id} cx="35%" cy="28%" r="80%">
          <stop offset="0%" stopColor="#fff8ee" />
          <stop offset="50%" stopColor={light} />
          <stop offset="100%" stopColor={dark} />
        </radialGradient>
      </defs>
      <ellipse cx="200" cy="508" rx={120 / squash} ry="14" fill="rgba(0,0,0,.2)" />
      <g transform={`translate(200 500) scale(${1 / squash} ${squash}) translate(-200 -500)`}>
        <rect x="80" y="90" width="240" height="410" rx="120" fill={`url(#${id})`} stroke={O} strokeWidth="9" />
        {/* brows */}
        <path d={e === "shock" ? "M120 150 q30 -25 55 -5 M225 145 q30 -20 55 5" : e === "pain" || e === "sick" ? "M120 160 q30 15 55 0 M225 160 q30 -15 55 0" : e === "think" ? "M120 165 q30 -10 55 0 M225 150 q30 -15 55 0" : "M125 162 q25 -10 50 0 M225 162 q25 -10 50 0"} fill="none" stroke={O} strokeWidth="8" strokeLinecap="round" />
        <ellipse cx="150" cy="215" rx="27" ry={eyeH + 3} fill="#fff" stroke={O} strokeWidth="6" />
        <ellipse cx="250" cy="215" rx="27" ry={eyeH + 3} fill="#fff" stroke={O} strokeWidth="6" />
        {blink > 0.5 && <>
          <circle cx={152 + look} cy="220" r={e === "shock" ? 9 : 12} fill={O} />
          <circle cx={252 + look} cy="220" r={e === "shock" ? 9 : 12} fill={O} />
        </>}
        {/* mouth */}
        {e === "happy" && mouthOpen < 0.2 ? (
          <path d="M160 320 q40 35 80 0" fill="none" stroke={O} strokeWidth="9" strokeLinecap="round" />
        ) : e === "sick" && mouthOpen < 0.2 ? (
          <path d="M160 330 q20 -15 40 0 q20 15 40 0" fill="none" stroke={O} strokeWidth="8" strokeLinecap="round" />
        ) : (
          <ellipse cx="200" cy={322 + mouthOpen * 18} rx={26 + mouthOpen * 26} ry={6 + mouthOpen * 46} fill="#5a1020" stroke={O} strokeWidth="7" />
        )}
        {/* cheeks */}
        <ellipse cx="120" cy="290" rx="20" ry="11" fill={e === "hot" ? "#ff4d4d" : "#ff8fa3"} opacity={e === "cold" ? 0.15 : 0.55} />
        <ellipse cx="280" cy="290" rx="20" ry="11" fill={e === "hot" ? "#ff4d4d" : "#ff8fa3"} opacity={e === "cold" ? 0.15 : 0.55} />
        {(e === "hot" || e === "pain") && [0, 1].map((i) => {
          const y = ((t * 140 + i * 120) % 220) + 120;
          return <path key={i} d={`M${318 + i * 10} ${y} q11 24 0 32 q-11 -8 0 -32z`} fill="#7fd6ff" stroke="#2a6a9a" strokeWidth="3" />;
        })}
      </g>
      {e === "sleepy" && <text x="300" y={90 - (t * 30) % 40} fontSize="60" fontFamily="Anton, sans-serif" fill="#7b2cbf" stroke={O} strokeWidth="3">z</text>}
      {e === "think" && <text x="300" y="90" fontSize="90" fontFamily="Anton, sans-serif" fill="#ffd60a" stroke={O} strokeWidth="5" paintOrder="stroke">?</text>}
    </svg>
  );
};
