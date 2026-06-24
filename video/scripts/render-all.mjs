// Render one vertical MP4 per Constitution day from data/days.json.
//
// Bundles the Remotion project ONCE, then renders each day with its own input
// props (image, audio, day number, hashtags, per-day duration). The public/
// folder symlinks images_v2 + audio_male so staticFile() resolves the assets.
//
// Usage:
//   node scripts/render-all.mjs            # render all 77 days
//   node scripts/render-all.mjs 1 2 3      # render only the given day numbers

import { bundle } from "@remotion/bundler";
import { selectComposition, renderMedia } from "@remotion/renderer";
import { readFileSync, mkdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");

const days = JSON.parse(readFileSync(path.join(ROOT, "data", "days.json"), "utf8"));

const onlyDays = process.argv.slice(2).map(Number).filter((n) => Number.isFinite(n));
const targets = onlyDays.length ? days.filter((d) => onlyDays.includes(d.day)) : days;

if (targets.length === 0) {
  console.error("No matching days to render.");
  process.exit(1);
}

const OUT_DIR = path.join(ROOT, "videos");
mkdirSync(OUT_DIR, { recursive: true });

console.log("Bundling Remotion project (once)...");
const serveUrl = await bundle({
  entryPoint: path.join(ROOT, "src", "index.ts"),
  publicDir: path.join(ROOT, "public"),
  onSymlinkDetected: () => {}, // symlinked images_v2 + audio_male are expected
});
console.log(`Bundle ready. Rendering ${targets.length} video(s)...\n`);

let ok = 0;
const failures = [];

for (const d of targets) {
  const id = String(d.day).padStart(2, "0");
  const out = path.join(OUT_DIR, `day_${id}.mp4`);
  try {
    const composition = await selectComposition({
      serveUrl,
      id: "ConstitutionDay",
      inputProps: d,
    });
    await renderMedia({
      composition,
      serveUrl,
      codec: "h264",
      audioCodec: "aac",
      crf: 23,
      outputLocation: out,
      inputProps: d,
    });
    const mb = (statSync(out).size / 1e6).toFixed(1);
    console.log(`✓ day ${id}  ${composition.durationInFrames}f  ${mb}MB  ${d.section}`);
    ok++;
  } catch (e) {
    const msg = e && e.message ? e.message : String(e);
    console.error(`✗ day ${id} FAILED: ${msg}`);
    failures.push({ day: d.day, error: msg });
  }
}

console.log(`\nDone. ${ok}/${targets.length} rendered. ${failures.length} failed.`);
if (failures.length) {
  console.error("Failures:", JSON.stringify(failures, null, 2));
  process.exit(1);
}
