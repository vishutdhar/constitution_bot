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
VIDEOS_DIR = BASE_DIR / "video" / "videos"
# Durable per-UTC-day claim files (committed+pushed BEFORE posting). One file per
# date so concurrent days never conflict and a same-date claim conflicts cleanly.
CLAIMS_DIR = BASE_DIR / "claims"
# Version-2 per-day parchment images (used by the video + the 3-slot image post).
IMAGESV2_DIR = BASE_DIR / "images_v2"

# 3-slot strategy: one section/day posted three ways. Each slot has its own
# durable claim (key "<date>__<slot>"); the day is pinned once per date (key
# "<date>__pin"). See docs/IDEMPOTENCY.md. Gated by the daily_3slot workflow.
SLOT_FORMATS = {"morning": "text", "afternoon": "image", "night": "video"}
# Days whose video narration is materially wrong (old text baked before the
# verbatim correction); at night these post the image instead of the video so we
# never broadcast clearly-wrong audio. See project notes / docs/IDEMPOTENCY.md.
WORST5_NIGHT_DAYS = {10, 23, 58, 69, 75}

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


def already_posted_today() -> bool:
    """
    Return True if any successful post is already logged for today's UTC date.

    Used to make the cron idempotent: with multiple daily cron windows, only
    the first successful run posts; later runs exit cleanly.
    """
    if not LOG_FILE.exists():
        return False
    try:
        with open(LOG_FILE) as f:
            log = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False

    today_utc = datetime.now(timezone.utc).date()
    for entry in log:
        if not entry.get("success"):
            continue
        ts = entry.get("timestamp")
        if not ts:
            continue
        try:
            entry_date = datetime.fromisoformat(ts).date()
        except (TypeError, ValueError):
            continue
        if entry_date == today_utc:
            return True
    return False


# ---------------------------------------------------------------------------
# Durable claim (idempotency fence) — see docs/IDEMPOTENCY.md
#
# The claim is written and pushed to origin/main BEFORE the irreversible X post.
# bot.py only reads/writes the claim files; ALL git lives in the workflow. These
# helpers are pure and exception-tolerant (mirror already_posted_today).
# ---------------------------------------------------------------------------
def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def claim_path(date_str: str) -> Path:
    return CLAIMS_DIR / f"{date_str}.json"


def read_claim(date_str: str) -> dict | None:
    """Return the claim record for a date, or None if missing/corrupt."""
    p = claim_path(date_str)
    if not p.exists():
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def claim_status(date_str: str) -> str | None:
    """
    Status of a date's claim: claimed | posted | posted_partial | posted_unknown |
    failed | unknown | None.

    Distinguishes a MISSING claim (None, re-postable) from a PRESENT-but-corrupt
    one ('unknown', treated as consumed) so a damaged claim never re-opens a day.
    """
    p = claim_path(date_str)
    if not p.exists():
        return None
    try:
        with open(p) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return "unknown"  # present but unreadable -> fail-safe to consumed
    status = data.get("status")
    return status if status else "unknown"


def should_skip_for_claim(status: str | None) -> bool:
    """
    True if a date is already consumed and must NOT be posted again.

    Consumed: claimed (intent durable; we may have posted), posted, posted_partial,
    posted_unknown (ambiguous lead, may be live), and unknown (corrupt claim — fail
    safe). Only None (no claim) and 'failed' (lead provably never landed) are
    re-postable. No-duplicate beats no-miss.
    """
    return status in ("claimed", "posted", "posted_partial", "posted_unknown", "unknown")


def finalize_status_for_result(result: dict) -> str:
    """
    Map a platform post() result to a claim status.

    Coupled to x_twitter's result contract:
      - uncertain (2xx lead, no id, may be live) -> posted_unknown (NOT retryable)
      - partial (lead live, thread incomplete)   -> posted_partial
      - success                                  -> posted
      - else (non-2xx lead, nothing landed)      -> failed (retryable)
    """
    if result.get("uncertain"):
        return "posted_unknown"
    if result.get("partial"):
        return "posted_partial"
    if result.get("success"):
        return "posted"
    return "failed"


def write_claim(date_str: str, day_num: int, status: str) -> None:
    """Write/overwrite a claim record (caller commits+pushes it)."""
    CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
    record = read_claim(date_str) or {}
    record.update(
        {
            "date": date_str,
            "day": day_num,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": os.getenv("GITHUB_RUN_ID"),
        }
    )
    record.setdefault("claimed_at", record["updated_at"])
    with open(claim_path(date_str), "w") as f:
        json.dump(record, f, indent=2)


