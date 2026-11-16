import React from "react";
import { AbsoluteFill, Sequence, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { AnimatedCounter } from "remotion-bits";
import { MarkerHighlight } from "../library/remocn/registry/marker-highlight";
import { fontFor } from "./fonts";
import type { BotProps } from "./schema";

// "37°C", "70%", "1,000" -> a counting number (remotion-bits). Anything else -> marker sticker (remocn).
const NUMBER = /^([^\d-]*)(-?[\d,]+(?:\.\d+)?)(.*)$/;

const Sticker: React.FC<{ text: string; p: BotProps }> = ({ text, p }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 10, stiffness: 180 } });
  const m = text.match(NUMBER);
  const body = m ? (
    <AnimatedCounter
      transition={{ values: [0, Number(m[2].replace(/,/g, ""))], duration: 24 }}
      prefix={m[1].replace(/ $/, "\u00a0")}
      postfix={m[3].replace(/^ /, "\u00a0")}
      toFixed={m[2].includes(".") ? 1 : 0}
      style={{ fontSize: 120, fontWeight: 800, color: "#111" }}
    />
  ) : (
    <MarkerHighlight highlight={p.uppercase ? text.toUpperCase() : text} markerColor={p.accent} baseColor="#111"
      highlightedTextColor="#111" fontSize={p.language === "hi" ? 78 : 86} fontWeight={800} />
  );
  return (
    <div style={{ background: "#fff", border: "8px solid #111", borderRadius: 32, padding: "18px 40px",
      boxShadow: "0 14px 0 #111", fontFamily: fontFor(p.language, "label"),
      transform: `scale(${pop}) rotate(${-4 + pop * 2}deg)` }}>
      {body}
    </div>
  );
};

export const Overlay: React.FC<{ text: string; p: BotProps; startAt: number }> = ({ text, p, startAt }) => (
  <Sequence from={Math.round(startAt)} layout="none">
    <AbsoluteFill style={{ alignItems: "center", paddingTop: 170 }}>
      <Sticker text={text} p={p} />
    </AbsoluteFill>
  </Sequence>
);
