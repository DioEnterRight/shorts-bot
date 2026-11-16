import React, { createContext, useContext } from "react";
import { Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

// ---------- design tokens (the channel's look: keep every scene on these) ----------
export const C = {
  ink: "#1d1a2f", paper: "#fff8ef", accent: "#ffcf3f", hot: "#ff4d6d", cool: "#3fa7ff", good: "#2ec27e",
  bad: "#ff5a36", purple: "#8b5cf6", skin: "#ffe1b8", body: "#ff9ebb", night: "#1b1f3b", sky: "#bfe9ff",
  muted: "#8a8aa3",
} as const;
export const FONT = { display: "Anton, 'Noto Sans Devanagari', 'Noto Sans', sans-serif",
  ui: "Poppins, 'Noto Sans Devanagari', 'Noto Sans', sans-serif" };
export const SAFE = { x: 70, top: 180, bottom: 520, w: 940 }; // keep content inside; captions live below `bottom`

export const ease = {
  out: Easing.bezier(0.16, 1, 0.3, 1), in: Easing.bezier(0.6, 0, 0.9, 0.35),
  inOut: Easing.bezier(0.65, 0, 0.35, 1), land: Easing.bezier(0.55, 0, 0.2, 1.12),
};
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** 0→1 between local frames a and b (default ease-out). */
export const prog = (f: number, a: number, b: number, e: (t: number) => number = ease.out) =>
  interpolate(f, [a, b], [0, 1], { ...clamp, easing: e });
/** Spring that starts at local frame `at`. kinds: settle, pop, heavy, elastic (one hero moment). */
export const sp = (f: number, at: number, kind: "settle" | "pop" | "heavy" | "elastic" = "settle") => {
  const cfg = { settle: { damping: 14, stiffness: 140, mass: 0.8 }, pop: { damping: 10, stiffness: 220, mass: 0.7 },
    heavy: { damping: 18, stiffness: 180, mass: 1 }, elastic: { damping: 8, stiffness: 200, mass: 0.8 } }[kind];
  return spring({ frame: f - at, fps: 30, config: cfg });
};
/** Deterministic pseudo-random 0..1 (never use Math.random in scenes). */
export const rand = (n: number) => { const x = Math.sin(n * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); };

// ---------- scene context: narration timing for THIS scene ----------
export type Word = { text: string; from: number; to: number };   // local frames of this scene
export type SceneInfo = {
  index: number; durationInFrames: number; sceneStart: number; preFrames: number;
  words: Word[]; line: string; language: string; accent: string;
  visemes: [number, string][]; emphasis: string;
};
export const SceneCtx = createContext<SceneInfo | null>(null);
export const useScene = (): SceneInfo => {
  const s = useContext(SceneCtx);
  if (!s) throw new Error("useScene() outside a scene");
  return s;
};
/** Local frame when `word` (first match, case-insensitive, partial ok) is spoken in this scene. */
export const useWordAt = (word: string, fallback = 0) => {
  const s = useScene();
  const w = word.toLowerCase();
  const hit = s.words.find((x) => x.text.toLowerCase().includes(w));
  return hit ? hit.from : fallback;
};
export const useF = () => useCurrentFrame();
export const useFps = () => useVideoConfig().fps;