def run_claim(date_str: str) -> int:
    """
    Write a durable 'claimed' record for date_str if the day is still free. Posts
    nothing. The workflow commits+pushes the claim to origin/main BEFORE the post
    step, so any later crash cannot cause a re-post. If today is already
    claimed/posted, writes nothing (so the workflow stages no change → skips).
    """
    if already_posted_today() or should_skip_for_claim(claim_status(date_str)):
        print(f"⏭️  {date_str} already claimed/posted — nothing to claim.")
        return 0

    posts = load_posts()
    total_days = len(posts)
    state = load_state()
    day_num = state["current_day"]
    if day_num > total_days:
        day_num = 1
    if not any(p["day"] == day_num for p in posts):
        print(f"❌ No post found for day {day_num} — not claiming.")
        return 1

    write_claim(date_str, day_num, "claimed")
    print(f"📌 Claimed day {day_num} for {date_str}.")
    return 0


def run_finalize(date_str: str) -> int:
    """
    Record date_str's post outcome into its claim file. Runs with if: always() so
    it executes even if the post step crashed. Pure file edit; never raises.
    """
    claim = read_claim(date_str)
    if claim is None:
        print(f"ℹ️  No claim for {date_str} to finalize.")
        return 0

    # Default to 'posted_unknown' (consumed, NOT retryable): we won the claim and
    # the post step ran, but left no outcome record (crash / log-write failure),
    # so we cannot prove nothing posted — never re-post. Only an explicit logged
    # result downgrades this (a non-2xx lead failure -> 'failed' -> retryable).
    status = "posted_unknown"
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE) as f:
                log = json.load(f)
        except (json.JSONDecodeError, OSError):
            log = []
        todays = []
        for e in log:
            ts = e.get("timestamp")
            try:
                if ts and datetime.fromisoformat(ts).date().isoformat() == date_str:
                    todays.append(e)
            except (TypeError, ValueError):
                continue
        if todays:
            status = finalize_status_for_result(todays[-1])

    try:
        write_claim(date_str, claim.get("day", 0), status)
        print(f"🏁 Finalized {date_str}: {status}")
    except OSError as e:
        print(f"⚠️  Could not finalize claim for {date_str}: {e}")
    return 0


# ---------------------------------------------------------------------------
# 3-slot posting (morning text / afternoon image / night video)
#
# One section per day, posted three ways. Each slot has its own durable claim
# (key "<date>__<slot>"); the day is pinned once per date (key "<date>__pin")
# and state advances exactly once per date. The corrected verbatim text is
# carried in the tweet copy in EVERY slot (the free accuracy lever); the image
# and video assets are used as-is.
# ---------------------------------------------------------------------------
def resolve_imagev2_path(day_num: int) -> str | None:
    """The version-2 per-day parchment image (images_v2/day_NN_*.png)."""
    import glob

    matches = sorted(glob.glob(str(IMAGESV2_DIR / f"day_{day_num:02d}_*.png")))
    return matches[0] if matches else None


def _slot_key(date_str: str, slot: str) -> str:
    return f"{date_str}__{slot}"


def pin_day(date_str: str) -> int:
    """
    Pin the section day for a date (written once; later slots read it). Does NOT
    advance state — state advances only after a slot actually posts (see
    run_post_slot), so a day on which every slot fails is retried the next date
    rather than silently skipped. Returns the pinned day.
    """
    pin = read_claim(_slot_key(date_str, "pin"))
    if pin and isinstance(pin.get("day"), int):
        return pin["day"]
    posts = load_posts()
    total = len(posts)
    state = load_state()
    day = state["current_day"]
    if day > total:
        day = 1
    write_claim(_slot_key(date_str, "pin"), day, "pinned")
    return day


def run_claim_slot(date_str: str, slot: str) -> int:
    """Claim one slot for a date (writes nothing if the slot is already consumed)."""
    key = _slot_key(date_str, slot)
    if should_skip_for_claim(claim_status(key)):
        print(f"⏭️  {date_str} {slot} already claimed/posted — nothing to claim.")
        return 0
    day = pin_day(date_str)
    posts = load_posts()
    if not any(p["day"] == day for p in posts):
        print(f"❌ No post found for day {day} — not claiming {slot}.")
        return 1
    write_claim(key, day, "claimed")
    print(f"📌 Claimed {slot} (day {day}) for {date_str}.")
    return 0


