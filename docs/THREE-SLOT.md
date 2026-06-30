# Three-slot posting

One section per day, posted three ways at three times, to add reach and a built-in
format test without new content:

| Slot | Time (UTC) | Format | Asset | Copy hook |
|---|---|---|---|---|
| morning | 12:23 | text only | none (the clause is the post) | "Read today's clause" |
| afternoon | 16:47 | image | `images_v2/day_NN_*.png` | "See today's clause" |
| night | 20:11 | video | `video/videos/day_NN.mp4` | "Hear today's clause" |

The **corrected verbatim text is carried in the tweet copy in every slot** (the
morning post body, and the caption + reply thread on the image and video posts).
The image and video assets are used as-is. This is the no-spend accuracy plan: even
where an old baked image or narration is imperfect, the words people read are correct.

Why this is needed: the verbatim text correction (PR #8, `9245e13`) fixed 25 days
AFTER the `images_v2` cards and the ElevenLabs audio (hence the videos) were baked,
so **21 of those 25 days have wrong baked content**. We do not re-bake them under the
no-spend rule; the corrected copy is the fix. Regenerating those 21 assets is the
deferred future work, documented in `docs/STATE.md` and `plan.md`. This 3-slot
feature itself merged in PR #9 (`7dff8be`).

The image lookup prefers `images_v2/` and falls back to the legacy `images/` set via
`image_mapping`, so a day missing from `images_v2/` still resolves a card.

## Accuracy exceptions and night degradation
The night slot degrades to a safe option in three layers:
- **Worst-5 night (days 10, 23, 58, 69, 75):** the video narration is materially
  wrong (old text baked before the verbatim correction), so at night these post the
  **image** instead of the video. See `WORST5_NIGHT_DAYS` in `bot.py`.
- **No video file present:** the night slot falls back to the image. Videos are
  gitignored and not present on the CI runner yet, so until they are published (a
  GitHub Release asset), the night slot posts the image. The storage decision and its
  options live in `docs/VIDEO-POSTING.md` (Production blocker). That blocker now gates
  the night slot, not just the legacy `--video` path.
- **Video rejected at upload:** when a video IS present but its upload or transcode is
  rejected, the post degrades to the day's image (passed alongside the video as an
  upload fallback) rather than to text only. The caption hook follows the actual media
  kind, so a downgraded night image says "See", not "Hear".

## Idempotency
Reuses the claim fence (`docs/IDEMPOTENCY.md`), generalized to per-(date, slot):
- Each slot has its own claim file `claims/<date>__<slot>.json`, claimed and pushed
  before its post.
- The section day is pinned once per date in `claims/<date>__pin.json` at claim
  time, and `state.json` advances exactly once per date AFTER the first slot
  actually posts (a day whose every slot fails is retried next date, not skipped).
- `--post-claimed --slot` is fail-closed: it refuses unless a live `claimed` record
  exists for that slot.

## CLI
```
python bot.py --preview --slot morning|afternoon|night [--day N]   # preview, no post
python bot.py --claim       --slot <slot> --date <YYYY-MM-DD>
python bot.py --post-claimed --slot <slot> --date <YYYY-MM-DD>
python bot.py --finalize     --slot <slot> --date <YYYY-MM-DD>
```

## Going live
The 3-slot workflow (`.github/workflows/daily_3slot.yml`) is **gated off**: the job
runs only when the repo variable `ENABLE_3SLOT == 'true'`. To switch over:
1. Set `ENABLE_3SLOT=true` (repo Settings -> Variables).
2. **Disable `daily_post.yml`** (the old single-post workflow) so the day is not
   double-posted.
Until both are done, the old single daily post keeps running and the 3-slot workflow
triggers but skips.
