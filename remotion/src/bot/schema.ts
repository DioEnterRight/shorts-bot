import { z } from "zod";

// Mirror of pipeline/remotion_render.py validate_props(). Remotion checks every render's props
// against this, so a bad handoff from Python fails before any frame is drawn.
export const CAMERAS = ["punch_in", "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "shake"] as const;
export const TRANSITIONS = ["cut", "whip", "zoom", "fade", "iris", "wave"] as const;
export const CAPTION_STYLES = ["word_pop", "karaoke", "highlight_box", "bounce_in", "active_pop", "outline", "stamp"] as const;
export const POSES = ["talk", "wave", "think", "walk", "jump", "shock"] as const;
export const LAYOUTS = ["actor", "props", "versus", "inside"] as const;
export const MOTIONS = ["pop", "pulse", "shake", "float", "spin", "grow", "bounce", "drip"] as const;
export const MOODS = ["fun", "calm", "warm", "cold", "danger", "body", "night"] as const;
export const EXPRESSIONS = ["neutral", "happy", "shock", "sick", "sleepy", "think", "hot", "cold", "pain"] as const;

const scene = z.object({
  durationInFrames: z.number().int().positive(),
  transitionIn: z.enum(TRANSITIONS),
  transitionFrames: z.number().int().nonnegative(),
  line: z.string(),
  media: z.string().nullable(),
  mediaIsVideo: z.boolean(),
  camera: z.enum(CAMERAS),
  overlay: z.string(),
  shot: z.string(),
  emphasis: z.string(),
  blocky: z.object({ pose: z.enum(POSES), pair: z.boolean() }),
  component: z.string().nullable(),
  cartoon: z.object({
    layout: z.enum(LAYOUTS),
    expression: z.enum(EXPRESSIONS),
    mood: z.enum(MOODS),
    props: z.array(z.object({ name: z.string(), motion: z.enum(MOTIONS) })).max(3),
  }),
});

export const botSchema = z
  .object({
    fps: z.literal(30),
    width: z.literal(1080),
    height: z.literal(1920),
    durationInFrames: z.number().int().positive(),
    language: z.string(),
    style: z.enum(["explainer", "cartoon", "blocky", "bespoke"]),
    visemes: z.array(z.tuple([z.number().int(), z.string()])),
    captionStyle: z.enum(CAPTION_STYLES),
    uppercase: z.boolean(),
    accent: z.string().regex(/^#[0-9A-Fa-f]{6}$/),
    audio: z.string(),
    scenes: z.array(scene).min(1),
    captions: z.array(
      z.object({
        text: z.string(),
        startMs: z.number(),
        endMs: z.number(),
        timestampMs: z.number().nullable(),
        confidence: z.number().nullable(),
      }),
    ),
    sfx: z.array(z.object({ name: z.enum(["hit", "pop", "tick", "whoosh"]), frame: z.number().int().nonnegative(), volume: z.number() })),
  })
  .superRefine((p, ctx) => {
    const series = p.scenes.reduce((a, s) => a + s.durationInFrames - s.transitionFrames, 0);
    if (series !== p.durationInFrames) {
      ctx.addIssue({ code: "custom", message: `scene frames ${series} != durationInFrames ${p.durationInFrames}` });
    }
    if (p.scenes[0].transitionFrames !== 0) ctx.addIssue({ code: "custom", message: "first scene cannot have a transition" });
    p.scenes.forEach((s, i) => {
      if (p.style === "explainer" && !s.media) ctx.addIssue({ code: "custom", message: `scene ${i} has no picture` });
    });
  });

export type BotProps = z.infer<typeof botSchema>;
export type BotScene = BotProps["scenes"][number];
