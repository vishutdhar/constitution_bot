#!/usr/bin/env python3
"""Generate ElevenLabs voice audio for every Constitution post.

Reads constitution_posts.json, calls ElevenLabs TTS for each post.text,
writes <out-dir>/day_NN.mp3. Idempotent — skips files that already exist.
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.environ.get("ELEVENLABS_API_KEY")
MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

if not API_KEY:
    sys.exit("ELEVENLABS_API_KEY not set in .env")

only_day = None
voice_override = None
out_dir_name = "audio_male"
for arg in sys.argv[1:]:
    if arg.startswith("--day="):
        only_day = int(arg.split("=", 1)[1])
    elif arg.startswith("--voice="):
        voice_override = arg.split("=", 1)[1]
    elif arg.startswith("--out-dir="):
        out_dir_name = arg.split("=", 1)[1]

VOICE_ID = voice_override or os.environ.get("ELEVENLABS_VOICE_ID")
if not VOICE_ID:
    sys.exit("voice id not set (pass --voice=<id> or ELEVENLABS_VOICE_ID in .env)")

POSTS_PATH = ROOT / "constitution_posts.json"
AUDIO_DIR = ROOT / out_dir_name
AUDIO_DIR.mkdir(exist_ok=True)

client = ElevenLabs(api_key=API_KEY)
posts = json.loads(POSTS_PATH.read_text())

for post in posts:
    day = post["day"]
    if only_day is not None and day != only_day:
        continue

    out = AUDIO_DIR / f"day_{day:02d}.mp3"
    if out.exists():
        print(f"day {day:02d}: skip (exists)")
        continue

    text = post["text"]
    print(f"day {day:02d}: generating ({len(text)} chars)...")

    audio = client.text_to_speech.convert(
        voice_id=VOICE_ID,
        model_id=MODEL_ID,
        text=text,
        output_format="mp3_44100_128",
    )
    with open(out, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    print(f"day {day:02d}: wrote {out.name}")

print("done.")
