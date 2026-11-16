import React from "react";
import { Root as ShortsSkillRoot } from "./library/shorts-skill/Root";

// Entry point for shorts-bot renders. The vendored kits under src/library/ are building blocks:
// - shorts-skill: kinetic-text short (JSON scenes, safe zones, reading-speed timing)
// - vibe-motion: explainer shot library (causal diagrams, reveals, camera moves)
// - remocn: captions, transitions, impacts (MIT, curated, CPU-safe)
// - remotion-bits (npm): particles, 3D cards, staggered text
// The shorts-bot provider compositions get added here when the pipeline is wired up.
export const Root: React.FC = () => <ShortsSkillRoot />;
