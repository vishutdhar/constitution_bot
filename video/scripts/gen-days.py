#!/usr/bin/env python3
"""
Generate video/data/days.json — the per-day manifest the Remotion renderer reads.

For each of the 77 days it records:
  - day, section, hashtags, text   (from ../constitution_posts.json)
  - image  -> images_v2/day_NN_*.png  (the unique per-day card; matched by prefix)
  - audio  -> audio_male/day_NN.mp3
  - audioSeconds      (measured with macOS `afinfo`)
  - durationInFrames  = ceil(audioSeconds * FPS) + TAIL

Re-run whenever the source posts/images/audio change:
    python3 scripts/gen-days.py
"""
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

FPS = 30
TAIL = 15  # ~0.5s after narration ends, covered by the composition's fade-out

VIDEO_DIR = Path(__file__).resolve().parents[1]
BOT_ROOT = VIDEO_DIR.parent
IMG_DIR = BOT_ROOT / "images_v2"
AUD_DIR = BOT_ROOT / "audio_male"
OUT = VIDEO_DIR / "data" / "days.json"


def audio_seconds(path: Path) -> float:
    out = subprocess.run(["afinfo", str(path)], capture_output=True, text=True).stdout
    m = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", out)
    if not m:
        raise RuntimeError(f"could not read duration for {path}")
    return float(m.group(1))


def main() -> int:
    posts = json.loads((BOT_ROOT / "constitution_posts.json").read_text())

    img_by_day: dict[int, str] = {}
    for fn in os.listdir(IMG_DIR):
        m = re.match(r"day_(\d{2})_", fn)
        if m:
            img_by_day[int(m.group(1))] = fn

    days = []
    errors = []
    for p in posts:
        d = p["day"]
        img = img_by_day.get(d)
        audio_rel = f"day_{d:02d}.mp3"
        if img is None:
            errors.append(f"day {d}: no images_v2 file")
            continue
        if not (AUD_DIR / audio_rel).exists():
            errors.append(f"day {d}: missing {audio_rel}")
            continue
        secs = audio_seconds(AUD_DIR / audio_rel)
        days.append(
            {
                "day": d,
                "section": p["section"],
                "hashtags": p["hashtags"],
                "text": p["text"],
                "image": f"images_v2/{img}",
                "audio": f"audio_male/{audio_rel}",
                "audioSeconds": round(secs, 3),
                "durationInFrames": math.ceil(secs * FPS) + TAIL,
            }
        )

    days.sort(key=lambda x: x["day"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(days, indent=2, ensure_ascii=False))
    print(f"wrote {len(days)} days -> {OUT}")

    if errors:
        print("ERRORS:\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