def run_finalize_slot(date_str: str, slot: str) -> int:
    """Record a slot's outcome into its claim. Runs with if: always(); never raises."""
    key = _slot_key(date_str, slot)
    claim = read_claim(key)
    if claim is None:
        print(f"ℹ️  No {slot} claim for {date_str} to finalize.")
        return 0
    status = "posted_unknown"
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE) as f:
                log = json.load(f)
        except (json.JSONDecodeError, OSError):
            log = []
        todays = []
        for e in log:
            if e.get("slot") != slot:
                continue
            ts = e.get("timestamp")
            try:
                if ts and datetime.fromisoformat(ts).date().isoformat() == date_str:
                    todays.append(e)
            except (TypeError, ValueError):
                continue
        if todays:
            status = finalize_status_for_result(todays[-1])
    try:
        write_claim(key, claim.get("day", 0), status)
        print(f"🏁 Finalized {date_str} {slot}: {status}")
    except OSError as e:
        print(f"⚠️  Could not finalize {slot} claim for {date_str}: {e}")
    return 0


def compose_slot(entry: dict, day: int, total_days: int, slot: str) -> dict:
    """
    Build the post for a slot. The corrected verbatim text is carried in the
    tweet copy in every slot; the image/video assets are used as-is.
    """
    section = entry["section"]
    full = entry["text"]
    tags = entry.get("hashtags", HASHTAGS)
    fmt = SLOT_FORMATS.get(slot, "text")

    # Night worst-5: the video narration is materially wrong -> post the image.
    if fmt == "video" and day in WORST5_NIGHT_DAYS:
        fmt = "image"

    media_path = None
    is_video = False
    if fmt == "video":
        media_path = resolve_video_path(day)
        if media_path:
            is_video = True
        else:
            fmt = "image"  # graceful fallback when the video is unavailable
    if fmt == "image":
        media_path = resolve_imagev2_path(day) or resolve_image_path(day, load_image_mapping())

    if media_path is None:
        # Text slot, or no asset available: the full clause IS the post.
        lead = f"📜 Day {day}/{total_days}: {section}\n\nRead today's clause:\n\n{full}\n\n{tags}"
        return {"slot": slot, "kind": "text", "media_path": None, "is_video": False,
                "lead_text": lead, "image_text": None, "body_text": None}

    hook = {"morning": "Read", "afternoon": "See", "night": "Hear"}.get(slot, "Read")
    caption = f"📜 {section}\n\nDay {day}/{total_days}. {hook} today's clause.\n\n{tags}"
    return {"slot": slot, "kind": "video" if is_video else "image", "media_path": media_path,
            "is_video": is_video, "lead_text": format_post(entry, total_days),
            "image_text": caption, "body_text": full}


def _post_composed(comp: dict, entry: dict) -> int:
    """Post a composed slot to all platforms; log per slot. Returns 0/1."""
    platforms = init_platforms()
    if not platforms:
        print("❌ No platforms configured. Set X_* env vars and try again.")
        return 1
    all_success = True
    for platform in platforms:
        # Only the single-tweet media caption must fit the per-tweet limit. The
        # text-only slot has no preflight gate: post() threads it (split_into_thread
        # at reply_char_limit), so a long verbatim clause is never rejected here.
        if comp["media_path"] and not platform.validate_length(comp["image_text"]):
            print(f"⚠️  Caption too long for {platform.name} ({weighted_len(comp['image_text'])} > {platform.max_length})")
            all_success = False
            continue
        kwargs = {"reply_char_limit": REPLY_CHAR_LIMIT}
        if comp["media_path"]:
            if comp["is_video"]:
                kwargs["video_path"] = comp["media_path"]
            else:
                kwargs["image_path"] = comp["media_path"]
            kwargs["image_text"] = comp["image_text"]
            kwargs["body_text"] = comp["body_text"]
        result = platform.post(comp["lead_text"], **kwargs)
        log_post(entry, result, platform.name, slot=comp["slot"])
        if not result["success"]:
            all_success = False
    return 0 if all_success else 1


