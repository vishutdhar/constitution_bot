"""
Regression tests for XTwitterPlatform media posting (no network, no pytest).

Covers:
  - _upload_video: X's chunked video upload finishes asynchronously and tweepy
    returns the media object even when the transcode FAILED, so _upload_video
    inspects processing_info and only returns a media_id on "succeeded"; it must
    also never raise (broad except), so the caller can always fall back.
  - post(): if the lead tweet is live but a reply fails, the result must be a
    PARTIAL success (so bot.py advances state and does not re-post the lead,
    which would duplicate it).

Run:  python tests/test_video_upload.py     (exit 0 = pass, 1 = fail)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tweepy  # noqa: E402
import platforms.x_twitter as xmod  # noqa: E402
from platforms.x_twitter import XTwitterPlatform  # noqa: E402


# --------------------------------------------------------------------------
# _upload_video stubs
# --------------------------------------------------------------------------
class FakeMedia:
    """Mimics tweepy.models.Media: media_id and/or processing_info, both optional."""

    def __init__(self, media_id=None, processing_info="__omit__"):
        if media_id is not None:
            self.media_id = media_id
        if processing_info != "__omit__":
            self.processing_info = processing_info


class FakeAPI:
    """Stands in for the authenticated v1.1 tweepy.API."""

    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc

    def media_upload(self, **kwargs):
        assert kwargs.get("chunked") is True
        assert kwargs.get("media_category") == "tweet_video"
        assert kwargs.get("wait_for_async_finalize") is True
        if self.exc:
            raise self.exc
        return self.result


def _check(name, api, expected, failures):
    platform = XTwitterPlatform("k", "s", "t", "ts")
    platform._api_v1 = api
    got = platform._upload_video("/fake/day_01.mp4")
    if got != expected:
        failures.append(f"{name}: got {got!r}, expected {expected!r}")


# --------------------------------------------------------------------------
# post() / reply-thread stubs
# --------------------------------------------------------------------------
class FakeClient:
    """
    Stands in for tweepy.Client. Can fail a tweet by raising a TweepyException,
    or by returning a 200 with no data (Response(data=None)) — which tweepy does
    NOT raise on, so `response.data["id"]` then raises a non-Tweepy TypeError.
    """

    def __init__(self, fail_lead=False, fail_replies=False, none_lead=False, none_replies=False):
        self.fail_lead = fail_lead
        self.fail_replies = fail_replies
        self.none_lead = none_lead
        self.none_replies = none_replies
        self.n = 0

    def create_tweet(self, **kwargs):
        self.n += 1
        is_reply = kwargs.get("in_reply_to_tweet_id") is not None
        if (is_reply and self.fail_replies) or (not is_reply and self.fail_lead):
            raise tweepy.TweepyException("simulated failure")
        if (is_reply and self.none_replies) or (not is_reply and self.none_lead):
            return type("R", (), {"data": None})()  # 200 with no data
        return type("R", (), {"data": {"id": f"id{self.n}"}})()


def _post(client, **post_kwargs):
    p = XTwitterPlatform("k", "s", "t", "ts")
    p._username = "USC1787"
    p._client = client
    p._upload_image = lambda path: "media1"  # pretend the image uploaded
    return p.post("fallback text", image_path="/x.png", image_text="cap", **post_kwargs)


def test_post(failures):
    # Long body so split_text_for_replies produces multiple reply chunks.
    body = " ".join(f"word{i}" for i in range(120))

    # Lead + replies all succeed -> full success, not partial.
    r = _post(FakeClient(), body_text=body, reply_char_limit=280)
    if not (r["success"] and not r["partial"] and r["media_kind"] == "image" and r["thread_length"] > 1):
        failures.append(f"post_full_success: {r}")

    # Lead posts, a reply fails -> PARTIAL success (state should advance).
    r = _post(FakeClient(fail_replies=True), body_text=body, reply_char_limit=280)
    if not (r["success"] and r["partial"] and r["tweet_id"] is not None and r["media_kind"] == "image"):
        failures.append(f"post_partial: {r}")

    # Lead itself fails -> hard failure, nothing posted.
    r = _post(FakeClient(fail_lead=True), body_text=body, reply_char_limit=280)
    if not (r["success"] is False and r["partial"] is False and r["tweet_id"] is None):
        failures.append(f"post_lead_failure: {r}")

    # Lead live, but a reply returns 200-with-no-data (TypeError on id, a
    # NON-Tweepy error) -> must still be a PARTIAL, not an uncaught crash.
    r = _post(FakeClient(none_replies=True), body_text=body, reply_char_limit=280)
    if not (r["success"] and r["partial"] and r["tweet_id"] is not None):
        failures.append(f"post_partial_nondata_reply: {r}")

    # Lead returns 200-with-no-data -> AMBIGUOUS: uncertain (consumed, NOT a
    # retryable failure) so the idempotency layer never re-posts a maybe-live lead.
    r = _post(FakeClient(none_lead=True), body_text=body, reply_char_limit=280)
    if not (r["success"] is True and r.get("uncertain") is True and r["tweet_id"] is None):
        failures.append(f"post_lead_nondata: {r}")


def main():
    failures = []

    # --- _upload_video ---
    _check("succeeded", FakeAPI(FakeMedia(123, {"state": "succeeded"})), "123", failures)
    _check("failed_state", FakeAPI(FakeMedia(123, {"state": "failed", "error": {"name": "InvalidMedia"}})), None, failures)
    _check("error_key", FakeAPI(FakeMedia(123, {"state": "in_progress", "error": {"code": 1}})), None, failures)
    _check("no_processing_info", FakeAPI(FakeMedia(456)), "456", failures)
    _check("no_media_id", FakeAPI(FakeMedia(None, {"state": "succeeded"})), None, failures)
    _check("tweepy_exception", FakeAPI(exc=tweepy.TweepyException("boom")), None, failures)
    # A non-TweepyException from inside tweepy (e.g. KeyError on a malformed
    # processing_info) must also be caught and fall back, not crash.
    _check("keyerror_from_tweepy", FakeAPI(exc=KeyError("state")), None, failures)

    platform = XTwitterPlatform("k", "s", "t", "ts")
    platform._api_v1 = None
    if platform._upload_video("/fake.mp4") is not None:
        failures.append("api_none: expected None")

    # --- post() partial-success handling (no real sleeps during retries) ---
    orig_sleep = xmod.time.sleep
    xmod.time.sleep = lambda *a, **k: None
    try:
        test_post(failures)
    finally:
        xmod.time.sleep = orig_sleep

    if failures:
        print("FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("All media-posting cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
