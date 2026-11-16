import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { RadialBurst } from "../../library/remocn/registry/radial-burst";
import { cameraTransform } from "../ExplainerScene";
import { Overlay } from "../Overlay";
import type { BotProps, BotScene } from "../schema";
import { Actor } from "./Actor";
import { Prop } from "./Props";

type Cartoon = BotScene["cartoon"];
const MOOD: Record<Cartoon["mood"], [string, string]> = {
  fun: ["#ffe66d", "#ff9f1c"], calm: ["#a0e7e5", "#4cc9f0"], warm: ["#ffb4a2", "#e5533d"],
  cold: ["#d6ecff", "#5fa8d3"], danger: ["#ff8fa3", "#9d0208"], body: ["#ffc8dd", "#cd4e7a"],
  night: ["#7b6cf6", "#22223b"],
};
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Motion presets: pure functions of time so renders are repeatable.
const motion = (m: string, t: number, f: number, fps: number, delay: number) => {
  const inn = spring({ frame: f - delay, fps, config: { damping: 11, stiffness: 170 } });
  switch (m) {
    case "pulse": return `scale(${inn * (1 + Math.sin(t * 7) * 0.08)})`;
    case "shake": return `scale(${inn}) translate(${Math.sin(t * 40) * 9}px, ${Math.cos(t * 33) * 5}px) rotate(${Math.sin(t * 25) * 4}deg)`;
    case "float": return `scale(${inn}) translateY(${Math.sin(t * 2.5) * 22}px)`;
    case "spin": return `scale(${inn}) rotate(${t * 140}deg)`;
    case "grow": return `scale(${inn * interpolate(f - delay, [0, 60], [0.6, 1.25], clamp)})`;
    case "bounce": return `scale(${inn}) translateY(${-Math.abs(Math.sin(t * 5)) * 60}px)`;
    case "drip": return `scale(${inn}) translateY(${((t * 120) % 140) - 20}px)`;
    default: return `scale(${inn})`;
  }
};

const Placed: React.FC<{ name: string; m: string; x: number; y: number; size: number; delay: number }> = ({ name, m, x, y, size, delay }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div style={{ position: "absolute", left: x - size / 2, top: y - size / 2, width: size, height: size, transform: motion(m, f / fps, f, fps, delay) }}>
      <Prop name={name} size={size} />
    </div>
  );
};

const Arrow: React.FC<{ x1: number; x2: number; y: number }> = ({ x1, x2, y }) => {
  const f = useCurrentFrame();
  const draw = interpolate(f, [8, 22], [0, 1], clamp);
  const dash = (f * 6) % 60;
  return (
    <svg width={1080} height={1920} style={{ position: "absolute", left: 0, top: 0 }}>
      <line x1={x1} y1={y} x2={x1 + (x2 - x1) * draw} y2={y} stroke="#22140c" strokeWidth={18} strokeDasharray="40 20" strokeDashoffset={-dash} strokeLinecap="round" />
      {draw > 0.95 && <path d={`M${x2 - 10} ${y - 34} L${x2 + 30} ${y} L${x2 - 10} ${y + 34}Z`} fill="#22140c" />}
    </svg>
  );
};

// Mouth moves while a word is being spoken (word times come from the voice step).
const useTalk = (p: BotProps, sceneStart: number) => {
  const f = useCurrentFrame();
  const ms = ((sceneStart + f) / p.fps) * 1000;
  const speaking = p.captions.some((c) => ms >= c.startMs && ms < c.endMs);
  return speaking ? 0.35 + 0.65 * Math.abs(Math.sin(f * 0.9)) : 0;
};

