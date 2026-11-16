import React from "react";
import { AbsoluteFill } from "remotion";
import { CaptionActivePop } from "../library/remocn/registry/caption-active-pop";
import { CaptionBounceIn } from "../library/remocn/registry/caption-bounce-in";
import { CaptionHighlightBox } from "../library/remocn/registry/caption-highlight-box";
import { CaptionKaraoke } from "../library/remocn/registry/caption-karaoke";
import { CaptionOutline } from "../library/remocn/registry/caption-outline";
import { CaptionStamp } from "../library/remocn/registry/caption-stamp";
import { CaptionWordPop } from "../library/remocn/registry/caption-word-pop";
import { fontFor } from "./fonts";
import type { BotProps } from "./schema";

const STYLE = {
  word_pop: CaptionWordPop,
  karaoke: CaptionKaraoke,
  highlight_box: CaptionHighlightBox,
  bounce_in: CaptionBounceIn,
  active_pop: CaptionActivePop,
  outline: CaptionOutline,
  stamp: CaptionStamp,
} as const;

// Lower third, above the Shorts/Reels buttons and title (same zone the ffmpeg renderer used).
export const Captions: React.FC<{ p: BotProps }> = ({ p }) => {
  const Comp = STYLE[p.captionStyle] as React.FC<{ captions: BotProps["captions"]; fontSize?: number; fontWeight?: number; color?: string }>;
  const hindi = p.language === "hi";
  const captions = p.uppercase ? p.captions.map((c) => ({ ...c, text: c.text.toUpperCase() })) : p.captions;
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 430 }}>
      <div
        style={{
          width: 940,
          fontFamily: fontFor(p.language, "caption"),
          // Devanagari needs room above/below for matras; the outline keeps it readable on any picture.
          lineHeight: hindi ? 1.45 : 1.1,
          WebkitTextStroke: hindi ? "8px #000" : "10px #000",
          paintOrder: "stroke fill",
          textAlign: "center",
        }}
      >
        <Comp captions={captions} fontSize={hindi ? 104 : 124} fontWeight={hindi ? 800 : 400} color="#ffffff" />
      </div>
    </AbsoluteFill>
  );
};
