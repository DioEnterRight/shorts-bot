import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { fitTextOnNLines } from "@remotion/layout-utils";
import * as Lucide from "lucide-react";
import { C, FONT, SAFE, ease, prog, rand, sp, useScene } from "./core";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// ---------- backgrounds: never a dead-still frame ----------
export const Stage: React.FC<{ from?: string; to?: string; pattern?: "dots" | "grid" | "rays" | "none"; children?: React.ReactNode }> =
  ({ from = C.sky, to = C.cool, pattern = "dots", children }) => {
    const f = useCurrentFrame();
    const drift = (f * 0.6) % 60;
    return (
      <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 35%, ${from}, ${to})`, overflow: "hidden" }}>
        {pattern === "dots" && <AbsoluteFill style={{ backgroundImage: "radial-gradient(rgba(255,255,255,.35) 3px, transparent 3px)", backgroundSize: "60px 60px", backgroundPosition: `${drift}px ${drift}px` }} />}
        {pattern === "grid" && <AbsoluteFill style={{ backgroundImage: "linear-gradient(rgba(255,255,255,.18) 2px, transparent 2px), linear-gradient(90deg, rgba(255,255,255,.18) 2px, transparent 2px)", backgroundSize: "90px 90px", backgroundPosition: `0 ${drift}px` }} />}
        {pattern === "rays" && <AbsoluteFill style={{ background: `repeating-conic-gradient(from ${f * 0.4}deg at 50% 40%, rgba(255,255,255,.14) 0 10deg, transparent 10deg 20deg)` }} />}
        <AbsoluteFill style={{ background: "radial-gradient(circle at 50% 45%, transparent 55%, rgba(0,0,0,.28))" }} />
        {children}
      </AbsoluteFill>
    );
  };

/** Absolutely positioned box, centred on x/y of the 1080x1920 canvas (w/h optional fixed size). */
export const At: React.FC<{ x: number; y: number; w?: number; h?: number; children?: React.ReactNode; style?: React.CSSProperties }> =
  ({ x, y, w, h, children, style }) => (
    <div style={{ position: "absolute", left: x, top: y, width: w, height: h, transform: "translate(-50%, -50%)", display: "flex", alignItems: "center", justifyContent: "center", ...style }}>{children}</div>
  );

/** Spring entrance at local frame `at` (+ optional idle motion after it lands). */
export const Pop: React.FC<{ at?: number; kind?: "settle" | "pop" | "heavy" | "elastic"; idle?: "none" | "float" | "pulse" | "wobble" | "spin"; children: React.ReactNode }> =
  ({ at = 0, kind = "pop", idle = "none", children }) => {
    const f = useCurrentFrame();
    const k = sp(f, at, kind);
    const t = Math.max(0, f - at) / 30;
    const idleT = idle === "float" ? `translateY(${Math.sin(t * 2.4) * 16}px)` : idle === "pulse" ? `scale(${1 + Math.sin(t * 6) * 0.05})`
      : idle === "wobble" ? `rotate(${Math.sin(t * 5) * 5}deg)` : idle === "spin" ? `rotate(${t * 90}deg)` : "";
    return <div style={{ transform: `scale(${k}) ${idleT}`, opacity: Math.min(1, k * 2) }}>{children}</div>;
  };

/** Leaves fast (ease-in) starting at `at`, over `dur` frames. */
export const Exit: React.FC<{ at: number; dur?: number; to?: "down" | "up" | "shrink"; children: React.ReactNode }> = ({ at, dur = 10, to = "shrink", children }) => {
  const f = useCurrentFrame();
  const p = prog(f, at, at + dur, ease.in);
  const tr = to === "down" ? `translateY(${p * 400}px)` : to === "up" ? `translateY(${-p * 400}px)` : `scale(${1 - p})`;
  return <div style={{ transform: tr, opacity: 1 - p }}>{children}</div>;
};

/** Big headline that fits the safe width in ≤ maxLines; words rise in, staggered from `at`. One word can be the accent. */
export const Headline: React.FC<{ text: string; at?: number; accent?: string; color?: string; maxLines?: number; maxSize?: number; width?: number }> =
  ({ text, at = 0, accent = "", color = "#fff", maxLines = 2, maxSize = 150, width = SAFE.w }) => {
    const f = useCurrentFrame();
    const { language } = useScene();
    const fam = language === "hi" ? "Noto Sans Devanagari" : "Anton";
    const { fontSize } = fitTextOnNLines({ text, maxLines, maxBoxWidth: width, fontFamily: fam, fontWeight: language === "hi" ? "700" : "400", maxFontSize: maxSize, validateFontIsLoaded: false });
    return (
      <div style={{ width, textAlign: "center", fontFamily: FONT.display, fontSize, lineHeight: language === "hi" ? 1.35 : 1.02, color, fontWeight: language === "hi" ? 700 : 400,
        textShadow: "0 8px 0 rgba(0,0,0,.25)", WebkitTextStroke: `${Math.max(4, fontSize / 22)}px ${C.ink}`, paintOrder: "stroke fill" }}>
        {text.split(" ").map((w, i) => {
          const p = prog(f, at + i * 3, at + i * 3 + 14);
          const isAcc = accent && w.toLowerCase().includes(accent.toLowerCase());
          return <span key={i} style={{ display: "inline-block", margin: "0 0.12em", transform: `translateY(${(1 - p) * 60}px) rotate(${(1 - p) * -6}deg)`, opacity: p, color: isAcc ? C.accent : color }}>{w}</span>;
        })}
      </div>
    );
  };

/** Small sticker label (≤ 4 words). */
export const Tag: React.FC<{ text: string; at?: number; bg?: string; color?: string; size?: number; rotate?: number }> =
  ({ text, at = 0, bg = "#fff", color = C.ink, size = 64, rotate = -3 }) => {
    const f = useCurrentFrame();
    const k = sp(f, at, "pop");
    return <div style={{ background: bg, color, fontFamily: FONT.ui, fontWeight: 800, fontSize: size, padding: "12px 30px", borderRadius: 26, border: `7px solid ${C.ink}`, boxShadow: `0 10px 0 ${C.ink}`, transform: `scale(${k}) rotate(${rotate}deg)`, whiteSpace: "nowrap" }}>{text}</div>;
  };

/** Number that counts up from `from` to `to` between local frames at..at+dur. */
export const Counter: React.FC<{ to: number; from?: number; at?: number; dur?: number; prefix?: string; suffix?: string; decimals?: number; size?: number; color?: string }> =
  ({ to, from = 0, at = 0, dur = 30, prefix = "", suffix = "", decimals = 0, size = 200, color = "#fff" }) => {
    const f = useCurrentFrame();
    const v = from + (to - from) * prog(f, at, at + dur, ease.land);
    return <div style={{ fontFamily: FONT.display, fontSize: size, color, WebkitTextStroke: `${size / 22}px ${C.ink}`, paintOrder: "stroke fill", fontVariantNumeric: "tabular-nums" }}>{prefix}{v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}{suffix}</div>;
  };

/** Any lucide icon by name (e.g. "Flame", "Snowflake", "Brain", "HeartPulse", "Bug", "Droplet", "Clock", "Zap"). */
export const Icon: React.FC<{ name: string; size?: number; color?: string; fill?: string; stroke?: number }> = ({ name, size = 220, color = C.ink, fill = "none", stroke = 2.2 }) => {
  const Comp = (Lucide as unknown as Record<string, React.FC<Record<string, unknown>>>)[name] ?? Lucide.CircleHelp;
  return <Comp size={size} color={color} fill={fill} strokeWidth={stroke} />;
};

/** Arrow that draws itself from (x1,y1) to (x2,y2) on the full canvas, optionally curved. */
export const Arrow: React.FC<{ x1: number; y1: number; x2: number; y2: number; at?: number; dur?: number; curve?: number; color?: string; width?: number; flow?: boolean }> =
  ({ x1, y1, x2, y2, at = 0, dur = 14, curve = 0, color = C.ink, width = 16, flow = false }) => {
    const f = useCurrentFrame();
    const p = prog(f, at, at + dur, ease.inOut);
    const mx = (x1 + x2) / 2 - (y2 - y1) * curve, my = (y1 + y2) / 2 + (x2 - x1) * curve;
    const d = `M${x1} ${y1} Q${mx} ${my} ${x2} ${y2}`;
    const len = Math.hypot(x2 - x1, y2 - y1) * (1 + Math.abs(curve));
    const ang = Math.atan2(y2 - my, x2 - mx) * 180 / Math.PI;
    return (
      <svg width={1080} height={1920} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
        <path d={d} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" strokeDasharray={flow ? "36 22" : `${len} ${len}`}
          strokeDashoffset={flow ? -f * 3 : len * (1 - p)} opacity={flow ? p : 1} />
        {p > 0.9 && <path d="M-34 -26 L10 0 L-34 26Z" fill={color} transform={`translate(${x2} ${y2}) rotate(${ang})`} />}
      </svg>
    );
  };

/** Circle/underline that draws around something at (x,y). */
export const Ring: React.FC<{ x: number; y: number; r?: number; at?: number; color?: string }> = ({ x, y, r = 160, at = 0, color = C.hot }) => {
  const f = useCurrentFrame();
  const p = prog(f, at, at + 16, ease.out);
  const len = 2 * Math.PI * r * 1.1;
  return (
    <svg width={1080} height={1920} style={{ position: "absolute", left: 0, top: 0 }}>
      <ellipse cx={x} cy={y} rx={r * 1.1} ry={r} fill="none" stroke={color} strokeWidth={12} strokeLinecap="round" strokeDasharray={`${len} ${len}`} strokeDashoffset={len * (1 - p)} transform={`rotate(-12 ${x} ${y})`} />
    </svg>
  );
};

/** Horizontal meter/gauge 0..1 that fills to `value` from `at`. */
export const Meter: React.FC<{ value: number; label?: string; at?: number; color?: string; width?: number }> = ({ value, label = "", at = 0, color = C.hot, width = 760 }) => {
  const f = useCurrentFrame();
  const v = value * prog(f, at, at + 26, ease.land);
  return (
    <div style={{ width, fontFamily: FONT.ui, fontWeight: 800, color: "#fff" }}>
      {label && <div style={{ fontSize: 52, marginBottom: 12, WebkitTextStroke: `4px ${C.ink}`, paintOrder: "stroke fill" }}>{label}</div>}
      <div style={{ height: 64, borderRadius: 32, background: "#fff", border: `7px solid ${C.ink}`, overflow: "hidden" }}>
        <div style={{ width: `${v * 100}%`, height: "100%", background: color, borderRight: v > 0.02 ? `7px solid ${C.ink}` : "none" }} />
      </div>
    </div>
  );
};

/** Vertical bars that grow one by one. Values are relative (max = tallest). */
export const Bars: React.FC<{ items: { label: string; value: number; color?: string }[]; at?: number; height?: number; width?: number }> =
  ({ items, at = 0, height = 620, width = 900 }) => {
    const f = useCurrentFrame();
    const max = Math.max(...items.map((i) => i.value));
    const bw = Math.min(200, (width - 40 * (items.length - 1)) / items.length);
    return (
      <div style={{ display: "flex", alignItems: "flex-end", gap: 40, height: height + 90, fontFamily: FONT.ui, fontWeight: 800 }}>
        {items.map((it, i) => {
          const p = prog(f, at + i * 8, at + i * 8 + 22, ease.land);
          return (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
              <div style={{ width: bw, height: (it.value / max) * height * p, background: it.color ?? C.cool, border: `7px solid ${C.ink}`, borderRadius: 18 }} />
              <div style={{ fontSize: 44, color: "#fff", WebkitTextStroke: `4px ${C.ink}`, paintOrder: "stroke fill", maxWidth: bw + 40, textAlign: "center" }}>{it.label}</div>
            </div>
          );
        })}
      </div>
    );
  };

/** Two-panel comparison (left vs right) that slides in. */
export const Split: React.FC<{ left: React.ReactNode; right: React.ReactNode; at?: number; leftBg?: string; rightBg?: string }> =
  ({ left, right, at = 0, leftBg = C.cool, rightBg = C.hot }) => {
    const f = useCurrentFrame();
    const p = prog(f, at, at + 14, ease.out);
    const panel = (bg: string, from: number): React.CSSProperties => ({ flex: 1, background: bg, border: `8px solid ${C.ink}`, borderRadius: 40, display: "flex", alignItems: "center", justifyContent: "center", transform: `translateX(${(1 - p) * from}px)`, overflow: "hidden" });
    return (
      <div style={{ display: "flex", gap: 30, width: SAFE.w, height: 900 }}>
        <div style={panel(leftBg, -700)}>{left}</div><div style={panel(rightBg, 700)}>{right}</div>
      </div>
    );
  };

/** Burst of small particles from (x,y) at `at` (impact moments). */
export const Burst: React.FC<{ x: number; y: number; at?: number; color?: string; n?: number }> = ({ x, y, at = 0, color = C.accent, n = 14 }) => {
  const f = useCurrentFrame();
  const p = prog(f, at, at + 22, ease.out);
  if (f < at || p >= 1) return null;
  return <>{Array.from({ length: n }).map((_, i) => {
    const a = (i / n) * Math.PI * 2 + rand(i) * 0.4, d = 80 + 260 * p * (0.6 + rand(i + 9) * 0.6);
    return <div key={i} style={{ position: "absolute", left: x + Math.cos(a) * d - 14, top: y + Math.sin(a) * d - 14, width: 28, height: 28, borderRadius: i % 2 ? 6 : 14, background: color, border: `4px solid ${C.ink}`, opacity: 1 - p, transform: `rotate(${p * 200}deg)` }} />;
  })}</>;
};

/** Camera move over the whole scene content. */
export const Camera: React.FC<{ move?: "push" | "pull" | "pan_left" | "pan_right" | "shake" | "still"; children: React.ReactNode }> = ({ move = "push", children }) => {
  const f = useCurrentFrame();
  const { durationInFrames } = useScene();
  const p = interpolate(f, [0, durationInFrames], [0, 1], { ...clamp, easing: ease.inOut });
  const tr = move === "push" ? `scale(${1 + p * 0.08})` : move === "pull" ? `scale(${1.08 - p * 0.08})`
    : move === "pan_left" ? `translateX(${40 - p * 80}px) scale(1.06)` : move === "pan_right" ? `translateX(${-40 + p * 80}px) scale(1.06)`
    : move === "shake" ? `translate(${Math.sin(f * 2.7) * Math.max(0, 1 - f / 12) * 24}px, ${Math.cos(f * 3.1) * Math.max(0, 1 - f / 12) * 24}px)` : "";
  return <AbsoluteFill style={{ transform: tr, transformOrigin: "50% 42%" }}>{children}</AbsoluteFill>;
};