export const CartoonScene: React.FC<{ s: BotScene; p: BotProps; impact: boolean; sceneStart: number }> = ({ s, p, impact, sceneStart }) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = f / fps;
  const pre = s.transitionFrames / 2;
  const local = Math.max(0, f - pre);
  const c = s.cartoon;
  const [a, b] = MOOD[c.mood];
  const talk = useTalk(p, sceneStart);
  const squash = 1 + talk * 0.05 + (c.expression === "shock" ? 0.06 * Math.max(0, 1 - local / 10) : 0);
  const props = c.props;
  const d = pre + 4;

  let body: React.ReactNode;
  if (c.layout === "actor") {
    const spots = [[220, 400], [860, 440], [540, 260]];
    body = (
      <>
        <div style={{ position: "absolute", left: 260, top: 540 }}><Actor expression={c.expression} talk={talk} t={t} squash={squash} /></div>
        {props.map((q, i) => <Placed key={i} name={q.name} m={q.motion} x={spots[i][0]} y={spots[i][1]} size={300} delay={d + 6 + i * 6} />)}
      </>
    );
  } else if (c.layout === "versus" && props.length >= 2) {
    body = (
      <>
        <Placed name={props[0].name} m={props[0].motion} x={270} y={820} size={400} delay={d} />
        <Arrow x1={440} x2={620} y={820} />
        <Placed name={props[1].name} m={props[1].motion} x={810} y={820} size={400} delay={d + 14} />
        {props[2] && <Placed name={props[2].name} m={props[2].motion} x={540} y={420} size={260} delay={d + 22} />}
      </>
    );
  } else if (c.layout === "inside") {
    const lens = spring({ frame: f - d - 4, fps, config: { damping: 13 } });
    body = (
      <>
        <div style={{ position: "absolute", left: -40, top: 1000, transform: "scale(.62)", transformOrigin: "0 0", opacity: 0.95 }}>
          <Actor expression={c.expression} talk={talk} t={t} squash={squash} />
        </div>
        <svg width={1080} height={1920} style={{ position: "absolute", left: 0, top: 0 }}>
          <path d={`M300 1180 L${380 + 160 * lens} ${1000 - 120 * lens}`} stroke="#fff" strokeWidth={10} strokeDasharray="22 16" opacity={lens} />
        </svg>
        <div style={{ position: "absolute", left: 590 - 400, top: 760 - 400, width: 800, height: 800, borderRadius: "50%",
          background: "radial-gradient(circle at 40% 35%, #ffe0ec, #ff8fab)", border: "16px solid #22140c", overflow: "hidden",
          transform: `scale(${lens})`, boxShadow: "0 24px 0 rgba(0,0,0,.25)" }}>
          {props.map((q, i) => <Placed key={i} name={q.name} m={q.motion} x={i === 0 ? 400 : i === 1 ? 210 : 600} y={i === 0 ? 410 : 220} size={i === 0 ? 470 : 200} delay={d + 10 + i * 6} />)}
        </div>
      </>
    );
  } else {
    const n = Math.max(1, props.length);
    const layouts: number[][][] = [[[540, 800, 640]], [[300, 820, 430], [790, 820, 430]], [[540, 560, 420], [280, 1020, 360], [800, 1020, 360]]];
    body = props.map((q, i) => { const [x, y, size] = layouts[Math.min(n, 3) - 1][i]; return <Placed key={i} name={q.name} m={q.motion} x={x} y={y} size={size} delay={d + i * 8} />; });
  }

  // a few slow bubbles so no frame is ever fully still
  const bubbles = Array.from({ length: 7 }).map((_, i) => {
    const y = 1920 - (((t * (40 + i * 9) + i * 300) % 2100));
    return <div key={i} style={{ position: "absolute", left: (i * 157) % 1000, top: y, width: 40 + (i % 3) * 30, height: 40 + (i % 3) * 30, borderRadius: "50%", background: "rgba(255,255,255,.22)" }} />;
  });

  return (
    <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 38%, ${a}, ${b})`, overflow: "hidden" }}>
      {bubbles}
      <AbsoluteFill style={{ transform: cameraTransform(s.camera, local, durationInFrames - pre), transformOrigin: "50% 45%" }}>{body}</AbsoluteFill>
      {impact && local < 14 && (
        <AbsoluteFill style={{ mixBlendMode: "screen", opacity: interpolate(local, [0, 3, 14], [0, 0.8, 0], clamp) }}>
          <RadialBurst color="#ffffff" accentColor={p.accent} backgroundColor="transparent" intensity={1.2} speed={1.6} />
        </AbsoluteFill>
      )}
      {s.overlay && <Overlay text={s.overlay} p={p} startAt={pre + 6} />}
    </AbsoluteFill>
  );
};
