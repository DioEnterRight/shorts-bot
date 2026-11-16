import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import type { TransitionPresentation } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { irisWipe } from "../library/remocn/registry/iris-wipe";
import { waveWipe } from "../library/remocn/registry/wave-wipe";
import { whipPan } from "../library/remocn/registry/whip-pan";
import { zoomBlur } from "../library/remocn/registry/zoom-blur";
import { BlockyScene } from "./BlockyScene";
import { Captions } from "./Captions";
import { ExplainerScene } from "./ExplainerScene";
import { loadBotFonts } from "./fonts";
import type { BotProps, BotScene } from "./schema";

loadBotFonts();

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const presentation = (kind: BotScene["transitionIn"], i: number): TransitionPresentation<any> => {
  switch (kind) {
    case "whip": return whipPan({ direction: i % 2 ? "left" : "right" });
    case "zoom": return zoomBlur({});
    case "iris": return irisWipe({});
    case "wave": return waveWipe({});
    default: return fade();
  }
};

// Python (pipeline/remotion_render.py) owns all timing; this only draws it.
export const ShortsBot: React.FC<BotProps> = (p) => {
  const impactAt = new Set(p.sfx.filter((q) => q.name === "hit").map((q) => q.frame));
  let start = 0;
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <TransitionSeries>
        {p.scenes.map((s, i) => {
          start += i ? p.scenes[i - 1].durationInFrames - s.transitionFrames : 0;
          const from = start;
          const impact = [...impactAt].some((f) => f >= from && f < from + s.durationInFrames);
          return (
            <React.Fragment key={i}>
              {i > 0 && s.transitionFrames > 0 && (
                <TransitionSeries.Transition presentation={presentation(s.transitionIn, i)} timing={linearTiming({ durationInFrames: s.transitionFrames })} />
              )}
              <TransitionSeries.Sequence durationInFrames={s.durationInFrames}>
                {p.style === "blocky" ? <BlockyScene s={s} p={p} index={i} /> : <ExplainerScene s={s} p={p} impact={impact} />}
              </TransitionSeries.Sequence>
            </React.Fragment>
          );
        })}
      </TransitionSeries>
      <Captions p={p} />
      <Audio src={staticFile(p.audio)} />
      {p.sfx.map((q, i) => (
        <Sequence key={i} from={q.frame} durationInFrames={45} layout="none">
          <Audio src={staticFile(`sfx/${q.name}.wav`)} volume={q.volume} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
