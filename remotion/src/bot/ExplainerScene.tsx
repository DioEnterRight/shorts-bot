import React from "react";
import { AbsoluteFill, Easing, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { CameraMotionBlur } from "@remotion/motion-blur";
import { RadialBurst } from "../library/remocn/registry/radial-burst";
import { Overlay } from "./Overlay";
import type { BotProps, BotScene } from "./schema";

const ease = Easing.bezier(0.33, 0, 0.2, 1);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Same camera vocabulary as the ffmpeg renderer, but eased and with motion blur on fast moves.
export const cameraTransform = (camera: BotScene["camera"], frame: number, dur: number) => {
  const p = interpolate(frame, [0, dur], [0, 1], { ...clamp, easing: ease });
  switch (camera) {
    case "punch_in": {
      const k = interpolate(frame, [0, 8], [1.35, 1.1], { ...clamp, easing: Easing.out(Easing.back(2)) });
      return `scale(${k + p * 0.06})`;
    }
    case "zoom_in": return `scale(${1.05 + p * 0.15})`;
    case "zoom_out": return `scale(${1.22 - p * 0.15})`;
    case "pan_left": return `scale(1.18) translateX(${60 - p * 120}px)`;
    case "pan_right": return `scale(1.18) translateX(${-60 + p * 120}px)`;
    case "pan_up": return `scale(1.18) translateY(${80 - p * 160}px)`;
    case "pan_down": return `scale(1.18) translateY(${-80 + p * 160}px)`;
    case "shake": {
      const s = Math.max(0, 1 - frame / 12) * 28;
      return `scale(1.15) translate(${Math.sin(frame * 2.7) * s}px, ${Math.cos(frame * 3.1) * s}px)`;
    }
  }
};

export const ExplainerScene: React.FC<{ s: BotScene; p: BotProps; impact: boolean }> = ({ s, p, impact }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const pre = s.transitionFrames / 2; // the part of this scene shown before its cut
  const local = Math.max(0, frame - pre);
  const src = staticFile(s.media as string);
  const fast = s.camera === "punch_in" || s.camera === "shake";
  const media = s.mediaIsVideo ? (
    <OffthreadVideo src={src} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
  ) : (
    <Img src={src} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
  );
  const moved = (
    <AbsoluteFill style={{ transform: cameraTransform(s.camera, local, durationInFrames - pre), transformOrigin: "50% 40%" }}>
      {media}
    </AbsoluteFill>
  );
  return (
    <AbsoluteFill style={{ backgroundColor: "#111" }}>
      {fast && local < 10 ? <CameraMotionBlur shutterAngle={180} samples={4}>{moved}</CameraMotionBlur> : moved}
      {/* soft vignette keeps captions readable on bright pictures */}
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(0,0,0,0) 55%, rgba(0,0,0,.45) 100%)" }} />
      {impact && local < 14 && (
        <AbsoluteFill style={{ mixBlendMode: "screen", opacity: interpolate(local, [0, 3, 14], [0, 0.85, 0], clamp) }}>
          <RadialBurst color="#ffffff" accentColor={p.accent} backgroundColor="transparent" intensity={1.2} speed={1.6} />
        </AbsoluteFill>
      )}
      {s.overlay && <Overlay text={s.overlay} p={p} startAt={pre + 6} />}
    </AbsoluteFill>
  );
};
