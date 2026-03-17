#!/usr/bin/env python3
"""
Daily Constitution Bot
Posts one section of the U.S. Constitution per day to X (Twitter).
Designed to be run once daily via cron, AWS Lambda, GitHub Actions, etc.

Usage:
    python bot.py              # Post today's section
    python bot.py --preview    # Preview without posting
    python bot.py --dry-run    # Alias for --preview
    python bot.py --day 46     # Post (or preview) a specific day
    python bot.py --reset      # Reset progress to day 1
    python bot.py --validate   # Verify all 77 days have valid image mappings
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from platforms.x_twitter import XTwitterPlatform, weighted_len

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
POSTS_FILE = BASE_DIR / "constitution_posts.json"
STATE_FILE = BASE_DIR / "state.json"
LOG_FILE = BASE_DIR / "post_log.json"
IMAGE_MAPPING_FILE = BASE_DIR / "image_mapping.json"
IMAGES_DIR = BASE_DIR / "images"

# ---------------------------------------------------------------------------
# Fallback hashtags — used only if an entry has no "hashtags" field
# ---------------------------------------------------------------------------
HASHTAGS = "#USConstitution #Constitution"

# ---------------------------------------------------------------------------
# Reply character limit — controls when body text gets split across replies.
# Free tier: 280 | Premium: 4000 (one clean reply, no splits)
# ---------------------------------------------------------------------------
REPLY_CHAR_LIMIT = 4000


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------
def load_state() -> dict:
    """Load current bot state (which day we're on)."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"current_day": 1}


def save_state(state: dict) -> None:
    """Persist bot state."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def reset_state() -> None:
    """Reset progress to day 1."""
    save_state({"current_day": 1})
    print("🔄 State reset to day 1.")


# ---------------------------------------------------------------------------
# Post loading & formatting
# ---------------------------------------------------------------------------
def load_posts() -> list[dict]:
    """Load the constitution posts from JSON."""
    with open(POSTS_FILE) as f:
        return json.load(f)


def format_post(entry: dict, total_days: int) -> str:
    """
    Format a constitution entry into a tweet (text-only fallback format).

    Template:
        📜 Day X/77 — {Section}

        {Text}

        #USConstitution #SectionSpecific #Community
    """
    header = f"📜 Day {entry['day']}/{total_days} — {entry['section']}"
    body = entry["text"]
    hashtags = entry.get("hashtags", HASHTAGS)
    tweet = f"{header}\n\n{body}\n\n{hashtags}"
    return tweet


def format_image_text(entry: dict) -> str:
    """
    Format the caption for the image tweet (tweet 1).
    Clean and eye-catching — no "Day X/77" counter.

    Template:
        📜 {Section}

        #USConstitution #SectionSpecific #Community
    """
    hashtags = entry.get("hashtags", HASHTAGS)
    return f"📜 {entry['section']}\n\n{hashtags}"


# ---------------------------------------------------------------------------
# Image mapping
# ---------------------------------------------------------------------------
def load_image_mapping() -> dict:
    """Load the day-to-image filename mapping from JSON."""
    if not IMAGE_MAPPING_FILE.exists():
        return {}
    with open(IMAGE_MAPPING_FILE) as f:
        return json.load(f)


def resolve_image_path(day_num: int, mapping: dict) -> str | None:
    """
    Look up the image for a given day and verify it exists on disk.

    Returns:
        Absolute path string if found, None otherwise.
    """
    filename = mapping.get(str(day_num))
    if not filename:
        return None

    image_path = IMAGES_DIR / filename
    if not image_path.exists():
        print(f"⚠️  Image file not found: {image_path}")
        return None

    return str(image_path)


def validate_all_mappings(posts: list[dict], mapping: dict) -> bool:
    """
    Verify every day in constitution_posts.json has a valid image mapping
    and the referenced image file exists on disk.

    Returns True if all valid, False if any errors found.
    """
    errors = []
    total = len(posts)

    print(f"\n{'='*60}")
    print(f"  Validating image mappings for {total} days")
    print(f"{'='*60}\n")

    for entry in posts:
        day = entry["day"]
        day_str = str(day)

        if day_str not in mapping:
            errors.append(f"  Day {day} ({entry['section']}): NO MAPPING")
            continue

        filename = mapping[day_str]
        image_path = IMAGES_DIR / filename

        if not image_path.exists():
            errors.append(f"  Day {day} ({entry['section']}): FILE MISSING → {filename}")

    if errors:
        print(f"❌ Found {len(errors)} error(s):\n")
        for err in errors:
            print(err)
        print()
        return False

    # Count unique images used
    unique_images = set(mapping.values())
    print(f"✅ All {total} days have valid image mappings")
    print(f"   {len(unique_images)} unique images used across {total} days\n")
    return True


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log_post(entry: dict, result: dict, platform: str) -> None:
    """Append a record to the post log."""
    log = []
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            log = json.load(f)

    log.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "day": entry["day"],
            "section": entry["section"],
            "platform": platform,
            "success": result["success"],
            "url": result.get("url"),
            "error": result.get("error"),
        }
    )

    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


# ---------------------------------------------------------------------------
# Platform initialization
# ---------------------------------------------------------------------------
def init_platforms() -> list:
    """
    Initialize all enabled platforms from environment variables.
    Add new platforms here as you build them.
    """
    platforms = []

    # --- X (Twitter) ---
    x_keys = {
        "api_key": os.getenv("X_API_KEY"),
        "api_secret": os.getenv("X_API_SECRET"),
        "access_token": os.getenv("X_ACCESS_TOKEN"),
        "access_token_secret": os.getenv("X_ACCESS_TOKEN_SECRET"),
        "handle": os.getenv("X_HANDLE", "USC1787"),
    }

    if all(v for k, v in x_keys.items() if k != "handle"):
        x = XTwitterPlatform(**x_keys)
        x.authenticate()
        platforms.append(x)
    else:
        missing = [k for k, v in x_keys.items() if not v]
        print(f"⚠️  X (Twitter) disabled — missing env vars: {', '.join(missing)}")

    # --- Future platforms ---
    # To add a new platform:
    # 1. Create platforms/bluesky.py (inherit from BasePlatform)
    # 2. Add initialization here, gated by env vars
    # Example:
    # if os.getenv("BLUESKY_HANDLE") and os.getenv("BLUESKY_APP_PASSWORD"):
    #     from platforms.bluesky import BlueskyPlatform
    #     bsky = BlueskyPlatform(
    #         handle=os.getenv("BLUESKY_HANDLE"),
    #         app_password=os.getenv("BLUESKY_APP_PASSWORD"),
    #     )
    #     bsky.authenticate()
    #     platforms.append(bsky)

    return platforms


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Daily Constitution Bot")
    parser.add_argument("--preview", "--dry-run", action="store_true", help="Preview the post without publishing")
    parser.add_argument("--day", type=int, help="Post a specific day number instead of the next in sequence")
    parser.add_argument("--reset", action="store_true", help="Reset progress to day 1")
    parser.add_argument("--validate", action="store_true", help="Verify all 77 days have valid image mappings")
    args = parser.parse_args()

    if args.reset:
        reset_state()
        return

    # Load data
    posts = load_posts()
    total_days = len(posts)
    state = load_state()
    image_mapping = load_image_mapping()

    # Validate mode — check all mappings and exit
    if args.validate:
        valid = validate_all_mappings(posts, image_mapping)
        sys.exit(0 if valid else 1)

    # Determine which day to post
    day_num = args.day if args.day else state["current_day"]

    if day_num > total_days:
        day_num = 1
        state["current_day"] = 1
        print(f"🔄 Completed all {total_days} days. Looping back to Day 1.")

    # Find the post entry
    entry = next((p for p in posts if p["day"] == day_num), None)
    if not entry:
        print(f"❌ No post found for day {day_num}")
        sys.exit(1)

    # Resolve image for this day
    image_path = resolve_image_path(day_num, image_mapping)

    # Build text components
    fallback_tweet = format_post(entry, total_days)  # Full text-only format
    image_text = format_image_text(entry)             # Image tweet caption
    body_text = entry["text"]                         # Constitutional text for replies

    # Display preview
    print(f"\n{'='*60}")
    print(f"  Day {day_num}/{total_days} — {entry['section']}")
    print(f"{'='*60}")

    if image_path:
        print(f"\n  🖼️  IMAGE TWEET (Tweet 1):")
        print(f"  {'-'*56}")
        print(f"  {image_text}")
        print(f"  + image: {Path(image_path).name}")
        print(f"  ({weighted_len(image_text)} chars)")
        print(f"\n  💬 REPLY THREAD (Tweet 2+):")
        print(f"  {'-'*56}")
        print(f"  {body_text}")
        print(f"  ({weighted_len(body_text)} chars)")
    else:
        print(f"\n  📝 TEXT-ONLY (no image found):")
        print(f"  {'-'*56}")
        print(f"  {fallback_tweet}")
        print(f"  ({weighted_len(fallback_tweet)} chars)")

    print(f"\n{'='*60}\n")

    # Preview mode — stop here
    if args.preview:
        if image_path:
            print(f"✅ Image post ready — {Path(image_path).name}")
            if weighted_len(body_text) > REPLY_CHAR_LIMIT:
                from platforms.x_twitter import split_text_for_replies
                chunks = split_text_for_replies(body_text, max_len=REPLY_CHAR_LIMIT)
                print(f"   Reply thread will be {len(chunks)} tweet(s)")
                for i, chunk in enumerate(chunks):
                    print(f"\n   Reply {i+1} ({weighted_len(chunk)} chars):")
                    print(f"   {chunk}")
        else:
            print("⚠️  No image available — will post text-only")
            if weighted_len(fallback_tweet) > REPLY_CHAR_LIMIT:
                from platforms.x_twitter import split_into_thread
                chunks = split_into_thread(fallback_tweet, max_len=REPLY_CHAR_LIMIT)
                print(f"   Thread will be {len(chunks)} tweet(s)")
        return

    # Initialize platforms and post
    platforms = init_platforms()

    if not platforms:
        print("❌ No platforms configured. Set environment variables and try again.")
        print("   Required for X: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET")
        sys.exit(1)

    all_success = True
    for platform in platforms:
        if not platform.validate_length(fallback_tweet):
            print(f"⚠️  Post too long for {platform.name} ({weighted_len(fallback_tweet)} > {platform.max_length})")
            all_success = False
            continue

        result = platform.post(
            fallback_tweet,
            image_path=image_path,
            image_text=image_text,
            body_text=body_text,
            reply_char_limit=REPLY_CHAR_LIMIT,
        )
        log_post(entry, result, platform.name)

        if not result["success"]:
            all_success = False

    # Advance state only if we're posting the current day (not a manual --day override)
    if all_success and not args.day:
        state["current_day"] = day_num + 1
        save_state(state)
        print(f"\n📅 Next scheduled: Day {day_num + 1}")

    if not all_success:
        sys.exit(1)


if __name__ == "__main__":
    main()
