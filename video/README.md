# Constitution Bot — Video Generator

Generates one vertical (1080×1920) social video per Constitution day (1–77) with
[Remotion](https://www.remotion.dev). Each video reuses the project's existing
per-day assets:

- **Image** — `../images_v2/day_NN_*.png` (the parchment card that already shows
  that day's text in calligraphy; it is the hero of the frame)
- **Audio** — `../audio_male/day_NN.mp3` (the narrated text; the video length is
  matched to it)
- **Text / section / hashtags** — `../constitution_posts.json`

The motion (slow push-in, light sweep, warm lamp flicker, fade in/out, a gold
progress bar) is deliberately **alignment-free** so nothing can drift against the
text baked into the artwork. On top we add only chrome: a header
(`THE U.S. CONSTITUTION` / `Day N of 77`) and a footer (`@USC1787` + that day's
hashtags).

## Setup

```bash
cd video
npm install
./scripts/setup-assets.sh        # recreate public/ symlinks (gitignored)
python3 scripts/gen-days.py      # (re)build data/days.json — needs macOS `afinfo`
```

`public/images_v2` and `public/audio_male` are symlinks into the parent project
so Remotion's `staticFile()` can resolve the assets without duplicating ~260MB.
They are gitignored; `setup-assets.sh` recreates them.

## Preview

```bash
npm run studio          # opens Remotion Studio (defaults to Day 1)
```

## Render

```bash
npm run render-all              # render all 77 -> videos/day_NN.mp4
node scripts/render-all.mjs 1 5 9   # render only specific day numbers
```

Output goes to `videos/` (gitignored). Renders are H.264 + AAC at CRF 23
(~10–25 MB per video — small enough for social upload).

## Data: `data/days.json`

The render reads this manifest, one entry per day:

```json
{
  "day": 1,
  "section": "Preamble",
  "hashtags": "#USConstitution #WeThePeople #Civics",
  "image": "images_v2/day_01_preamble.png",
  "audio": "audio_male/day_01.mp3",
  "audioSeconds": 22.988,
  "durationInFrames": 705
}
```

`durationInFrames = ceil(audioSeconds * 30) + 15` (a ~0.5s tail for the fade-out).
Regenerate with `python3 scripts/gen-days.py`.

## Notes

- **Pre-render locally, not in CI.** The daily posting bot runs on GitHub Actions;
  installing Remotion + headless Chrome there is avoidable. Render the 77 videos
  here and let the bot upload the pre-rendered `videos/day_NN.mp4` for the day.
- `videos/`, `out/`, `node_modules/`, and the `public/` symlinks are gitignored.
