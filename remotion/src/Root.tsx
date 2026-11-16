import React from "react";
import { Composition } from "remotion";
import { ShortsBot } from "./bot/ShortsBot";
import { botSchema, type BotProps } from "./bot/schema";
import sample from "./bot/sample-props.json";

// ShortsBot: what the daily bot renders (props come from pipeline/remotion_render.py).
// sample-props.json is only the Studio preview (blocky style, so it needs no pictures).
// Only one composition is registered: `remotion compositions --props` runs every composition's
// calculateMetadata with the bot's props. The vendored kits under src/library/ are imported as parts.
export const Root: React.FC = () => (
  <>
    <Composition
      id="ShortsBot"
      component={ShortsBot}
      schema={botSchema}
      defaultProps={sample as BotProps}
      calculateMetadata={({ props }) => {
        // Remotion 4 only warns on schema errors; a bad handoff from Python must stop the render.
        const ok = botSchema.safeParse(props);
        if (!ok.success) throw new Error(`ShortsBot props rejected: ${ok.error.message}`);
        return {
        durationInFrames: props.durationInFrames,
        fps: props.fps,
        width: props.width,
        height: props.height,
        };
      }}
    />
  </>
);
