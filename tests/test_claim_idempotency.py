"""
Regression tests for the claim-before-post idempotency fence (no pytest).

bot.py is pure here — these monkeypatch its module-level path constants to a temp
dir (like test_video_upload.py monkeypatches time.sleep) and exercise the claim
helpers + run_claim/run_finalize decision logic with file fixtures.

Run:  python tests/test_claim_idempotency.py   (exit 0 = pass, 1 = fail)
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tweepy  # noqa: E402
import bot  # noqa: E402
from platforms.x_twitter import XTwitterPlatform  # noqa: E402


def today():
    return datetime.now(timezone.utc).date().isoformat()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def setup_tmp(tmp, *, state_day=5, log=None):
    tmp = Path(tmp)
    bot.CLAIMS_DIR = tmp / "claims"
    bot.STATE_FILE = tmp / "state.json"
    bot.LOG_FILE = tmp / "post_log.json"
    bot.POSTS_FILE = tmp / "posts.json"
    bot.STATE_FILE.write_text(json.dumps({"current_day": state_day}))
    bot.POSTS_FILE.write_text(
        json.dumps([{"day": d, "section": f"S{d}", "hashtags": "#x", "text": "t"} for d in range(1, 78)])
    )
    if log is not None:
        bot.LOG_FILE.write_text(json.dumps(log))


def main():
    failures = []

    def check(name, cond):
        if not cond:
            failures.append(name)

    # finalize_status_for_result must stay coupled to the REAL result builders.
    p = XTwitterPlatform("k", "s", "t", "ts")
    p._username = "u"
    res_ok = p._post_ok("url", "id1", 3, "image")
    res_hard = p._post_failed(tweepy.TweepyException("x"), None, 0, "image")     # nothing landed
    res_partial = p._post_failed(tweepy.TweepyException("x"), "id1", 1, "image")  # lead live
    res_uncertain = p._post_uncertain("image", "lead 2xx, no id")               # ambiguous lead
    check("fin_posted", bot.finalize_status_for_result(res_ok) == "posted")
    check("fin_partial", bot.finalize_status_for_result(res_partial) == "posted_partial")
    check("fin_failed", bot.finalize_status_for_result(res_hard) == "failed")
    check("fin_uncertain", bot.finalize_status_for_result(res_uncertain) == "posted_unknown")

    # should_skip_for_claim truth table.
    check("skip_none", bot.should_skip_for_claim(None) is False)
    check("skip_failed", bot.should_skip_for_claim("failed") is False)
    check("skip_claimed", bot.should_skip_for_claim("claimed") is True)
    check("skip_posted", bot.should_skip_for_claim("posted") is True)
    check("skip_partial", bot.should_skip_for_claim("posted_partial") is True)
    check("skip_posted_unknown", bot.should_skip_for_claim("posted_unknown") is True)
    check("skip_unknown", bot.should_skip_for_claim("unknown") is True)

    # claim_status tolerant of missing/corrupt.
    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp)
        check("status_missing", bot.claim_status(today()) is None)
        bot.CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
        bot.claim_path(today()).write_text("{not json")
        check("status_corrupt", bot.claim_status(today()) == "unknown")

    # run_claim on a free day writes a 'claimed' record pinned to state day.
    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5)
        check("claim_rc", bot.run_claim(today()) == 0)
        c = bot.read_claim(today())
        check("claim_written", c is not None and c["status"] == "claimed" and c["day"] == 5)
        # Re-running must not change an existing claim (idempotent).
        before = bot.claim_path(today()).read_text()
        bot.run_claim(today())
        check("claim_idempotent", bot.claim_path(today()).read_text() == before)

    # A 'failed' claim is re-claimable (lead provably never landed).
    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5)
        bot.write_claim(today(), 5, "failed")
        bot.run_claim(today())
        check("claim_retry_after_failed", bot.claim_status(today()) == "claimed")

    # already_posted_today (legacy log) blocks claiming.
    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5, log=[{"timestamp": now_iso(), "success": True, "day": 5}])
        bot.run_claim(today())
        check("claim_skip_when_posted", bot.read_claim(today()) is None)

    # finalize maps the day's last log entry to a claim status.
    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5, log=[{"timestamp": now_iso(), "success": True, "partial": True, "day": 5}])
        bot.write_claim(today(), 5, "claimed")
        bot.run_finalize(today())
        check("finalize_partial", bot.claim_status(today()) == "posted_partial")

    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5, log=[{"timestamp": now_iso(), "success": False, "partial": False, "day": 5}])
        bot.write_claim(today(), 5, "claimed")
        bot.run_finalize(today())
        check("finalize_hard_failed", bot.claim_status(today()) == "failed")

    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5)  # no log at all
        bot.write_claim(today(), 5, "claimed")
        bot.run_finalize(today())
        # No outcome record but the claim was won => consumed (not retryable),
        # NOT 'failed' (which would re-open the day and risk a duplicate).
        check("finalize_nolog_unknown", bot.claim_status(today()) == "posted_unknown")

    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5)  # no claim
        bot.run_finalize(today())
        check("finalize_noclaim_noop", bot.read_claim(today()) is None)

    # End-to-end: an UNCERTAIN result through the real log_post -> run_finalize
    # path must finalize as 'posted_unknown' (regression: the 'uncertain' key must
    # survive log serialization, else it collapses to 'posted_partial').
    with tempfile.TemporaryDirectory() as tmp:
        setup_tmp(tmp, state_day=5)
        bot.write_claim(today(), 5, "claimed")
        bot.log_post({"day": 5, "section": "S5"}, p._post_uncertain("image", "no id"), "X")
        bot.run_finalize(today())
        check("finalize_uncertain_roundtrip", bot.claim_status(today()) == "posted_unknown")

    if failures:
        print("FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("All claim-idempotency cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