def run_post_slot(date_str: str, slot: str) -> int:
    """Post one slot. Fail-closed: requires a live 'claimed' record for the slot."""
    key = _slot_key(date_str, slot)
    if claim_status(key) != "claimed":
        print(f"❌ No live {slot} claim for {date_str} — refusing to post.")
        return 1
    day = read_claim(key)["day"]
    posts = load_posts()
    total = len(posts)
    entry = next((p for p in posts if p["day"] == day), None)
    if not entry:
        print(f"❌ No post found for day {day}")
        return 1
    rc = _post_composed(compose_slot(entry, day, total, slot), entry)
    if rc == 0:
        # Advance the section ONCE per date, only after a slot actually posts, so a
        # day on which every slot failed is retried next date, not lost.
        state = load_state()
        if state.get("current_day") == day:
            state["current_day"] = (day % total) + 1
            save_state(state)
            print(f"📅 Advanced to day {(day % total) + 1}")
    return rc


def preview_slot(slot: str, day_override: int | None = None) -> int:
    """Preview a slot for the next (or a specific) day. Posts nothing."""
    posts = load_posts()
    total = len(posts)
    state = load_state()
    day = day_override or state["current_day"]
    if day > total:
        day = 1
    entry = next((p for p in posts if p["day"] == day), None)
    if not entry:
        print(f"❌ No post found for day {day}")
        return 1
    comp = compose_slot(entry, day, total, slot)
    print(f"\n{'='*60}\n  {slot.upper()} — Day {day}/{total} — {entry['section']}  [{comp['kind']}]\n{'='*60}")
    if comp["media_path"]:
        print(f"  media: {Path(comp['media_path']).name}")
        print(f"\n  CAPTION (tweet 1):\n  {comp['image_text']}")
        print(f"\n  REPLY (full verbatim text):\n  {comp['body_text']}")
    else:
        print(f"\n  TEXT POST:\n  {comp['lead_text']}")
    print(f"{'='*60}\n")
    return 0


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
    header = f"📜 Day {entry['day']}/{total_days}: {entry['section']}"
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


