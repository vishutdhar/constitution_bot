"""
Regression tests for the 3-slot posting logic (no network, no pytest).

Covers the per-(date,slot) claim fence, the once-per-date day pin + state advance,
slot independence, the compose format selection (text/image/video + worst-5 night
downgrade), and finalize status mapping.

Run:  python tests/test_slots.py   (exit 0 = pass, 1 = fail)
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot  # noqa: E402


def today():
    return datetime.now(timezone.utc).date().isoformat()


def setup_tmp(tmp, *, state_day=5, image_days=(), video_days=()):
    tmp = Path(tmp)
    bot.CLAIMS_DIR = tmp / "claims"
    bot.STATE_FILE = tmp / "state.json"
    bot.POSTS_FILE = tmp / "posts.json"
    bot.LOG_FILE = tmp / "post_log.json"
    bot.IMAGE_MAPPING_FILE = tmp / "image_mapping.json"
    bot.IMAGESV2_DIR = tmp / "images_v2"
    bot.VIDEOS_DIR = tmp / "videos"
    bot.IMAGESV2_DIR.mkdir(parents=True, exist_ok=True)
    bot.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    bot.STATE_FILE.write_text(json.dumps({"current_day": state_day}))
    bot.POSTS_FILE.write_text(
        json.dumps([{"day": d, "section": f"S{d}", "hashtags": "#x", "text": f"text {d}"} for d in range(1, 78)])
    )
    bot.IMAGE_MAPPING_FILE.write_text("{}")
    for d in image_days:
        (bot.IMAGESV2_DIR / f"day_{d:02d}_s.png").write_text("img")
    for d in video_days:
        (bot.VIDEOS_DIR / f"day_{d:02d}.mp4").write_text("vid")


def main():
    failures = []

    def check(name, cond):
        if not cond:
            failures.append(name)

    # Pin advances state ONCE per date across all three slots; all slots share the day.
    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5)
        D = "2026-01-01"
        for slot in ("morning", "afternoon", "night"):
            check(f"claim_{slot}_rc", bot.run_claim_slot(D, slot) == 0)
        check("state_advanced_once", json.load(open(bot.STATE_FILE))["current_day"] == 6)
        days = {s: bot.read_claim(bot._slot_key(D, s))["day"] for s in ("morning", "afternoon", "night")}
        check("all_slots_day5", set(days.values()) == {5})
        check("all_slots_claimed", all(bot.claim_status(bot._slot_key(D, s)) == "claimed" for s in days))
        # Re-claiming a slot writes nothing new and does not advance again.
        before = bot.claim_path(bot._slot_key(D, "morning")).read_text()
        bot.run_claim_slot(D, "morning")
        check("reclaim_noop", bot.claim_path(bot._slot_key(D, "morning")).read_text() == before)
        check("state_still_6", json.load(open(bot.STATE_FILE))["current_day"] == 6)

    # compose_slot format selection.
    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5, image_days=(5, 10), video_days=(5, 10))
        posts = {p["day"]: p for p in bot.load_posts()}
        m = bot.compose_slot(posts[5], 5, 77, "morning")
        check("morning_text", m["kind"] == "text" and m["media_path"] is None and "Read today" in m["lead_text"])
        a = bot.compose_slot(posts[5], 5, 77, "afternoon")
        check("afternoon_image", a["kind"] == "image" and a["media_path"].endswith("day_05_s.png") and a["body_text"] == "text 5")
        n = bot.compose_slot(posts[5], 5, 77, "night")
        check("night_video", n["kind"] == "video" and n["is_video"] and n["media_path"].endswith("day_05.mp4"))
        # Worst-5 night (day 10) downgrades to image even though a video exists.
        n10 = bot.compose_slot(posts[10], 10, 77, "night")
        check("night_worst5_image", n10["kind"] == "image" and not n10["is_video"] and n10["media_path"].endswith("day_10_s.png"))
        # Night with NO video available falls back to image.
        setup_tmp(tmp, state_day=5, image_days=(6,), video_days=())
        posts = {p["day"]: p for p in bot.load_posts()}
        n6 = bot.compose_slot(posts[6], 6, 77, "night")
        check("night_no_video_fallback", n6["kind"] == "image")

    # Fail-closed: posting a slot with no live claim returns nonzero.
    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5)
        check("post_no_claim_fails", bot.run_post_slot("2026-01-01", "morning") == 1)

    # Finalize maps the slot's log entry to a claim status.
    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5)
        D = today()
        bot.write_claim(bot._slot_key(D, "morning"), 5, "claimed")
        bot.LOG_FILE.write_text(json.dumps([
            {"timestamp": datetime.now(timezone.utc).isoformat(), "slot": "afternoon", "success": True},
            {"timestamp": datetime.now(timezone.utc).isoformat(), "slot": "morning", "success": True, "partial": False},
        ]))
        bot.run_finalize_slot(D, "morning")
        check("finalize_morning_posted", bot.claim_status(bot._slot_key(D, "morning")) == "posted")
        # afternoon has a log entry but no claim -> finalize is a no-op (no crash).
        bot.run_finalize_slot(D, "afternoon")
        check("finalize_no_claim_noop", bot.read_claim(bot._slot_key(D, "afternoon")) is None)

    # A long text slot must reach the threader, not be rejected by the 1400 preflight
    # gate (Codex P2). The media caption gate still applies.
    class FakePlatform:
        name = "X"
        max_length = 1400

        def __init__(self):
            self.posted = []

        def validate_length(self, text):
            return len(text) <= self.max_length

        def post(self, text, **kw):
            self.posted.append((text, kw))
            return {"success": True}

    orig_init = bot.init_platforms
    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5)
        fp = FakePlatform()
        bot.init_platforms = lambda: [fp]
        try:
            comp = {"slot": "morning", "kind": "text", "media_path": None, "is_video": False,
                    "lead_text": "X" * 2200, "image_text": None, "body_text": None}
            rc = bot._post_composed(comp, {"day": 75, "section": "S75"})
        finally:
            bot.init_platforms = orig_init
        check("long_text_not_skipped", rc == 0 and len(fp.posted) == 1)

        fp2 = FakePlatform()
        bot.init_platforms = lambda: [fp2]
        try:
            comp2 = {"slot": "afternoon", "kind": "image", "media_path": "/x.png", "is_video": False,
                     "lead_text": "f", "image_text": "Y" * 1500, "body_text": "b"}
            rc2 = bot._post_composed(comp2, {"day": 5, "section": "S5"})
        finally:
            bot.init_platforms = orig_init
        check("long_caption_skipped", rc2 == 1 and len(fp2.posted) == 0)

    if failures:
        print("FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("All 3-slot cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
