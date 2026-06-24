"""
Regression test for XTwitterPlatform._upload_video (no network, no pytest).

X's chunked video upload finishes asynchronously, and tweepy returns the media
object even when the async transcode FAILED. So _upload_video must inspect
processing_info itself and only return a media_id on a "succeeded" state.

Run:  python tests/test_video_upload.py     (exit 0 = pass, 1 = fail)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tweepy  # noqa: E402
from platforms.x_twitter import XTwitterPlatform  # noqa: E402


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
        # Video must go through the chunked + async-finalize path.
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


def main():
    failures = []

    # Async transcode succeeded -> media_id as string.
    _check("succeeded", FakeAPI(FakeMedia(123, {"state": "succeeded"})), "123", failures)
    # Async transcode failed -> None (caller falls back).
    _check("failed_state", FakeAPI(FakeMedia(123, {"state": "failed", "error": {"name": "InvalidMedia"}})), None, failures)
    # Error key present even mid-flight -> None.
    _check("error_key", FakeAPI(FakeMedia(123, {"state": "in_progress", "error": {"code": 1}})), None, failures)
    # Small video uploaded synchronously (no processing_info) -> media_id.
    _check("no_processing_info", FakeAPI(FakeMedia(456)), "456", failures)
    # Missing media_id -> None.
    _check("no_media_id", FakeAPI(FakeMedia(None, {"state": "succeeded"})), None, failures)
    # tweepy raised -> None.
    _check("tweepy_exception", FakeAPI(exc=tweepy.TweepyException("boom")), None, failures)

    # v1.1 API not initialized -> None.
    platform = XTwitterPlatform("k", "s", "t", "ts")
    platform._api_v1 = None
    if platform._upload_video("/fake.mp4") is not None:
        failures.append("api_none: expected None")

    if failures:
        print("FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("All _upload_video cases passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
