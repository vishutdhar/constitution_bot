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
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from platforms.x_twitter import XTwitterPlatform

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
POSTS_FILE = BASE_DIR / "constitution_posts.json"
STATE_FILE = BASE_DIR / "state.json"
LOG_FILE = BASE_DIR / "post_log.json"

# ---------------------------------------------------------------------------
# Hashtags appended to every post (customize as you like)
# ---------------------------------------------------------------------------
HASHTAGS = "#Constitution #WeThePeople"


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
    Format a constitution entry into a tweet.

    Template:
        📜 Day X/77 — {Section}

        {Text}

        #Constitution #WeThePeople
    """
    header = f"📜 Day {entry['day']}/{total_days} — {entry['section']}"
    body = entry["text"]
    tweet = f"{header}\n\n{body}\n\n{HASHTAGS}"
    return tweet


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
    args = parser.parse_args()

    if args.reset:
        reset_state()
        return

    # Load data
    posts = load_posts()
    total_days = len(posts)
    state = load_state()

    # Determine which day to post
    day_num = args.day if args.day else state["current_day"]

    if day_num > total_days:
        print(f"🎉 All {total_days} days have been posted! The full Constitution has been shared.")
        print("   Use --reset to start over, or --day N to repost a specific day.")
        return

    # Find the post entry
    entry = next((p for p in posts if p["day"] == day_num), None)
    if not entry:
        print(f"❌ No post found for day {day_num}")
        sys.exit(1)

    # Format the tweet
    tweet = format_post(entry, total_days)

    print(f"\n{'='*60}")
    print(f"  Day {day_num}/{total_days} — {entry['section']}")
    print(f"{'='*60}")
    print(tweet)
    print(f"{'='*60}")
    print(f"  Characters: {len(tweet)}")
    print(f"{'='*60}\n")

    # Preview mode — stop here
    if args.preview:
        if len(tweet) > 280:
            print(f"⚠️  Warning: Tweet is {len(tweet)} chars (limit: 280)")
        else:
            print("✅ Tweet fits within 280 character limit.")
        return

    # Initialize platforms and post
    platforms = init_platforms()

    if not platforms:
        print("❌ No platforms configured. Set environment variables and try again.")
        print("   Required for X: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET")
        sys.exit(1)

    all_success = True
    for platform in platforms:
        if not platform.validate_length(tweet):
            print(f"⚠️  Post too long for {platform.name} ({len(tweet)} > {platform.max_length})")
            all_success = False
            continue

        result = platform.post(tweet)
        log_post(entry, result, platform.name)

        if not result["success"]:
            all_success = False

    # Advance state only if we're posting the current day (not a manual --day override)
    if all_success and not args.day:
        state["current_day"] = day_num + 1
        save_state(state)
        print(f"\n📅 Next scheduled: Day {day_num + 1}")


if __name__ == "__main__":
    main()