def resolve_video_path(day_num: int) -> str | None:
    """
    Locate the pre-rendered Remotion video for a given day, if present.

    Videos live in video/videos/day_NN.mp4 (generated by the Remotion project
    under video/). They are gitignored, so this returns None when they have not
    been rendered/made available — letting the caller fall back to the image.

    Returns:
        Absolute path string if the file exists, None otherwise.
    """
    video_path = VIDEOS_DIR / f"day_{day_num:02d}.mp4"
    if not video_path.exists():
        # Absence is an expected, documented fallback (videos are gitignored and
        # may not be fetched in CI), so this is informational, not a warning.
        print(f"ℹ️  No video for day {day_num} ({video_path.name}); using image")
        return None

    return str(video_path)


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
def log_post(entry: dict, result: dict, platform: str, slot: str | None = None) -> None:
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
            "slot": slot,
            "success": result["success"],
            "partial": result.get("partial", False),
            "uncertain": result.get("uncertain", False),
            "media_kind": result.get("media_kind"),
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
    parser.add_argument("--video", action="store_true", help="Attach the pre-rendered video for the day (also enabled by POST_VIDEO env)")
    parser.add_argument("--claim", action="store_true", help="Durably claim the date (write claims/<date>.json) BEFORE posting; posts nothing")
    parser.add_argument("--post-claimed", action="store_true", help="Post the day pinned by the claim file for --date")
    parser.add_argument("--finalize", action="store_true", help="Record the post outcome into the claim file for --date (run with if: always())")
    parser.add_argument("--date", type=str, help="UTC date (YYYY-MM-DD) the claim modes operate on; defaults to today. Pinned across claim/post/finalize.")
    parser.add_argument("--slot", choices=["morning", "afternoon", "night"], help="3-slot mode: which slot (morning=text, afternoon=image, night=video) to claim/post/finalize/preview")
    args = parser.parse_args()

    if args.reset:
        reset_state()
        return

    # The claim/post/finalize trio must agree on ONE date even across a midnight
    # UTC flip, so the workflow pins --date from the claim step.
    claim_date = args.date or _today_utc()

    # --- 3-slot mode (driven by the gated daily_3slot workflow) ---
    if args.slot:
        if args.claim:
            sys.exit(run_claim_slot(claim_date, args.slot))
        if args.finalize:
            sys.exit(run_finalize_slot(claim_date, args.slot))
        if args.post_claimed:
            sys.exit(run_post_slot(claim_date, args.slot))
        if args.preview:
            sys.exit(preview_slot(args.slot, args.day))
        print("--slot requires one of --claim / --post-claimed / --finalize / --preview")
        sys.exit(2)

    # Idempotency fence modes (used by the CI workflow). See docs/IDEMPOTENCY.md.
    if args.claim:
        sys.exit(run_claim(claim_date))
    if args.finalize:
        sys.exit(run_finalize(claim_date))

    # Idempotency: skip if today's post already succeeded.
    # Exceptions: --preview (informational), --day N (manual override), --validate (meta).
    if not args.day and not args.preview and not args.validate and already_posted_today():
        today = datetime.now(timezone.utc).date().isoformat()
        print(f"✅ Already posted today ({today}) — skipping.")
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

    # Determine which day to post. --post-claimed pins the day from the claim file
    # for claim_date (written + pushed BEFORE this step). Fail-closed: only post
    # when a live 'claimed' record exists — never fall back to state, since posting
    # without the durable fence is exactly what risks a duplicate.
    if args.post_claimed:
        if claim_status(claim_date) != "claimed":
            print(f"❌ No live claim (status 'claimed') for {claim_date} — refusing to post.")
            sys.exit(1)
        day_num = read_claim(claim_date)["day"]
    else:
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

    # Resolve video for this day. Opt-in via --video or POST_VIDEO env so the
    # default behavior (image posts) is unchanged until video is enabled.
    post_video = args.video or os.getenv("POST_VIDEO", "").strip().lower() in ("1", "true", "yes", "on")
    video_path = resolve_video_path(day_num) if post_video else None

    # The media that will actually be attached (post() prefers video over image).
    media_path = video_path or image_path

    # Build text components
    fallback_tweet = format_post(entry, total_days)  # Full text-only format
    image_text = format_image_text(entry)             # Image tweet caption
    body_text = entry["text"]                         # Constitutional text for replies

    # Display preview
    print(f"\n{'='*60}")
    print(f"  Day {day_num}/{total_days} — {entry['section']}")
    print(f"{'='*60}")

    if media_path:
        media_kind = "VIDEO" if video_path else "IMAGE"
        media_icon = "🎬" if video_path else "🖼️"
        print(f"\n  {media_icon}  {media_kind} TWEET (Tweet 1):")
        print(f"  {'-'*56}")
        print(f"  {image_text}")
        print(f"  + {media_kind.lower()}: {Path(media_path).name}")
        print(f"  ({weighted_len(image_text)} chars)")
        print(f"\n  💬 REPLY THREAD (Tweet 2+):")
        print(f"  {'-'*56}")
        print(f"  {body_text}")
        print(f"  ({weighted_len(body_text)} chars)")
    else:
        print(f"\n  📝 TEXT-ONLY (no media found):")
        print(f"  {'-'*56}")
        print(f"  {fallback_tweet}")
        print(f"  ({weighted_len(fallback_tweet)} chars)")

    print(f"\n{'='*60}\n")

    # Preview mode — stop here
    if args.preview:
        if media_path:
            media_kind = "Video" if video_path else "Image"
            print(f"✅ {media_kind} post ready — {Path(media_path).name}")
            if weighted_len(body_text) > REPLY_CHAR_LIMIT:
                from platforms.x_twitter import split_text_for_replies
                chunks = split_text_for_replies(body_text, max_len=REPLY_CHAR_LIMIT)
                print(f"   Reply thread will be {len(chunks)} tweet(s)")
                for i, chunk in enumerate(chunks):
                    print(f"\n   Reply {i+1} ({weighted_len(chunk)} chars):")
                    print(f"   {chunk}")
        else:
            print("⚠️  No media available — will post text-only")
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
        # Gate on the text actually sent: when media is attached, tweet 1 is the
        # short image_text (the long fallback_tweet is never sent on that path).
        gate_text = image_text if media_path else fallback_tweet
        if not platform.validate_length(gate_text):
            print(f"⚠️  Post too long for {platform.name} ({weighted_len(gate_text)} > {platform.max_length})")
            all_success = False
            continue

        # Only pass video_path when set, so a platform whose post() predates the
        # video parameter (e.g. Bluesky on its feature branch) still works.
        post_kwargs = {
            "image_path": image_path,
            "image_text": image_text,
            "body_text": body_text,
            "reply_char_limit": REPLY_CHAR_LIMIT,
        }
        if video_path:
            post_kwargs["video_path"] = video_path

        result = platform.post(fallback_tweet, **post_kwargs)
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
