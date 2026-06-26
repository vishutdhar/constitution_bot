// Render one verification still per day (frame 45, after header+footer fade in)
// into out/stills/day_NN.png. Used to visually QA all 77 days quickly without
// inspecting full videos. Reuses one bundle.
//
// Usage: node scripts/render-stills.mjs   (all days)
//        node scripts/render-stills.mjs 1 2 3

import { bundle } from "@remotion/bundler";
import { selectComposition, renderStill } from "@remotion/renderer";
import { readFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const days = JSON.parse(readFileSync(path.join(ROOT, "data", "days.json"), "utf8"));

const rawDayArgs = process.argv.slice(2);
const onlyDays = rawDayArgs.map(Number).filter((n) => Number.isInteger(n));
// If args were given but none parse to a valid day number, fail fast instead
// of silently re-rendering stills for all 77 days.
if (rawDayArgs.length > 0 && onlyDays.length === 0) {
  console.error(`No valid day numbers in arguments: ${rawDayArgs.join(" ")}`);
  process.exit(1);
}
const targets = onlyDays.length ? days.filter((d) => onlyDays.includes(d.day)) : days;
if (targets.length === 0) {
  console.error("No matching days for stills.");
  process.exit(1);
}

const OUT = path.join(ROOT, "out", "stills");
mkdirSync(OUT, { recursive: true });

console.log("Bundling...");
const serveUrl = await bundle({
  entryPoint: path.join(ROOT, "src", "index.ts"),
  publicDir: path.join(ROOT, "public"),
  onSymlinkDetected: () => {},
});

let ok = 0;
const failures = [];
for (const d of targets) {
  const id = String(d.day).padStart(2, "0");
  const FRAME = 45;
  try {
    const composition = await selectComposition({ serveUrl, id: "ConstitutionDay", inputProps: d });
    await renderStill({
      composition,
      serveUrl,
      frame: Math.min(FRAME, composition.durationInFrames - 1),
      output: path.join(OUT, `day_${id}.png`),
      inputProps: d,
      // Full scale: at 0.5 the thin header number anti-aliased away over light
      // backgrounds on some days, producing false QA flags. QA must match
      // deliverable fidelity.
      scale: 1,
      overwrite: true,
    });
    ok++;
  } catch (e) {
    failures.push({ day: d.day, error: e && e.message ? e.message : String(e) });
  }
}
console.log(`Stills: ${ok}/${targets.length} ok, ${failures.length} failed.`);
if (failures.length) {
  console.error(JSON.stringify(failures, null, 2));
  process.exit(1);
}
