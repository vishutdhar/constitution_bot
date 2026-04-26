#!/usr/bin/env python3
"""Generate Constitution parchment images via OpenAI gpt-image-2.

Parses chatgpt_image_prompts_v2.txt, calls gpt-image-2 for each section,
writes <out-dir>/<filename>. Idempotent — skips files that already exist.

Usage:
    python3 scripts/generate_images.py --day=1        # just day 1 (test)
    python3 scripts/generate_images.py                # all 77
    python3 scripts/generate_images.py --quality=medium
"""
import base64
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    sys.exit("OPENAI_API_KEY not set in .env")

MODEL = "gpt-image-2"
SIZE = "2160x3840"  # 4K portrait (max resolution; experimental per OpenAI docs)
QUALITY = "high"
OUT_DIR_NAME = "images_v2"
PROMPTS_PATH = ROOT / "chatgpt_image_prompts_v2.txt"

only_day = None
for arg in sys.argv[1:]:
    if arg.startswith("--day="):
        only_day = int(arg.split("=", 1)[1])
    elif arg.startswith("--quality="):
        QUALITY = arg.split("=", 1)[1]
    elif arg.startswith("--out-dir="):
        OUT_DIR_NAME = arg.split("=", 1)[1]

OUT_DIR = ROOT / OUT_DIR_NAME
OUT_DIR.mkdir(exist_ok=True)

SECTION_RE = re.compile(
    r"SECTION\s+(\d+)\s+of\s+77\s*\n"
    r"TITLE:\s*(.+?)\n"
    r"COVERS:\s*Day\s+(\d+)\s*\n"
    r"FILENAME:\s*(\S+)\s*\n"
    r"[-—\s]+\n"
    r"PROMPT:\s*\n(.*?)(?=\n———|\Z)",
    re.DOTALL,
)


def parse_prompts(text: str):
    for m in SECTION_RE.finditer(text):
        yield {
            "section": int(m.group(1)),
            "title": m.group(2).strip(),
            "day": int(m.group(3)),
            "filename": m.group(4).strip(),
            "prompt": m.group(5).strip(),
        }


def main() -> None:
    client = OpenAI(api_key=API_KEY)
    sections = list(parse_prompts(PROMPTS_PATH.read_text()))
    if len(sections) != 77:
        print(f"warning: parsed {len(sections)} sections (expected 77)", file=sys.stderr)

    for s in sections:
        if only_day is not None and s["day"] != only_day:
            continue

        out = OUT_DIR / s["filename"]
        if out.exists():
            print(f"day {s['day']:02d}: skip (exists) {out.name}")
            continue

        print(f"day {s['day']:02d}: generating {out.name} ({QUALITY}, {SIZE})...")
        resp = client.images.generate(
            model=MODEL,
            prompt=s["prompt"],
            size=SIZE,
            quality=QUALITY,
            n=1,
        )
        img_b64 = resp.data[0].b64_json
        out.write_bytes(base64.b64decode(img_b64))
        print(f"day {s['day']:02d}: wrote {out.name} ({out.stat().st_size // 1024} KB)")

    print("done.")


if __name__ == "__main__":
    main()
