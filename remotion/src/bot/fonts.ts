import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

// Bundled fonts (public/fonts, OFL). loadFont blocks rendering until each file is ready.
const FONTS = [
  { family: "Anton", file: "Anton-Regular.ttf" },
  { family: "Poppins", file: "Poppins-ExtraBold.ttf", weight: "800" },
  { family: "Noto Sans", file: "NotoSans-Bold.ttf", weight: "700" },
  { family: "Noto Sans Devanagari", file: "NotoSansDevanagari-Bold.ttf", weight: "700" },
];

let loaded = false;
export const loadBotFonts = () => {
  if (loaded) return;
  loaded = true;
  for (const f of FONTS) {
    loadFont({ family: f.family, url: staticFile(`fonts/${f.file}`), weight: f.weight ?? "400" });
  }
};

// Hindi lines mix Devanagari with Latin words: Devanagari font first, Noto Sans for the Latin glyphs.
export const fontFor = (language: string, use: "caption" | "label") => {
  if (language === "hi") return "'Noto Sans Devanagari', 'Noto Sans', sans-serif";
  return use === "caption" ? "Anton, 'Noto Sans', sans-serif" : "Poppins, 'Noto Sans', sans-serif";
};
