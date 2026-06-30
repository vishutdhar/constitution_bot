# Posting videos instead of images

The bot can attach the pre-rendered Remotion video (`video/videos/day_NN.mp4`)
to the day's X post instead of the static image. It is **opt-in and off by
default**, so existing image-posting behavior is unchanged until explicitly
enabled.

> Two ways to post video now exist. This doc covers the **legacy single-post path**
> (`--video` / `POST_VIDEO`) on `daily_post.yml`. The **go-forward video path is the
> 3-slot night slot** (`docs/THREE-SLOT.md`), gated by `ENABLE_3SLOT`, not
> `POST_VIDEO`. The upload mechanics below are shared by both. Two differences in the
> slot path: the night slot has a worst-5 exception (days 10, 23, 58, 69, 75 post the
> image, since their narration is wrong), and it passes the day's image as an upload
> fallback so a rejected video degrades to the image. The legacy `--video` path has no
> worst-5 guard.

## What changed

- `platforms/x_twitter.py` — new `_upload_video()` uses X's **chunked** upload
  (`media_category="tweet_video"`, `wait_for_async_finalize=True`) and verifies
  the async transcode reached `succeeded` before using the media. `post()` now
  resolves media in order: **video → image → text-only**.
- `platforms/base.py` — `post()` gained a `video_path` parameter.
- `bot.py` — resolves `video/videos/day_NN.mp4`, gated behind `--video` (CLI)
  or `POST_VIDEO` (env). When off, or when the file is missing, it falls back to
  the image exactly as before.
- `tests/test_video_upload.py` — dependency-free regression test for the
  upload/transcode failure handling.

## Enabling

```bash
python bot.py --day 1 --video       # one-off
POST_VIDEO=true python bot.py       # for the scheduled run
```

If the video file is missing at runtime, the bot logs a warning and falls back
to the image — it never fails the run just because a video is absent.

## Test safely before going live

1. Dry run (no credentials needed, nothing posted):
   ```bash
   python bot.py --preview --day 1 --video
   ```
2. One real post with credentials set, to confirm your X API tier permits video
   upload (this is the open question — video upload is heavier than image):
   ```bash
   python bot.py --day 1 --video      # posts day 1 to the live account
   ```
   Watch for `✅ Video uploaded` then `✅ Posted video tweet`. If the tier
   rejects video, you'll see the upload warning and an automatic image fallback.
3. Only after a successful manual video post should `POST_VIDEO` be enabled on
   the scheduled GitHub Actions run.

## Production blocker: where do the videos live?

The 77 rendered videos (~1.1 GB) are **gitignored**. The daily job runs on
GitHub Actions, so the files are not present there yet. This blocker is system wide:
it gates the 3-slot **night slot** too, not just the legacy `POST_VIDEO` path, so
until it is resolved the night slot falls back to the image even on non worst-5 days.
Pick one before enabling video in CI:

| Option | Notes |
|---|---|
| **GitHub Release asset** (recommended) | Upload `videos/` as a release; the workflow downloads the day's file before posting. Keeps the repo small; no LFS billing. |
| **Git LFS** | Commit the mp4s via LFS. Simple to consume, but uses LFS storage/bandwidth quota. |
| **Render in CI** | Install Remotion + headless Chrome on the runner and render on demand. Heaviest; avoid unless needed. |
| **Commit directly** | ~1.1 GB in git history — not recommended. |

Until one of these is wired up, keep `POST_VIDEO` off in the scheduled workflow.
Local/manual `--video` runs work today because the files exist on disk.

## Not included

Bluesky video is out of scope here (Bluesky is not on `main`, and its video
limits are tighter). X video first; revisit Bluesky separately.

### ⚠️ When merging the Bluesky branch

`base.py`'s `post()` gained a `video_path` parameter. The unmerged Bluesky
branch's `BlueskyPlatform.post()` does **not** have it, and `git` auto-merges
the two with no conflict — so a naive merge would `TypeError` the moment a
video run reached Bluesky. `bot.py` now only passes `video_path` when it is
set (so the default image path is merge-safe), but before enabling `POST_VIDEO`
with Bluesky present, add `video_path: str | None = None` to
`BlueskyPlatform.post()` (it can ignore it — Bluesky video is not implemented).
