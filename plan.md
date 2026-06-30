# Constitution Bot, Plan

Last updated: 2026-06-30. Current state: looping (state.json day 57). The media
assets and the 3-slot posting code are built and merged; 3-slot is gated off.

For the authoritative current state and direction, read `docs/STATE.md`. This file
is the tactical history of how the media relaunch was built, plus the preserved
playbook for the one piece of deferred work (regenerating wrong-content assets).

## Status of the media relaunch

The original goal of this plan (build per day image, audio, and video, then post
richer content) is done, though the final shape differs from the early sketch.

| Original phase | Status | What actually shipped |
|---|---|---|
| Phase 1, v2 images | Done | `images_v2/`, one parchment card per day |
| Phase 2a, ElevenLabs audio | Done | `audio_male/`, `audio_female/` narration |
| Phase 2b, short video | Done | Remotion (not ffmpeg) 1080x1920 videos in `video/videos/` |
| Phase 2c, wire into bot | Done, redesigned | Not a `media_mode` flag and not one-post-with-media. It became **3-slot**: three separate posts per day at three UTC times (text, image, video), gated by the repo variable `ENABLE_3SLOT`. See `docs/THREE-SLOT.md`. |

Two important pivots happened after the early sketch:

1. **Verbatim correction.** A fact check (PR #8) found 25 days of abridged or
   mislabeled text and corrected them to complete verbatim. The text policy is now
   verbatim in full.
2. **No-spend constraint.** The owner set a firm rule: no paid regeneration of images
   (OpenAI) or audio (ElevenLabs). Because the images and audio were baked from the
   pre-correction text, 21 of the 25 corrected days carry imperfect baked assets. We
   do not re-bake them; the corrected text is carried in every slot's caption and
   reply, and the worst-5 narration days post the image at night instead of the video.

## Deferred work: regenerate the 21 wrong-content assets

This is the real fix for the baked errors, deferred until spend is approved. The
playbook below is preserved from the original v2 image generation so it can be
repeated for just the affected days.

Affected days (wrong baked image and narration): 10, 23, 25, 29, 30, 37, 38, 41, 42,
43, 58, 60, 61, 62, 63, 66, 68, 69, 70, 73, 75. The materially wrong five are 10, 23,
58, 69, 75.

### Image regeneration playbook (one image per day)

- **Source of truth for prompts:** `chatgpt_image_prompts_v2.txt`, one prompt per day,
  each embedding that day's actual constitutional text.
- **Prompt template** (already baked into the v2 prompts):
  - Parchment scroll on a wooden desk, American flags, oil lamp, leather books,
    pocket watch, quill.
  - Title and text from that day's `constitution_posts.json` entry.
  - "The text must be completely readable, every single word must be accurate and legible."
  - "Research how the constitution looks like in reality and make it look as close to real as possible." (Confirmed necessary to get the realistic style.)
- **Generation method:** ChatGPT Pro UI, prompt by prompt, to avoid paid image APIs.
  Codex CLI cannot generate images; free image APIs cannot render long quoted text
  legibly; the OpenAI Images API is paid per image. Expect a typo retry loop (day 36
  once produced "juaicial", fixed from a regenerated image in PR #7).
- **Output rule (v2 then archive):** new PNGs land in `images_v2/` using the filename
  from each prompt's FILENAME line; nothing is deleted mid process; promote and
  archive only after review.
- **Image policy for long days:** show a verbatim excerpt on the parchment; the full
  text still rides in the thread and the video narration.

### Audio and video regeneration

- Regenerate the affected days' narration with ElevenLabs (Creator tier), same voice
  as the series for consistency. Spot check 18th century spellings.
- Re-render those days' videos: `node video/scripts/render-all.mjs <day> ...`
  (see `video/README.md`). After regeneration the worst-5 nights can revert to video.

## Architecture (current)

- **Bot:** `bot.py`, pure file IO; all git lives in the workflows.
- **Platform:** `platforms/x_twitter.py`, X API v2, threading, chunked video upload.
- **State and fence:** `state.json` plus the claim fence in `claims/` (see
  `docs/IDEMPOTENCY.md`).
- **Content:** `constitution_posts.json`, 77 sections, verbatim.
- **Media:** `images_v2/`, `audio_male/`, `audio_female/`, `video/`.
- **Automation:** GitHub Actions, crons 12:23 / 16:47 / 20:11 UTC. Live workflow is
  `daily_post.yml`; the gated 3-slot workflow is `daily_3slot.yml`.
- **Repo:** https://github.com/vishutdhar/constitution_bot (private).
- **X account:** @USC1787.

## Longer horizon

Growth, monetization, multi-platform, and the companion iOS app are tracked in
`FUTURE_PLANNING.md`.
