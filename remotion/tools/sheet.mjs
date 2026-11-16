// Contact sheet for the self-review loop: renders 2 small stills per scene of ShortsBot
// (just after it settles, and near its end), tiles them into one PNG, and reports scenes that crash.
//
//   node tools/sheet.mjs --props <props.json> --public-dir <dir> [--out out/sheet.png] [--report out/sheet.json]
//
// Tiles go left->right, top->bottom: scene 1 early, scene 1 late, scene 2 early, ...
// Each tile has its scene number and frame burned in the top-left corner.
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const propsPath = arg("--props");
const publicDir = arg("--public-dir");
const out = path.resolve(arg("--out", "out/sheet.png"));
const report = path.resolve(arg("--report", "out/sheet.json"));
if (!propsPath || !publicDir) throw new Error("usage: --props <file> --public-dir <dir>");
const browserExecutable = process.env.REMOTION_BROWSER || null;
const props = JSON.parse(fs.readFileSync(propsPath, "utf8"));
const tmp = fs.mkdtempSync("/tmp/sheet-");
fs.mkdirSync(path.dirname(out), { recursive: true });

const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts"), publicDir: path.resolve(publicDir) });
const chromiumOptions = { gl: "swangle" };
const composition = await selectComposition({ serveUrl, id: "ShortsBot", inputProps: props, browserExecutable, chromiumOptions });

const frames = [];
let start = 0;
props.scenes.forEach((s, i) => {
  if (i) start += props.scenes[i - 1].durationInFrames - s.transitionFrames;
  const pre = s.transitionFrames / 2;
  const early = Math.round(start + pre + Math.min(20, s.durationInFrames * 0.35));
  const late = Math.round(start + s.durationInFrames - s.transitionFrames / 2 - 6);
  frames.push({ scene: i + 1, frame: early }, { scene: i + 1, frame: Math.max(early + 1, late) });
});

const failed = new Set();
const tiles = [];
for (const [k, fr] of frames.entries()) {
  const file = path.join(tmp, `t${String(k).padStart(3, "0")}.png`);
  try {
    await renderStill({ composition, serveUrl, output: file, frame: fr.frame, inputProps: props, scale: 0.3, browserExecutable, chromiumOptions });
    // burn "S3 f120" label
    const lab = path.join(tmp, `l${String(k).padStart(3, "0")}.png`);
    execFileSync("ffmpeg", ["-v", "error", "-y", "-i", file, "-vf",
      `drawbox=x=0:y=0:w=150:h=46:color=black@0.7:t=fill,drawtext=text='S${fr.scene} f${fr.frame}':x=8:y=10:fontsize=26:fontcolor=white`, lab]);
    tiles.push(lab);
  } catch (e) {
    failed.add(fr.scene);
    console.error(`Scene ${fr.scene} frame ${fr.frame} failed: ${String(e.message).slice(0, 400)}`);
  }
}
if (tiles.length) {
  const cols = 6;
  const rows = Math.ceil(tiles.length / cols);
  execFileSync("ffmpeg", ["-v", "error", "-y", "-framerate", "1", "-pattern_type", "glob", "-i", path.join(tmp, "l*.png"),
    "-vf", `tile=${cols}x${rows}:padding=6:color=white`, "-frames:v", "1", out]);
}
fs.writeFileSync(report, JSON.stringify({ sheet: tiles.length ? out : null, failedScenes: [...failed].sort((a, b) => a - b) }, null, 1));
console.log(`sheet: ${out}  failed scenes: ${JSON.stringify([...failed])}`);
