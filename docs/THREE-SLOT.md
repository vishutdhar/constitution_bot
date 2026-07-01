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
  gitignored; in CI the workflow's "Fetch night video" step downloads the pinned
  day's file from the `videos-v1` GitHub Release before posting, and any fetch
  failure simply leaves the file absent (image fallback, never a lost slot). See
  `docs/VIDEO-POSTING.md` (Production storage) for the release layout.
- **Video rejected at upload:** when a video IS present but its upload or transcode is
  rejected, the post degrades to the day's image (passed alongside the video as an
  upload fallback) rather than to text only.

The caption hook is chosen at compose time from the format that was selected, so the
first two downgrades (worst-5 and no-file) build the caption as an image and say "See".
The third (upload rejected) is decided at runtime inside `post()` after the caption is
already built as a video ("Hear"), and the caption is not recomputed, so that fallback
image keeps the "Hear today's clause" wording. This is a known minor cosmetic mismatch
on a rare path (it needs a video file present, so it cannot occur while videos are
absent from the runner); the verbatim text in the post is still correct.

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
runs only when the repo variable `ENABLE_3SLOT == 'true'`. To switch over, do these in
order (disable the old poster first):
1. **Disable `daily_post.yml`** (the old single-post workflow). The two workflows share
   the same crons but write different claim keys, so they do not fence each other; if
   both are ever active at once a shared window double-posts.
2. Then set `ENABLE_3SLOT=true` (repo Settings -> Variables).

Order matters: disabling first means the worst case between the two changes is one
missed window, never a duplicate. While `ENABLE_3SLOT` is unset the 3-slot workflow
triggers on schedule but skips, so the old single daily post keeps running until step 2.
