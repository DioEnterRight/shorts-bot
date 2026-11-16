import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { ThreeCanvas } from "@remotion/three";
import { Overlay } from "./Overlay";
import { cameraTransform } from "./ExplainerScene";
import type { BotProps, BotScene } from "./schema";

// Original blocky toy characters (no game branding): cube head, box body, box limbs, toon shading.
// All motion is a pure function of the frame, so every render of the same props is identical.
type Look = { skin: string; shirt: string; pants: string };
const LOOKS: Look[] = [
  { skin: "#ffd23f", shirt: "#3a86ff", pants: "#2b2d42" },
  { skin: "#ffd23f", shirt: "#ff006e", pants: "#3d405b" },
  { skin: "#f4a261", shirt: "#2a9d8f", pants: "#264653" },
];
const SKIES = [["#7bdff2", "#b2f7ef"], ["#ffafcc", "#bde0fe"], ["#ffd6a5", "#fdffb6"], ["#cdb4db", "#a2d2ff"]];

const Box: React.FC<{ size: [number, number, number]; pos: [number, number, number]; color: string; rot?: [number, number, number] }> = ({ size, pos, color, rot }) => (
  <mesh position={pos} rotation={rot ?? [0, 0, 0]}>
    <boxGeometry args={size} />
    <meshToonMaterial color={color} />
  </mesh>
);

const Character: React.FC<{ look: Look; pose: BotScene["blocky"]["pose"]; t: number; x: number; facing: number }> = ({ look, pose, t, x, facing }) => {
  const swing = pose === "walk" ? Math.sin(t * 9) * 0.7 : 0;
  const hop = pose === "jump" ? Math.abs(Math.sin(t * 5)) * 0.9 : pose === "walk" ? Math.abs(Math.sin(t * 9)) * 0.12 : 0;
  const armUp = pose === "wave" ? -2.6 + Math.sin(t * 12) * 0.35 : pose === "shock" ? -2.9 : pose === "think" ? -1.9 : swing;
  const talk = pose === "talk" ? (Math.sin(t * 22) > 0 ? 0.14 : 0.05) : pose === "shock" ? 0.22 : 0.05;
  const shake = pose === "shock" ? Math.sin(t * 60) * 0.05 : 0;
  return (
    <group position={[x + shake, hop, 0]} rotation={[0, facing, 0]}>
      <Box size={[0.5, 0.75, 0.5]} pos={[-0.27, 0.38, 0]} color={look.pants} rot={[swing, 0, 0]} />
      <Box size={[0.5, 0.75, 0.5]} pos={[0.27, 0.38, 0]} color={look.pants} rot={[-swing, 0, 0]} />
      <Box size={[1.1, 1.0, 0.55]} pos={[0, 1.25, 0]} color={look.shirt} />
      <group position={[-0.78, 1.7, 0]} rotation={[armUp * 0.15, 0, pose === "think" ? 0 : -armUp * 0.25]}>
        <Box size={[0.42, 0.95, 0.42]} pos={[0, -0.45, 0]} color={look.skin} rot={[-swing, 0, 0]} />
      </group>
      <group position={[0.78, 1.7, 0]} rotation={[0, 0, armUp * (pose === "wave" ? 1 : 0.25)]}>
        <Box size={[0.42, 0.95, 0.42]} pos={[0, -0.45, 0]} color={look.skin} rot={[swing, 0, 0]} />
      </group>
      <group position={[0, 2.25, 0]} rotation={[pose === "think" ? 0.15 : 0, 0, pose === "think" ? 0.15 : 0]}>
        <Box size={[0.9, 0.9, 0.9]} pos={[0, 0, 0]} color={look.skin} />
        <Box size={[0.13, pose === "shock" ? 0.26 : 0.18, 0.02]} pos={[-0.2, 0.1, 0.46]} color="#111" />
        <Box size={[0.13, pose === "shock" ? 0.26 : 0.18, 0.02]} pos={[0.2, 0.1, 0.46]} color="#111" />
        <Box size={[0.34, talk, 0.02]} pos={[0, -0.2, 0.46]} color="#111" />
      </group>
    </group>
  );
};

export const BlockyScene: React.FC<{ s: BotScene; p: BotProps; index: number }> = ({ s, p, index }) => {
  const frame = useCurrentFrame();
  const { width, height, fps, durationInFrames } = useVideoConfig();
  const pre = s.transitionFrames / 2;
  const t = frame / fps;
  const [a, b] = SKIES[index % SKIES.length];
  const drift = interpolate(frame, [0, durationInFrames], [0, 1]);
  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, ${a}, ${b})` }}>
      <AbsoluteFill style={{ transform: cameraTransform(s.camera, Math.max(0, frame - pre), durationInFrames - pre) }}>
        <ThreeCanvas width={width} height={height} camera={{ position: [0, 1.9, 14 - drift * 1.5], fov: 38 }} gl={{ alpha: true }}>
          <ambientLight intensity={0.9} />
          <directionalLight position={[4, 8, 6]} intensity={1.6} />
          <Box size={[30, 0.4, 30]} pos={[0, -0.2, -6]} color="#7ae582" />
          {[-6, -3.5, 4, 6.5].map((x, i) => (
            <Box key={i} size={[1.4, 1.4 + (i % 2), 1.4]} pos={[x, 0.7 + (i % 2) * 0.5, -6 - i]} color={["#ffbe0b", "#fb5607", "#8338ec", "#3a86ff"][(i + index) % 4]} />
          ))}
          <group position={[0, 0, 0]} scale={0.85}>
            <Character look={LOOKS[index % LOOKS.length]} pose={s.blocky.pose} t={t} x={s.blocky.pair ? -1.2 : 0} facing={s.blocky.pair ? 0.35 : 0} />
            {s.blocky.pair && <Character look={LOOKS[(index + 1) % LOOKS.length]} pose="talk" t={t + 0.4} x={1.2} facing={-0.35} />}
          </group>
        </ThreeCanvas>
      </AbsoluteFill>
      {s.overlay && <Overlay text={s.overlay} p={p} startAt={pre + 6} />}
    </AbsoluteFill>
  );
};
